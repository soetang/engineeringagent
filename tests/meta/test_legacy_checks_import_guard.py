from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


def _iter_python_files(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*.py") if path.is_file()),
        key=lambda path: path.as_posix(),
    )


def test_production_code_does_not_import_legacy_checks_entrypoints() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    src_root = repo_root / "src" / "engineeringagent"

    forbidden_modules = (
        "engineeringagent.harness_checks_runtime",
        "engineeringagent.validator",
        "engineeringagent.reviewers",
        "engineeringagent.fitness",
        "engineeringagent.retry_feedback",
    )
    forbidden_leaf = {
        "harness_checks_runtime",
        "validator",
        "reviewers",
        "fitness",
        "retry_feedback",
    }
    excluded_files: set[Path] = set()
    excluded_packages = {"retry_feedback"}

    violations: list[str] = []

    for path in _iter_python_files(src_root):
        if path in excluded_files:
            continue

        rel_to_src = path.relative_to(src_root)
        if rel_to_src.parts and rel_to_src.parts[0] in excluded_packages:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    for forbidden in forbidden_modules:
                        if name == forbidden or name.startswith(f"{forbidden}."):
                            rel = path.relative_to(repo_root).as_posix()
                            violations.append(
                                f"{rel}:{node.lineno}: import {name} (forbidden)"
                            )
            elif isinstance(node, ast.ImportFrom):
                module = node.module
                level = int(getattr(node, "level", 0) or 0)
                lineno = int(getattr(node, "lineno", 0) or 0)

                def _record(reason: str) -> None:
                    rel = path.relative_to(repo_root).as_posix()
                    violations.append(f"{rel}:{lineno}: {reason} (forbidden)")

                if level == 0 and module is not None:
                    for forbidden in forbidden_modules:
                        if module == forbidden or module.startswith(f"{forbidden}."):
                            _record(f"from {module} import ...")
                    if module == "engineeringagent":
                        for alias in node.names:
                            if alias.name in forbidden_leaf:
                                _record(f"from engineeringagent import {alias.name}")

                if level == 1:
                    # Relative imports within the engineeringagent package.
                    if module in forbidden_leaf:
                        _record(f"from .{module} import ...")
                    if module is None:
                        for alias in node.names:
                            if alias.name in forbidden_leaf:
                                _record(f"from . import {alias.name}")

    assert not violations, "\n".join(
        [
            "production imports legacy checks entrypoints:",
            *violations,
            "remediation: migrate callers to engineeringagent.checks.run_checks(...) and checks/* runtimes",
        ]
    )


def test_legacy_fitness_package_is_removed() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    src_root = repo_root / "src" / "engineeringagent"

    assert not (src_root / "fitness").exists()
    assert importlib.util.find_spec("engineeringagent.fitness") is None


def test_legacy_retry_feedback_package_is_removed() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    src_root = repo_root / "src" / "engineeringagent"

    assert not (src_root / "retry_feedback").exists()
    assert importlib.util.find_spec("engineeringagent.retry_feedback") is None
