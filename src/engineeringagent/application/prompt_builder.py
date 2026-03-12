"""Application service for deterministic prompt assembly."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from engineeringagent.domain.specification.feature_specification import FeatureSpecification
from engineeringagent.ports import PromptDefinitionRepository


class ImplementationPromptRequest(BaseModel):
    """Typed input for implementation prompt rendering."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_id: str
    specification_path: Path
    plan_path: Path | None = None
    research_path: Path | None = None
    handoff_path: Path | str | None = None
    retry_feedback: str | None = None


class PromptBuilder:
    """Deterministic prompt builder backed by prompt definitions."""

    def __init__(
        self,
        prompt_definitions: PromptDefinitionRepository,
        *,
        implementation_prompt_id: str = "implementation_default",
    ) -> None:
        self._prompt_definitions = prompt_definitions
        self._implementation_prompt_id = implementation_prompt_id

    def build_implementation_prompt_request(
        self,
        *,
        specification: FeatureSpecification,
        specification_path: Path,
        feedback: str | None,
        handoff_path: str | None = None,
    ) -> ImplementationPromptRequest:
        """Resolve explicit application prompt inputs from feature artifacts."""

        return ImplementationPromptRequest(
            feature_id=specification.feature_id,
            specification_path=specification_path,
            plan_path=_resolved_artifact_reference(
                specification_path,
                specification.artifacts.plan,
            ),
            research_path=_resolved_artifact_reference(
                specification_path,
                specification.artifacts.research,
            ),
            handoff_path=handoff_path,
            retry_feedback=_normalize_plain_prompt_feedback(feedback),
        )

    def build_implementation_prompt(self, request: ImplementationPromptRequest) -> str:
        """Render the implementation prompt for one iteration."""
        implementation_definition = self._prompt_definitions.get(
            self._implementation_prompt_id
        )
        prompt_values: dict[str, str] = {
            "feature_id": request.feature_id,
            "specification_path": str(request.specification_path),
        }
        if request.plan_path is not None:
            prompt_values["plan_path"] = str(request.plan_path)
        if request.research_path is not None:
            prompt_values["research_path"] = str(request.research_path)
        if request.handoff_path is not None:
            prompt_values["handoff_path"] = str(request.handoff_path)
        normalized_feedback = _normalize_feedback(request.retry_feedback)
        if normalized_feedback:
            prompt_values["retry_feedback"] = normalized_feedback
        return implementation_definition.render(prompt_values)

def _resolved_artifact_reference(
    specification_path: Path, artifact_reference: str | None
) -> Path | None:
    if artifact_reference is None:
        return None
    normalized = artifact_reference.strip()
    if not normalized:
        return None
    return specification_path.parent / normalized


def _normalize_feedback(feedback: str | None) -> str:
    """Normalize feedback for prompt injection."""
    normalized = _normalize_plain_prompt_feedback(feedback)
    return normalized or ""


def _normalize_plain_prompt_feedback(value: str | None) -> str | None:
    """Trim plain retry feedback and collapse blanks to None."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None
