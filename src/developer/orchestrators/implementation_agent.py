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
        *,
        max_iterations: int | None,
        observer: ImplementationLifecycleObserver | None = None,
        context: ImplementationContext | None = None,
    ) -> None:
        """Create an implementation agent wired to its dependencies.

        Args:
            prompt_builder: Builds prompts for each loop iteration.
            agent_runner: Runs the agent with a rendered prompt.
            gate_runner: Executes quality gates for each phase.
            task: Determines whether the task is complete.
            observer: Optional lifecycle observer for side effects.
            context: Optional typed execution context.
            max_iterations: Maximum number of loop iterations, or None for unbounded.
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
        attempt = 0
        while self._should_continue(attempt):
            attempt += 1
            prompt = self._prompt_builder.build(self._build_prompt_context(feedback))
            agent_result = AgentResult.model_validate(
                self._agent_runner.run_agent(prompt, output_format=AgentResult)
            )
            self._update_latest_change_summary(agent_result.summary)

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

            publication_feedback, publication = self._notify_run_succeeded()
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

        self._notify_run_failed(feedback)
        return OrchestratorOutcome(
            status="failed",
            iterations=attempt,
            feedback=feedback,
        )

    def _should_continue(self, attempt: int) -> bool:
        """Return whether another implementation iteration may run."""
        return self._max_iterations is None or attempt < self._max_iterations

    def _build_prompt_context(self, feedback: str | None) -> dict[str, str | None]:
        """Build the prompt payload for the next agent iteration."""
        return {
            "feedback": feedback,
            "task_path": self._task.task_path,
        }

    def _update_latest_change_summary(self, summary: str) -> None:
        """Store the latest agent summary on the shared execution context."""
        self._context = self._context.model_copy(
            update={"latest_change_summary": summary}
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
    ) -> tuple[str | None, RunPublicationResult | None]:
        """Run the success observer hook and convert errors into feedback."""
        if self._observer is None:
            return None, None
        try:
            return None, self._observer.on_run_succeeded(self._context)
        except Exception as exc:
            return str(exc), None

    def _notify_run_failed(self, feedback: str | None) -> None:
        """Run the failure observer hook and ignore cleanup failures."""
        if self._observer is None:
            return
        try:
            self._observer.on_run_failed(self._context, feedback)
        except Exception:
            return
