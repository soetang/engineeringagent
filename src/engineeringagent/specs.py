from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Annotated
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
)

from engineeringagent.domain.shared import FeatureId, FeatureStatus, PlanningTier
from engineeringagent.domain.quality import (
    HarnessCheckPhase as _HarnessCheckPhase,
    HarnessChecksDocument,
)
from engineeringagent.domain.specification.feature_specification import (
    FeatureArtifacts,
    FeaturePriority,
    FeatureType,
)
from engineeringagent import spec_bundles as _spec_bundles

JSON_SCHEMA_DRAFT_URL = "https://json-schema.org/draft/2020-12/schema"

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
FeaturePackagePaths = _spec_bundles.FeaturePackagePaths
HarnessCheckPhase = _HarnessCheckPhase
load_yaml = _spec_bundles.load_yaml
dump_yaml = _spec_bundles.dump_yaml
iter_feature_files = _spec_bundles.iter_feature_files
feature_storage_root = _spec_bundles.feature_storage_root
resolve_feature_package_paths = _spec_bundles.resolve_feature_package_paths
load_markdown_frontmatter = _spec_bundles.load_markdown_frontmatter
resolve_feature_plan_path = _spec_bundles.resolve_feature_plan_path
resolve_feature_research_path = _spec_bundles.resolve_feature_research_path
load_feature_plan_artifact = _spec_bundles.load_feature_plan_artifact
feature_progress_kind = _spec_bundles.feature_progress_kind
progress_kind_label = _spec_bundles.progress_kind_label
_is_bundled_feature_spec_path = _spec_bundles.is_bundled_feature_spec_path
_bundled_feature_artifact_issues = _spec_bundles.bundled_feature_artifact_issues


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
    """Top-level schema for docs/spec/potential_features.yaml."""

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


def feature_contract_issues(
    feature: dict[str, Any], file_path: Path
) -> list[ValidationIssue]:
    """Collect strict contract validation issues for one feature document.

    Args:
        feature: Feature mapping to validate.
        file_path: Source path used in issue reporting.

    Returns:
        Validation issues produced by strict Pydantic contract checks.
    """
    if not _is_bundled_feature_spec_path(file_path):
        return [
            ValidationIssue(
                path=str(file_path),
                message="feature specs must use bundled spec.yaml entrypoints",
            )
        ]

    issues = _model_contract_issues(
        model_type=BundledFeatureSpec,
        payload=feature,
        file_path=file_path,
    )
    if issues:
        return issues
    return [*issues, *_bundled_feature_artifact_issues(feature, file_path)]


def potential_features_contract_issues(
    document: dict[str, Any], file_path: Path
) -> list[ValidationIssue]:
    """Collect strict contract issues for potential features backlog YAML."""
    return _model_contract_issues(
        model_type=PotentialFeaturesDocument,
        payload=document,
        file_path=file_path,
    )


def checks_contract_issues(
    document: dict[str, Any], file_path: Path
) -> list[ValidationIssue]:
    """Collect strict contract issues for harness/checks.yaml."""
    return _model_contract_issues(
        model_type=HarnessChecksDocument,
        payload=document,
        file_path=file_path,
    )


def _model_contract_issues(
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


_spec_bundles.configure_spec_contracts(
    planning_tier=PlanningTier,
    build_validation_issue=ValidationIssue,
    feature_plan_artifact=FeaturePlanArtifact,
    model_contract_issues=_model_contract_issues,
)


def feature_sort_key(feature: dict[str, Any]) -> tuple[int, str]:
    """Build a deterministic sort key for feature priority.

    Args:
        feature: Feature mapping with priority and id fields.

    Returns:
        Tuple used for ascending priority and id ordering.
    """
    priority = feature.get("priority", "medium")
    return (PRIORITY_ORDER.get(priority, 1), str(feature.get("id", "")))
