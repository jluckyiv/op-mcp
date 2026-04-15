"""MCP server entrypoint for the `op` CLI wrapper.

Run with `op-mcp` (installed entrypoint) or `python -m op_mcp.server`.
Communicates over stdio using the MCP protocol.

Architecture:

    MCP client (Cowork, Claude Code, Claude Desktop)
      ↓ stdio (MCP protocol)
    op-mcp (this process)
      ↓ asyncio.create_subprocess_exec
    op CLI (1Password CLI)
      ↓ biometric prompt (Touch ID) + 1Password desktop app
    1Password vaults

The server itself holds no state. Every tool call spawns a fresh `op`
subprocess. `op` caches its own session inside the 1Password desktop
app — we don't manage sessions, tokens, or credentials.
"""

from __future__ import annotations

import logging
import shutil
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from op_mcp import __version__
from op_mcp.runner import DEFAULT_BINARY, OpBinaryNotFoundError, OpRunner
from op_mcp.tools import items as item_tools
from op_mcp.tools import secrets as secret_tools

logger = logging.getLogger("op_mcp")


def _configure_logging() -> None:
    """Log to stderr so stdout stays clean for the MCP protocol."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        stream=sys.stderr,
    )


def _preflight_binary_check(binary: str) -> None:
    """Fast existence check at startup. Full validation happens on first call."""
    path = shutil.which(binary)
    if path is None:
        logger.error(
            "`%s` binary not found on PATH. "
            "Install the 1Password CLI before starting this server.",
            binary,
        )
        raise OpBinaryNotFoundError(binary)
    logger.info("Found op binary: %s", path)


def build_server(runner: OpRunner | None = None) -> FastMCP:
    """Build and return a configured MCP server.

    Split out from `main()` so tests can instantiate the server without
    spawning the stdio transport.
    """
    runner = runner or OpRunner()
    mcp = FastMCP("op-mcp")
    register_tools(mcp, runner)
    return mcp


def register_tools(mcp: FastMCP, runner: OpRunner) -> None:
    """Register all tool handlers with the MCP server."""
    secret_tools.register(mcp, runner)
    item_tools.register(mcp, runner)

    @mcp.tool()
    async def op_version() -> str:
        """Return the version of the `op` CLI binary. No auth required."""
        return (await runner.version()).strip()

    @mcp.tool()
    async def op_whoami() -> Any:
        """Return the currently authenticated 1Password account.

        Useful for confirming which account is active and that auth is working,
        without attempting a real secret read.
        """
        return await runner.run("whoami", "--format=json", expect_json=True)

    @mcp.tool()
    async def op_ping() -> dict[str, str]:
        """Liveness check for the MCP server. Does not invoke the `op` CLI."""
        return {
            "status": "ok",
            "wrapper_version": __version__,
            "binary": runner.binary,
        }


def main() -> None:
    """Console entrypoint for `op-mcp`."""
    _configure_logging()
    logger.info("op-mcp %s starting", __version__)

    try:
        _preflight_binary_check(DEFAULT_BINARY)
    except OpBinaryNotFoundError as exc:
        logger.error("Startup failed: %s", exc)
        sys.exit(1)

    mcp = build_server()
    mcp.run()


if __name__ == "__main__":
    main()
