from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import engineeringagent.opencode.permissions as permissions


def test_evaluate_permission_probe_reports_nonzero_exit() -> None:
    result = permissions.evaluate_permission_probe(returncode=9, output="PERMISSION_OK")

    assert result.ok is False
    assert result.reason == "opencode exited with status 9"


def test_evaluate_permission_probe_reports_missing_success_token() -> None:
    result = permissions.evaluate_permission_probe(returncode=0, output="all good")

    assert result.ok is False
    assert "decision token" in result.reason


def test_evaluate_permission_probe_reports_explicit_denial_token() -> None:
    result = permissions.evaluate_permission_probe(
        returncode=0,
        output=f"{permissions.PROBE_DENIED_TOKEN}\n",
    )

    assert result.ok is False
    assert "explicit denial token" in result.reason


def test_output_has_permission_rejection_matches_explicit_rejection_line() -> None:
    output = "permission requested for bash command git status --short (auto-reject)"

    assert permissions.output_has_permission_rejection(output) is True


def test_output_has_permission_rejection_ignores_quoted_diff_lines() -> None:
    output = (
        "+                \"echo 'permission requested for bash command git status --short (auto-reject)' >&2\",\n"
        '-            output="permission requested for bash command git status --short (auto-reject)",\n'
        "@@ -12,7 +12,7 @@\n"
        "context\n"
    )

    assert permissions.output_has_permission_rejection(output) is False


def test_evaluate_permission_probe_accepts_success_token_when_diff_text_is_also_present() -> (
    None
):
    output = (
        "+                \"echo 'permission requested for bash command git status --short (auto-reject)' >&2\",\n"
        "PERMISSION_OK\n"
    )
    result = permissions.evaluate_permission_probe(returncode=0, output=output)

    assert result.ok is True


def test_run_permission_probe_retries_until_explicit_decision_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def fake_start_agent(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return subprocess.CompletedProcess(
                [
                    "opencode",
                    "run",
                    "--agent",
                    permissions.DEFAULT_OPENCODE_AGENT,
                    "<prompt>",
                ],
                0,
                stdout="chatty text instead of probe token\n",
                stderr="",
            )
        return subprocess.CompletedProcess(
            [
                "opencode",
                "run",
                "--agent",
                permissions.DEFAULT_OPENCODE_AGENT,
                "<prompt>",
            ],
            0,
            stdout=f"{permissions.PROBE_TOKEN}\n",
            stderr="",
        )

    monkeypatch.setattr(permissions, "start_agent", fake_start_agent)

    result = permissions.run_permission_probe(tmp_path)

    assert result.ok is True
    assert calls == 2


def test_run_permission_probe_stops_after_max_retries_when_output_is_undecidable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def fake_start_agent(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(
            [
                "opencode",
                "run",
                "--agent",
                permissions.DEFAULT_OPENCODE_AGENT,
                "<prompt>",
            ],
            0,
            stdout="undecidable probe output\n",
            stderr="",
        )

    monkeypatch.setattr(permissions, "start_agent", fake_start_agent)

    result = permissions.run_permission_probe(tmp_path)

    assert result.ok is False
    assert calls == permissions.PROBE_MAX_ATTEMPTS
    assert "after 3 probe attempts" in result.reason


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


def test_permission_remediation_hint_does_not_require_opencode_json() -> None:
    assert (
        ".opencode/agents/engineeringagent.md"
        in permissions.PERMISSION_REMEDIATION_HINT
    )
    legacy_repo_root_config = ".".join(["opencode", "json"])
    assert legacy_repo_root_config not in permissions.PERMISSION_REMEDIATION_HINT
