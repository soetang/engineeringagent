"""Run YAML-configured import-boundary fitness rules."""

from __future__ import annotations

import argparse
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
    paths: tuple[str, ...]
    allowed_local_prefixes: tuple[str, ...]
    allowed_relative_import_roots: tuple[str, ...]
    denied_local_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class Violation:
    """A rule violation found in one file."""

    file_path: Path
    line: int
    module: str
    rule_name: str
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

    return [_build_rule_spec(rule) for rule in raw_rules]


def find_violations(repo_root: Path, rules: list[RuleSpec]) -> list[Violation]:
    """Evaluate all configured rules against the repository tree."""
    violations: list[Violation] = []
    for rule in rules:
        for file_path in iter_rule_files(repo_root=repo_root, rule=rule):
            violations.extend(
                check_file(file_path=file_path, repo_root=repo_root, rule=rule)
            )
    return violations


def iter_rule_files(repo_root: Path, rule: RuleSpec) -> list[Path]:
    """Return the sorted Python files matched by a rule."""
    matched_files: set[Path] = set()
    for pattern in rule.paths:
        matched_files.update(
            path.resolve() for path in repo_root.glob(pattern) if path.is_file()
        )
    return sorted(matched_files)


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
    ) or (
        import_statement.relative_root is not None
        and import_statement.relative_root in rule.allowed_relative_import_roots
    )

    is_denied = any(
        matches_prefix(module_name, prefix) for prefix in rule.denied_local_prefixes
    )
    return is_denied and not is_allowed


def format_violations(violations: list[Violation]) -> str:
    """Render terminal-friendly violation output."""
    lines = ["Architectural fitness check failed.", ""]
    for violation in violations:
        relative_path = violation.file_path.relative_to(Path.cwd())
        lines.append(f"{relative_path}:{violation.line} imports {violation.module}")
        lines.append(f"  rule: {violation.rule_name}")
        lines.append(
            "  allowed local prefixes: " + ", ".join(violation.allowed_local_prefixes)
        )
        lines.append("")

    return "\n".join(lines).rstrip()


def _build_rule_spec(raw_rule: Any) -> RuleSpec:
    if not isinstance(raw_rule, dict):
        raise ValueError("Each rule must be a mapping")

    name = raw_rule.get("name")
    paths = raw_rule.get("paths")
    allow = raw_rule.get("allow", {})
    deny = raw_rule.get("deny", {})

    if not isinstance(name, str) or not name:
        raise ValueError("Each rule must include a non-empty 'name'")
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise ValueError(f"Rule '{name}' must include a 'paths' list of strings")
    if not isinstance(allow, dict) or not isinstance(deny, dict):
        raise ValueError(
            f"Rule '{name}' must use mapping values for 'allow' and 'deny'"
        )

    return RuleSpec(
        name=name,
        paths=tuple(paths),
        allowed_local_prefixes=_as_string_tuple(
            allow.get("local_prefixes", []),
            context=f"rule '{name}' allow.local_prefixes",
        ),
        allowed_relative_import_roots=_as_string_tuple(
            allow.get("relative_import_roots", []),
            context=f"rule '{name}' allow.relative_import_roots",
        ),
        denied_local_prefixes=_as_string_tuple(
            deny.get("local_prefixes", []),
            context=f"rule '{name}' deny.local_prefixes",
        ),
    )


def _as_string_tuple(value: Any, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Expected {context} to be a list of strings")
    return tuple(value)


if __name__ == "__main__":
    raise SystemExit(main())
