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
    """Verify the smoke template uses a bundled planned feature package."""
    template_path = (
        repo_root
        / "harness"
        / "fitness-functions"
        / "real_opencode_hello_world_feature_template.yaml"
    )
    payload = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)

    assert payload.get("planning_tier") == "planned"
    assert payload.get("artifacts") == {"plan": "plan.md"}
    assert "subtasks" not in payload


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


def test_smoke_harness_runs_loop_via_run_all(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    smoke = _load_smoke_module(repo_root)

    argv = smoke.build_run_argv(tmp_repo=tmp_path)

    assert argv[:5] == ["uv", "run", "engineeringagent", "--project-root", str(tmp_path)]
    assert argv[5:] == ["run", "--all", "--max-iterations", "3"]


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


def test_smoke_harness_uses_uv_run_engineeringagent_entrypoint(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    smoke = _load_smoke_module(repo_root)

    init_argv = smoke.build_init_argv(tmp_repo=tmp_path)
    run_argv = smoke.build_run_argv(tmp_repo=tmp_path)

    assert init_argv[:5] == ["uv", "run", "engineeringagent", "--project-root", str(tmp_path)]
    assert run_argv[:5] == ["uv", "run", "engineeringagent", "--project-root", str(tmp_path)]
    assert "engineeringagent.cli" not in init_argv
    assert "engineeringagent.cli" not in run_argv


def test_smoke_helper_targets_bundled_feature_package(repo_root: Path) -> None:
    smoke = _load_smoke_module(repo_root)

    assert smoke._FEATURE_SPEC_RELATIVE_PATH == Path(
        "docs/spec/features/FEAT-001-hello-world-smoke/spec.yaml"
    )


def test_smoke_helper_reads_plan_template_from_docs_fixture(repo_root: Path) -> None:
    smoke = _load_smoke_module(repo_root)

    assert smoke._PLAN_TEMPLATE_PATH == Path(
        "docs/fixtures/real_opencode_hello_world_plan_template.md"
    )


def test_plan_template_verification_commands_use_uv_run(repo_root: Path) -> None:
    smoke = _load_smoke_module(repo_root)
    frontmatter = smoke.load_markdown_frontmatter(repo_root / smoke._PLAN_TEMPLATE_PATH)
    assert isinstance(frontmatter, dict)
    phases = frontmatter.get("phases")
    assert isinstance(phases, list)
    assert phases

    verification = phases[0].get("verification")
    assert isinstance(verification, list)
    assert verification
    assert all(
        isinstance(command, str) and command.startswith("uv run ")
        for command in verification
    )


def test_smoke_fixture_bundle_templates_stay_in_sync(repo_root: Path) -> None:
    smoke = _load_smoke_module(repo_root)

    violations = smoke._bundle_template_violations(repo_root)

    assert violations == []


def test_smoke_fixture_bundle_detects_mismatched_plan_metadata(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    smoke = _load_smoke_module(repo_root)
    plan_frontmatter = smoke.load_markdown_frontmatter(repo_root / smoke._PLAN_TEMPLATE_PATH)
    plan_frontmatter["feature_id"] = "FEAT-999"
    plan_frontmatter["planning_tier"] = "researched"

    monkeypatch.setattr(
        smoke,
        "load_markdown_frontmatter",
        lambda _path: plan_frontmatter,
    )

    violations = smoke._bundle_template_violations(repo_root)

    assert "plan frontmatter feature_id must match spec id FEAT-001" in violations
    assert "plan frontmatter planning_tier must match spec planning_tier planned" in violations


def test_smoke_fixture_bundle_detects_invalid_plan_phase_statuses_and_verification(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    smoke = _load_smoke_module(repo_root)
    plan_frontmatter = smoke.load_markdown_frontmatter(repo_root / smoke._PLAN_TEMPLATE_PATH)
    plan_frontmatter["status"] = "ready"
    plan_frontmatter["phases"] = [
        {
            "id": "P1",
            "title": "Implement hello world",
            "status": "pending",
            "verification": [],
        }
    ]

    monkeypatch.setattr(
        smoke,
        "load_markdown_frontmatter",
        lambda _path: plan_frontmatter,
    )

    violations = smoke._bundle_template_violations(repo_root)

    assert "plan frontmatter status must use runtime vocabulary" in violations
    assert "plan phase 1 status must use runtime vocabulary" in violations
    assert "plan phase 1 must declare at least one verification command" in violations


def test_parse_archived_bundle_statuses_reads_plan_phase_statuses(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    smoke = _load_smoke_module(repo_root)

    feature_dir = tmp_path / "docs" / "spec" / "features_done" / "FEAT-001-hello-world-smoke"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.yaml").write_text(
        "\n".join(
            [
                "id: FEAT-001",
                "title: Smoke feature",
                "type: feature",
                "expected_commit_subject: 'feat: implement hello-world smoke interface'",
                "planning_tier: planned",
                "status: done",
                "priority: high",
                "objective: smoke",
                "acceptance:",
                "  - done",
                "artifacts:",
                "  plan: plan.md",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (feature_dir / "plan.md").write_text(
        "\n".join(
            [
                "---",
                "plan_id: FEAT-001",
                "feature_id: FEAT-001",
                "status: done",
                "source_spec: spec.yaml",
                "planning_tier: planned",
                "phases:",
                "  - id: P1",
                "    title: Implement hello world",
                "    status: done",
                "    verification:",
                "      - uv run python -c \"print('ok')\"",
                "---",
                "",
                "# Plan",
                "",
            ]
        ),
        encoding="utf-8",
    )

    top_status, phase_statuses = smoke._parse_feature_statuses(feature_dir / "spec.yaml")
    assert top_status == "done"
    assert phase_statuses == ("done",)
