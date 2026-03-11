from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

import engineeringagent.loop as loop_module
import engineeringagent.presentation.terminal as presentation_module
from engineeringagent.loop_runtime.models import IterationSummaryInputs
from tests.loop.feature_iteration_support import (
    FEATURE_LOG_REF,
    RUNS_LOG_REF,
    base_feature,
    copy_canonical_prompts,
    init_git_repo,
    make_bundled_project_root,
    make_project_root,
    progress_root,
    read_runs,
    run_git,
    run_loop,
    run_python_script,
    with_opencode_implement_result,
    with_opencode_implement_side_effect,
    write_set_done_and_create_feature_script,
    write_set_done_script,
)


def test_run_loop_all_discovers_backlog_and_in_progress_only(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, _ = make_project_root(tmp_path, feature_data=base_feature())
    features_dir = project_root / "docs" / "spec" / "features"

    backlog_feature = base_feature(status="backlog")
    backlog_feature["id"] = "FEAT-901"
    (features_dir / "FEAT-901-backlog" / "spec.yaml").parent.mkdir(
        parents=True, exist_ok=True
    )
    (features_dir / "FEAT-901-backlog" / "spec.yaml").write_text(
        yaml.safe_dump(backlog_feature, sort_keys=False),
        encoding="utf-8",
    )

    in_progress_feature = base_feature(status="in_progress")
    in_progress_feature["id"] = "FEAT-902"
    (features_dir / "FEAT-902-in-progress" / "spec.yaml").parent.mkdir(
        parents=True, exist_ok=True
    )
    (features_dir / "FEAT-902-in-progress" / "spec.yaml").write_text(
        yaml.safe_dump(in_progress_feature, sort_keys=False),
        encoding="utf-8",
    )

    blocked_feature = base_feature(status="blocked")
    blocked_feature["id"] = "FEAT-903"
    (features_dir / "FEAT-903-blocked" / "spec.yaml").parent.mkdir(
        parents=True, exist_ok=True
    )
    (features_dir / "FEAT-903-blocked" / "spec.yaml").write_text(
        yaml.safe_dump(blocked_feature, sort_keys=False),
        encoding="utf-8",
    )

    done_feature = base_feature(status="done")
    done_feature["id"] = "FEAT-904"
    (features_dir / "FEAT-904-done" / "spec.yaml").parent.mkdir(
        parents=True, exist_ok=True
    )
    (features_dir / "FEAT-904-done" / "spec.yaml").write_text(
        yaml.safe_dump(done_feature, sort_keys=False),
        encoding="utf-8",
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        dry_run=True,
        run_all=True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "[dry-run] Resolved 3 feature file(s)." in output
    assert "feature=FEAT-902" in output
    assert "FEAT-903" not in output
    assert "FEAT-904" not in output


def test_run_all_uses_configured_docs_root(tmp_path: Path, capsys: Any) -> None:
    configured_docs_root = tmp_path / "docs.engineeringagent"
    configured_features_dir = configured_docs_root / "spec" / "features"
    default_features_dir = tmp_path / "docs" / "spec" / "features"

    (tmp_path / "engineeringagent.toml").write_text(
        'docs-root = "docs.engineeringagent"\n',
        encoding="utf-8",
    )
    (tmp_path / "harness" / "gates.yaml").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "harness" / "gates.yaml").write_text(
        yaml.safe_dump({"profiles": {"loop_fast": []}, "gates": {}}, sort_keys=False),
        encoding="utf-8",
    )

    configured_feature = base_feature(status="backlog")
    configured_feature["id"] = "FEAT-910"
    (configured_features_dir / "FEAT-910-configured-docs-root" / "spec.yaml").parent.mkdir(
        parents=True, exist_ok=True
    )
    (configured_features_dir / "FEAT-910-configured-docs-root" / "spec.yaml").write_text(
        yaml.safe_dump(configured_feature, sort_keys=False),
        encoding="utf-8",
    )

    default_feature = base_feature(status="backlog")
    default_feature["id"] = "FEAT-911"
    (default_features_dir / "FEAT-911-default-docs-root" / "spec.yaml").parent.mkdir(
        parents=True, exist_ok=True
    )
    (default_features_dir / "FEAT-911-default-docs-root" / "spec.yaml").write_text(
        yaml.safe_dump(default_feature, sort_keys=False),
        encoding="utf-8",
    )

    code = run_loop(
        project_root=tmp_path,
        feature_paths=[],
        dry_run=True,
        run_all=True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "[dry-run] Resolved 1 feature file(s)." in output
    assert "feature=FEAT-910" in output
    assert "FEAT-911" not in output


def test_run_loop_all_excludes_blocked_and_done_from_startup_snapshot(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, _ = make_project_root(tmp_path, feature_data=base_feature(status="done"))
    features_dir = project_root / "docs" / "spec" / "features"

    blocked_feature = base_feature(status="blocked")
    blocked_feature["id"] = "FEAT-903"
    (features_dir / "FEAT-903-blocked" / "spec.yaml").parent.mkdir(
        parents=True, exist_ok=True
    )
    (features_dir / "FEAT-903-blocked" / "spec.yaml").write_text(
        yaml.safe_dump(blocked_feature, sort_keys=False),
        encoding="utf-8",
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        dry_run=True,
        run_all=True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "No runnable active features found for --all startup snapshot" in output


def test_run_loop_all_exits_zero_when_no_runnable_features(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, _ = make_project_root(
        tmp_path, feature_data=base_feature(status="blocked")
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        dry_run=False,
        run_all=True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "No runnable active features found for --all startup snapshot" in output
    assert "result=no_work" in output


def test_run_loop_all_does_not_include_specs_created_after_startup(
    tmp_path: Path,
) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    features_dir = project_root / "docs" / "spec" / "features"
    created_feature_path = (
        features_dir / "FEAT-999-created-after-startup" / "spec.yaml"
    )
    script_path = write_set_done_and_create_feature_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-and-create-feature.py"
    )
    init_git_repo(project_root)

    def implement_effect() -> None:
        run_python_script(script_path, feature_path, created_feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[],
            dry_run=False,
            run_all=True,
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
    runs = read_runs(project_root)

    assert code == 0
    assert not feature_path.exists()
    assert archived_path.exists()
    assert created_feature_path.exists()
    assert [run["feature_id"] for run in runs] == ["FEAT-900"]


def test_run_loop_all_dry_run_reports_snapshot_selection(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, _ = make_project_root(tmp_path, feature_data=base_feature())

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        dry_run=True,
        run_all=True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "Startup snapshot captured" in output
    assert "Selection is taken from the startup snapshot" in output


def test_run_loop_all_snapshot_banner_mentions_feature_entrypoints_for_bundles(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, _, _ = make_bundled_project_root(
        tmp_path,
        feature_data={
            **base_feature(),
            "planning_tier": "planned",
            "artifacts": {"plan": "plan.md"},
        },
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": "backlog",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Bundle run-all smoke coverage",
                    "status": "backlog",
                }
            ],
        },
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        dry_run=True,
        run_all=True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "runnable feature entrypoint(s) from docs/spec/features/" in output
    assert "docs/spec/features/*.yaml" not in output
    assert "Selection is taken from the startup snapshot" in output


def test_run_loop_completes_feature_and_commits(tmp_path: Path) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    script_path = write_set_done_script(tmp_path.parent / f"{tmp_path.name}-set-done.py")
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
    runs = read_runs(project_root)
    assert len(runs) >= 1
    assert runs[-1]["feature_id"] == "FEAT-900"
    assert runs[-1]["result"] == "passed"
    assert runs[-1]["failed_gate"] is None

    archived_path = (
        project_root
        / "docs"
        / "spec"
        / "features_done"
        / feature_path.parent.name
        / "spec.yaml"
    )
    assert not feature_path.exists()
    assert archived_path.exists()

    feature = yaml.safe_load(archived_path.read_text(encoding="utf-8"))
    assert feature["status"] == "done"

    log = run_git(project_root, "log", "--oneline").stdout.strip().splitlines()
    assert len(log) >= 2


def test_archive_path_uses_configured_docs_root(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs.engineeringagent"
    feature_path = (
        docs_root / "spec" / "features" / "FEAT-910-configured-archive" / "spec.yaml"
    )
    feature = base_feature(status="backlog")
    feature["id"] = "FEAT-910"

    (tmp_path / "engineeringagent.toml").write_text(
        'docs-root = "docs.engineeringagent"\n',
        encoding="utf-8",
    )
    (tmp_path / "harness" / "gates.yaml").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "harness" / "gates.yaml").write_text(
        yaml.safe_dump({"profiles": {"loop_fast": []}, "gates": {}}, sort_keys=False),
        encoding="utf-8",
    )
    copy_canonical_prompts(tmp_path)
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding="utf-8")

    script_path = write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-configured-archive.py"
    )
    init_git_repo(tmp_path)

    def implement_effect() -> None:
        run_python_script(script_path, feature_path)

    with with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=tmp_path,
            feature_paths=[str(feature_path)],
            dry_run=False,
            max_iterations=5,
        )

    archived_path = (
        docs_root / "spec" / "features_done" / "FEAT-910-configured-archive" / "spec.yaml"
    )
    assert code == 0
    assert not feature_path.exists()
    assert archived_path.exists()


def test_run_loop_commit_ignores_runs_jsonl_when_gitignored(tmp_path: Path) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    script_path = write_set_done_script(tmp_path.parent / f"{tmp_path.name}-set-done.py")
    (project_root / ".gitignore").write_text(f"{RUNS_LOG_REF}\n", encoding="utf-8")
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
    assert (progress_root(project_root) / "runs" / "runs.jsonl").exists()
    status = run_git(project_root, "status", "--short").stdout
    assert RUNS_LOG_REF not in status


def test_run_loop_writes_per_feature_progress_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(presentation_module, "stdout_is_tty", lambda _stdout: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    script_path = write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-progress-log.py"
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
    feature_log_path = progress_root(project_root) / "features" / "FEAT-900" / "run.txt"
    assert feature_log_path.exists()
    log_text = feature_log_path.read_text(encoding="utf-8")
    assert "attempt=1" in log_text
    assert "feature_id=FEAT-900" in log_text
    assert "result=passed" in log_text
    assert "\x1b[" not in log_text

    handoff_path = progress_root(project_root) / "features" / "FEAT-900" / "handoff.md"
    assert handoff_path.exists()
    assert handoff_path.stat().st_size > 0


def test_run_loop_progress_logs_are_gitignored(tmp_path: Path) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    script_path = write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-progress-log-ignore.py"
    )
    (project_root / ".gitignore").write_text(
        f"{RUNS_LOG_REF}\n.engineeringagent/progress/features/*/run.txt\n",
        encoding="utf-8",
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
    assert (progress_root(project_root) / "features" / "FEAT-900" / "run.txt").exists()
    status = run_git(project_root, "status", "--short").stdout
    assert RUNS_LOG_REF not in status
    assert FEATURE_LOG_REF not in status


def test_run_loop_concise_mode_hides_raw_implement_and_gate_output(
    tmp_path: Path, capsys: Any
) -> None:
    implement_stdout_token = "IMPLEMENT_RAW_STDOUT_TOKEN"
    implement_stderr_token = "IMPLEMENT_RAW_STDERR_TOKEN"
    gate_stdout_token = "GATE_RAW_STDOUT_TOKEN"
    gate_stderr_token = "GATE_RAW_STDERR_TOKEN"

    gate_script = tmp_path.parent / f"{tmp_path.name}-emit-gate-output.py"
    gate_script.write_text(
        "\n".join(
            [
                "import sys",
                f"print({gate_stdout_token!r})",
                f"print({gate_stderr_token!r}, file=sys.stderr)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    gates_data = {
        "profiles": {"loop_fast": ["emit_gate_output"]},
        "gates": {"emit_gate_output": {"run": f'"{sys.executable}" "{gate_script}"'}},
    }
    project_root, feature_path = make_project_root(
        tmp_path,
        feature_data=base_feature(),
        gates_data=gates_data,
    )
    init_git_repo(project_root)

    def implement_effect() -> None:
        feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
        feature["status"] = "done"
        feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding="utf-8")

    with (
        with_opencode_implement_side_effect(implement_effect),
        with_opencode_implement_result(
            stdout=f"{implement_stdout_token}\n",
            stderr=f"{implement_stderr_token}\n",
        ),
    ):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            dry_run=False,
            max_iterations=5,
            verbose_output=False,
        )

    output = capsys.readouterr().out
    assert code == 0
    assert implement_stdout_token not in output
    assert gate_stdout_token not in output

    feature_log_path = progress_root(project_root) / "features" / "FEAT-900" / "run.txt"
    log_text = feature_log_path.read_text(encoding="utf-8")
    assert implement_stdout_token in log_text
    assert implement_stderr_token in log_text
    assert gate_stdout_token in log_text
    assert gate_stderr_token in log_text
    assert "command_timing phase=gates gate=emit_gate_output" in log_text


def test_run_loop_verbose_output_streams_raw_implement_and_gate_output(
    tmp_path: Path, capsys: Any
) -> None:
    implement_stdout_token = "IMPLEMENT_VERBOSE_STDOUT_TOKEN"
    implement_stderr_token = "IMPLEMENT_VERBOSE_STDERR_TOKEN"
    gate_stdout_token = "GATE_VERBOSE_STDOUT_TOKEN"
    gate_stderr_token = "GATE_VERBOSE_STDERR_TOKEN"

    gate_script = tmp_path.parent / f"{tmp_path.name}-emit-gate-verbose-output.py"
    gate_script.write_text(
        "\n".join(
            [
                "import sys",
                f"print({gate_stdout_token!r})",
                f"print({gate_stderr_token!r}, file=sys.stderr)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    gates_data = {
        "profiles": {"loop_fast": ["emit_gate_output"]},
        "gates": {"emit_gate_output": {"run": f'"{sys.executable}" "{gate_script}"'}},
    }
    project_root, feature_path = make_project_root(
        tmp_path,
        feature_data=base_feature(),
        gates_data=gates_data,
    )
    init_git_repo(project_root)

    def implement_effect() -> None:
        feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
        feature["status"] = "done"
        feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding="utf-8")

    with (
        with_opencode_implement_side_effect(implement_effect),
        with_opencode_implement_result(
            stdout=f"{implement_stdout_token}\n",
            stderr=f"{implement_stderr_token}\n",
        ),
    ):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            dry_run=False,
            max_iterations=5,
            verbose_output=True,
        )

    captured = capsys.readouterr()
    merged_output = captured.out + captured.err
    assert code == 0
    assert implement_stdout_token in merged_output
    assert implement_stderr_token in merged_output
    assert gate_stdout_token in merged_output
    assert gate_stderr_token in merged_output


def test_run_loop_plain_output_when_not_tty(
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    monkeypatch.setattr(presentation_module, "stdout_is_tty", lambda _stdout: False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    loop_module.print_summary(
        IterationSummaryInputs(
            feature_id="FEAT-900",
            result="passed",
            failed_gate=None,
            attempt=1,
            next_action="continue_same_feature",
        )
    )

    output = capsys.readouterr().out
    assert "\x1b[" not in output
    assert "Loop summary: result=passed" in output
    assert "next=continue_same_feature" in output


def test_run_loop_styled_output_when_tty(
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    monkeypatch.setattr(presentation_module, "stdout_is_tty", lambda _stdout: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    loop_module.print_summary(
        IterationSummaryInputs(
            feature_id="FEAT-900",
            result="passed",
            failed_gate=None,
            attempt=1,
            next_action="continue_same_feature",
        )
    )

    output = capsys.readouterr().out
    assert "\x1b[" in output
    assert "Loop summary: result=passed" in output
    assert "next=continue_same_feature" in output


def test_run_loop_no_color_env_does_not_disable_styling(
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    monkeypatch.setattr(presentation_module, "stdout_is_tty", lambda _stdout: True)
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "xterm-256color")

    loop_module.print_summary(
        IterationSummaryInputs(
            feature_id="FEAT-900",
            result="failed",
            failed_gate="spec_validate",
            attempt=1,
            next_action="retry_same_feature",
        )
    )

    output = capsys.readouterr().out
    assert "\x1b[" in output
    assert "Loop summary: result=failed" in output
    assert "Failed gate:" in output
    assert "spec_validate" in output


def test_run_loop_iteration_output_uses_emoji_contract(
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    monkeypatch.setattr(presentation_module, "stdout_is_tty", lambda _stdout: False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    loop_module.print_summary(
        IterationSummaryInputs(
            feature_id="FEAT-900",
            result="passed",
            failed_gate=None,
            attempt=1,
            next_action="continue_same_feature",
            selected_path="docs/spec/features/FEAT-900/spec.yaml",
            implement_step="opencode run --agent engineeringagent",
        )
    )
    loop_module.print_summary(
        IterationSummaryInputs(
            feature_id="FEAT-900",
            result="failed",
            failed_gate="spec_validate",
            attempt=2,
            next_action="retry_same_feature",
            selected_path="docs/spec/features/FEAT-900/spec.yaml",
            implement_step="opencode run --agent engineeringagent",
            log_path=FEATURE_LOG_REF,
        )
    )
    loop_module.print_summary(
        IterationSummaryInputs(
            feature_id="FEAT-900",
            result="passed",
            failed_gate=None,
            attempt=3,
            next_action="select_next_feature",
            selected_path="docs/spec/features/FEAT-900/spec.yaml",
            implement_step="opencode run --agent engineeringagent",
            archived_selection_path="docs/spec/features_done/FEAT-900/spec.yaml",
        )
    )

    output = capsys.readouterr().out
    assert "🔁 Iteration 1 · FEAT-900" in output
    assert "🎯 Selected: docs/spec/features/FEAT-900/spec.yaml" in output
    assert "🛠 Implement: opencode run --agent engineeringagent" in output
    assert "✅ Passed" in output
    assert "➡️ Next: continue_same_feature" in output
    assert "🔁 Iteration 2 · FEAT-900" in output
    assert "❌ Failed: gate=spec_validate" in output
    assert f"📄 Log: {FEATURE_LOG_REF}" in output
    assert "➡️ Next: retry_same_feature" in output
    assert "♻️ Selected archived counterpart:" in output
    assert "➡️ Next: select_next_feature" in output


def test_run_loop_passed_iteration_not_completed_records_continue_next_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    monkeypatch.setattr(presentation_module, "stdout_is_tty", lambda _stdout: False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    project_root, feature_path = make_project_root(
        tmp_path, feature_data=base_feature(status="backlog")
    )
    init_git_repo(project_root)

    with with_opencode_implement_result(returncode=0, stdout="ok\n", stderr=""):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            dry_run=False,
            max_iterations=1,
        )

    output = capsys.readouterr().out
    assert code == 1
    assert "Reached max iteration cap (1) before completion." in output
    assert "next=continue_same_feature" in output

    runs = read_runs(project_root)
    assert runs
    assert runs[-1]["result"] == "passed"
    assert runs[-1]["next_action"] == "continue_same_feature"


def test_run_loop_telemetry_includes_log_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(presentation_module, "stdout_is_tty", lambda _stdout: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    script_path = write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-log-path.py"
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
    runs = read_runs(project_root)
    assert runs
    assert runs[-1]["log_path"] == FEATURE_LOG_REF
    assert "\x1b[" not in (progress_root(project_root) / "runs" / "runs.jsonl").read_text(
        encoding="utf-8"
    )


def test_run_loop_failure_prints_detailed_log_pointer(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    init_git_repo(project_root)

    with with_opencode_implement_result(
        returncode=1, stdout="", stderr="opencode failed"
    ):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            dry_run=False,
            max_iterations=1,
        )

    output = capsys.readouterr().out
    assert code == 1
    assert "result=failed" in output
    assert f"Detailed log: {FEATURE_LOG_REF}" in output
