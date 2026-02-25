from __future__ import annotations

# Tests load fitness scripts and call internal helpers.
# pylint: disable=protected-access

import importlib.util
from pathlib import Path

import pytest
from engineeringagent import checks


def _load_checker_module(repo_root: Path):
    checker_path = (
        repo_root / "harness" / "fitness-functions" / "check_checks_import_surface.py"
    )
    spec = importlib.util.spec_from_file_location(
        "engineeringagent_tests.checks_import_surface_checker",
        checker_path,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checker_flags_checks_submodule_imports_outside_checks_dir(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    checker = _load_checker_module(repo_root)

    src_root = tmp_path / "src" / "engineeringagent"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "app.py").write_text(
        "\n".join(
            [
                "from engineeringagent.checks.validate.runtime import run_validate",
                "\n",
                "def run() -> None:",
                "    _ = run_validate",
                "",
            ]
        ),
        encoding="utf-8",
    )

    violations = checker._collect_violations(tmp_path)
    assert (
        "src/engineeringagent/app.py:1 imports checks submodule engineeringagent.checks.validate.runtime"
        in violations
    )


def test_checker_allows_importing_allowed_top_level_names(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    checker = _load_checker_module(repo_root)

    src_root = tmp_path / "src" / "engineeringagent"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "ok.py").write_text(
        "\n".join(
            [
                "from engineeringagent.checks import run_checks",
                "\n",
                "def run() -> None:",
                "    _ = run_checks",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert not checker._collect_violations(tmp_path)


def test_checker_allows_importing_shared_loader_from_top_level_checks(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    checker = _load_checker_module(repo_root)

    src_root = tmp_path / "src" / "engineeringagent"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "ok_loader.py").write_text(
        "\n".join(
            [
                "from engineeringagent.checks import load_harness_checks_document",
                "\n",
                "def run() -> None:",
                "    _ = load_harness_checks_document",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert not checker._collect_violations(tmp_path)


def test_checker_allows_importing_checks_group_helpers_from_top_level_checks(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    checker = _load_checker_module(repo_root)

    src_root = tmp_path / "src" / "engineeringagent"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "ok_groups.py").write_text(
        "\n".join(
            [
                "from engineeringagent.checks import list_check_groups, normalize_check_groups",
                "\n",
                "def run() -> None:",
                "    _ = list_check_groups",
                "    _ = normalize_check_groups",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert not checker._collect_violations(tmp_path)


def test_checker_allowed_top_level_names_match_checks_exports(repo_root: Path) -> None:
    checker = _load_checker_module(repo_root)
    assert checker._ALLOWED_CHECKS_IMPORT_NAMES == set(checks.__all__)


def test_checker_flags_disallowed_top_level_imports_even_if_exported(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    checker = _load_checker_module(repo_root)

    src_root = tmp_path / "src" / "engineeringagent"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "bad.py").write_text(
        "\n".join(
            [
                "from engineeringagent.checks import CONTRACT_VERSION",
                "\n",
                "def run() -> None:",
                "    _ = CONTRACT_VERSION",
                "",
            ]
        ),
        encoding="utf-8",
    )

    violations = checker._collect_violations(tmp_path)
    assert (
        "src/engineeringagent/bad.py:1 imports disallowed name CONTRACT_VERSION from engineeringagent.checks"
        in violations
    )


@pytest.mark.parametrize(
    "legacy_name",
    [
        "load_reviewer_config",
        "parse_reviewer_decision",
        "plan_reviewers",
        "run_planned_command_checks",
        "run_planned_fitness_checks",
        "run_planned_reviewer_checks",
    ],
)
def test_checker_flags_removed_legacy_runtime_helper_imports(
    tmp_path: Path,
    repo_root: Path,
    legacy_name: str,
) -> None:
    checker = _load_checker_module(repo_root)

    src_root = tmp_path / "src" / "engineeringagent"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "bad_legacy.py").write_text(
        "\n".join(
            [
                f"from engineeringagent.checks import {legacy_name}",
                "\n",
                "def run() -> None:",
                f"    _ = {legacy_name}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    violations = checker._collect_violations(tmp_path)
    assert (
        f"src/engineeringagent/bad_legacy.py:1 imports disallowed name {legacy_name} from engineeringagent.checks"
        in violations
    )
