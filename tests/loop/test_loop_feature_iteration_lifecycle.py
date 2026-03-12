from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

import engineeringagent.loop as loop_module
from engineeringagent.adapters.runtime import enforce_worktree_precondition
import engineeringagent.adapters.runtime.loop_run_builder as loop_run_builder_module
from engineeringagent.application import ImplementStepResult
from engineeringagent.bootstrap import runtime_support as runtime_support_module
from engineeringagent.ports import WorktreeStatus
from tests.loop.feature_iteration_support import (
    base_feature,
    init_git_repo,
    invoke_cli,
    make_project_root,
    move_feature_to_done,
    passing_implement_result,
    read_runs,
    run_git,
    run_loop,
    run_python_script,
    with_opencode_implement_side_effect,
    write_delete_selected_feature_script,
    write_move_to_done_script,
    write_set_done_script,
)


def test_run_loop_requires_clean_worktree_by_default(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    init_git_repo(project_root)

    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    feature["context"] = "dirty change"
    feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding="utf-8")

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "Precondition failed" in output
    assert "--allow-dirty" in output


def test_run_loop_archives_done_active_feature(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    project_root, feature_path = make_project_root(
        tmp_path,
        feature_data=base_feature(status="done"),
    )
    init_git_repo(project_root)

    monkeypatch.setattr(
        loop_module,
        "run_implement_step",
        lambda *_args, **_kwargs: passing_implement_result(),
    )
    monkeypatch.setattr(loop_module, "preflight", lambda **_: True)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=2,
    )

    archived_path = (
        project_root
        / "docs"
        / "spec"
        / "features_done"
        / feature_path.parent.name
        / "spec.yaml"
    )
    assert code == 0
    assert not feature_path.exists()
    assert archived_path.exists()


def test_run_loop_requires_git_repo_before_allow_dirty_hint(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "Precondition failed" in output
    assert "run inside a git repository" in output
    assert "--allow-dirty" not in output
    assert "git init" in output


def test_enforce_worktree_precondition_reads_git_status_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubVersionControlGateway:
        def __init__(self) -> None:
            self.calls: list[Path] = []

        def worktree_status(self, workspace_path: Path) -> WorktreeStatus:
            self.calls.append(workspace_path)
            return WorktreeStatus(dirty=False, stdout="", stderr="")

    gateway = StubVersionControlGateway()
    monkeypatch.setattr(
        loop_module,
        "_build_version_control_gateway",
        lambda _project_root: gateway,
    )

    code = enforce_worktree_precondition(
        tmp_path,
        allow_dirty=False,
        read_worktree_status=gateway.worktree_status,
    )

    assert code is None
    assert gateway.calls == [tmp_path]


def test_run_loop_allows_uncommitted_changes_with_allow_dirty(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    script_path = write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-allow-dirty.py"
    )
    init_git_repo(project_root)

    (project_root / "notes.txt").write_text("restart with edits\n", encoding="utf-8")

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            dry_run=False,
            allow_dirty=True,
            max_iterations=5,
        )

    output = capsys.readouterr().out
    assert code == 0
    assert "Allow-dirty override enabled" in output


def test_run_loop_moves_completed_feature_to_features_done(tmp_path: Path) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    script_path = write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-archive.py"
    )
    init_git_repo(project_root)

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            dry_run=False,
            max_iterations=5,
        )

    archived_path = (
        project_root
        / "docs"
        / "spec"
        / "features_done"
        / feature_path.parent.name
        / "spec.yaml"
    )
    assert code == 0
    assert not feature_path.exists()
    assert archived_path.exists()


def test_run_loop_selected_feature_moved_to_features_done_completes_cleanly(
    tmp_path: Path,
    capsys: Any,
) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    init_git_repo(project_root)
    script_path = write_move_to_done_script(
        tmp_path.parent / f"{tmp_path.name}-move-selected-to-done.py"
    )

    def implement_effect() -> None:
        run_python_script(script_path, project_root, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            dry_run=False,
            max_iterations=3,
        )

    archived_path = (
        project_root
        / "docs"
        / "spec"
        / "features_done"
        / feature_path.parent.name
        / "spec.yaml"
    )
    output = capsys.readouterr().out
    assert code == 0
    assert not feature_path.exists()
    assert archived_path.exists()
    assert "selected feature path is missing and not recoverable" not in output
    runs = read_runs(project_root)
    assert runs
    assert runs[-1]["result"] == "passed"
    assert runs[-1]["failed_gate"] is None
    assert runs[-1]["next_action"] == "select_next_feature"


def test_run_loop_archived_done_without_completion_commit_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    project_root, _feature_path = make_project_root(tmp_path, feature_data=base_feature())
    init_git_repo(project_root)

    def fake_choose_feature_with_selector(
        project_root: Path,
        pending: list[tuple[Path, dict[str, Any]]],
    ) -> tuple[Path, dict[str, Any]]:
        chosen_path, chosen_feature = pending[0]
        move_feature_to_done(project_root, chosen_path)
        return chosen_path, chosen_feature

    monkeypatch.setattr(
        loop_run_builder_module,
        "_choose_feature_with_selector",
        fake_choose_feature_with_selector,
    )
    monkeypatch.setattr(loop_module, "preflight", lambda **_: True)

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        dry_run=False,
        run_all=True,
        max_iterations=3,
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "selected feature path is missing and not recoverable" in output
    assert "selected feature path disappeared during loop iteration" in output
    assert "next=retry_same_feature" in output

    runs = read_runs(project_root)
    assert runs
    assert runs[-1]["result"] == "failed"
    assert runs[-1]["failed_gate"] == "feature_missing"
    assert runs[-1]["next_action"] == "retry_same_feature"
    assert all(run["next_action"] != "select_next_feature" for run in runs)


def test_run_loop_all_selected_feature_moved_to_features_done_continues_to_next(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    project_root, first_feature_path = make_project_root(
        tmp_path, feature_data=base_feature()
    )
    second_feature = base_feature(status="backlog")
    second_feature["id"] = "FEAT-901"
    second_feature_path = (
        project_root / "docs" / "spec" / "features" / "FEAT-901-secondary" / "spec.yaml"
    )
    second_feature_path.parent.mkdir(parents=True, exist_ok=True)
    second_feature_path.write_text(
        yaml.safe_dump(second_feature, sort_keys=False),
        encoding="utf-8",
    )
    init_git_repo(project_root)

    def fake_run_implement_step(
        project_root: Path,
        feature: dict[str, Any],
        feature_path: Path,
        feedback: str | None,
        verbose_output: bool,
    ) -> ImplementStepResult:
        del feedback, verbose_output
        if str(feature.get("id", "")) == "FEAT-900":
            move_feature_to_done(project_root, feature_path)
            return passing_implement_result()
        feature["status"] = "done"
        feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding="utf-8")
        return passing_implement_result()

    monkeypatch.setattr(runtime_support_module, "run_implement_step", fake_run_implement_step)
    monkeypatch.setattr(loop_module, "run_implement_step", fake_run_implement_step)
    monkeypatch.setattr(loop_module, "preflight", lambda **_: True)

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        dry_run=False,
        run_all=True,
        max_iterations=5,
    )

    archived_first = (
        project_root
        / "docs"
        / "spec"
        / "features_done"
        / first_feature_path.parent.name
        / "spec.yaml"
    )
    archived_second = (
        project_root
        / "docs"
        / "spec"
        / "features_done"
        / second_feature_path.parent.name
        / "spec.yaml"
    )
    output = capsys.readouterr().out
    assert code == 0
    assert not first_feature_path.exists()
    assert not second_feature_path.exists()
    assert archived_first.exists()
    assert archived_second.exists()
    assert "selected feature path is missing and not recoverable" not in output
    runs = read_runs(project_root)
    run_feature_ids = [run["feature_id"] for run in runs]
    assert "FEAT-900" in run_feature_ids
    assert "FEAT-901" in run_feature_ids
    first_run = next(run for run in runs if run["feature_id"] == "FEAT-900")
    assert first_run["failed_gate"] is None


def test_run_loop_missing_selected_feature_without_archive_fails_cleanly(
    tmp_path: Path,
    capsys: Any,
) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    init_git_repo(project_root)
    script_path = write_delete_selected_feature_script(
        tmp_path.parent / f"{tmp_path.name}-delete-selected-feature.py"
    )

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            dry_run=False,
            max_iterations=3,
        )

    output = capsys.readouterr().out
    assert code == 1
    assert "Stopping loop: selected feature path is missing and not recoverable." in output
    assert "selected feature path disappeared during loop iteration" in output
    assert str(feature_path) in output

    runs = read_runs(project_root)
    assert runs
    assert runs[-1]["result"] == "failed"
    assert runs[-1]["failed_gate"] == "feature_missing"


def test_run_loop_fails_when_preexisting_done_active_feature_trips_validate(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    preexisting_done_path = (
        project_root
        / "docs"
        / "spec"
        / "features"
        / "FEAT-901-preexisting-done"
        / "spec.yaml"
    )
    preexisting_done_path.parent.mkdir(parents=True, exist_ok=True)
    preexisting_done_feature = base_feature(status="done")
    preexisting_done_feature["id"] = "FEAT-901"
    preexisting_done_path.write_text(
        yaml.safe_dump(preexisting_done_feature, sort_keys=False),
        encoding="utf-8",
    )

    init_git_repo(project_root)

    def fake_run_implement_step(
        project_root: Path,
        feature: dict[str, Any],
        feature_path: Path,
        feedback: str | None,
        verbose_output: bool,
    ) -> ImplementStepResult:
        del project_root, feedback, verbose_output
        if str(feature.get("id", "")) == "FEAT-900":
            feature["status"] = "done"
            feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding="utf-8")
        return passing_implement_result()

    monkeypatch.setattr(runtime_support_module, "run_implement_step", fake_run_implement_step)
    monkeypatch.setattr(loop_module, "run_implement_step", fake_run_implement_step)
    monkeypatch.setattr(loop_module, "preflight", lambda **_: True)
    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path), str(preexisting_done_path)],
        dry_run=False,
        max_iterations=5,
    )

    archived_selected_path = (
        project_root
        / "docs"
        / "spec"
        / "features_done"
        / feature_path.parent.name
        / "spec.yaml"
    )
    archived_preexisting_done_path = (
        project_root
        / "docs"
        / "spec"
        / "features_done"
        / preexisting_done_path.parent.name
        / "spec.yaml"
    )

    assert code == 1
    assert not archived_selected_path.exists()
    assert feature_path.exists()
    assert preexisting_done_path.exists()
    assert not archived_preexisting_done_path.exists()
    runs = read_runs(project_root)
    assert runs[-1]["failed_gate"] == "validate"


def test_run_loop_archives_done_feature_before_gate_execution(tmp_path: Path) -> None:
    gate_script = tmp_path.parent / f"{tmp_path.name}-assert-pre-gate-archive.py"
    gate_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "active = Path(sys.argv[1])",
                "archived = Path(sys.argv[2])",
                "if active.exists() or not archived.exists():",
                "    raise SystemExit(1)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    feature_data = base_feature()
    gates_data = {
        "profiles": {"loop_fast": ["assert_pre_gate_archive"]},
        "gates": {
            "assert_pre_gate_archive": {
                "run": (
                    f'"{sys.executable}" "{gate_script}" '
                    "docs/spec/features/FEAT-900-ralph-test/spec.yaml "
                    "docs/spec/features_done/FEAT-900-ralph-test/spec.yaml"
                )
            }
        },
    }
    project_root, feature_path = make_project_root(
        tmp_path,
        feature_data=feature_data,
        gates_data=gates_data,
    )
    script_path = write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-pre-gate-archive.py"
    )
    init_git_repo(project_root)

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            dry_run=False,
            max_iterations=5,
        )

    archived_path = (
        project_root
        / "docs"
        / "spec"
        / "features_done"
        / feature_path.parent.name
        / "spec.yaml"
    )
    assert code == 0
    assert not feature_path.exists()
    assert archived_path.exists()


def test_run_loop_restores_archived_feature_when_gate_fails_after_prearchive(
    tmp_path: Path,
) -> None:
    gate_script = tmp_path.parent / f"{tmp_path.name}-fail-after-pre-gate-archive.py"
    gate_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "active = Path(sys.argv[1])",
                "archived = Path(sys.argv[2])",
                "if active.exists() or not archived.exists():",
                "    raise SystemExit('pre-gate archive ordering check failed')",
                "raise SystemExit('forced gate failure after pre-archive')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    feature_data = base_feature()
    gates_data = {
        "profiles": {"loop_fast": ["spec_validate"]},
        "gates": {
            "spec_validate": {
                "run": (
                    f'"{sys.executable}" "{gate_script}" '
                    "docs/spec/features/FEAT-900-ralph-test/spec.yaml "
                    "docs/spec/features_done/FEAT-900-ralph-test/spec.yaml"
                )
            }
        },
    }
    project_root, feature_path = make_project_root(
        tmp_path,
        feature_data=feature_data,
        gates_data=gates_data,
    )
    script_path = write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-rollback.py"
    )
    init_git_repo(project_root)

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            dry_run=False,
            max_iterations=1,
        )

    archived_path = (
        project_root
        / "docs"
        / "spec"
        / "features_done"
        / feature_path.parent.name
        / "spec.yaml"
    )
    restored_feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    runs = read_runs(project_root)

    assert code == 1
    assert feature_path.exists()
    assert not archived_path.exists()
    assert restored_feature["status"] == "done"
    assert runs[-1]["result"] == "failed"
    assert runs[-1]["failed_gate"] == "spec_validate"
    assert runs[-1]["next_action"] == "retry_same_feature"


def test_run_loop_spec_validate_no_longer_blocks_done_archive_ordering(
    tmp_path: Path,
) -> None:
    gate_script = tmp_path.parent / f"{tmp_path.name}-spec-validate-done-in-active-check.py"
    gate_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "import yaml",
                "active = Path(sys.argv[1])",
                "if active.exists():",
                "    feature = yaml.safe_load(active.read_text(encoding='utf-8'))",
                "    if feature.get('status') == 'done':",
                "        raise SystemExit('spec_validate blocked: done feature remained in active dir')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    feature_data = base_feature()
    gates_data = {
        "profiles": {"loop_fast": ["spec_validate"]},
        "gates": {
            "spec_validate": {
                "run": f'"{sys.executable}" "{gate_script}" docs/spec/features/FEAT-900-ralph-test/spec.yaml'
            }
        },
    }
    project_root, feature_path = make_project_root(
        tmp_path,
        feature_data=feature_data,
        gates_data=gates_data,
    )
    script_path = write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-spec-validate-ordering.py"
    )
    init_git_repo(project_root)

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            dry_run=False,
            max_iterations=5,
        )

    archived_path = (
        project_root
        / "docs"
        / "spec"
        / "features_done"
        / feature_path.parent.name
        / "spec.yaml"
    )
    runs = read_runs(project_root)

    assert code == 0
    assert not feature_path.exists()
    assert archived_path.exists()
    assert len(runs) == 1
    assert runs[0]["result"] == "passed"
    assert runs[0]["failed_gate"] is None


def test_run_loop_completion_commit_includes_archive_move(tmp_path: Path) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    script_path = write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-commit-move.py"
    )
    init_git_repo(project_root)

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            dry_run=False,
            max_iterations=5,
        )

    assert code == 0
    changed_paths = run_git(
        project_root,
        "show",
        "--name-status",
        "--pretty=format:",
        "HEAD",
    ).stdout.splitlines()
    expected_rename_suffix = (
        f"\tdocs/spec/features/{feature_path.parent.name}/spec.yaml"
        f"\tdocs/spec/features_done/{feature_path.parent.name}/spec.yaml"
    )
    assert any(
        line.startswith("R") and line.endswith(expected_rename_suffix)
        for line in changed_paths
    )


def test_loop_uses_expected_commit_subject(tmp_path: Path) -> None:
    feature_data = base_feature()
    feature_data["expected_commit_subject"] = "docs: publish FEAT-900 release notes"
    project_root, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    script_path = write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-expected-subject.py"
    )
    init_git_repo(project_root)

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            dry_run=False,
            max_iterations=5,
        )

    assert code == 0
    subject = run_git(project_root, "log", "-1", "--pretty=%s").stdout.strip()
    assert subject == "docs: publish FEAT-900 release notes"


def test_loop_fails_validation_when_expected_commit_subject_missing(
    tmp_path: Path,
) -> None:
    max_iterations = 5
    feature_data = base_feature()
    feature_data.pop("expected_commit_subject")
    feature_data["type"] = "bug"
    project_root, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    script_path = write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-fallback-subject.py"
    )
    init_git_repo(project_root)

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            dry_run=False,
            max_iterations=max_iterations,
        )

    assert code == 1
    runs = read_runs(project_root)
    assert len(runs) == max_iterations
    assert all(run["result"] == "failed" for run in runs)
    assert all(run["failed_gate"] == "validate" for run in runs)
    assert runs[-1]["attempt"] == max_iterations


def test_git_add_failure_exits_immediately(tmp_path: Path) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    script_path = write_set_done_script(tmp_path.parent / f"{tmp_path.name}-set-done.py")
    init_git_repo(project_root)

    (project_root / ".git" / "index.lock").write_text("locked\n", encoding="utf-8")

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            dry_run=False,
            max_iterations=6,
        )

    assert code == 1
    runs = read_runs(project_root)
    assert len(runs) == 1
    assert runs[0]["result"] == "failed"
    assert runs[0]["failed_gate"] == "git_add"
    assert runs[0]["attempt"] == 1


def test_run_loop_commit_failure_preserves_retryable_feature_path(
    tmp_path: Path,
) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    script_path = tmp_path.parent / f"{tmp_path.name}-set-done-allow.py"
    attempted_paths_path = project_root / ".attempted_feature_paths"
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "import yaml",
                "project_root = Path(sys.argv[1])",
                "feature_path = Path(sys.argv[2])",
                "counter_path = project_root / '.attempt_count'",
                "count = int(counter_path.read_text(encoding='utf-8')) if counter_path.exists() else 0",
                "count += 1",
                "counter_path.write_text(str(count), encoding='utf-8')",
                "attempted_paths_path = project_root / '.attempted_feature_paths'",
                "with attempted_paths_path.open('a', encoding='utf-8') as f:",
                "    f.write(str(feature_path) + '\\n')",
                "feature = yaml.safe_load(feature_path.read_text(encoding='utf-8'))",
                "feature['status'] = 'done'",
                "feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding='utf-8')",
                "if count >= 2:",
                "    (project_root / '.allow_commit').write_text('ok\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    init_git_repo(project_root)

    hook_path = project_root / ".git" / "hooks" / "pre-commit"
    hook_path.write_text(
        "#!/usr/bin/env bash\n"
        "if [ ! -f .allow_commit ]; then\n"
        "  echo hook blocked\n"
        "  exit 1\n"
        "fi\n",
        encoding="utf-8",
    )
    hook_path.chmod(0o755)

    def implement_effect() -> None:
        run_python_script(script_path, project_root, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            dry_run=False,
            max_iterations=6,
        )

    assert code == 0
    runs = read_runs(project_root)
    assert len(runs) >= 2
    assert runs[0]["failed_gate"] == "git_commit"
    assert runs[-1]["result"] == "passed"
    archived_path = (
        project_root
        / "docs"
        / "spec"
        / "features_done"
        / feature_path.parent.name
        / "spec.yaml"
    )
    assert archived_path.exists()
    attempted_paths = attempted_paths_path.read_text(encoding="utf-8").splitlines()
    assert attempted_paths
    assert all(path == str(feature_path) for path in attempted_paths)


def test_cli_legacy_loop_command_removed() -> None:
    result = invoke_cli(["loop", "run", "--feature-id", "FEAT-900"])

    assert result.exit_code == 2
    assert "No such command" in result.stderr


def test_cli_run_help_includes_allow_dirty_flag() -> None:
    result = invoke_cli(["run", "--help"])

    assert result.exit_code == 0
    assert "--allow-dirty" in result.stdout


def test_cli_run_help_includes_verbose_output_flag() -> None:
    result = invoke_cli(["run", "--help"])

    assert result.exit_code == 0
    assert "--verbose-output" in result.stdout


def test_run_loop_reports_invalid_feature_path(tmp_path: Path, capsys: Any) -> None:
    project_root, _ = make_project_root(tmp_path, feature_data=base_feature())
    init_git_repo(project_root)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(project_root / "missing.yaml")],
        dry_run=False,
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "does not exist" in output
