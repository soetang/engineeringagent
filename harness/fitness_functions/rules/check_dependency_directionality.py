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
_SOURCE_ROOT = Path("src") / "engineeringagent"
_LAYER_DIRECTORIES = {
    "adapters": Path("adapters"),
    "application": Path("application"),
    "bootstrap": Path("bootstrap"),
    "domain": Path("domain"),
    "ports": Path("ports"),
    "presentation": Path("presentation"),
    "presentation_cli": Path("presentation") / "cli",
}
_BLOCKED_MODULE_PREFIXES = {
    layer_id: f"engineeringagent.{layer_path.as_posix().replace('/', '.')}"
    for layer_id, layer_path in _LAYER_DIRECTORIES.items()
}


def _read_module_list(
    rule: dict[str, object],
    *,
    field_name: str,
    alias_field_name: str,
    item_label: str,
) -> list[str]:
    layer_values = rule.get(alias_field_name)
    if layer_values is not None:
        if not isinstance(layer_values, list) or not layer_values:
            raise ValueError(
                f"policy {alias_field_name} must be a non-empty list of layer ids"
            )
        expanded_values: list[str] = []
        for layer_id in layer_values:
            if not isinstance(layer_id, str) or not layer_id:
                raise ValueError(
                    f"policy {alias_field_name} must contain only non-empty strings"
                )
            if layer_id not in _LAYER_DIRECTORIES:
                known_layers = ", ".join(sorted(_LAYER_DIRECTORIES))
                raise ValueError(
                    f"unknown {item_label} layer id '{layer_id}'; expected one of: "
                    f"{known_layers}"
                )
            expanded_values.append(layer_id)
        return expanded_values
    if rule.get(field_name) is not None:
        raise ValueError(
            "dependency directionality policy no longer accepts module-path "
            f"field '{field_name}'; use '{alias_field_name}' layer ids instead"
        )
    raise ValueError(f"policy rules must define '{alias_field_name}'")


def _load_policy(config_file: Path) -> dict[str, tuple[str, ...]]:
    payload = load_yaml_policy(config_file)
    rules = payload.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("policy field 'rules' must be a non-empty list")

    disallowed_imports: dict[str, tuple[str, ...]] = {}
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"policy rules[{index}] must be a mapping")

        if rule.get("module") is not None:
            raise ValueError(
                "dependency directionality policy no longer accepts module-path "
                "field 'module'; use 'source_layers' instead"
            )
        source_modules = _read_module_list(
            rule,
            field_name="sources",
            alias_field_name="source_layers",
            item_label="source",
        )

        blocked_dependencies = _read_module_list(
            rule,
            field_name="blocked_dependencies",
            alias_field_name="blocked_layers",
            item_label="blocked dependency",
        )
        for source_layer in source_modules:
            if source_layer in disallowed_imports:
                raise ValueError(f"duplicate policy layer: {source_layer}")
            disallowed_imports[source_layer] = tuple(blocked_dependencies)

    return disallowed_imports


def _iter_layer_module_paths(project_root: Path, layer_id: str) -> tuple[Path, ...]:
    layer_root = project_root / _SOURCE_ROOT / _LAYER_DIRECTORIES[layer_id]
    if not layer_root.exists():
        return ()
    if layer_root.is_file():
        return (layer_root,)
    return tuple(
        sorted(
            path
            for path in layer_root.rglob("*.py")
            if path.is_file() and "__pycache__" not in path.parts
        )
    )


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
    for source_layer, blocked_layers in sorted(_load_policy(config_file).items()):
        module_paths = _iter_layer_module_paths(project_root, source_layer)
        if not module_paths:
            violations.append(
                f"missing layer root for directionality check: {source_layer}"
            )
            continue

        for module_path in module_paths:
            module_name = _path_to_module_name(project_root, module_path)
            for imported in sorted(_collect_imports(module_path, module_name)):
                for blocked_layer in blocked_layers:
                    blocked_prefix = _BLOCKED_MODULE_PREFIXES[blocked_layer]
                    if imported == blocked_prefix or imported.startswith(
                        f"{blocked_prefix}."
                    ):
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
