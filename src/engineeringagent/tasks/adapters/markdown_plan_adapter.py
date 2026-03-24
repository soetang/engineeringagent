"""Task adapter for markdown plans with YAML frontmatter."""

from engineeringagent.tasks.adapter_protocol import TaskAdapter
from engineeringagent.tasks.implementation_task import MarkdownPlanImplementationTask
from engineeringagent.tasks.models import PlanValidationResult
from engineeringagent.tasks.services.markdown_plan_loader import MarkdownPlanLoader


class MarkdownPlanAdapter(TaskAdapter):
    """Resolve markdown task plan inputs into concrete task objects."""

    def __init__(
        self,
        loader: MarkdownPlanLoader | None = None,
    ) -> None:
        """Store the markdown plan loader dependency."""
        self._loader = loader or MarkdownPlanLoader()

    def can_resolve(self, task_input: str) -> bool:
        """Return whether the input looks like a markdown plan path."""
        normalized = task_input[1:] if task_input.startswith("@") else task_input
        return normalized.endswith(".md")

    def resolve(self, task_input: str) -> MarkdownPlanImplementationTask:
        """Resolve a valid markdown plan into a concrete task object."""
        definition = self._loader.load_definition(task_input)
        return MarkdownPlanImplementationTask(plan=definition, loader=self._loader)

    def validate(self, task_input: str) -> PlanValidationResult:
        """Validate one markdown plan path."""
        return self._loader.validate(task_input)
