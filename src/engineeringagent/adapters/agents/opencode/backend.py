from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from engineeringagent.adapters.agents.contracts import (
    AgentBackendError,
    AgentBackendFailureDetails,
    AgentBackendRunResult,
    AgentOutputValidationError,
    AgentRunRequest,
)

from .client import DEFAULT_OPENCODE_AGENT, start_agent

_MAX_VALIDATION_ERROR_CHARS = 500
_MAX_LAST_TEXT_CHARS = 2000


def _truncate_stable(value: str, *, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _format_validation_error(exc: ValidationError) -> str:
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


class OpenCodeAgentBackend:
    """Agent backend adapter for OpenCode.

    Text and structured execution are both backend-owned. Structured mode uses
    deterministic prompt/retry handling and same-session followups through the
    OpenCode JSON protocol.
    """

    def __init__(
        self,
        *,
        agent: str = DEFAULT_OPENCODE_AGENT,
        format: str | None = None,  # pylint: disable=redefined-builtin
    ) -> None:
        self._agent = agent
        self._format = format

    @property
    def name(self) -> str:
        """Backend identifier used in error messages and telemetry."""
        return "opencode"

    def run(
        self,
        project_root: Path,
        prompt: str,
        *,
        session_id: str | None = None,
    ) -> AgentBackendRunResult:
        """Run the OpenCode agent and return a backend-normalized result."""
        if self._format == "json":
            return self._run_json(project_root, prompt, session_id=session_id)

        proc = start_agent(
            project_root,
            prompt,
            agent=self._agent,
            format=self._format,
            session=session_id,
        )

        if proc.returncode != 0:
            raise AgentBackendError(
                backend=self.name,
                message="opencode run failed",
                process=AgentBackendFailureDetails(
                    returncode=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    command_args=list(proc.args),
                ),
            )

        output = (proc.stdout or "") + (proc.stderr or "")
        return AgentBackendRunResult(text=output)

    def run_request(self, request: AgentRunRequest) -> Any:
        """Execute one normalized request through backend-owned behavior."""
        if request.output_type is str:
            return self.run(request.project_root, request.prompt).text

        return self.run_structured(
            request.project_root,
            request.prompt,
            output_type=request.output_type,
            max_validation_retries=request.max_validation_retries,
        )

    def _run_json(
        self,
        project_root: Path,
        prompt: str,
        *,
        session_id: str | None,
    ) -> AgentBackendRunResult:
        proc = start_agent(
            project_root,
            prompt,
            agent=self._agent,
            format="json",
            session=session_id,
        )

        if proc.returncode != 0:
            raise AgentBackendError(
                backend=self.name,
                message="opencode run failed",
                process=AgentBackendFailureDetails(
                    returncode=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    command_args=list(proc.args),
                ),
            )

        text_payload = proc.text_payload
        if not isinstance(text_payload, str) or not text_payload.strip():
            raise AgentBackendError(
                backend=self.name,
                message="opencode json output missing final text payload",
                process=AgentBackendFailureDetails(
                    returncode=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    command_args=list(proc.args),
                ),
                backend_metadata={"session_id": proc.session_id}
                if proc.session_id
                else None,
            )

        return AgentBackendRunResult(
            text=text_payload,
            session_id=proc.session_id,
        )

    def run_structured(
        self,
        project_root: Path,
        prompt: str,
        *,
        output_type: Any,
        max_validation_retries: int,
    ) -> Any:
        """Run structured output with backend-owned prompt/retry policy."""
        if max_validation_retries < 0:
            raise ValueError("max_validation_retries must be >= 0")

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

        attempt_prompt = _render_initial_structured_prompt(
            task_prompt=prompt,
            schema_json=schema_json,
        )
        attempts_allowed = 1 + max_validation_retries
        for attempt in range(attempts_allowed):
            run_result = self._run_json(
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
                last_error_summary,
                limit=_MAX_VALIDATION_ERROR_CHARS,
            )
            or "output does not match schema",
            backend_metadata={"session_id": session_id} if session_id else None,
        )
