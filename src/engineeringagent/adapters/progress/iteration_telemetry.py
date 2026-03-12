"""Progress-adapter telemetry helpers for iteration reporting."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from engineeringagent.application.feature_iteration.contracts import (
    CommandTiming,
    IterationTelemetryInputs,
    PhaseTiming,
)
from engineeringagent.domain.audit import (
    ProgressEvent,
    fallback_implement_progress_envelope,
)
from engineeringagent.domain.shared import utc_now_iso
from engineeringagent.presentation.presenters import (
    HandoffRenderMetadata,
    render_handoff_markdown_entry,
)

from . import paths as progress_paths
from .filesystem_journal import FilesystemProgressJournal

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
FEEDBACK_CONTEXT_BLOCK_RE = re.compile(
    r"\nfeedback_context:\n.*?(?=\nreviewer '|\Z)",
    re.DOTALL,
)
_PROGRESS_JOURNAL = FilesystemProgressJournal()


def _strip_feedback_context_blocks(text: str) -> str:
    return FEEDBACK_CONTEXT_BLOCK_RE.sub("", text)


def append_run(project_root: Path, payload: dict[str, Any]) -> None:
    """Append one loop telemetry audit event as JSONL."""
    event_timestamp = str(payload.get("ts") or utc_now_iso())
    feature_id = payload.get("feature_id")
    normalized_feature_id = (
        feature_id.strip()
        if isinstance(feature_id, str) and feature_id.strip()
        else None
    )
    _PROGRESS_JOURNAL.append(
        project_root=project_root,
        event=ProgressEvent(
            timestamp=event_timestamp,
            event_kind="iteration.telemetry",
            feature_id=normalized_feature_id,
            payload=payload,
        ),
    )


def _append_feature_progress_log(
    project_root: Path,
    feature_id: str,
    lines: Sequence[str],
) -> None:
    _PROGRESS_JOURNAL.append_feature_log(
        project_root=project_root,
        feature_id=feature_id,
        lines=lines,
    )


def _truncate_feedback(text: str, max_chars: int = 8_000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)


def _sanitize_payload_strings(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            sanitized[key] = _strip_ansi(value)
        else:
            sanitized[key] = value
    return sanitized


def _resolve_forwarded_reviewer_feedback(
    telemetry_inputs: IterationTelemetryInputs,
) -> str | None:
    forwarded = telemetry_inputs.reviewer_feedback_forwarded
    if isinstance(forwarded, str) and forwarded.strip():
        return _strip_ansi(forwarded).strip()

    feedback = telemetry_inputs.feedback
    if not isinstance(feedback, str) or not feedback.strip():
        return None
    if telemetry_inputs.reviewer_status == "not_run":
        return None
    if not feedback.lstrip().startswith("reviewer '"):
        return None
    return _strip_ansi(feedback).strip()


def _summarize_reviewer_feedback(text: str, max_chars: int = 240) -> str:
    cleaned = _strip_feedback_context_blocks(text)
    compact = " ".join(cleaned.split())
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars] + "...[truncated]"


def _reviewer_feedback_metadata(
    telemetry_inputs: IterationTelemetryInputs,
) -> tuple[str | None, bool, str]:
    forwarded = _resolve_forwarded_reviewer_feedback(telemetry_inputs)
    if forwarded is None:
        return None, False, ""
    return forwarded, True, _summarize_reviewer_feedback(forwarded)


def _format_phase_timing_fields(timing: PhaseTiming) -> str:
    return (
        f"phase={timing.phase} "
        f"started_at={timing.started_at} "
        f"ended_at={timing.ended_at} "
        f"duration_sec={timing.duration_sec}"
    )


def _format_phase_timing_line(timing: PhaseTiming) -> str:
    return f"phase_timing {_format_phase_timing_fields(timing)}"


def _command_timing_fields_parts(timing: CommandTiming) -> list[str]:
    parts: list[str] = [f"phase={timing.phase}"]
    if timing.gate is not None:
        parts.append(f"gate={timing.gate}")
    if timing.reviewer_id is not None:
        parts.append(f"reviewer_id={timing.reviewer_id}")
    parts.extend(
        [
            f"command={timing.command}",
            f"started_at={timing.started_at}",
            f"ended_at={timing.ended_at}",
            f"duration_sec={timing.duration_sec}",
        ]
    )
    return parts


def _format_command_timing_line(timing: CommandTiming) -> str:
    return " ".join(["command_timing", *_command_timing_fields_parts(timing)])


def _slowest_summary_line(telemetry_inputs: IterationTelemetryInputs) -> str | None:
    best_duration = -1
    best_line: str | None = None

    for timing in telemetry_inputs.phase_timings:
        if timing.duration_sec > best_duration:
            best_duration = timing.duration_sec
            best_line = f"slowest=phase {_format_phase_timing_fields(timing)}"

    for timing in telemetry_inputs.command_timings:
        if timing.duration_sec > best_duration:
            best_duration = timing.duration_sec
            best_line = " ".join(
                ["slowest=command", *_command_timing_fields_parts(timing)]
            )

    return best_line


def write_iteration_telemetry(  # noqa: C901
    telemetry_inputs: IterationTelemetryInputs,
    *,
    git_head_resolver: Callable[[Path], str | None],
) -> str:
    """Persist telemetry JSONL and per-feature progress log for one iteration."""
    project_root = telemetry_inputs.iteration_inputs.project_root
    feature_id = telemetry_inputs.feature_id or "unknown-feature"
    feature_progress_log_reference = progress_paths.run_feature_log_reference(
        project_root, feature_id
    )

    run_payload: dict[str, Any] = {
        "ts": utc_now_iso(),
        "feature_id": telemetry_inputs.feature_id,
        "progress_kind": telemetry_inputs.progress_kind,
        "progress_id": telemetry_inputs.progress_id,
        "progress_title": telemetry_inputs.progress_title,
        "result": telemetry_inputs.result,
        "failed_gate": telemetry_inputs.failed_gate,
        "verification_status": telemetry_inputs.verification_status,
        "verification_failed_command": telemetry_inputs.verification_failed_command,
        "reviewer_status": telemetry_inputs.reviewer_status,
        "reviewer_decision": telemetry_inputs.reviewer_decision,
        "failed_reviewer_id": telemetry_inputs.failed_reviewer_id,
        "duration_sec": int(time.time() - telemetry_inputs.started),
        "attempt": telemetry_inputs.iteration_inputs.attempt,
        "commit": git_head_resolver(project_root),
        "next_action": telemetry_inputs.next_action,
        "log_path": feature_progress_log_reference,
    }
    (
        reviewer_feedback_forwarded,
        reviewer_feedback_present,
        reviewer_feedback_summary,
    ) = _reviewer_feedback_metadata(telemetry_inputs)
    run_payload["reviewer_feedback_present"] = reviewer_feedback_present
    run_payload["reviewer_feedback_summary"] = reviewer_feedback_summary
    run_payload = _sanitize_payload_strings(run_payload)

    feature_progress_log_lines = [
        (
            f"ts={run_payload['ts']} === ITERATION "
            f"attempt={telemetry_inputs.iteration_inputs.attempt} "
            f"feature_id={feature_id} ==="
        ),
        f"feature_path={telemetry_inputs.iteration_inputs.feature_path}",
        f"implement={telemetry_inputs.implement_status}",
        f"gates={telemetry_inputs.gate_status}",
        "verification="
        f"{telemetry_inputs.verification_status}"
        f" failed_command={telemetry_inputs.verification_failed_command or '-'}",
        "reviewer="
        f"{telemetry_inputs.reviewer_status}"
        f" decision={telemetry_inputs.reviewer_decision or '-'}"
        f" failed_reviewer={telemetry_inputs.failed_reviewer_id or '-'}",
        "reviewer_feedback="
        f"{'present' if reviewer_feedback_present else 'absent'}"
        f" summary={reviewer_feedback_summary or '-'}",
        "progress="
        f"{telemetry_inputs.progress_kind or '-'}:{telemetry_inputs.progress_id or '-'} "
        f"title={telemetry_inputs.progress_title or '-'}",
        "result="
        f"{run_payload.get('result')} failed_gate={run_payload.get('failed_gate') or '-'} "
        f"next_action={run_payload.get('next_action')}",
    ]

    for timing in telemetry_inputs.phase_timings:
        feature_progress_log_lines.append(_format_phase_timing_line(timing))

    for timing in telemetry_inputs.command_timings:
        feature_progress_log_lines.append(_format_command_timing_line(timing))

    slowest_summary = _slowest_summary_line(telemetry_inputs)
    if slowest_summary is not None:
        feature_progress_log_lines.append(slowest_summary)

    if telemetry_inputs.implement_output:
        feature_progress_log_lines.extend(
            [
                "implement_output_begin",
                telemetry_inputs.implement_output.rstrip("\n"),
                "implement_output_end",
            ]
        )
    if telemetry_inputs.gate_output:
        feature_progress_log_lines.extend(
            [
                "gate_output_begin",
                telemetry_inputs.gate_output.rstrip("\n"),
                "gate_output_end",
            ]
        )
    if telemetry_inputs.verification_output:
        feature_progress_log_lines.extend(
            [
                "verification_output_begin",
                telemetry_inputs.verification_output.rstrip("\n"),
                "verification_output_end",
            ]
        )
    if telemetry_inputs.reviewer_output:
        feature_progress_log_lines.extend(
            [
                "reviewer_output_begin",
                telemetry_inputs.reviewer_output.rstrip("\n"),
                "reviewer_output_end",
            ]
        )
    if telemetry_inputs.completion_output:
        feature_progress_log_lines.extend(
            [
                "completion_output_begin",
                telemetry_inputs.completion_output.rstrip("\n"),
                "completion_output_end",
            ]
        )
    if reviewer_feedback_forwarded is not None:
        feature_progress_log_lines.extend(
            [
                "reviewer_feedback_forwarded_begin",
                _truncate_feedback(reviewer_feedback_forwarded.rstrip("\n")),
                "reviewer_feedback_forwarded_end",
            ]
        )
    if telemetry_inputs.feedback:
        feature_progress_log_lines.append(
            f"detail={_truncate_feedback(telemetry_inputs.feedback)}"
        )
    _append_feature_progress_log(
        project_root,
        feature_id,
        [_strip_ansi(line) for line in feature_progress_log_lines],
    )
    append_run(project_root, run_payload)
    _write_feature_handoff_markdown(
        telemetry_inputs=telemetry_inputs,
        feature_id=feature_id,
        timestamp=str(run_payload["ts"]),
        project_root=project_root,
    )
    return feature_progress_log_reference


def _write_feature_handoff_markdown(
    *,
    telemetry_inputs: IterationTelemetryInputs,
    feature_id: str,
    timestamp: str,
    project_root: Path,
) -> None:
    envelope = telemetry_inputs.implement_handoff_envelope
    used_fallback = telemetry_inputs.implement_handoff_used_fallback
    if envelope is None or used_fallback:
        envelope = fallback_implement_progress_envelope(
            progress_kind=telemetry_inputs.progress_kind,
            progress_id=telemetry_inputs.progress_id,
            progress_title=telemetry_inputs.progress_title,
        )
        used_fallback = True

    entry_lines = render_handoff_markdown_entry(
        attempt=telemetry_inputs.iteration_inputs.attempt,
        envelope=envelope,
        metadata=HandoffRenderMetadata(
            timestamp=timestamp,
            used_fallback=used_fallback,
            progress_kind=telemetry_inputs.progress_kind,
            progress_id=telemetry_inputs.progress_id,
            progress_title=telemetry_inputs.progress_title,
        ),
    )
    _PROGRESS_JOURNAL.write_handoff(
        project_root=project_root,
        feature_id=feature_id,
        lines=entry_lines,
    )
