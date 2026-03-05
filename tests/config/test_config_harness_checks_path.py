from __future__ import annotations

from pathlib import Path

from engineeringagent.config import (
    DEFAULT_HARNESS_CHECKS_PATH,
    repo_relative_label,
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


def test_repo_relative_label_prefers_project_relative_path(tmp_path: Path) -> None:
    checks_path = tmp_path / "harness" / "checks.yaml"
    assert repo_relative_label(tmp_path, checks_path) == "harness/checks.yaml"


def test_repo_relative_label_falls_back_to_full_path_for_external_target(
    tmp_path: Path,
) -> None:
    external_path = Path("/tmp/external-checks.yaml")
    assert repo_relative_label(tmp_path, external_path) == str(external_path)
