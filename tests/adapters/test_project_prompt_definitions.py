from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.adapters.prompts import (
    FilesystemPromptDefinitionRepository,
    ProjectPromptDefinitionRepository,
)


def test_filesystem_prompt_definition_repository_lists_markdown_templates(
    tmp_path: Path,
) -> None:
    """Filesystem prompt repositories expose stable markdown prompt ids."""

    prompts_root = tmp_path / "prompts"
    prompts_root.mkdir()
    (prompts_root / "loop_selector.md").write_text("selector", encoding="utf-8")
    (prompts_root / "loop_feedback.md").write_text("feedback", encoding="utf-8")

    repository = FilesystemPromptDefinitionRepository(prompts_root)

    assert repository.list_ids() == ["loop_feedback", "loop_selector"]


def test_filesystem_prompt_definition_repository_loads_template_text(
    tmp_path: Path,
) -> None:
    """Filesystem prompt repositories return renderable prompt definitions."""

    prompts_root = tmp_path / "prompts"
    prompts_root.mkdir()
    (prompts_root / "loop_selector.md").write_text("repo selector", encoding="utf-8")

    prompt = FilesystemPromptDefinitionRepository(prompts_root).get("loop_selector")

    assert prompt.prompt_id == "loop_selector"
    assert prompt.body_template == "repo selector"
    assert [item.name for item in prompt.interpolations] == ["choices"]


def test_project_prompt_definition_repository_prefers_repo_prompt_templates(
    tmp_path: Path,
) -> None:
    """Project prompt repositories prefer repository-local prompt templates."""

    prompts_root = tmp_path / "harness" / "prompts"
    prompts_root.mkdir(parents=True)
    (prompts_root / "loop_selector.md").write_text(
        "repo override: $choices",
        encoding="utf-8",
    )

    repository = ProjectPromptDefinitionRepository(tmp_path)

    assert (
        repository.get("loop_selector").render({"choices": "- id=FEAT-100"})
        == "repo override: - id=FEAT-100"
    )


def test_project_prompt_definition_repository_falls_back_to_bundled_templates(
    tmp_path: Path,
) -> None:
    """Project prompt repositories keep bundled defaults when repo prompts are absent."""

    repository = ProjectPromptDefinitionRepository(tmp_path)

    prompt = repository.get("loop_selector")

    assert prompt.prompt_id == "loop_selector"
    assert prompt.placeholder_names == ("choices",)


def test_project_prompt_definition_repository_lists_repo_and_bundled_ids(
    tmp_path: Path,
) -> None:
    """Project prompt repositories expose the union of repo and bundled ids."""

    prompts_root = tmp_path / "harness" / "prompts"
    prompts_root.mkdir(parents=True)
    (prompts_root / "custom_prompt.md").write_text("custom", encoding="utf-8")

    repository = ProjectPromptDefinitionRepository(tmp_path)

    assert repository.list_ids() == [
        "custom_prompt",
        "loop_feedback",
        "loop_implementation",
        "loop_selector",
    ]


def test_filesystem_prompt_definition_repository_rejects_unknown_prompt_id(
    tmp_path: Path,
) -> None:
    """Filesystem prompt repositories fail clearly for unknown prompt ids."""

    repository = FilesystemPromptDefinitionRepository(tmp_path / "missing-prompts")

    with pytest.raises(KeyError, match="unknown prompt definition"):
        repository.get("missing-prompt")


def test_prompt_definition_render_rejects_undeclared_interpolations(
    tmp_path: Path,
) -> None:
    """Prompt rendering should fail when callers pass undeclared values."""

    prompts_root = tmp_path / "prompts"
    prompts_root.mkdir()
    (prompts_root / "loop_selector.md").write_text("$choices", encoding="utf-8")

    prompt = FilesystemPromptDefinitionRepository(prompts_root).get("loop_selector")

    with pytest.raises(ValueError, match="unexpected interpolations"):
        prompt.render({"choices": "ok", "extra": "nope"})
