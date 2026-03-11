from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


CONTRACT_VERSION = "1.0"

CommandFailurePhase: TypeAlias = Literal["gates", "verification", "completion_commit"]
ReviewerPhase: TypeAlias = Literal["iteration_end", "feature_done"]
ReviewerDecisionName: TypeAlias = Literal["approve", "request_changes"]

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


class FeedbackModel(BaseModel):
    """Base model for feedback envelopes emitted by runtime flows."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RerunInstructions(FeedbackModel):
    """Instructions for how a contributor should rerun a failing command."""

    cwd: Literal["repo_root"]
    instructions: NonEmptyStr


class CommandFailureFeedbackEnvelope(FeedbackModel):
    """Envelope describing a failing command check during loop execution."""

    kind: Literal["command_failure"]
    phase: CommandFailurePhase
    message: NonEmptyStr

    gate: NonEmptyStr | None = None
    precommit: Annotated[bool, Field(strict=True)] = False
    command: SingleLineStr
    rerun: RerunInstructions


class FailedFitnessRule(FeedbackModel):
    """Serialized representation of a failed fitness rule."""

    rule_id: RuleId
    status: Literal["fail"]
    remediation: NonEmptyStr
    violations: Annotated[
        list[NonEmptyStr], Field(default_factory=list, max_length=MAX_RULE_VIOLATIONS)
    ]
    details: dict[str, Any] | None = None


class FitnessFailureFeedbackEnvelope(FeedbackModel):
    """Envelope describing one or more failing fitness rules."""

    kind: Literal["fitness_failure"]
    phase: Literal["gates"]
    message: NonEmptyStr

    gate: NonEmptyStr | None = None
    command: SingleLineStr
    failed_rules: Annotated[
        list[FailedFitnessRule],
        Field(default_factory=list, max_length=MAX_FAILED_RULES),
    ]


class ReviewerDecisionPayload(FeedbackModel):
    """Reviewer decision payload embedded in feedback."""

    decision: ReviewerDecisionName
    summary: NonEmptyStr
    required_actions: Annotated[
        list[NonEmptyStr],
        Field(default_factory=list, max_length=MAX_REQUIRED_ACTIONS),
    ]
    scope_notes: NonEmptyStr | None = None


class ReviewerFeedbackEnvelope(FeedbackModel):
    """Envelope capturing reviewer feedback for a failed iteration."""

    kind: Literal["reviewer_feedback"]
    phase: Literal["reviewers"]
    message: NonEmptyStr

    reviewer_id: Annotated[str, Field(strict=True, min_length=1, max_length=64)]
    reviewer_phase: ReviewerPhase
    decision: ReviewerDecisionPayload


FeedbackEnvelope: TypeAlias = (
    CommandFailureFeedbackEnvelope
    | FitnessFailureFeedbackEnvelope
    | ReviewerFeedbackEnvelope
)


FeedbackEnvelopeDiscriminated: TypeAlias = Annotated[
    FeedbackEnvelope,
    Field(discriminator="kind"),
]


_FEEDBACK_ENVELOPE_ADAPTER = TypeAdapter(FeedbackEnvelopeDiscriminated)


def parse_feedback_envelope(payload: object) -> FeedbackEnvelope:
    """Parse and validate a v1 feedback envelope."""
    if isinstance(payload, str):
        return _FEEDBACK_ENVELOPE_ADAPTER.validate_json(payload)

    return _FEEDBACK_ENVELOPE_ADAPTER.validate_python(payload)


def serialize_feedback_envelope(envelope: FeedbackEnvelope) -> str:
    """Serialize a feedback envelope as strict deterministic JSON."""
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


def build_command_failure_feedback(
    *,
    phase: CommandFailurePhase,
    command: str,
    gate: str | None = None,
    precommit: bool = False,
    message: str | None = None,
) -> str:
    """Build a serialized command_failure feedback envelope."""
    header = (
        message or "Command check failed. Rerun the command to see full diagnostics."
    )
    envelope = CommandFailureFeedbackEnvelope(
        kind="command_failure",
        phase=phase,
        gate=gate,
        precommit=precommit,
        command=command,
        rerun=_RERUN_INSTRUCTIONS,
        message=header,
    )
    return serialize_feedback_envelope(envelope)


def build_fitness_failure_feedback(
    *,
    gate: str | None,
    command: str,
    failed_rules: Iterable[Mapping[str, object]],
    message: str | None = None,
) -> str:
    """Build a serialized fitness_failure feedback envelope."""
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

    envelope = FitnessFailureFeedbackEnvelope(
        kind="fitness_failure",
        phase="gates",
        gate=gate,
        command=command,
        failed_rules=normalized_rules,
        message=header,
    )
    return serialize_feedback_envelope(envelope)


def build_reviewer_feedback(
    *,
    reviewer_id: str,
    reviewer_phase: ReviewerPhase,
    decision: Mapping[str, object],
    message: str | None = None,
) -> str:
    """Build a serialized reviewer_feedback envelope."""
    decision_name_raw = decision.get("decision")
    decision_name: ReviewerDecisionName
    if decision_name_raw == "approve":
        decision_name = "approve"
    else:
        decision_name = "request_changes"
    summary_raw = decision.get("summary")
    summary = (
        summary_raw
        if isinstance(summary_raw, str) and summary_raw.strip()
        else "(no summary)"
    )
    scope_notes_raw = decision.get("scope_notes")
    scope_notes = (
        scope_notes_raw
        if isinstance(scope_notes_raw, str) and scope_notes_raw.strip()
        else None
    )
    required_actions: list[str] = []
    required_actions_raw = decision.get("required_actions", [])
    if isinstance(required_actions_raw, list):
        for value in required_actions_raw:
            if not isinstance(value, str):
                continue
            normalized = value.strip()
            if not normalized:
                continue
            required_actions.append(normalized)
            if len(required_actions) >= MAX_REQUIRED_ACTIONS:
                break

    envelope = ReviewerFeedbackEnvelope(
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
        message=message or _default_reviewer_message(decision_name),
    )
    return serialize_feedback_envelope(envelope)


def _default_reviewer_message(decision_name: ReviewerDecisionName) -> str:
    if decision_name == "approve":
        return "Reviewer approved the changes."
    return "Reviewer requested changes."
