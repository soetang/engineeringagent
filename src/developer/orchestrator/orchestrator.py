"""Loop-based orchestrator for iterative agent execution."""

from .models import (
    AgentResult,
    CompletionResult,
    GatePhase,
    OrchestratorOutcome,
)
from .protocols import AgentRunner, CompletionJudge, GateRunner, PromptBuilder


class AgentOrchestrator:
    """Execute a task through repeated agent and gate cycles."""

    def __init__(
        self,
        prompt_builder: PromptBuilder,
        agent_runner: AgentRunner,
        gate_runner: GateRunner,
        completion_judge: CompletionJudge,
        max_iterations: int = 3,
    ) -> None:
        """Create an orchestrator wired to its collaboration dependencies.

        Args:
            prompt_builder: Builds prompts for each loop iteration.
            agent_runner: Runs the agent with a rendered prompt.
            gate_runner: Executes quality gates for each phase.
            completion_judge: Indicates whether the task is complete.
            max_iterations: Maximum number of loop iterations.
        """
        self._prompt_builder = prompt_builder
        self._agent_runner = agent_runner
        self._gate_runner = gate_runner
        self._completion_judge = completion_judge
        self._max_iterations = max_iterations

    def run(
        self,
        task: str,
        injections: dict | None = None,
    ) -> OrchestratorOutcome:
        """Run the orchestrator loop for a single task.

        Args:
            task: The task instruction for the agent loop.
            injections: Optional context provided by callers (currently ignored
                for prompt rendering).

        Returns:
            OrchestratorOutcome: minimal loop result payload.
        """
        feedback: str | None = None
        for attempt in range(1, self._max_iterations + 1):
            prompt = self._prompt_builder.build({"feedback": feedback})
            _ = self._agent_runner.run_agent(prompt, output_format=AgentResult)

            feedback = self._run_gate_feedback(GatePhase.ITERATION_COMPLETE)
            if feedback is not None:
                continue

            completion = self._completion_judge.is_complete()
            if completion == CompletionResult.INCOMPLETE:
                feedback = None
                continue

            feedback = self._run_gate_feedback(GatePhase.IMPLEMENTATION_COMPLETE)
            if feedback is not None:
                continue

            return OrchestratorOutcome(status="success", iterations=attempt)

        return OrchestratorOutcome(status="failed", iterations=self._max_iterations)

    def _run_gate_feedback(self, phase: GatePhase) -> str | None:
        """Run a gate for a phase and return feedback when it fails."""
        gate_result = self._gate_runner.check(phase, stop_on_first_failure=True)
        if gate_result.passed:
            return None
        return gate_result.feedback
