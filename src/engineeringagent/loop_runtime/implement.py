"""Loop runtime implementation phase helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

from engineeringagent.loop_runtime.models import ImplementStepInputs
from engineeringagent.opencode.client import DEFAULT_OPENCODE_AGENT
from engineeringagent.opencode_permissions import output_has_permission_rejection
from engineeringagent import progress_paths
from engineeringagent.prompts import (
    build_implementation_prompt,
)


def run_implement_step_from_inputs(
    implement_inputs: ImplementStepInputs,
    *,
    start_agent_fn: Callable[..., Any],
) -> tuple[bool, str | None, str]:
    """Run implement logic while facade keeps public signature seams."""
    if implement_inputs.skip_implement:
        print("Implement step: skipped")
        return (True, None, "[implement] skipped")

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

    print(f"Implement step: opencode run --agent {DEFAULT_OPENCODE_AGENT}")
    try:
        proc = start_agent_fn(implement_inputs.project_root, prompt)
    except FileNotFoundError:
        return (False, "opencode_missing", "[implement] opencode executable missing")

    _print_process_output(proc, verbose_output=implement_inputs.verbose_output)
    output = (proc.stdout or "") + (proc.stderr or "")
    command_output = (
        f"[implement] command=opencode run --agent {DEFAULT_OPENCODE_AGENT} <prompt>\n"
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


def _print_process_output(proc: Any, *, verbose_output: bool) -> None:
    if not verbose_output:
        return
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)


def requires_opencode_permission_precheck(
    skip_implement: bool,
) -> bool:
    """Return whether default OpenCode mode requires permission precheck."""
    return not skip_implement


def run_opencode_permission_precheck(
    project_root: Path,
    skip_implement: bool,
    *,
    run_permission_probe_fn: Callable[[Path], Any],
    permission_remediation_hint: str,
) -> bool:
    """Run OpenCode permission precheck for default implement mode."""
    if not requires_opencode_permission_precheck(
        skip_implement=skip_implement,
    ):
        return True

    print("Running pre-run OpenCode permission precheck (default implement mode).")
    print(
        "Hint: if OpenCode cannot proceed or appears stuck, interrupt and rerun with "
        "--skip-implement to bypass the implement step and run gates only."
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
    print("Hint: use --skip-implement to bypass the implement step and run gates only.")
    return False
