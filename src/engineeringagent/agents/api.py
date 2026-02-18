from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar, overload

from pydantic import TypeAdapter, ValidationError

from engineeringagent.agents.contracts import (
    AgentBackend,
    AgentOutputValidationError,
)
from engineeringagent.agents.registry import get_backend_factory, resolve_backend_id


_MAX_VALIDATION_ERROR_CHARS = 500
_MAX_LAST_TEXT_CHARS = 2000


T = TypeVar("T")


def _truncate_stable(value: str, *, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _format_validation_error(exc: ValidationError) -> str:
    """Return a deterministic one-line validation error summary."""
    parts: list[str] = []
    for error in exc.errors():
        loc = error.get("loc")
        if isinstance(loc, (tuple, list)):
            loc_text = ".".join(str(item) for item in loc) or "root"
        else:
            loc_text = "root"
        message = str(error.get("msg") or "validation error").strip()
        parts.append(f"{loc_text}: {message}")

    # Preserve order while de-duplicating.
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        if part in seen:
            continue
        unique.append(part)
        seen.add(part)

    if not unique:
        return "output does not match schema"
    return "; ".join(unique)


def _render_initial_structured_prompt(*, task_prompt: str, schema_json: str) -> str:
    return "\n".join(
        (
            "---",
            "Return exactly one strict JSON value and no other text.",
            "No Markdown. No code fences. No surrounding commentary.",
            "",
            "The JSON value MUST validate against the JSON Schema below.",
            "",
            "JSON Schema:",
            schema_json,
            "",
            "Task:",
            task_prompt.strip(),
            "---",
        )
    )


def _render_retry_structured_prompt(*, error_summary: str, schema_json: str) -> str:
    bounded = _truncate_stable(error_summary.strip(), limit=_MAX_VALIDATION_ERROR_CHARS)
    return "\n".join(
        (
            "---",
            "Your previous output did not validate as strict JSON matching the required schema.",
            "",
            "Error:",
            bounded or "output does not match schema",
            "",
            "Return exactly one strict JSON value and no other text.",
            "No Markdown. No code fences. No surrounding commentary.",
            "",
            "JSON Schema:",
            schema_json,
            "---",
        )
    )


@overload
def run_agent(
    project_root: Path,
    prompt: str,
    *,
    output_type: type[str] = str,
    backend: AgentBackend | None = None,
    max_validation_retries: int = 2,
) -> str: ...


@overload
def run_agent(
    project_root: Path,
    prompt: str,
    *,
    output_type: type[T],
    backend: AgentBackend | None = None,
    max_validation_retries: int = 2,
) -> T: ...


@overload
def run_agent(
    project_root: Path,
    prompt: str,
    *,
    output_type: Any,
    backend: AgentBackend | None = None,
    max_validation_retries: int = 2,
) -> Any: ...


def run_agent(
    project_root: Path,
    prompt: str,
    *,
    output_type: Any = str,
    backend: AgentBackend | None = None,
    max_validation_retries: int = 2,
) -> Any:
    """Run an agent and return either text or validated structured output.

    This is the canonical boundary API for production callers.

    Args:
        project_root: Repository root used as agent execution working directory.
        prompt: Prompt passed to the backend agent.
        output_type: `str` for plain text, or a TypeAdapter-supported schema type.
        backend: Optional backend implementation. When omitted, the default
            production backend is selected internally.
        max_validation_retries: Maximum same-session retries for parse/validation
            failures when structured output is requested.

    Returns:
        The final output value: a `str` or validated structured output.
    """
    if max_validation_retries < 0:
        raise ValueError("max_validation_retries must be >= 0")

    if backend is None:
        backend_id = resolve_backend_id(project_root)
        create_backend = get_backend_factory(backend_id)
        backend = create_backend(output_type is not str)

    assert backend is not None

    if output_type is str:
        return backend.run(project_root, prompt).text

    adapter: TypeAdapter[Any] = TypeAdapter(output_type)
    schema_json = json.dumps(
        adapter.json_schema(),
        indent=2,
        sort_keys=True,
        ensure_ascii=True,
    )

    session_id: str | None = None
    last_text: str | None = None
    last_error_summary = ""

    initial_prompt = _render_initial_structured_prompt(
        task_prompt=prompt,
        schema_json=schema_json,
    )

    attempt_prompt = initial_prompt
    attempts_allowed = 1 + max_validation_retries
    for attempt in range(attempts_allowed):
        run_result = backend.run(
            project_root,
            attempt_prompt,
            session_id=session_id,
        )
        session_id = run_result.session_id or session_id
        text = (run_result.text or "").strip()
        last_text = text
        if not text:
            last_error_summary = "output is empty"
        else:
            try:
                payload = json.loads(text)
                return adapter.validate_python(payload)
            except json.JSONDecodeError as exc:
                last_error_summary = f"json parse error: {exc}"
            except ValidationError as exc:
                last_error_summary = _format_validation_error(exc)

        if attempt >= attempts_allowed - 1:
            break
        attempt_prompt = _render_retry_structured_prompt(
            error_summary=last_error_summary,
            schema_json=schema_json,
        )

    raise AgentOutputValidationError(
        backend=backend.name,
        attempts=attempts_allowed,
        last_text=_truncate_stable(last_text or "", limit=_MAX_LAST_TEXT_CHARS) or None,
        error_summary=_truncate_stable(
            last_error_summary, limit=_MAX_VALIDATION_ERROR_CHARS
        )
        or "output does not match schema",
        backend_metadata={"session_id": session_id} if session_id else None,
    )
