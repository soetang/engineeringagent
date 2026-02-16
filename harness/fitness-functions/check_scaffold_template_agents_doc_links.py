from __future__ import annotations

from pathlib import Path

import yaml

from engineeringagent.fitness.envelope import emit_result_envelope


RULE_ID = "architecture.scaffold-template-agents-doc-links"

_POLICY_PATH = Path("harness/scaffold_policy.yaml")
_AGENTS_TEMPLATE_PATH = Path("src/engineeringagent/scaffold_templates/AGENTS.md")
_REMEDIATION = (
    "update src/engineeringagent/scaffold_templates/AGENTS.md to link each "
    "scaffolded reference doc listed in harness/scaffold_policy.yaml scaffold_docs "
    "with a short per-file description."
)


def _load_scaffold_doc_paths(project_root: Path) -> list[str]:
    policy_path = project_root / _POLICY_PATH
    if not policy_path.exists():
        return []

    with policy_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        return []

    raw_scaffold_docs = payload.get("scaffold_docs")
    if not isinstance(raw_scaffold_docs, list):
        return []

    scaffold_docs: list[str] = []
    for item in raw_scaffold_docs:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if not normalized:
            continue
        scaffold_docs.append(normalized)

    return scaffold_docs


def _is_bullet_line(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith("- ") or stripped.startswith("* ")


def _line_contains_link_with_description(line: str, doc_path: str) -> bool:
    if doc_path not in line:
        return False
    if not _is_bullet_line(line):
        return False
    suffix = line.split(doc_path, 1)[1]
    if ":" not in suffix:
        return False
    after_colon = suffix.split(":", 1)[1].strip()
    return bool(after_colon)


def _agents_links_violations(project_root: Path) -> list[str]:
    violations: list[str] = []

    if not (project_root / _POLICY_PATH).exists():
        violations.append(f"{_POLICY_PATH}:1 missing scaffold policy; {_REMEDIATION}")
        return sorted(violations)

    scaffold_docs = _load_scaffold_doc_paths(project_root)
    if not scaffold_docs:
        violations.append(
            f"{_POLICY_PATH}:1 has no scaffold_docs configured; {_REMEDIATION}"
        )
        return sorted(violations)

    template_file = project_root / _AGENTS_TEMPLATE_PATH
    if not template_file.exists() or not template_file.is_file():
        violations.append(
            f"{_AGENTS_TEMPLATE_PATH}:1 missing scaffold template; {_REMEDIATION}"
        )
        return sorted(violations)

    agents_text = template_file.read_text(encoding="utf-8")
    lines = agents_text.splitlines()

    for doc_path in sorted(set(scaffold_docs)):
        candidates = [
            (index, line)
            for index, line in enumerate(lines, start=1)
            if doc_path in line
        ]
        if not candidates:
            violations.append(
                f"{_AGENTS_TEMPLATE_PATH}:1 missing link for {doc_path} "
                f"(policy={_POLICY_PATH}); {_REMEDIATION}"
            )
            continue

        if any(
            _line_contains_link_with_description(line, doc_path)
            for _, line in candidates
        ):
            continue

        first_line = candidates[0][0]
        violations.append(
            f"{_AGENTS_TEMPLATE_PATH}:{first_line} missing per-file description for "
            f"{doc_path} (policy={_POLICY_PATH}); {_REMEDIATION}"
        )

    return sorted(violations)


def main() -> int:
    """Run the scaffolded-docs AGENTS link check and emit a result envelope."""
    violations = _agents_links_violations(Path("."))
    status = "pass" if not violations else "fail"
    summary = (
        "Scaffold template AGENTS links each scaffolded reference doc."
        if status == "pass"
        else f"Detected {len(violations)} scaffold AGENTS docs link violation(s)."
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
