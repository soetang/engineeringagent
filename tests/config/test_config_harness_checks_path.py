from __future__ import annotations

from pathlib import Path

from engineeringagent.config import (
    DEFAULT_PROGRESS_ROOT,
    DEFAULT_HARNESS_CHECKS_PATH,
    repo_relative_label,
    resolve_progress_root,
    resolve_harness_checks_config_path,
)


def test_resolve_harness_checks_path_defaults_when_not_configured(
    tmp_path: Path,
) -> None:
    assert resolve_harness_checks_config_path(tmp_path) == (
        tmp_path / DEFAULT_HARNESS_CHECKS_PATH
    )


def test_resolve_harness_checks_path_uses_pyproject_tool_engineeringagent(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.engineeringagent.harness.checks]\npath = \"repo/checks/custom.yaml\"\n",
        encoding="utf-8",
    )

    assert resolve_harness_checks_config_path(tmp_path) == (
        tmp_path / "repo/checks/custom.yaml"
    )


def test_resolve_progress_root_defaults_when_not_configured(tmp_path: Path) -> None:
    assert resolve_progress_root(tmp_path) == (tmp_path / DEFAULT_PROGRESS_ROOT)


def test_resolve_progress_root_prefers_engineeringagent_toml_over_pyproject(
    tmp_path: Path,
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        '[paths]\nprogress_root = ".engineeringagent/from-engineeringagent"\n',
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent.paths]\nprogress_root = ".engineeringagent/from-pyproject"\n',
        encoding="utf-8",
    )

    assert resolve_progress_root(tmp_path) == (
        tmp_path / ".engineeringagent/from-engineeringagent"
    )


def test_resolve_progress_root_uses_pyproject_tool_engineeringagent(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent.paths]\nprogress_root = "state/progress"\n',
        encoding="utf-8",
    )

    assert resolve_progress_root(tmp_path) == (tmp_path / "state/progress")


def test_repo_relative_label_prefers_project_relative_path(tmp_path: Path) -> None:
    checks_path = tmp_path / "harness" / "checks.yaml"
    assert repo_relative_label(tmp_path, checks_path) == "harness/checks.yaml"


def test_repo_relative_label_falls_back_to_full_path_for_external_target(
    tmp_path: Path,
) -> None:
    external_path = Path("/tmp/external-checks.yaml")
    assert repo_relative_label(tmp_path, external_path) == str(external_path)
