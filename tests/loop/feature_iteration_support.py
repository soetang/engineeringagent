from __future__ import annotations

import json
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterator

import pytest
import yaml
from typer.testing import CliRunner

import engineeringagent.agents.helpers as agent_helpers
from engineeringagent.bootstrap import runtime_support as runtime_support_module
from engineeringagent.agents import AgentBackendError, AgentBackendFailureDetails
from engineeringagent.adapters.agents.opencode.permissions import (
    PermissionProbeResult,
)
from engineeringagent.application import ImplementStepResult, RunLoopRequest
from engineeringagent.bootstrap import AppFactory
from engineeringagent.domain.audit import fallback_implement_progress_envelope
from engineeringagent.presentation import cli as cli_module


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
    """Run the loop through the application service boundary."""
    result = AppFactory(project_root).build_run_loop_service().run(
        RunLoopRequest(
            project_root=project_root,
            feature_paths=tuple(feature_paths),
            run_all=run_all,
            dry_run=dry_run,
            max_iterations=max_iterations,
            allow_dirty=allow_dirty,
            verbose_output=verbose_output,
        )
    )
    return result.exit_code


OPENCODE_IMPLEMENT = SimpleNamespace(side_effect=None, fake_result=None)
PROGRESS_ROOT_PARTS = (".engineeringagent", "progress")
RUNS_LOG_REF = ".engineeringagent/progress/runs/runs.jsonl"
FEATURE_LOG_REF = ".engineeringagent/progress/FEAT-900/run.txt"
FEATURE_LOG_GLOB_REF = ".engineeringagent/progress/*/run.txt"


def passing_implement_result(output: str = "") -> ImplementStepResult:
    return (True, None, output, fallback_implement_progress_envelope(), True)


@contextmanager
def with_opencode_implement_side_effect(effect: Callable[[], None]) -> Iterator[None]:
    previous = OPENCODE_IMPLEMENT.side_effect
    OPENCODE_IMPLEMENT.side_effect = effect
    try:
        yield
    finally:
        OPENCODE_IMPLEMENT.side_effect = previous


@contextmanager
def with_opencode_implement_result(
    *,
    returncode: int = 0,
    stdout: str = "ok\n",
    stderr: str = "",
) -> Iterator[None]:
    previous = OPENCODE_IMPLEMENT.fake_result
    OPENCODE_IMPLEMENT.fake_result = (returncode, stdout, stderr)
    try:
        yield
    finally:
        OPENCODE_IMPLEMENT.fake_result = previous


@pytest.fixture(autouse=True)
def stub_opencode_start_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_agent(
        _project_root: Path,
        _prompt: str,
        *,
        output_type: Any | None = None,
        **_unused_kwargs: Any,
    ) -> str:
        is_implement_call = output_type is not None
        if is_implement_call:
            effect = OPENCODE_IMPLEMENT.side_effect
            if effect is not None:
                effect()

        override = OPENCODE_IMPLEMENT.fake_result if is_implement_call else None
        if override is None:
            override = (0, "ok\n", "")

        returncode, stdout, stderr = override
        if returncode != 0:
            raise AgentBackendError(
                backend="opencode",
                message="opencode run failed",
                process=AgentBackendFailureDetails(
                    returncode=returncode,
                    stdout=stdout,
                    stderr=stderr,
                ),
            )
        return stdout + stderr

    monkeypatch.setattr(runtime_support_module.agent_runtime, "run_agent", fake_run_agent)


@pytest.fixture(autouse=True)
def stub_permission_precheck(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_permission_probe(_project_root: Path) -> PermissionProbeResult:
        return PermissionProbeResult(
            ok=True,
            reason="ok",
            returncode=0,
            output="PERMISSION_OK\n",
        )

    monkeypatch.setattr(
        agent_helpers,
        "run_permission_probe",
        fake_run_permission_probe,
    )


def invoke_cli(args: list[str]) -> Any:
    runner = CliRunner(mix_stderr=False)
    return runner.invoke(cli_module.build_typer_app(), args)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def copy_canonical_prompts(project_root: Path) -> None:
    source_root = Path(__file__).resolve().parents[2] / "harness" / "prompts"
    target_root = project_root / "harness" / "prompts"
    shutil.copytree(source_root, target_root, dirs_exist_ok=True)


def base_feature(status: str = "backlog") -> dict[str, Any]:
    return {
        "id": "FEAT-900",
        "title": "Feature iteration smoke test",
        "type": "feature",
        "expected_commit_subject": "feat: complete FEAT-900 feature iteration smoke test",
        "planning_tier": "direct",
        "status": status,
        "priority": "high",
        "objective": "Verify feature iteration does not require subtask selection.",
        "acceptance": ["Feature iteration runs as a feature-level unit."],
        "artifacts": {},
        "updated_at": "2026-02-12T00:00:00Z",
    }


def make_project_root(
    tmp_path: Path,
    feature_data: dict[str, Any],
    gates_data: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    project_root = tmp_path
    feature_path = (
        project_root / "docs" / "spec" / "features" / "FEAT-900-ralph-test" / "spec.yaml"
    )
    feature_payload = dict(feature_data)
    feature_payload.setdefault("planning_tier", "direct")
    feature_payload.setdefault("artifacts", {})

    checks: dict[str, Any] = {}
    if gates_data is not None:
        gates = gates_data.get("gates") if isinstance(gates_data, dict) else None
        if isinstance(gates, dict):
            for gate_id, gate in gates.items():
                if not isinstance(gate_id, str) or not gate_id:
                    continue
                if not isinstance(gate, dict):
                    continue
                command = gate.get("run")
                if not isinstance(command, str) or not command.strip():
                    continue
                checks[gate_id] = {
                    "type": "command",
                    "command": command,
                }

    write_yaml(
        project_root / "harness" / "checks.yaml",
        {
            "contract_version": "1.0",
            "defaults": {"when": {"phase": "iteration_end"}},
            "groups": (
                [
                    {
                        "group_id": "commands",
                        "description": "Command checks.",
                        "checks": list(checks),
                    }
                ]
                if checks
                else []
            ),
            "checks": checks,
        },
    )
    copy_canonical_prompts(project_root)
    write_yaml(feature_path, feature_payload)
    return project_root, feature_path


def make_bundled_project_root(
    tmp_path: Path,
    *,
    feature_data: dict[str, Any],
    plan_frontmatter: dict[str, Any],
    plan_body: str = "# Plan\n",
    gates_data: dict[str, Any] | None = None,
) -> tuple[Path, Path, Path]:
    project_root = tmp_path
    feature_root = (
        project_root / "docs" / "spec" / "features" / "FEAT-900-bundled-smoke-test"
    )
    feature_path = feature_root / "spec.yaml"
    plan_path = feature_root / "plan.md"

    checks: dict[str, Any] = {}
    if gates_data is not None:
        gates = gates_data.get("gates") if isinstance(gates_data, dict) else None
        if isinstance(gates, dict):
            for gate_id, gate in gates.items():
                if not isinstance(gate_id, str) or not gate_id:
                    continue
                if not isinstance(gate, dict):
                    continue
                command = gate.get("run")
                if not isinstance(command, str) or not command.strip():
                    continue
                checks[gate_id] = {
                    "type": "command",
                    "command": command,
                }

    write_yaml(
        project_root / "harness" / "checks.yaml",
        {
            "contract_version": "1.0",
            "defaults": {"when": {"phase": "iteration_end"}},
            "checks": checks,
        },
    )
    copy_canonical_prompts(project_root)
    write_yaml(feature_path, feature_data)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        "---\n"
        + yaml.safe_dump(plan_frontmatter, sort_keys=False)
        + "---\n\n"
        + plan_body,
        encoding="utf-8",
    )
    return project_root, feature_path, plan_path


def progress_root(project_root: Path) -> Path:
    return project_root.joinpath(*PROGRESS_ROOT_PARTS)


def read_runs(project_root: Path) -> list[dict[str, Any]]:
    runs_path = progress_root(project_root) / "runs" / "runs.jsonl"
    return [
        json.loads(line) for line in runs_path.read_text(encoding="utf-8").splitlines()
    ]


def run_git(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=project_root, check=True, capture_output=True, text=True
    )


def run_python_script(script_path: Path, *args: Path) -> None:
    subprocess.run(
        [sys.executable, str(script_path), *(str(arg) for arg in args)],
        check=True,
        capture_output=True,
        text=True,
    )


def patch_run_agent_with_fake(
    monkeypatch: pytest.MonkeyPatch,
    fake_subprocess_run: Any,
) -> None:
    def fake_run_agent(project_root: Path, prompt: str, **_kwargs: Any) -> str:
        del project_root
        proc = fake_subprocess_run(["opencode", "run", "--agent", "build", prompt])
        output = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            raise AgentBackendError(
                backend="opencode",
                message="opencode run failed",
                process=AgentBackendFailureDetails(
                    returncode=int(proc.returncode),
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                ),
            )
        return output

    monkeypatch.setattr(runtime_support_module.agent_runtime, "run_agent", fake_run_agent)


def install_prompt_capture_agent(
    monkeypatch: pytest.MonkeyPatch,
    prompt_handler: Callable[[str, list[str]], subprocess.CompletedProcess[str]],
) -> list[str]:
    prompts: list[str] = []
    real_run = subprocess.run

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if isinstance(command, list) and command[:3] == ["opencode", "run", "--agent"]:
            prompt = command[4]
            prompts.append(prompt)
            return prompt_handler(prompt, prompts)
        check = bool(kwargs.pop("check", False))
        return real_run(command, check=check, **kwargs)

    patch_run_agent_with_fake(monkeypatch, fake_subprocess_run)
    return prompts


def install_shell_command_results(
    monkeypatch: pytest.MonkeyPatch,
    results: list[subprocess.CompletedProcess[str]],
) -> None:
    remaining = iter(results)

    def fake_run_shell_command(
        project_root: Path, command: str
    ) -> subprocess.CompletedProcess[str]:
        del project_root, command
        return next(remaining)

    monkeypatch.setattr(
        "engineeringagent.adapters.runtime.iteration_phases.run_shell_command",
        fake_run_shell_command,
    )


def write_fail_once_script(
    script_path: Path,
    counter_path: Path,
    message: str,
) -> Path:
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "counter = Path(sys.argv[1])",
                "count = int(counter.read_text(encoding='utf-8')) if counter.exists() else 0",
                "count += 1",
                "counter.write_text(str(count), encoding='utf-8')",
                "if count == 1:",
                f"    print({message!r})",
                "    raise SystemExit(1)",
                "print('ok')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script_path


def init_git_repo(project_root: Path) -> None:
    run_git(project_root, "init")
    run_git(project_root, "add", "-A")
    run_git(
        project_root,
        "-c",
        "user.name=test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "init",
    )


def write_set_done_script(script_path: Path) -> Path:
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
                "plan_path = feature_path.parent / 'plan.md'",
                "if plan_path.is_file():",
                "    document = plan_path.read_text(encoding='utf-8')",
                "    frontmatter_end = document.find('\\n---', 4)",
                "    frontmatter = yaml.safe_load(document[4:frontmatter_end])",
                "    frontmatter['status'] = 'done'",
                "    for phase in frontmatter.get('phases', []):",
                "        if isinstance(phase, dict):",
                "            phase['status'] = 'done'",
                "    plan_path.write_text(",
                "        '---\\n' + yaml.safe_dump(frontmatter, sort_keys=False) + '---\\n' + document[frontmatter_end + 4:],",
                "        encoding='utf-8',",
                "    )",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script_path


def write_set_plan_phase_done_script(script_path: Path, phase_id: str) -> Path:
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "import yaml",
                f"target_phase_id = {phase_id!r}",
                "plan_path = Path(sys.argv[1])",
                "document = plan_path.read_text(encoding='utf-8')",
                "frontmatter_end = document.find('\\n---', 4)",
                "frontmatter = yaml.safe_load(document[4:frontmatter_end])",
                "for phase in frontmatter.get('phases', []):",
                "    if isinstance(phase, dict) and phase.get('id') == target_phase_id:",
                "        phase['status'] = 'done'",
                "        break",
                "plan_path.write_text(",
                "    '---\\n' + yaml.safe_dump(frontmatter, sort_keys=False) + '---\\n' + document[frontmatter_end + 4:],",
                "    encoding='utf-8',",
                ")",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script_path


def write_set_done_and_duplicate_plan_phase_script(
    script_path: Path,
    phase_id: str,
    duplicate_verification_command: str,
) -> Path:
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "import yaml",
                f"target_phase_id = {phase_id!r}",
                f"duplicate_verification_command = {duplicate_verification_command!r}",
                "plan_path = Path(sys.argv[1])",
                "document = plan_path.read_text(encoding='utf-8')",
                "frontmatter_end = document.find('\\n---', 4)",
                "frontmatter = yaml.safe_load(document[4:frontmatter_end])",
                "phases = frontmatter.get('phases', [])",
                "for phase in phases:",
                "    if isinstance(phase, dict) and phase.get('id') == target_phase_id:",
                "        phase['status'] = 'done'",
                "        phases.append({",
                "            'id': target_phase_id,",
                "            'title': 'Duplicated done phase',",
                "            'status': 'done',",
                "            'verification': [duplicate_verification_command],",
                "        })",
                "        break",
                "plan_path.write_text(",
                "    '---\\n' + yaml.safe_dump(frontmatter, sort_keys=False) + '---\\n' + document[frontmatter_end + 4:],",
                "    encoding='utf-8',",
                ")",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script_path


def write_set_done_and_create_feature_script(script_path: Path) -> Path:
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "import yaml",
                "feature_path = Path(sys.argv[1])",
                "created_feature_path = Path(sys.argv[2])",
                "feature = yaml.safe_load(feature_path.read_text(encoding='utf-8'))",
                "feature['status'] = 'done'",
                "feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding='utf-8')",
                "created_feature = {",
                "    'id': 'FEAT-999',",
                "    'title': 'Created after startup snapshot',",
                "    'type': 'feature',",
                "    'expected_commit_subject': 'feat: create feature after startup snapshot',",
                "    'planning_tier': 'direct',",
                "    'status': 'backlog',",
                "    'priority': 'high',",
                "    'objective': 'Ensure run --all startup snapshot remains stable.',",
                "    'acceptance': ['Feature can be selected in a later run.'],",
                "    'artifacts': {},",
                "    'updated_at': '2026-02-14T00:00:00Z',",
                "}",
                "created_feature_path.parent.mkdir(parents=True, exist_ok=True)",
                "created_feature_path.write_text(",
                "    yaml.safe_dump(created_feature, sort_keys=False),",
                "    encoding='utf-8',",
                ")",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script_path


def write_move_to_done_script(script_path: Path) -> Path:
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import shutil",
                "import sys",
                "import yaml",
                "project_root = Path(sys.argv[1])",
                "feature_path = Path(sys.argv[2])",
                "feature = yaml.safe_load(feature_path.read_text(encoding='utf-8'))",
                "feature['status'] = 'done'",
                "feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding='utf-8')",
                "done_root = project_root / 'docs' / 'spec' / 'features_done' / feature_path.parent.name",
                "done_root.parent.mkdir(parents=True, exist_ok=True)",
                "shutil.move(str(feature_path.parent), str(done_root))",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script_path


def write_delete_selected_feature_script(script_path: Path) -> Path:
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "feature_path = Path(sys.argv[1])",
                "feature_path.unlink()",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script_path


def move_feature_to_done(project_root: Path, feature_path: Path) -> None:
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    feature["status"] = "done"
    feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding="utf-8")
    done_root = project_root / "docs" / "spec" / "features_done" / feature_path.parent.name
    done_root.parent.mkdir(parents=True, exist_ok=True)
    feature_path.parent.rename(done_root)
