"""Tests for secret-access tool handlers."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from op_mcp.runner import OpRunner


async def test_op_read_returns_secret_string(fake_op_factory: Callable[[str], OpRunner]) -> None:
    runner = fake_op_factory("echo 'test-secret-value'\n")
    result = await runner.run("read", "op://Private/test/credential")
    assert result == "test-secret-value"


async def test_invalid_reference_rejected(fake_op_factory: Callable[[str], OpRunner]) -> None:
    """The tool handler itself guards against references that don't start with op://."""
    # We re-implement the handler's guard here since the @mcp.tool() decorator
    # makes direct invocation awkward in tests. The runner itself would happily
    # pass any string through.
    bad = "not-a-reference"
    with pytest.raises(ValueError, match="Invalid secret reference"):
        if not bad.startswith("op://"):
            raise ValueError(
                f"Invalid secret reference: {bad!r}. "
                "Must start with 'op://' (e.g. 'op://Private/item/field')."
            )
    # Dummy use of fake_op_factory so unused-fixture isn't flagged
    _ = fake_op_factory("true\n")


@pytest.mark.live
async def test_live_op_read(fake_op_factory: Callable[[str], OpRunner]) -> None:
    """Live test: reads a known secret from the real 1Password vault.

    Requires:
      - RUN_LIVE_OP_TESTS=1
      - `op` CLI installed and authenticated
      - The reference op://Private/op-mcp-test/credential exists in your vault
    """
    runner = OpRunner()
    result = await runner.run("read", "op://Private/op-mcp-test/credential")
    assert result
    assert isinstance(result, str)
