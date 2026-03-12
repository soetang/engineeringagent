from __future__ import annotations

import ast
from pathlib import Path

import yaml

from engineeringagent.adapters.quality.fitness import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.harness-fitness-helper-surface"
_LEGACY_RESULT_ENVELOPE_IMPORTS = {
    "result_envelope",
    "result_envelope.emit_result_envelope",
}
_LEGACY_CHECKS_IMPORT_PREFIX = "engineeringagent.checks"
_REMEDIATION = (
    "harness fitness rules must use engineeringagent.adapters.quality.fitness."
    "emit_fitness_result and adapter-owned helpers instead of the legacy "
    "engineeringagent.checks facade or local result_envelope helpers"
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


def _iter_manifest_scripts(project_root: Path) -> list[Path]:
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
            if (
                isinstance(token, str)
                and token.startswith("harness/fitness_functions/")
                and token.endswith(".py")
            ):
                scripts.add(project_root / token)
                break

    return sorted(scripts, key=lambda path: path.relative_to(project_root).as_posix())


def _collect_violations(project_root: Path) -> list[str]:
    violations: list[str] = []
    legacy_helper_path = (
        project_root / "harness" / "fitness_functions" / "result_envelope.py"
    )
    if legacy_helper_path.exists():
        violations.append(
            "harness/fitness_functions/result_envelope.py: legacy local result envelope "
            f"helper must remain absent; {_REMEDIATION}"
        )

    for path in _iter_manifest_scripts(project_root):
        relpath = path.relative_to(project_root).as_posix()
        module_name = f"harness.fitness_functions.rules.{path.stem}"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relpath)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == _LEGACY_CHECKS_IMPORT_PREFIX or alias.name in (
                        "result_envelope",
                    ):
                        violations.append(
                            f"{relpath}:{node.lineno} imports legacy helper module "
                            f"{alias.name}; {_REMEDIATION}"
                        )
                continue

            if not isinstance(node, ast.ImportFrom):
                continue

            base = _resolve_import_from_base(module_name, node)
            if base is None:
                continue
            if base == _LEGACY_CHECKS_IMPORT_PREFIX:
                violations.append(
                    f"{relpath}:{node.lineno} imports from legacy helper module "
                    f"{base}; {_REMEDIATION}"
                )
                continue
            for alias in node.names:
                imported_name = base if alias.name == "*" else f"{base}.{alias.name}"
                if imported_name in _LEGACY_RESULT_ENVELOPE_IMPORTS:
                    violations.append(
                        f"{relpath}:{node.lineno} imports legacy helper module "
                        f"{imported_name}; {_REMEDIATION}"
                    )

    return sorted(set(violations))


def main() -> int:
    """Run the harness-fitness helper-surface fitness rule."""
    violations = _collect_violations(Path("."))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Harness fitness rules only use adapter-owned fitness helpers."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} legacy harness fitness helper import(s)."
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
