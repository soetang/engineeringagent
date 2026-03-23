"""Validation helpers for markdown-backed task plans."""

import re
from typing import Any
from collections.abc import Mapping

from developer.tasks.models import (
    PlanValidationError,
    PlanValidationResult,
    TaskPhaseDefinition,
    TaskPlanDefinition,
)

TASK_STATUSES = {"draft", "ready", "in_progress", "blocked", "done"}
PHASE_STATUSES = {"todo", "in_progress", "blocked", "done"}
TASK_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class PlanValidator:
    """Validate frontmatter for markdown task plans."""

    def validate(self, frontmatter: dict[str, object]) -> PlanValidationResult:
        """Return all semantic validation errors for one parsed plan."""
        errors: list[PlanValidationError] = []

        schema_version = _require_int(frontmatter, "schema_version", errors)
        task_id = _require_string(frontmatter, "task_id", errors)
        _require_string(frontmatter, "title", errors)
        status = _require_string(frontmatter, "status", errors)
        phases_value = frontmatter.get("phases")

        if schema_version is not None and schema_version != 1:
            errors.append(
                PlanValidationError(
                    location="schema_version",
                    message="schema_version must be 1",
                )
            )

        if task_id is not None and not TASK_ID_PATTERN.fullmatch(task_id):
            errors.append(
                PlanValidationError(
                    location="task_id",
                    message="task_id must be a lowercase hyphenated slug",
                )
            )

        if status is not None and status not in TASK_STATUSES:
            errors.append(
                PlanValidationError(
                    location="status",
                    message=(
                        "status must be one of draft, ready, in_progress, blocked, done"
                    ),
                )
            )

        self._validate_optional_string(frontmatter, "branch", errors)
        self._validate_optional_string(frontmatter, "base_branch", errors)
        self._validate_optional_string(frontmatter, "workspace_provider", errors)
        self._validate_optional_string(frontmatter, "agent_kind", errors)
        phases = self._validate_phases(phases_value, errors)

        if status == "done" and phases is not None:
            incomplete = [phase.id for phase in phases if phase.status != "done"]
            if incomplete:
                errors.append(
                    PlanValidationError(
                        location="status",
                        message="task cannot be 'done' until all phases are 'done'",
                    )
                )

        return PlanValidationResult(valid=not errors, errors=errors)

    def build_definition(
        self, frontmatter: dict[str, object], plan_path: str
    ) -> TaskPlanDefinition:
        """Build a typed plan definition after validation succeeds."""
        phases_value = frontmatter.get("phases", [])
        if not isinstance(phases_value, list):
            raise TypeError(f"Expected phases to be a list, got: {phases_value!r}")
        schema_version_value = frontmatter["schema_version"]
        if isinstance(schema_version_value, bool) or not isinstance(
            schema_version_value, int
        ):
            raise TypeError(
                f"Expected integer schema_version, got: {schema_version_value!r}"
            )
        return TaskPlanDefinition(
            schema_version=schema_version_value,
            task_id=str(frontmatter["task_id"]),
            title=str(frontmatter["title"]),
            status=str(frontmatter["status"]),
            branch=_optional_string(frontmatter.get("branch")),
            base_branch=_optional_string(frontmatter.get("base_branch")),
            workspace_provider=_optional_string(frontmatter.get("workspace_provider")),
            agent_kind=_optional_string(frontmatter.get("agent_kind")),
            phases=[
                TaskPhaseDefinition.model_validate(phase) for phase in phases_value
            ],
            path=plan_path,
        )

    def _validate_optional_string(
        self,
        frontmatter: dict[str, object],
        field_name: str,
        errors: list[PlanValidationError],
    ) -> None:
        """Validate one optional non-empty string field."""
        if field_name not in frontmatter:
            return
        value = frontmatter[field_name]
        if not isinstance(value, str) or not value.strip():
            errors.append(
                PlanValidationError(
                    location=field_name,
                    message=f"{field_name} must be a non-empty string",
                )
            )

    def _validate_phases(
        self,
        phases_value: object,
        errors: list[PlanValidationError],
    ) -> list[TaskPhaseDefinition] | None:
        """Validate the phases list and return typed phases when possible."""
        if phases_value is None:
            errors.append(
                PlanValidationError(
                    location="phases",
                    message="phases is required",
                )
            )
            return None
        if not isinstance(phases_value, list):
            errors.append(
                PlanValidationError(
                    location="phases",
                    message="phases must be a list",
                )
            )
            return None
        if not phases_value:
            errors.append(
                PlanValidationError(
                    location="phases",
                    message="phases must include at least one phase",
                )
            )
            return None

        phases: list[TaskPhaseDefinition] = []
        phase_ids: set[str] = set()
        for index, phase_value in enumerate(phases_value):
            location = f"phases[{index}]"
            if not isinstance(phase_value, Mapping):
                errors.append(
                    PlanValidationError(
                        location=location,
                        message="phase must be an object",
                    )
                )
                continue

            phase_id = _require_string(phase_value, "id", errors, prefix=location)
            phase_title = _require_string(phase_value, "title", errors, prefix=location)
            phase_status = _require_string(
                phase_value, "status", errors, prefix=location
            )

            if phase_id is not None:
                if phase_id in phase_ids:
                    errors.append(
                        PlanValidationError(
                            location=f"{location}.id",
                            message=f"duplicate phase id: {phase_id}",
                        )
                    )
                phase_ids.add(phase_id)

            if phase_status is not None and phase_status not in PHASE_STATUSES:
                errors.append(
                    PlanValidationError(
                        location=f"{location}.status",
                        message=(
                            "phase status must be one of todo, in_progress, blocked, done"
                        ),
                    )
                )

            if (
                phase_id is not None
                and phase_title is not None
                and phase_status is not None
                and phase_status in PHASE_STATUSES
            ):
                phases.append(
                    TaskPhaseDefinition(
                        id=phase_id,
                        title=phase_title,
                        status=phase_status,
                    )
                )

        return phases


def _require_int(
    payload: dict[str, object],
    field_name: str,
    errors: list[PlanValidationError],
) -> int | None:
    """Return a required integer field when valid."""
    value = payload.get(field_name)
    if value is None:
        errors.append(
            PlanValidationError(
                location=field_name,
                message=f"{field_name} is required",
            )
        )
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(
            PlanValidationError(
                location=field_name,
                message=f"{field_name} must be an integer",
            )
        )
        return None
    return value


def _require_string(
    payload: Mapping[str, Any],
    field_name: str,
    errors: list[PlanValidationError],
    prefix: str | None = None,
) -> str | None:
    """Return a required non-empty string field when valid."""
    value = payload.get(field_name)
    location = f"{prefix}.{field_name}" if prefix else field_name
    if value is None:
        errors.append(
            PlanValidationError(
                location=location,
                message=f"{field_name} is required",
            )
        )
        return None
    if not isinstance(value, str) or not value.strip():
        errors.append(
            PlanValidationError(
                location=location,
                message=f"{field_name} must be a non-empty string",
            )
        )
        return None
    return value.strip()


def _optional_string(value: object) -> str | None:
    """Return a stripped string value or None."""
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None
