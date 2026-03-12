from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.config import (
    DEFAULT_HARNESS_ROOT,
    DEFAULT_PROGRESS_ROOT,
    DEFAULT_HARNESS_CHECKS_PATH,
    repo_relative_label,
    resolve_harness_root,
    resolve_progress_root,
    resolve_specifications_root,
    resolve_harness_checks_config_path,
)


def test_resolve_harness_checks_path_defaults_when_not_configured(
    tmp_path: Path,
) -> None:
    """Checks config resolution defaults to the canonical harness path."""

    assert resolve_harness_checks_config_path(tmp_path) == (
        tmp_path / DEFAULT_HARNESS_CHECKS_PATH
    )


def test_resolve_harness_checks_path_uses_pyproject_tool_engineeringagent(
    tmp_path: Path,
) -> None:
    """Checks config resolution reads pyproject fallback when repo config is absent."""

    (tmp_path / "pyproject.toml").write_text(
        "[tool.engineeringagent.harness.checks]\npath = \"repo/checks/custom.yaml\"\n",
        encoding="utf-8",
    )

    assert resolve_harness_checks_config_path(tmp_path) == (
        tmp_path / "repo/checks/custom.yaml"
    )


def test_resolve_progress_root_defaults_when_not_configured(tmp_path: Path) -> None:
    """Progress root resolution defaults to the canonical progress directory."""

    assert resolve_progress_root(tmp_path) == (tmp_path / DEFAULT_PROGRESS_ROOT)


def test_resolve_progress_root_prefers_engineeringagent_toml_over_pyproject(
    tmp_path: Path,
) -> None:
    """Progress root resolution prefers engineeringagent.toml over pyproject."""

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
    """Progress root resolution reads pyproject fallback when repo config is absent."""

    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent.paths]\nprogress_root = "state/progress"\n',
        encoding="utf-8",
    )

    assert resolve_progress_root(tmp_path) == (tmp_path / "state/progress")


def test_resolve_harness_root_defaults_when_not_configured(tmp_path: Path) -> None:
    """Harness root resolution defaults to the canonical harness directory."""

    assert resolve_harness_root(tmp_path) == (tmp_path / DEFAULT_HARNESS_ROOT)


def test_resolve_harness_root_prefers_engineeringagent_toml_over_pyproject(
    tmp_path: Path,
) -> None:
    """Harness root resolution prefers engineeringagent.toml over pyproject."""

    (tmp_path / "engineeringagent.toml").write_text(
        '[paths]\nharness_root = "repo-harness"\n',
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent.paths]\nharness_root = "pyproject-harness"\n',
        encoding="utf-8",
    )

    assert resolve_harness_root(tmp_path) == (tmp_path / "repo-harness")


def test_resolve_harness_root_uses_pyproject_tool_engineeringagent(
    tmp_path: Path,
) -> None:
    """Harness root resolution reads pyproject fallback when repo config is absent."""

    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent.paths]\nharness_root = "custom/harness"\n',
        encoding="utf-8",
    )

    assert resolve_harness_root(tmp_path) == (tmp_path / "custom/harness")


def test_resolve_specifications_root_defaults_to_docs_specifications(
    tmp_path: Path,
) -> None:
    """Specifications root falls back to the canonical architecture location."""

    assert resolve_specifications_root(tmp_path) == (
        tmp_path / "docs" / "specifications"
    )


def test_resolve_specifications_root_prefers_engineeringagent_toml_over_pyproject(
    tmp_path: Path,
) -> None:
    """Specifications root prefers engineeringagent.toml over pyproject."""

    (tmp_path / "engineeringagent.toml").write_text(
        '[paths]\nspecifications_root = "docs/specifications"\n',
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent.paths]\nspecifications_root = "docs/from-pyproject"\n',
        encoding="utf-8",
    )

    assert resolve_specifications_root(tmp_path) == (
        tmp_path / "docs" / "specifications"
    )


def test_resolve_specifications_root_uses_pyproject_tool_engineeringagent(
    tmp_path: Path,
) -> None:
    """Specifications root reads pyproject fallback when repo config is absent."""

    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent.paths]\nspecifications_root = "docs/specifications"\n',
        encoding="utf-8",
    )

    assert resolve_specifications_root(tmp_path) == (
        tmp_path / "docs" / "specifications"
    )


def test_repo_relative_label_prefers_project_relative_path(tmp_path: Path) -> None:
    """Repository labels render project-relative paths when possible."""

    checks_path = tmp_path / "harness" / "checks.yaml"
    assert repo_relative_label(tmp_path, checks_path) == "harness/checks.yaml"


def test_repo_relative_label_falls_back_to_full_path_for_external_target(
    tmp_path: Path,
) -> None:
    """Repository labels fall back to absolute paths for external targets."""

    external_path = Path("/tmp/external-checks.yaml")
    assert repo_relative_label(tmp_path, external_path) == str(external_path)
