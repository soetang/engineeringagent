from __future__ import annotations

from collections.abc import Mapping
from typing import Any


FEATURE_TYPE_COMMIT_PREFIX: dict[str, str] = {
    "feature": "feat",
    "bug": "fix",
    "spec": "spec",
    "docs": "docs",
    "chore": "chore",
    "test": "test",
}


def feature_completion_commit_subject(feature: Mapping[str, Any]) -> str:
    """Return the completion commit subject for a feature."""

    expected_subject = str(feature.get("expected_commit_subject", "")).strip()
    if expected_subject:
        return expected_subject

    feature_id = str(feature.get("id", "unknown-feature"))
    title = str(feature.get("title", "")).strip()
    feature_type = str(feature.get("type", "feature")).strip()
    prefix = FEATURE_TYPE_COMMIT_PREFIX.get(feature_type, "feat")
    message = f"{prefix}: complete {feature_id}"
    if title:
        message = f"{message} - {title}"
    return message
