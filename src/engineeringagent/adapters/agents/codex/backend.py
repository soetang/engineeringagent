from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from engineeringagent.agents.contracts import (
    AgentBackendError,
    AgentBackendFailureDetails,
    AgentBackendRunResult,
    AgentOutputValidationError,
    AgentRunRequest,
)
from engineeringagent.adapters.config import (
    resolve_agents_codex_model,
    resolve_agents_codex_profile,
)

from .client import (
    DEFAULT_CODEX_SANDBOX,
    CodexExecConfig,
    CodexExecResult,
    run_codex_exec,
)

_MAX_VALIDATION_ERROR_CHARS = 500
_MAX_LAST_TEXT_CHARS = 2000


def _truncate_stable(value: str, *, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _walk_codex_schema_node(node: Any) -> None:
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict):
            node["required"] = list(properties.keys())
        for child in node.values():
            _walk_codex_schema_node(child)
    elif isinstance(node, list):
        for child in node:
            _walk_codex_schema_node(child)


def _codex_schema_require_all_object_properties(
    schema: dict[str, Any],
) -> dict[str, Any]:
    """Normalize JSON Schema for Codex strict schema-mode compatibility.

    Codex schema mode requires object schemas to list every property name in the
    `required` array. Pydantic JSON Schema often omits optional/defaulted fields
    from `required`, so promote all declared object properties to required while
    preserving each property's own type (including `null` unions for optionals).
    """

    normalized = json.loads(json.dumps(schema))
    _walk_codex_schema_node(normalized)
    return normalized


class CodexAgentBackend:
    """Agent backend adapter for Codex CLI."""

    def __init__(
        self,
        *,
        profile: str | None = None,
        model: str | None = None,
        sandbox: str = DEFAULT_CODEX_SANDBOX,
    ) -> None:
        self._profile = profile
        self._model = model
        self._sandbox = sandbox

    @property
    def name(self) -> str:
        """Backend identifier used in error reporting."""
        return "codex"

    def run(
        self,
        project_root: Path,
        prompt: str,
        *,
        session_id: str | None = None,
    ) -> AgentBackendRunResult:
        """Run Codex CLI and normalize the final message payload."""
        del session_id
        proc = self._run_or_raise(
            project_root,
            prompt,
            output_schema=None,
        )

        return AgentBackendRunResult(text=proc.output_last_message)

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

    def run_structured(
        self,
        project_root: Path,
        prompt: str,
        *,
        output_type: Any,
        max_validation_retries: int,
    ) -> Any:
        """Run one Codex schema-mode request and validate locally once."""
        del max_validation_retries
        adapter: TypeAdapter[Any] = TypeAdapter(output_type)
        output_schema = _codex_schema_require_all_object_properties(
            adapter.json_schema()
        )

        proc = self._run_or_raise(
            project_root,
            prompt,
            output_schema=output_schema,
        )

        payload_text = proc.output_last_message.strip()
        try:
            payload = json.loads(payload_text)
            return adapter.validate_python(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AgentOutputValidationError(
                backend=self.name,
                attempts=1,
                last_text=_truncate_stable(payload_text, limit=_MAX_LAST_TEXT_CHARS)
                or None,
                error_summary=_truncate_stable(
                    str(exc),
                    limit=_MAX_VALIDATION_ERROR_CHARS,
                )
                or "output does not match schema",
            ) from exc

    def _run_or_raise(
        self,
        project_root: Path,
        prompt: str,
        *,
        output_schema: dict[str, Any] | None,
    ) -> CodexExecResult:
        profile = self._profile or resolve_agents_codex_profile(project_root)
        model = self._model or resolve_agents_codex_model(project_root)
        try:
            proc = run_codex_exec(
                project_root,
                prompt,
                config=CodexExecConfig(
                    output_schema=output_schema,
                    profile=profile,
                    model=model,
                    sandbox=self._sandbox,
                ),
            )
        except FileNotFoundError as exc:
            raise AgentBackendError(
                backend=self.name,
                message="codex executable missing",
            ) from exc

        if proc.returncode != 0:
            raise AgentBackendError(
                backend=self.name,
                message="codex exec failed",
                process=AgentBackendFailureDetails(
                    returncode=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    command_args=proc.args,
                ),
            )
        return proc
