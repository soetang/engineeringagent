"""Shared signature shims for loop facade compatibility seams."""

from __future__ import annotations

import inspect
from typing import Any


def _parameter(
    name: str,
    default: Any = inspect.Parameter.empty,
) -> inspect.Parameter:
    return inspect.Parameter(
        name,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        default=default,
    )


RUN_IMPLEMENT_STEP_SIGNATURE = inspect.Signature(
    parameters=(
        _parameter("project_root"),
        _parameter("feature"),
        _parameter("feature_path"),
        _parameter("implement_command"),
        _parameter("opencode_prompt"),
        _parameter("skip_implement"),
        _parameter("hook_feedback"),
        _parameter("verbose_output"),
    )
)

PRINT_SUMMARY_SIGNATURE = inspect.Signature(
    parameters=(
        _parameter("feature_id"),
        _parameter("result"),
        _parameter("failed_gate"),
        _parameter("attempt"),
        _parameter("next_action"),
        _parameter("selected_path", None),
        _parameter("implement_step", None),
        _parameter("log_path", None),
        _parameter("archived_selection_path", None),
        _parameter("verification_status", None),
        _parameter("verification_failed_command", None),
        _parameter("reviewer_status", None),
        _parameter("reviewer_decision", None),
        _parameter("failed_reviewer_id", None),
    )
)

RUN_FEATURE_ITERATION_SIGNATURE = inspect.Signature(
    parameters=(
        _parameter("project_root"),
        _parameter("feature_path"),
        _parameter("gate_profile"),
        _parameter("implement_command"),
        _parameter("opencode_prompt"),
        _parameter("skip_implement"),
        _parameter("attempt"),
        _parameter("hook_feedback"),
        _parameter("verbose_output"),
    )
)

RUN_LOOP_SIGNATURE = inspect.Signature(
    parameters=(
        _parameter("project_root"),
        _parameter("feature_paths"),
        _parameter("gate_profile"),
        _parameter("implement_command"),
        _parameter("opencode_prompt"),
        _parameter("skip_implement"),
        _parameter("dry_run"),
        _parameter("run_all", False),
        _parameter("max_iterations", 50),
        _parameter("allow_dirty", False),
        _parameter("verbose_output", False),
    )
)


def bind_facade_call(
    signature: inspect.Signature,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Bind facade arguments against a compatibility signature."""
    bound_arguments = signature.bind(*args, **kwargs)
    bound_arguments.apply_defaults()
    return dict(bound_arguments.arguments)
