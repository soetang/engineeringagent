"""Application-owned iteration report publishing seam."""

from __future__ import annotations

from typing import Callable, TypeAlias

from .contracts import IterationOutcome, IterationReport

IterationReportPublisher: TypeAlias = Callable[[IterationReport], IterationOutcome]
