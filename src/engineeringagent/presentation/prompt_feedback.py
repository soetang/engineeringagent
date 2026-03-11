from __future__ import annotations


CHECKS_FAILURE_FALLBACK = "checks failed"


def format_command_failure_output_excerpt(output: str, *, max_lines: int = 20) -> str:
    """Build a bounded, deterministic excerpt from failed command output."""
    normalized = (output or "").strip()
    if not normalized:
        return "(no output)"

    lines = normalized.splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[-max_lines:])


def format_command_return_code(value: int | str | None) -> str:
    """Normalize command return-code values for deterministic feedback blocks."""
    if value is None:
        return "unknown"
    normalized = str(value).strip()
    return normalized if normalized else "unknown"


def format_failed_command_feedback_lines(
    *,
    command: str,
    return_code: int | str | None,
    failure_output: object | None,
) -> list[str]:
    """Build normalized feedback lines for failed command diagnostics."""
    normalized_output = failure_output if isinstance(failure_output, str) else ""
    lines = [
        f"- command: `{command}`",
        f"- returncode: {format_command_return_code(return_code)}",
        "- failure_output_excerpt:",
    ]
    lines.extend(
        f"  {entry}"
        for entry in format_command_failure_output_excerpt(
            normalized_output
        ).splitlines()
    )
    return lines


def normalize_prompt_feedback(value: str | None) -> str | None:
    """Return stripped prompt feedback or None for blank/non-string input."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def resolve_prompt_feedback(
    value: str | None,
    *,
    fallback: str | None = None,
) -> str | None:
    """Return normalized prompt feedback, optionally falling back to a default."""
    normalized = normalize_prompt_feedback(value)
    if normalized is not None:
        return normalized
    return normalize_prompt_feedback(fallback)


def normalize_checks_prompt_feedback(
    value: str | None,
    *,
    fallback_on_empty: bool,
) -> str | None:
    """Normalize checks result prompt feedback for API/loop consumers."""
    return resolve_prompt_feedback(
        value,
        fallback=CHECKS_FAILURE_FALLBACK if fallback_on_empty else None,
    )


def normalize_checks_contract_prompt_feedback(value: str | None) -> str | None:
    """Normalize checks prompt feedback for the checks result contract."""

    return normalize_checks_prompt_feedback(value, fallback_on_empty=False)


def resolve_checks_prompt_feedback(value: str | None) -> str | None:
    """Normalize checks feedback, falling back to deterministic text."""

    return normalize_checks_prompt_feedback(value, fallback_on_empty=True)
