from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar, overload
from engineeringagent.agents.runtime import resolve_agent_strategy

T = TypeVar("T")


@overload
def run_agent(
    project_root: Path,
    prompt: str,
    *,
    output_type: type[str] = str,
    max_validation_retries: int = 2,
) -> str: ...


@overload
def run_agent(
    project_root: Path,
    prompt: str,
    *,
    output_type: type[T],
    max_validation_retries: int = 2,
) -> T: ...


@overload
def run_agent(
    project_root: Path,
    prompt: str,
    *,
    output_type: Any,
    max_validation_retries: int = 2,
) -> Any: ...


def run_agent(
    project_root: Path,
    prompt: str,
    *,
    output_type: Any = str,
    max_validation_retries: int = 2,
) -> Any:
    """Run an agent and return either text or validated structured output.

    This is the canonical boundary API for production callers.

    Args:
        project_root: Repository root used as agent execution working directory.
        prompt: Prompt passed to the backend agent.
        output_type: `str` for plain text, or a TypeAdapter-supported schema type.
        max_validation_retries: Maximum same-session retries for parse/validation
            failures when structured output is requested.

    Returns:
        The final output value: a `str` or validated structured output.
    """
    if max_validation_retries < 0:
        raise ValueError("max_validation_retries must be >= 0")

    if output_type is str:
        backend = resolve_agent_strategy(
            project_root,
            structured_output=False,
        )
        return backend.run(project_root, prompt).text

    backend = resolve_agent_strategy(
        project_root,
        structured_output=True,
    )
    return backend.run_structured(
        project_root,
        prompt,
        output_type=output_type,
        max_validation_retries=max_validation_retries,
    )
