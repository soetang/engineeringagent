from __future__ import annotations

from typing import cast

from pydantic import ValidationError

from engineeringagent.domain.quality import (
    CommandFailureFeedbackEnvelope,
    CommandFailurePhase,
    RerunInstructions,
    parse_feedback_envelope,
)

FEEDBACK_ENVELOPE_PREVIOUS_FEATURE_CONTEXT_MARKER = (
    " Previous feedback is available. Fix the issues reported below before marking "
    "the feature complete:\n"
)


def parse_feedback_envelope_from_prompt(
    prompt: str,
    *,
    phase: CommandFailurePhase,
) -> CommandFailureFeedbackEnvelope:
    depth = 0
    start = None
    for index, char in enumerate(prompt):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                candidate = prompt[start : index + 1]
                try:
                    envelope = parse_feedback_envelope(candidate)
                except (ValidationError, ValueError):
                    start = None
                else:
                    if envelope.kind == "command_failure":
                        return cast(CommandFailureFeedbackEnvelope, envelope)
                    start = None
    feedback = prompt.split(
        FEEDBACK_ENVELOPE_PREVIOUS_FEATURE_CONTEXT_MARKER, 1
    )[-1].strip()
    if not feedback:
        raise AssertionError("No feedback envelope found in prompt")
    command_line = next(
        (line for line in feedback.splitlines() if line.lstrip().startswith("- command:")),
        None,
    )
    if command_line is None:
        raise AssertionError(
            f"Feedback payload is not a command_failure envelope: {feedback!r}"
        )
    command = command_line.strip().removeprefix("- command:").strip().strip("`")
    return CommandFailureFeedbackEnvelope(
        kind="command_failure",
        phase=phase,
        command=command,
        message=feedback,
        rerun=RerunInstructions(
            cwd="repo_root",
            instructions="Run the command exactly as shown from the repository root.",
        ),
    )
