from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import pytest

from engineeringagent.application.feature_iteration.contracts import (
    ImplementStepInputs,
)
from engineeringagent.application.feature_iteration.implementation_step import (
    ImplementStepFailureDependencies,
    ImplementStepOutputDependencies,
    ImplementStepRuntimeDependencies,
    run_implement_step_from_inputs,
)
from engineeringagent.domain.audit import (
    ImplementProgressEnvelope,
    ProgressEvent,
)
from engineeringagent.ports import AgentRunRequest


class _FakeAgentRunner:
    def __init__(self, result: object) -> None:
        """Store a deterministic agent result for the test."""
        self._result = result
        self.requests: list[AgentRunRequest] = []

    def run(self, request: AgentRunRequest) -> object:
        """Record the request and return the prepared result."""
        self.requests.append(request)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _FakePromptBuilder:
    def build_implementation_prompt_from_specification(
        self,
        *,
        specification: object,
        specification_path: Path,
        feedback: str | None,
        handoff_path: str | None = None,
    ) -> str:
        """Return a deterministic prompt while asserting expected inputs."""
        assert getattr(specification, "feature_id") == "FEAT-300"
        assert specification_path.name == "spec.yaml"
        assert feedback == "retry"
        assert handoff_path is None
        return "implement prompt"


class _FakeProgressJournal:
    def __init__(self) -> None:
        """Track handoff lookups while rejecting unrelated journal calls."""
        self.handoff_calls: list[tuple[Path, str]] = []
        self.handoff_path: Path | None = None

    def latest_handoff_path(
        self,
        *,
        project_root: Path,
        feature_id: str,
    ) -> Path | None:
        """Record the lookup and return no persisted handoff."""
        self.handoff_calls.append((project_root, feature_id))
        return self.handoff_path

    def append(self, *, project_root: Path, event: ProgressEvent) -> None:
        """Reject append calls; implement-step tests should not write events."""
        raise AssertionError((project_root, event))

    def append_feature_log(
        self,
        *,
        project_root: Path,
        feature_id: str,
        lines: Sequence[str],
    ) -> None:
        """Reject feature-log writes during implement-step tests."""
        raise AssertionError((project_root, feature_id, lines))

    def write_iteration_report(
        self,
        *,
        project_root: Path,
        feature_id: str,
        payload: dict[str, Any],
    ) -> None:
        """Reject iteration-report writes during implement-step tests."""
        raise AssertionError((project_root, feature_id, payload))

    def write_handoff(
        self,
        *,
        project_root: Path,
        feature_id: str,
        lines: Sequence[str],
    ) -> None:
        """Reject handoff writes during implement-step tests."""
        raise AssertionError((project_root, feature_id, lines))


def _capture_command(observed: dict[str, object], command: str) -> None:
    """Append one emitted implement command to the observed output list."""
    commands = observed.setdefault("commands", [])
    assert isinstance(commands, list)
    commands.append(command)


def _capture_output(observed: dict[str, object], output: str) -> None:
    """Append one emitted verbose payload to the observed output list."""
    outputs = observed.setdefault("outputs", [])
    assert isinstance(outputs, list)
    outputs.append(output)


def _ensure_progress_artifacts(
    observed: dict[str, object], inputs: ImplementStepInputs
) -> None:
    """Record the implement-step inputs passed to artifact preparation."""
    observed["ensure_inputs"] = inputs


def _runtime_dependencies(observed: dict[str, object]) -> ImplementStepRuntimeDependencies:
    """Build implement-step runtime dependencies with captured output callbacks."""
    return ImplementStepRuntimeDependencies(
        describe_action=lambda _project_root, **_kwargs: "uv run engineeringagent implement",
        failure_dependencies=ImplementStepFailureDependencies(
            classify_backend_exception=lambda exc: ("implement", str(exc)),
            should_handle_backend_exception=lambda _exc: True,
            format_failed_backend_output=lambda command, _exc, message: (
                f"[implement] command={command}\n[implement] error={message}"
            ),
        ),
        ensure_progress_artifacts=lambda inputs: _ensure_progress_artifacts(
            observed, inputs
        ),
        repo_relative_label=lambda _project_root, path: str(path),
        output_dependencies=ImplementStepOutputDependencies(
            emit_step_start=lambda command: _capture_command(observed, command),
            emit_output=lambda output: _capture_output(observed, output),
        ),
    )


def _implement_inputs(verbose_output: bool = True) -> ImplementStepInputs:
    """Build a stable implement-step input payload for tests."""
    return ImplementStepInputs(
        project_root=Path("/tmp/project"),
        feature={"id": "FEAT-300", "title": "Move output ownership"},
        feature_path=Path("docs/specifications/features/FEAT-300/spec.yaml"),
        feedback="retry",
        verbose_output=verbose_output,
    )


def test_run_implement_step_emits_start_and_output_through_runtime_callbacks() -> None:
    """Route implement-step status output through injected runtime callbacks."""
    observed: dict[str, Any] = {}
    progress_journal = _FakeProgressJournal()
    runner = _FakeAgentRunner(
        ImplementProgressEnvelope(
            summary="updated implementation step",
            completed_work=["moved implement-step status output to callbacks"],
            verification=[
                "uv run pytest tests/application/feature_iteration/test_implementation_step.py"
            ],
            remaining_work=["run the full checks phase"],
        )
    )

    result = run_implement_step_from_inputs(
        _implement_inputs(verbose_output=True),
        agent_runner=runner,
        prompt_builder=_FakePromptBuilder(),
        progress_journal=progress_journal,
        runtime_dependencies=_runtime_dependencies(observed),
    )

    assert result[0] is True
    assert progress_journal.handoff_calls == [(Path("/tmp/project"), "FEAT-300")]
    assert observed["commands"] == ["uv run engineeringagent implement"]
    assert observed["outputs"] == [
        '{"blockers": [], "completed_work": ["moved implement-step status output to callbacks"], "remaining_work": ["run the full checks phase"], "summary": "updated implementation step", "verification": ["uv run pytest tests/application/feature_iteration/test_implementation_step.py"]}'
    ]
    assert runner.requests[0].prompt == "implement prompt"


def test_run_implement_step_skips_output_callback_when_verbose_is_disabled() -> None:
    """Skip verbose output emission while still announcing the implement command."""
    observed: dict[str, Any] = {}
    progress_journal = _FakeProgressJournal()

    run_implement_step_from_inputs(
        _implement_inputs(verbose_output=False),
        agent_runner=_FakeAgentRunner(
            ImplementProgressEnvelope(
                summary="quiet execution",
                completed_work=["prepared quiet execution"],
                verification=["none"],
                remaining_work=["continue iteration"],
            )
        ),
        prompt_builder=_FakePromptBuilder(),
        progress_journal=progress_journal,
        runtime_dependencies=_runtime_dependencies(observed),
    )

    assert progress_journal.handoff_calls == [(Path("/tmp/project"), "FEAT-300")]
    assert observed["commands"] == ["uv run engineeringagent implement"]
    assert observed.get("outputs") is None


def test_run_implement_step_reraises_unhandled_backend_exception() -> None:
    """Reraise exceptions that runtime policy does not classify as handled."""

    class _UnhandledFailure(Exception):
        pass

    observed: dict[str, Any] = {}
    progress_journal = _FakeProgressJournal()

    with pytest.raises(_UnhandledFailure, match="boom"):
        run_implement_step_from_inputs(
            _implement_inputs(),
            agent_runner=_FakeAgentRunner(_UnhandledFailure("boom")),
            prompt_builder=_FakePromptBuilder(),
            progress_journal=progress_journal,
            runtime_dependencies=ImplementStepRuntimeDependencies(
                describe_action=lambda _project_root, **_kwargs: (
                    "uv run engineeringagent implement"
                ),
                failure_dependencies=ImplementStepFailureDependencies(
                    classify_backend_exception=lambda exc: ("implement", str(exc)),
                    should_handle_backend_exception=lambda _exc: False,
                    format_failed_backend_output=lambda command, _exc, message: (
                        f"[implement] command={command}\n[implement] error={message}"
                    ),
                ),
                ensure_progress_artifacts=lambda inputs: _ensure_progress_artifacts(
                    observed, inputs
                ),
                repo_relative_label=lambda _project_root, path: str(path),
                output_dependencies=ImplementStepOutputDependencies(
                    emit_step_start=lambda command: _capture_command(observed, command),
                    emit_output=lambda output: _capture_output(observed, output),
                ),
            ),
        )

    assert progress_journal.handoff_calls == [(Path("/tmp/project"), "FEAT-300")]
    assert observed["commands"] == ["uv run engineeringagent implement"]
