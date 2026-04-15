"""Subprocess glue for invoking the `op` CLI.

Every tool handler calls `OpRunner.run(...)` and either gets parsed JSON
back or an `OpCliError` that tells the MCP client what went wrong.

Design notes:

- One process per invocation. No shared state, no cached client, no mutex.
  The `op` CLI's biometric auth runs on every call (or uses its own cached
  session inside the OS keychain — that's `op`'s job, not ours). Stateless
  on our side means no session drift.

- `--format=json` is passed on commands that support it (`item get`,
  `item list`). `op read` returns a raw secret value; we return it as a
  string. Callers tell `run()` which mode they want via `expect_json`.

- Timeouts default to 15s. The `op` CLI's slowest call is the initial
  Touch ID prompt; after that, reads are instant. 15s is generous.

- stderr is captured and surfaced on error. `op` writes its prompts and
  error messages to stderr; preserving it helps diagnose failures
  (expired session, missing item, biometric declined, etc.).
"""

from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_BINARY = "op"


class OpCliError(Exception):
    """An `op` CLI invocation failed.

    Attributes:
        argv: The command line that was run, for debugging.
        returncode: Exit code from the CLI.
        stderr: Captured stderr (may contain auth prompts or error text).
        stdout: Captured stdout (may contain partial output before failure).
    """

    def __init__(
        self,
        argv: list[str],
        returncode: int,
        stderr: str,
        stdout: str,
        message: str | None = None,
    ) -> None:
        self.argv = argv
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout
        detail = message or f"op CLI exited {returncode}"
        if stderr.strip():
            detail += f": {stderr.strip()}"
        super().__init__(detail)


class OpBinaryNotFoundError(OpCliError):
    """The `op` binary is not on PATH."""

    def __init__(self, binary: str) -> None:
        super().__init__(
            argv=[binary],
            returncode=-1,
            stderr="",
            stdout="",
            message=(
                f"`{binary}` binary not found on PATH. "
                "Install the 1Password CLI (https://developer.1password.com/docs/cli/) "
                "and ensure it is on PATH."
            ),
        )


class OpOutputNotJSONError(OpCliError):
    """The CLI exited 0 but stdout didn't parse as JSON when JSON was expected."""

    def __init__(self, argv: list[str], stdout: str, stderr: str, parse_error: str) -> None:
        super().__init__(
            argv=argv,
            returncode=0,
            stderr=stderr,
            stdout=stdout,
            message=(
                f"op CLI returned non-JSON output despite --format=json "
                f"(JSON parse error: {parse_error})."
            ),
        )


@dataclass(frozen=True)
class OpRunner:
    """Configured invoker for the `op` CLI.

    Frozen dataclass so instances are safe to share across concurrent
    tool handlers. No mutable state; each `run()` call spawns a fresh
    subprocess.
    """

    binary: str = DEFAULT_BINARY
    default_timeout: float = DEFAULT_TIMEOUT_SECONDS

    def resolve_binary(self) -> str:
        """Return the absolute path to the binary, or raise."""
        path = shutil.which(self.binary)
        if path is None:
            raise OpBinaryNotFoundError(self.binary)
        return path

    async def run(
        self,
        *args: str,
        expect_json: bool = False,
        timeout: float | None = None,
    ) -> Any:
        """Invoke `op <args...>` and return parsed JSON or raw text.

        Args:
            *args: CLI arguments after the `op` binary. Callers must include
                `--format=json` themselves when appropriate — unlike the jams
                CLI, `op` doesn't accept `--format json` uniformly across
                subcommands. The `expect_json` flag only controls parsing,
                not argument injection.
            expect_json: If True, parse stdout as JSON. If False (default),
                return stdout as a stripped string.
            timeout: Override the runner's default timeout in seconds.

        Returns:
            Parsed JSON (dict, list, etc.) when `expect_json=True`.
            Stripped stdout string when `expect_json=False`.

        Raises:
            OpBinaryNotFoundError: `op` is not on PATH.
            OpCliError: CLI exited non-zero.
            OpOutputNotJSONError: `expect_json=True` but stdout wasn't JSON.
        """
        binary_path = self.resolve_binary()
        argv = [binary_path, *args]
        effective_timeout = timeout if timeout is not None else self.default_timeout

        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=effective_timeout,
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise OpCliError(
                argv=argv,
                returncode=-1,
                stderr="",
                stdout="",
                message=f"op CLI timed out after {effective_timeout}s",
            ) from None

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        returncode = proc.returncode if proc.returncode is not None else -1

        if returncode != 0:
            raise OpCliError(
                argv=argv,
                returncode=returncode,
                stderr=stderr,
                stdout=stdout,
            )

        if not expect_json:
            return stdout.strip()

        try:
            return json.loads(stdout) if stdout.strip() else None
        except json.JSONDecodeError as exc:
            raise OpOutputNotJSONError(
                argv=argv,
                stdout=stdout,
                stderr=stderr,
                parse_error=str(exc),
            ) from exc

    async def version(self) -> str:
        """Return the `op` CLI version string. Used for startup validation."""
        return await self.run("--version", timeout=5.0)
