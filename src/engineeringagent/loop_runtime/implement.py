"""Loop runtime implementation phase helpers."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from engineeringagent.agents import (
    AgentBackendError,
    classify_backend_exception,
    describe_action,
)
from engineeringagent.loop_runtime.models import ImplementStepInputs
from engineeringagent.progress import logging as progress_logging
from engineeringagent.progress import paths as progress_paths
from engineeringagent.prompts import (
    build_implementation_prompt,
)


def run_implement_step_from_inputs(
    implement_inputs: ImplementStepInputs,
    *,
    run_agent_fn: Callable[[Path, str], str],
) -> tuple[bool, str | None, str]:
    """Run implement logic while facade keeps public signature seams."""
    return _run_implement(
        implement_inputs,
        run_agent_fn=run_agent_fn,
    )


def _run_implement(
    implement_inputs: ImplementStepInputs,
    *,
    run_agent_fn: Callable[[Path, str], str],
) -> tuple[bool, str | None, str]:
    prompt = _build_implement_prompt(implement_inputs)
    command = describe_action(
        implement_inputs.project_root,
        action="implement",
        structured=False,
    )

    _ensure_progress_artifacts(implement_inputs)
    print(f"Implement step: {command}", flush=True)
    try:
        output = run_agent_fn(implement_inputs.project_root, prompt)
    except (AgentBackendError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        failed_gate, message = classify_backend_exception(exc)
        command_output = _format_failed_implement_output(
            command=command,
            exc=exc,
            message=message,
        )
        return (False, failed_gate, command_output)

    _print_agent_output(output, verbose_output=implement_inputs.verbose_output)
    command_output = (
        f"[implement] command={command}\n[implement] returncode=0\n{output}"
    )
    return (True, None, command_output)


def _format_failed_implement_output(
    *, command: str, exc: Exception, message: str
) -> str:
    if isinstance(exc, FileNotFoundError):
        return message

    if isinstance(exc, subprocess.TimeoutExpired):
        return (
            f"[implement] command={command}\n"
            "[implement] error=timeout\n"
            f"{message}.\n"
            "[implement] hint: interrupt stuck runs and investigate backend credentials/config.\n"
            "[implement] hint: for a non-mutating preview use `engineeringagent run --dry-run`.\n"
        )

    if isinstance(exc, AgentBackendError):
        output = exc.output.strip()
        details = output or message
        returncode = exc.returncode if exc.returncode is not None else 1
        return (
            f"[implement] command={command}\n"
            f"[implement] returncode={returncode}\n"
            f"{details}"
        )

    return f"[implement] command={command}\n[implement] error={message}"


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


def _print_agent_output(output: str, *, verbose_output: bool) -> None:
    if not verbose_output:
        return
    if output:
        print(output, end="")
