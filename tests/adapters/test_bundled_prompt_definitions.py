from __future__ import annotations

import pytest

from engineeringagent.adapters.prompts import BundledPromptDefinitionRepository


def test_bundled_prompt_definition_repository_lists_stable_prompt_ids() -> None:
    """Expose the packaged prompt ids through the repository port."""
    repository = BundledPromptDefinitionRepository()

    assert repository.list_ids() == [
        "loop_feedback",
        "loop_implementation",
        "loop_selector",
    ]


def test_bundled_prompt_definition_repository_loads_template_text() -> None:
    """Load packaged prompt definitions through the adapter."""
    repository = BundledPromptDefinitionRepository()

    prompt = repository.get("loop_selector")

    assert prompt.prompt_id == "loop_selector"
    assert prompt.target == "operator"
    assert prompt.placeholder_names == ("choices",)
    assert prompt.render({"choices": "- id=FEAT-100 path=docs/spec.yaml"}).startswith(
        "Choose the next feature spec"
    )


def test_bundled_prompt_definition_repository_rejects_unknown_prompt_id() -> None:
    """Raise a deterministic error for unknown prompt ids."""
    repository = BundledPromptDefinitionRepository()

    with pytest.raises(KeyError, match="unknown prompt definition"):
        repository.get("missing-prompt")
