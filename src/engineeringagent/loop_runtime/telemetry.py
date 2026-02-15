"""Loop runtime telemetry helpers."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

import engineeringagent.progress_logging as progress_logging
import engineeringagent.progress_paths as progress_paths

from .models import IterationTelemetryInputs

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def now_iso() -> str:
    """Return current UTC timestamp in compact ISO-8601 format."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def append_run(log_path: Path, payload: dict[str, Any]) -> None:
    """Append one loop telemetry record as JSONL."""
    progress_logging.append_jsonl_record(log_path=log_path, payload=payload)


def _append_feature_progress_log(log_path: Path, lines: Sequence[str]) -> None:
    progress_logging.append_text_block(log_path=log_path, lines=lines)


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

    hook_feedback = telemetry_inputs.hook_feedback
    if not isinstance(hook_feedback, str) or not hook_feedback.strip():
        return None
    if telemetry_inputs.reviewer_status == "not_run":
        return None
    if not hook_feedback.lstrip().startswith("reviewer '"):
        return None
    return _strip_ansi(hook_feedback).strip()


def _summarize_reviewer_feedback(text: str, max_chars: int = 240) -> str:
    compact = " ".join(text.split())
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


def write_iteration_telemetry(
    telemetry_inputs: IterationTelemetryInputs,
    *,
    git_head_resolver: Callable[[Path], str | None],
) -> str:
    """Persist telemetry JSONL and per-feature progress log for one iteration."""
    project_root = telemetry_inputs.iteration_inputs.project_root
    feature_id = telemetry_inputs.feature_id or "unknown-feature"
    runs_log = progress_paths.runs_jsonl_path(project_root)
    feature_progress_log_path = progress_paths.run_feature_log_path(
        project_root, feature_id
    )
    feature_progress_log_reference = progress_paths.run_feature_log_reference(
        project_root, feature_id
    )

    run_payload: dict[str, Any] = {
        "ts": now_iso(),
        "feature_id": telemetry_inputs.feature_id,
        "subtask_id": None,
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
        "ts="
        f"{run_payload['ts']} attempt={telemetry_inputs.iteration_inputs.attempt} "
        f"feature_id={run_payload.get('feature_id') or 'unknown-feature'}",
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
        "result="
        f"{run_payload.get('result')} failed_gate={run_payload.get('failed_gate') or '-'} "
        f"next_action={run_payload.get('next_action')}",
    ]
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
    if reviewer_feedback_forwarded is not None:
        feature_progress_log_lines.extend(
            [
                "reviewer_feedback_forwarded_begin",
                _truncate_feedback(reviewer_feedback_forwarded.rstrip("\n")),
                "reviewer_feedback_forwarded_end",
            ]
        )
    if telemetry_inputs.hook_feedback:
        feature_progress_log_lines.append(
            f"detail={_truncate_feedback(telemetry_inputs.hook_feedback)}"
        )
    _append_feature_progress_log(
        feature_progress_log_path,
        [_strip_ansi(line) for line in feature_progress_log_lines],
    )
    append_run(runs_log, run_payload)
    return feature_progress_log_reference
