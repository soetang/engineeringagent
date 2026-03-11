from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from engineeringagent.application import (
    ImplementationPromptFeature,
    ImplementationPromptRequest,
    PromptArtifactPaths,
)
from engineeringagent.ports import PromptBuilder


def test_prompt_builder_protocol_default_method_raises() -> None:
    """The prompt-builder protocol stays non-callable without implementation."""

    with pytest.raises(NotImplementedError):
        PromptBuilder.build_implementation_prompt(  # type: ignore[misc]
            cast(Any, object()),
            ImplementationPromptRequest(
                feature=ImplementationPromptFeature(feature_id="FEAT-1"),
                artifacts=PromptArtifactPaths(specification=Path("spec.yaml")),
                handoff_path=None,
                feedback=None,
                progress_kind="feature",
            ),
        )
