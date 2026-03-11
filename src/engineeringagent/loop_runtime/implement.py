"""Loop runtime implementation phase helpers."""

from __future__ import annotations

import subprocess
import json
from pathlib import Path
from typing import Any
from typing import Protocol

from engineeringagent.adapters.agents import ConfiguredAgentRunner
from engineeringagent.adapters.progress import FilesystemProgressJournal
from engineeringagent.application import (
    ImplementationPromptRequest,
)
from engineeringagent.agents import (
    AgentBackendError,
    AgentOutputValidationError,
    classify_backend_exception,
    describe_action,
)
from engineeringagent.domain.specification import (
    current_progress_unit,
    feature_progress_reference,
)
from engineeringagent.loop_runtime.models import ImplementStepInputs
from engineeringagent.loop_runtime.models import ImplementStepResult
from engineeringagent.ports import AgentRunRequest, AgentRunner
from engineeringagent.bootstrap import AppFactory
from engineeringagent.progress import handoff as progress_handoff
from engineeringagent.progress import paths as progress_paths
from engineeringagent.specs import (
    feature_progress_kind,
)


_PROGRESS_JOURNAL = FilesystemProgressJournal()
_AGENT_RUNNER = ConfiguredAgentRunner()


class _ImplementationPromptBuilder(Protocol):
    """Local duck-typed seam for prompt rendering in loop tests."""

    def build_implementation_prompt_request(
        self,
        *,
        feature: dict[str, Any],
        feature_path: Path,
        feedback: str | None,
        handoff_path: str | None = None,
    ) -> ImplementationPromptRequest:
        """Build one implementation prompt request from feature data."""
        raise NotImplementedError

    def build_implementation_prompt(
        self,
        request: ImplementationPromptRequest,
    ) -> str:
        """Render one implementation prompt from normalized request data."""
        raise NotImplementedError


def run_implement_step_from_inputs(
    implement_inputs: ImplementStepInputs,
    *,
    agent_runner: AgentRunner,
    prompt_builder: _ImplementationPromptBuilder | None = None,
) -> ImplementStepResult:
    """Run the implement phase and coerce structured progress output."""
    prompt = _build_implement_prompt(
        implement_inputs,
        prompt_builder=prompt_builder
        or AppFactory(implement_inputs.project_root).build_prompt_builder(),
    )
    command = describe_action(
        implement_inputs.project_root,
        action="implement",
        structured=False,
    )
    fallback_context = _fallback_progress_context(implement_inputs)

    _ensure_progress_artifacts(implement_inputs)
    print(f"Implement step: {command}", flush=True)
    try:
        raw_output = _run_agent_with_structured_output(
            agent_runner,
            implement_inputs=implement_inputs,
            prompt=prompt,
        )
    except AgentOutputValidationError as exc:
        fallback_envelope = progress_handoff.fallback_implement_progress_envelope(
            **fallback_context
        )
        output = _format_structured_output_validation_failure(exc)
        _print_agent_output(output, verbose_output=implement_inputs.verbose_output)
        command_output = _format_success_implement_output(command, output)
        return (True, None, command_output, fallback_envelope, True)
    except (AgentBackendError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        failed_gate, message = classify_backend_exception(exc)
        command_output = _format_failed_implement_output(
            command=command,
            exc=exc,
            message=message,
        )
        return (
            False,
            failed_gate,
            command_output,
            progress_handoff.fallback_implement_progress_envelope(**fallback_context),
            True,
        )

    envelope, used_fallback, output = _coerce_implement_output(
        raw_output,
        fallback_context=fallback_context,
    )
    _print_agent_output(output, verbose_output=implement_inputs.verbose_output)
    command_output = _format_success_implement_output(command, output)
    return (True, None, command_output, envelope, used_fallback)


def _run_agent_with_structured_output(
    agent_runner: AgentRunner,
    *,
    implement_inputs: ImplementStepInputs,
    prompt: str,
) -> Any:
    return agent_runner.run(
        AgentRunRequest(
            project_root=implement_inputs.project_root,
            prompt=prompt,
            output_type=progress_handoff.ImplementProgressEnvelope,
        )
    )


def _coerce_implement_output(
    raw_output: object,
    *,
    fallback_context: dict[str, str | None],
) -> tuple[progress_handoff.ImplementProgressEnvelope, bool, str]:
    if isinstance(raw_output, progress_handoff.ImplementProgressEnvelope):
        output = json.dumps(
            raw_output.model_dump(exclude_none=True),
            sort_keys=True,
            ensure_ascii=True,
        )
        return raw_output, False, output

    payload: object = raw_output
    output = str(raw_output)
    if isinstance(raw_output, str):
        output = raw_output
        stripped = raw_output.strip()
        if stripped:
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                payload = raw_output

    envelope, used_fallback = progress_handoff.parse_implement_progress_envelope(
        payload,
        **fallback_context,
    )
    return envelope, used_fallback, output


def _fallback_progress_context(
    implement_inputs: ImplementStepInputs,
) -> dict[str, str | None]:
    progress_unit = current_progress_unit(
        implement_inputs.feature_path,
        implement_inputs.feature,
    )
    if progress_unit is not None:
        return {
            "progress_kind": progress_unit.kind,
            "progress_id": progress_unit.id,
            "progress_title": progress_unit.title,
        }
    progress_kind = feature_progress_kind(
        implement_inputs.feature_path,
        implement_inputs.feature,
    )
    progress_id: str | None = None
    progress_title: str | None = None
    if progress_kind == "feature":
        progress_id, progress_title = feature_progress_reference(implement_inputs.feature)
    return {
        "progress_kind": progress_kind,
        "progress_id": progress_id,
        "progress_title": progress_title,
    }


def _format_structured_output_validation_failure(
    exc: AgentOutputValidationError,
) -> str:
    lines = [
        "[implement] structured_output=invalid",
        "[implement] fallback_handoff_envelope=used",
        f"[implement] validation_error={exc.error_summary}",
    ]
    if exc.last_text:
        lines.append(f"[implement] last_output={exc.last_text}")
    return "\n".join(lines)


def _format_failed_implement_output(
    *, command: str, exc: Exception, message: str
) -> str:
    if isinstance(exc, FileNotFoundError):
        return message

    if isinstance(exc, subprocess.TimeoutExpired):
        return (
            f"[implement] command={command}\n"
            "[implement] error=timeout\n"
            f"{message}.\n"
            "[implement] hint: interrupt stuck runs and investigate backend credentials/config.\n"
            "[implement] hint: for a non-mutating preview use `engineeringagent run --dry-run`.\n"
        )

    if isinstance(exc, AgentBackendError):
        output = exc.output.strip()
        details = output or message
        returncode = exc.returncode if exc.returncode is not None else 1
        return (
            f"[implement] command={command}\n"
            f"[implement] returncode={returncode}\n"
            f"{details}"
        )

    return f"[implement] command={command}\n[implement] error={message}"


def _format_success_implement_output(command: str, output: str) -> str:
    return f"[implement] command={command}\n[implement] returncode=0\n{output}"


def _build_implement_prompt(
    implement_inputs: ImplementStepInputs,
    *,
    prompt_builder: _ImplementationPromptBuilder,
) -> str:
    request = prompt_builder.build_implementation_prompt_request(
        feature=implement_inputs.feature,
        feature_path=implement_inputs.feature_path,
        feedback=implement_inputs.feedback,
    )
    if _PROGRESS_JOURNAL.latest_handoff_path(
        project_root=implement_inputs.project_root,
        feature_id=request.feature.feature_id,
    ):
        handoff_path = progress_paths.handoff_markdown_reference(
            implement_inputs.project_root,
            request.feature.feature_id,
        )
        request = request.model_copy(update={"handoff_path": handoff_path})
    return prompt_builder.build_implementation_prompt(request)


def _ensure_progress_artifacts(implement_inputs: ImplementStepInputs) -> None:
    project_root = implement_inputs.project_root
    feature_id = implement_inputs.feature.get("id")
    if not isinstance(feature_id, str) or not feature_id.strip():
        feature_id = "unknown-feature"

    progress_paths.runs_dir(project_root).mkdir(parents=True, exist_ok=True)
    progress_paths.runs_jsonl_path(project_root).touch(exist_ok=True)

    timestamp = progress_handoff.now_iso()
    _PROGRESS_JOURNAL.append_feature_log(
        project_root=project_root,
        feature_id=feature_id,
        lines=[
            (
                f"ts={timestamp} === IMPLEMENT START feature_id={feature_id} "
                f"feature_path={implement_inputs.feature_path} ==="
            )
        ],
    )


def _print_agent_output(output: str, *, verbose_output: bool) -> None:
    if not verbose_output:
        return
    if output:
        print(output, end="")
