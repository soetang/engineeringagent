"""Application-owned implementation-step orchestration."""

from __future__ import annotations

import json
import subprocess
from enum import Enum
from pathlib import Path
from typing import Any, Callable, TypeVar

from engineeringagent.application.feature_iteration_runtime.contracts import (
    ImplementStepInputs,
    ImplementStepResult,
)
from engineeringagent.domain.audit import (
    ImplementProgressEnvelope,
    fallback_implement_progress_envelope,
    parse_implement_progress_envelope,
)
from engineeringagent.domain.specification import (
    FeatureArtifacts,
    FeaturePriority,
    FeatureSpecification,
    FeatureStatus,
    FeatureType,
    PlanningTier,
    current_progress_unit,
    feature_progress_reference,
)
from engineeringagent.ports import AgentRunner, AgentRunRequest, ProgressJournal

ImplementationPromptBuilder = Any
DescribeImplementAction = Any
ClassifyImplementFailure = Callable[[Exception], tuple[str, str]]
EnsureProgressArtifacts = Callable[[ImplementStepInputs], None]
RepoRelativePathLabeler = Callable[[Path, Path], str]
EmitImplementStepStart = Callable[[str], None]
EmitImplementOutput = Callable[[str], None]
EnumT = TypeVar("EnumT", bound=Enum)


class ImplementStepOutputDependencies:
    """Runtime-owned output callbacks for implement-step status emission."""

    def __init__(
        self,
        *,
        emit_step_start: EmitImplementStepStart,
        emit_output: EmitImplementOutput,
    ) -> None:
        self.emit_step_start = emit_step_start
        self.emit_output = emit_output


class ImplementStepRuntimeDependencies:
    """Runtime-owned helpers injected into implementation orchestration."""

    def __init__(
        self,
        *,
        describe_action: DescribeImplementAction,
        classify_backend_exception: ClassifyImplementFailure,
        ensure_progress_artifacts: EnsureProgressArtifacts,
        repo_relative_label: RepoRelativePathLabeler,
        output_dependencies: ImplementStepOutputDependencies,
    ) -> None:
        self.describe_action = describe_action
        self.classify_backend_exception = classify_backend_exception
        self.ensure_progress_artifacts = ensure_progress_artifacts
        self.repo_relative_label = repo_relative_label
        self.output = output_dependencies


def run_implement_step_from_inputs(
    implement_inputs: ImplementStepInputs,
    *,
    agent_runner: AgentRunner,
    prompt_builder: ImplementationPromptBuilder,
    progress_journal: ProgressJournal,
    runtime_dependencies: ImplementStepRuntimeDependencies,
) -> ImplementStepResult:
    """Run the implement phase and coerce structured progress output."""
    prompt = _build_implement_prompt(
        implement_inputs,
        prompt_builder=prompt_builder,
        progress_journal=progress_journal,
        repo_relative_label=runtime_dependencies.repo_relative_label,
    )
    command = runtime_dependencies.describe_action(
        implement_inputs.project_root,
        action="implement",
        structured=False,
    )
    fallback_context = _fallback_progress_context(implement_inputs)

    runtime_dependencies.ensure_progress_artifacts(implement_inputs)
    runtime_dependencies.output.emit_step_start(command)
    try:
        raw_output = _run_agent_with_structured_output(
            agent_runner,
            implement_inputs=implement_inputs,
            prompt=prompt,
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        if _should_reraise_implement_exception(exc):
            raise
        if exc.__class__.__name__ == "AgentOutputValidationError":
            fallback_envelope = fallback_implement_progress_envelope(**fallback_context)
            output = _format_structured_output_validation_failure(exc)
            _emit_agent_output(
                output,
                verbose_output=implement_inputs.verbose_output,
                emit_output=runtime_dependencies.output.emit_output,
            )
            command_output = _format_success_implement_output(command, output)
            return (True, None, command_output, fallback_envelope, True)
        failed_gate, message = runtime_dependencies.classify_backend_exception(exc)
        command_output = _format_failed_implement_output(
            command=command,
            exc=exc,
            message=message,
        )
        return (
            False,
            failed_gate,
            command_output,
            fallback_implement_progress_envelope(**fallback_context),
            True,
        )

    envelope, used_fallback, output = _coerce_implement_output(
        raw_output,
        fallback_context=fallback_context,
    )
    _emit_agent_output(
        output,
        verbose_output=implement_inputs.verbose_output,
        emit_output=runtime_dependencies.output.emit_output,
    )
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
            output_type=ImplementProgressEnvelope,
        )
    )


def _should_reraise_implement_exception(exc: Exception) -> bool:
    if isinstance(exc, (FileNotFoundError, subprocess.TimeoutExpired)):
        return False
    return exc.__class__.__name__ not in {
        "AgentBackendError",
        "AgentOutputValidationError",
    }


def _coerce_implement_output(
    raw_output: object,
    *,
    fallback_context: dict[str, str | None],
) -> tuple[ImplementProgressEnvelope, bool, str]:
    if isinstance(raw_output, ImplementProgressEnvelope):
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

    envelope, used_fallback = parse_implement_progress_envelope(
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

    progress_kind = _feature_progress_kind(implement_inputs)
    if progress_kind == "phase":
        progress_id = None
        progress_title = None
    else:
        progress_id, progress_title = feature_progress_reference(implement_inputs.feature)
    return {
        "progress_kind": progress_kind,
        "progress_id": progress_id,
        "progress_title": progress_title,
    }


def _feature_progress_kind(implement_inputs: ImplementStepInputs) -> str | None:
    artifacts = implement_inputs.feature.get("artifacts")
    if isinstance(artifacts, dict):
        plan_reference = artifacts.get("plan")
        if isinstance(plan_reference, str) and plan_reference.strip():
            return "phase"
    if isinstance(implement_inputs.feature.get("id"), str):
        return "feature"
    return None


def _format_structured_output_validation_failure(exc: Exception) -> str:
    error_summary = str(getattr(exc, "error_summary", "")).strip() or str(exc)
    lines = [
        "[implement] structured_output=invalid",
        "[implement] fallback_handoff_envelope=used",
        f"[implement] validation_error={error_summary}",
    ]
    last_text = getattr(exc, "last_text", None)
    if isinstance(last_text, str) and last_text:
        lines.append(f"[implement] last_output={last_text}")
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

    if exc.__class__.__name__ == "AgentBackendError":
        output = str(getattr(exc, "output", "")).strip()
        details = output or message
        returncode = getattr(exc, "returncode", None)
        if not isinstance(returncode, int):
            returncode = 1
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
    prompt_builder: ImplementationPromptBuilder,
    progress_journal: ProgressJournal,
    repo_relative_label: RepoRelativePathLabeler,
) -> str:
    persisted_handoff_path = progress_journal.latest_handoff_path(
        project_root=implement_inputs.project_root,
        feature_id=str(implement_inputs.feature.get("id", "")),
    )
    handoff_path = None
    if persisted_handoff_path is not None:
        handoff_path = repo_relative_label(
            implement_inputs.project_root,
            persisted_handoff_path,
        )
    return prompt_builder.build_implementation_prompt_from_specification(
        specification=_coerce_feature_specification(implement_inputs.feature),
        specification_path=implement_inputs.feature_path,
        feedback=implement_inputs.feedback,
        handoff_path=handoff_path,
    )


def _coerce_feature_specification(
    feature: dict[str, object],
) -> FeatureSpecification:
    artifacts = feature.get("artifacts")
    feature_id = _optional_str(feature.get("feature_id"))
    if feature_id is None:
        feature_id = _optional_str(feature.get("id")) or "unknown-feature"
    title = _optional_str(feature.get("title")) or feature_id
    return FeatureSpecification(
        feature_id=feature_id,
        title=title,
        feature_type=_coerce_enum(
            feature.get("feature_type", feature.get("type")),
            FeatureType,
            FeatureType.FEATURE,
        ),
        expected_commit_subject=_first_non_empty_str(
            feature,
            "expected_commit_subject",
            default="feat: implement unknown-feature",
        ),
        planning_tier=_coerce_enum(
            feature.get("planning_tier"),
            PlanningTier,
            PlanningTier.DIRECT,
        ),
        status=_coerce_enum(
            feature.get("status"),
            FeatureStatus,
            FeatureStatus.BACKLOG,
        ),
        priority=_coerce_enum(
            feature.get("priority"),
            FeaturePriority,
            FeaturePriority.HIGH,
        ),
        objective=_first_non_empty_str(feature, "objective", default=title),
        context=_optional_str(feature.get("context")),
        constraints=_string_tuple(feature.get("constraints")),
        implementation_notes=_optional_str(feature.get("implementation_notes")),
        acceptance=_string_tuple(feature.get("acceptance")),
        artifacts=_coerce_artifacts(artifacts),
        updated_at=_optional_str(feature.get("updated_at")),
    )


def _coerce_artifacts(value: object) -> FeatureArtifacts:
    if not isinstance(value, dict):
        return FeatureArtifacts()
    return FeatureArtifacts(
        plan=_optional_str(value.get("plan")),
        research=_optional_str(value.get("research")),
        supporting=_string_tuple(value.get("supporting")),
    )


def _optional_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _first_non_empty_str(values: dict[str, object], key: str, default: str) -> str:
    value = _optional_str(values.get(key))
    return value or default


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(
        normalized for item in value if (normalized := _optional_str(item)) is not None
    )


def _coerce_enum(
    value: object,
    enum_type: type[EnumT],
    default: EnumT,
) -> EnumT:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            try:
                return enum_type(normalized)
            except ValueError:
                pass
    return default


def _emit_agent_output(
    output: str,
    *,
    verbose_output: bool,
    emit_output: EmitImplementOutput,
) -> None:
    if not verbose_output or not output:
        return
    emit_output(output)
