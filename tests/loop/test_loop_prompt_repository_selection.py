from __future__ import annotations

from pathlib import Path

from engineeringagent.prompts import build_implementation_prompt, build_selector_prompt


def test_selector_prompt_prefers_repo_local_template(tmp_path: Path) -> None:
    """Selector prompt rendering uses repository-local templates when available."""

    prompts_root = tmp_path / "harness" / "prompts"
    prompts_root.mkdir(parents=True)
    (prompts_root / "loop_selector.md").write_text(
        "repo selector\n$choices\n",
        encoding="utf-8",
    )

    prompt = build_selector_prompt(
        [(tmp_path / "feature.yaml", {"id": "FEAT-100", "status": "backlog"})],
        project_root=tmp_path,
    )

    assert prompt.startswith("repo selector\n")


def test_implementation_prompt_prefers_repo_local_template(tmp_path: Path) -> None:
    """Implementation prompt rendering uses repository-local prompt overrides."""

    prompts_root = tmp_path / "harness" / "prompts"
    prompts_root.mkdir(parents=True)
    (prompts_root / "loop_implementation.md").write_text(
        "repo implementation\n$feature_id\n$artifact_paths\n",
        encoding="utf-8",
    )
    (prompts_root / "loop_feedback.md").write_text(
        "\n\nRepo feedback:\n$feedback\n",
        encoding="utf-8",
    )
    feature_path = tmp_path / "docs" / "features" / "spec.yaml"
    feature_path.parent.mkdir(parents=True)
    feature_path.write_text("id: FEAT-101\n", encoding="utf-8")

    prompt = build_implementation_prompt(
        feature={"id": "FEAT-101"},
        feature_path=feature_path,
        feedback="retry",
        project_root=tmp_path,
    )

    assert prompt.startswith("repo implementation\nFEAT-101\n")
    assert "Repo feedback:\nretry" in prompt
