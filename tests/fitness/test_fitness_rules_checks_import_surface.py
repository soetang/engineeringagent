from __future__ import annotations

import importlib.util
from pathlib import Path


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

    assert checker._collect_violations(tmp_path) == []
