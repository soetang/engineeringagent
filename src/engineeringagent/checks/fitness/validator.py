from __future__ import annotations

from pydantic import ValidationError

from engineeringagent.checks.fitness.registry import (
    DEFAULT_CUSTOM_RULE_MANIFEST,
    build_rule_catalog,
)
from engineeringagent.checks.validate.contracts import ValidationContext, ValidationIssue


class FitnessCatalogStrategyValidator:
    """Validate fitness strategy static catalog/manifest contracts."""

    strategy_type = "fitness"
    validator_id = "fitness.catalog"

    def validate(self, *, context: ValidationContext) -> tuple[ValidationIssue, ...]:
        """Return deterministic fitness strategy validation issues."""

        try:
            build_rule_catalog(context.project_root)
        except OSError as exc:
            return (
                ValidationIssue(
                    validator_id=self.validator_id,
                    scope="strategy",
                    path=DEFAULT_CUSTOM_RULE_MANIFEST.as_posix(),
                    message=f"failed to read fitness manifest: {exc}",
                    code="fitness.catalog.read-failure",
                ),
            )
        except (ValidationError, ValueError) as exc:
            return (
                ValidationIssue(
                    validator_id=self.validator_id,
                    scope="strategy",
                    path=DEFAULT_CUSTOM_RULE_MANIFEST.as_posix(),
                    message=str(exc),
                    code="fitness.catalog.invalid-manifest",
                ),
            )
        return ()
