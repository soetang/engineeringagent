from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from engineeringagent.git import client as git_client


@pytest.mark.parametrize(
    ("hook_type", "expected_command"),
    [
        (None, ["pre-commit", "install"]),
        ("commit-msg", ["pre-commit", "install", "--hook-type", "commit-msg"]),
    ],
)
def test_precommit_install_invokes_subprocess_non_interactive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    hook_type: str | None,
    expected_command: list[str],
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def _fake_run(cmd: list[str], **kwargs: object) -> object:
        calls.append((cmd, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(git_client.subprocess, "run", _fake_run)

    git_client.precommit_install(tmp_path, hook_type=hook_type)

    assert len(calls) == 1
    cmd, kwargs = calls[0]
    assert cmd == expected_command
    assert kwargs["cwd"] == tmp_path
    assert kwargs["stdin"] is git_client.subprocess.DEVNULL
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["check"] is False
