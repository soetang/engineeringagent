"""Loop runtime implementation phase helpers."""

from __future__ import annotations

import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from engineeringagent.loop_runtime.models import ImplementStepInputs
from engineeringagent.opencode.client import DEFAULT_OPENCODE_AGENT
from engineeringagent.opencode_permissions import output_has_permission_rejection
from engineeringagent import progress_paths
from engineeringagent import progress_logging
from engineeringagent.prompts import (
    build_implementation_prompt,
)


def _format_opencode_run_command(agent: str) -> str:
    return f"opencode run --agent {agent} <prompt>"


def run_implement_step_from_inputs(
    implement_inputs: ImplementStepInputs,
    *,
    start_agent_fn: Callable[..., Any],
) -> tuple[bool, str | None, str]:
    """Run implement logic while facade keeps public signature seams."""
    return _run_default_opencode_implement(
        implement_inputs,
        start_agent_fn=start_agent_fn,
    )


def _run_default_opencode_implement(
    implement_inputs: ImplementStepInputs,
    *,
    start_agent_fn: Callable[..., Any],
) -> tuple[bool, str | None, str]:
    prompt = _build_implement_prompt(implement_inputs)
    command = _format_opencode_run_command(DEFAULT_OPENCODE_AGENT)

    _ensure_progress_artifacts(implement_inputs)
    print(
        f"Implement step: opencode run --agent {DEFAULT_OPENCODE_AGENT}",
        flush=True,
    )
    try:
        proc = start_agent_fn(implement_inputs.project_root, prompt)
    except FileNotFoundError:
        return (False, "opencode_missing", "[implement] opencode executable missing")
    except subprocess.TimeoutExpired as exc:
        del exc
        command_output = (
            f"[implement] command={command}\n"
            "[implement] error=timeout\n"
            "[implement] opencode timed out before producing output.\n"
            "[implement] hint: interrupt stuck runs and investigate OpenCode credentials/config.\n"
            "[implement] hint: for a non-mutating preview use `engineeringagent run --dry-run`.\n"
        )
        return (False, "opencode_build", command_output)

    _print_process_output(proc, verbose_output=implement_inputs.verbose_output)
    output = (proc.stdout or "") + (proc.stderr or "")
    command_output = (
        f"[implement] command={command}\n"
        f"[implement] returncode={proc.returncode}\n"
        f"{output}"
    )
    if output_has_permission_rejection(output):
        return (False, "opencode_permission", command_output)
    if proc.returncode != 0:
        return (False, "opencode_build", command_output)
    return (True, None, command_output)


def _build_implement_prompt(implement_inputs: ImplementStepInputs) -> str:
    return build_implementation_prompt(
        feature=implement_inputs.feature,
        feature_path=implement_inputs.feature_path,
        hook_feedback=implement_inputs.hook_feedback,
    )


def _ensure_progress_artifacts(implement_inputs: ImplementStepInputs) -> None:
    project_root = implement_inputs.project_root
    feature_id = implement_inputs.feature.get("id")
    if not isinstance(feature_id, str) or not feature_id.strip():
        feature_id = "unknown-feature"

    progress_paths.progress_dir(project_root).mkdir(parents=True, exist_ok=True)
    progress_paths.runs_jsonl_path(project_root).touch(exist_ok=True)

    timestamp = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    progress_logging.append_text_block(
        log_path=progress_paths.run_feature_log_path(project_root, feature_id),
        lines=[
            (
                f"ts={timestamp} === IMPLEMENT START feature_id={feature_id} "
                f"feature_path={implement_inputs.feature_path} ==="
            )
        ],
    )


def _print_process_output(proc: Any, *, verbose_output: bool) -> None:
    if not verbose_output:
        return
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)


def run_opencode_permission_precheck(
    project_root: Path,
    *,
    run_permission_probe_fn: Callable[[Path], Any],
    permission_remediation_hint: str,
) -> bool:
    """Run OpenCode permission precheck before entering the loop."""
    print("Running pre-run OpenCode permission precheck.")
    print(
        "Hint: if OpenCode cannot proceed or appears stuck, interrupt and rerun after "
        "fixing permissions. For a non-mutating preview, use `engineeringagent run --dry-run`."
    )
    print(
        "Logs: "
        f"{progress_paths.runs_jsonl_reference(project_root)} and "
        f"{progress_paths.run_feature_log_template_reference(project_root)} "
        "(written after each iteration)."
    )
    result = run_permission_probe_fn(project_root)
    if result.ok:
        print("OpenCode permission precheck passed.")
        return True

    print(f"Precondition failed: OpenCode permission precheck failed ({result.reason})")
    if result.output:
        print(result.output, end="" if result.output.endswith("\n") else "\n")
    print(permission_remediation_hint)
    return False
