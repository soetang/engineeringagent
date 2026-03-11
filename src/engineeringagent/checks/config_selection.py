from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from engineeringagent.checks.config_loader import load_harness_checks_document
from engineeringagent.checks.request_normalization import (
    CHECK_GROUP_COMMANDS,
    CHECK_GROUP_FITNESS,
    CHECK_GROUP_REVIEWERS,
    HARNESS_GROUPS,
    _NormalizedRunChecksRequest,
)
from engineeringagent.specs import (
    HarnessCheckCommandDefinition,
    HarnessCheckFitnessDefinition,
    HarnessCheckReviewerDefinition,
    HarnessChecksDocument,
)


class ChecksConfigSelectionError(BaseModel):
    """Deterministic error returned when config load/selection fails."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group: str
    check_id: str | None
    output: str
    payload: dict[str, Any] | None


def needs_harness_checks_document(ordered_groups: tuple[str, ...]) -> bool:
    """Return whether any selected checks group requires checks.yaml."""
    return any(group in HARNESS_GROUPS for group in ordered_groups)


def _resolve_check_group_for_id(
    doc: HarnessChecksDocument, check_id: str
) -> str | None:
    check = doc.checks.get(check_id)
    if isinstance(check, HarnessCheckCommandDefinition):
        return CHECK_GROUP_COMMANDS
    if isinstance(check, HarnessCheckFitnessDefinition):
        return CHECK_GROUP_FITNESS
    if isinstance(check, HarnessCheckReviewerDefinition):
        return CHECK_GROUP_REVIEWERS
    return None


def _filter_doc_to_check_id(
    doc: HarnessChecksDocument, check_id: str
) -> HarnessChecksDocument:
    check = doc.checks.get(check_id)
    if check is None:
        return doc
    return doc.model_copy(update={"checks": {check_id: check}})


def load_selected_harness_checks_document(
    project_root: Path,
    *,
    request: _NormalizedRunChecksRequest,
) -> tuple[HarnessChecksDocument | None, ChecksConfigSelectionError | None]:
    """Load checks config and apply optional check-id selection."""
    if not needs_harness_checks_document(request.ordered_groups):
        if request.check_id is not None:
            output = "unknown check_id: no harness checks document loaded"
            return (
                None,
                ChecksConfigSelectionError(
                    group="selection",
                    check_id=request.check_id,
                    output=output,
                    payload={
                        "kind": "selection_error",
                        "message": output,
                        "check_id": request.check_id,
                    },
                ),
            )
        return None, None

    doc, doc_error = load_harness_checks_document(
        project_root,
        error_prefix="checks config error",
    )
    if doc_error is not None:
        return (
            None,
            ChecksConfigSelectionError(
                group="config",
                check_id=request.check_id,
                output=doc_error,
                payload={
                    "kind": "config_error",
                    "message": doc_error,
                },
            ),
        )
    if doc is None:
        output = "checks config error: failed to load checks configuration"
        return (
            None,
            ChecksConfigSelectionError(
                group="config",
                check_id=request.check_id,
                output=output,
                payload={
                    "kind": "config_error",
                    "message": output,
                },
            ),
        )

    if request.check_id is None:
        return doc, None

    resolved_group = _resolve_check_group_for_id(doc, request.check_id)
    if resolved_group is None or resolved_group not in request.ordered_groups:
        enabled = [group for group in request.ordered_groups if group in HARNESS_GROUPS]
        output = (
            "unknown check_id for enabled groups: "
            f"check_id={request.check_id} enabled_groups={enabled}"
        )
        return (
            None,
            ChecksConfigSelectionError(
                group="selection",
                check_id=request.check_id,
                output=output,
                payload={
                    "kind": "selection_error",
                    "message": output,
                    "check_id": request.check_id,
                },
            ),
        )

    return _filter_doc_to_check_id(doc, request.check_id), None
