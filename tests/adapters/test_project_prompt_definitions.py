from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.adapters.prompts import (
    FilesystemPromptDefinitionRepository,
    ProjectPromptDefinitionRepository,
)


def _write_prompt_module(prompts_root: Path, prompt_id: str, body: str) -> None:
    (prompts_root / f"{prompt_id}.py").write_text(body, encoding="utf-8")


def test_filesystem_prompt_definition_repository_lists_python_modules(
    tmp_path: Path,
) -> None:
    """Filesystem prompt repositories expose stable Python prompt ids."""

    prompts_root = tmp_path / "prompts"
    prompts_root.mkdir()
    _write_prompt_module(
        prompts_root,
        "loop_selector",
        "from engineeringagent.ports import PromptDefinition, PromptInterpolation\n"
        "PROMPT_DEFINITION = PromptDefinition(\n"
        "    prompt_id='loop_selector',\n"
        "    purpose='selector',\n"
        "    target='operator',\n"
        "    body_template='selector: $choices',\n"
        "    interpolations=(PromptInterpolation(\n"
        "        name='choices', source='test', required=True, rationale='test'),),\n"
        ")\n",
    )
    _write_prompt_module(
        prompts_root,
        "loop_feedback",
        "from engineeringagent.ports import PromptDefinition, PromptInterpolation\n"
        "PROMPT_DEFINITION = PromptDefinition(\n"
        "    prompt_id='loop_feedback',\n"
        "    purpose='feedback',\n"
        "    target='implementation',\n"
        "    body_template='feedback: $feedback',\n"
        "    interpolations=(PromptInterpolation(\n"
        "        name='feedback', source='test', required=True, rationale='test'),),\n"
        ")\n",
    )

    repository = FilesystemPromptDefinitionRepository(prompts_root)

    assert repository.list_ids() == ["loop_feedback", "loop_selector"]


def test_filesystem_prompt_definition_repository_loads_template_text(
    tmp_path: Path,
) -> None:
    """Filesystem prompt repositories return renderable prompt definitions."""

    prompts_root = tmp_path / "prompts"
    prompts_root.mkdir()
    _write_prompt_module(
        prompts_root,
        "loop_selector",
        "from engineeringagent.ports import PromptDefinition, PromptInterpolation\n"
        "PROMPT_DEFINITION = PromptDefinition(\n"
        "    prompt_id='loop_selector',\n"
        "    purpose='selector',\n"
        "    target='operator',\n"
        "    body_template='repo selector',\n"
        "    interpolations=(PromptInterpolation(\n"
        "        name='choices', source='test', required=True, rationale='test'),),\n"
        ")\n",
    )

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
    _write_prompt_module(
        prompts_root,
        "loop_selector",
        "from engineeringagent.ports import PromptDefinition, PromptInterpolation\n"
        "PROMPT_DEFINITION = PromptDefinition(\n"
        "    prompt_id='loop_selector',\n"
        "    purpose='selector',\n"
        "    target='operator',\n"
        "    body_template='repo override: $choices',\n"
        "    interpolations=(PromptInterpolation(\n"
        "        name='choices', source='test', required=True, rationale='test'),),\n"
        ")\n",
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
    _write_prompt_module(
        prompts_root,
        "custom_prompt",
        "from engineeringagent.ports import PromptDefinition\n"
        "PROMPT_DEFINITION = PromptDefinition(\n"
        "    prompt_id='custom_prompt',\n"
        "    purpose='custom',\n"
        "    target='operator',\n"
        "    renderer=lambda values: 'custom',\n"
        "    interpolations=(),\n"
        ")\n",
    )

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
    _write_prompt_module(
        prompts_root,
        "loop_selector",
        "from engineeringagent.ports import PromptDefinition, PromptInterpolation\n"
        "PROMPT_DEFINITION = PromptDefinition(\n"
        "    prompt_id='loop_selector',\n"
        "    purpose='selector',\n"
        "    target='operator',\n"
        "    body_template='$choices',\n"
        "    interpolations=(PromptInterpolation(\n"
        "        name='choices', source='test', required=True, rationale='test'),),\n"
        ")\n",
    )

    prompt = FilesystemPromptDefinitionRepository(prompts_root).get("loop_selector")

    with pytest.raises(ValueError, match="unexpected interpolations"):
        prompt.render({"choices": "ok", "extra": "nope"})
