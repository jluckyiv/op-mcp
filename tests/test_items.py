"""Tests for item and vault tool handlers."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from op_mcp.runner import OpRunner


async def test_op_list_vaults_returns_list(fake_op_factory: Callable[[str], OpRunner]) -> None:
    runner = fake_op_factory('echo \'[{"id":"abc","name":"Private","type":"P"}]\'\n')
    result = await runner.run("vault", "list", "--format=json", expect_json=True)
    assert isinstance(result, list)
    assert result[0]["name"] == "Private"


async def test_op_get_item_returns_dict(fake_op_factory: Callable[[str], OpRunner]) -> None:
    runner = fake_op_factory(
        'echo \'{"id":"xyz","title":"My Item","fields":[{"id":"username","value":"alice"}]}\'\n'
    )
    result = await runner.run("item", "get", "My Item", "--format=json", expect_json=True)
    assert isinstance(result, dict)
    assert result["title"] == "My Item"
    assert result["fields"][0]["value"] == "alice"


@pytest.mark.live
async def test_live_list_vaults() -> None:
    """Live test: lists vaults from the real 1Password account."""
    runner = OpRunner()
    result = await runner.run("vault", "list", "--format=json", expect_json=True)
    assert isinstance(result, list)
    assert len(result) > 0


@pytest.mark.live
async def test_live_get_item() -> None:
    """Live test: fetches full item detail.

    Requires an item named 'op-mcp-test' in the Private vault.
    """
    runner = OpRunner()
    result = await runner.run(
        "item", "get", "op-mcp-test", "--vault", "Private", "--format=json", expect_json=True
    )
    assert isinstance(result, dict)
    assert "fields" in result
