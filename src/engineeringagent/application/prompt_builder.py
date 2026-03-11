"""Application service for deterministic prompt assembly."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence, TypeVar

from engineeringagent.domain.specification.feature_specification import (
    FeatureArtifacts,
    FeaturePriority,
    FeatureSpecification,
    FeatureStatus,
    FeatureType,
    PlanningTier,
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
        feature: Mapping[str, object] | FeatureSpecification,
        specification_path: Path,
        feedback: str | None,
        handoff_path: str | None = None,
    ) -> ImplementationPromptRequest:
        """Resolve explicit application prompt inputs from feature artifacts."""

        specification = _coerce_feature_specification(feature)
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

    def build_implementation_prompt_from_specification(
        self,
        *,
        specification: FeatureSpecification,
        specification_path: Path,
        feedback: str | None,
        handoff_path: str | None = None,
    ) -> str:
        """Render the implementation prompt from typed specification inputs."""

        request = self.build_implementation_prompt_request(
            feature=specification,
            specification_path=specification_path,
            feedback=feedback,
            handoff_path=handoff_path,
        )
        return self.build_implementation_prompt(request)

    def build_implementation_prompt_from_feature(
        self,
        *,
        feature: Mapping[str, object] | FeatureSpecification,
        feature_path: Path,
        feedback: str | None,
        handoff_path: str | None = None,
    ) -> str:
        """Render the implementation prompt from the current feature state."""

        request = self.build_implementation_prompt_request(
            feature=feature,
            specification_path=feature_path,
            feedback=feedback,
            handoff_path=handoff_path,
        )
        return self.build_implementation_prompt(request)

    def build_selector_prompt(
        self,
        pending: Sequence[tuple[Path, Mapping[str, object]]],
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


def _resolved_artifact_reference(
    specification_path: Path,
    artifact_reference: str | None,
) -> str | None:
    if artifact_reference is None:
        return None
    normalized = artifact_reference.strip()
    if not normalized:
        return None
    return str(specification_path.parent / normalized)


EnumT = TypeVar("EnumT", bound=Enum)


def _normalize_feedback(feedback: str | None) -> str:
    """Normalize feedback for prompt injection."""
    normalized = _normalize_plain_prompt_feedback(feedback)
    return normalized or ""


def _normalize_plain_prompt_feedback(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _coerce_feature_specification(
    feature: Mapping[str, object] | FeatureSpecification,
) -> FeatureSpecification:
    if isinstance(feature, FeatureSpecification):
        return feature

    artifacts = feature.get("artifacts")
    feature_id = _first_non_empty_str(
        feature,
        "feature_id",
        "id",
        default="unknown-feature",
    )
    title = _first_non_empty_str(feature, "title", default=feature_id)
    return FeatureSpecification(
        feature_id=feature_id,
        title=title,
        feature_type=_coerce_enum(
            feature.get("feature_type", feature.get("type")),
            FeatureType,
            FeatureType.FEATURE,
        ),
        expected_commit_subject=_first_non_empty_str(
            feature,
            "expected_commit_subject",
            default="feat: implement unknown-feature",
        ),
        planning_tier=_coerce_enum(
            feature.get("planning_tier"),
            PlanningTier,
            PlanningTier.DIRECT,
        ),
        status=_coerce_enum(
            feature.get("status"),
            FeatureStatus,
            FeatureStatus.BACKLOG,
        ),
        priority=_coerce_enum(
            feature.get("priority"),
            FeaturePriority,
            FeaturePriority.HIGH,
        ),
        objective=_first_non_empty_str(feature, "objective", default=title),
        context=_optional_str(feature.get("context")),
        constraints=_string_tuple(feature.get("constraints")),
        implementation_notes=_optional_str(feature.get("implementation_notes")),
        acceptance=_string_tuple(feature.get("acceptance")),
        artifacts=_coerce_artifacts(artifacts),
        updated_at=_optional_str(feature.get("updated_at")),
    )


def _coerce_artifacts(value: object) -> FeatureArtifacts:
    if not isinstance(value, Mapping):
        return FeatureArtifacts()
    return FeatureArtifacts(
        plan=_optional_str(value.get("plan")),
        research=_optional_str(value.get("research")),
        supporting=_string_tuple(value.get("supporting")),
    )


def _optional_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _first_non_empty_str(
    values: Mapping[str, object],
    *keys: str,
    default: str,
) -> str:
    for key in keys:
        value = _optional_str(values.get(key))
        if value is not None:
            return value
    return default


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(
        normalized
        for item in value
        if (normalized := _optional_str(item)) is not None
    )


def _coerce_enum(value: object, enum_type: type[EnumT], default: EnumT) -> EnumT:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            try:
                return enum_type(normalized)
            except ValueError:
                return default
    return default
