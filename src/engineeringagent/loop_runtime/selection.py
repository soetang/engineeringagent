"""Loop runtime feature selection helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Sequence

from engineeringagent.opencode.client import DEFAULT_OPENCODE_AGENT
from engineeringagent.prompts import build_selector_prompt
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

    path_strings = {str(path): path for path, _ in pending}
    for path_str, path in path_strings.items():
        if path_str in text:
            return path

    by_name: dict[str, list[Path]] = {}
    by_id: dict[str, list[Path]] = {}
    for path, feature in pending:
        by_name.setdefault(path.name, []).append(path)
        feature_id = str(feature.get("id", "")).strip()
        if feature_id:
            by_id.setdefault(feature_id, []).append(path)

    tokens = [token.strip("`'\" ,") for token in text.replace("\n", " ").split(" ")]
    for token in tokens:
        if token in by_name and len(by_name[token]) == 1:
            return by_name[token][0]
        if token in by_id and len(by_id[token]) == 1:
            return by_id[token][0]
    return None


def choose_feature_with_selector(
    project_root: Path,
    pending: Sequence[tuple[Path, dict[str, Any]]],
    *,
    start_agent_fn: Callable[..., Any],
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

    prompt = build_selector_prompt(pending)
    print(f"Selector step: opencode run --agent {DEFAULT_OPENCODE_AGENT}")
    try:
        proc = start_agent_fn(project_root, prompt)
    except FileNotFoundError:
        fallback = deterministic_feature_choice_fn(pending)
        print(f"Selector fallback: opencode missing; selected {fallback[1].get('id')}")
        return fallback

    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        chosen_path = parse_selector_output_fn(output, pending)
        if chosen_path is not None:
            chosen_feature = next(
                feature for path, feature in pending if path == chosen_path
            )
            return (chosen_path, chosen_feature)

    fallback = deterministic_feature_choice_fn(pending)
    print(
        f"Selector fallback: parse or command failure; selected {fallback[1].get('id')}"
    )
    return fallback
