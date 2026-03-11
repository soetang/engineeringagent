"""Application service for deterministic prompt assembly."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from engineeringagent.domain.specification import (
    resolve_feature_plan_path,
    resolve_feature_research_path,
)
from engineeringagent.ports import PromptDefinitionRepository

from .prompt_models import (
    ImplementationPromptRequest,
)


class PromptBuilder:
    """Deterministic prompt builder backed by prompt definitions."""

    def __init__(self, prompt_definitions: PromptDefinitionRepository) -> None:
        self._prompt_definitions = prompt_definitions

    def build_implementation_prompt_request(
        self,
        *,
        feature: Mapping[str, Any],
        feature_path: Path,
        feedback: str | None,
        handoff_path: str | None = None,
    ) -> ImplementationPromptRequest:
        """Resolve explicit application prompt inputs from feature artifacts."""

        feature_payload = dict(feature)
        return ImplementationPromptRequest(
            feature_id=_feature_id(feature_payload),
            specification_path=feature_path,
            plan_path=_resolved_plan_reference(feature_path, feature_payload),
            research_path=_resolved_research_reference(feature_path, feature_payload),
            handoff_path=handoff_path,
            retry_feedback=_normalize_plain_prompt_feedback(feedback),
        )

    def build_implementation_prompt(self, request: ImplementationPromptRequest) -> str:
        """Render the implementation prompt for one iteration."""
        implementation_definition = self._prompt_definitions.get(
            "implementation_default"
        )
        return implementation_definition.render(
            {
                "feature_id": request.feature_id,
                "specification_path": str(request.specification_path),
                "plan_path": request.plan_path or "",
                "research_path": request.research_path or "",
                "handoff_path": request.handoff_path or "",
                "retry_feedback": _normalize_feedback(request.retry_feedback),
            }
        )

    def build_implementation_prompt_from_feature(
        self,
        *,
        feature: Mapping[str, Any],
        feature_path: Path,
        feedback: str | None,
        handoff_path: str | None = None,
    ) -> str:
        """Render the implementation prompt from feature-owned inputs."""

        request = self.build_implementation_prompt_request(
            feature=feature,
            feature_path=feature_path,
            feedback=feedback,
            handoff_path=handoff_path,
        )
        return self.build_implementation_prompt(request)

    def build_selector_prompt(
        self,
        pending: Sequence[tuple[Path, Mapping[str, Any]]],
    ) -> str:
        """Render the selector prompt from deterministic feature summaries."""

        choices = []
        for feature_path, feature in pending:
            choices.append(
                f"- id={feature.get('id')} status={feature.get('status')} "
                f"priority={feature.get('priority')} path={feature_path}"
            )

        selector_definition = self._prompt_definitions.get("loop_selector")
        return selector_definition.render(
            {
                "choices": "\n".join(choices),
            }
        )


def _resolved_plan_reference(
    feature_path: Path,
    feature: Mapping[str, Any],
) -> str | None:
    artifact_path = resolve_feature_plan_path(feature_path, dict(feature))
    if artifact_path is None:
        return None
    return str(artifact_path)


def _resolved_research_reference(
    feature_path: Path,
    feature: Mapping[str, Any],
) -> str | None:
    artifact_path = resolve_feature_research_path(feature_path, dict(feature))
    if artifact_path is None:
        return None
    return str(artifact_path)


def _normalize_feedback(feedback: str | None) -> str:
    """Normalize feedback for prompt injection."""
    normalized = _normalize_plain_prompt_feedback(feedback)
    return normalized or ""


def _normalize_plain_prompt_feedback(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _feature_id(feature: Mapping[str, Any]) -> str:
    value = feature.get("id")
    if isinstance(value, str) and value.strip():
        return value
    return "unknown-feature"
