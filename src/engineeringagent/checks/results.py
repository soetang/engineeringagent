from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from engineeringagent.checks.contracts import (
    CheckDecision,
    CheckExecutionRecord,
    CommandInvocationRecord,
)


class ChecksRunResult(BaseModel):
    """Structured result for a checks run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    dry_run: bool = False
    failed_check_id: str | None = None
    failed_payload: dict[str, Any] | None = None
    output: str = ""
    decisions: tuple[CheckDecision, ...] = ()
    executions: tuple[CheckExecutionRecord, ...] = ()
    prompt_feedback: str | None = None
    command_invocations: tuple[CommandInvocationRecord, ...] = ()
