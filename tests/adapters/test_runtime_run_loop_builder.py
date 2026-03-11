from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, TypedDict

import engineeringagent.adapters.runtime.run_loop_builder as run_builder_module
from engineeringagent.adapters.runtime.run_loop_context import (
    LoopRun,
    RunConfig,
    RunState,
)
from engineeringagent.application.feature_iteration_models import (
    FeatureIterationInputs,
    IterationOutcome,
    IterationSummaryInputs,
)
from engineeringagent.ports import VersionControlFailure, WorktreeStatus


class _ConfigOverrides(TypedDict, total=False):
    run_all: bool
    dry_run: bool
    max_iterations: int
    verbose_output: bool


class _OutcomeExtras(TypedDict, total=False):
    failed_gate: str
    next_action: str
    feedback: str
    log_path: str


BuildSelectorPrompt = Callable[[list[tuple[Path, dict[str, Any]]]], str]
RunAgentFn = Callable[..., object]


def _config(
    tmp_path: Path,
    *,
    run_all: bool = False,
    dry_run: bool = False,
    max_iterations: int = 5,
    verbose_output: bool = False,
) -> RunConfig:
    return RunConfig(
        project_root=tmp_path,
        feature_paths=(),
        dry_run=dry_run,
        run_all=run_all,
        max_iterations=max_iterations,
        verbose_output=verbose_output,
    )


def _loop_run(
    tmp_path: Path,
    *,
    resolved_feature_paths: tuple[Path, ...] = (),
    total_iterations: int = 0,
    config_overrides: _ConfigOverrides | None = None,
) -> LoopRun:
    overrides = config_overrides or {}
    return run_builder_module.build_loop_run(
        _config(
            tmp_path,
            run_all=overrides.get("run_all", False),
            dry_run=overrides.get("dry_run", False),
            max_iterations=overrides.get("max_iterations", 5),
            verbose_output=overrides.get("verbose_output", False),
        ),
        enforce_worktree_precondition_fn=lambda _project_root, _allow_dirty: None,
        run_selected_feature_iterations_fn=lambda _loop_run: 0,
        print_summary_fn=lambda _summary: None,
    ).with_state(
        RunState(
            total_iterations=total_iterations,
            resolved_feature_paths=resolved_feature_paths,
        )
    )


def _outcome(
    *,
    completed: bool,
    result: str,
    extras: _OutcomeExtras | None = None,
) -> IterationOutcome:
    payload = extras or {}
    return IterationOutcome(
        completed=completed,
        result=result,
        failed_gate=payload.get("failed_gate"),
        next_action=str(payload.get("next_action", "continue_same_feature")),
        feedback=payload.get("feedback"),
        log_path=payload.get("log_path"),
    )


def test_run_all_snapshot_helpers_cover_banner_and_no_work(capsys: Any) -> None:
    """Render both snapshot banner helpers."""

    run_builder_module._print_run_all_snapshot_banner([Path("a"), Path("b")])
    captured: list[IterationSummaryInputs] = []
    run_builder_module._print_run_all_no_work_message(print_summary_fn=captured.append)

    output = capsys.readouterr().out
    assert "Startup snapshot captured 2 runnable feature entrypoint(s)" in output
    assert "No runnable active features found for --all startup snapshot" in output
    assert len(captured) == 1
    assert captured[0].result == "no_work"
    assert captured[0].next_action == "stop"


def test_build_selector_prompt_and_choose_feature_delegate(monkeypatch: Any, tmp_path: Path) -> None:
    """Build selector text and pass the expected collaborators to selection."""

    feature_path = tmp_path / "docs" / "spec" / "features" / "FEAT-300" / "spec.yaml"
    pending = [(feature_path, {"id": "FEAT-300", "status": "backlog", "priority": "high"})]
    recorded: dict[str, object] = {}

    def _choose(
        project_root: Path,
        pending_features: list[tuple[Path, dict[str, Any]]],
        *,
        build_selector_prompt_fn: BuildSelectorPrompt,
        run_agent_fn: RunAgentFn,
    ) -> tuple[Path, dict[str, Any]]:
        recorded["project_root"] = project_root
        recorded["prompt"] = build_selector_prompt_fn(pending_features)
        recorded["run_agent_fn"] = run_agent_fn
        return pending_features[0]

    monkeypatch.setattr(run_builder_module, "choose_feature_with_selector", _choose)

    selected = run_builder_module._choose_feature_with_selector(tmp_path, pending)

    assert selected == pending[0]
    assert recorded["project_root"] == tmp_path
    assert "Choose the next feature spec to execute" in str(recorded["prompt"])
    assert f"path={feature_path}" in str(recorded["prompt"])
    assert recorded["run_agent_fn"] is run_builder_module.run_agent


def test_iteration_cap_helpers_cover_continue_and_stop(capsys: Any) -> None:
    """Return deterministic cap decisions before and after failures."""

    assert run_builder_module._iteration_cap_reached(1, 2) is False
    assert run_builder_module._iteration_cap_reached(2, 2) is True
    assert run_builder_module._iteration_cap_reached_after_failure(
        _outcome(
            completed=False,
            result="failed",
            extras={"log_path": ".engineeringagent/progress/run.txt"},
        ),
        total_iterations=1,
        max_iterations=2,
    ) is False
    assert run_builder_module._iteration_cap_reached_after_failure(
        _outcome(
            completed=False,
            result="failed",
            extras={"log_path": ".engineeringagent/progress/run.txt"},
        ),
        total_iterations=2,
        max_iterations=2,
    ) is True

    output = capsys.readouterr().out
    assert "Reached max iteration cap (2) before completion." in output
    assert "Detailed log: .engineeringagent/progress/run.txt" in output


def test_snapshot_and_candidate_helpers_cover_all_branches(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Resolve snapshot removal and runnable candidates deterministically."""

    feature_path = tmp_path / "feature.yaml"
    other_path = tmp_path / "other.yaml"
    feature_path.write_text("", encoding="utf-8")
    other_path.write_text("", encoding="utf-8")

    assert run_builder_module._drop_completed_feature_from_snapshot(
        [feature_path, other_path],
        feature_path,
    ) == [feature_path, other_path]

    feature_path.unlink()
    assert run_builder_module._drop_completed_feature_from_snapshot(
        [feature_path, other_path],
        feature_path,
    ) == [other_path]

    pending = [(other_path, {"id": "FEAT-301"})]
    done_pending_archive = [(tmp_path / "archived.yaml", {"id": "FEAT-302"})]
    monkeypatch.setattr(run_builder_module, "pending_features", lambda _paths: pending)
    monkeypatch.setattr(
        run_builder_module,
        "done_features_pending_archive",
        lambda _paths: done_pending_archive,
    )
    assert run_builder_module._runnable_feature_candidates([other_path]) == pending

    monkeypatch.setattr(run_builder_module, "pending_features", lambda _paths: [])
    assert (
        run_builder_module._runnable_feature_candidates([other_path])
        == done_pending_archive
    )

    monkeypatch.setattr(
        run_builder_module,
        "done_features_pending_archive",
        lambda _paths: [],
    )
    assert run_builder_module._runnable_feature_candidates([other_path]) == []


def test_terminal_failure_exit_code_covers_known_failures(capsys: Any) -> None:
    """Map terminal failure gates to stable exit codes and messaging."""

    assert (
        run_builder_module._terminal_iteration_failure_exit_code(
            _outcome(
                completed=False,
                result="failed",
                extras={
                    "failed_gate": "git_add",
                    "log_path": ".engineeringagent/progress/git_add.txt",
                },
            )
        )
        == 1
    )
    assert (
        run_builder_module._terminal_iteration_failure_exit_code(
            _outcome(
                completed=False,
                result="failed",
                extras={
                    "failed_gate": "feature_missing",
                    "feedback": "feature file was deleted",
                    "log_path": ".engineeringagent/progress/feature_missing.txt",
                },
            )
        )
        == 1
    )
    assert (
        run_builder_module._terminal_iteration_failure_exit_code(
            _outcome(
                completed=False,
                result="failed",
                extras={"failed_gate": "reviewers"},
            )
        )
        is None
    )

    output = capsys.readouterr().out
    assert "git_add failure requires operator intervention" in output
    assert "selected feature path is missing and not recoverable" in output
    assert "Detail: feature file was deleted" in output


def test_target_and_snapshot_resolution_helpers(monkeypatch: Any, tmp_path: Path) -> None:
    """Dispatch snapshot and target resolution through the expected helpers."""

    resolved_paths = [tmp_path / "feature.yaml"]
    monkeypatch.setattr(
        run_builder_module,
        "discover_active_feature_paths",
        lambda project_root: resolved_paths if project_root == tmp_path else [],
    )
    monkeypatch.setattr(
        run_builder_module,
        "resolve_feature_paths",
        lambda project_root, feature_paths: [project_root / str(feature_paths[0])],
    )

    assert run_builder_module._resolve_run_targets(tmp_path, ("feature.yaml",), True) == resolved_paths
    assert run_builder_module._resolve_run_targets(tmp_path, ("feature.yaml",), False) == [tmp_path / "feature.yaml"]

    captured: list[IterationSummaryInputs] = []
    assert (
        run_builder_module._emit_run_all_snapshot_feedback(
            resolved_paths,
            False,
            print_summary_fn=captured.append,
        )
        is None
    )
    assert (
        run_builder_module._emit_run_all_snapshot_feedback(
            resolved_paths,
            True,
            print_summary_fn=captured.append,
        )
        is None
    )
    assert (
        run_builder_module._emit_run_all_snapshot_feedback(
            [],
            True,
            print_summary_fn=captured.append,
        )
        == 0
    )
    assert len(captured) == 1
    assert captured[0].result == "no_work"


def test_handle_dry_run_covers_pending_and_empty_paths(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Handle dry-run selection for both empty and pending snapshots."""

    feature_path = tmp_path / "docs" / "spec" / "features" / "FEAT-400" / "spec.yaml"
    pending = [(feature_path, {"id": "FEAT-400"})]

    monkeypatch.setattr(run_builder_module, "pending_features", lambda _paths: [])
    captured: list[IterationSummaryInputs] = []
    assert (
        run_builder_module._handle_dry_run(
            [],
            False,
            False,
            print_summary_fn=captured.append,
        )
        is None
    )
    assert (
        run_builder_module._handle_dry_run(
            [],
            False,
            True,
            print_summary_fn=captured.append,
        )
        == 0
    )
    assert (
        run_builder_module._handle_dry_run(
            [],
            True,
            True,
            print_summary_fn=captured.append,
        )
        == 0
    )

    monkeypatch.setattr(run_builder_module, "pending_features", lambda _paths: pending)
    monkeypatch.setattr(
        run_builder_module,
        "deterministic_feature_choice",
        lambda pending_features: pending_features[0],
    )
    assert (
        run_builder_module._handle_dry_run(
            [feature_path],
            True,
            True,
            print_summary_fn=captured.append,
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "No pending features found in provided paths." in output
    assert "[dry-run] Selection is taken from the startup snapshot" in output
    assert "[dry-run] Selected feature=FEAT-400" in output
    assert [summary.result for summary in captured] == [
        "dry_run",
        "no_work",
        "dry_run",
    ]
    assert captured[-1].feature_id == "FEAT-400"


def test_enforce_worktree_precondition_covers_git_failure_and_dirty_modes(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Reject unreadable and dirty worktrees unless explicitly overridden."""

    def _raise_failure(_project_root: Path) -> WorktreeStatus:
        raise VersionControlFailure("git status failed")

    assert (
        run_builder_module.enforce_worktree_precondition(
            tmp_path,
            False,
            read_worktree_status=_raise_failure,
        )
        == 1
    )
    assert (
        run_builder_module.enforce_worktree_precondition(
            tmp_path,
            False,
            read_worktree_status=lambda _project_root: WorktreeStatus(
                dirty=False,
                stdout="",
                stderr="",
            ),
        )
        is None
    )
    assert (
        run_builder_module.enforce_worktree_precondition(
            tmp_path,
            False,
            read_worktree_status=lambda _project_root: WorktreeStatus(
                dirty=True,
                stdout="",
                stderr="",
            ),
        )
        == 1
    )
    assert (
        run_builder_module.enforce_worktree_precondition(
            tmp_path,
            True,
            read_worktree_status=lambda _project_root: WorktreeStatus(
                dirty=True,
                stdout="",
                stderr="",
            ),
        )
        is None
    )

    output = capsys.readouterr().out
    assert "unable to read git status; run inside a git repository" in output
    assert "working tree must be clean before running automated loop" in output
    assert "Allow-dirty override enabled" in output


def test_run_selected_feature_iterations_handles_completion_and_terminal_failure(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Iterate through a completion and stop on a terminal missing-feature failure."""

    first_path = tmp_path / "first.yaml"
    second_path = tmp_path / "second.yaml"
    first_path.write_text("", encoding="utf-8")
    second_path.write_text("", encoding="utf-8")
    loop_run = _loop_run(
        tmp_path,
        resolved_feature_paths=(first_path, second_path),
        config_overrides={"max_iterations": 5, "verbose_output": True},
    )
    pending_sequences = [
        [(first_path, {"id": "FEAT-500"})],
        [(second_path, {"id": "FEAT-501"})],
        [],
    ]

    monkeypatch.setattr(
        run_builder_module,
        "_runnable_feature_candidates",
        lambda _resolved_paths: pending_sequences.pop(0),
    )
    monkeypatch.setattr(
        run_builder_module,
        "_choose_feature_with_selector",
        lambda _project_root, pending: pending[0],
    )

    seen_inputs: list[FeatureIterationInputs] = []

    def _run_feature_iteration(inputs: FeatureIterationInputs) -> IterationOutcome:
        seen_inputs.append(inputs)
        if inputs.feature_path == first_path:
            first_path.unlink()
            return _outcome(
                completed=True,
                result="passed",
                extras={"next_action": "continue_same_feature"},
            )
        return _outcome(
            completed=False,
            result="failed",
            extras={
                "failed_gate": "feature_missing",
                "feedback": "selected path disappeared",
                "log_path": ".engineeringagent/progress/FEAT-501/run.txt",
                "next_action": "stop",
            },
        )

    assert (
        run_builder_module.run_selected_feature_iterations(
            loop_run,
            run_feature_iteration=_run_feature_iteration,
        )
        == 1
    )

    assert [item.feature_path for item in seen_inputs] == [first_path, second_path]
    assert seen_inputs[0].attempt == 1
    assert seen_inputs[1].attempt == 2
    assert seen_inputs[1].verbose_output is True
    output = capsys.readouterr().out
    assert "Selected feature=FEAT-500" in output
    assert "Selected feature=FEAT-501" in output
    assert "selected feature path is missing and not recoverable" in output


def test_run_selected_feature_iterations_covers_done_and_iteration_cap(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Return early for empty snapshots and when the cap is reached after a failure."""

    empty_loop = _loop_run(
        tmp_path,
        resolved_feature_paths=(),
        config_overrides={"max_iterations": 3},
    )
    monkeypatch.setattr(run_builder_module, "_runnable_feature_candidates", lambda _paths: [])
    assert (
        run_builder_module.run_selected_feature_iterations(
            empty_loop,
            run_feature_iteration=lambda _inputs: _outcome(completed=True, result="passed"),
        )
        == 0
    )

    feature_path = tmp_path / "feature.yaml"
    feature_path.write_text("", encoding="utf-8")
    capped_loop = _loop_run(
        tmp_path,
        resolved_feature_paths=(feature_path,),
        total_iterations=1,
        config_overrides={"max_iterations": 2},
    )
    monkeypatch.setattr(
        run_builder_module,
        "_runnable_feature_candidates",
        lambda _paths: [(feature_path, {"id": "FEAT-600"})],
    )
    monkeypatch.setattr(
        run_builder_module,
        "_choose_feature_with_selector",
        lambda _project_root, pending: pending[0],
    )
    assert (
        run_builder_module.run_selected_feature_iterations(
            capped_loop,
            run_feature_iteration=lambda _inputs: _outcome(
                completed=False,
                result="failed",
                extras={
                    "failed_gate": "checks",
                    "log_path": ".engineeringagent/progress/FEAT-600/run.txt",
                },
            ),
        )
        == 1
    )

    output = capsys.readouterr().out
    assert "All provided features are done and committed." in output
    assert "Reached max iteration cap (2) before completion." in output


def test_build_run_config_and_loop_run_wire_default_services(tmp_path: Path) -> None:
    """Build typed config and loop context from scalar options."""

    config = run_builder_module.build_run_config(
        project_root=tmp_path,
        feature_paths=("a.yaml", Path("b.yaml")),
        options=run_builder_module.RunConfigOptions(
            dry_run=True,
            run_all=True,
            max_iterations=7,
            allow_dirty=True,
            verbose_output=True,
        ),
    )
    loop_run = run_builder_module.build_loop_run(
        config,
        enforce_worktree_precondition_fn=lambda _project_root, _allow_dirty: None,
        run_selected_feature_iterations_fn=lambda _loop_run: 0,
        print_summary_fn=lambda _summary: None,
    )

    assert config.feature_paths == ("a.yaml", Path("b.yaml"))
    assert config.run_all is True
    assert config.dry_run is True
    assert config.max_iterations == 7
    assert config.allow_dirty is True
    assert config.verbose_output is True
    assert loop_run.config == config
    assert loop_run.services.resolve_run_targets is run_builder_module._resolve_run_targets
    assert callable(loop_run.services.emit_run_all_snapshot_feedback)
    assert callable(loop_run.services.handle_dry_run)
    assert loop_run.services.run_permission_precheck is run_builder_module.preflight
