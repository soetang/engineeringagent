"""Load markdown task plans through one parse/validate/build flow."""

from engineeringagent.tasks.errors import TaskPlanValidationError
from engineeringagent.tasks.models import PlanValidationResult, TaskPlanDefinition
from engineeringagent.tasks.services.markdown_plan_parser import MarkdownPlanParser
from engineeringagent.tasks.services.plan_validator import PlanValidator


class MarkdownPlanLoader:
    """Load and validate markdown task plans."""

    def __init__(
        self,
        parser: MarkdownPlanParser | None = None,
        validator: PlanValidator | None = None,
    ) -> None:
        """Store parsing and validation dependencies."""
        self._parser = parser or MarkdownPlanParser()
        self._validator = validator or PlanValidator()

    def validate(self, task_input: str) -> PlanValidationResult:
        """Return structured semantic validation errors for one plan."""
        frontmatter, _canonical_path = self._parse_frontmatter(task_input)
        return self._validator.validate(frontmatter)

    def load_definition(self, task_input: str) -> TaskPlanDefinition:
        """Load one valid task plan definition or raise a validation error."""
        frontmatter, canonical_path = self._parse_frontmatter(task_input)
        validation = self._validator.validate(frontmatter)
        if not validation.valid:
            self._raise_validation_error(canonical_path, validation)
        return self._validator.build_definition(frontmatter, canonical_path)

    def load_definition_if_valid(self, task_input: str) -> TaskPlanDefinition | None:
        """Load one task plan definition, returning None for semantic invalidity."""
        frontmatter, canonical_path = self._parse_frontmatter(task_input)
        validation = self._validator.validate(frontmatter)
        if not validation.valid:
            return None
        return self._validator.build_definition(frontmatter, canonical_path)

    def _parse_frontmatter(self, task_input: str) -> tuple[dict[str, object], str]:
        """Parse one plan and return frontmatter plus canonical path."""
        frontmatter, _body, canonical_path = self._parser.parse(task_input)
        return frontmatter, canonical_path

    def _raise_validation_error(
        self,
        canonical_path: str,
        validation: PlanValidationResult,
    ) -> None:
        """Raise one formatted validation error for CLI-facing flows."""
        error_lines = [
            f"{error.location}: {error.message}" for error in validation.errors
        ]
        raise TaskPlanValidationError(
            f"Plan validation failed: {canonical_path}\n" + "\n".join(error_lines)
        )
