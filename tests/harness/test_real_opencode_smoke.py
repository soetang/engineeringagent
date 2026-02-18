from __future__ import annotations

# Tests load the smoke script module and exercise internal helpers.
# pylint: disable=protected-access

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
    assert len(verification) == 2
    assert all(command.startswith("uv run python -c ") for command in verification)


def test_smoke_harness_pins_spark_model_in_init_command(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    spark_template_path = (
        repo_root
        / "harness"
        / "fitness-functions"
        / "opencode.agent.engineeringagent.spark.md.tmpl"
    )
    assert not spark_template_path.exists()

    smoke = _load_smoke_module(repo_root)
    assert not hasattr(smoke, "_write_spark_agent_override")

    argv = smoke.build_init_argv(tmp_repo=tmp_path)
    assert "--model" in argv
    assert smoke.SPARK_AGENT_MODEL == "openai/gpt-5.3-codex-spark"

    model_flag_index = argv.index("--model")
    assert argv[model_flag_index + 1] == "openai/gpt-5.3-codex-spark"


def test_verification_commands_use_uv_run_in_smoke_helper(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Ensure the smoke helper executes helper checks via `uv run python`."""
    smoke = _load_smoke_module(repo_root)

    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(
        argv: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((argv, dict(kwargs)))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(smoke.subprocess, "run", fake_run)

    violations: list[str] = []
    assert smoke._run_verification_commands(tmp_path, violations) is True
    assert not violations

    assert len(calls) == 2
    assert all(argv[:4] == ["uv", "run", "python", "-c"] for argv, _kwargs in calls)
