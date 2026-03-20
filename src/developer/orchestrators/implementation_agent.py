"""Loop-based orchestrator for iterative agent execution."""

from .models import AgentResult, CompletionResult, GatePhase, ImplementationContext
from .models import OrchestratorOutcome, RunPublicationResult
from .protocols import (
    AgentRunner,
    GateRunner,
    ImplementationLifecycleObserver,
    ImplementationTask,
    PromptBuilder,
)


class ImplementationAgent:
    """Execute an implementation task through repeated agent and gate cycles."""

    def __init__(
        self,
        prompt_builder: PromptBuilder,
        agent_runner: AgentRunner,
        gate_runner: GateRunner,
        task: ImplementationTask,
        observer: ImplementationLifecycleObserver | None = None,
        context: ImplementationContext | None = None,
        max_iterations: int = 3,
    ) -> None:
        """Create an implementation agent wired to its dependencies.

        Args:
            prompt_builder: Builds prompts for each loop iteration.
            agent_runner: Runs the agent with a rendered prompt.
            gate_runner: Executes quality gates for each phase.
            task: Determines whether the task is complete.
            observer: Optional lifecycle observer for side effects.
            context: Optional typed execution context.
            max_iterations: Maximum number of loop iterations.
        """
        self._prompt_builder = prompt_builder
        self._agent_runner = agent_runner
        self._gate_runner = gate_runner
        self._task = task
        self._observer = observer
        self._context = context or ImplementationContext(
            task_name=task.task_name,
            task_path=task.task_path,
            task_branch_name=task.get_branch_name(),
        )
        self._max_iterations = max_iterations

    def run(self) -> OrchestratorOutcome:
        """Run the implementation loop."""
        feedback: str | None = None
        for attempt in range(1, self._max_iterations + 1):
            prompt = self._prompt_builder.build(
                {
                    "feedback": feedback,
                    "task_name": self._task.task_name,
                    "task_path": self._task.task_path,
                }
            )
            agent_result = AgentResult.model_validate(
                self._agent_runner.run_agent(prompt, output_format=AgentResult)
            )
            self._context = self._context.model_copy(
                update={"latest_change_summary": agent_result.summary}
            )

            feedback = self._run_gate_feedback(GatePhase.ITERATION_COMPLETE)
            if feedback is not None:
                continue

            observer_feedback = self._notify_iteration_passed(attempt, agent_result)
            if observer_feedback is not None:
                return OrchestratorOutcome(
                    status="failed",
                    iterations=attempt,
                    feedback=observer_feedback,
                )

            completion = self._task.is_complete()
            if completion == CompletionResult.INCOMPLETE:
                feedback = None
                continue

            feedback = self._run_gate_feedback(GatePhase.IMPLEMENTATION_COMPLETE)
            if feedback is not None:
                continue

            publication_feedback, publication = self._notify_run_succeeded(attempt)
            if publication_feedback is not None:
                return OrchestratorOutcome(
                    status="failed",
                    iterations=attempt,
                    feedback=publication_feedback,
                )
            return OrchestratorOutcome(
                status="success",
                iterations=attempt,
                publication_message=publication.message if publication else None,
            )

        self._notify_run_failed(self._max_iterations, feedback)
        return OrchestratorOutcome(
            status="failed",
            iterations=self._max_iterations,
            feedback=feedback,
        )

    def _run_gate_feedback(self, phase: GatePhase) -> str | None:
        """Run a gate for a phase and return feedback when it fails."""
        gate_result = self._gate_runner.check(phase, stop_on_first_failure=True)
        if gate_result.passed:
            return None
        return gate_result.feedback

    def _notify_iteration_passed(
        self,
        attempt: int,
        agent_result: AgentResult,
    ) -> str | None:
        """Run the iteration observer hook and convert errors into feedback."""
        if self._observer is None:
            return None
        try:
            self._observer.on_iteration_passed(attempt, self._context, agent_result)
        except Exception as exc:
            return str(exc)
        return None

    def _notify_run_succeeded(
        self,
        attempt: int,
    ) -> tuple[str | None, RunPublicationResult | None]:
        """Run the success observer hook and convert errors into feedback."""
        if self._observer is None:
            return None, None
        try:
            return None, self._observer.on_run_succeeded(attempt, self._context)
        except Exception as exc:
            return str(exc), None

    def _notify_run_failed(self, attempt: int, feedback: str | None) -> None:
        """Run the failure observer hook and ignore cleanup failures."""
        if self._observer is None:
            return
        try:
            self._observer.on_run_failed(attempt, self._context, feedback)
        except Exception:
            return
