from __future__ import annotations

from pathlib import Path

from tests.loop.feature_iteration_support import (
    base_feature,
    invoke_cli,
    make_project_root,
    progress_root,
)


def test_cli_run_dry_run_path_first(tmp_path: Path) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())

    result = invoke_cli(
        [
            "--project-root",
            str(project_root),
            "run",
            str(feature_path),
            "--dry-run",
        ]
    )

    assert result.exit_code == 0
    assert "result=dry_run" in result.stdout
    assert not (progress_root(project_root) / "runs" / "runs.jsonl").exists()


def test_cli_run_all_dry_run(tmp_path: Path) -> None:
    project_root, _ = make_project_root(tmp_path, feature_data=base_feature())

    result = invoke_cli(
        [
            "--project-root",
            str(project_root),
            "run",
            "--all",
            "--dry-run",
        ]
    )

    assert result.exit_code == 0
    assert "result=dry_run" in result.stdout


def test_cli_run_rejects_combined_all_and_paths(tmp_path: Path) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())

    result = invoke_cli(
        [
            "--project-root",
            str(project_root),
            "run",
            "--all",
            str(feature_path),
            "--dry-run",
        ]
    )

    assert result.exit_code == 1
    assert "cannot be used with --all" in result.stdout


def test_cli_run_requires_paths_or_all(tmp_path: Path) -> None:
    project_root, _ = make_project_root(tmp_path, feature_data=base_feature())

    result = invoke_cli(
        [
            "--project-root",
            str(project_root),
            "run",
            "--dry-run",
        ]
    )

    assert result.exit_code == 1
    assert "provide one or more feature paths, or use --all" in result.stdout
