"""Shared test fixtures.

Provides a `fake_op_factory` fixture that writes a temporary shell
script named `op` on PATH and yields an `OpRunner` pointed at it.
Tests use this to exercise the subprocess glue without needing the
real 1Password CLI installed.

Live tests (marked `@pytest.mark.live`) are skipped unless
`RUN_LIVE_OP_TESTS=1` is set. Live tests exercise the real `op` CLI
against an authenticated 1Password session — they will trigger Touch
ID prompts and should never run in CI.
"""

from __future__ import annotations

import os
import stat
import textwrap
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from op_mcp.runner import OpRunner


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip @pytest.mark.live tests unless RUN_LIVE_OP_TESTS=1."""
    if os.environ.get("RUN_LIVE_OP_TESTS") == "1":
        return
    skip_live = pytest.mark.skip(reason="live tests require RUN_LIVE_OP_TESTS=1")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture
def fake_op_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[[str], OpRunner]:
    """Return a factory that installs a fake `op` binary with custom behavior.

    Usage:
        runner = fake_op_factory('''
            echo 'my-secret-value'
        ''')
        result = await runner.run("read", "op://Private/x/y")
    """

    def _install(script_body: str) -> OpRunner:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        binary = bin_dir / "op"
        body = textwrap.dedent(script_body).lstrip()
        binary.write_text(
            "#!/bin/sh\n" + body,
            encoding="utf-8",
        )
        binary.chmod(binary.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
        return OpRunner()

    return _install


@pytest.fixture
def empty_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Clear PATH so `op` resolution fails. Used to test missing-binary handling."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.setenv("PATH", str(empty_dir))
    yield
