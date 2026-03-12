from __future__ import annotations

import sys
from pathlib import Path

import yaml

from engineeringagent.application.feature_iteration_service import (
    FeatureIterationRequest,
)
from engineeringagent.application.feature_iteration_service import (
    IterationOutcome,
)
from engineeringagent.bootstrap import AppFactory
from engineeringagent.adapters.runtime.feature_state import (
    refresh_feature_after_implement,
)
from engineeringagent.domain.specification import (
    done_transition_verification_commands,
    progress_status_snapshot,
)
from tests.loop.feature_iteration_support import (
    base_feature,
    init_git_repo,
    make_bundled_project_root,
    read_runs,
    run_python_script,
    with_opencode_implement_side_effect,
    write_set_done_and_duplicate_plan_phase_script,
    write_set_plan_phase_done_script,
)


def _run_feature_iteration(
    *,
    project_root: Path,
    feature_path: Path,
    run_all: bool,
    attempt: int,
    feedback: str | None,
    verbose_output: bool,
) -> IterationOutcome:
    result = AppFactory(project_root).build_feature_iteration_service().run(
        FeatureIterationRequest(
            project_root=project_root,
            feature_path=feature_path,
            run_all=run_all,
            attempt=attempt,
            feedback=feedback,
            verbose_output=verbose_output,
        )
    )
    return IterationOutcome.model_validate(result.model_dump())


def test_verification_runs_for_newly_done_bundled_plan_phase(tmp_path: Path) -> None:
    """Run phase verification when the current iteration completes a phase."""

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
    """Deduplicate identical verification commands across newly done phases."""

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
    """Run verification when the pre-implement snapshot did not include the phase."""

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
    """Mark the feature done when every planned phase is complete."""

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
    """Normalize whitespace-padded phase statuses before syncing feature state."""

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
    """Keep the feature active when a later phase lacks a resolved status."""

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
    """Use raw frontmatter fallback when the validated plan artifact is unavailable."""

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


def test_phase_verification_selection_uses_first_post_entry_for_duplicate_phase_ids(
    tmp_path: Path,
) -> None:
    """Use the first post-implement duplicate phase id when collecting commands."""

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
    """Use the first pre-implement duplicate phase id when detecting transitions."""

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
