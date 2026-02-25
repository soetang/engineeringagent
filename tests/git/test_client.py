from __future__ import annotations

import subprocess
from pathlib import Path

from engineeringagent.git.client import diff_name_status


def test_diff_name_status_includes_base_and_head(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def _run(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(
        "engineeringagent.git.client.subprocess.run",
        _run,
        raising=True,
    )

    result = diff_name_status(tmp_path, base="main", head="feature")

    assert result.returncode == 0
    assert captured["args"] == (
        [
            "git",
            "diff",
            "--name-status",
            "--find-renames",
            "--diff-filter=AMDR",
            "main",
            "feature",
        ],
    )
    assert captured["kwargs"] == {
        "cwd": tmp_path,
        "capture_output": True,
        "text": True,
        "check": False,
    }
