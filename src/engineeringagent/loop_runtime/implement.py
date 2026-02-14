"""Loop runtime implementation phase helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

from engineeringagent.loop_runtime.models import ImplementStepInputs
from engineeringagent.opencode.client import DEFAULT_OPENCODE_AGENT
from engineeringagent.opencode_permissions import output_has_permission_rejection
from engineeringagent.prompts import (
    build_implementation_prompt,
    inject_retry_feedback,
)


def run_implement_step_from_inputs(
    implement_inputs: ImplementStepInputs,
    *,
    run_shell_command_fn: Callable[[Path, str], Any],
    start_agent_fn: Callable[..., Any],
) -> tuple[bool, str | None, str]:
    """Run implement logic while facade keeps public signature seams."""
    if implement_inputs.skip_implement:
        print("Implement step: skipped")
        return (True, None, "[implement] skipped")

    if implement_inputs.implement_command:
        return _run_custom_implement_command(
            implement_inputs,
            run_shell_command_fn=run_shell_command_fn,
        )

    return _run_default_opencode_implement(
        implement_inputs,
        start_agent_fn=start_agent_fn,
    )


def _run_custom_implement_command(
    implement_inputs: ImplementStepInputs,
    *,
    run_shell_command_fn: Callable[[Path, str], Any],
) -> tuple[bool, str | None, str]:
    command = implement_inputs.implement_command
    assert command is not None
    print(f"Implement step: custom command ({command})")
    proc = run_shell_command_fn(
        implement_inputs.project_root,
        command,
    )
    _print_process_output(proc, verbose_output=implement_inputs.verbose_output)

    output = (proc.stdout or "") + (proc.stderr or "")
    command_output = (
        f"[implement] command={command}\n"
        f"[implement] returncode={proc.returncode}\n"
        f"{output}"
    )
    if proc.returncode != 0:
        return (False, "implement_command", command_output)
    return (True, None, command_output)


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
    if implement_inputs.opencode_prompt:
        return inject_retry_feedback(
            implement_inputs.opencode_prompt,
            implement_inputs.hook_feedback,
        )
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
    implement_command: str | None,
    skip_implement: bool,
) -> bool:
    """Return whether default OpenCode mode requires permission precheck."""
    return implement_command is None and not skip_implement


def run_opencode_permission_precheck(
    project_root: Path,
    implement_command: str | None,
    skip_implement: bool,
    *,
    run_permission_probe_fn: Callable[[Path], Any],
    permission_remediation_hint: str,
) -> bool:
    """Run OpenCode permission precheck for default implement mode."""
    if not requires_opencode_permission_precheck(
        implement_command=implement_command,
        skip_implement=skip_implement,
    ):
        return True

    print("Running pre-run OpenCode permission precheck (default implement mode).")
    result = run_permission_probe_fn(project_root)
    if result.ok:
        print("OpenCode permission precheck passed.")
        return True

    print(f"Precondition failed: OpenCode permission precheck failed ({result.reason})")
    if result.output:
        print(result.output, end="" if result.output.endswith("\n") else "\n")
    print(permission_remediation_hint)
    print(
        "Hint: use --skip-implement or --implement-command to bypass default OpenCode implement mode."
    )
    return False
