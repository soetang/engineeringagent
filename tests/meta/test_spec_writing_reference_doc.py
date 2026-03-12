from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from engineeringagent.adapters.documents import guidance_topic_catalog
from engineeringagent.spec_bundles import iter_feature_files, load_markdown_frontmatter


def _feature_verification_commands(features_dir: Path) -> list[str]:
    commands: list[str] = []
    for feature_path in iter_feature_files(features_dir):
        body = feature_path.read_text(encoding="utf-8")
        document = yaml.safe_load(body)
        assert isinstance(document, dict)

        plan_path = feature_path.parent / "plan.md"
        if not plan_path.is_file():
            continue

        frontmatter = load_markdown_frontmatter(plan_path)
        phases = frontmatter.get("phases", [])
        assert isinstance(phases, list)
        for phase in phases:
            assert isinstance(phase, dict)
            verification = phase.get("verification", [])
            assert isinstance(verification, list)
            for command in verification:
                if isinstance(command, str):
                    commands.append(command)

    return commands


def _load_plan_phases(frontmatter: dict[str, object]) -> list[dict[str, Any]]:
    phases = frontmatter.get("phases")
    assert isinstance(phases, list)
    assert all(isinstance(phase, dict) for phase in phases)
    return phases


def test_feature_verification_commands_include_bundled_plan_phases(
    tmp_path: Path,
) -> None:
    """Read verification commands from bundled plan phases."""
    features_dir = tmp_path / "docs" / "spec" / "features"
    features_dir.mkdir(parents=True)
    bundled_dir = features_dir / "FEAT-002-bundled"
    bundled_dir.mkdir()
    (bundled_dir / "spec.yaml").write_text(
        "\n".join(
            [
                "id: FEAT-002",
                "artifacts:",
                "  plan: plan.md",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (bundled_dir / "plan.md").write_text(
        "\n".join(
            [
                "---",
                "plan_id: FEAT-002",
                "feature_id: FEAT-002",
                "status: backlog",
                "source_spec: spec.yaml",
                "planning_tier: planned",
                "phases:",
                "  - id: P1",
                "    title: Verify bundle",
                "    status: backlog",
                "    verification:",
                "      - uv run pytest -q tests/unit/test_bundle.py",
                "---",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert _feature_verification_commands(features_dir) == [
        "uv run pytest -q tests/unit/test_bundle.py",
    ]


def test_active_feature_verification_commands_do_not_require_ripgrep(
    repo_root: Path,
) -> None:
    """Ensure spec verification commands avoid ripgrep as a hard dependency."""
    features_dir = repo_root / "docs" / "spec" / "features"

    for command in _feature_verification_commands(features_dir):
        assert not command.strip().startswith("rg "), f"verification command uses rg: {command}"


def test_bundled_spec_example_uses_plan_artifact_without_subtasks(
    repo_root: Path,
) -> None:
    """Keep the hello-world feature template on bundled plan artifacts only."""
    example_path = (
        repo_root
        / "harness"
        / "fitness_functions"
        / "real_opencode_hello_world_feature_template.yaml"
    )
    example = yaml.safe_load(example_path.read_text(encoding="utf-8"))

    assert example["planning_tier"] == "planned"
    assert example["artifacts"] == {"plan": "plan.md"}
    assert "subtasks" not in example


def test_smoke_feature_template_matches_bundled_workflow(repo_root: Path) -> None:
    """Keep the smoke template aligned with the bundled feature workflow."""
    template_path = (
        repo_root
        / "harness"
        / "fitness_functions"
        / "real_opencode_hello_world_feature_template.yaml"
    )
    template = yaml.safe_load(template_path.read_text(encoding="utf-8"))

    assert template["planning_tier"] == "planned"
    assert template["artifacts"] == {"plan": "plan.md"}
    assert "subtasks" not in template


def test_bundled_plan_templates_use_runtime_status_vocabulary(repo_root: Path) -> None:
    """Keep guidance and fixtures on the active runtime status vocabulary."""
    smoke_frontmatter = load_markdown_frontmatter(
        repo_root / "docs" / "fixtures" / "real_opencode_hello_world_plan_template.md"
    )
    plan_session_doc = guidance_topic_catalog.load_guidance_topic_body("plan-session")
    smoke_phases = _load_plan_phases(smoke_frontmatter)

    assert smoke_frontmatter["status"] == "backlog"
    assert all(phase["status"] == "backlog" for phase in smoke_phases)

    assert "status: draft" not in plan_session_doc
    assert "status: ready" not in plan_session_doc
    assert "status: pending" not in plan_session_doc
    assert "status: backlog" in plan_session_doc


def test_research_session_approach_uses_bundled_research_tracking_language(
) -> None:
    """Keep research guidance aligned with bundled artifact language."""
    research_session_doc = guidance_topic_catalog.load_guidance_topic_body("research-session")

    assert "TodoWrite" not in research_session_doc
    assert "track all subtasks" not in research_session_doc
    assert "track the research areas" in research_session_doc
    assert "Parallel Sub-Agent Tasks" in research_session_doc


def test_approach_docs_use_bundled_phase_language_and_uv_run_commands(
    repo_root: Path,
) -> None:
    """Keep packaged approach docs aligned with the bundled workflow contract."""
    workflow_doc = (
        repo_root / "src" / "engineeringagent" / "approach" / "docs" / "workflow.md"
    ).read_text(encoding="utf-8")
    quality_checks_doc = (
        repo_root
        / "src"
        / "engineeringagent"
        / "approach"
        / "docs"
        / "quality-checks.md"
    ).read_text(encoding="utf-8")
    reviewer_authoring_doc = (
        repo_root
        / "src"
        / "engineeringagent"
        / "approach"
        / "docs"
        / "reviewer-authoring.md"
    ).read_text(encoding="utf-8")
    principles_doc = (
        repo_root / "src" / "engineeringagent" / "approach" / "docs" / "principles.md"
    ).read_text(encoding="utf-8")

    assert "Select one eligible feature and one eligible plan phase" in workflow_doc
    assert "subtask verification commands" not in workflow_doc
    assert "Update the bundled feature package status surfaces (`plan.md` when present, always `spec.yaml`) and `updated_at`." in workflow_doc
    assert "Update the feature YAML status and `updated_at`." not in workflow_doc
    assert "`uv run engineeringagent run --all`" in workflow_doc
    assert "`uv run engineeringagent checks run --all-phases`" in workflow_doc
    assert "`uv run engineeringagent validate --schema-only`" in workflow_doc

    assert "`uv run engineeringagent run --all`" in quality_checks_doc
    assert "`uv run engineeringagent checks run --all-phases`" in quality_checks_doc
    assert "`uv run engineeringagent validate --schema-only`" in quality_checks_doc
    assert (
        "`uv run engineeringagent checks run --checks fitness --phase iteration_end`"
        in quality_checks_doc
    )

    assert "uv run engineeringagent validate --schema-only" in reviewer_authoring_doc
    assert (
        "uv run engineeringagent checks run --phase feature_done"
        in reviewer_authoring_doc
    )

    assert (
        "most important open plan phase or feature-level implementation step"
        in principles_doc
    )
    assert "current plan phase or current implementation step" in principles_doc
    assert "current subtask" not in principles_doc


def test_specifications_doc_requires_bundled_spec_packages_only(
    repo_root: Path,
) -> None:
    """Keep the specifications guidance on bundled spec packages only."""
    specifications_doc = (
        repo_root / "src" / "engineeringagent" / "approach" / "docs" / "specifications.md"
    ).read_text(encoding="utf-8")

    assert "Create a bundled feature package rooted at `docs/spec/features/FEAT-XXX-some-header/spec.yaml`." in specifications_doc
    assert "Bundled `spec.yaml` packages are the only supported active feature layout." in specifications_doc
    assert "docs/spec/features/FEAT-XXX-some-header.yaml" not in specifications_doc
    assert "temporary compatibility shim" not in specifications_doc


def test_specifications_doc_keeps_spec_yaml_canonical_and_plan_phase_owned(
    repo_root: Path,
) -> None:
    """Keep the specifications guidance explicit about spec and plan ownership."""
    specifications_doc = (
        repo_root / "src" / "engineeringagent" / "approach" / "docs" / "specifications.md"
    ).read_text(encoding="utf-8")

    assert "Treat `spec.yaml` as the canonical source for feature identity, status, and acceptance." in specifications_doc
    assert "`plan.md` owns implementation sequencing and per-phase status" in specifications_doc
    assert "`plan.md` must not replace canonical feature status in `spec.yaml`." in specifications_doc


def test_reviewer_authoring_doc_covers_bundled_feature_review_context(
    repo_root: Path,
) -> None:
    """Keep reviewer guidance aligned with bundled feature review inputs."""
    reviewer_authoring_doc = (
        repo_root
        / "src"
        / "engineeringagent"
        / "approach"
        / "docs"
        / "reviewer-authoring.md"
    ).read_text(encoding="utf-8")

    assert "docs/spec/features/**/spec.yaml" in reviewer_authoring_doc
    assert "docs/spec/features/*.yaml" not in reviewer_authoring_doc
    assert "compatibility wrapper" not in reviewer_authoring_doc
    assert "canonical bundled package" not in reviewer_authoring_doc
    assert "`plan.md` phases" in reviewer_authoring_doc or "plan.md phases" in reviewer_authoring_doc
    assert "`research.md`" in reviewer_authoring_doc or "research.md" in reviewer_authoring_doc
