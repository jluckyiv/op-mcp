"""Tests for the subprocess runner."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from op_mcp.runner import (
    OpBinaryNotFoundError,
    OpCliError,
    OpOutputNotJSONError,
    OpRunner,
)


async def test_run_returns_stripped_text(fake_op_factory: Callable[[str], OpRunner]) -> None:
    runner = fake_op_factory("echo 'my-secret-value'\n")
    result = await runner.run("read", "op://Private/x/y")
    assert result == "my-secret-value"


async def test_run_returns_parsed_json(fake_op_factory: Callable[[str], OpRunner]) -> None:
    runner = fake_op_factory("echo '[{\"id\":\"abc\",\"title\":\"Test\"}]'\n")
    result = await runner.run("item", "list", "--format=json", expect_json=True)
    assert result == [{"id": "abc", "title": "Test"}]


async def test_run_nonzero_raises_cli_error(fake_op_factory: Callable[[str], OpRunner]) -> None:
    runner = fake_op_factory("echo 'boom' >&2\nexit 2\n")
    with pytest.raises(OpCliError) as excinfo:
        await runner.run("read", "op://bogus")
    assert excinfo.value.returncode == 2
    assert "boom" in excinfo.value.stderr


async def test_run_bad_json_raises(fake_op_factory: Callable[[str], OpRunner]) -> None:
    runner = fake_op_factory("echo 'not json'\n")
    with pytest.raises(OpOutputNotJSONError):
        await runner.run("item", "list", expect_json=True)


async def test_missing_binary_raises(empty_path: None) -> None:  # noqa: ARG001
    runner = OpRunner()
    with pytest.raises(OpBinaryNotFoundError):
        await runner.run("read", "op://x/y/z")


async def test_timeout_raises(fake_op_factory: Callable[[str], OpRunner]) -> None:
    runner = fake_op_factory("sleep 2\n")
    with pytest.raises(OpCliError) as excinfo:
        await runner.run("read", "op://slow", timeout=0.2)
    assert "timed out" in str(excinfo.value).lower()
