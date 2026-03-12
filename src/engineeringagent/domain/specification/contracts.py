from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from engineeringagent.domain.quality import HarnessChecksDocument
from engineeringagent.domain.shared import (
    FeatureId,
    FeatureStatus,
    JSON_SCHEMA_DRAFT_URL,
    PlanningTier,
)

from .feature_specification import FeatureArtifacts, FeaturePriority, FeatureType

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

NonEmptyStr = Annotated[str, Field(strict=True, min_length=1)]
StrictString = Annotated[str, Field(strict=True)]
CommitSubject = Annotated[
    str,
    Field(
        strict=True,
        pattern=r"^(feat|fix|spec|docs|chore|test): [^\n]+$",
    ),
]


class StrictContractModel(BaseModel):
    """Pydantic base model that forbids unknown fields."""

    model_config = ConfigDict(extra="forbid")


class PotentialFeatureStatus(str, Enum):
    """Lifecycle status for a potential feature entry."""

    IDEA = "idea"


PotentialFeatureId = Annotated[
    str, Field(strict=True, min_length=1, pattern=r"^POT-[0-9]{3,}$")
]


class PotentialFeatureSpec(StrictContractModel):
    """One entry in the potential features backlog document."""

    id: PotentialFeatureId
    title: NonEmptyStr
    status: PotentialFeatureStatus
    context: StrictString | None = None
    value: list[StrictString] | None = None
    acceptance_hint: list[StrictString] | None = None


class PotentialFeaturesDocument(StrictContractModel):
    """Top-level schema for docs/specifications/potential_features.yaml."""

    version: Annotated[int, Field(strict=True, ge=1)]
    description: StrictString | None = None
    potential_features: list[PotentialFeatureSpec] = Field(default_factory=list)


class BundledFeatureSpec(StrictContractModel):
    """Top-level schema for bundled docs/specifications/features/<feature>/spec.yaml."""

    model_config = ConfigDict(extra="forbid", title="Agent Harness Bundled Feature")

    id: FeatureId
    title: NonEmptyStr
    type: FeatureType
    expected_commit_subject: CommitSubject
    planning_tier: PlanningTier
    status: FeatureStatus
    priority: FeaturePriority
    objective: NonEmptyStr
    context: StrictString | None = None
    constraints: list[StrictString] | None = None
    implementation_notes: StrictString | None = None
    acceptance: Annotated[list[StrictString], Field(min_length=1)]
    artifacts: FeatureArtifacts
    updated_at: StrictString | None = None


class PlanPhaseArtifact(StrictContractModel):
    """Structured plan phase metadata stored in plan.md frontmatter."""

    id: NonEmptyStr
    title: NonEmptyStr
    status: StrictString
    verification: list[StrictString] | None = None


class FeaturePlanArtifact(StrictContractModel):
    """Required plan.md frontmatter for bundled planned/researched features."""

    plan_id: NonEmptyStr
    feature_id: FeatureId
    status: StrictString
    source_spec: StrictString
    source_research: StrictString | None = None
    planning_tier: PlanningTier
    phases: Annotated[list[PlanPhaseArtifact], Field(min_length=1)]


class ValidationIssue(StrictContractModel):
    """One contract validation issue emitted by strict model checks."""

    path: str
    message: str


def feature_schema_from_model() -> dict[str, Any]:
    """Return feature schema generated from the Pydantic feature model."""
    schema = BundledFeatureSpec.model_json_schema(mode="validation")
    schema["$schema"] = JSON_SCHEMA_DRAFT_URL
    return schema


def checks_schema_from_model() -> dict[str, Any]:
    """Return harness checks schema generated from the Pydantic checks model."""
    schema = HarnessChecksDocument.model_json_schema(mode="validation")
    schema["$schema"] = JSON_SCHEMA_DRAFT_URL
    return schema


def _path_from_pydantic_loc(loc: tuple[Any, ...]) -> str:
    """Convert a Pydantic error location tuple into a dotted path."""
    parts: list[str] = []
    for segment in loc:
        if isinstance(segment, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{segment}]"
            else:
                parts.append(f"[{segment}]")
            continue
        parts.append(str(segment))
    if not parts:
        return "<root>"
    return ".".join(parts).replace(".[", "[")


def model_contract_issues(
    model_type: type[BaseModel],
    payload: dict[str, Any],
    file_path: Path,
) -> list[ValidationIssue]:
    """Collect deterministic issues produced by strict model validation."""
    try:
        model_type.model_validate(payload)
    except ValidationError as exc:
        issues: list[ValidationIssue] = []
        errors = sorted(
            exc.errors(include_url=False),
            key=lambda err: _path_from_pydantic_loc(tuple(err.get("loc", ()))),
        )
        for error in errors:
            path = _path_from_pydantic_loc(tuple(error.get("loc", ())))
            issues.append(
                ValidationIssue(
                    path=f"{file_path}:{path}",
                    message=str(error.get("msg", "invalid value")),
                )
            )
        return issues
    return []


def feature_model_contract_issues(
    feature: dict[str, Any],
    file_path: Path,
) -> list[ValidationIssue]:
    """Collect strict model-only contract validation issues for one feature document."""
    return model_contract_issues(
        model_type=BundledFeatureSpec,
        payload=feature,
        file_path=file_path,
    )


def potential_features_contract_issues(
    document: dict[str, Any], file_path: Path
) -> list[ValidationIssue]:
    """Collect strict contract issues for potential features backlog YAML."""
    return model_contract_issues(
        model_type=PotentialFeaturesDocument,
        payload=document,
        file_path=file_path,
    )


def checks_contract_issues(
    document: dict[str, Any], file_path: Path
) -> list[ValidationIssue]:
    """Collect strict contract issues for harness/checks.yaml."""
    return model_contract_issues(
        model_type=HarnessChecksDocument,
        payload=document,
        file_path=file_path,
    )


def feature_sort_key(feature: dict[str, Any]) -> tuple[int, str]:
    """Build a deterministic sort key for feature priority."""
    priority = feature.get("priority", "medium")
    return (PRIORITY_ORDER.get(priority, 1), str(feature.get("id", "")))
