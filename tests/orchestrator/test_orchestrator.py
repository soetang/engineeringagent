"""Unit tests for the orchestrator loop with fake adapters."""

from collections.abc import Iterable

from developer.orchestrator import models
from developer.orchestrator.orchestrator import AgentOrchestrator


class FakePromptBuilder:
    """Prompt builder that records every injection payload."""

    def __init__(self) -> None:
        """Initialize an empty prompt input history."""
        self.inputs: list[dict] = []

    def build(self, injections: dict) -> str:
        """Record the payload and return a deterministic prompt."""
        self.inputs.append(dict(injections))
        return (
            f"TASK={injections.get('task')}|"
            f"FEEDBACK={injections.get('feedback')}|"
            f"ITERATION={injections.get('iteration')}"
        )


class FakeAgentRunner:
    """Agent runner with scripted results."""

    def __init__(self, results: Iterable[str] | None = None) -> None:
        """Initialize the runner with scripted summaries."""
        self.results = list(results or ["ok"])
        self.runs = 0

    def run(self, prompt: str, output_format=None) -> models.AgentResult:  # noqa: ARG002
        """Pop and return the next scripted agent result."""
        self.runs += 1
        if not self.results:
            self.results = ["ok"]
        summary = self.results.pop(0)
        return models.AgentResult(summary=summary)


class FakeGateRunner:
    """Gate runner with scripted pass/fail results."""

    def __init__(self, checks: Iterable[models.GateResult]) -> None:
        """Initialize scripted gate check results."""
        self.checks = list(checks)
        self.calls: list[models.GatePhase] = []

    def check(self, phase: models.GatePhase) -> models.GateResult:
        """Return the next scripted gate result."""
        self.calls.append(phase)
        return self.checks.pop(0)


class FakeCompletionJudge:
    """Completion judge with scripted completion states."""

    def __init__(self, states: Iterable[models.CompletionResult] | None = None) -> None:
        """Initialize scripted completion states."""
        self.states = list(states or [models.CompletionResult.COMPLETE])

    def is_complete(self) -> models.CompletionResult:
        """Return the next scripted completion state."""
        if not self.states:
            return models.CompletionResult.COMPLETE
        return self.states.pop(0)


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
    completion_judge = FakeCompletionJudge([models.CompletionResult.COMPLETE])

    orchestrator = AgentOrchestrator(
        prompt_builder=prompt_builder,
        agent_runner=agent_runner,
        gate_runner=gate_runner,
        completion_judge=completion_judge,
    )
    outcome = orchestrator.run("first task")

    assert outcome.status == "success"
    assert outcome.iterations == 2
    assert len(prompt_builder.inputs) == 2
    assert prompt_builder.inputs[0]["feedback"] is None
    assert prompt_builder.inputs[1]["feedback"] == "fix fast gate"


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
    completion_judge = FakeCompletionJudge(
        [
            models.CompletionResult.INCOMPLETE,
            models.CompletionResult.COMPLETE,
        ]
    )

    orchestrator = AgentOrchestrator(
        prompt_builder=prompt_builder,
        agent_runner=agent_runner,
        gate_runner=gate_runner,
        completion_judge=completion_judge,
    )
    outcome = orchestrator.run("second task")

    assert outcome.status == "success"
    assert outcome.iterations == 2
    assert len(prompt_builder.inputs) == 2
    assert prompt_builder.inputs[0]["feedback"] is None
    assert prompt_builder.inputs[1]["feedback"] is None


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
    completion_judge = FakeCompletionJudge(
        [
            models.CompletionResult.COMPLETE,
            models.CompletionResult.COMPLETE,
        ]
    )

    orchestrator = AgentOrchestrator(
        prompt_builder=prompt_builder,
        agent_runner=agent_runner,
        gate_runner=gate_runner,
        completion_judge=completion_judge,
    )
    outcome = orchestrator.run("third task")

    assert outcome.status == "success"
    assert outcome.iterations == 2
    assert len(prompt_builder.inputs) == 2
    assert prompt_builder.inputs[1]["feedback"] == "fix final gate"


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
    completion_judge = FakeCompletionJudge([models.CompletionResult.COMPLETE])

    orchestrator = AgentOrchestrator(
        prompt_builder=prompt_builder,
        agent_runner=agent_runner,
        gate_runner=gate_runner,
        completion_judge=completion_judge,
    )
    outcome = orchestrator.run("fourth task")

    assert outcome.status == "success"
    assert outcome.iterations == 1
    assert len(prompt_builder.inputs) == 1


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
    completion_judge = FakeCompletionJudge()

    orchestrator = AgentOrchestrator(
        prompt_builder=prompt_builder,
        agent_runner=agent_runner,
        gate_runner=gate_runner,
        completion_judge=completion_judge,
        max_iterations=3,
    )
    outcome = orchestrator.run("failing task")

    assert outcome.status == "failed"
    assert outcome.iterations == 3
    assert len(prompt_builder.inputs) == 3


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
    completion_judge = FakeCompletionJudge(
        [
            models.CompletionResult.COMPLETE,
            models.CompletionResult.COMPLETE,
            models.CompletionResult.COMPLETE,
        ]
    )

    orchestrator = AgentOrchestrator(
        prompt_builder=prompt_builder,
        agent_runner=agent_runner,
        gate_runner=gate_runner,
        completion_judge=completion_judge,
        max_iterations=3,
    )
    outcome = orchestrator.run("failing task")

    assert outcome.status == "success"
    assert outcome.iterations == 3
    assert len(prompt_builder.inputs) == 3
