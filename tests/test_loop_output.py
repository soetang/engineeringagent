from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import engineeringagent.loop_runtime.presentation as presentation_module
from engineeringagent.loop import print_summary
import engineeringagent.loop_runtime.telemetry as telemetry_module
from engineeringagent.loop_runtime.models import (
    FeatureIterationInputs,
    CommandTiming,
    IterationTelemetryInputs,
    PhaseTiming,
)
from engineeringagent.loop_runtime.phases import (
    VerificationPhaseDependencies,
    run_verification_phase,
)
from engineeringagent.loop_runtime.telemetry import write_iteration_telemetry


def test_loop_runtime_models_define_timing_types_before_first_use() -> None:
    import engineeringagent.loop_runtime.models as models_module

    source = Path(models_module.__file__).read_text(encoding="utf-8")

    phase_class_pos = source.index("class PhaseTiming")
    assert "PhaseTiming" not in source[:phase_class_pos]

    command_class_pos = source.index("class CommandTiming")
    assert "CommandTiming" not in source[:command_class_pos]


def test_timing_format_helpers_emit_expected_lines() -> None:
    phase_timing = PhaseTiming(
        phase="implement",
        started_at="1970-01-01T00:00:02Z",
        ended_at="1970-01-01T00:00:07Z",
        duration_sec=5,
    )
    assert telemetry_module._format_phase_timing_line(phase_timing) == (
        "phase_timing phase=implement started_at=1970-01-01T00:00:02Z "
        "ended_at=1970-01-01T00:00:07Z duration_sec=5"
    )

    command_timing = CommandTiming(
        phase="verification",
        command="uv run pytest -q tests/test_loop_output.py",
        started_at="1970-01-01T00:00:10Z",
        ended_at="1970-01-01T00:00:18Z",
        duration_sec=8,
        gate="precommit",
    )
    assert telemetry_module._format_command_timing_line(command_timing) == (
        "command_timing phase=verification gate=precommit "
        "command=uv run pytest -q tests/test_loop_output.py "
        "started_at=1970-01-01T00:00:10Z ended_at=1970-01-01T00:00:18Z "
        "duration_sec=8"
    )


def test_timing_format_helpers_use_concrete_types() -> None:
    from typing import get_type_hints

    phase_hints = get_type_hints(telemetry_module._format_phase_timing_fields)
    assert phase_hints["timing"] is PhaseTiming

    phase_line_hints = get_type_hints(telemetry_module._format_phase_timing_line)
    assert phase_line_hints["timing"] is PhaseTiming

    command_parts_hints = get_type_hints(telemetry_module._command_timing_fields_parts)
    assert command_parts_hints["timing"] is CommandTiming

    command_line_hints = get_type_hints(telemetry_module._format_command_timing_line)
    assert command_line_hints["timing"] is CommandTiming


def test_progress_log_records_verification_status(tmp_path: Path) -> None:
    verification_command = (
        "uv run pytest -q "
        "tests/test_loop_output.py::test_progress_log_records_verification_status"
    )
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040.yaml",
        gate_profile="loop_fast",
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
    assert run["reviewer_feedback_present"] is False
    assert run["reviewer_feedback_summary"] == ""

    feature_log = (tmp_path / "progress" / "run-feature-FEAT-040.txt").read_text(
        encoding="utf-8"
    )
    first_line = feature_log.splitlines()[0]
    assert first_line.startswith("ts=")
    assert "=== ITERATION" in first_line
    assert "attempt=3" in first_line
    assert "feature_id=FEAT-040" in first_line
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


def test_progress_log_writes_do_not_use_path_open(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040.yaml",
        gate_profile="loop_fast",
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-040",
        result="passed",
        failed_gate=None,
        next_action="advance_to_next_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="passed",
        verification_failed_command=None,
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
        implement_output="ok",
        gate_output="ok",
        verification_output="ok",
        reviewer_output="",
        hook_feedback="",
    )

    original_open = Path.open

    def _path_open_forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError(
            "Direct Path.open() writes are forbidden for progress log sinks; "
            "use logging handlers."
        )

    monkeypatch.setattr(Path, "open", _path_open_forbidden)
    try:
        write_iteration_telemetry(
            telemetry_inputs,
            git_head_resolver=lambda _: "abc1234",
        )
    finally:
        monkeypatch.setattr(Path, "open", original_open)

    assert (tmp_path / "progress" / "runs.jsonl").exists()
    assert (tmp_path / "progress" / "run-feature-FEAT-040.txt").exists()


def test_progress_log_strips_ansi_only_at_write_time(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    import engineeringagent.loop_runtime.telemetry as telemetry_module

    implement_status = "\x1b[31mpassed\x1b[0m"
    gate_status = "\x1b[32mpassed\x1b[0m"

    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040.yaml",
        gate_profile="loop_fast",
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-040",
        result="passed",
        failed_gate=None,
        next_action="advance_to_next_feature",
        implement_status=implement_status,
        gate_status=gate_status,
        verification_status="passed",
        verification_failed_command=None,
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
        implement_output="",
        gate_output="",
        verification_output="",
        reviewer_output="",
        hook_feedback="",
    )

    original_strip_ansi = telemetry_module._strip_ansi
    strip_inputs: list[str] = []

    def _tracking_strip_ansi(text: str) -> str:
        strip_inputs.append(text)
        return original_strip_ansi(text)

    monkeypatch.setattr(telemetry_module, "_strip_ansi", _tracking_strip_ansi)

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    implement_line = f"implement={implement_status}"
    gates_line = f"gates={gate_status}"
    assert implement_status not in strip_inputs
    assert gate_status not in strip_inputs
    assert implement_line in strip_inputs
    assert gates_line in strip_inputs

    feature_log = (tmp_path / "progress" / "run-feature-FEAT-040.txt").read_text(
        encoding="utf-8"
    )
    assert "\x1b[" not in feature_log


def test_progress_log_records_phase_timings(tmp_path: Path, monkeypatch: Any) -> None:
    import engineeringagent.loop_runtime.telemetry as telemetry_module

    monkeypatch.setattr(telemetry_module, "now_iso", lambda: "1970-01-01T00:00:10Z")
    monkeypatch.setattr(telemetry_module.time, "time", lambda: 0.0)

    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040.yaml",
        gate_profile="loop_fast",
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        phase_timings=[
            PhaseTiming(
                phase="initial_load",
                started_at="1970-01-01T00:00:00Z",
                ended_at="1970-01-01T00:00:02Z",
                duration_sec=2,
            ),
            PhaseTiming(
                phase="implement",
                started_at="1970-01-01T00:00:02Z",
                ended_at="1970-01-01T00:00:07Z",
                duration_sec=5,
            ),
        ],
        feature_id="FEAT-040",
        result="passed",
        failed_gate=None,
        next_action="advance_to_next_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="passed",
        verification_failed_command=None,
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
        implement_output="",
        gate_output="",
        verification_output="",
        reviewer_output="",
        hook_feedback="",
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    feature_log = (tmp_path / "progress" / "run-feature-FEAT-040.txt").read_text(
        encoding="utf-8"
    )
    assert (
        "phase_timing phase=initial_load started_at=1970-01-01T00:00:00Z "
        "ended_at=1970-01-01T00:00:02Z duration_sec=2"
    ) in feature_log
    assert (
        "phase_timing phase=implement started_at=1970-01-01T00:00:02Z "
        "ended_at=1970-01-01T00:00:07Z duration_sec=5"
    ) in feature_log


def test_progress_log_records_verification_command_timings(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    import engineeringagent.loop_runtime.phases as phases_module
    import engineeringagent.loop_runtime.telemetry as telemetry_module

    from types import SimpleNamespace

    monkeypatch.setattr(telemetry_module, "now_iso", lambda: "1970-01-01T00:00:20Z")

    time_values = [10.0, 14.0]

    def _fake_time() -> float:
        if time_values:
            return time_values.pop(0)
        return 14.0

    monkeypatch.setattr(phases_module.time, "time", _fake_time)

    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040.yaml",
        gate_profile="loop_fast",
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )
    command = "uv run pytest -q tests/test_loop_output.py"
    verification_outcome = run_verification_phase(
        iteration_inputs,
        [command],
        VerificationPhaseDependencies(
            run_shell_command=lambda *_args, **_kwargs: SimpleNamespace(
                returncode=0,
                stdout="ok\n",
                stderr="",
            )
        ),
    )

    assert len(verification_outcome.command_timings) == 1
    timing = verification_outcome.command_timings[0]
    assert timing.phase == "verification"
    assert timing.command == command
    assert timing.started_at == "1970-01-01T00:00:10Z"
    assert timing.ended_at == "1970-01-01T00:00:14Z"
    assert timing.duration_sec == 4

    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        phase_timings=[],
        command_timings=verification_outcome.command_timings,
        feature_id="FEAT-040",
        result="passed",
        failed_gate=None,
        next_action="advance_to_next_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="passed",
        verification_failed_command=None,
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
        implement_output="",
        gate_output="",
        verification_output=verification_outcome.verification_output,
        reviewer_output="",
        hook_feedback=None,
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    feature_log = (tmp_path / "progress" / "run-feature-FEAT-040.txt").read_text(
        encoding="utf-8"
    )
    assert (
        "command_timing phase=verification command=uv run pytest -q "
        "tests/test_loop_output.py started_at=1970-01-01T00:00:10Z "
        "ended_at=1970-01-01T00:00:14Z duration_sec=4"
    ) in feature_log


def test_verification_command_timing_clamps_ended_at_when_clock_skews_backwards(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    import engineeringagent.loop_runtime.phases as phases_module

    from types import SimpleNamespace

    time_values = [10.0, 9.0]

    def _fake_time() -> float:
        if time_values:
            return time_values.pop(0)
        return 9.0

    monkeypatch.setattr(phases_module.time, "time", _fake_time)

    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040.yaml",
        gate_profile="loop_fast",
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )
    command = "uv run pytest -q tests/test_loop_output.py"
    verification_outcome = run_verification_phase(
        iteration_inputs,
        [command],
        VerificationPhaseDependencies(
            run_shell_command=lambda *_args, **_kwargs: SimpleNamespace(
                returncode=0,
                stdout="ok\n",
                stderr="",
            )
        ),
    )

    assert len(verification_outcome.command_timings) == 1
    timing = verification_outcome.command_timings[0]
    assert timing.started_at == "1970-01-01T00:00:10Z"
    assert timing.ended_at == "1970-01-01T00:00:10Z"
    assert timing.duration_sec == 0


def test_progress_log_records_slowest_summary(tmp_path: Path) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040.yaml",
        gate_profile="loop_fast",
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        phase_timings=[
            PhaseTiming(
                phase="implement",
                started_at="1970-01-01T00:00:02Z",
                ended_at="1970-01-01T00:00:07Z",
                duration_sec=5,
            )
        ],
        command_timings=[
            CommandTiming(
                phase="verification",
                command="uv run pytest -q tests/test_loop_output.py",
                started_at="1970-01-01T00:00:10Z",
                ended_at="1970-01-01T00:00:18Z",
                duration_sec=8,
            )
        ],
        feature_id="FEAT-040",
        result="passed",
        failed_gate=None,
        next_action="advance_to_next_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="passed",
        verification_failed_command=None,
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
        implement_output="",
        gate_output="",
        verification_output="",
        reviewer_output="",
        hook_feedback="",
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    feature_log = (tmp_path / "progress" / "run-feature-FEAT-040.txt").read_text(
        encoding="utf-8"
    )
    assert (
        "slowest=command phase=verification command=uv run pytest -q "
        "tests/test_loop_output.py started_at=1970-01-01T00:00:10Z "
        "ended_at=1970-01-01T00:00:18Z duration_sec=8"
    ) in feature_log


def test_progress_log_records_code_simplifier_advisory_followup_status(
    tmp_path: Path,
) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-059.yaml",
        gate_profile="loop_fast",
        attempt=2,
        hook_feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-059",
        result="failed",
        failed_gate="reviewer_advisory_followup",
        next_action="retry_same_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="passed",
        verification_failed_command=None,
        reviewer_status="failed:advisory_followup",
        reviewer_decision="warning",
        failed_reviewer_id="code_simplifier",
        implement_output="",
        gate_output="",
        verification_output="",
        reviewer_output="[reviewer:code_simplifier] mode=advisory decision=warning",
        hook_feedback="reviewer 'code_simplifier' advisory feedback: simplify nested branching.",
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "def5678",
    )

    run = json.loads((tmp_path / "progress" / "runs.jsonl").read_text(encoding="utf-8"))
    assert run["reviewer_status"] == "failed:advisory_followup"
    assert run["reviewer_decision"] == "warning"
    assert run["failed_reviewer_id"] == "code_simplifier"
    assert run["reviewer_feedback_present"] is True
    assert "simplify nested branching" in run["reviewer_feedback_summary"]

    feature_log = (tmp_path / "progress" / "run-feature-FEAT-059.txt").read_text(
        encoding="utf-8"
    )
    assert (
        "reviewer=failed:advisory_followup decision=warning "
        "failed_reviewer=code_simplifier"
    ) in feature_log
    assert "reviewer_output_begin" in feature_log
    assert "[reviewer:code_simplifier] mode=advisory decision=warning" in feature_log
    assert "reviewer_output_end" in feature_log
    assert "reviewer_feedback_forwarded_begin" in feature_log
    assert "reviewer 'code_simplifier' advisory feedback" in feature_log
    assert "reviewer_feedback_forwarded_end" in feature_log


def test_run_telemetry_summary_strips_feedback_context_block(tmp_path: Path) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-059.yaml",
        gate_profile="loop_fast",
        attempt=2,
        hook_feedback=None,
        verbose_output=False,
    )
    hook_feedback = (
        "reviewer 'readme_process' requested changes (attempt 1/3): "
        "Add missing usage section.\n"
        "required_actions:\n"
        "- Add CLI example\n"
        "- Document sandbox scope\n"
        "feedback_context:\n"
        "This reviewer runs with constrained context and may not see the full repo.\n"
        "Treat failures as real, but align fixes with the full codebase."
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-079",
        result="failed",
        failed_gate="reviewer_blocking",
        next_action="retry_same_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="passed",
        verification_failed_command=None,
        reviewer_status="failed:blocking",
        reviewer_decision="request_changes",
        failed_reviewer_id="readme_process",
        implement_output="",
        gate_output="",
        verification_output="",
        reviewer_output="[reviewer:readme_process] mode=blocking decision=request_changes",
        hook_feedback=hook_feedback,
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    run = json.loads((tmp_path / "progress" / "runs.jsonl").read_text(encoding="utf-8"))
    assert run["reviewer_feedback_present"] is True
    assert "requested changes" in run["reviewer_feedback_summary"]
    assert "Add missing usage section" in run["reviewer_feedback_summary"]
    assert "feedback_context:" not in run["reviewer_feedback_summary"]


def test_reviewer_feedback_forwarded_field_takes_precedence(tmp_path: Path) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-059.yaml",
        gate_profile="loop_fast",
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-079",
        result="failed",
        failed_gate="reviewer_blocking",
        next_action="retry_same_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="passed",
        verification_failed_command=None,
        reviewer_status="failed:blocking",
        reviewer_decision="request_changes",
        failed_reviewer_id="readme_process",
        implement_output="",
        gate_output="",
        verification_output="",
        reviewer_output="[reviewer:readme_process] mode=blocking decision=request_changes",
        reviewer_feedback_forwarded=(
            "reviewer 'readme_process' feedback (mode=blocking, decision=request_changes): "
            "Use the repo README conventions.\nfeedback_context:\nclean-room sandbox"
        ),
        hook_feedback="(ignored) not a reviewer line",
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    run = json.loads((tmp_path / "progress" / "runs.jsonl").read_text(encoding="utf-8"))
    assert run["reviewer_feedback_present"] is True
    assert "readme_process" in run["reviewer_feedback_summary"]


def test_reviewer_feedback_summary_truncates_after_stripping_context() -> None:
    text = (
        "reviewer 'readme_process' feedback (mode=blocking, decision=request_changes): "
        + ("x" * 50)
        + "\nfeedback_context:\n"
        + ("y" * 500)
    )
    stripped = telemetry_module._strip_feedback_context_blocks(text)
    assert "feedback_context:" not in stripped
    summarized = telemetry_module._summarize_reviewer_feedback(text, max_chars=32)
    assert summarized.endswith("...[truncated]")
    assert "feedback_context:" not in summarized


def test_command_timing_line_includes_reviewer_id() -> None:
    timing = CommandTiming(
        phase="reviewers",
        gate=None,
        reviewer_id="readme_process",
        command="run_reviewer",
        started_at="1970-01-01T00:00:10Z",
        ended_at="1970-01-01T00:00:13Z",
        duration_sec=3,
    )
    line = telemetry_module._format_command_timing_line(timing)
    assert "reviewer_id=readme_process" in line


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
