"""Run YAML-configured import-boundary fitness rules."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from harness.fitness.ast_utils import (
    ImportStatement,
    build_module_context,
    collect_imports,
    matches_prefix,
)


@dataclass(frozen=True)
class RuleSpec:
    """One import-boundary rule loaded from YAML."""

    name: str
    description: str | None
    targets: tuple[str, ...]
    mode: str
    allowed_local_prefixes: tuple[str, ...]
    denied_local_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class Violation:
    """A rule violation found in one file."""

    file_path: Path
    line: int
    module: str
    rule_name: str
    rule_description: str | None
    allowed_local_prefixes: tuple[str, ...]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional CLI arguments.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the import-rules YAML config.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run configured architectural import-boundary checks.

    Args:
        argv: Optional CLI arguments.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    repo_root = Path.cwd()

    try:
        rules = load_rules(repo_root / args.config)
        violations = find_violations(repo_root=repo_root, rules=rules)
    except Exception as error:
        print(f"Architectural fitness check failed: {error}", file=sys.stderr)
        return 1

    if violations:
        print(format_violations(violations), file=sys.stderr)
        return 1

    return 0


def load_rules(config_path: Path) -> list[RuleSpec]:
    """Load and validate rule definitions from YAML.

    Args:
        config_path: Path to the YAML config file.

    Returns:
        Parsed rule specs.

    Raises:
        ValueError: If the config is invalid.
    """
    try:
        with config_path.open() as handle:
            data = yaml.safe_load(handle)
    except FileNotFoundError as error:
        raise ValueError(f"Config file not found: {config_path}") from error
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML in {config_path}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {config_path}")

    raw_rules = data.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError(f"Expected a non-empty 'rules' list in {config_path}")

    repo_root = config_path.resolve().parents[2]
    return _resolve_rule_specs(
        repo_root=repo_root,
        rules=[_build_rule_spec(rule) for rule in raw_rules],
    )


def find_violations(repo_root: Path, rules: list[RuleSpec]) -> list[Violation]:
    """Evaluate all configured rules against the repository tree."""
    violations: list[Violation] = []
    for file_path, rule in iter_selected_rules(
        repo_root=repo_root, rules=rules
    ).items():
        violations.extend(
            check_file(file_path=file_path, repo_root=repo_root, rule=rule)
        )
    return violations


def iter_selected_rules(repo_root: Path, rules: list[RuleSpec]) -> dict[Path, RuleSpec]:
    """Return the most-specific rule selected for each configured file."""
    candidate_rules: dict[Path, list[RuleSpec]] = {}
    for rule in rules:
        for file_path in _iter_target_files(repo_root=repo_root, rule=rule):
            candidate_rules.setdefault(file_path, []).append(rule)

    selected_rules: dict[Path, RuleSpec] = {}
    for file_path, matching_rules in candidate_rules.items():
        selected_rules[file_path] = _select_rule_for_file(
            file_path=file_path,
            repo_root=repo_root,
            matching_rules=matching_rules,
        )

    return dict(sorted(selected_rules.items()))


def check_file(file_path: Path, repo_root: Path, rule: RuleSpec) -> list[Violation]:
    """Return all rule violations found in a single file."""
    context = build_module_context(file_path=file_path, repo_root=repo_root)
    imports = collect_imports(file_path.read_text(), context)

    return [
        Violation(
            file_path=file_path,
            line=import_statement.line,
            module=import_statement.module,
            rule_name=rule.name,
            rule_description=rule.description,
            allowed_local_prefixes=rule.allowed_local_prefixes,
        )
        for import_statement in imports
        if is_violation(import_statement=import_statement, rule=rule)
    ]


def is_violation(import_statement: ImportStatement, rule: RuleSpec) -> bool:
    """Return whether one import breaks a rule."""
    if import_statement.category != "local":
        return False

    module_name = import_statement.module
    is_allowed = any(
        matches_prefix(module_name, prefix) for prefix in rule.allowed_local_prefixes
    )
    is_denied = any(
        matches_prefix(module_name, prefix) for prefix in rule.denied_local_prefixes
    )
    if rule.mode == "allow_only":
        return not is_allowed
    if rule.mode == "deny_only":
        return is_denied
    if rule.mode == "deny_except":
        return is_denied and not is_allowed
    raise ValueError(f"Unsupported rule mode: {rule.mode}")


def format_violations(violations: list[Violation]) -> str:
    """Render terminal-friendly violation output."""
    lines = ["Architectural fitness check failed.", ""]
    for violation in violations:
        relative_path = violation.file_path.relative_to(Path.cwd())
        lines.append(f"{relative_path}:{violation.line} imports {violation.module}")
        lines.append(f"  rule: {violation.rule_name}")
        if violation.rule_description:
            lines.append(f"  reason: {violation.rule_description}")
        lines.append(
            "  allowed local prefixes: " + ", ".join(violation.allowed_local_prefixes)
        )
        lines.append("")

    return "\n".join(lines).rstrip()


def _build_rule_spec(raw_rule: Any) -> RuleSpec:
    if not isinstance(raw_rule, dict):
        raise ValueError("Each rule must be a mapping")

    name = raw_rule.get("name")
    description = raw_rule.get("description")
    targets = raw_rule.get("targets")
    mode = raw_rule.get("mode")
    allow = raw_rule.get("allow")
    deny = raw_rule.get("deny")

    if not isinstance(name, str) or not name:
        raise ValueError("Each rule must include a non-empty 'name'")
    if description is not None and (
        not isinstance(description, str) or not description.strip()
    ):
        raise ValueError(
            f"Rule '{name}' must use a non-empty string when 'description' is set"
        )
    if not isinstance(targets, list) or not targets:
        raise ValueError(f"Rule '{name}' must include a non-empty 'targets' list")
    if not all(isinstance(target, str) for target in targets):
        raise ValueError(f"Rule '{name}' targets must be dotted selector strings")
    for target in targets:
        _validate_target(name=name, target=target)
    if mode not in {"allow_only", "deny_only", "deny_except"}:
        raise ValueError(f"Rule '{name}' has invalid mode '{mode}'")

    if mode == "allow_only":
        if deny is not None:
            raise ValueError(f"Rule '{name}' mode 'allow_only' does not accept 'deny'")
        allowed_local_prefixes = _as_string_tuple(
            allow,
            context=f"rule '{name}' allow",
            required=True,
        )
        denied_local_prefixes = ()
    elif mode == "deny_only":
        if allow is not None:
            raise ValueError(f"Rule '{name}' mode 'deny_only' does not accept 'allow'")
        allowed_local_prefixes = ()
        denied_local_prefixes = _as_string_tuple(
            deny,
            context=f"rule '{name}' deny",
            required=True,
        )
    else:
        allowed_local_prefixes = _as_string_tuple(
            allow,
            context=f"rule '{name}' allow",
            required=False,
        )
        denied_local_prefixes = _as_string_tuple(
            deny,
            context=f"rule '{name}' deny",
            required=True,
        )

    return RuleSpec(
        name=name,
        description=description,
        targets=tuple(targets),
        mode=mode,
        allowed_local_prefixes=allowed_local_prefixes,
        denied_local_prefixes=denied_local_prefixes,
    )


def _as_string_tuple(
    value: Any,
    *,
    context: str,
    required: bool,
) -> tuple[str, ...]:
    if value is None:
        if required:
            raise ValueError(f"Expected {context} to be a non-empty list of strings")
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Expected {context} to be a list of strings")
    if required and not value:
        raise ValueError(f"Expected {context} to be a non-empty list of strings")
    return tuple(value)


def _resolve_rule_specs(repo_root: Path, rules: list[RuleSpec]) -> list[RuleSpec]:
    for rule in rules:
        _iter_target_files(repo_root=repo_root, rule=rule)
    return rules


def _iter_target_files(repo_root: Path, rule: RuleSpec) -> tuple[Path, ...]:
    matched_files: set[Path] = set()
    for target in rule.targets:
        matched_files.update(_resolve_target(repo_root=repo_root, target=target))
    return tuple(sorted(matched_files))


def _resolve_target(repo_root: Path, target: str) -> tuple[Path, ...]:
    module_path = repo_root / "src" / Path(*target.split("."))
    package_init = module_path / "__init__.py"
    module_file = module_path.with_suffix(".py")

    if module_file.is_file():
        return (module_file.resolve(),)
    if module_path.is_dir():
        package_files = tuple(
            sorted(path.resolve() for path in module_path.rglob("*.py"))
        )
        if not package_files:
            raise ValueError(
                f"Target '{target}' does not contain any Python source files"
            )
        return package_files
    if package_init.is_file():
        return (package_init.resolve(),)
    raise ValueError(
        f"Target '{target}' does not resolve to a source module or package under src/"
    )


def _select_rule_for_file(
    file_path: Path,
    repo_root: Path,
    matching_rules: list[RuleSpec],
) -> RuleSpec:
    ranked_rules = sorted(
        matching_rules,
        key=lambda rule: _rule_specificity_for_file(
            file_path=file_path,
            repo_root=repo_root,
            rule=rule,
        ),
        reverse=True,
    )
    winner = ranked_rules[0]
    if len(ranked_rules) == 1:
        return winner

    winning_score = _rule_specificity_for_file(
        file_path=file_path,
        repo_root=repo_root,
        rule=winner,
    )
    same_score_rules = [
        rule
        for rule in ranked_rules[1:]
        if _rule_specificity_for_file(
            file_path=file_path,
            repo_root=repo_root,
            rule=rule,
        )
        == winning_score
    ]
    if same_score_rules:
        conflicting_names = ", ".join(
            sorted(rule.name for rule in [winner, *same_score_rules])
        )
        raise ValueError(
            f"File '{file_path}' matches multiple rules with the same specificity: "
            f"{conflicting_names}"
        )
    return winner


def _rule_specificity_for_file(
    file_path: Path,
    repo_root: Path,
    rule: RuleSpec,
) -> tuple[int, int]:
    module_context = build_module_context(file_path=file_path, repo_root=repo_root)
    matching_targets = [
        target
        for target in rule.targets
        if matches_prefix(module_context.module_name, target)
    ]
    if not matching_targets:
        raise ValueError(f"Rule '{rule.name}' does not apply to '{file_path}'")
    most_specific_target = max(
        matching_targets,
        key=lambda target: (len(target.split(".")), len(target)),
    )
    return (len(most_specific_target.split(".")), len(most_specific_target))


_DOTTED_SELECTOR_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$"
)


def _validate_target(*, name: str, target: str) -> None:
    if not _DOTTED_SELECTOR_PATTERN.fullmatch(target):
        raise ValueError(
            f"Rule '{name}' target '{target}' must be a dotted module selector"
        )


if __name__ == "__main__":
    raise SystemExit(main())
