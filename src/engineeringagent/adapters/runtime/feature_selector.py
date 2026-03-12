"""Runtime adapter for selector-driven feature choice."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from engineeringagent.adapters.agents import (
    AgentBackendError,
    classify_backend_exception,
    describe_action,
)
from engineeringagent.domain.specification import (
    FeatureSelectionCandidate,
    deterministic_feature_choice,
    parse_selector_output,
)


def choose_feature_with_selector(
    project_root: Path,
    pending: Sequence[tuple[Path, FeatureSelectionCandidate]],
    *,
    build_selector_prompt_fn: Callable[
        [Sequence[tuple[Path, FeatureSelectionCandidate]]],
        str,
    ],
    run_agent_fn: Callable[[Path, str], str],
) -> tuple[Path, FeatureSelectionCandidate]:
    """Choose a feature using selector output with deterministic fallback."""
    if len(pending) == 1:
        return pending[0]

    prompt = build_selector_prompt_fn(pending)
    step_label = describe_action(project_root, action="selector", structured=False)
    print(f"Selector step: {step_label}")
    try:
        output = run_agent_fn(project_root, prompt)
    except (FileNotFoundError, AgentBackendError) as exc:
        failed_gate, _message = classify_backend_exception(exc)
        fallback = deterministic_feature_choice(pending)
        print(f"Selector fallback: {failed_gate}; selected {fallback[1].feature_id}")
        return fallback

    chosen_path = parse_selector_output(output, pending)
    if chosen_path is not None:
        chosen_feature = next(
            feature for path, feature in pending if path == chosen_path
        )
        return (chosen_path, chosen_feature)

    fallback = deterministic_feature_choice(pending)
    print(f"Selector fallback: selector_parse; selected {fallback[1].feature_id}")
    return fallback
