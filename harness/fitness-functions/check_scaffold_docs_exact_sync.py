from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from engineeringagent.fitness.envelope import emit_result_envelope


RULE_ID = "architecture.scaffold-docs-exact-sync"

_POLICY_PATH = Path("harness/scaffold_policy.yaml")
_TEMPLATE_ROOT = Path("src/engineeringagent/scaffold_templates")
_REMEDIATION = (
    "update src/engineeringagent/scaffold_templates to byte-for-byte match the "
    "canonical docs/ files declared in harness/scaffold_policy.yaml exact_sync."
)


@dataclass(frozen=True)
class _ExactSyncEntry:
    docs_path: Path
    template_name: str


def _load_scaffold_policy(project_root: Path) -> tuple[Path, list[_ExactSyncEntry]]:
    policy_path = project_root / _POLICY_PATH
    if not policy_path.exists():
        return Path("docs"), []

    with policy_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        return Path("docs"), []

    docs_root_raw = payload.get("docs_root")
    docs_root = Path(docs_root_raw) if isinstance(docs_root_raw, str) else Path("docs")

    exact_sync_raw = payload.get("exact_sync")
    if not isinstance(exact_sync_raw, list):
        return docs_root, []

    entries: list[_ExactSyncEntry] = []
    for item in exact_sync_raw:
        if not isinstance(item, dict):
            continue
        docs_path = item.get("docs_path")
        template_name = item.get("template_name")
        if not isinstance(docs_path, str) or not isinstance(template_name, str):
            continue
        entries.append(
            _ExactSyncEntry(docs_path=Path(docs_path), template_name=template_name)
        )

    return docs_root, entries


def _resolve_docs_path(docs_root: Path, docs_path: Path) -> Path:
    """Resolve docs_path supporting both docs-root-relative and repo-relative values."""
    if docs_path == docs_root or docs_root in docs_path.parents:
        return docs_path
    return docs_root / docs_path


def _describe_missing(path: Path) -> str:
    return f"{path}:1 missing file"


def _compare_exact_sync_pairs(project_root: Path) -> list[str]:
    violations: list[str] = []
    docs_root, entries = _load_scaffold_policy(project_root)

    policy_path = _POLICY_PATH
    if not entries:
        if not (project_root / policy_path).exists():
            violations.append(
                f"{policy_path}:1 missing scaffold policy; {_REMEDIATION}"
            )
        else:
            violations.append(
                f"{policy_path}:1 has no exact_sync entries configured; {_REMEDIATION}"
            )
        return sorted(violations)

    for entry in entries:
        docs_relative = _resolve_docs_path(docs_root, entry.docs_path)
        template_relative = _TEMPLATE_ROOT / entry.template_name

        docs_file = project_root / docs_relative
        template_file = project_root / template_relative

        missing_parts: list[str] = []
        if not docs_file.exists() or not docs_file.is_file():
            missing_parts.append(_describe_missing(docs_relative))
        if not template_file.exists() or not template_file.is_file():
            missing_parts.append(_describe_missing(template_relative))
        if missing_parts:
            violations.append(
                f"{docs_relative}:1 exact-sync pair missing path(s): "
                f"{', '.join(missing_parts)} (template={template_relative}); "
                f"{_REMEDIATION}"
            )
            continue

        docs_bytes = docs_file.read_bytes()
        template_bytes = template_file.read_bytes()
        if docs_bytes != template_bytes:
            violations.append(
                f"{docs_relative}:1 differs byte-for-byte from {template_relative}:1 "
                f"(policy={policy_path}); {_REMEDIATION}"
            )

    return sorted(violations)


def main() -> int:
    """Run the exact-sync check and emit a result envelope."""
    violations = _compare_exact_sync_pairs(Path("."))
    status = "pass" if not violations else "fail"
    summary = (
        "Configured scaffold docs exact-sync pairs match byte-for-byte."
        if status == "pass"
        else f"Detected {len(violations)} scaffold docs exact-sync violation(s)."
    )

    emit_result_envelope(
        rule_id=RULE_ID,
        status=status,
        severity="error",
        summary=summary,
        violations=violations,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
