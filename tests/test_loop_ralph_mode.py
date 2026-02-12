from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

import engineeringagent.loop as loop_module
from engineeringagent.cli import build_parser
from engineeringagent.loop import build_ralph_opencode_prompt, run_loop


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _base_feature(status: str = "backlog") -> dict[str, Any]:
    return {
        "id": "FEAT-900",
        "title": "Ralph mode smoke test",
        "status": status,
        "priority": "high",
        "objective": "Verify feature-level loop mode does not require subtask selection.",
        "acceptance": ["Ralph mode runs as a feature-level unit."],
        "updated_at": "2026-02-12T00:00:00Z",
    }


def _make_project_root(
    tmp_path: Path,
    feature_data: dict[str, Any],
    gates_data: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    project_root = tmp_path
    feature_path = (
        project_root / "docs" / "spec" / "features" / "FEAT-900-ralph-test.yaml"
    )

    if gates_data is None:
        gates_data = {
            "profiles": {"loop_fast": []},
            "gates": {},
        }

    _write_yaml(project_root / "harness" / "gates.yaml", gates_data)
    _write_yaml(feature_path, feature_data)
    return project_root, feature_path


def _read_runs(project_root: Path) -> list[dict[str, Any]]:
    runs_path = project_root / "progress" / "runs.jsonl"
    return [
        json.loads(line) for line in runs_path.read_text(encoding="utf-8").splitlines()
    ]


def _run_git(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=project_root, check=True, capture_output=True, text=True
    )


def _init_git_repo(project_root: Path) -> None:
    _run_git(project_root, "init")
    _run_git(project_root, "add", "-A")
    _run_git(
        project_root,
        "-c",
        "user.name=test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "init",
    )


def _write_set_done_script(script_path: Path) -> Path:
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "import yaml",
                "feature_path = Path(sys.argv[1])",
                "feature = yaml.safe_load(feature_path.read_text(encoding='utf-8'))",
                "feature['status'] = 'done'",
                "feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script_path


def test_ralph_prompt_includes_feature_file_path(tmp_path: Path) -> None:
    _, feature_path = _make_project_root(tmp_path, feature_data=_base_feature())
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    prompt = build_ralph_opencode_prompt(feature=feature, feature_path=feature_path)

    assert str(feature_path) in prompt
    assert "Read and use this feature spec from disk" in prompt


def test_cli_run_dry_run_skip_implement_path_first(tmp_path: Path, capsys: Any) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )

    parser = build_parser()
    args = parser.parse_args(
        [
            "--project-root",
            str(project_root),
            "run",
            str(feature_path),
            "--dry-run",
            "--skip-implement",
        ]
    )

    code = args.func(args)
    output = capsys.readouterr().out

    assert code == 0
    assert "result=dry_run" in output
    assert not (project_root / "progress" / "runs.jsonl").exists()


def test_cli_run_all_dry_run_skip_implement(tmp_path: Path, capsys: Any) -> None:
    project_root, _ = _make_project_root(tmp_path, feature_data=_base_feature())

    parser = build_parser()
    args = parser.parse_args(
        [
            "--project-root",
            str(project_root),
            "run",
            "--all",
            "--dry-run",
            "--skip-implement",
        ]
    )

    code = args.func(args)
    output = capsys.readouterr().out

    assert code == 0
    assert "result=dry_run" in output


def test_cli_run_rejects_combined_all_and_paths(tmp_path: Path, capsys: Any) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )

    parser = build_parser()
    args = parser.parse_args(
        [
            "--project-root",
            str(project_root),
            "run",
            "--all",
            str(feature_path),
            "--dry-run",
            "--skip-implement",
        ]
    )

    code = args.func(args)
    output = capsys.readouterr().out

    assert code == 1
    assert "cannot be used with --all" in output


def test_cli_run_requires_paths_or_all(tmp_path: Path, capsys: Any) -> None:
    project_root, _ = _make_project_root(tmp_path, feature_data=_base_feature())

    parser = build_parser()
    args = parser.parse_args(
        [
            "--project-root",
            str(project_root),
            "run",
            "--dry-run",
            "--skip-implement",
        ]
    )

    code = args.func(args)
    output = capsys.readouterr().out

    assert code == 1
    assert "provide one or more feature paths, or use --all" in output


def test_run_loop_all_discovers_backlog_and_in_progress_only(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, _ = _make_project_root(tmp_path, feature_data=_base_feature())
    features_dir = project_root / "docs" / "spec" / "features"

    backlog_feature = _base_feature(status="backlog")
    backlog_feature["id"] = "FEAT-901"
    _write_yaml(features_dir / "FEAT-901-backlog.yaml", backlog_feature)

    in_progress_feature = _base_feature(status="in_progress")
    in_progress_feature["id"] = "FEAT-902"
    _write_yaml(features_dir / "FEAT-902-in-progress.yaml", in_progress_feature)

    blocked_feature = _base_feature(status="blocked")
    blocked_feature["id"] = "FEAT-903"
    _write_yaml(features_dir / "FEAT-903-blocked.yaml", blocked_feature)

    done_feature = _base_feature(status="done")
    done_feature["id"] = "FEAT-904"
    _write_yaml(features_dir / "FEAT-904-done.yaml", done_feature)

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt=None,
        skip_implement=True,
        dry_run=True,
        run_all=True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "[dry-run] Resolved 3 feature file(s)." in output
    assert "feature=FEAT-902" in output
    assert "FEAT-903" not in output
    assert "FEAT-904" not in output


def test_run_loop_all_excludes_blocked_and_done_from_startup_snapshot(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, _ = _make_project_root(
        tmp_path, feature_data=_base_feature(status="done")
    )
    features_dir = project_root / "docs" / "spec" / "features"

    blocked_feature = _base_feature(status="blocked")
    blocked_feature["id"] = "FEAT-903"
    _write_yaml(features_dir / "FEAT-903-blocked.yaml", blocked_feature)

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt=None,
        skip_implement=True,
        dry_run=True,
        run_all=True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "No runnable active features found for --all startup snapshot" in output


def test_run_loop_all_exits_zero_when_no_runnable_features(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, _ = _make_project_root(
        tmp_path, feature_data=_base_feature(status="blocked")
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt=None,
        skip_implement=True,
        dry_run=False,
        run_all=True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "No runnable active features found for --all startup snapshot" in output
    assert "result=no_work" in output


def test_run_loop_all_does_not_include_specs_created_after_startup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    features_dir = project_root / "docs" / "spec" / "features"

    selected_feature_ids: list[str] = []

    def fake_require_clean_worktree(_project_root: Path) -> tuple[bool, str]:
        return (True, "")

    def fake_choose_feature_with_selector(
        _project_root: Path,
        pending: list[tuple[Path, dict[str, Any]]],
    ) -> tuple[Path, dict[str, Any]]:
        chosen_path, chosen_feature = pending[0]
        selected_feature_ids.append(str(chosen_feature.get("id", "")))
        return chosen_path, chosen_feature

    def fake_run_feature_iteration(
        project_root: Path,
        feature_path: Path,
        gate_profile: str,
        implement_command: str | None,
        opencode_prompt: str | None,
        skip_implement: bool,
        attempt: int,
        hook_feedback: str | None,
    ) -> loop_module.IterationOutcome:
        del project_root, gate_profile, implement_command, opencode_prompt
        del skip_implement, attempt, hook_feedback

        created = _base_feature(status="backlog")
        created["id"] = "FEAT-999"
        _write_yaml(features_dir / "FEAT-999-created-after-startup.yaml", created)

        feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
        feature["status"] = "done"
        _write_yaml(feature_path, feature)

        return loop_module.IterationOutcome(
            completed=True,
            result="passed",
            failed_gate=None,
            next_action="select_next_feature",
            hook_feedback=None,
        )

    monkeypatch.setattr(
        loop_module, "_require_clean_worktree", fake_require_clean_worktree
    )
    monkeypatch.setattr(
        loop_module,
        "_choose_feature_with_selector",
        fake_choose_feature_with_selector,
    )
    monkeypatch.setattr(
        loop_module, "_run_feature_iteration", fake_run_feature_iteration
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt=None,
        skip_implement=True,
        dry_run=False,
        run_all=True,
    )

    assert code == 0
    assert selected_feature_ids == ["FEAT-900"]
    assert feature_path.exists()


def test_run_loop_all_dry_run_reports_snapshot_selection(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, _ = _make_project_root(tmp_path, feature_data=_base_feature())

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt=None,
        skip_implement=True,
        dry_run=True,
        run_all=True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "Startup snapshot captured" in output
    assert "Selection is taken from the startup snapshot" in output


def test_run_loop_completes_feature_and_commits(tmp_path: Path) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    script_path = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done.py"
    )
    _init_git_repo(project_root)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        implement_command=f'"{sys.executable}" "{script_path}" "{feature_path}"',
        opencode_prompt=None,
        skip_implement=False,
        dry_run=False,
        max_iterations=5,
    )

    assert code == 0
    runs = _read_runs(project_root)
    assert len(runs) >= 1
    assert runs[-1]["feature_id"] == "FEAT-900"
    assert runs[-1]["result"] == "passed"
    assert runs[-1]["failed_gate"] is None

    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    assert feature["status"] == "done"

    log = _run_git(project_root, "log", "--oneline").stdout.strip().splitlines()
    assert len(log) >= 2


def test_run_loop_commit_ignores_runs_jsonl_when_gitignored(tmp_path: Path) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    script_path = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done.py"
    )
    (project_root / ".gitignore").write_text("progress/runs.jsonl\n", encoding="utf-8")
    _init_git_repo(project_root)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        implement_command=f'"{sys.executable}" "{script_path}" "{feature_path}"',
        opencode_prompt=None,
        skip_implement=False,
        dry_run=False,
        max_iterations=5,
    )

    assert code == 0
    assert (project_root / "progress" / "runs.jsonl").exists()
    status = _run_git(project_root, "status", "--short").stdout
    assert "progress/runs.jsonl" not in status


def test_run_loop_requires_clean_worktree(tmp_path: Path, capsys: Any) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    _init_git_repo(project_root)

    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    feature["context"] = "dirty change"
    _write_yaml(feature_path, feature)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt=None,
        skip_implement=True,
        dry_run=False,
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "Precondition failed" in output


def test_commit_failure_retries_same_feature(tmp_path: Path) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    script_path = tmp_path.parent / f"{tmp_path.name}-set-done-allow.py"
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
    _init_git_repo(project_root)

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

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        implement_command=f'"{sys.executable}" "{script_path}" "{project_root}" "{feature_path}"',
        opencode_prompt=None,
        skip_implement=False,
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    runs = _read_runs(project_root)
    assert len(runs) >= 2
    assert runs[0]["failed_gate"] == "git_commit"
    assert runs[-1]["result"] == "passed"


def test_cli_legacy_loop_command_removed() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["loop", "run", "--feature-id", "FEAT-900"])


def test_run_loop_reports_invalid_feature_path(tmp_path: Path, capsys: Any) -> None:
    project_root, _ = _make_project_root(tmp_path, feature_data=_base_feature())
    _init_git_repo(project_root)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(project_root / "missing.yaml")],
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt=None,
        skip_implement=True,
        dry_run=False,
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "does not exist" in output


def test_commit_failure_feedback_is_injected_into_next_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    _init_git_repo(project_root)

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

    real_run = subprocess.run
    prompts: list[str] = []

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if isinstance(command, list) and command[:3] == ["opencode", "run", "--agent"]:
            prompt = command[4]
            prompts.append(prompt)

            feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
            feature["status"] = "done"
            feature_path.write_text(
                yaml.safe_dump(feature, sort_keys=False), encoding="utf-8"
            )

            if len(prompts) >= 2:
                (project_root / ".allow_commit").write_text("ok\n", encoding="utf-8")

            return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

        return real_run(command, **kwargs)

    monkeypatch.setattr(loop_module.subprocess, "run", fake_subprocess_run)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt=None,
        skip_implement=False,
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 2
    assert "Previous commit or pre-commit hooks failed" in prompts[1]
    assert "hook blocked" in prompts[1]
