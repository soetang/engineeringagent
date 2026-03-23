"""Implementation task models."""

from developer.orchestrators.loop.models import CompletionResult
from developer.orchestrators.runs.protocols import ImplementationRunTask
from developer.tasks.models import TaskPhaseDefinition, TaskPlanDefinition
from developer.tasks.services.markdown_plan_loader import MarkdownPlanLoader


class MarkdownPlanImplementationTask(ImplementationRunTask):
    """Concrete implementation task backed by a markdown plan file."""

    def __init__(
        self,
        plan: TaskPlanDefinition,
        loader: MarkdownPlanLoader,
    ) -> None:
        """Store the validated plan definition and reload dependencies."""
        self._plan = plan
        self._loader = loader

    @property
    def task_id(self) -> str:
        """Return the stable task identity."""
        return self._plan.task_id

    @property
    def task_name(self) -> str:
        """Return the human-readable task title."""
        return self._plan.title

    @property
    def task_path(self) -> str:
        """Return the canonical markdown plan path."""
        return self._plan.path

    @property
    def base_branch(self) -> str | None:
        """Return the task's preferred base branch from frontmatter."""
        return self._plan.base_branch

    @property
    def status(self) -> str:
        """Return the current top-level task status from the resolved plan."""
        return self._plan.status

    @property
    def phases(self) -> list[TaskPhaseDefinition]:
        """Return the resolved phase definitions."""
        return self._plan.phases

    def is_complete(self) -> CompletionResult:
        """Re-read the plan file and report current completion state."""
        definition = self._reload_definition()
        if definition is None:
            return CompletionResult.INCOMPLETE
        is_complete = definition.status == "done" and all(
            phase.status == "done" for phase in definition.phases
        )
        return CompletionResult.COMPLETE if is_complete else CompletionResult.INCOMPLETE

    def get_branch_name(self) -> str:
        """Return the explicit branch or a stable fallback from task_id."""
        return self._plan.branch or self._plan.task_id

    def _reload_definition(self) -> TaskPlanDefinition | None:
        """Reload the current on-disk plan definition when it is still valid."""
        return self._loader.load_definition_if_valid(self._plan.path)
