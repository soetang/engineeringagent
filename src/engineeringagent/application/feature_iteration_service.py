"""Application service for feature-iteration execution requests."""

from __future__ import annotations

from typing import Callable

from engineeringagent.application.feature_iteration_runtime import (
    FeatureIterationRequest,
    FeatureIterationResult,
)

FeatureIterationWorkflow = Callable[[FeatureIterationRequest], FeatureIterationResult]


class FeatureIterationService:
    """Own feature-iteration sequencing behind a stable application contract."""

    def __init__(
        self,
        *,
        workflow: FeatureIterationWorkflow,
    ) -> None:
        self._workflow = workflow

    def run(self, request: FeatureIterationRequest) -> FeatureIterationResult:
        """Execute one feature iteration through the runtime pipeline."""
        return self._workflow(request)
