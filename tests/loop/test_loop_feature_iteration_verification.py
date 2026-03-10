from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

from engineeringagent.loop import _run_feature_iteration
from engineeringagent.loop_runtime.feature_state import refresh_feature_after_implement
from engineeringagent.loop_runtime.progress_units import (
    current_progress_unit,
    done_transition_verification_commands,
    progress_status_snapshot,
)
from tests.loop.feature_iteration_support import (
    FEATURE_LOG_REF,
    base_feature,
    init_git_repo,
    invoke_cli,
    make_bundled_project_root,
    make_project_root,
    progress_root,
    read_runs,
    run_python_script,
    with_opencode_implement_side_effect,
    write_add_done_subtask_script,
    write_set_done_and_duplicate_plan_phase_script,
    write_set_done_and_duplicate_subtask_script,
    write_set_done_script,
    write_set_plan_phase_done_script,
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


def test_verification_runs_for_newly_done_bundled_plan_phase(tmp_path: Path) -> None:
    verification_marker = "phase-verification-ran.txt"
    verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{verification_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = {
        **base_feature(status="in_progress"),
        "title": "Bundled feature iteration smoke test",
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    plan_frontmatter = {
        "plan_id": "FEAT-900",
        "feature_id": "FEAT-900",
        "status": "in_progress",
        "source_spec": "spec.yaml",
        "planning_tier": "planned",
        "phases": [
            {
                "id": "P1",
                "title": "Run plan verification",
                "status": "pending",
                "verification": [verification_command],
            }
        ],
    }
    project_root, feature_path, plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter=plan_frontmatter,
    )
    init_git_repo(project_root)
    script_path = write_set_plan_phase_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-plan-phase-done.py",
        "P1",
    )

    def implement_effect() -> None:
        run_python_script(script_path, plan_path)

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
    assert outcome.verification_status == "passed"
    assert outcome.verification_failed_command is None
    assert (project_root / verification_marker).exists()


def test_phase_verification_runs_duplicate_commands_only_once_per_iteration(
    tmp_path: Path,
) -> None:
    verification_marker = "deduplicated-phase-verification-ran.txt"
    verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{verification_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = {
        **base_feature(status="in_progress"),
        "title": "Bundled phase verification deduplication test",
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    project_root, feature_path, plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Complete the first bundled phase",
                    "status": "pending",
                    "verification": [verification_command],
                },
                {
                    "id": "P2",
                    "title": "Complete the second bundled phase",
                    "status": "pending",
                    "verification": [verification_command],
                },
            ],
        },
    )
    init_git_repo(project_root)

    def implement_effect() -> None:
        document = plan_path.read_text(encoding="utf-8")
        frontmatter_end = document.find("\n---", 4)
        frontmatter = yaml.safe_load(document[4:frontmatter_end])
        assert isinstance(frontmatter, dict)
        for phase in frontmatter.get("phases", []):
            if isinstance(phase, dict):
                phase["status"] = "done"
        plan_path.write_text(
            "---\n"
            + yaml.safe_dump(frontmatter, sort_keys=False)
            + "---\n"
            + document[frontmatter_end + 4 :],
            encoding="utf-8",
        )

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
    assert log_text.count(f"[verification] command={verification_command}") == 1


def test_phase_verification_runs_when_pre_implement_phase_status_is_missing(
    tmp_path: Path,
) -> None:
    verification_marker = "phase-verification-missing-status-ran.txt"
    verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{verification_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = {
        **base_feature(status="in_progress"),
        "title": "Bundled missing-status phase verification test",
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    project_root, feature_path, plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Recover verification from missing pre-status",
                    "verification": [verification_command],
                }
            ],
        },
    )
    init_git_repo(project_root)
    script_path = write_set_plan_phase_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-missing-status-phase-done.py",
        "P1",
    )

    def implement_effect() -> None:
        run_python_script(script_path, plan_path)

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
    assert outcome.verification_status == "passed"
    assert (project_root / verification_marker).exists()


def test_refresh_feature_after_implement_marks_completed_bundled_plan_done(
    tmp_path: Path,
) -> None:
    feature_data = {
        **base_feature(status="in_progress"),
        "title": "Bundled plan completion sync test",
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    project_root, feature_path, plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Complete the only bundled phase",
                    "status": "in_progress",
                }
            ],
        },
    )
    script_path = write_set_plan_phase_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-complete-plan-phase-done.py",
        "P1",
    )

    run_python_script(script_path, plan_path)
    outcome = refresh_feature_after_implement(project_root, feature_path)

    assert outcome.result == "passed"
    refreshed_feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    assert refreshed_feature["status"] == "done"
    assert outcome.feature is not None and outcome.feature["status"] == "done"
    plan_document = plan_path.read_text(encoding="utf-8")
    frontmatter_end = plan_document.find("\n---", 4)
    frontmatter = yaml.safe_load(plan_document[4:frontmatter_end])
    assert frontmatter["status"] == "done"
    assert frontmatter["phases"][0]["status"] == "done"


def test_refresh_feature_after_implement_normalizes_phase_statuses_before_sync(
    tmp_path: Path,
) -> None:
    feature_data = {
        **base_feature(status="in_progress"),
        "title": "Bundled plan whitespace status sync test",
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    project_root, feature_path, plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": " in_progress ",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Normalize bundled phase status before sync",
                    "status": " done ",
                }
            ],
        },
    )

    outcome = refresh_feature_after_implement(project_root, feature_path)

    assert outcome.result == "passed"
    assert outcome.feature is not None and outcome.feature["status"] == "done"
    refreshed_feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    assert refreshed_feature["status"] == "done"
    plan_document = plan_path.read_text(encoding="utf-8")
    frontmatter_end = plan_document.find("\n---", 4)
    frontmatter = yaml.safe_load(plan_document[4:frontmatter_end])
    assert frontmatter["status"] == "done"
    assert frontmatter["phases"][0]["status"] == " done "


def test_refresh_feature_after_implement_keeps_feature_in_progress_when_later_phase_has_no_status(
    tmp_path: Path,
) -> None:
    feature_data = {
        **base_feature(status="in_progress"),
        "title": "Bundled plan later missing-status sync test",
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    project_root, feature_path, plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Completed phase",
                    "status": "done",
                },
                {
                    "id": "P2",
                    "title": "Current phase",
                    "status": "done",
                },
                {
                    "id": "P3",
                    "title": "Later phase still untouched",
                },
            ],
        },
    )

    outcome = refresh_feature_after_implement(project_root, feature_path)

    assert outcome.result == "passed"
    assert outcome.feature is not None and outcome.feature["status"] == "in_progress"
    refreshed_feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    assert refreshed_feature["status"] == "in_progress"
    plan_document = plan_path.read_text(encoding="utf-8")
    frontmatter_end = plan_document.find("\n---", 4)
    frontmatter = yaml.safe_load(plan_document[4:frontmatter_end])
    assert frontmatter["status"] == "in_progress"
    assert "status" not in frontmatter["phases"][2]


def test_verification_runs_for_newly_done_phase_with_parseable_invalid_plan_contract(
    tmp_path: Path,
) -> None:
    verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('invalid-plan-phase-verification-ran.txt').write_text('ok', encoding='utf-8')\""
    )
    feature_data = {
        **base_feature(status="in_progress"),
        "title": "Bundled feature invalid plan contract smoke test",
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    plan_frontmatter = {
        "plan_id": "FEAT-900",
        "status": "in_progress",
        "source_spec": "spec.yaml",
        "planning_tier": "planned",
        "phases": [
            {
                "id": "P1",
                "title": "Run verification from invalid bundled plan contract",
                "status": "pending",
                "verification": [verification_command],
            }
        ],
    }
    project_root, feature_path, plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter=plan_frontmatter,
    )
    script_path = write_set_plan_phase_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-invalid-plan-phase-done.py",
        "P1",
    )

    def implement_effect() -> None:
        run_python_script(script_path, plan_path)

    pre_statuses = progress_status_snapshot(feature_path, feature_data)
    implement_effect()
    post_feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    commands = done_transition_verification_commands(
        pre_statuses,
        feature_path,
        post_feature,
    )

    assert commands == [verification_command]


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


def test_phase_verification_selection_uses_first_post_entry_for_duplicate_phase_ids(
    tmp_path: Path,
) -> None:
    primary_marker = "phase-verification-primary-ran.txt"
    duplicate_marker = "phase-verification-duplicate-ran.txt"
    primary_verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{primary_marker}').write_text('ok', encoding='utf-8')\""
    )
    duplicate_verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{duplicate_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = {
        **base_feature(status="in_progress"),
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    project_root, feature_path, plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Preserve one stable phase transition",
                    "status": "backlog",
                    "verification": [primary_verification_command],
                }
            ],
        },
    )
    script_path = write_set_done_and_duplicate_plan_phase_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-and-duplicate-phase-id.py",
        "P1",
        duplicate_verification_command,
    )

    def implement_effect() -> None:
        run_python_script(script_path, plan_path)

    with with_opencode_implement_side_effect(implement_effect):
        outcome = _run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            attempt=1,
            feedback=None,
            verbose_output=False,
        )

    assert outcome.verification_status == "passed"
    assert (project_root / primary_marker).exists()
    assert not (project_root / duplicate_marker).exists()


def test_phase_verification_selection_uses_first_pre_status_for_duplicate_phase_ids(
    tmp_path: Path,
) -> None:
    verification_marker = "phase-verification-first-pre-status-ran.txt"
    verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{verification_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = {
        **base_feature(status="in_progress"),
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    project_root, feature_path, plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Primary pre-implement phase",
                    "status": "backlog",
                    "verification": [verification_command],
                },
                {
                    "id": "P1",
                    "title": "Duplicate pre-implement phase",
                    "status": "done",
                    "verification": ["true"],
                },
            ],
        },
    )
    script_path = write_set_plan_phase_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-first-duplicate-phase-done.py",
        "P1",
    )

    def implement_effect() -> None:
        run_python_script(script_path, plan_path)

    with with_opencode_implement_side_effect(implement_effect):
        outcome = _run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            attempt=1,
            feedback=None,
            verbose_output=False,
        )

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
