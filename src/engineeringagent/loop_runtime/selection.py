"""Loop runtime feature selection helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Sequence

from engineeringagent.adapters.prompts import FilesystemPromptDefinitionRepository
from engineeringagent.agents import (
    AgentBackendError,
    classify_backend_exception,
    describe_action,
)
from engineeringagent.application import build_selector_prompt
from engineeringagent.config import resolve_harness_root
from engineeringagent.specs import feature_sort_key

STATUS_ORDER: dict[str, int] = {
    "in_progress": 0,
    "backlog": 1,
    "blocked": 2,
}


def deterministic_feature_choice(
    pending: Sequence[tuple[Path, dict[str, Any]]],
) -> tuple[Path, dict[str, Any]]:
    """Choose a deterministic feature when selector output is unavailable."""

    def sort_key(item: tuple[Path, dict[str, Any]]) -> tuple[int, int, str, str]:
        feature_path, feature = item
        status_rank = STATUS_ORDER.get(str(feature.get("status", "")), 99)
        priority_rank, feature_id = feature_sort_key(feature)
        return (status_rank, priority_rank, feature_id, str(feature_path))

    return sorted(pending, key=sort_key)[0]


def parse_selector_output(
    output: str,
    pending: Sequence[tuple[Path, dict[str, Any]]],
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
    pending: Sequence[tuple[Path, dict[str, Any]]],
) -> Path | None:
    for path, _feature in pending:
        if str(path) in text:
            return path
    return None


def _build_selector_token_indexes(
    pending: Sequence[tuple[Path, dict[str, Any]]],
) -> dict[str, dict[str, list[Path]]]:
    by_name: dict[str, list[Path]] = {}
    by_parent_name: dict[str, list[Path]] = {}
    by_id: dict[str, list[Path]] = {}
    for path, feature in pending:
        by_name.setdefault(path.name, []).append(path)
        if path.name == "spec.yaml":
            by_parent_name.setdefault(path.parent.name, []).append(path)
        feature_id = str(feature.get("id", "")).strip()
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


def choose_feature_with_selector(
    project_root: Path,
    pending: Sequence[tuple[Path, dict[str, Any]]],
    *,
    run_agent_fn: Callable[[Path, str], str],
    parse_selector_output_fn: Callable[
        [str, Sequence[tuple[Path, dict[str, Any]]]],
        Path | None,
    ] = parse_selector_output,
    deterministic_feature_choice_fn: Callable[
        [Sequence[tuple[Path, dict[str, Any]]]],
        tuple[Path, dict[str, Any]],
    ] = deterministic_feature_choice,
) -> tuple[Path, dict[str, Any]]:
    """Choose a feature using selector output with deterministic fallback."""
    if len(pending) == 1:
        return pending[0]

    prompt = build_selector_prompt(
        pending,
        prompt_definitions=FilesystemPromptDefinitionRepository(
            resolve_harness_root(project_root) / "prompts"
        ),
    )
    step_label = describe_action(project_root, action="selector", structured=False)
    print(f"Selector step: {step_label}")
    try:
        output = run_agent_fn(project_root, prompt)
    except (FileNotFoundError, AgentBackendError) as exc:
        failed_gate, _message = classify_backend_exception(exc)
        fallback = deterministic_feature_choice_fn(pending)
        print(f"Selector fallback: {failed_gate}; selected {fallback[1].get('id')}")
        return fallback

    chosen_path = parse_selector_output_fn(output, pending)
    if chosen_path is not None:
        chosen_feature = next(
            feature for path, feature in pending if path == chosen_path
        )
        return (chosen_path, chosen_feature)

    fallback = deterministic_feature_choice_fn(pending)
    print(f"Selector fallback: selector_parse; selected {fallback[1].get('id')}")
    return fallback
