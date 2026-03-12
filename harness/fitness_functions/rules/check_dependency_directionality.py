from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.checks.fitness.local_support_loader import load_local_support_module


_SUPPORT_MODULE = load_local_support_module(
    "policy_rule_support",
    caller_file=Path(__file__),
)
load_yaml_policy = _SUPPORT_MODULE.load_yaml_policy
run_policy_rule = _SUPPORT_MODULE.run_policy_rule


RULE_ID = "architecture.dep-directionality"
_DEFAULT_POLICY = (
    Path(__file__).resolve().parent.parent
    / "policies"
    / "dependency_directionality.yaml"
)


def _load_policy(config_file: Path) -> dict[str, tuple[str, ...]]:
    payload = load_yaml_policy(config_file)
    rules = payload.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("policy field 'rules' must be a non-empty list")

    disallowed_imports: dict[str, tuple[str, ...]] = {}
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"policy rules[{index}] must be a mapping")

        sources = rule.get("sources")
        module = rule.get("module")
        blocked_dependencies = rule.get("blocked_dependencies")
        if sources is None:
            if not isinstance(module, str) or not module:
                raise ValueError(
                    f"policy rules[{index}] must define either non-empty "
                    "'sources' or 'module'"
                )
            source_modules = [module]
        else:
            if not isinstance(sources, list) or not sources:
                raise ValueError(
                    f"policy rules[{index}].sources must be a non-empty list"
                )
            if not all(isinstance(source, str) and source for source in sources):
                raise ValueError(
                    f"policy rules[{index}].sources must contain only non-empty strings"
                )
            source_modules = sources

        if not isinstance(blocked_dependencies, list) or not blocked_dependencies:
            raise ValueError(
                f"policy rules[{index}].blocked_dependencies must be a non-empty list"
            )
        if not all(
            isinstance(dependency, str) and dependency
            for dependency in blocked_dependencies
        ):
            raise ValueError(
                f"policy rules[{index}].blocked_dependencies must contain only "
                "non-empty strings"
            )
        for source_module in source_modules:
            if source_module in disallowed_imports:
                raise ValueError(f"duplicate policy module: {source_module}")
            disallowed_imports[source_module] = tuple(blocked_dependencies)

    return disallowed_imports


def _module_path(project_root: Path, module_name: str) -> Path:
    _, _, suffix = module_name.partition("engineeringagent.")
    module_root = project_root / "src" / "engineeringagent"
    relative_path = Path(*suffix.split(".")) if suffix else Path()
    package_path = module_root / relative_path / "__init__.py"
    if package_path.is_file():
        return package_path
    return module_root / relative_path.with_suffix(".py")


def _module_paths(project_root: Path, module_name: str) -> tuple[Path, ...]:
    module_path = _module_path(project_root, module_name)
    if module_path.name == "__init__.py":
        package_root = module_path.parent
        return tuple(
            sorted(
                path
                for path in package_root.rglob("*.py")
                if path.is_file() and "__pycache__" not in path.parts
            )
        )
    return (module_path,)


def _path_to_module_name(project_root: Path, path: Path) -> str:
    relative_path = path.relative_to(project_root / "src")
    parts = list(relative_path.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = Path(parts[-1]).stem
    return ".".join(parts)


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


def _collect_imports(path: Path, module_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import_from_base(module_name, node)
            if base is None:
                continue
            imports.add(base)
            for alias in node.names:
                imports.add(f"{base}.{alias.name}")
    return imports


def _directionality_violations(
    project_root: Path, *, config_file: Path
) -> list[str]:
    violations: list[str] = []
    for source_name, blocked_modules in sorted(_load_policy(config_file).items()):
        module_paths = _module_paths(project_root, source_name)
        if not module_paths or not module_paths[0].exists():
            violations.append(
                f"missing module for directionality check: {source_name}"
            )
            continue

        for module_path in module_paths:
            module_name = _path_to_module_name(project_root, module_path)
            for imported in sorted(_collect_imports(module_path, module_name)):
                for blocked in blocked_modules:
                    if imported == blocked or imported.startswith(f"{blocked}."):
                        violations.append(
                            f"{module_name} imports blocked dependency {imported}"
                        )
    return sorted(violations)


def main() -> int:
    """Run the dependency directionality fitness rule."""
    return run_policy_rule(
        rule_id=RULE_ID,
        default_policy=_DEFAULT_POLICY,
        pass_summary="Dependency directionality constraints satisfied.",
        fail_summary=lambda count: (
            f"Detected {count} dependency directionality violation(s)."
        ),
        error_summary_prefix="Dependency directionality scan failed",
        evaluate=lambda project_root, config_file: _directionality_violations(
            project_root,
            config_file=config_file,
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
