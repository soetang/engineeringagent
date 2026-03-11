from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from engineeringagent.adapters.prompts import (
    FilesystemPromptDefinitionRepository,
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
        "from pydantic import BaseModel\n"
        "from engineeringagent.ports import PromptDefinition, PromptInterpolation\n"
        "class SelectorInput(BaseModel):\n"
        "    choices: str\n"
        "PROMPT_DEFINITION = PromptDefinition(\n"
        "    prompt_id='loop_selector',\n"
        "    purpose='selector',\n"
        "    target='operator',\n"
        "    output_mode='text',\n"
        "    token_budget_hint=100,\n"
        "    input_model=SelectorInput,\n"
        "    body_template='selector: $choices',\n"
        "    interpolations=(PromptInterpolation(\n"
        "        name='choices', source='test', required=True, rationale='test'),),\n"
        ")\n",
    )
    _write_prompt_module(
        prompts_root,
        "loop_feedback",
        "from pydantic import BaseModel\n"
        "from engineeringagent.ports import PromptDefinition, PromptInterpolation\n"
        "class FeedbackInput(BaseModel):\n"
        "    feedback: str\n"
        "PROMPT_DEFINITION = PromptDefinition(\n"
        "    prompt_id='loop_feedback',\n"
        "    purpose='feedback',\n"
        "    target='implementation',\n"
        "    output_mode='text',\n"
        "    token_budget_hint=100,\n"
        "    input_model=FeedbackInput,\n"
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
        "from pydantic import BaseModel\n"
        "from engineeringagent.ports import PromptDefinition, PromptInterpolation\n"
        "class SelectorInput(BaseModel):\n"
        "    choices: str\n"
        "PROMPT_DEFINITION = PromptDefinition(\n"
        "    prompt_id='loop_selector',\n"
        "    purpose='selector',\n"
        "    target='operator',\n"
        "    output_mode='text',\n"
        "    token_budget_hint=100,\n"
        "    input_model=SelectorInput,\n"
        "    body_template='repo selector',\n"
        "    interpolations=(PromptInterpolation(\n"
        "        name='choices', source='test', required=True, rationale='test'),),\n"
        ")\n",
    )

    prompt = FilesystemPromptDefinitionRepository(prompts_root).get("loop_selector")

    assert prompt.prompt_id == "loop_selector"
    assert prompt.body_template == "repo selector"
    assert prompt.input_model.__name__ == "SelectorInput"
    assert [item.name for item in prompt.interpolations] == ["choices"]


def test_filesystem_prompt_definition_repository_rejects_unknown_prompt_id(
    tmp_path: Path,
) -> None:
    """Filesystem prompt repositories fail clearly for unknown prompt ids."""

    repository = FilesystemPromptDefinitionRepository(tmp_path / "missing-prompts")

    with pytest.raises(KeyError, match="unknown prompt definition"):
        repository.get("missing-prompt")


def test_filesystem_prompt_definition_repository_rejects_unloadable_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filesystem prompt repositories fail clearly when importlib returns no loader."""

    prompts_root = tmp_path / "prompts"
    prompts_root.mkdir()
    _write_prompt_module(prompts_root, "loop_selector", "PROMPT_DEFINITION = object()\n")

    monkeypatch.setattr(
        "engineeringagent.adapters.prompts.filesystem_prompt_definition_repository.importlib.util.spec_from_file_location",
        lambda *_args, **_kwargs: SimpleNamespace(loader=None),
    )

    with pytest.raises(KeyError, match="failed to load prompt definition module"):
        FilesystemPromptDefinitionRepository(prompts_root).get("loop_selector")


def test_filesystem_prompt_definition_repository_requires_prompt_definition_export(
    tmp_path: Path,
) -> None:
    """Filesystem prompt repositories require PROMPT_DEFINITION exports."""

    prompts_root = tmp_path / "prompts"
    prompts_root.mkdir()
    _write_prompt_module(prompts_root, "loop_selector", "VALUE = 'missing'\n")

    with pytest.raises(KeyError, match="must export PROMPT_DEFINITION"):
        FilesystemPromptDefinitionRepository(prompts_root).get("loop_selector")


def test_prompt_definition_render_rejects_undeclared_interpolations(
    tmp_path: Path,
) -> None:
    """Prompt rendering should fail when callers pass undeclared values."""

    prompts_root = tmp_path / "prompts"
    prompts_root.mkdir()
    _write_prompt_module(
        prompts_root,
        "loop_selector",
        "from pydantic import BaseModel\n"
        "from engineeringagent.ports import PromptDefinition, PromptInterpolation\n"
        "class SelectorInput(BaseModel):\n"
        "    choices: str\n"
        "PROMPT_DEFINITION = PromptDefinition(\n"
        "    prompt_id='loop_selector',\n"
        "    purpose='selector',\n"
        "    target='operator',\n"
        "    output_mode='text',\n"
        "    token_budget_hint=100,\n"
        "    input_model=SelectorInput,\n"
        "    body_template='$choices',\n"
        "    interpolations=(PromptInterpolation(\n"
        "        name='choices', source='test', required=True, rationale='test'),),\n"
        ")\n",
    )

    prompt = FilesystemPromptDefinitionRepository(prompts_root).get("loop_selector")

    with pytest.raises(ValueError, match="unexpected interpolations"):
        prompt.render({"choices": "ok", "extra": "nope"})
