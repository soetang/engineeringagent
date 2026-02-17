from __future__ import annotations

from collections.abc import Iterable, Mapping

from .contracts import (
    CommandFailureRetryFeedbackEnvelope,
    FailedFitnessRule,
    FitnessFailureRetryFeedbackEnvelope,
    ReviewerDecisionPayload,
    ReviewerFeedbackRetryEnvelope,
    RerunInstructions,
    MAX_FAILED_RULES,
    MAX_REQUIRED_ACTIONS,
    MAX_RULE_VIOLATIONS,
    serialize_retry_feedback_envelope,
)


_RERUN_INSTRUCTIONS = RerunInstructions(
    cwd="repo_root",
    instructions="Run the command exactly as shown from the repository root.",
)


def build_command_failure_retry_feedback(
    *,
    phase: str,
    command: str,
    gate: str | None = None,
    precommit: bool = False,
    message: str | None = None,
) -> str:
    """Build a serialized command_failure retry-feedback envelope.

    The returned JSON string is intended to be injected directly into the next
    implement prompt. It is validated against the strict v1 contract.
    """
    header = (
        message or "Command check failed. Rerun the command to see full diagnostics."
    )
    envelope = CommandFailureRetryFeedbackEnvelope(
        kind="command_failure",
        phase=phase,  # type: ignore[arg-type]
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
    """Build a serialized fitness_failure retry-feedback envelope.

    `failed_rules` is expected to contain failures-only entries (pass noise
    filtered out by construction).
    """
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
    reviewer_phase: str,
    decision: Mapping[str, object],
    message: str | None = None,
) -> str:
    """Build a serialized reviewer_feedback retry-feedback envelope.

    Reviewer feedback must be forwarded as strict JSON so the next implement pass
    receives deterministic, schema-validated context.
    """

    decision_name_raw = decision.get("decision")
    decision_name = (
        decision_name_raw
        if isinstance(decision_name_raw, str) and decision_name_raw.strip()
        else "request_changes"
    )
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
        reviewer_phase=reviewer_phase,  # type: ignore[arg-type]
        decision=ReviewerDecisionPayload(
            decision=decision_name,  # type: ignore[arg-type]
            summary=summary,
            required_actions=required_actions,
            scope_notes=scope_notes,
        ),
        message=header,
    )
    return serialize_retry_feedback_envelope(envelope)
