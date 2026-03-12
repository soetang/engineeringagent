"""Legacy compatibility shim for adapter-owned agent helpers."""

from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.agents.helpers import (
    classify_backend_exception,
    describe_action,
)
from engineeringagent.adapters.agents.opencode.permissions import (
    PERMISSION_REMEDIATION_HINT,
    run_permission_probe,
)
from engineeringagent.adapters.agents.registry import resolve_backend_id
from engineeringagent.adapters.progress import paths as progress_paths


def preflight(project_root: Path) -> bool:
    """Run backend-selected preflight checks through the legacy shim surface."""
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

__all__ = [
    "PERMISSION_REMEDIATION_HINT",
    "classify_backend_exception",
    "describe_action",
    "preflight",
    "run_permission_probe",
]
