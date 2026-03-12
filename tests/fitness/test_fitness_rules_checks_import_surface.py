from __future__ import annotations

# Tests load fitness scripts and call internal helpers.
# pylint: disable=protected-access

import importlib.util
from pathlib import Path

import pytest
from engineeringagent import checks


def _load_checker_module(repo_root: Path):
    checker_path = (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
        / "check_checks_import_surface.py"
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
    """Production code outside checks may not import checks submodules directly."""

    checker = _load_checker_module(repo_root)

    src_root = tmp_path / "src" / "engineeringagent"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "app.py").write_text(
        "\n".join(
            [
                "from engineeringagent.adapters.quality.command_checks import plan_command_checks",
                "\n",
                "def run() -> None:",
                "    _ = plan_command_checks",
                "",
            ]
        ),
        encoding="utf-8",
    )

    violations = checker._collect_violations(tmp_path)
    assert (
        "src/engineeringagent/app.py:1 imports disallowed adapter-quality module "
        "engineeringagent.adapters.quality.command_checks"
        in violations
    )


def test_checker_allows_importing_allowed_top_level_names(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Top-level checks exports remain the supported external import surface."""

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


def test_checker_flags_checks_facade_import_from_bootstrap_modules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Bootstrap modules must use concrete quality/runtime seams, not the facade."""

    checker = _load_checker_module(repo_root)

    src_root = tmp_path / "src" / "engineeringagent"
    (src_root / "bootstrap").mkdir(parents=True)
    (src_root / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "bootstrap" / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "bootstrap" / "app_factory.py").write_text(
        "\n".join(
            [
                "from engineeringagent.checks import collect_changed_paths",
                "",
                "COLLECT = collect_changed_paths",
                "",
            ]
        ),
        encoding="utf-8",
    )

    violations = checker._collect_violations(tmp_path)
    assert (
        "src/engineeringagent/bootstrap/app_factory.py:1 imports engineeringagent.checks facade "
        "from an internal runtime/bootstrap module"
        in violations
    )


def test_checker_flags_checks_facade_import_from_adapter_modules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Adapter modules must use concrete quality/runtime seams, not the facade."""

    checker = _load_checker_module(repo_root)

    src_root = tmp_path / "src" / "engineeringagent"
    (src_root / "adapters" / "runtime").mkdir(parents=True)
    (src_root / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "adapters" / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "adapters" / "runtime" / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )
    (src_root / "adapters" / "runtime" / "phase.py").write_text(
        "\n".join(
            [
                "from engineeringagent.checks import run_checks",
                "",
                "RUN = run_checks",
                "",
            ]
        ),
        encoding="utf-8",
    )

    violations = checker._collect_violations(tmp_path)
    assert (
        "src/engineeringagent/adapters/runtime/phase.py:1 imports engineeringagent.checks facade "
        "from an internal runtime/bootstrap module"
        in violations
    )


def test_checker_ignores_adapter_quality_runtime_when_it_composes_checks_internals(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Checks-internal adapter composition remains allowed within adapter quality code."""

    checker = _load_checker_module(repo_root)

    src_root = tmp_path / "src" / "engineeringagent" / "adapters" / "quality"
    src_root.mkdir(parents=True)
    (tmp_path / "src" / "engineeringagent" / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )
    (tmp_path / "src" / "engineeringagent" / "adapters" / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )
    (src_root / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "runtime.py").write_text(
        "\n".join(
            [
                "from engineeringagent.adapters.quality.config_selection import load_selected_harness_checks_document",
                "from engineeringagent.adapters.quality.check_strategies import CommandCheckStrategy",
                "",
                "__all__ = ['load_selected_harness_checks_document', 'CommandCheckStrategy']",
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
    """The top-level checks loader stays available to non-checks callers."""

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


def test_checker_allows_importing_top_level_validation_entrypoint(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Non-checks callers may import the top-level validation facade."""

    checker = _load_checker_module(repo_root)

    src_root = tmp_path / "src" / "engineeringagent"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "ok_validate.py").write_text(
        "\n".join(
            [
                "from engineeringagent.checks import validate_repository",
                "\n",
                "def run() -> None:",
                "    _ = validate_repository",
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
    """Group helper imports are allowed only through the top-level checks facade."""

    checker = _load_checker_module(repo_root)

    src_root = tmp_path / "src" / "engineeringagent"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "ok_groups.py").write_text(
        "\n".join(
            [
                "from engineeringagent.checks import list_check_groups, normalize_groups",
                "\n",
                "def run() -> None:",
                "    _ = list_check_groups",
                "    _ = normalize_groups",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert not checker._collect_violations(tmp_path)


def test_checker_allowed_top_level_names_match_checks_exports(repo_root: Path) -> None:
    """The fitness rule and the exported checks facade must stay aligned."""

    checker = _load_checker_module(repo_root)
    assert checker._ALLOWED_CHECKS_IMPORT_NAMES == set(checks.__all__)


def test_checker_flags_disallowed_top_level_imports_even_if_exported(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Legacy top-level names remain forbidden even if they were once exported."""

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
    """Removed legacy checks helpers must stay blocked by the import-surface rule."""

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


def test_cli_production_module_uses_checks_top_level_surface_only(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """CLI production code may only depend on the top-level checks facade."""

    checker = _load_checker_module(repo_root)

    src_root = tmp_path / "src" / "engineeringagent" / "cli"
    src_root.mkdir(parents=True)
    (tmp_path / "src" / "engineeringagent" / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )
    (src_root / "__init__.py").write_text(
        "\n".join(
            [
                "from engineeringagent.checks import HarnessCheckPhase, run_checks",
                "",
                "__all__ = ['HarnessCheckPhase', 'run_checks']",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (src_root / "checks.py").write_text(
        "\n".join(
            [
                "from engineeringagent.checks import HarnessCheckPhase",
                "",
                "PHASE = HarnessCheckPhase.ITERATION_END",
                "",
            ]
        ),
        encoding="utf-8",
    )

    violations = checker._collect_violations(tmp_path)
    cli_violations = [
        line for line in violations if line.startswith("src/engineeringagent/cli/")
    ]

    assert cli_violations == []


def test_checker_still_flags_non_specs_checks_strategy_imports(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Checks strategy modules remain internal outside approved specs tooling."""

    checker = _load_checker_module(repo_root)

    src_root = tmp_path / "src" / "engineeringagent"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "bad.py").write_text(
        "\n".join(
            [
                "from engineeringagent.checks.strategy_contracts import CheckDecision",
                "",
                "VALUE = CheckDecision",
                "",
            ]
        ),
        encoding="utf-8",
    )

    violations = checker._collect_violations(tmp_path)
    assert (
        "src/engineeringagent/bad.py:1 imports checks submodule engineeringagent.checks.strategy_contracts"
        in violations
    )
