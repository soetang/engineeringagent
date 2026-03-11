"""Specification-domain models for bundled feature packages."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

NonEmptyStr = Annotated[str, Field(strict=True, min_length=1)]
StrictString = Annotated[str, Field(strict=True)]


class FeatureStatus(str, Enum):
    """Lifecycle status for a feature specification."""

    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class FeaturePriority(str, Enum):
    """Priority bucket used when selecting work."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FeatureType(str, Enum):
    """Work category represented by a feature specification."""

    FEATURE = "feature"
    BUG = "bug"
    SPEC = "spec"
    DOCS = "docs"
    CHORE = "chore"
    TEST = "test"


class PlanningTier(str, Enum):
    """Planning depth required by the selected feature."""

    DIRECT = "direct"
    PLANNED = "planned"
    RESEARCHED = "researched"


class FeatureArtifacts(BaseModel):
    """Artifact references declared by a bundled feature specification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan: StrictString | None = None
    research: StrictString | None = None
    supporting: tuple[StrictString, ...] = ()


class FeatureSpecification(BaseModel):
    """Typed feature specification used by application services and ports."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_id: NonEmptyStr
    title: NonEmptyStr
    feature_type: FeatureType
    expected_commit_subject: NonEmptyStr
    planning_tier: PlanningTier
    status: FeatureStatus
    priority: FeaturePriority
    objective: NonEmptyStr
    context: StrictString | None = None
    constraints: tuple[StrictString, ...] = ()
    implementation_notes: StrictString | None = None
    acceptance: tuple[StrictString, ...]
    artifacts: FeatureArtifacts
    updated_at: StrictString | None = None


class FeatureSelectionCandidate(BaseModel):
    """One selection candidate derived from the active spec catalog."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_id: NonEmptyStr
    status: FeatureStatus
    priority: FeaturePriority
    planning_tier: PlanningTier
    next_phase_id: StrictString | None = None
    phase_dependencies_satisfied: bool
    block_reason_code: StrictString | None = None
