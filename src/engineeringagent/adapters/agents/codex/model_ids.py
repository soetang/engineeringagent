from __future__ import annotations

OPENAI_PROVIDER_PREFIX = "openai/"


def normalize_codex_model_id(value: str) -> str:
    """Normalize model ids for Codex CLI compatibility."""
    normalized = value.strip()
    if normalized.startswith(OPENAI_PROVIDER_PREFIX):
        stripped = normalized[len(OPENAI_PROVIDER_PREFIX) :]
        if stripped:
            return stripped
    return normalized
