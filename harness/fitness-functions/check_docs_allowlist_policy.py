from __future__ import annotations

from pathlib import Path

from engineeringagent.checks import emit_result_envelope
from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.docs-allowlist-policy"

_POLICY_PATH = Path("harness/scaffold_policy.yaml")

_REMEDIATION = (
    "Add every markdown file under docs_root (excluding docs_root/spec/) to exactly one of "
    "human_docs or agent_docs in harness/scaffold_policy.yaml."
)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _parse_policy_minimal(policy_text: str) -> dict[str, object]:
    """Parse a small YAML subset from harness/scaffold_policy.yaml.

    Constraint: stdlib-only.

    Supported constructs:
    - Top-level scalar key-values: `key: value`
    - Top-level lists of scalars:
        key:
          - item

    This parser intentionally ignores complex/nested YAML values.
    """

    result: dict[str, object] = {}
    list_key: str | None = None

    for raw_line in policy_text.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line or raw_line.lstrip().startswith("#"):
            continue

        if list_key in {"human_docs", "agent_docs"} and stripped_line.startswith("-"):
            item = stripped_line[1:].strip()
            if item:
                item = _strip_quotes(item)
                bucket = result.setdefault(list_key, [])
                if isinstance(bucket, list):
                    bucket.append(item)
            continue

        if (
            raw_line.startswith(" ")
            or raw_line.startswith("\t")
            or stripped_line.startswith("-")
        ):
            continue

        list_key = None

        if ":" not in raw_line:
            continue
        key, rest = raw_line.split(":", 1)
        key = key.strip()
        rest = rest.strip()

        if not key:
            continue

        if rest == "":
            if key in {"human_docs", "agent_docs"}:
                result.setdefault(key, [])
                list_key = key
            continue

        # Accept flow-style empty lists written by PyYAML (e.g. `human_docs: []`).
        if key in {"human_docs", "agent_docs"} and "".join(rest.split()) == "[]":
            result[key] = []
            continue

        if key in {"contract_version", "docs_root"}:
            result[key] = _strip_quotes(rest)

    return result


def _resolve_docs_allowlist_entry(*, docs_root: Path, entry: str) -> Path:
    """Resolve entry supporting both docs-root-relative and repo-relative values."""
    entry_path = Path(_strip_quotes(entry))
    if entry_path == docs_root or docs_root in entry_path.parents:
        return entry_path
    return docs_root / entry_path


def _collect_docs_markdown_files(*, project_root: Path, docs_root: Path) -> set[str]:
    root = project_root / docs_root
    if not root.exists() or not root.is_dir():
        return set()

    discovered: set[str] = set()
    for path in root.rglob("*.md"):
        if not path.is_file():
            continue
        relative = path.relative_to(project_root)
        relative_to_docs = path.relative_to(root)
        if relative_to_docs.parts and relative_to_docs.parts[0] == "spec":
            continue
        discovered.add(relative.as_posix())
    return discovered


def _validate_policy(
    *,
    project_root: Path,
    policy_path: Path,
) -> tuple[Path, set[str], set[str], list[str]]:
    violations: list[str] = []
    docs_root = Path("docs")
    human_docs: set[str] = set()
    agent_docs: set[str] = set()

    full_path = project_root / policy_path
    if not full_path.exists():
        violations.append(f"{policy_path}:1 missing scaffold policy; {_REMEDIATION}")
        return docs_root, human_docs, agent_docs, sorted(violations)

    policy_payload = _parse_policy_minimal(full_path.read_text(encoding="utf-8"))

    for key in ("contract_version", "docs_root", "human_docs", "agent_docs"):
        if key not in policy_payload:
            violations.append(
                f"{policy_path}:1 missing required key {key}; {_REMEDIATION}"
            )

    docs_root_raw = policy_payload.get("docs_root")
    if isinstance(docs_root_raw, str) and docs_root_raw.strip():
        docs_root = Path(docs_root_raw)

    human_raw = policy_payload.get("human_docs")
    if isinstance(human_raw, list):
        for item in human_raw:
            if isinstance(item, str) and item.strip():
                human_docs.add(
                    _resolve_docs_allowlist_entry(
                        docs_root=docs_root, entry=item
                    ).as_posix()
                )

    agent_raw = policy_payload.get("agent_docs")
    if isinstance(agent_raw, list):
        for item in agent_raw:
            if isinstance(item, str) and item.strip():
                agent_docs.add(
                    _resolve_docs_allowlist_entry(
                        docs_root=docs_root, entry=item
                    ).as_posix()
                )

    return docs_root, human_docs, agent_docs, sorted(violations)


def _check_docs_allowlist_policy(project_root: Path) -> list[str]:
    docs_root, human_docs, agent_docs, violations = _validate_policy(
        project_root=project_root,
        policy_path=_POLICY_PATH,
    )

    discovered = _collect_docs_markdown_files(
        project_root=project_root, docs_root=docs_root
    )

    overlap = sorted(human_docs.intersection(agent_docs))
    for path in overlap:
        violations.append(
            f"{path}:1 appears in both human_docs and agent_docs (policy={_POLICY_PATH}); "
            f"{_REMEDIATION}"
        )

    covered = human_docs.union(agent_docs)
    missing = sorted(discovered.difference(covered))
    for path in missing:
        violations.append(
            f"{path}:1 missing from both human_docs and agent_docs (policy={_POLICY_PATH}); "
            f"{_REMEDIATION}"
        )

    return sorted(violations)


def main() -> int:
    violations = _check_docs_allowlist_policy(Path("."))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "All docs markdown files are explicitly classified as human_docs or agent_docs."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} docs allowlist policy violation(s)."
    )

    emit_result_envelope(
        FitnessRuleResult(
            contract_version=CONTRACT_VERSION,
            rule_id=RULE_ID,
            status=status,
            severity=RuleSeverity.ERROR,
            summary=summary,
            violations=violations,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
