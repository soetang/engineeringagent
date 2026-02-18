from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


CONTRACT_VERSION = "1.0"

CommandFailurePhase: TypeAlias = Literal["gates", "verification", "completion_commit"]
ReviewerPhase: TypeAlias = Literal["iteration_end", "feature_done"]
ReviewerDecisionName: TypeAlias = Literal["approve", "request_changes", "warning"]

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
    phase: CommandFailurePhase
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
    decision: ReviewerDecisionName
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
    reviewer_phase: ReviewerPhase
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


_RERUN_INSTRUCTIONS = RerunInstructions(
    cwd="repo_root",
    instructions="Run the command exactly as shown from the repository root.",
)


def build_command_failure_retry_feedback(
    *,
    phase: CommandFailurePhase,
    command: str,
    gate: str | None = None,
    precommit: bool = False,
    message: str | None = None,
) -> str:
    """Build a serialized command_failure retry-feedback envelope."""
    header = (
        message or "Command check failed. Rerun the command to see full diagnostics."
    )
    envelope = CommandFailureRetryFeedbackEnvelope(
        kind="command_failure",
        phase=phase,
        gate=gate,
        precommit=precommit,
        command=command,
        rerun=_RERUN_INSTRUCTIONS,
        message=header,
    )
    return serialize_retry_feedback_envelope(envelope)


def build_fitness_failure_retry_feedback(
    *,
    gate: str | None,
    command: str,
    failed_rules: Iterable[Mapping[str, object]],
    message: str | None = None,
) -> str:
    """Build a serialized fitness_failure retry-feedback envelope."""
    header = (
        message or "Fitness rule(s) failed. Apply remediation and rerun the command."
    )
    normalized_rules: list[FailedFitnessRule] = []
    for entry in failed_rules:
        if len(normalized_rules) >= MAX_FAILED_RULES:
            break
        rule_id = entry.get("rule_id")
        remediation = entry.get("remediation")
        violations_raw = entry.get("violations", [])
        details_raw = entry.get("details")
        if not isinstance(rule_id, str) or not isinstance(remediation, str):
            continue
        violations: list[str] = []
        if isinstance(violations_raw, list):
            for value in violations_raw:
                if isinstance(value, str) and value.strip():
                    violations.append(value)
                if len(violations) >= MAX_RULE_VIOLATIONS:
                    break
        details = details_raw if isinstance(details_raw, dict) else None
        normalized_rules.append(
            FailedFitnessRule(
                rule_id=rule_id,
                status="fail",
                remediation=remediation,
                violations=violations,
                details=details,
            )
        )

    envelope = FitnessFailureRetryFeedbackEnvelope(
        kind="fitness_failure",
        phase="gates",
        gate=gate,
        command=command,
        failed_rules=normalized_rules,
        message=header,
    )
    return serialize_retry_feedback_envelope(envelope)


def build_reviewer_feedback_retry_feedback(
    *,
    reviewer_id: str,
    reviewer_phase: ReviewerPhase,
    decision: Mapping[str, object],
    message: str | None = None,
) -> str:
    """Build a serialized reviewer_feedback retry-feedback envelope."""

    decision_name_raw = decision.get("decision")
    decision_name: ReviewerDecisionName
    if decision_name_raw == "approve":
        decision_name = "approve"
    elif decision_name_raw == "warning":
        decision_name = "warning"
    else:
        decision_name = "request_changes"
    summary_raw = decision.get("summary")
    summary = (
        summary_raw
        if isinstance(summary_raw, str) and summary_raw.strip()
        else "(no summary)"
    )

    required_actions_raw = decision.get("required_actions", [])
    required_actions: list[str] = []
    if isinstance(required_actions_raw, list):
        for item in required_actions_raw:
            if isinstance(item, str) and item.strip():
                required_actions.append(item.strip())
            if len(required_actions) >= MAX_REQUIRED_ACTIONS:
                break

    scope_notes_raw = decision.get("scope_notes")
    scope_notes = (
        scope_notes_raw.strip()
        if isinstance(scope_notes_raw, str) and scope_notes_raw.strip()
        else None
    )

    header = message
    if not header:
        if decision_name == "warning":
            header = "Reviewer provided warning feedback. Address any required actions before completing."
        else:
            header = (
                "Reviewer requested changes. Apply required actions before completing."
            )

    envelope = ReviewerFeedbackRetryEnvelope(
        kind="reviewer_feedback",
        phase="reviewers",
        reviewer_id=reviewer_id,
        reviewer_phase=reviewer_phase,
        decision=ReviewerDecisionPayload(
            decision=decision_name,
            summary=summary,
            required_actions=required_actions,
            scope_notes=scope_notes,
        ),
        message=header,
    )
    return serialize_retry_feedback_envelope(envelope)
