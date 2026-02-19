from __future__ import annotations

import ast
from pathlib import Path


def _collect_production_python_modules(repo_root: Path) -> list[Path]:
    src_root = repo_root / "src" / "engineeringagent"
    return sorted(
        path
        for path in src_root.rglob("*.py")
        if "tests" not in path.parts and not path.name.startswith("test_")
    )


def _find_legacy_import_violations(
    file_paths: list[Path], *, repo_root: Path
) -> list[str]:
    violations: list[str] = []
    legacy_modules = {
        "engineeringagent.progress_paths",
        "engineeringagent.progress_logging",
    }
    legacy_package_members = {"progress_paths", "progress_logging"}

    for path in file_paths:
        source = path.read_text(encoding="utf-8")
        rel_path = path.relative_to(repo_root).as_posix()
        module = ast.parse(source, filename=rel_path)

        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in legacy_modules:
                        violations.append(
                            f"{rel_path}:{node.lineno}: imports removed module {alias.name!r}"
                        )
            if isinstance(node, ast.ImportFrom):
                if node.module in legacy_modules:
                    violations.append(
                        f"{rel_path}:{node.lineno}: imports from removed module {node.module!r}"
                    )
                if node.module == "engineeringagent":
                    for alias in node.names:
                        if alias.name in legacy_package_members:
                            violations.append(
                                f"{rel_path}:{node.lineno}: imports removed member engineeringagent.{alias.name}"
                            )

    return violations


def test_legacy_progress_shim_modules_are_deleted(repo_root: Path) -> None:
    shim_paths = [
        repo_root / "src" / "engineeringagent" / "progress_paths.py",
        repo_root / "src" / "engineeringagent" / "progress_logging.py",
    ]

    existing = [path.as_posix() for path in shim_paths if path.exists()]
    assert not existing, (
        "Legacy progress shim modules should be deleted:\n" + "\n".join(existing)
    )


def test_production_modules_do_not_import_legacy_progress_shims(
    repo_root: Path,
) -> None:
    targets = _collect_production_python_modules(repo_root)

    violations = _find_legacy_import_violations(targets, repo_root=repo_root)

    assert not violations, "Legacy progress helper imports remain:\n" + "\n".join(
        violations
    )


def test_progress_package_reexports_common_helpers() -> None:
    from engineeringagent.progress import (
        append_jsonl_record,
        append_text_block,
        progress_dir,
        reviewers_state_path,
        runs_jsonl_path,
    )

    assert callable(append_jsonl_record)
    assert callable(append_text_block)
    assert callable(progress_dir)
    assert callable(reviewers_state_path)
    assert callable(runs_jsonl_path)
