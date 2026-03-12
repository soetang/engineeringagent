"""Adapter-owned agent runtime support helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from engineeringagent.adapters.progress import paths as progress_paths
from engineeringagent.ports import AgentBackendError

from .opencode.client import DEFAULT_OPENCODE_AGENT
from .opencode.permissions import (
    PERMISSION_REMEDIATION_HINT,
    output_has_permission_rejection,
    run_permission_probe,
)
from .registry import resolve_backend_id


def preflight(project_root: Path) -> bool:
    """Run backend-selected preflight checks before loop execution."""
    backend_id = resolve_backend_id(project_root)
    if backend_id == "opencode":
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
        result = run_permission_probe(project_root)
        if result.ok:
            print("OpenCode permission precheck passed.")
            return True

        print(
            f"Precondition failed: OpenCode permission precheck failed ({result.reason})"
        )
        if result.output:
            print(result.output, end="" if result.output.endswith("\n") else "\n")
        print(PERMISSION_REMEDIATION_HINT)
        return False
    return True


def describe_action(project_root: Path, *, action: str, structured: bool) -> str:
    """Return stable backend-specific action labels for runtime telemetry."""
    normalized_action = action.strip()
    if not normalized_action:
        raise ValueError("action must be a non-empty string")

    backend_id = resolve_backend_id(project_root)
    if backend_id == "opencode":
        command = f"opencode run --agent {DEFAULT_OPENCODE_AGENT}"
        if structured:
            return f"{command} --format json"
        return command

    return f"{backend_id} run {normalized_action}"


def classify_backend_exception(exc: Exception) -> tuple[str, str]:
    """Map backend invocation exceptions to deterministic gate + message."""
    if isinstance(exc, FileNotFoundError):
        return ("agent_missing", "[implement] backend executable missing")

    if isinstance(exc, subprocess.TimeoutExpired):
        return (
            "agent_timeout",
            "[implement] backend timed out before producing output",
        )

    if isinstance(exc, AgentBackendError):
        failed_gate = f"{exc.backend}_build"
        if exc.backend == "opencode" and output_has_permission_rejection(exc.output):
            failed_gate = "opencode_permission"

        message = exc.output.strip() or exc.message.strip()
        if not message:
            message = f"{exc.backend} backend failure"
        return (failed_gate, message)

    message = str(exc).strip() or exc.__class__.__name__
    return ("agent_error", message)


def should_handle_backend_exception(exc: Exception) -> bool:
    """Return whether implement-step orchestration should handle the exception."""
    if isinstance(exc, (FileNotFoundError, subprocess.TimeoutExpired)):
        return True
    return exc.__class__.__name__ in {
        "AgentBackendError",
        "AgentOutputValidationError",
    }


def format_failed_backend_output(command: str, exc: Exception, message: str) -> str:
    """Render deterministic implement-step output for handled backend failures."""
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
        details = exc.output.strip() or message
        returncode = exc.returncode if isinstance(exc.returncode, int) else 1
        return (
            f"[implement] command={command}\n"
            f"[implement] returncode={returncode}\n"
            f"{details}"
        )

    return f"[implement] command={command}\n[implement] error={message}"
