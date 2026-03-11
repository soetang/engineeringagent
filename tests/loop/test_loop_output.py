from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, get_type_hints

import engineeringagent.adapters.progress.iteration_telemetry as telemetry_module
import engineeringagent.presentation.presenters.terminal as presentation_module
from engineeringagent.loop import print_summary
import engineeringagent.loop_runtime.phases as phases_module
import engineeringagent.application.feature_iteration.models as models_module
from engineeringagent.application.feature_iteration.models import (
    FeatureIterationInputs,
    CommandTiming,
    IterationTelemetryInputs,
    IterationSummaryInputs,
    PhaseTiming,
)
from engineeringagent.loop_runtime.phases import (
    run_verification_phase,
)
from engineeringagent.adapters.progress.iteration_telemetry import (
    _command_timing_fields_parts,
    _format_command_timing_line,
    _format_phase_timing_fields,
    _format_phase_timing_line,
    _strip_ansi,
    _strip_feedback_context_blocks,
    _summarize_reviewer_feedback,
    write_iteration_telemetry,
)
from engineeringagent.adapters.progress.handoff import (
    ImplementProgressEnvelope,
    HandoffRenderMetadata,
    render_handoff_markdown_entry,
    parse_implement_progress_envelope,
)
from engineeringagent.adapters.progress import FilesystemProgressJournal


_PROGRESS_ROOT_PARTS = (".engineeringagent", "progress")
_PROGRESS_JOURNAL = FilesystemProgressJournal()


def _progress_root(project_root: Path) -> Path:
    return project_root.joinpath(*_PROGRESS_ROOT_PARTS)


def test_loop_runtime_models_define_timing_types_before_first_use() -> None:
    source = Path(models_module.__file__).read_text(encoding="utf-8")

    phase_class_pos = source.index("class PhaseTiming")
    assert "PhaseTiming" not in source[:phase_class_pos]

    command_class_pos = source.index("class CommandTiming")
    assert "CommandTiming" not in source[:command_class_pos]


def test_handoff_envelope_parser_accepts_valid_payload() -> None:
    envelope, used_fallback = parse_implement_progress_envelope(
        {
            "summary": "  Added markdown handoff rendering. ",
            "completed_work": [" Added parser helper "],
            "verification": [
                "uv run pytest -q tests/loop/test_loop_output.py -k handoff"
            ],
            "remaining_work": ["Wire observer append call"],
            "blockers": ["None"],
        }
    )

    assert used_fallback is False
    assert envelope == ImplementProgressEnvelope(
        summary="Added markdown handoff rendering.",
        completed_work=["Added parser helper"],
        verification=["uv run pytest -q tests/loop/test_loop_output.py -k handoff"],
        remaining_work=["Wire observer append call"],
        blockers=["None"],
    )


def test_handoff_envelope_parser_falls_back_for_invalid_payload() -> None:
    envelope, used_fallback = parse_implement_progress_envelope(
        {
            "summary": "",
            "completed_work": [],
            "verification": [],
            "remaining_work": [],
        }
    )

    assert used_fallback is True
    assert envelope.summary.startswith("Structured handoff output unavailable")
    assert envelope.completed_work == []
    assert envelope.verification == []
    assert envelope.remaining_work == [
        "Review latest progress logs and continue the highest-priority open implementation step."
    ]
    assert envelope.blockers == []


def test_handoff_markdown_write_replaces_previous_contents(
    tmp_path: Path,
) -> None:
    handoff_path = _progress_root(tmp_path) / "features" / "FEAT-130" / "handoff.md"
    _PROGRESS_JOURNAL.write_handoff(
        project_root=tmp_path,
        feature_id="FEAT-130",
        lines=["## Iteration 4 - 2026-02-25T07:00:00Z", "", "Summary: first"],
    )
    _PROGRESS_JOURNAL.write_handoff(
        project_root=tmp_path,
        feature_id="FEAT-130",
        lines=["## Iteration 5 - 2026-02-25T07:01:00Z", "", "Summary: second"],
    )

    assert handoff_path.exists()
    assert handoff_path.read_text(encoding="utf-8") == (
        "## Iteration 5 - 2026-02-25T07:01:00Z\n\nSummary: second\n"
    )


def test_handoff_markdown_entry_omits_empty_and_placeholder_sections() -> None:
    envelope = ImplementProgressEnvelope(
        summary="Minimizing handoff noise in markdown.",
        completed_work=["Render compact completed-work bullets."],
        verification=["uv run pytest -q tests/loop/test_loop_output.py -k handoff"],
        remaining_work=["(none)", "Continue next subtask."],
        blockers=["(none)"],
    )
    lines = render_handoff_markdown_entry(
        attempt=3,
        envelope=envelope,
        metadata=HandoffRenderMetadata(timestamp="2026-03-03T19:18:56Z"),
    )

    section_headers = [line for line in lines if line.startswith("### ")]
    bullet_lines = [line for line in lines if line.startswith("- ")]

    assert section_headers == [
        "### Completed Work",
        "### Verification",
    ]
    assert "### Blockers" not in section_headers
    assert "### Verification" in section_headers
    assert "### Remaining Work" not in lines
    assert "- (none)" not in bullet_lines
    assert "- Continue next subtask." not in lines


def test_handoff_markdown_entry_includes_phase_progress_context() -> None:
    envelope = ImplementProgressEnvelope(
        summary="Keep bundled handoff entries phase-oriented.",
        completed_work=["Recorded deterministic phase context in handoff output."],
        verification=[],
        remaining_work=["Continue the current bundled phase."],
        blockers=[],
    )

    lines = render_handoff_markdown_entry(
        attempt=4,
        envelope=envelope,
        metadata=HandoffRenderMetadata(
            timestamp="2026-03-09T21:30:00Z",
            progress_kind="phase",
            progress_id="P3",
            progress_title="Move implementation sequencing from subtasks to plan phases",
        ),
    )

    assert (
        "Progress: phase P3 - Move implementation sequencing from subtasks to plan phases"
        in lines
    )


def test_handoff_render_metadata_exposes_pydantic_dump_defaults() -> None:
    metadata = HandoffRenderMetadata()

    assert metadata.model_dump() == {
        "timestamp": None,
        "used_fallback": False,
        "progress_kind": None,
        "progress_id": None,
        "progress_title": None,
    }


def test_write_iteration_telemetry_writes_handoff_snapshot_from_envelope(
    tmp_path: Path,
) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-130.yaml",
        attempt=5,
        feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-130",
        result="passed",
        failed_gate=None,
        next_action="continue_same_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="not_run",
        verification_failed_command=None,
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
        progress_kind="phase",
        progress_id="P2",
        progress_title="Track bundled handoff progress",
        implement_output="",
        implement_handoff_envelope=ImplementProgressEnvelope(
            summary="Added handoff snapshot wiring to telemetry flow.",
            completed_work=["Wired markdown snapshot write after JSONL write"],
            verification=["uv run pytest -q tests/loop/test_loop_output.py -k handoff"],
            remaining_work=["Add integration coverage for loop observer chain"],
            blockers=[],
        ),
        implement_handoff_used_fallback=False,
        gate_output="",
        verification_output="",
        reviewer_output="",
        feedback=None,
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    handoff_path = _progress_root(tmp_path) / "features" / "FEAT-130" / "handoff.md"
    assert handoff_path.exists()
    assert handoff_path.stat().st_size > 0
    handoff_text = handoff_path.read_text(encoding="utf-8")
    assert "Progress: phase P2 - Track bundled handoff progress" in handoff_text


def test_write_iteration_telemetry_appends_fallback_handoff_when_missing(
    tmp_path: Path,
) -> None:
    handoff_path = _progress_root(tmp_path) / "features" / "FEAT-130" / "handoff.md"
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text("seed-entry\n", encoding="utf-8")

    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-130.yaml",
        attempt=6,
        feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-130",
        result="passed",
        failed_gate=None,
        next_action="continue_same_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="not_run",
        verification_failed_command=None,
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
        implement_output="",
        gate_output="",
        verification_output="",
        reviewer_output="",
        feedback=None,
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    assert handoff_path.exists()
    assert handoff_path.read_text(encoding="utf-8") != "seed-entry\n"


def test_write_iteration_telemetry_uses_phase_wording_for_fallback_handoff(
    tmp_path: Path,
) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-130" / "spec.yaml",
        attempt=7,
        feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-130",
        result="passed",
        failed_gate=None,
        next_action="continue_same_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="not_run",
        verification_failed_command=None,
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
        progress_kind="phase",
        progress_id="P3",
        progress_title="Move implementation sequencing from subtasks to plan phases",
        implement_output="",
        implement_handoff_envelope=None,
        implement_handoff_used_fallback=False,
        gate_output="",
        verification_output="",
        reviewer_output="",
        feedback=None,
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    handoff_path = _progress_root(tmp_path) / "features" / "FEAT-130" / "handoff.md"
    handoff_text = handoff_path.read_text(encoding="utf-8")
    assert "### Remaining Work" not in handoff_text
    assert (
        "Progress: phase P3 - Move implementation sequencing from subtasks to plan phases"
        in handoff_text
    )


def test_write_iteration_telemetry_uses_feature_wording_for_direct_bundle_fallback_handoff(
    tmp_path: Path,
) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-182" / "spec.yaml",
        attempt=8,
        feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-182",
        result="passed",
        failed_gate=None,
        next_action="continue_same_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="not_run",
        verification_failed_command=None,
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
        progress_kind="feature",
        progress_id="FEAT-182",
        progress_title="Direct bundled fallback handoff context",
        implement_output="",
        implement_handoff_envelope=None,
        implement_handoff_used_fallback=False,
        gate_output="",
        verification_output="",
        reviewer_output="",
        feedback=None,
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    handoff_path = _progress_root(tmp_path) / "features" / "FEAT-182" / "handoff.md"
    handoff_text = handoff_path.read_text(encoding="utf-8")
    assert "### Remaining Work" not in handoff_text
    assert (
        "Progress: implementation step FEAT-182 - Direct bundled fallback handoff context"
        in handoff_text
    )


def test_timing_format_helpers_emit_expected_lines() -> None:
    phase_timing = PhaseTiming(
        phase="implement",
        started_at="1970-01-01T00:00:02Z",
        ended_at="1970-01-01T00:00:07Z",
        duration_sec=5,
    )
    assert _format_phase_timing_line(phase_timing) == (
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
    assert _format_command_timing_line(command_timing) == (
        "command_timing phase=verification gate=precommit "
        "command=uv run pytest -q tests/test_loop_output.py "
        "started_at=1970-01-01T00:00:10Z ended_at=1970-01-01T00:00:18Z "
        "duration_sec=8"
    )


def test_timing_format_helpers_use_concrete_types() -> None:
    phase_hints = get_type_hints(_format_phase_timing_fields)
    assert phase_hints["timing"] is PhaseTiming

    phase_line_hints = get_type_hints(_format_phase_timing_line)
    assert phase_line_hints["timing"] is PhaseTiming

    command_parts_hints = get_type_hints(_command_timing_fields_parts)
    assert command_parts_hints["timing"] is CommandTiming

    command_line_hints = get_type_hints(_format_command_timing_line)
    assert command_line_hints["timing"] is CommandTiming


def test_progress_log_records_verification_status(tmp_path: Path) -> None:
    verification_command = (
        "uv run pytest -q "
        "tests/test_loop_output.py::test_progress_log_records_verification_status"
    )
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040.yaml",
        attempt=3,
        feedback=None,
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
        reviewer_status="failed:request_changes",
        reviewer_decision="request_changes",
        failed_reviewer_id="security-reviewer",
        implement_output="",
        gate_output="",
        verification_output="E       assert 1 == 2",
        reviewer_output="[reviewer:security-reviewer] decision=request_changes",
        feedback=f"[verification] command={verification_command}",
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    run = json.loads(
        (_progress_root(tmp_path) / "runs" / "runs.jsonl").read_text(encoding="utf-8")
    )
    assert run["verification_status"] == f"failed:{verification_command}"
    assert run["verification_failed_command"] == verification_command
    assert run["reviewer_status"] == "failed:request_changes"
    assert run["reviewer_decision"] == "request_changes"
    assert run["failed_reviewer_id"] == "security-reviewer"
    assert run["reviewer_feedback_present"] is False
    assert run["reviewer_feedback_summary"] == ""

    feature_log = (
        _progress_root(tmp_path) / "features" / "FEAT-040" / "run.txt"
    ).read_text(encoding="utf-8")
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
        "reviewer=failed:request_changes decision=request_changes "
        "failed_reviewer=security-reviewer"
    ) in feature_log
    assert "reviewer_output_begin" in feature_log
    assert "decision=request_changes" in feature_log
    assert "reviewer_output_end" in feature_log


def test_progress_log_records_phase_progress_metadata(tmp_path: Path) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040" / "spec.yaml",
        attempt=3,
        feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-040",
        result="passed",
        failed_gate=None,
        next_action="continue_same_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="not_run",
        verification_failed_command=None,
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
        progress_kind="phase",
        progress_id="P2",
        progress_title="Track bundled phase progress",
        implement_output="",
        gate_output="",
        verification_output="",
        reviewer_output="",
        feedback=None,
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    run = json.loads(
        (_progress_root(tmp_path) / "runs" / "runs.jsonl").read_text(encoding="utf-8")
    )
    assert run["progress_kind"] == "phase"
    assert run["progress_id"] == "P2"
    assert run["progress_title"] == "Track bundled phase progress"

    feature_log = (
        _progress_root(tmp_path) / "features" / "FEAT-040" / "run.txt"
    ).read_text(encoding="utf-8")
    assert "progress=phase:P2 title=Track bundled phase progress" in feature_log


def test_progress_log_writes_do_not_use_path_open(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040.yaml",
        attempt=1,
        feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-040",
        result="passed",
        failed_gate=None,
        next_action="continue_same_feature",
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
        feedback="",
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

    assert (_progress_root(tmp_path) / "runs" / "runs.jsonl").exists()
    assert (_progress_root(tmp_path) / "features" / "FEAT-040" / "run.txt").exists()


def test_progress_log_strips_ansi_only_at_write_time(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    implement_status = "\x1b[31mpassed\x1b[0m"
    gate_status = "\x1b[32mpassed\x1b[0m"

    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040.yaml",
        attempt=1,
        feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-040",
        result="passed",
        failed_gate=None,
        next_action="continue_same_feature",
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
        feedback="",
    )

    original_strip_ansi = _strip_ansi
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

    feature_log = (
        _progress_root(tmp_path) / "features" / "FEAT-040" / "run.txt"
    ).read_text(encoding="utf-8")
    assert "\x1b[" not in feature_log


def test_progress_log_records_phase_timings(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(
        telemetry_module.progress_handoff,
        "now_iso",
        lambda: "1970-01-01T00:00:10Z",
    )
    monkeypatch.setattr(telemetry_module.time, "time", lambda: 0.0)

    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040.yaml",
        attempt=1,
        feedback=None,
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
        next_action="continue_same_feature",
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
        feedback="",
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    feature_log = (
        _progress_root(tmp_path) / "features" / "FEAT-040" / "run.txt"
    ).read_text(encoding="utf-8")
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
    monkeypatch.setattr(
        telemetry_module.progress_handoff,
        "now_iso",
        lambda: "1970-01-01T00:00:20Z",
    )

    time_values = [10.0, 14.0]

    def _fake_time() -> float:
        if time_values:
            return time_values.pop(0)
        return 14.0

    monkeypatch.setattr(phases_module.time, "time", _fake_time)

    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040.yaml",
        attempt=1,
        feedback=None,
        verbose_output=False,
    )
    command = "uv run pytest -q tests/test_loop_output.py"
    monkeypatch.setattr(
        phases_module,
        "run_shell_command",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="ok\n",
            stderr="",
        ),
    )
    verification_outcome = run_verification_phase(
        iteration_inputs,
        [command],
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
        next_action="continue_same_feature",
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
        feedback=None,
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    feature_log = (
        _progress_root(tmp_path) / "features" / "FEAT-040" / "run.txt"
    ).read_text(encoding="utf-8")
    assert (
        "command_timing phase=verification command=uv run pytest -q "
        "tests/test_loop_output.py started_at=1970-01-01T00:00:10Z "
        "ended_at=1970-01-01T00:00:14Z duration_sec=4"
    ) in feature_log


def test_verification_command_timing_clamps_ended_at_when_clock_skews_backwards(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    time_values = [10.0, 9.0]

    def _fake_time() -> float:
        if time_values:
            return time_values.pop(0)
        return 9.0

    monkeypatch.setattr(phases_module.time, "time", _fake_time)

    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040.yaml",
        attempt=1,
        feedback=None,
        verbose_output=False,
    )
    command = "uv run pytest -q tests/test_loop_output.py"
    monkeypatch.setattr(
        phases_module,
        "run_shell_command",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="ok\n",
            stderr="",
        ),
    )
    verification_outcome = run_verification_phase(
        iteration_inputs,
        [command],
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
        attempt=1,
        feedback=None,
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
        next_action="continue_same_feature",
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
        feedback="",
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    feature_log = (
        _progress_root(tmp_path) / "features" / "FEAT-040" / "run.txt"
    ).read_text(encoding="utf-8")
    assert (
        "slowest=command phase=verification command=uv run pytest -q "
        "tests/test_loop_output.py started_at=1970-01-01T00:00:10Z "
        "ended_at=1970-01-01T00:00:18Z duration_sec=8"
    ) in feature_log


def test_progress_log_records_reviewer_approve_status(
    tmp_path: Path,
) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-059.yaml",
        attempt=2,
        feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-059",
        result="passed",
        failed_gate=None,
        next_action="continue_same_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="passed",
        verification_failed_command=None,
        reviewer_status="passed",
        reviewer_decision="approve",
        failed_reviewer_id=None,
        implement_output="",
        gate_output="",
        verification_output="",
        reviewer_output="[reviewer:code_simplifier] decision=approve",
        feedback=(
            "reviewer 'code_simplifier' feedback (decision=approve): simplify nested branching."
        ),
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "def5678",
    )

    run = json.loads(
        (_progress_root(tmp_path) / "runs" / "runs.jsonl").read_text(encoding="utf-8")
    )
    assert run["reviewer_status"] == "passed"
    assert run["reviewer_decision"] == "approve"
    assert run["failed_reviewer_id"] is None
    assert run["reviewer_feedback_present"] is True
    assert "simplify nested branching" in run["reviewer_feedback_summary"]

    feature_log = (
        _progress_root(tmp_path) / "features" / "FEAT-059" / "run.txt"
    ).read_text(encoding="utf-8")
    assert "reviewer=passed decision=approve failed_reviewer=-" in feature_log
    assert "reviewer_output_begin" in feature_log
    assert "[reviewer:code_simplifier] decision=approve" in feature_log
    assert "reviewer_output_end" in feature_log
    assert "reviewer_feedback_forwarded_begin" in feature_log
    assert "reviewer 'code_simplifier' feedback" in feature_log
    assert "reviewer_feedback_forwarded_end" in feature_log


def test_run_telemetry_summary_strips_feedback_context_block(tmp_path: Path) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-059.yaml",
        attempt=2,
        feedback=None,
        verbose_output=False,
    )
    feedback = (
        "reviewer 'onboarding_review' requested changes (attempt 1/3): "
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
        failed_gate="reviewer_request_changes",
        next_action="retry_same_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="passed",
        verification_failed_command=None,
        reviewer_status="failed:request_changes",
        reviewer_decision="request_changes",
        failed_reviewer_id="onboarding_review",
        implement_output="",
        gate_output="",
        verification_output="",
        reviewer_output="[reviewer:onboarding_review] decision=request_changes",
        feedback=feedback,
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    run = json.loads(
        (_progress_root(tmp_path) / "runs" / "runs.jsonl").read_text(encoding="utf-8")
    )
    assert run["reviewer_feedback_present"] is True
    assert "requested changes" in run["reviewer_feedback_summary"]
    assert "Add missing usage section" in run["reviewer_feedback_summary"]
    assert "feedback_context:" not in run["reviewer_feedback_summary"]


def test_reviewer_feedback_forwarded_field_takes_precedence(tmp_path: Path) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-059.yaml",
        attempt=1,
        feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-079",
        result="failed",
        failed_gate="reviewer_request_changes",
        next_action="retry_same_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="passed",
        verification_failed_command=None,
        reviewer_status="failed:request_changes",
        reviewer_decision="request_changes",
        failed_reviewer_id="onboarding_review",
        implement_output="",
        gate_output="",
        verification_output="",
        reviewer_output="[reviewer:onboarding_review] decision=request_changes",
        reviewer_feedback_forwarded=(
            "reviewer 'onboarding_review' feedback (decision=request_changes): "
            "Use the repo README conventions.\nfeedback_context:\nclean-room sandbox"
        ),
        feedback="(ignored) not a reviewer line",
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: "abc1234",
    )

    run = json.loads(
        (_progress_root(tmp_path) / "runs" / "runs.jsonl").read_text(encoding="utf-8")
    )
    assert run["reviewer_feedback_present"] is True
    assert "onboarding_review" in run["reviewer_feedback_summary"]


def test_reviewer_feedback_summary_truncates_after_stripping_context() -> None:
    text = (
        "reviewer 'onboarding_review' feedback (decision=request_changes): "
        + ("x" * 50)
        + "\nfeedback_context:\n"
        + ("y" * 500)
    )
    stripped = _strip_feedback_context_blocks(text)
    assert "feedback_context:" not in stripped
    summarized = _summarize_reviewer_feedback(text, max_chars=32)
    assert summarized.endswith("...[truncated]")
    assert "feedback_context:" not in summarized


def test_command_timing_line_includes_reviewer_id() -> None:
    timing = CommandTiming(
        phase="reviewers",
        gate=None,
        reviewer_id="onboarding_review",
        command="run_reviewer",
        started_at="1970-01-01T00:00:10Z",
        ended_at="1970-01-01T00:00:13Z",
        duration_sec=3,
    )
    line = _format_command_timing_line(timing)
    assert "reviewer_id=onboarding_review" in line


def test_non_verbose_terminal_output_shows_verification_summary(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    verification_command = "uv run pytest -q tests/test_loop_output.py"
    monkeypatch.setattr(presentation_module, "stdout_is_tty", lambda _stdout: False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    print_summary(
        IterationSummaryInputs(
            feature_id="FEAT-040",
            result="failed",
            failed_gate=None,
            attempt=2,
            next_action="retry_same_feature",
            selected_path="docs/spec/features/FEAT-040-per-iteration-verification-feedback-and-failure-signaling.yaml",
            implement_step="default opencode implement step",
            log_path=".engineeringagent/progress/features/FEAT-040/run.txt",
            verification_status=f"failed:{verification_command}",
            verification_failed_command=verification_command,
            reviewer_status="failed:request_changes",
            reviewer_decision="request_changes",
            failed_reviewer_id="security-reviewer",
        )
    )

    output = capsys.readouterr().out
    assert "🧪 Verify: failed (uv run pytest -q tests/test_loop_output.py)" in output
    assert (
        "👀 Reviewer: failed:request_changes (request_changes) [security-reviewer]"
        in output
    )
    assert "❌ Failed: gate=unknown" in output


def test_non_verbose_terminal_output_surfaces_phase_progress_context(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.setattr(presentation_module, "stdout_is_tty", lambda _stdout: False)

    print_summary(
        IterationSummaryInputs(
            feature_id="FEAT-181",
            result="passed",
            failed_gate=None,
            attempt=3,
            next_action="continue_same_feature",
            selected_path="docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/spec.yaml",
            implement_step="uv run engineeringagent implement",
            progress_kind="phase",
            progress_id="P3",
            progress_title="Move implementation sequencing from subtasks to plan phases",
        )
    )

    output = capsys.readouterr().out
    assert (
        "📍 Progress: phase P3 - Move implementation sequencing from subtasks to plan phases"
        in output
    )
