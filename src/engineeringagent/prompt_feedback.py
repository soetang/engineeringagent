from __future__ import annotations


CHECKS_FAILURE_FALLBACK = "checks failed"


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
