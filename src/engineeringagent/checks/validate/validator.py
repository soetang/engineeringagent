from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.config import resolve_specifications_root

from .contracts import ValidationContext, ValidationIssue
from .repo_validators import RepoPolicyValidator
from .registry import ValidationRegistry
from .strategy_validators import default_strategy_validators


def validate(project_root: Path, schema_only: bool = False) -> list[str]:
    """Validate repository documents and static check-domain contracts."""

    specifications_root = resolve_specifications_root(project_root)
    docs_root = specifications_root.parent
    context = ValidationContext(
        project_root=project_root,
        docs_root=docs_root,
        schema_only=schema_only,
    )
    registry = _build_validation_registry()
    return _render_validation_messages(registry.run(context=context))


def _build_validation_registry() -> ValidationRegistry:
    """Build deterministic repo-policy + strategy validator composition."""

    return ValidationRegistry(
        repo_validators=[RepoPolicyValidator()],
        strategy_validators=default_strategy_validators(),
    )


def _render_validation_messages(
    issues: tuple[ValidationIssue, ...],
) -> list[str]:
    """Render stable user-facing validate output lines."""

    messages: list[str] = []
    for issue in issues:
        if issue.path:
            messages.append(f"{issue.path}: {issue.message}")
            continue
        messages.append(issue.message)
    return messages
