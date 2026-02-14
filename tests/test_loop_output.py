from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import engineeringagent.loop_runtime.presentation as presentation_module
from engineeringagent.loop import print_summary
from engineeringagent.loop_runtime.models import (
    FeatureIterationInputs,
    IterationTelemetryInputs,
)
from engineeringagent.loop_runtime.telemetry import write_iteration_telemetry


def test_progress_log_records_verification_status(tmp_path: Path) -> None:
    verification_command = (
        "uv run pytest -q "
        "tests/test_loop_output.py::test_progress_log_records_verification_status"
    )
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040.yaml",
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt=None,
        skip_implement=False,
        attempt=3,
        hook_feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-040",
        result="failed",
        failed_gate=None,
        next_action="retry_same_feature",
        implement_status="passed",
        gate_status="not_run",
        verification_status=f"failed:{verification_command}",
        verification_failed_command=verification_command,
        reviewer_status="failed:blocking",
        reviewer_decision="request_changes",
        failed_reviewer_id="security-reviewer",
        implement_output="",
        gate_output="",
        verification_output="E       assert 1 == 2",
        reviewer_output="[reviewer:security-reviewer] mode=blocking decision=request_changes",
        hook_feedback=f"[verification] command={verification_command}",
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    run = json.loads((tmp_path / "progress" / "runs.jsonl").read_text(encoding="utf-8"))
    assert run["verification_status"] == f"failed:{verification_command}"
    assert run["verification_failed_command"] == verification_command
    assert run["reviewer_status"] == "failed:blocking"
    assert run["reviewer_decision"] == "request_changes"
    assert run["failed_reviewer_id"] == "security-reviewer"

    feature_log = (tmp_path / "progress" / "run-feature-FEAT-040.txt").read_text(
        encoding="utf-8"
    )
    assert (
        f"verification=failed:{verification_command} "
        f"failed_command={verification_command}"
    ) in feature_log
    assert "verification_output_begin" in feature_log
    assert "E       assert 1 == 2" in feature_log
    assert "verification_output_end" in feature_log
    assert (
        "reviewer=failed:blocking decision=request_changes "
        "failed_reviewer=security-reviewer"
    ) in feature_log
    assert "reviewer_output_begin" in feature_log
    assert "mode=blocking decision=request_changes" in feature_log
    assert "reviewer_output_end" in feature_log


def test_non_verbose_terminal_output_shows_verification_summary(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    verification_command = "uv run pytest -q tests/test_loop_output.py"
    monkeypatch.setattr(presentation_module, "_stdout_is_tty", lambda _stdout: False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    print_summary(
        feature_id="FEAT-040",
        result="failed",
        failed_gate=None,
        attempt=2,
        next_action="retry_same_feature",
        selected_path="docs/spec/features/FEAT-040-per-iteration-verification-feedback-and-failure-signaling.yaml",
        implement_step="default opencode implement step",
        log_path="progress/run-feature-FEAT-040.txt",
        verification_status=f"failed:{verification_command}",
        verification_failed_command=verification_command,
        reviewer_status="failed:blocking",
        reviewer_decision="request_changes",
        failed_reviewer_id="security-reviewer",
    )

    output = capsys.readouterr().out
    assert "🧪 Verify: failed (uv run pytest -q tests/test_loop_output.py)" in output
    assert (
        "👀 Reviewer: failed:blocking (request_changes) [security-reviewer]" in output
    )
    assert "❌ Failed: gate=unknown" in output
