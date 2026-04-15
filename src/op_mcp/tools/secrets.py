"""MCP tool handlers for secret access.

Wraps:
  - op read                → op_read_secret
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from op_mcp.runner import OpRunner


def register(mcp: FastMCP, runner: OpRunner) -> None:
    """Register secret-access tool handlers."""

    @mcp.tool()
    async def op_read_secret(reference: str) -> str:
        """Read a single secret value from 1Password.

        The reference must be an `op://` URL like
        `op://Private/my-item/credential`. Returns the secret value
        as a plain string.

        Touch ID is prompted by the `op` CLI on first call per session.
        Subsequent calls reuse the cached session until it expires.
        """
        if not reference.startswith("op://"):
            raise ValueError(
                f"Invalid secret reference: {reference!r}. "
                "Must start with 'op://' (e.g. 'op://Private/item/field')."
            )
        return await runner.run("read", reference)
