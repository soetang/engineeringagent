from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import engineeringagent.opencode_permissions as permissions


def test_evaluate_permission_probe_reports_nonzero_exit() -> None:
    result = permissions.evaluate_permission_probe(returncode=9, output="PERMISSION_OK")

    assert result.ok is False
    assert result.reason == "opencode exited with status 9"


def test_evaluate_permission_probe_reports_missing_success_token() -> None:
    result = permissions.evaluate_permission_probe(returncode=0, output="all good")

    assert result.ok is False
    assert "success token" in result.reason


def test_run_permission_probe_reports_missing_opencode_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def raise_not_found(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("missing")

    monkeypatch.setattr(permissions, "start_agent", raise_not_found)

    result = permissions.run_permission_probe(tmp_path)

    assert result.ok is False
    assert result.returncode == 127
    assert result.reason == "opencode CLI not found in PATH"
