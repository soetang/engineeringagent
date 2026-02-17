from __future__ import annotations

import json
from typing import Any, Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


CONTRACT_VERSION = "1.0"

NonEmptyStr = Annotated[str, Field(strict=True, min_length=1)]
SingleLineStr = Annotated[str, Field(strict=True, min_length=1, pattern=r"^[^\r\n]+$")]

RuleId = Annotated[
    str,
    Field(
        strict=True,
        min_length=3,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    ),
]


MAX_FAILED_RULES = 25
MAX_RULE_VIOLATIONS = 50
MAX_REQUIRED_ACTIONS = 20


class RetryFeedbackModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RerunInstructions(RetryFeedbackModel):
    cwd: Literal["repo_root"]
    instructions: NonEmptyStr


class CommandFailureRetryFeedbackEnvelope(RetryFeedbackModel):
    kind: Literal["command_failure"]
    phase: Literal["gates", "verification", "completion_commit"]
    message: NonEmptyStr

    gate: NonEmptyStr | None = None
    precommit: Annotated[bool, Field(strict=True)] = False
    command: SingleLineStr
    rerun: RerunInstructions


class FailedFitnessRule(RetryFeedbackModel):
    rule_id: RuleId
    status: Literal["fail"]
    remediation: NonEmptyStr
    violations: Annotated[
        list[NonEmptyStr], Field(default_factory=list, max_length=MAX_RULE_VIOLATIONS)
    ]
    details: dict[str, Any] | None = None


class FitnessFailureRetryFeedbackEnvelope(RetryFeedbackModel):
    kind: Literal["fitness_failure"]
    phase: Literal["gates"]
    message: NonEmptyStr

    gate: NonEmptyStr | None = None
    command: SingleLineStr
    failed_rules: Annotated[
        list[FailedFitnessRule],
        Field(default_factory=list, max_length=MAX_FAILED_RULES),
    ]


class ReviewerDecisionPayload(RetryFeedbackModel):
    decision: Literal["approve", "request_changes", "warning"]
    summary: NonEmptyStr
    required_actions: Annotated[
        list[NonEmptyStr],
        Field(default_factory=list, max_length=MAX_REQUIRED_ACTIONS),
    ]
    scope_notes: NonEmptyStr | None = None


class ReviewerFeedbackRetryEnvelope(RetryFeedbackModel):
    kind: Literal["reviewer_feedback"]
    phase: Literal["reviewers"]
    message: NonEmptyStr

    reviewer_id: Annotated[str, Field(strict=True, min_length=1, max_length=64)]
    reviewer_phase: Literal["iteration_end", "feature_done"]
    decision: ReviewerDecisionPayload


RetryFeedbackEnvelope: TypeAlias = (
    CommandFailureRetryFeedbackEnvelope
    | FitnessFailureRetryFeedbackEnvelope
    | ReviewerFeedbackRetryEnvelope
)


RetryFeedbackEnvelopeDiscriminated: TypeAlias = Annotated[
    RetryFeedbackEnvelope,
    Field(discriminator="kind"),
]


_RETRY_FEEDBACK_ENVELOPE_ADAPTER = TypeAdapter(RetryFeedbackEnvelopeDiscriminated)


def parse_retry_feedback_envelope(payload: object) -> RetryFeedbackEnvelope:
    """Parse and validate a v1 retry-feedback envelope.

    Args:
        payload: A decoded JSON object or a Python mapping.

    Returns:
        Validated retry-feedback envelope.
    """
    if isinstance(payload, str):
        return _RETRY_FEEDBACK_ENVELOPE_ADAPTER.validate_json(payload)

    return _RETRY_FEEDBACK_ENVELOPE_ADAPTER.validate_python(payload)


def serialize_retry_feedback_envelope(envelope: RetryFeedbackEnvelope) -> str:
    """Serialize a retry-feedback envelope as strict deterministic JSON.

    The output is intended for prompt injection:
    - one JSON object
    - compact (no newlines)
    - sorted keys for deterministic prompts
    - ASCII-only
    """
    payload = envelope.model_dump(mode="json", exclude_none=True)
    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
