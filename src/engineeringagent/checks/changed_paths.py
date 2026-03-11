from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from engineeringagent.adapters.vcs import GitCliVersionControlGateway
from engineeringagent.ports import VersionControlFailure, VersionControlGateway


FALLBACK_CHANGE_DISCOVERY_REASON = "fallback_run_all_change_discovery_failed"
_DEFAULT_VERSION_CONTROL = GitCliVersionControlGateway()


class ChangedPathsResult(BaseModel):
    """Deterministic changed-path discovery result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    paths: tuple[str, ...]
    run_all: bool
    reason: str | None


def collect_changed_paths(
    cwd: Path,
    *,
    base: str | None = None,
    head: str | None = None,
    version_control: VersionControlGateway | None = None,
) -> ChangedPathsResult:
    """Collect repository-relative changed paths for on_change matching."""

    gateway = _DEFAULT_VERSION_CONTROL if version_control is None else version_control
    try:
        diff_summary = gateway.diff_against_base(
            cwd,
            base_ref=base,
            head_ref=head,
        )
    except VersionControlFailure:
        return ChangedPathsResult(
            paths=(),
            run_all=True,
            reason=FALLBACK_CHANGE_DISCOVERY_REASON,
        )

    changed_paths: set[str] = set()
    for line in diff_summary.summary_text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            return ChangedPathsResult(
                paths=(),
                run_all=True,
                reason=FALLBACK_CHANGE_DISCOVERY_REASON,
            )

        status = parts[0]
        if status.startswith("R"):
            if len(parts) < 3:
                return ChangedPathsResult(
                    paths=(),
                    run_all=True,
                    reason=FALLBACK_CHANGE_DISCOVERY_REASON,
                )
            changed_paths.add(parts[1].replace("\\", "/"))
            changed_paths.add(parts[2].replace("\\", "/"))
            continue

        changed_paths.add(parts[1].replace("\\", "/"))

    return ChangedPathsResult(
        paths=tuple(sorted(changed_paths)),
        run_all=False,
        reason=None,
    )
