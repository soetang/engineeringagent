"""Prompt definition repository port."""

from __future__ import annotations

from string import Template
from typing import Any, Literal, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, model_validator


def _template_placeholders(template_text: str) -> tuple[str, ...]:
    names: set[str] = set()
    for match in Template.pattern.finditer(template_text):
        name = match.group("named") or match.group("braced")
        if name:
            names.add(name)
    return tuple(sorted(names))


class PromptInterpolation(BaseModel):
    """One declared prompt interpolation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    source: str
    required: bool
    render_as: Literal[
        "scalar",
        "bullet_list",
        "path_list",
        "markdown_block",
        "json_block",
        "excerpt",
        "full_document",
    ] = "scalar"
    content_policy: Literal[
        "path_only",
        "summary_only",
        "excerpt_only",
        "full_content",
    ] = "summary_only"
    content_bound: dict[str, Any] | None = None
    rationale: str


class PromptDefinition(BaseModel):
    """Stable prompt definition with explicit interpolation ownership."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt_id: str
    purpose: str
    target: Literal["implementation", "reviewer", "operator"]
    body_template: str
    interpolations: tuple[PromptInterpolation, ...]

    @model_validator(mode="after")
    def _validate_template_contract(self) -> PromptDefinition:
        declared = [item.name for item in self.interpolations]
        duplicates = sorted({name for name in declared if declared.count(name) > 1})
        if duplicates:
            duplicates_text = ", ".join(duplicates)
            raise ValueError(
                f"prompt definition {self.prompt_id!r} declares duplicate "
                f"interpolations: {duplicates_text}"
            )

        placeholders = set(_template_placeholders(self.body_template))
        undeclared = sorted(placeholders - set(declared))
        if undeclared:
            undeclared_text = ", ".join(undeclared)
            raise ValueError(
                f"prompt definition {self.prompt_id!r} uses undeclared "
                f"placeholders: {undeclared_text}"
            )
        return self

    @property
    def placeholder_names(self) -> tuple[str, ...]:
        """Return placeholders referenced by the template body."""
        return _template_placeholders(self.body_template)

    def render(self, values: Mapping[str, object]) -> str:
        """Render the template using only declared interpolations."""
        declared_names = {item.name for item in self.interpolations}
        unexpected = sorted(set(values) - declared_names)
        if unexpected:
            unexpected_text = ", ".join(unexpected)
            raise ValueError(
                f"prompt definition {self.prompt_id!r} received unexpected "
                f"interpolations: {unexpected_text}"
            )

        missing = sorted(
            item.name
            for item in self.interpolations
            if item.required and item.name not in values
        )
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(
                f"prompt definition {self.prompt_id!r} is missing required "
                f"interpolations: {missing_text}"
            )

        substitutions = {
            item.name: _coerce_prompt_value(values.get(item.name))
            for item in self.interpolations
        }
        return Template(self.body_template).substitute(substitutions)


def _coerce_prompt_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


class PromptDefinitionRepository(Protocol):
    """Load stable prompt definitions by id."""

    def get(self, prompt_id: str) -> PromptDefinition:
        """Return one prompt definition."""
        raise NotImplementedError

    def list_ids(self) -> list[str]:
        """Return available prompt definition ids."""
        raise NotImplementedError
