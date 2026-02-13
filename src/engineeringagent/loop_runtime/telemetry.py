"""Loop runtime telemetry helpers."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from .models import IterationTelemetryInputs


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
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file_handle:
        file_handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def _sanitize_feature_id_for_log(feature_id: str) -> str:
    sanitized = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_" for char in feature_id
    ).strip("_")
    return sanitized or "unknown-feature"


def _resolve_feature_progress_log_path(project_root: Path, feature_id: str) -> Path:
    safe_feature_id = _sanitize_feature_id_for_log(feature_id)
    return project_root / "progress" / f"run-feature-{safe_feature_id}.txt"


def _append_feature_progress_log(log_path: Path, lines: Sequence[str]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file_handle:
        file_handle.write("\n".join(lines) + "\n")


def _truncate_feedback(text: str, max_chars: int = 8_000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


def write_iteration_telemetry(
    telemetry_inputs: IterationTelemetryInputs,
    *,
    git_head_resolver: Callable[[Path], str | None],
) -> str:
    """Persist telemetry JSONL and per-feature progress log for one iteration."""
    runs_log = (
        telemetry_inputs.iteration_inputs.project_root / "progress" / "runs.jsonl"
    )
    feature_progress_log_path = _resolve_feature_progress_log_path(
        telemetry_inputs.iteration_inputs.project_root,
        telemetry_inputs.feature_id or "unknown-feature",
    )
    try:
        feature_progress_log_reference = str(
            feature_progress_log_path.relative_to(
                telemetry_inputs.iteration_inputs.project_root
            )
        )
    except ValueError:
        feature_progress_log_reference = str(feature_progress_log_path)

    run_payload: dict[str, Any] = {
        "ts": now_iso(),
        "feature_id": telemetry_inputs.feature_id,
        "subtask_id": None,
        "result": telemetry_inputs.result,
        "failed_gate": telemetry_inputs.failed_gate,
        "duration_sec": int(time.time() - telemetry_inputs.started),
        "attempt": telemetry_inputs.iteration_inputs.attempt,
        "commit": git_head_resolver(telemetry_inputs.iteration_inputs.project_root),
        "next_action": telemetry_inputs.next_action,
        "log_path": feature_progress_log_reference,
    }

    feature_progress_log_lines = [
        "ts="
        f"{run_payload['ts']} attempt={telemetry_inputs.iteration_inputs.attempt} "
        f"feature_id={telemetry_inputs.feature_id or 'unknown-feature'}",
        f"feature_path={telemetry_inputs.iteration_inputs.feature_path}",
        f"implement={telemetry_inputs.implement_status}",
        f"gates={telemetry_inputs.gate_status}",
        "result="
        f"{telemetry_inputs.result} failed_gate={telemetry_inputs.failed_gate or '-'} "
        f"next_action={telemetry_inputs.next_action}",
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
    if telemetry_inputs.hook_feedback:
        feature_progress_log_lines.append(
            f"detail={_truncate_feedback(telemetry_inputs.hook_feedback)}"
        )
    _append_feature_progress_log(feature_progress_log_path, feature_progress_log_lines)
    append_run(runs_log, run_payload)
    return feature_progress_log_reference
