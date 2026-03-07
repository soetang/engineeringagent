from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

from engineeringagent.loop import _run_feature_iteration
from engineeringagent.prompts import build_implementation_prompt
from tests.loop.feature_iteration_support import (
    FEATURE_LOG_REF,
    base_feature,
    invoke_cli,
    make_project_root,
    progress_root,
    read_runs,
    run_python_script,
    with_opencode_implement_side_effect,
    write_add_done_subtask_script,
    write_set_done_and_duplicate_subtask_script,
    write_set_done_script,
    write_set_subtask_done_script,
)


def test_verification_is_not_run_without_done_transition(tmp_path: Path) -> None:
    verification_marker = "verification-ran.txt"
    verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{verification_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Run verification command",
            "status": "backlog",
            "context": "Verify selected subtask commands run under loop control.",
            "verification": [verification_command],
        }
    ]
    project_root, feature_path = make_project_root(tmp_path, feature_data=feature_data)

    outcome = _run_feature_iteration(
        project_root=project_root,
        feature_path=feature_path,
        run_all=False,
        attempt=1,
        feedback=None,
        verbose_output=False,
    )

    assert outcome.result == "passed"
    assert outcome.verification_status == "not_run"
    assert outcome.verification_failed_command is None
    assert not (project_root / verification_marker).exists()


def test_verification_failure_for_newly_done_subtask_marks_iteration_non_pass(
    tmp_path: Path,
) -> None:
    verification_command = (
        f'"{sys.executable}" -c "import sys; print(\'verification failure\'); '
        'sys.exit(1)"'
    )
    feature_data = base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Fail verification command",
            "status": "backlog",
            "context": "Ensure failed verification marks iteration as failed.",
            "verification": [verification_command],
        }
    ]
    project_root, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    script_path = write_set_subtask_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-subtask-done.py",
        "ST-001",
    )

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        outcome = _run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            attempt=1,
            feedback=None,
            verbose_output=False,
        )

    assert outcome.result == "failed"
    assert outcome.failed_gate is None
    assert outcome.next_action == "retry_same_feature"
    assert outcome.verification_status == f"failed:{verification_command}"
    assert outcome.verification_failed_command == verification_command

    runs = read_runs(project_root)
    assert runs[-1]["result"] == "failed"
    assert runs[-1]["verification_status"] == f"failed:{verification_command}"
    assert runs[-1]["verification_failed_command"] == verification_command


def test_verification_rejects_shell_chaining_without_partial_execution(
    tmp_path: Path,
) -> None:
    marker_path = tmp_path / "verification-shell-chaining-marker.txt"
    verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{marker_path.as_posix()}').write_text('ran', encoding='utf-8')\" "
        '&& echo "should-not-run"'
    )
    feature_data = base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Reject shell chaining in verification command",
            "status": "backlog",
            "context": "Ensure shell-only syntax fails before any command execution.",
            "verification": [verification_command],
        }
    ]
    project_root, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    script_path = write_set_subtask_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-subtask-done-shell-chain.py",
        "ST-001",
    )

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        outcome = _run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            attempt=1,
            feedback=None,
            verbose_output=False,
        )

    assert outcome.result == "failed"
    assert outcome.next_action == "retry_same_feature"
    assert outcome.verification_status == f"failed:{verification_command}"
    assert outcome.verification_failed_command == verification_command
    feature_log = progress_root(project_root) / "features" / "FEAT-900" / "run.txt"
    log_text = feature_log.read_text(encoding="utf-8")
    assert "[verification] returncode=2" in log_text
    assert "shell syntax is not supported" in log_text
    assert "Remediation: provide a plain argv-style command" in log_text
    assert not marker_path.exists()


def test_verification_selection_ignores_non_string_commands(tmp_path: Path) -> None:
    verification_marker = "verification-valid-ran.txt"
    valid_verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{verification_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Ignore non-string verification entries",
            "status": "backlog",
            "context": "Ensure done-transition verification ignores non-command values.",
            "verification": [123, valid_verification_command],
        }
    ]
    project_root, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    script_path = write_set_subtask_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-subtask-done-ignore-invalid.py",
        "ST-001",
    )

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        outcome = _run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            attempt=1,
            feedback=None,
            verbose_output=False,
        )

    assert outcome.result == "failed"
    assert outcome.failed_gate == "validate"
    assert outcome.verification_status == "passed"
    assert outcome.verification_failed_command is None
    assert (project_root / verification_marker).exists()


def test_verification_selection_ignores_blank_string_commands(
    tmp_path: Path,
) -> None:
    verification_marker = "verification-blank-filter-ran.txt"
    valid_verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{verification_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Ignore blank verification entries",
            "status": "backlog",
            "context": "Ensure done-transition verification ignores blank commands.",
            "verification": ["   ", valid_verification_command],
        }
    ]
    project_root, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    script_path = write_set_subtask_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-subtask-done-ignore-blank.py",
        "ST-001",
    )

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        outcome = _run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            attempt=1,
            feedback=None,
            verbose_output=False,
        )

    runs = read_runs(project_root)
    feature_log = project_root / str(runs[-1]["log_path"])
    log_text = feature_log.read_text(encoding="utf-8")

    assert outcome.result == "passed"
    assert outcome.verification_status == "passed"
    assert outcome.verification_failed_command is None
    assert (project_root / verification_marker).exists()
    assert "[verification] command=   " not in log_text
    assert f"[verification] command={valid_verification_command}" in log_text


def test_verification_selection_normalizes_command_whitespace(
    tmp_path: Path,
) -> None:
    verification_marker = "verification-whitespace-normalized-ran.txt"
    trimmed_verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{verification_marker}').write_text('ok', encoding='utf-8')\""
    )
    padded_verification_command = f"  {trimmed_verification_command}  "
    feature_data = base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Normalize command whitespace",
            "status": "backlog",
            "context": "Ensure done-transition verification trims command whitespace.",
            "verification": [padded_verification_command],
        }
    ]
    project_root, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    script_path = write_set_subtask_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-subtask-done-normalize-whitespace.py",
        "ST-001",
    )

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        outcome = _run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            attempt=1,
            feedback=None,
            verbose_output=False,
        )

    runs = read_runs(project_root)
    feature_log = project_root / str(runs[-1]["log_path"])
    log_text = feature_log.read_text(encoding="utf-8")

    assert outcome.result == "passed"
    assert outcome.verification_status == "passed"
    assert (project_root / verification_marker).exists()
    assert f"[verification] command={trimmed_verification_command}" in log_text
    assert f"[verification] command={padded_verification_command}" not in log_text


def test_verification_ignores_new_done_subtasks_without_pre_snapshot_status(
    tmp_path: Path,
) -> None:
    verification_marker = "verification-added-subtask-ran.txt"
    verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{verification_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Leave existing subtask untouched",
            "status": "backlog",
            "context": "Ensure only stable-id status transitions drive verification.",
            "verification": [verification_command],
        }
    ]
    project_root, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    script_path = write_add_done_subtask_script(
        tmp_path.parent / f"{tmp_path.name}-add-done-subtask.py",
        "ST-002",
        verification_command,
    )

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        outcome = _run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            attempt=1,
            feedback=None,
            verbose_output=False,
        )

    assert outcome.result == "passed"
    assert outcome.verification_status == "not_run"
    assert outcome.verification_failed_command is None
    assert not (project_root / verification_marker).exists()


def test_verification_selection_uses_first_post_entry_for_duplicate_subtask_ids(
    tmp_path: Path,
) -> None:
    primary_marker = "verification-primary-ran.txt"
    duplicate_marker = "verification-duplicate-ran.txt"
    primary_verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{primary_marker}').write_text('ok', encoding='utf-8')\""
    )
    duplicate_verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{duplicate_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Preserve one stable-id transition",
            "status": "backlog",
            "context": "Ensure duplicate post-implement IDs do not duplicate verification.",
            "verification": [primary_verification_command],
        }
    ]
    project_root, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    script_path = write_set_done_and_duplicate_subtask_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-and-duplicate-id.py",
        "ST-001",
        duplicate_verification_command,
    )

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        outcome = _run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            attempt=1,
            feedback=None,
            verbose_output=False,
        )

    assert outcome.result == "failed"
    assert outcome.failed_gate == "validate"
    assert outcome.verification_status == "passed"
    assert (project_root / primary_marker).exists()
    assert not (project_root / duplicate_marker).exists()


def test_verification_selection_uses_first_pre_status_for_duplicate_subtask_ids(
    tmp_path: Path,
) -> None:
    verification_marker = "verification-first-pre-status-ran.txt"
    verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{verification_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Primary pre-implement entry",
            "status": "backlog",
            "context": "Use first pre-implement status for done-transition diffing.",
            "verification": [verification_command],
        },
        {
            "id": "ST-001",
            "title": "Duplicate pre-implement entry",
            "status": "done",
            "context": "Duplicate id should not mask first-entry transition.",
            "verification": ["true"],
        },
    ]
    project_root, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    script_path = write_set_subtask_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-first-duplicate-id-done.py",
        "ST-001",
    )

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        outcome = _run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            attempt=1,
            feedback=None,
            verbose_output=False,
        )

    assert outcome.result == "failed"
    assert outcome.failed_gate == "validate"
    assert outcome.verification_status == "passed"
    assert (project_root / verification_marker).exists()


def test_verification_failure_restores_feature_archived_during_iteration(
    tmp_path: Path,
) -> None:
    verification_command = f'"{sys.executable}" -c "import sys; sys.exit(1)"'
    feature_data = base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Fail verification after archive move",
            "status": "backlog",
            "context": "Ensure verification failure restores active feature path.",
            "verification": [verification_command],
        }
    ]
    project_root, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    set_subtask_done_script = write_set_subtask_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-subtask-done-before-archive.py",
        "ST-001",
    )
    set_done_script = write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-before-verification.py"
    )

    def implement_effect() -> None:
        run_python_script(set_subtask_done_script, feature_path)
        run_python_script(set_done_script, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        outcome = _run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            attempt=1,
            feedback=None,
            verbose_output=False,
        )

    archived_path = project_root / "docs" / "spec" / "features_done" / feature_path.name

    assert outcome.result == "failed"
    assert outcome.failed_gate is None
    assert outcome.next_action == "retry_same_feature"
    assert outcome.verification_status == f"failed:{verification_command}"
    assert feature_path.exists()
    assert not archived_path.exists()


def test_ralph_prompt_includes_feature_file_path(tmp_path: Path) -> None:
    feature_data = base_feature()
    feature_data["context"] = "Loop iteration uses runtime phase orchestration."
    _, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    prompt = build_implementation_prompt(
        feature=feature,
        feature_path=feature_path,
        feedback=None,
    )

    expected_interpolated_values = (
        str(feature_path),
        ".engineeringagent/progress/features/FEAT-900/handoff.md",
        "feature FEAT-900 (Feature iteration smoke test)",
        f"Objective: {feature_data['objective']}",
        f"Context: {feature_data['context']}",
    )
    for value in expected_interpolated_values:
        assert value in prompt


def test_ralph_prompt_contract_uses_schema_only_validate_command(
    tmp_path: Path,
) -> None:
    _, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    prompt = build_implementation_prompt(
        feature=feature,
        feature_path=feature_path,
        feedback=None,
    )

    assert "uv run engineeringagent validate --schema-only" in prompt


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
