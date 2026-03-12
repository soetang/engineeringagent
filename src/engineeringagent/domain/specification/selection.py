"""Specification-domain helpers for deterministic feature selection."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .feature_specification import FeatureSelectionCandidate

STATUS_ORDER: dict[str, int] = {
    "in_progress": 0,
    "backlog": 1,
    "blocked": 2,
}

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def deterministic_feature_choice(
    pending: Sequence[tuple[Path, FeatureSelectionCandidate]],
) -> tuple[Path, FeatureSelectionCandidate]:
    """Choose a deterministic feature when selector output is unavailable."""

    def sort_key(
        item: tuple[Path, FeatureSelectionCandidate],
    ) -> tuple[int, int, str, str]:
        feature_path, feature = item
        status_rank = STATUS_ORDER.get(feature.status.value, 99)
        priority_rank = PRIORITY_ORDER.get(feature.priority.value, 1)
        feature_id = feature.feature_id
        return (status_rank, priority_rank, feature_id, str(feature_path))

    return sorted(pending, key=sort_key)[0]


def parse_selector_output(
    output: str,
    pending: Sequence[tuple[Path, FeatureSelectionCandidate]],
) -> Path | None:
    """Parse selector output into one of the pending feature paths."""
    text = output.strip()
    if not text:
        return None

    matched_path = _match_selector_path_fragment(text, pending)
    if matched_path is not None:
        return matched_path

    token_indexes = _build_selector_token_indexes(pending)
    tokens = _selector_tokens(text)
    for token in tokens:
        matched_path = _unique_index_match(token_indexes, token)
        if matched_path is not None:
            return matched_path
    return None


def _match_selector_path_fragment(
    text: str,
    pending: Sequence[tuple[Path, FeatureSelectionCandidate]],
) -> Path | None:
    for path, _feature in pending:
        if str(path) in text:
            return path
    return None


def _build_selector_token_indexes(
    pending: Sequence[tuple[Path, FeatureSelectionCandidate]],
) -> dict[str, dict[str, list[Path]]]:
    by_name: dict[str, list[Path]] = {}
    by_parent_name: dict[str, list[Path]] = {}
    by_id: dict[str, list[Path]] = {}
    for path, feature in pending:
        by_name.setdefault(path.name, []).append(path)
        if path.name == "spec.yaml":
            by_parent_name.setdefault(path.parent.name, []).append(path)
        feature_id = feature.feature_id.strip()
        if feature_id:
            by_id.setdefault(feature_id, []).append(path)
    return {
        "by_name": by_name,
        "by_parent_name": by_parent_name,
        "by_id": by_id,
    }


def _selector_tokens(text: str) -> list[str]:
    return [token.strip("`'\" ,") for token in text.replace("\n", " ").split(" ")]


def _unique_index_match(
    token_indexes: dict[str, dict[str, list[Path]]],
    token: str,
) -> Path | None:
    for index_name in ("by_name", "by_parent_name", "by_id"):
        matches = token_indexes[index_name].get(token, [])
        if len(matches) == 1:
            return matches[0]
    return None
