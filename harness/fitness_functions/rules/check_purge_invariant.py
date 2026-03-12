from __future__ import annotations

import subprocess
from pathlib import Path

from engineeringagent.checks import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "quality.purge-invariant"
PROJECT_ROOT = Path(".")
EXCLUDED_PREFIXES = (
    "docs/spec/features_done/",
    ".engineeringagent/progress/",
)


def _purge_forbidden_needles() -> tuple[str, ...]:
    removed_reviewer_id = "_".join(["readme", "process"])
    removed_sandbox_mode = "_".join(["clean", "room", "readme", "cli"])
    return (removed_reviewer_id, removed_sandbox_mode)


def _tracked_project_files(project_root: Path) -> tuple[tuple[str, ...], list[str]]:
    proc = subprocess.run(
        ["git", "ls-files"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        detail = f": {stderr}" if stderr else ""
        return (), [f"git ls-files failed{detail}"]

    return (
        tuple(
            rel
            for line in (proc.stdout or "").splitlines()
            for rel in (line.strip(),)
            if rel and not rel.endswith("/") and not rel.startswith(EXCLUDED_PREFIXES)
        ),
        [],
    )


def _read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _collect_violations(project_root: Path) -> list[str]:
    if not (project_root / ".git").exists():
        return []

    needles = _purge_forbidden_needles()
    tracked_files, failures = _tracked_project_files(project_root)
    if failures:
        return failures

    violations: list[str] = []
    needle_blobs = tuple(needle.encode("utf-8") for needle in needles)
    for rel in tracked_files:
        payload = _read_bytes(project_root / rel)
        if payload is None:
            continue
        for needle, needle_blob in zip(needles, needle_blobs, strict=True):
            if needle_blob not in payload:
                continue
            violations.append(
                f"{rel}: forbidden token present (purge invariant): {needle}"
            )
            break
    return violations


def main() -> int:
    """Report forbidden tracked tokens that must stay purged from the repo."""
    violations = sorted(_collect_violations(PROJECT_ROOT))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Tracked repository files satisfy the purge invariant."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} purge invariant violation(s)."
    )
    emit_fitness_result(
        FitnessRuleResult(
            contract_version=CONTRACT_VERSION,
            rule_id=RULE_ID,
            status=status,
            severity=RuleSeverity.ERROR,
            summary=summary,
            violations=violations,
        )
    )
    return 0 if status == RuleStatus.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
