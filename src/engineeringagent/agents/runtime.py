from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, overload

from pydantic import TypeAdapter, ValidationError

from engineeringagent.agents.contracts import (
    AgentBackend,
    AgentBackendRunResult,
    AgentOutputValidationError,
    StructuredOutputAgentBackend,
)
from engineeringagent.agents.registry import get_backend_factory, resolve_backend_id


_MAX_VALIDATION_ERROR_CHARS = 500
_MAX_LAST_TEXT_CHARS = 2000


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


class PromptRetryStructuredStrategy(StructuredOutputAgentBackend):
    """Structured-output adapter for plain text backends."""

    def __init__(self, backend: AgentBackend) -> None:
        self._backend = backend

    @property
    def name(self) -> str:
        """Expose the wrapped backend name for typed errors."""
        return self._backend.name

    def run(
        self,
        project_root: Path,
        prompt: str,
        *,
        session_id: str | None = None,
    ) -> AgentBackendRunResult:
        """Delegate plain-text execution to the wrapped backend."""
        return self._backend.run(project_root, prompt, session_id=session_id)

    def run_structured(
        self,
        project_root: Path,
        prompt: str,
        *,
        output_type: Any,
        max_validation_retries: int,
    ) -> Any:
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
            run_result = self._backend.run(
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
            backend=self.name,
            attempts=attempts_allowed,
            last_text=_truncate_stable(last_text or "", limit=_MAX_LAST_TEXT_CHARS)
            or None,
            error_summary=_truncate_stable(
                last_error_summary, limit=_MAX_VALIDATION_ERROR_CHARS
            )
            or "output does not match schema",
            backend_metadata={"session_id": session_id} if session_id else None,
        )


@overload
def resolve_agent_strategy(
    project_root: Path,
    *,
    structured_output: Literal[False],
) -> AgentBackend: ...


@overload
def resolve_agent_strategy(
    project_root: Path,
    *,
    structured_output: Literal[True],
) -> StructuredOutputAgentBackend: ...


def resolve_agent_strategy(
    project_root: Path,
    *,
    structured_output: bool,
) -> AgentBackend | StructuredOutputAgentBackend:
    """Resolve and construct the configured agent backend strategy."""
    backend_id = resolve_backend_id(project_root)
    create_backend = get_backend_factory(backend_id)
    backend = create_backend(structured_output)

    if structured_output:
        if isinstance(backend, StructuredOutputAgentBackend):
            return backend
        return PromptRetryStructuredStrategy(backend)

    return backend
