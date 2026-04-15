"""Tests for server wiring and infrastructure tools."""

from __future__ import annotations

from collections.abc import Callable

from op_mcp import __version__
from op_mcp.runner import OpRunner
from op_mcp.server import build_server


def test_build_server_returns_configured_mcp(fake_op_factory: Callable[[str], OpRunner]) -> None:
    runner = fake_op_factory("echo '2.33.1'\n")
    mcp = build_server(runner)
    assert mcp.name == "op-mcp"


async def test_op_ping_reports_wrapper_version(
    fake_op_factory: Callable[[str], OpRunner],
) -> None:
    runner = fake_op_factory("echo '2.33.1'\n")
    ping = await runner.version()
    # Runner.version() uses `--version`; the fake just echoes regardless.
    assert ping.strip() == "2.33.1"
    assert __version__  # sanity


async def test_op_whoami_returns_dict(fake_op_factory: Callable[[str], OpRunner]) -> None:
    runner = fake_op_factory(
        'echo \'{"url":"my.1password.com","email":"user@example.com","userUUID":"abc123"}\'\n'
    )
    result = await runner.run("whoami", "--format=json", expect_json=True)
    assert isinstance(result, dict)
    assert "email" in result
