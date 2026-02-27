from __future__ import annotations

from collections.abc import Iterable

from engineeringagent.checks.validate.contracts import (
    RepoValidator,
    StrategyValidator,
    ValidationContext,
    ValidationIssue,
)


class ValidationRegistry:
    """Deterministic registry for repo and optional strategy validators."""

    def __init__(
        self,
        *,
        repo_validators: Iterable[RepoValidator] = (),
        strategy_validators: Iterable[StrategyValidator] = (),
    ) -> None:
        repo_registry: dict[str, RepoValidator] = {}
        strategy_registry: dict[str, StrategyValidator] = {}

        for validator in repo_validators:
            validator_id = validator.validator_id.strip()
            if not validator_id:
                raise ValueError("validate repo validator_id must be non-empty")
            if validator_id in repo_registry or validator_id in strategy_registry:
                raise ValueError(
                    f"duplicate validate validator registration: {validator_id}"
                )
            repo_registry[validator_id] = validator

        for validator in strategy_validators:
            strategy_type = validator.strategy_type.strip()
            validator_id = validator.validator_id.strip()
            if not strategy_type:
                raise ValueError("validate strategy validator strategy_type must be non-empty")
            if not validator_id:
                raise ValueError("validate strategy validator_id must be non-empty")
            if validator_id in repo_registry or validator_id in strategy_registry:
                raise ValueError(
                    f"duplicate validate validator registration: {validator_id}"
                )
            strategy_registry[validator_id] = validator

        self._repo_validators = tuple(
            repo_registry[validator_id]
            for validator_id in sorted(repo_registry)
        )
        self._strategy_validators = tuple(
            strategy_registry[validator_id]
            for validator_id in sorted(
                strategy_registry,
                key=lambda validator_id: (
                    strategy_registry[validator_id].strategy_type,
                    validator_id,
                ),
            )
        )

    @property
    def repo_validators(self) -> tuple[RepoValidator, ...]:
        """Deterministically sorted repository validators."""
        return self._repo_validators

    @property
    def strategy_validators(self) -> tuple[StrategyValidator, ...]:
        """Deterministically sorted optional strategy validators."""
        return self._strategy_validators

    def run(self, *, context: ValidationContext) -> tuple[ValidationIssue, ...]:
        """Run all registered validators in deterministic registry order."""
        issues: list[ValidationIssue] = []
        selected_groups = (
            frozenset(context.selected_groups)
            if context.selected_groups is not None
            else None
        )
        for validator in self._repo_validators:
            validator_issues = validator.validate(context=context)
            validator_issues = self._validate_issue_contracts(
                validator_issues,
                expected_scope="repo",
                validator_id=validator.validator_id,
            )
            issues.extend(validator_issues)
        for validator in self._strategy_validators:
            if (
                selected_groups is not None
                and validator.strategy_type not in selected_groups
            ):
                continue
            validator_issues = validator.validate(context=context)
            validator_issues = self._validate_issue_contracts(
                validator_issues,
                expected_scope="strategy",
                validator_id=validator.validator_id,
            )
            issues.extend(validator_issues)
        return tuple(issues)

    @staticmethod
    def _validate_issue_contracts(
        issues: object,
        *,
        expected_scope: str,
        validator_id: str,
    ) -> tuple[ValidationIssue, ...]:
        if not isinstance(issues, tuple):
            raise ValueError(
                "validate issue container type mismatch for "
                f"{validator_id}: expected tuple, got {type(issues).__name__}"
            )
        for issue in issues:
            if not isinstance(issue, ValidationIssue):
                raise ValueError(
                    "validate issue item type mismatch for "
                    f"{validator_id}: expected ValidationIssue, got {type(issue).__name__}"
                )
            if issue.scope != expected_scope:
                raise ValueError(
                    "validate issue scope mismatch for "
                    f"{validator_id}: expected {expected_scope}, got {issue.scope}"
                )
            if issue.validator_id != validator_id:
                raise ValueError(
                    "validate issue validator_id mismatch for "
                    f"{validator_id}: got {issue.validator_id}"
                )
        return issues
