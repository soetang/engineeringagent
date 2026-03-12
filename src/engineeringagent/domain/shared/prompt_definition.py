"""Pure prompt-definition contracts shared across the product."""

from __future__ import annotations

from string import Template
from typing import Any, Callable, Literal, Mapping

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

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    prompt_id: str
    purpose: str
    target: Literal["implementation", "reviewer", "operator"]
    output_mode: Literal["text", "structured"]
    token_budget_hint: int
    input_model: type[BaseModel]
    output_model: type[BaseModel] | None = None
    body_template: str | None = None
    renderer: Callable[[BaseModel], str] | None = None
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

        if self.body_template is None and self.renderer is None:
            raise ValueError(
                f"prompt definition {self.prompt_id!r} must define either "
                "body_template or renderer"
            )

        if self.body_template is not None and self.renderer is not None:
            raise ValueError(
                f"prompt definition {self.prompt_id!r} must not define both "
                "body_template and renderer"
            )

        if self.body_template is not None:
            placeholders = set(_template_placeholders(self.body_template))
            undeclared = sorted(placeholders - set(declared))
            if undeclared:
                undeclared_text = ", ".join(undeclared)
                raise ValueError(
                    f"prompt definition {self.prompt_id!r} uses undeclared "
                    f"placeholders: {undeclared_text}"
                )
        if self.token_budget_hint <= 0:
            raise ValueError(
                f"prompt definition {self.prompt_id!r} must define a positive "
                "token_budget_hint"
            )
        if self.output_mode == "structured" and self.output_model is None:
            raise ValueError(
                f"prompt definition {self.prompt_id!r} must define output_model "
                "when output_mode='structured'"
            )
        return self

    @property
    def placeholder_names(self) -> tuple[str, ...]:
        """Return placeholders referenced by the template body."""
        if self.body_template is not None:
            return _template_placeholders(self.body_template)
        return tuple(sorted(item.name for item in self.interpolations))

    def render(self, values: BaseModel | Mapping[str, object]) -> str:
        """Render the template using only declared interpolations."""
        value_mapping: Mapping[str, object]
        if isinstance(values, BaseModel):
            value_mapping = values.model_dump(mode="python")
        else:
            value_mapping = values

        declared_names = {item.name for item in self.interpolations}
        unexpected = sorted(set(value_mapping) - declared_names)
        if unexpected:
            unexpected_text = ", ".join(unexpected)
            raise ValueError(
                f"prompt definition {self.prompt_id!r} received unexpected "
                f"interpolations: {unexpected_text}"
            )

        missing = sorted(
            item.name
            for item in self.interpolations
            if item.required and item.name not in value_mapping
        )
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(
                f"prompt definition {self.prompt_id!r} is missing required "
                f"interpolations: {missing_text}"
            )

        input_data = self.input_model.model_validate(value_mapping)
        normalized_values = input_data.model_dump(mode="python")
        if self.renderer is not None:
            return self.renderer(input_data)
        substitutions = {
            item.name: _coerce_prompt_value(normalized_values.get(item.name))
            for item in self.interpolations
        }
        assert self.body_template is not None
        return Template(self.body_template).substitute(substitutions)


def _coerce_prompt_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)
