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
        "implementation_default",
        "from pydantic import BaseModel\n"
        "from engineeringagent.ports import PromptDefinition, PromptInterpolation\n"
        "class ImplementationInput(BaseModel):\n"
        "    feature_id: str\n"
        "    specification_path: str\n"
        "PROMPT_DEFINITION = PromptDefinition(\n"
        "    prompt_id='implementation_default',\n"
        "    purpose='implementation',\n"
        "    target='implementation',\n"
        "    output_mode='structured',\n"
        "    token_budget_hint=100,\n"
        "    input_model=ImplementationInput,\n"
        "    output_model=ImplementationInput,\n"
        "    body_template='implementation: $feature_id $specification_path',\n"
        "    interpolations=(\n"
        "        PromptInterpolation(name='feature_id', source='test', required=True, rationale='test'),\n"
        "        PromptInterpolation(name='specification_path', source='test', required=True, rationale='test'),\n"
        "    ),\n"
        ")\n",
    )

    repository = FilesystemPromptDefinitionRepository(prompts_root)

    assert repository.list_ids() == ["implementation_default", "loop_selector"]


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
