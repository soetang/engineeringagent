from __future__ import annotations

import json
import subprocess
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

import engineeringagent.loop as loop_module
from engineeringagent.loop import run_loop
from engineeringagent.opencode_permissions import evaluate_permission_probe


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _make_project_root(tmp_path: Path) -> tuple[Path, Path]:
    project_root = tmp_path
    feature_path = (
        project_root
        / "docs"
        / "spec"
        / "features"
        / "FEAT-901-opencode-integration.yaml"
    )

    _write_yaml(
        project_root / "harness" / "gates.yaml",
        {
            "profiles": {"loop_fast": []},
            "gates": {},
        },
    )
    _write_yaml(
        feature_path,
        {
            "id": "FEAT-901",
            "title": "OpenCode integration test",
            "type": "feature",
            "expected_commit_subject": "feat: validate opencode integration loop",
            "status": "backlog",
            "priority": "high",
            "objective": "Verify loop can execute OpenCode from implement step.",
            "acceptance": ["Loop runs OpenCode successfully."],
            "updated_at": "2026-02-12T00:00:00Z",
        },
    )
    (project_root / "opencode.json").write_text(
        json.dumps(
            {
                "$schema": "https://opencode.ai/config.json",
                "model": "openai/gpt-5.1-codex-mini",
                "default_agent": "build",
                "agent": {
                    "build": {
                        "mode": "primary",
                        "model": "openai/gpt-5.1-codex-mini",
                    }
                },
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return project_root, feature_path


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


def _move_feature_to_done(project_root: Path, feature_path: Path) -> None:
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    feature["status"] = "done"
    done_path = project_root / "docs" / "spec" / "features_done" / feature_path.name
    done_path.parent.mkdir(parents=True, exist_ok=True)
    done_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding="utf-8")
    feature_path.unlink()


@pytest.mark.integration
def test_loop_runs_opencode_integration(tmp_path: Path) -> None:
    if shutil.which("opencode") is None:
        pytest.skip("opencode CLI not found in PATH")

    project_root, feature_path = _make_project_root(tmp_path)
    _init_git_repo(project_root)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt="Reply READY.",
        skip_implement=False,
        dry_run=False,
        max_iterations=1,
    )

    assert code == 1

    runs_path = project_root / "progress" / "runs.jsonl"
    run = json.loads(runs_path.read_text(encoding="utf-8").splitlines()[0])
    assert run["feature_id"] == "FEAT-901"
    assert run["result"] in {"passed", "failed"}
    assert run["failed_gate"] is None

    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    assert feature["status"] in {"in_progress", "done"}


def test_evaluate_permission_probe_detects_rejection_signal() -> None:
    result = evaluate_permission_probe(
        returncode=0,
        output="permission requested: bash git status --short (auto-reject)",
    )

    assert result.ok is False
    assert "rejection" in result.reason


def test_loop_reports_permission_rejection_in_run_telemetry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, _ = _make_project_root(tmp_path)
    _init_git_repo(project_root)

    def fake_subprocess_run(command: Any, **_: Any) -> subprocess.CompletedProcess[str]:
        if command == ["git", "status", "--porcelain"]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command == ["git", "rev-parse", "--short", "HEAD"]:
            return subprocess.CompletedProcess(command, 0, stdout="abc123\n", stderr="")
        if isinstance(command, list) and command[:3] == ["opencode", "run", "--agent"]:
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="",
                stderr="permission requested for bash command git status --short (auto-reject)",
            )
        raise AssertionError(f"unexpected subprocess.run call: {command}")

    monkeypatch.setattr(loop_module, "run_process", fake_subprocess_run)

    code = run_loop(
        project_root=project_root,
        feature_paths=[
            str(
                project_root
                / "docs"
                / "spec"
                / "features"
                / "FEAT-901-opencode-integration.yaml"
            )
        ],
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt="Run exactly: git status --short.",
        skip_implement=False,
        dry_run=False,
        max_iterations=1,
    )

    assert code == 1
    runs_path = project_root / "progress" / "runs.jsonl"
    run = json.loads(runs_path.read_text(encoding="utf-8").splitlines()[0])
    assert run["result"] == "failed"
    assert run["failed_gate"] == "opencode_permission"


def test_loop_archived_done_requires_same_iteration_completion_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, feature_path = _make_project_root(tmp_path)
    second_feature_path = (
        project_root / "docs" / "spec" / "features" / "FEAT-902-follow-on.yaml"
    )
    _write_yaml(
        second_feature_path,
        {
            "id": "FEAT-902",
            "title": "Follow-on feature",
            "type": "feature",
            "status": "backlog",
            "priority": "high",
            "objective": "Should not run when selected feature fails.",
            "acceptance": ["Loop must stop before selecting next feature."],
            "updated_at": "2026-02-12T00:00:00Z",
        },
    )
    _init_git_repo(project_root)
    starting_head = _run_git(project_root, "rev-parse", "HEAD").stdout.strip()

    def fake_run_implement_step(
        project_root: Path,
        feature: dict[str, Any],
        feature_path: Path,
        implement_command: str | None,
        opencode_prompt: str | None,
        skip_implement: bool,
        hook_feedback: str | None,
        verbose_output: bool,
    ) -> tuple[bool, str | None, str]:
        del implement_command, opencode_prompt, skip_implement, hook_feedback
        del verbose_output
        feature_id = str(feature.get("id", ""))
        if feature_id == "FEAT-901":
            _move_feature_to_done(project_root, feature_path)
            return (True, None, "")
        if feature_id == "FEAT-902":
            feature_payload = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
            feature_payload["status"] = "done"
            feature_path.write_text(
                yaml.safe_dump(feature_payload, sort_keys=False), encoding="utf-8"
            )
            return (True, None, "")
        raise AssertionError(f"unexpected feature selected: {feature_id}")

    monkeypatch.setattr(loop_module, "run_implement_step", fake_run_implement_step)

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt=None,
        skip_implement=False,
        dry_run=False,
        run_all=True,
        max_iterations=4,
    )

    assert code == 0
    runs = [
        json.loads(line)
        for line in (project_root / "progress" / "runs.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [run["feature_id"] for run in runs[:2]] == ["FEAT-901", "FEAT-902"]
    assert all(run["result"] == "passed" for run in runs[:2])

    archived_selected = (
        project_root / "docs" / "spec" / "features_done" / feature_path.name
    )
    assert not feature_path.exists()
    assert archived_selected.exists()
    archived_follow_on = (
        project_root / "docs" / "spec" / "features_done" / second_feature_path.name
    )
    assert not second_feature_path.exists()
    assert archived_follow_on.exists()

    ending_head = _run_git(project_root, "rev-parse", "HEAD").stdout.strip()
    assert ending_head != starting_head
