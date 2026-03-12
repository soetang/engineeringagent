from __future__ import annotations

import ast
from pathlib import Path

import yaml

from engineeringagent.checks import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.harness-src-import-allowlist"

_ALLOWED_ENGINEERINGAGENT_IMPORT_PREFIXES: tuple[str, ...] = (
    "engineeringagent.checks",
    "engineeringagent.domain.specification",
    "engineeringagent.adapters.config",
    "engineeringagent.adapters.quality.fitness",
)

_ALLOWED_ENGINEERINGAGENT_IMPORT_PREFIXES_WITH_DOT = tuple(
    f"{prefix}." for prefix in _ALLOWED_ENGINEERINGAGENT_IMPORT_PREFIXES
)

_ALLOWED_ENGINEERINGAGENT_IMPORT_PREFIXES_DISPLAY = ", ".join(
    _ALLOWED_ENGINEERINGAGENT_IMPORT_PREFIXES
)


def _resolve_import_from_base(module_name: str, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module

    module_parts = module_name.split(".")
    if node.level > len(module_parts):
        return None

    base_parts = module_parts[: -node.level]
    if node.module:
        base_parts.extend(node.module.split("."))
    if not base_parts:
        return None
    return ".".join(base_parts)


def _collect_engineeringagent_imports(path: Path, module_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "engineeringagent" or alias.name.startswith(
                    "engineeringagent."
                ):
                    imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import_from_base(module_name, node)
            if base is None:
                continue
            for alias in node.names:
                if alias.name == "*":
                    candidate = base
                else:
                    candidate = f"{base}.{alias.name}"

                if candidate == "engineeringagent" or candidate.startswith(
                    "engineeringagent."
                ):
                    imports.add(candidate)
    return imports


def _is_allowed_engineeringagent_import(module_name: str) -> bool:
    return (
        module_name in _ALLOWED_ENGINEERINGAGENT_IMPORT_PREFIXES
        or module_name.startswith(_ALLOWED_ENGINEERINGAGENT_IMPORT_PREFIXES_WITH_DOT)
    )


def _iter_harness_fitness_rule_scripts(project_root: Path) -> list[Path]:
    manifest_path = project_root / "harness" / "fitness_functions" / "rules.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    scripts: set[Path] = set()
    for rule in manifest.get("rules", []):
        if not isinstance(rule, dict):
            continue
        command = rule.get("command")
        if not isinstance(command, list):
            continue
        for token in command:
            if not isinstance(token, str):
                continue
            if not token.startswith("harness/fitness_functions/"):
                continue
            if not token.endswith(".py"):
                continue
            scripts.add(project_root / token)
            break

    return sorted(scripts, key=lambda path: path.relative_to(project_root).as_posix())


def _collect_violations(project_root: Path) -> list[str]:
    violations: set[str] = set()
    for path in _iter_harness_fitness_rule_scripts(project_root):
        relpath = path.relative_to(project_root).as_posix()
        module_name = f"harness.fitness_functions.{path.stem}"
        try:
            imports = sorted(_collect_engineeringagent_imports(path, module_name))
        except SyntaxError as exc:
            violations.add(f"{relpath}: failed to parse for import scan: {exc.msg}")
            continue

        for imported in imports:
            if _is_allowed_engineeringagent_import(imported):
                continue
            violations.add(
                f"{relpath}: imports disallowed module {imported} (allowed: {_ALLOWED_ENGINEERINGAGENT_IMPORT_PREFIXES_DISPLAY})"
            )

    return sorted(violations)


def main() -> int:
    """Run the harness-to-src import allowlist fitness rule."""
    violations = _collect_violations(Path("."))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Harness fitness functions only import from the approved engineeringagent surface."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} disallowed harness-to-src import(s)."
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
