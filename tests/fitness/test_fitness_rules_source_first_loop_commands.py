from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import yaml


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness_functions"
        / "check_source_first_loop_commands.py"
    )


def _write_yaml(path: Path, content: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(content, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def _write_markdown_frontmatter(path: Path, frontmatter: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        + yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=False)
        + "---\n",
        encoding="utf-8",
    )


def _smoke_plan_frontmatter(command: str) -> dict[str, object]:
    return {
        "plan_id": "FEAT-001",
        "feature_id": "FEAT-001",
        "status": "backlog",
        "source_spec": "spec.yaml",
        "planning_tier": "planned",
        "phases": [
            {
                "id": "P1",
                "title": "Smoke phase",
                "status": "backlog",
                "verification": [command],
            }
        ],
    }


def _run_checker(
    project_root: Path,
    *,
    checker_path: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    proc = subprocess.run(
        [sys.executable, str(checker_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    return proc, payload


def test_detects_forbidden_uvx_from_dot_in_feature_verification(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when a bundled plan phase verification command uses uvx --from ."""
    feature_root = tmp_path / "docs/spec/features/FEAT-001-bundled"
    _write_yaml(
        feature_root / "spec.yaml",
        {
            "id": "FEAT-001",
            "title": "Bundled feature",
            "type": "spec",
            "expected_commit_subject": "spec: bundled feature",
            "planning_tier": "planned",
            "status": "backlog",
            "priority": "high",
            "objective": "Exercise bundled verification scanning.",
            "acceptance": ["Detect bundled plan verification commands."],
            "artifacts": {"plan": "plan.md"},
        },
    )
    _write_markdown_frontmatter(
        feature_root / "plan.md",
        _smoke_plan_frontmatter("uvx --from . engineeringagent validate"),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    violations = payload["violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert (
        "docs/spec/features/FEAT-001-bundled/plan.md:phases[0].verification[0]"
        in violations[0]
    )


def test_detects_forbidden_uvx_from_dot_in_checks_config(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when a command check uses uvx --from . engineeringagent."""
    feature_root = tmp_path / "docs/spec/features/FEAT-001-bundled"
    _write_yaml(
        feature_root / "spec.yaml",
        {
            "id": "FEAT-001",
            "title": "Bundled feature",
            "type": "spec",
            "expected_commit_subject": "spec: bundled feature",
            "planning_tier": "planned",
            "status": "backlog",
            "priority": "high",
            "objective": "Exercise bundled verification scanning.",
            "acceptance": ["Allow bundled plan verification commands."],
            "artifacts": {"plan": "plan.md"},
        },
    )
    _write_markdown_frontmatter(
        feature_root / "plan.md",
        _smoke_plan_frontmatter("uv run engineeringagent validate --schema-only"),
    )
    _write_yaml(
        tmp_path / "harness/checks.yaml",
        {
            "contract_version": "1.0",
            "checks": {
                "fitness_validate": {
                    "type": "command",
                    "command": "uvx --from . engineeringagent checks run --checks fitness --phase iteration_end",
                }
            },
        },
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    violations = payload["violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert "harness/checks.yaml:checks.fitness_validate.command" in violations[0]


def test_detects_legacy_module_form_in_loop_command_surfaces(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when loop command surfaces still use python -m engineeringagent.cli."""
    feature_root = tmp_path / "docs/spec/features/FEAT-001-bundled"
    _write_yaml(
        feature_root / "spec.yaml",
        {
            "id": "FEAT-001",
            "title": "Bundled feature",
            "type": "spec",
            "expected_commit_subject": "spec: bundled feature",
            "planning_tier": "planned",
            "status": "backlog",
            "priority": "high",
            "objective": "Exercise bundled verification scanning.",
            "acceptance": ["Detect bundled plan verification commands."],
            "artifacts": {"plan": "plan.md"},
        },
    )
    _write_markdown_frontmatter(
        feature_root / "plan.md",
        _smoke_plan_frontmatter("uv run python -m engineeringagent.cli validate"),
    )
    _write_yaml(
        tmp_path / "harness/checks.yaml",
        {
            "contract_version": "1.0",
            "checks": {
                "spec_validate": {
                    "type": "command",
                    "command": "uv run python -m engineeringagent.cli validate",
                }
            },
        },
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    violations = payload["violations"]
    assert isinstance(violations, list)
    assert len(violations) == 2
    assert "docs/spec/features/FEAT-001-bundled/plan.md:phases[0].verification[0]" in (
        violations[0]
    )
    assert "harness/checks.yaml:checks.spec_validate.command" in violations[1]
    assert "prefer `uv run engineeringagent ...`" in violations[0]


def test_detects_forbidden_uvx_from_dot_in_bundled_plan_phase_verification(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when bundled plan phases use uvx --from . engineeringagent."""
    feature_root = tmp_path / "docs/spec/features/FEAT-181-bundled"
    _write_yaml(
        feature_root / "spec.yaml",
        {
            "id": "FEAT-181",
            "title": "Bundled feature",
            "type": "spec",
            "expected_commit_subject": "spec: bundled feature",
            "planning_tier": "planned",
            "status": "backlog",
            "priority": "high",
            "objective": "Exercise bundled verification scanning.",
            "acceptance": ["Detect bundled plan verification commands."],
            "artifacts": {"plan": "plan.md"},
        },
    )
    _write_markdown_frontmatter(
        feature_root / "plan.md",
        {
            "plan_id": "FEAT-181",
            "feature_id": "FEAT-181",
            "status": "backlog",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Phase one",
                    "status": "backlog",
                    "verification": [
                        "uvx --from . engineeringagent validate --schema-only"
                    ],
                }
            ],
        },
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    violations = payload["violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert "docs/spec/features/FEAT-181-bundled/plan.md:phases[0].verification[0]" in (
        violations[0]
    )


def test_detects_forbidden_uvx_from_dot_in_bundled_declared_plan_artifact(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when bundled specs point at a non-default plan artifact path."""
    feature_root = tmp_path / "docs/spec/features/FEAT-181-bundled"
    _write_yaml(
        feature_root / "spec.yaml",
        {
            "id": "FEAT-181",
            "title": "Bundled feature",
            "type": "spec",
            "expected_commit_subject": "spec: bundled feature",
            "planning_tier": "planned",
            "status": "backlog",
            "priority": "high",
            "objective": "Exercise bundled verification scanning.",
            "acceptance": ["Detect declared bundled plan verification commands."],
            "artifacts": {"plan": "planning/active-plan.md"},
        },
    )
    _write_markdown_frontmatter(
        feature_root / "planning/active-plan.md",
        {
            "plan_id": "FEAT-181",
            "feature_id": "FEAT-181",
            "status": "backlog",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Phase one",
                    "status": "backlog",
                    "verification": [
                        "uvx --from . engineeringagent validate --schema-only"
                    ],
                }
            ],
        },
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    violations = payload["violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert (
        "docs/spec/features/FEAT-181-bundled/planning/active-plan.md:phases[0].verification[0]"
        in violations[0]
    )


def test_detects_forbidden_uvx_from_dot_in_smoke_plan_template(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the real-opencode smoke plan template regresses to uvx --from ."""
    _write_markdown_frontmatter(
        tmp_path / "docs/fixtures/real_opencode_hello_world_plan_template.md",
        _smoke_plan_frontmatter("uvx --from . engineeringagent validate --schema-only"),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    violations = payload["violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert "docs/fixtures/real_opencode_hello_world_plan_template.md:phases[0].verification[0]" in (
        violations[0]
    )


def test_detects_forbidden_uvx_from_dot_in_plan_session_approach_doc(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when packaged plan-session guidance regresses to uvx --from ."""
    path = tmp_path / "src/engineeringagent/approach/docs/plan-session.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                "approach_id: plan-session",
                "description: Task-specific: only when creating plan.md.",
                "---",
                "",
                "# Plan Session Approach",
                "",
                "- `uvx --from . engineeringagent validate --schema-only`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    violations = payload["violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert "src/engineeringagent/approach/docs/plan-session.md:line 8" in violations[0]


def test_detects_forbidden_uvx_from_dot_in_research_session_approach_doc(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when packaged research-session guidance regresses to uvx --from ."""
    path = tmp_path / "src/engineeringagent/approach/docs/research-session.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                "approach_id: research-session",
                "description: Task-specific: only when creating research.md.",
                "---",
                "",
                "# Research Session Approach",
                "",
                "- `uvx --from . engineeringagent validate --schema-only`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    violations = payload["violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert "src/engineeringagent/approach/docs/research-session.md:line 8" in violations[0]


def test_detects_forbidden_uvx_from_dot_in_workflow_approach_doc(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when contributor workflow guidance regresses to uvx --from ."""
    path = tmp_path / "src/engineeringagent/approach/docs/workflow.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                "approach_id: workflow",
                "---",
                "",
                "# Workflow",
                "",
                "Run the loop with: `uvx --from . engineeringagent run --all`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    violations = payload["violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert "src/engineeringagent/approach/docs/workflow.md:line 7" in violations[0]


def test_detects_forbidden_uvx_from_dot_in_loop_implementation_prompt_definition(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the loop implementation prompt regresses to uvx --from ."""
    path = (
        tmp_path
        / "harness/prompts/loop_implementation.py"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "COMMAND = 'uvx --from . engineeringagent validate --schema-only'\n",
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    violations = payload["violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert "harness/prompts/loop_implementation.py:line 1" in (
        violations[0]
    )


def test_smoke_plan_template_fixtures_use_bundled_status_vocabulary() -> None:
    smoke_failure_frontmatter = _smoke_plan_frontmatter(
        "uvx --from . engineeringagent validate --schema-only"
    )
    smoke_success_frontmatter = _smoke_plan_frontmatter(
        "uv run engineeringagent validate --schema-only"
    )

    for frontmatter in (smoke_failure_frontmatter, smoke_success_frontmatter):
        assert frontmatter["status"] in {"backlog", "in_progress", "done", "blocked"}
        phases = frontmatter["phases"]
        assert isinstance(phases, list)
        assert phases[0]["status"] in {"backlog", "in_progress", "done", "blocked"}


def test_allows_uv_run_source_first_forms(tmp_path: Path, repo_root: Path) -> None:
    """Pass when scoped commands use uv run or direct local workspace execution."""
    _write_yaml(
        tmp_path / "docs/spec/features/FEAT-001-bundled/spec.yaml",
        {
            "id": "FEAT-001",
            "title": "Bundled feature",
            "type": "spec",
            "expected_commit_subject": "spec: bundled feature",
            "planning_tier": "planned",
            "status": "backlog",
            "priority": "high",
            "objective": "Exercise bundled verification scanning.",
            "acceptance": ["Allow bundled source-first verification commands."],
            "artifacts": {"plan": "plan.md"},
        },
    )
    _write_markdown_frontmatter(
        tmp_path / "docs/spec/features/FEAT-001-bundled/plan.md",
        _smoke_plan_frontmatter("uv run engineeringagent validate --schema-only"),
    )
    _write_yaml(
        tmp_path / "docs/spec/features/FEAT-181-bundled/spec.yaml",
        {
            "id": "FEAT-181",
            "title": "Bundled feature",
            "type": "spec",
            "expected_commit_subject": "spec: bundled feature",
            "planning_tier": "planned",
            "status": "backlog",
            "priority": "high",
            "objective": "Exercise bundled verification scanning.",
            "acceptance": ["Allow bundled source-first verification commands."],
            "artifacts": {"plan": "plan.md"},
        },
    )
    _write_markdown_frontmatter(
        tmp_path / "docs/spec/features/FEAT-181-bundled/plan.md",
        {
            "plan_id": "FEAT-181",
            "feature_id": "FEAT-181",
            "status": "backlog",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Phase one",
                    "status": "backlog",
                    "verification": [
                        "uv run engineeringagent validate --schema-only",
                    ],
                }
            ],
        },
    )
    _write_yaml(
        tmp_path / "harness/checks.yaml",
        {
            "contract_version": "1.0",
            "checks": {
                "spec_validate": {
                    "type": "command",
                    "command": "uv run engineeringagent validate --schema-only",
                },
                "fitness_validate": {
                    "type": "command",
                    "command": "uv run engineeringagent checks run --checks fitness --phase iteration_end",
                },
            },
        },
    )
    _write_markdown_frontmatter(
        tmp_path / "docs/fixtures/real_opencode_hello_world_plan_template.md",
        _smoke_plan_frontmatter("uv run engineeringagent validate --schema-only"),
    )
    prompt_definition_path = (
        tmp_path / "harness/prompts/loop_implementation.py"
    )
    prompt_definition_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_definition_path.write_text(
        "COMMAND = 'uv run engineeringagent validate --schema-only'\n",
        encoding="utf-8",
    )
    workflow_doc_path = tmp_path / "src/engineeringagent/approach/docs/workflow.md"
    workflow_doc_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_doc_path.write_text(
        "Run the loop with: `uv run engineeringagent run --all`\n",
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert not payload["violations"]
