from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest
import yaml


def _load_smoke_module(repo_root: Path):
    smoke_path = (
        repo_root
        / "harness"
        / "fitness-functions"
        / "check_real_opencode_hello_world_smoke.py"
    )
    spec = importlib.util.spec_from_file_location(
        "engineeringagent_tests.real_opencode_smoke",
        smoke_path,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_template_verification_commands_use_uv_run(repo_root: Path) -> None:
    """Verify template verification commands stay on uv-backed execution."""
    template_path = (
        repo_root
        / "harness"
        / "fitness-functions"
        / "real_opencode_hello_world_feature_template.yaml"
    )
    payload = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)

    subtasks = payload.get("subtasks")
    assert isinstance(subtasks, list) and subtasks

    verification = subtasks[0].get("verification")
    assert isinstance(verification, list)
    assert verification == [
        "uv run python -c \"from hello_world import hello; assert hello('World') == 'Hello, World!'\"",
        "uv run python -c \"import subprocess; out=subprocess.check_output(['uv','run','python','-m','hello_world'], text=True); assert out.strip()=='Hello, World!'\"",
    ]
    assert all(command.startswith("uv run python") for command in verification)


def test_smoke_helper_writes_spark_agent_override(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    smoke = _load_smoke_module(repo_root)

    violations: list[str] = []
    smoke._write_spark_agent_override(tmp_path, violations)
    assert violations == []

    agent_path = tmp_path / ".opencode" / "agents" / "engineeringagent.md"
    assert agent_path.exists()
    payload = agent_path.read_text(encoding="utf-8")
    assert 'model: "openai/gpt-5.3-codex-spark"' in payload


def test_verification_commands_use_uv_run_in_smoke_helper(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Ensure the smoke helper executes helper checks via `uv run python`."""
    smoke = _load_smoke_module(repo_root)

    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, dict(kwargs)))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(smoke.subprocess, "run", fake_run)

    violations: list[str] = []
    assert smoke._run_verification_commands(tmp_path, violations) is True
    assert not violations

    expected_commands = [
        [
            "uv",
            "run",
            "python",
            "-c",
            "from hello_world import hello; assert hello('World') == 'Hello, World!'",
        ],
        [
            "uv",
            "run",
            "python",
            "-c",
            "import subprocess; out=subprocess.check_output(['uv','run','python','-m','hello_world'], text=True); assert out.strip()=='Hello, World!'",
        ],
    ]
    assert [call[0] for call in calls] == expected_commands
    assert all(call[0][0] == "uv" for call in calls)
