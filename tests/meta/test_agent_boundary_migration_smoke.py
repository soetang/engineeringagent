from __future__ import annotations

from pathlib import Path


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_cli_no_longer_imports_opencode_start_agent() -> None:
    text = _read_text(Path("src/engineeringagent/cli.py"))
    assert "from engineeringagent.opencode.client import start_agent" not in text


def test_checks_api_no_longer_imports_opencode_start_agent() -> None:
    text = _read_text(Path("src/engineeringagent/checks/api.py"))
    assert "from engineeringagent.opencode.client import start_agent" not in text


def test_loop_no_longer_imports_opencode_start_agent() -> None:
    text = _read_text(Path("src/engineeringagent/loop.py"))
    assert "from .opencode.client import run_shell_command, start_agent" not in text
