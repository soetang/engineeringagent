"""Unit tests for the implementation loop with fake adapters."""

from collections.abc import Iterable, Mapping
from typing import Any

from engineeringagent.orchestrators.loop import models
from engineeringagent.orchestrators.loop.implementation_agent import ImplementationAgent


class FakePromptBuilder:
    """Prompt builder that records every injection payload."""

    def __init__(self) -> None:
        """Initialize an empty prompt input history."""
        self.inputs: list[dict[str, object]] = []

    def build(self, context: Mapping[str, Any]) -> str:
        """Record the payload and return a deterministic prompt."""
        self.inputs.append(dict(context))
        return f"FEEDBACK={context.get('feedback')}"


def _assert_prompt_payloads(
    payloads: list[dict[str, object]],
    expected_feedbacks: list[str | None],
) -> None:
    """Verify each payload contains expected task-path and feedback values."""
    assert payloads == [
        {
            "feedback": feedback,
            "task_path": None,
        }
        for feedback in expected_feedbacks
    ]


class FakeAgentRunner:
    """Agent runner with scripted results."""

    def __init__(self, results: Iterable[str] | None = None) -> None:
        """Initialize the runner with scripted summaries."""
        self.results = list(results or ["ok"])
        self.runs = 0

    def run_agent(self, prompt: str, output_format=None) -> models.AgentResult:
        """Pop and return the next scripted agent result."""
        self.runs += 1
        del prompt, output_format
        if not self.results:
            self.results = ["ok"]
        summary = self.results.pop(0)
        return models.AgentResult(summary=summary)


class FakeGateRunner:
    """Gate runner with scripted pass/fail results."""

    def __init__(self, checks: Iterable[models.GateResult]) -> None:
        """Initialize scripted gate check results."""
        self.checks = list(checks)
        self.calls: list[tuple[models.GatePhase, bool]] = []

    def check(
        self,
        phase: models.GatePhase,
        stop_on_first_failure: bool = False,
    ) -> models.GateResult:
        """Return the next scripted gate result."""
        self.calls.append((phase, stop_on_first_failure))
        return self.checks.pop(0)


class FakeTask:
    """Task with scripted completion states."""

    def __init__(self, states: Iterable[models.CompletionResult] | None = None) -> None:
        """Initialize scripted completion states."""
        self._task_id = "implementation"
        self._task_name = "implementation"
        self._task_path = None
        self.states = list(states or [models.CompletionResult.COMPLETE])

    @property
    def task_id(self) -> str:
        """Return the fake task id."""
        return self._task_id

    @property
    def task_name(self) -> str:
        """Return the fake task name."""
        return self._task_name

    @property
    def task_path(self) -> str | None:
        """Return the fake task path."""
        return self._task_path

    def is_complete(self) -> models.CompletionResult:
        """Return the next scripted completion state."""
        if not self.states:
            return models.CompletionResult.COMPLETE
        return self.states.pop(0)

    def get_branch_name(self) -> str:
        """Return the fake branch name."""
        return self._task_id


class RecordingObserver:
    """Observer that records lifecycle callbacks."""

    def __init__(self, *, iteration_error: str | None = None) -> None:
        self.iteration_error = iteration_error
        self.iteration_calls: list[tuple[int, str]] = []
        self.success_calls = 0
        self.failure_calls: list[str | None] = []

    def validate(self, context: models.ImplementationContext) -> None:
        """Record validation without mutating the context."""
        del context

    def on_iteration_passed(
        self,
        attempt: int,
        context: models.ImplementationContext,
        agent_result: models.AgentResult,
    ) -> models.IterationArtifact | None:
        """Record passing iterations and optionally raise an error."""
        del context
        self.iteration_calls.append((attempt, agent_result.summary))
        if self.iteration_error is not None:
            raise ValueError(self.iteration_error)
        return None

    def on_run_succeeded(
        self,
        context: models.ImplementationContext,
    ) -> models.RunPublicationResult | None:
        """Record successful completion and return a publication message."""
        del context
        self.success_calls += 1
        return models.RunPublicationResult(message="published")

    def on_run_failed(
        self,
        context: models.ImplementationContext,
        feedback: str | None,
    ) -> None:
        """Record terminal run failures."""
        del context
        self.failure_calls.append(feedback)


def test_fast_gate_fail_then_recover_with_feedback() -> None:
    """Fast gate feedback should be carried into the retry prompt."""
    prompt_builder = FakePromptBuilder()
    agent_runner = FakeAgentRunner(["first", "second"])
    gate_runner = FakeGateRunner(
        [
            models.GateResult(passed=False, feedback="fix fast gate"),
            models.GateResult(passed=True),
            models.GateResult(passed=True),
        ]
    )

    implementation_agent = ImplementationAgent(
        prompt_builder=prompt_builder,
        agent_runner=agent_runner,
        gate_runner=gate_runner,
        task=FakeTask([models.CompletionResult.COMPLETE]),
        max_iterations=3,
    )
    outcome = implementation_agent.run()

    assert outcome.status == "success"
    assert outcome.iterations == 2
    _assert_prompt_payloads(prompt_builder.inputs, [None, "fix fast gate"])


def test_prompt_builder_receives_task_path_and_feedback_context() -> None:
    """Prompt payload should include only feedback and task path."""
    prompt_builder = FakePromptBuilder()
    agent_runner = FakeAgentRunner(["only"])
    gate_runner = FakeGateRunner(
        [models.GateResult(passed=True), models.GateResult(passed=True)]
    )

    implementation_agent = ImplementationAgent(
        prompt_builder=prompt_builder,
        agent_runner=agent_runner,
        gate_runner=gate_runner,
        task=FakeTask([models.CompletionResult.COMPLETE]),
        max_iterations=3,
    )
    outcome = implementation_agent.run()

    assert outcome.status == "success"
    assert len(prompt_builder.inputs) == 1
    _assert_prompt_payloads(prompt_builder.inputs, [None])


def test_unbounded_iterations_allow_late_success() -> None:
    """None max_iterations should allow an unbounded loop."""
    prompt_builder = FakePromptBuilder()
    agent_runner = FakeAgentRunner(["first", "second", "third", "fourth"])
    gate_runner = FakeGateRunner(
        [
            models.GateResult(passed=True),
            models.GateResult(passed=True),
            models.GateResult(passed=True),
            models.GateResult(passed=True),
            models.GateResult(passed=True),
        ]
    )

    implementation_agent = ImplementationAgent(
        prompt_builder=prompt_builder,
        agent_runner=agent_runner,
        gate_runner=gate_runner,
        task=FakeTask(
            [
                models.CompletionResult.INCOMPLETE,
                models.CompletionResult.INCOMPLETE,
                models.CompletionResult.COMPLETE,
            ]
        ),
        max_iterations=None,
    )

    outcome = implementation_agent.run()

    assert outcome.status == "success"
    assert outcome.iterations == 3


def test_incomplete_path_uses_none_feedback() -> None:
    """Completion incomplete should clear feedback before the next attempt."""
    prompt_builder = FakePromptBuilder()
    agent_runner = FakeAgentRunner(["attempt1", "attempt2"])
    gate_runner = FakeGateRunner(
        [
            models.GateResult(passed=True),
            models.GateResult(passed=True),
            models.GateResult(passed=True),
        ]
    )

    implementation_agent = ImplementationAgent(
        prompt_builder=prompt_builder,
        agent_runner=agent_runner,
        gate_runner=gate_runner,
        task=FakeTask(
            [
                models.CompletionResult.INCOMPLETE,
                models.CompletionResult.COMPLETE,
            ]
        ),
        max_iterations=3,
    )
    outcome = implementation_agent.run()

    assert outcome.status == "success"
    assert outcome.iterations == 2
    assert len(prompt_builder.inputs) == 2
    _assert_prompt_payloads(prompt_builder.inputs, [None, None])


def test_final_gate_fail_then_recover_with_feedback() -> None:
    """Final gate feedback should be passed to the retry prompt."""
    prompt_builder = FakePromptBuilder()
    agent_runner = FakeAgentRunner(["first", "second"])
    gate_runner = FakeGateRunner(
        [
            models.GateResult(passed=True),
            models.GateResult(passed=False, feedback="fix final gate"),
            models.GateResult(passed=True),
            models.GateResult(passed=True),
        ]
    )

    implementation_agent = ImplementationAgent(
        prompt_builder=prompt_builder,
        agent_runner=agent_runner,
        gate_runner=gate_runner,
        task=FakeTask(
            [
                models.CompletionResult.COMPLETE,
                models.CompletionResult.COMPLETE,
            ]
        ),
        max_iterations=3,
    )
    outcome = implementation_agent.run()

    assert outcome.status == "success"
    assert outcome.iterations == 2
    assert len(prompt_builder.inputs) == 2
    _assert_prompt_payloads(prompt_builder.inputs, [None, "fix final gate"])


def test_all_pass_first_try() -> None:
    """A fully passing flow should complete in a single iteration."""
    prompt_builder = FakePromptBuilder()
    agent_runner = FakeAgentRunner(["only"])
    gate_runner = FakeGateRunner(
        [
            models.GateResult(passed=True),
            models.GateResult(passed=True),
        ]
    )

    implementation_agent = ImplementationAgent(
        prompt_builder=prompt_builder,
        agent_runner=agent_runner,
        gate_runner=gate_runner,
        task=FakeTask([models.CompletionResult.COMPLETE]),
        max_iterations=3,
    )
    outcome = implementation_agent.run()

    assert outcome.status == "success"
    assert outcome.iterations == 1
    assert len(prompt_builder.inputs) == 1
    _assert_prompt_payloads(prompt_builder.inputs, [None])


def test_max_iterations_failure() -> None:
    """Exhausting max iterations should return failed status."""
    prompt_builder = FakePromptBuilder()
    agent_runner = FakeAgentRunner(["first", "second", "third"])
    gate_runner = FakeGateRunner(
        [
            models.GateResult(passed=False, feedback="fail 1"),
            models.GateResult(passed=False, feedback="fail 2"),
            models.GateResult(passed=False, feedback="fail 3"),
        ]
    )
    observer = RecordingObserver()

    implementation_agent = ImplementationAgent(
        prompt_builder=prompt_builder,
        agent_runner=agent_runner,
        gate_runner=gate_runner,
        task=FakeTask(),
        observer=observer,
        max_iterations=3,
    )
    outcome = implementation_agent.run()

    assert outcome.status == "failed"
    assert outcome.iterations == 3
    assert outcome.feedback == "fail 3"
    assert len(prompt_builder.inputs) == 3
    _assert_prompt_payloads(
        prompt_builder.inputs,
        [None, "fail 1", "fail 2"],
    )
    assert observer.failure_calls == ["fail 3"]


def test_max_iterations_complete_in_last_iteration() -> None:
    """Success can occur on the final allowed iteration."""
    prompt_builder = FakePromptBuilder()
    agent_runner = FakeAgentRunner(["first", "second", "third"])
    gate_runner = FakeGateRunner(
        [
            models.GateResult(passed=False, feedback="fail 1"),
            models.GateResult(passed=False, feedback="fail 2"),
            models.GateResult(passed=True),
            models.GateResult(passed=True),
        ]
    )

    implementation_agent = ImplementationAgent(
        prompt_builder=prompt_builder,
        agent_runner=agent_runner,
        gate_runner=gate_runner,
        task=FakeTask(
            [
                models.CompletionResult.COMPLETE,
                models.CompletionResult.COMPLETE,
                models.CompletionResult.COMPLETE,
            ]
        ),
        max_iterations=3,
    )
    outcome = implementation_agent.run()

    assert outcome.status == "success"
    assert outcome.iterations == 3
    assert len(prompt_builder.inputs) == 3
    _assert_prompt_payloads(
        prompt_builder.inputs,
        [None, "fail 1", "fail 2"],
    )


def test_implementation_agent_force_single_failure_feedback() -> None:
    """Gate calls should use stop-on-first-failure mode."""
    prompt_builder = FakePromptBuilder()
    agent_runner = FakeAgentRunner(["first", "second", "third"])
    gate_runner = FakeGateRunner(
        [
            models.GateResult(passed=False, feedback="iteration failure"),
            models.GateResult(passed=True),
            models.GateResult(passed=True),
            models.GateResult(passed=True),
        ]
    )

    implementation_agent = ImplementationAgent(
        prompt_builder=prompt_builder,
        agent_runner=agent_runner,
        gate_runner=gate_runner,
        task=FakeTask(
            [
                models.CompletionResult.INCOMPLETE,
                models.CompletionResult.COMPLETE,
            ]
        ),
        max_iterations=3,
    )
    outcome = implementation_agent.run()

    assert outcome.iterations == 3
    assert outcome.status == "success"
    assert gate_runner.calls == [
        (models.GatePhase.ITERATION_COMPLETE, True),
        (models.GatePhase.ITERATION_COMPLETE, True),
        (models.GatePhase.ITERATION_COMPLETE, True),
        (models.GatePhase.IMPLEMENTATION_COMPLETE, True),
    ]


def test_observer_failure_returns_failed_outcome() -> None:
    """Observer hook failures should become failed orchestrator outcomes."""
    implementation_agent = ImplementationAgent(
        prompt_builder=FakePromptBuilder(),
        agent_runner=FakeAgentRunner(["only"]),
        gate_runner=FakeGateRunner(
            [models.GateResult(passed=True), models.GateResult(passed=True)]
        ),
        task=FakeTask([models.CompletionResult.COMPLETE]),
        observer=RecordingObserver(iteration_error="commit failed"),
        max_iterations=3,
    )

    outcome = implementation_agent.run()

    assert outcome.status == "failed"
    assert outcome.feedback == "commit failed"


def test_success_observer_message_is_returned() -> None:
    """Successful publication messages should be surfaced on the outcome."""
    observer = RecordingObserver()
    implementation_agent = ImplementationAgent(
        prompt_builder=FakePromptBuilder(),
        agent_runner=FakeAgentRunner(["only"]),
        gate_runner=FakeGateRunner(
            [models.GateResult(passed=True), models.GateResult(passed=True)]
        ),
        task=FakeTask([models.CompletionResult.COMPLETE]),
        observer=observer,
        max_iterations=3,
    )

    outcome = implementation_agent.run()

    assert outcome.status == "success"
    assert outcome.publication_message == "published"
    assert observer.iteration_calls == [(1, "only")]
    assert observer.success_calls == 1
