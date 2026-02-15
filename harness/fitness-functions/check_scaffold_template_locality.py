from __future__ import annotations

import ast
import re
from pathlib import Path

from result_envelope import emit_result_envelope


RULE_ID = "architecture.scaffold-template-locality"
_SOURCE_PACKAGE_ROOT = Path("src/engineeringagent")
_SCAFFOLD_TEMPLATE_ROOT = _SOURCE_PACKAGE_ROOT / "scaffold_templates"
_REQUIRED_SCAFFOLD_TEMPLATES = (
    "AGENTS.md",
    "precommit.core.yaml",
    "precommit.python_uv.yaml",
    "reference.docs-architecture-llms.md",
    "reference.workflow-llms.md",
)
_SCAFFOLD_TEMPLATE_ALLOWED_ROOT = _SOURCE_PACKAGE_ROOT / "scaffold_templates"
_SCAFFOLD_TEMPLATE_CANARY_TOKENS = (
    ("agent", "operating", "guide", "for", "this", "repository"),
    ("keep", "this", "file", "concise"),
    ("first", "window", "boot", "sequence"),
    ("audience", "split"),
)
_SCAFFOLD_TEMPLATE_LOCALITY_REMEDIATION = (
    "move scaffold template content into "
    "src/engineeringagent/scaffold_templates and keep scaffold content reads "
    "inside engineeringagent.init_scaffold."
)


def _iter_literal_string_segments(tree: ast.AST) -> list[tuple[int, str]]:
    segments: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            line = getattr(node, "lineno", 1)
            segments.append((line, node.value))
            continue
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    line = getattr(value, "lineno", getattr(node, "lineno", 1))
                    segments.append((line, value.value))
    return segments


def _normalize_for_canary_matching(value: str) -> str:
    lowered = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(normalized.split())


def _is_scaffold_template_allowed_path(relative_path: Path) -> bool:
    return (
        relative_path == _SCAFFOLD_TEMPLATE_ALLOWED_ROOT
        or _SCAFFOLD_TEMPLATE_ALLOWED_ROOT in relative_path.parents
    )


def _scaffold_template_integrity_violations(project_root: Path) -> list[str]:
    template_root = project_root / _SCAFFOLD_TEMPLATE_ROOT
    violations: list[str] = []
    if not template_root.exists() or not template_root.is_dir():
        violations.append(
            "src/engineeringagent/scaffold_templates:1 missing scaffold template "
            f"directory; {_SCAFFOLD_TEMPLATE_LOCALITY_REMEDIATION}"
        )
        return violations

    for template_name in _REQUIRED_SCAFFOLD_TEMPLATES:
        template_path = template_root / template_name
        relative = template_path.relative_to(project_root)
        if not template_path.exists() or not template_path.is_file():
            violations.append(
                f"{relative}:1 missing required scaffold template "
                f"'{template_name}'; {_SCAFFOLD_TEMPLATE_LOCALITY_REMEDIATION}"
            )
            continue
        if not template_path.read_text(encoding="utf-8").strip():
            violations.append(
                f"{relative}:1 required scaffold template '{template_name}' is empty; "
                f"{_SCAFFOLD_TEMPLATE_LOCALITY_REMEDIATION}"
            )

    return violations


def _scaffold_template_source_locality_violations(project_root: Path) -> list[str]:
    source_root = project_root / _SOURCE_PACKAGE_ROOT
    violations: list[str] = []
    if not source_root.exists():
        violations.append(
            f"{_SOURCE_PACKAGE_ROOT}:1 missing source package root; "
            f"{_SCAFFOLD_TEMPLATE_LOCALITY_REMEDIATION}"
        )
        return violations

    canaries = tuple(" ".join(tokens) for tokens in _SCAFFOLD_TEMPLATE_CANARY_TOKENS)
    normalized_canaries = {
        canary: _normalize_for_canary_matching(canary) for canary in canaries
    }

    for file_path in sorted(source_root.rglob("*.py")):
        relative = file_path.relative_to(project_root)
        if _is_scaffold_template_allowed_path(relative):
            continue

        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for line, segment in _iter_literal_string_segments(tree):
            normalized_segment = _normalize_for_canary_matching(segment)
            if not normalized_segment:
                continue
            for canary, normalized_canary in normalized_canaries.items():
                if normalized_canary and normalized_canary in normalized_segment:
                    violations.append(
                        f"{relative}:{line} contains scaffold template canary "
                        f"'{canary}' outside scaffold template assets; "
                        f"{_SCAFFOLD_TEMPLATE_LOCALITY_REMEDIATION}"
                    )

    return violations


def _scaffold_template_locality_violations(project_root: Path) -> list[str]:
    violations = _scaffold_template_integrity_violations(project_root)
    violations.extend(_scaffold_template_source_locality_violations(project_root))
    return sorted(violations)


def main() -> int:
    violations = _scaffold_template_locality_violations(Path("."))
    status = "pass" if not violations else "fail"
    summary = (
        "Scaffold template locality constraints satisfied."
        if status == "pass"
        else f"Detected {len(violations)} scaffold template locality violation(s)."
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
