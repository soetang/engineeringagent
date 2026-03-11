"""Shared-kernel identifier value types."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

FeatureId = Annotated[str, Field(strict=True, min_length=1)]
PhaseId = Annotated[str, Field(strict=True, min_length=1)]
CheckId = Annotated[str, Field(strict=True, min_length=1)]
TopicId = Annotated[str, Field(strict=True, min_length=1)]
