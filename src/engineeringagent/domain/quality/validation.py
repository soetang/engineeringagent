from __future__ import annotations

from typing import NamedTuple

from typing_extensions import Literal


class ValidationIssue(NamedTuple):
    """Canonical quality-domain validation issue."""

    validator_id: str
    scope: Literal["repo", "strategy"]
    path: str
    message: str
    code: str
