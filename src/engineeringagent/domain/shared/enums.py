"""Shared-kernel enums and literals."""

from __future__ import annotations

from enum import Enum

BackendId = str


class FeatureStatus(str, Enum):
    """Lifecycle status for a feature specification."""

    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class PlanningTier(str, Enum):
    """Planning depth required by the selected feature."""

    DIRECT = "direct"
    PLANNED = "planned"
    RESEARCHED = "researched"


class CheckPhase(str, Enum):
    """Execution phase for harness checks."""

    ITERATION_END = "iteration_end"
    FEATURE_DONE = "feature_done"
    MANUAL = "manual"


class ReviewDecision(str, Enum):
    """Canonical reviewer decision names."""

    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    COMMENT = "comment"
