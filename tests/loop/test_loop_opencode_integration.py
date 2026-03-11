from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

import engineeringagent.loop as loop_module
from engineeringagent.agents import AgentBackendError, AgentBackendFailureDetails
from engineeringagent.checks.pytest.config import (
    resolve_harness_pytest_opencode_integration_enabled,
)
from engineeringagent.loop import (
    RunConfigOptions,
    build_loop_run,
    build_run_config,
)
from engineeringagent.bootstrap.runtime_execution import (
    run_loop_controller as _run_loop,
)
from engineeringagent.adapters.progress import paths as progress_paths
from engineeringagent.adapters.progress.handoff import ImplementProgressEnvelope
from engineeringagent.agents.backends.opencode.permissions import (
    PERMISSION_REMEDIATION_HINT,
    PermissionProbeResult,
    evaluate_permission_probe,
)
from tests.loop.feature_iteration_support import copy_canonical_prompts
from tests.loop._feedback_envelope import parse_feedback_envelope_from_prompt

pytestmark = pytest.mark.integration


def test_opencode_integration_gate_does_not_reference_env_var() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    forbidden = "ENGINEERINGAGENT_" + "OPENCODE_INTEGRATION"
    assert forbidden not in source


def run_loop(
    *,
    project_root: Path,
    feature_paths: list[str],
    dry_run: bool,
    run_all: bool = False,
    max_iterations: int = 50,
    allow_dirty: bool = False,
    verbose_output: bool = False,
) -> int:
    """Run loop controller through the canonical run-config pipeline."""
    config = build_run_config(
        project_root=project_root,
        feature_paths=feature_paths,
        options=RunConfigOptions(
            dry_run,
            run_all,
            max_iterations,
            allow_dirty,
            verbose_output,
        ),
    )
    return _run_loop(build_loop_run(config))


_SPARK_AGENT_MODEL = "openai/gpt-5.3-codex-spark"


def _progress_runs_jsonl_path(project_root: Path) -> Path:
    return progress_paths.runs_jsonl_path(project_root)


def _progress_runs_jsonl_reference(project_root: Path) -> str:
    return progress_paths.runs_jsonl_reference(project_root)


def _progress_feature_log_path(project_root: Path, feature_id: str) -> Path:
    return progress_paths.run_feature_log_path(project_root, feature_id)


def _progress_feature_log_template_reference(project_root: Path) -> str:
    return progress_paths.run_feature_log_template_reference(project_root)


def _build_test_agent_config(*, repo_root: Path, model: str) -> str:
    """Return an agent config identical to repo policy but with a pinned model."""
    policy_path = repo_root / ".opencode" / "agents" / "engineeringagent.md"
    policy_lines = policy_path.read_text(encoding="utf-8").splitlines()
    rendered: list[str] = []
    for line in policy_lines:
        if line.lstrip().startswith("model:"):
            rendered.append(f'model: "{model}"')
        else:
            rendered.append(line)
    return "\n".join(rendered).rstrip("\n") + "\n"


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
        / "FEAT-901-opencode-integration"
        / "spec.yaml"
    )

    _write_yaml(
        project_root / "harness" / "checks.yaml",
        {
            "contract_version": "1.0",
            "defaults": {"when": {"phase": "iteration_end"}},
            "checks": {},
        },
    )
    copy_canonical_prompts(project_root)
    _write_yaml(
        feature_path,
        {
            "id": "FEAT-901",
            "title": "OpenCode integration test",
            "type": "feature",
            "expected_commit_subject": "feat: validate opencode integration loop",
            "planning_tier": "direct",
            "status": "backlog",
            "priority": "high",
            "objective": "Verify loop can execute OpenCode from implement step.",
            "acceptance": ["Loop runs OpenCode successfully."],
            "artifacts": {},
            "updated_at": "2026-02-12T00:00:00Z",
        },
    )

    engineeringagent_path = (
        project_root / ".opencode" / "agents" / "engineeringagent.md"
    )
    engineeringagent_path.parent.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parents[2]
    engineeringagent_path.write_text(
        _build_test_agent_config(repo_root=repo_root, model=_SPARK_AGENT_MODEL),
        encoding="utf-8",
    )

    return project_root, feature_path


def test_opencode_integration_scaffold_writes_only_engineeringagent_agent_config(
    tmp_path: Path,
) -> None:
    project_root, _feature_path = _make_project_root(tmp_path)
    agent_path = project_root / ".opencode" / "agents" / "engineeringagent.md"
    assert agent_path.exists()
    assert not (project_root / ".opencode" / "agents" / "build.md").exists()
    legacy_repo_root_config = ".".join(["opencode", "json"])
    assert not (project_root / legacy_repo_root_config).exists()

    payload = agent_path.read_text(encoding="utf-8")
    model_lines = [
        line for line in payload.splitlines() if line.lstrip().startswith("model:")
    ]
    assert len(model_lines) == 1
    assert _SPARK_AGENT_MODEL in model_lines[0]


def _run_git(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=project_root, check=True, capture_output=True, text=True
    )


def _init_git_repo(project_root: Path) -> None:
    _run_git(project_root, "init")
    hooks_path = project_root / ".git" / "hooks-empty"
    hooks_path.mkdir(parents=True, exist_ok=True)
    _run_git(project_root, "config", "core.hooksPath", str(hooks_path))
    _run_git(project_root, "config", "commit.gpgsign", "false")
    _run_git(project_root, "config", "user.name", "test")
    _run_git(project_root, "config", "user.email", "test@example.com")
    _run_git(project_root, "add", "-A")
    _run_git(project_root, "commit", "-m", "init")


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


def test_loop_runs_opencode_integration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if not resolve_harness_pytest_opencode_integration_enabled(repo_root):
        pytest.skip(
            "set [harness.pytest].opencode-integration = true in engineeringagent.toml to run"
        )

    def fake_run_permission_probe(_: Path) -> PermissionProbeResult:
        return PermissionProbeResult(ok=True, reason="ok", returncode=0, output="")

    def fake_run_agent(*_: Any, **__: Any) -> str:
        return "PERMISSION_OK\n"

    monkeypatch.setattr(
        "engineeringagent.agents.helpers.run_permission_probe",
        fake_run_permission_probe,
    )
    monkeypatch.setattr(loop_module, "run_agent", fake_run_agent)

    project_root, feature_path = _make_project_root(tmp_path)
    _init_git_repo(project_root)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=1,
    )

    assert code in {0, 1}

    runs_path = _progress_runs_jsonl_path(project_root)
    run = json.loads(runs_path.read_text(encoding="utf-8").splitlines()[0])
    assert run["feature_id"] == "FEAT-901"
    assert run["result"] == "passed"
    assert run["failed_gate"] is None

    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    assert feature["status"] in {"in_progress", "done"}


def test_evaluate_permission_probe_detects_rejection_signal() -> None:
    result = evaluate_permission_probe(
        returncode=0,
        output=(
            "permission requested: bash git status --short (auto-reject)\nPERMISSION_OK"
        ),
    )

    assert result.ok is False
    assert "rejection" in result.reason


def test_loop_reports_permission_rejection_in_run_telemetry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, feature_path = _make_project_root(tmp_path)
    _init_git_repo(project_root)
    build_agent_path = project_root / ".opencode" / "agents" / "build.md"
    assert not build_agent_path.exists()

    precheck_calls: list[Path] = []

    def fake_run_agent(
        project_root: Path,
        prompt: str,
        *,
        output_type: type[Any],
    ) -> str:
        del project_root
        del prompt
        assert output_type is ImplementProgressEnvelope
        raise AgentBackendError(
            backend="opencode",
            message="opencode run failed",
            process=AgentBackendFailureDetails(
                returncode=1,
                stdout="",
                stderr=(
                    "permission requested for bash command git status --short "
                    "(auto-reject)"
                ),
            ),
        )

    def fake_run_permission_probe(target_root: Path) -> PermissionProbeResult:
        precheck_calls.append(target_root)
        return PermissionProbeResult(ok=True, reason="ok", returncode=0, output="")

    monkeypatch.setattr(
        "engineeringagent.agents.helpers.run_permission_probe",
        fake_run_permission_probe,
    )
    monkeypatch.setattr(loop_module, "run_agent", fake_run_agent)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=1,
    )

    assert code == 1
    runs_path = _progress_runs_jsonl_path(project_root)
    runs = runs_path.read_text(encoding="utf-8").splitlines()
    assert len(runs) == 1
    run = json.loads(runs[0])
    assert run["result"] == "failed"
    assert run["failed_gate"] == "opencode_permission"
    assert run["verification_status"] == "not_run"
    assert run["verification_failed_command"] is None
    assert run["next_action"] == "retry_same_feature"
    assert run["log_path"]
    assert precheck_calls == [project_root]
    assert not build_agent_path.exists()

    feature_log_path = project_root / str(run["log_path"])
    assert feature_log_path.exists()
    feature_log = feature_log_path.read_text(encoding="utf-8")
    assert "failed_gate=opencode_permission" in feature_log
    assert "permission requested for bash command git status --short" in feature_log


def test_run_loop_creates_progress_artifacts_before_implement_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, _feature_path = _make_project_root(tmp_path)
    _init_git_repo(project_root)

    def fake_run_permission_probe(_: Path) -> PermissionProbeResult:
        return PermissionProbeResult(ok=True, reason="ok", returncode=0, output="")

    observed: dict[str, bool] = {
        "saw_implement": False,
    }

    def fake_run_agent(
        project_root: Path,
        prompt: str,
        *,
        output_type: type[Any],
    ) -> str:
        del prompt
        assert output_type is ImplementProgressEnvelope
        observed["saw_implement"] = True
        assert progress_paths.progress_dir(project_root).exists()
        assert _progress_runs_jsonl_path(project_root).exists()
        raise AgentBackendError(
            backend="opencode",
            message="opencode run failed",
            process=AgentBackendFailureDetails(
                returncode=1,
                stdout="",
                stderr="opencode failed",
            ),
        )

    monkeypatch.setattr(
        "engineeringagent.agents.helpers.run_permission_probe",
        fake_run_permission_probe,
    )
    monkeypatch.setattr(loop_module, "run_agent", fake_run_agent)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(_feature_path)],
        dry_run=False,
        max_iterations=1,
    )

    assert observed["saw_implement"] is True
    assert code == 1


def test_run_loop_permission_precheck_applies_only_to_default_implement_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, feature_path = _make_project_root(tmp_path)
    _init_git_repo(project_root)

    precheck_calls: list[Path] = []

    def fake_run_permission_probe(target_root: Path) -> PermissionProbeResult:
        precheck_calls.append(target_root)
        return PermissionProbeResult(
            ok=False,
            reason="permission request rejection detected in opencode output",
            returncode=1,
            output="permission requested for bash command git status --short (auto-reject)",
        )

    monkeypatch.setattr(
        "engineeringagent.agents.helpers.run_permission_probe",
        fake_run_permission_probe,
    )

    default_mode_code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=1,
    )

    assert default_mode_code == 1
    assert precheck_calls == [project_root]


def test_run_loop_exits_before_selection_when_permission_precheck_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, feature_path = _make_project_root(tmp_path)
    _init_git_repo(project_root)

    def fake_run_permission_probe(_: Path) -> PermissionProbeResult:
        return PermissionProbeResult(
            ok=False,
            reason="permission request rejection detected in opencode output",
            returncode=1,
            output="permission requested for bash command git status --short (auto-reject)",
        )

    monkeypatch.setattr(
        "engineeringagent.agents.helpers.run_permission_probe",
        fake_run_permission_probe,
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=1,
    )

    output = capsys.readouterr().out

    assert code == 1
    assert not _progress_runs_jsonl_path(project_root).exists()
    assert "Precondition failed: OpenCode permission precheck failed" in output
    assert "git status --short" in output
    assert PERMISSION_REMEDIATION_HINT in output
    assert "Selected feature=" not in output
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    assert feature["status"] == "backlog"


def test_run_loop_skips_permission_precheck_in_dry_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, feature_path = _make_project_root(tmp_path)
    _init_git_repo(project_root)

    precheck_called = False

    def fail_if_prechecked(_: Path) -> PermissionProbeResult:
        nonlocal precheck_called
        precheck_called = True
        raise AssertionError("permission precheck should be skipped")

    monkeypatch.setattr(
        "engineeringagent.agents.helpers.run_permission_probe", fail_if_prechecked
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=True,
        max_iterations=1,
    )

    assert code == 0
    assert precheck_called is False
    assert not _progress_runs_jsonl_path(project_root).exists()


def test_run_loop_permission_precheck_failure_prints_remediation_hint(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, feature_path = _make_project_root(tmp_path)
    _init_git_repo(project_root)
    build_agent_path = project_root / ".opencode" / "agents" / "build.md"
    assert not build_agent_path.exists()

    def fake_run_permission_probe(_: Path) -> PermissionProbeResult:
        return PermissionProbeResult(
            ok=False,
            reason="opencode exited with status 127",
            returncode=127,
            output="",
        )

    monkeypatch.setattr(
        "engineeringagent.agents.helpers.run_permission_probe",
        fake_run_permission_probe,
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=1,
    )

    output = capsys.readouterr().out

    assert code == 1
    assert "Precondition failed: OpenCode permission precheck failed" in output
    assert "opencode exited with status 127" in output
    assert PERMISSION_REMEDIATION_HINT in output
    assert ".opencode/agents/engineeringagent.md" in output
    assert ".opencode/agents/build.md" not in output
    assert "--implement-command" not in output
    assert "engineeringagent run --dry-run" in output
    assert not build_agent_path.exists()


def test_run_loop_permission_precheck_pass_prints_bypass_hint_and_log_locations(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, feature_path = _make_project_root(tmp_path)
    _init_git_repo(project_root)

    def fake_run_permission_probe(_: Path) -> PermissionProbeResult:
        return PermissionProbeResult(
            ok=True,
            reason="ok",
            returncode=0,
            output="PERMISSION_OK\n",
        )

    def fake_run_agent(*_: Any, **__: Any) -> str:
        raise AgentBackendError(
            backend="opencode",
            message="opencode run failed",
            process=AgentBackendFailureDetails(
                returncode=1,
                stdout="",
                stderr="opencode failed",
            ),
        )

    monkeypatch.setattr(
        "engineeringagent.agents.helpers.run_permission_probe",
        fake_run_permission_probe,
    )
    monkeypatch.setattr(loop_module, "run_agent", fake_run_agent)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=1,
    )

    output = capsys.readouterr().out

    assert code == 1
    assert "Running pre-run OpenCode permission precheck" in output
    assert "default implement mode" not in output
    assert "--implement-command" not in output
    assert "engineeringagent run --dry-run" in output
    assert _progress_runs_jsonl_reference(project_root) in output
    assert _progress_feature_log_template_reference(project_root) in output


def test_gate_failure_feedback_round_trips_to_retry_prompt_integration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, feature_path = _make_project_root(tmp_path)
    _init_git_repo(project_root)

    gate_counter_path = project_root / ".spec-validate-gate-attempt"
    gate_script = tmp_path.parent / f"{tmp_path.name}-gate-fail-once.py"
    gate_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                f"counter_path = Path({str(gate_counter_path)!r})",
                "count = int(counter_path.read_text(encoding='utf-8')) if counter_path.exists() else 0",
                "count += 1",
                "counter_path.write_text(str(count), encoding='utf-8')",
                "if count == 1:",
                "    print('SPEC_VALIDATE_INTEGRATION_TOKEN')",
                "    raise SystemExit(1)",
                "print('spec_validate passed')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_yaml(
        project_root / "harness" / "checks.yaml",
        {
            "contract_version": "1.0",
            "defaults": {"when": {"phase": "iteration_end"}},
            "checks": {
                "spec_validate": {
                    "type": "command",
                    "command": f'"{sys.executable}" "{gate_script}"',
                }
            },
        },
    )

    prompts: list[str] = []
    set_done_script = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-opencode-integration.py"
    )

    def fake_start_agent(
        project_root: Path,
        prompt: str,
        *,
        output_type: type[Any],
        agent: str = "build",
        capture_output: bool = True,
        text: bool = True,
    ) -> str:
        del project_root, agent, capture_output, text
        assert output_type is ImplementProgressEnvelope
        prompts.append(prompt)
        subprocess.run(
            [sys.executable, str(set_done_script), str(feature_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return "ok\n"

    def fake_run_permission_probe(_: Path) -> PermissionProbeResult:
        return PermissionProbeResult(ok=True, reason="ok", returncode=0, output="")

    monkeypatch.setattr(loop_module, "run_agent", fake_start_agent)
    monkeypatch.setattr(
        "engineeringagent.agents.helpers.run_permission_probe",
        fake_run_permission_probe,
    )
    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        allow_dirty=True,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 2
    feedback = parse_feedback_envelope_from_prompt(prompts[1], phase="gates")
    assert feedback.kind == "command_failure"
    assert feedback.phase == "gates"
    assert feedback.command == f'"{sys.executable}" "{gate_script}"'
    assert "SPEC_VALIDATE_INTEGRATION_TOKEN" in feedback.message


def test_gate_failure_feedback_replaces_previous_feedback_integration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, feature_path = _make_project_root(tmp_path)
    _init_git_repo(project_root)

    first_counter_path = project_root / ".first-spec-validate-attempt"
    second_counter_path = project_root / ".second-spec-validate-attempt"
    first_gate_script = tmp_path.parent / f"{tmp_path.name}-gate-fail-once-first.py"
    first_gate_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                f"counter_path = Path({str(first_counter_path)!r})",
                "count = int(counter_path.read_text(encoding='utf-8')) if counter_path.exists() else 0",
                "count += 1",
                "counter_path.write_text(str(count), encoding='utf-8')",
                "if count == 1:",
                "    print('OPENCODE_FIRST_GATE_OUTPUT_TOKEN')",
                "    raise SystemExit(1)",
                "print('ok')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    second_gate_script = tmp_path.parent / f"{tmp_path.name}-gate-fail-once-second.py"
    second_gate_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                f"counter_path = Path({str(second_counter_path)!r})",
                "count = int(counter_path.read_text(encoding='utf-8')) if counter_path.exists() else 0",
                "count += 1",
                "counter_path.write_text(str(count), encoding='utf-8')",
                "if count == 1:",
                "    print('OPENCODE_SECOND_GATE_OUTPUT_TOKEN')",
                "    raise SystemExit(1)",
                "print('ok')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_yaml(
        project_root / "harness" / "checks.yaml",
        {
            "contract_version": "1.0",
            "defaults": {"when": {"phase": "iteration_end"}},
            "checks": {
                "spec_validate": {
                    "type": "command",
                    "command": f'"{sys.executable}" "{first_gate_script}"',
                }
            },
        },
    )

    prompts: list[str] = []
    set_done_script = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-opencode-feedback-replace.py"
    )

    def fake_start_agent(
        project_root: Path,
        prompt: str,
        *,
        output_type: type[Any],
        agent: str = "build",
        capture_output: bool = True,
        text: bool = True,
    ) -> str:
        del project_root, agent, capture_output, text
        assert output_type is ImplementProgressEnvelope
        prompts.append(prompt)
        if len(prompts) == 2:
            _write_yaml(
                tmp_path / "harness" / "checks.yaml",
                {
                    "contract_version": "1.0",
                    "defaults": {"when": {"phase": "iteration_end"}},
                    "checks": {
                        "spec_validate": {
                            "type": "command",
                            "command": f'"{sys.executable}" "{second_gate_script}"',
                        }
                    },
                },
            )
        if len(prompts) >= 3:
            subprocess.run(
                [sys.executable, str(set_done_script), str(feature_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        return "ok\n"

    def fake_run_permission_probe(_: Path) -> PermissionProbeResult:
        return PermissionProbeResult(ok=True, reason="ok", returncode=0, output="")

    monkeypatch.setattr(loop_module, "run_agent", fake_start_agent)
    monkeypatch.setattr(
        "engineeringagent.agents.helpers.run_permission_probe",
        fake_run_permission_probe,
    )

    first_output = "OPENCODE_FIRST_GATE_OUTPUT_TOKEN"
    second_output = "OPENCODE_SECOND_GATE_OUTPUT_TOKEN"

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        allow_dirty=True,
        max_iterations=8,
    )

    assert code == 0
    assert len(prompts) >= 3
    first_feedback = parse_feedback_envelope_from_prompt(prompts[1], phase="gates")
    second_feedback = parse_feedback_envelope_from_prompt(prompts[2], phase="gates")
    assert first_feedback.kind == "command_failure"
    assert first_feedback.phase == "gates"
    assert first_feedback.command == f'"{sys.executable}" "{first_gate_script}"'
    assert first_output in first_feedback.message
    assert second_feedback.kind == "command_failure"
    assert second_feedback.phase == "gates"
    assert second_feedback.command == f'"{sys.executable}" "{second_gate_script}"'
    assert second_output in second_feedback.message
    assert second_output not in first_feedback.message
    assert first_output not in second_feedback.message
    assert second_output in second_feedback.message


def test_loop_archived_done_continues_run_all_when_selected_path_disappears(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for git_env_key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(git_env_key, raising=False)

    project_root, feature_path = _make_project_root(tmp_path)
    second_feature_path = (
        project_root / "docs" / "spec" / "features" / "FEAT-902-follow-on" / "spec.yaml"
    )
    _write_yaml(
        second_feature_path,
        {
            "id": "FEAT-902",
            "title": "Follow-on feature",
            "type": "feature",
            "expected_commit_subject": "feat: complete follow-on feature",
            "planning_tier": "direct",
            "status": "backlog",
            "priority": "high",
            "objective": "Should run after selected feature archival recovery.",
            "acceptance": ["Loop continues to next selected feature."],
            "artifacts": {},
            "updated_at": "2026-02-12T00:00:00Z",
        },
    )
    _init_git_repo(project_root)
    starting_head = _run_git(project_root, "rev-parse", "HEAD").stdout.strip()
    script_path = tmp_path.parent / f"{tmp_path.name}-archive-done-then-complete.py"
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "import yaml",
                "project_root = Path(sys.argv[1])",
                "active_dir = project_root / 'docs' / 'spec' / 'features'",
                "done_dir = project_root / 'docs' / 'spec' / 'features_done'",
                "first_path = active_dir / 'FEAT-901-opencode-integration' / 'spec.yaml'",
                "second_path = active_dir / 'FEAT-902-follow-on' / 'spec.yaml'",
                "if first_path.exists():",
                "    feature = yaml.safe_load(first_path.read_text(encoding='utf-8'))",
                "    feature['status'] = 'done'",
                "    archived_path = done_dir / first_path.parent.name / 'spec.yaml'",
                "    archived_path.parent.mkdir(parents=True, exist_ok=True)",
                "    archived_path.write_text(",
                "        yaml.safe_dump(feature, sort_keys=False),",
                "        encoding='utf-8',",
                "    )",
                "    first_path.unlink()",
                "    raise SystemExit(0)",
                "if second_path.exists():",
                "    feature = yaml.safe_load(second_path.read_text(encoding='utf-8'))",
                "    feature['status'] = 'done'",
                "    second_path.write_text(",
                "        yaml.safe_dump(feature, sort_keys=False),",
                "        encoding='utf-8',",
                "    )",
                "    raise SystemExit(0)",
                "raise SystemExit(1)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_run_permission_probe(_: Path) -> PermissionProbeResult:
        return PermissionProbeResult(ok=True, reason="ok", returncode=0, output="")

    def fake_run_agent(
        project_root: Path,
        prompt: str,
        *,
        output_type: type[Any] | None = None,
    ) -> str:
        if "Choose the next feature spec to execute" in prompt:
            return str(feature_path)

        assert output_type is ImplementProgressEnvelope
        subprocess.run(
            [sys.executable, str(script_path), str(project_root)],
            check=True,
            capture_output=True,
            text=True,
        )
        return "ok\n"

    monkeypatch.setattr(
        "engineeringagent.agents.helpers.run_permission_probe",
        fake_run_permission_probe,
    )
    monkeypatch.setattr(loop_module, "run_agent", fake_run_agent)

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        dry_run=False,
        run_all=True,
        max_iterations=4,
    )

    assert code == 0
    runs = [
        json.loads(line)
        for line in _progress_runs_jsonl_path(project_root).read_text(encoding="utf-8").splitlines()
    ]
    assert len(runs) == 2
    assert runs[0]["feature_id"] == "FEAT-901"
    assert runs[0]["result"] == "passed"
    assert runs[0]["failed_gate"] is None
    assert runs[0]["next_action"] == "select_next_feature"
    assert runs[1]["feature_id"] == "FEAT-902"
    assert runs[1]["result"] == "passed"

    archived_selected = (
        project_root
        / "docs"
        / "spec"
        / "features_done"
        / feature_path.parent.name
        / "spec.yaml"
    )
    archived_follow_on = (
        project_root
        / "docs"
        / "spec"
        / "features_done"
        / second_feature_path.parent.name
        / "spec.yaml"
    )
    assert not feature_path.exists()
    assert archived_selected.exists()
    assert not second_feature_path.exists()
    assert archived_follow_on.exists()

    ending_head = _run_git(project_root, "rev-parse", "HEAD").stdout.strip()
    assert ending_head != starting_head
