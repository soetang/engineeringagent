from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, cast

import pytest

from engineeringagent.adapters.quality.validation import (
    ValidationContext,
    ValidationIssue,
    ValidationRegistry,
)


class _RepoValidator:
    def __init__(
        self,
        *,
        validator_id: str,
        issues: tuple[ValidationIssue, ...] = (),
    ) -> None:
        self.validator_id = validator_id
        self._issues = issues

    def validate(
        self,
        *,
        context: ValidationContext,
    ) -> tuple[ValidationIssue, ...]:
        del context
        return self._issues


class _StrategyValidator:
    def __init__(
        self,
        *,
        strategy_type: str,
        validator_id: str,
        issues: tuple[ValidationIssue, ...] = (),
    ) -> None:
        self.strategy_type = strategy_type
        self.validator_id = validator_id
        self._issues = issues

    def validate(
        self,
        *,
        context: ValidationContext,
    ) -> tuple[ValidationIssue, ...]:
        del context
        return self._issues


class _ListIssueRepoValidator:
    def __init__(
        self,
        *,
        validator_id: str,
        issues: list[ValidationIssue],
    ) -> None:
        self.validator_id = validator_id
        self._issues = issues

    def validate(
        self,
        *,
        context: ValidationContext,
    ) -> list[ValidationIssue]:
        del context
        return self._issues


class _InvalidTupleIssueRepoValidator:
    def __init__(self, *, validator_id: str, issues: tuple[object, ...]) -> None:
        self.validator_id = validator_id
        self._issues = issues

    def validate(
        self,
        *,
        context: ValidationContext,
    ) -> tuple[object, ...]:
        del context
        return self._issues


def _issue(
    validator_id: str,
    scope: Literal["repo", "strategy"],
    path: str,
    message: str,
    code: str,
) -> ValidationIssue:
    return ValidationIssue(validator_id, scope, path, message, code)


def test_validation_registry_rejects_empty_repo_validator_id() -> None:
    """Repo validator registrations require a non-empty identifier."""

    with pytest.raises(ValueError, match="repo validator_id must be non-empty"):
        ValidationRegistry(repo_validators=[_RepoValidator(validator_id=" ")])


def test_validation_registry_rejects_empty_strategy_validator_fields() -> None:
    """Strategy validator registrations require both strategy type and id."""

    with pytest.raises(
        ValueError, match="strategy validator strategy_type must be non-empty"
    ):
        ValidationRegistry(
            strategy_validators=[
                _StrategyValidator(strategy_type=" ", validator_id="reviewer.rules")
            ]
        )

    with pytest.raises(ValueError, match="strategy validator_id must be non-empty"):
        ValidationRegistry(
            strategy_validators=[
                _StrategyValidator(strategy_type="reviewer", validator_id=" ")
            ]
        )


def test_validation_registry_rejects_duplicate_validator_id() -> None:
    """Validator ids must stay unique across repo and strategy registrations."""

    with pytest.raises(
        ValueError,
        match="duplicate validate validator registration: repo.rules",
    ):
        ValidationRegistry(
            repo_validators=[
                _RepoValidator(validator_id="repo.rules"),
                _RepoValidator(validator_id="repo.rules"),
            ]
        )

    with pytest.raises(
        ValueError,
        match="duplicate validate validator registration: repo.rules",
    ):
        ValidationRegistry(
            repo_validators=[_RepoValidator(validator_id="repo.rules")],
            strategy_validators=[
                _StrategyValidator(
                    strategy_type="reviewer",
                    validator_id="repo.rules",
                )
            ],
        )


def test_validation_registry_runs_in_deterministic_order() -> None:
    """Registry execution order is deterministic after registration sorting."""

    issue_a = _issue("repo.alpha", "repo", "a.yaml", "repo-a", "R001")
    issue_b = _issue("repo.beta", "repo", "b.yaml", "repo-b", "R002")
    issue_c = _issue(
        "fitness.catalog",
        "strategy",
        "catalog.yaml",
        "fitness-c",
        "S001",
    )
    issue_d = _issue(
        "reviewer.prompts",
        "strategy",
        "prompts/foo.md",
        "reviewer-d",
        "S002",
    )

    registry = ValidationRegistry(
        repo_validators=[
            _RepoValidator(validator_id="repo.beta", issues=(issue_b,)),
            _RepoValidator(validator_id="repo.alpha", issues=(issue_a,)),
        ],
        strategy_validators=[
            _StrategyValidator(
                strategy_type="reviewer",
                validator_id="reviewer.prompts",
                issues=(issue_d,),
            ),
            _StrategyValidator(
                strategy_type="fitness",
                validator_id="fitness.catalog",
                issues=(issue_c,),
            ),
        ],
    )

    context = ValidationContext(
        project_root=Path("/tmp/project"),
        docs_root=Path("/tmp/project/docs"),
        schema_only=False,
    )
    issues = registry.run(context=context)

    assert tuple(validator.validator_id for validator in registry.repo_validators) == (
        "repo.alpha",
        "repo.beta",
    )
    assert tuple(
        (validator.strategy_type, validator.validator_id)
        for validator in registry.strategy_validators
    ) == (
        ("fitness", "fitness.catalog"),
        ("reviewer", "reviewer.prompts"),
    )
    assert issues == (issue_a, issue_b, issue_c, issue_d)


def test_validation_registry_filters_strategy_validators_by_selected_groups() -> None:
    """Selected groups filter strategy validators without skipping repo validators."""

    issue_repo = _issue("repo.policy", "repo", "", "repo", "R001")
    issue_fitness = _issue("fitness.catalog", "strategy", "", "fitness", "S001")
    issue_reviewer = _issue(
        "reviewer.prompts",
        "strategy",
        "",
        "reviewer",
        "S002",
    )

    registry = ValidationRegistry(
        repo_validators=[_RepoValidator(validator_id="repo.policy", issues=(issue_repo,))],
        strategy_validators=[
            _StrategyValidator(
                strategy_type="fitness",
                validator_id="fitness.catalog",
                issues=(issue_fitness,),
            ),
            _StrategyValidator(
                strategy_type="reviewer",
                validator_id="reviewer.prompts",
                issues=(issue_reviewer,),
            ),
        ],
    )

    context = ValidationContext(
        project_root=Path("/tmp/project"),
        docs_root=Path("/tmp/project/docs"),
        schema_only=False,
        selected_groups=("reviewer",),
    )

    assert registry.run(context=context) == (issue_repo, issue_reviewer)


def test_validation_registry_requires_tuple_issue_containers() -> None:
    """Validators must return tuples to satisfy the registry contract."""

    registry = ValidationRegistry(
        repo_validators=[
            cast(
                Any,
                _ListIssueRepoValidator(
                    validator_id="repo.policy",
                    issues=[],
                ),
            )
        ]
    )

    context = ValidationContext(
        project_root=Path("/tmp/project"),
        docs_root=Path("/tmp/project/docs"),
        schema_only=False,
    )

    with pytest.raises(
        ValueError,
        match="validate issue container type mismatch for repo.policy: expected tuple, got list",
    ):
        registry.run(context=context)


def test_validation_registry_requires_validation_issue_items() -> None:
    """Validators must return `ValidationIssue` objects inside their tuples."""

    registry = ValidationRegistry(
        repo_validators=[
            cast(
                Any,
                _InvalidTupleIssueRepoValidator(
                    validator_id="repo.policy",
                    issues=("bad",),
                ),
            )
        ]
    )

    context = ValidationContext(
        project_root=Path("/tmp/project"),
        docs_root=Path("/tmp/project/docs"),
        schema_only=False,
    )

    with pytest.raises(
        ValueError,
        match="validate issue item type mismatch for repo.policy: expected ValidationIssue, got str",
    ):
        registry.run(context=context)


def test_validation_registry_requires_matching_issue_scope() -> None:
    """Registry rejects issues whose scope disagrees with validator ownership."""

    wrong_scope_registry = ValidationRegistry(
        repo_validators=[
            _RepoValidator(
                validator_id="repo.policy",
                issues=(
                    _issue(
                        "repo.policy",
                        "strategy",
                        "",
                        "wrong scope",
                        "R001",
                    ),
                ),
            )
        ]
    )

    context = ValidationContext(
        project_root=Path("/tmp/project"),
        docs_root=Path("/tmp/project/docs"),
        schema_only=False,
    )

    with pytest.raises(
        ValueError,
        match="validate issue scope mismatch for repo.policy: expected repo, got strategy",
    ):
        wrong_scope_registry.run(context=context)


def test_validation_registry_requires_matching_issue_validator_id() -> None:
    """Registry rejects issues whose validator id differs from the emitter."""

    wrong_validator_registry = ValidationRegistry(
        repo_validators=[
            _RepoValidator(
                validator_id="repo.policy",
                issues=(
                    _issue(
                        "repo.other",
                        "repo",
                        "",
                        "wrong validator",
                        "R001",
                    ),
                ),
            )
        ]
    )

    context = ValidationContext(
        project_root=Path("/tmp/project"),
        docs_root=Path("/tmp/project/docs"),
        schema_only=False,
    )

    with pytest.raises(
        ValueError,
        match="validate issue validator_id mismatch for repo.policy: got repo.other",
    ):
        wrong_validator_registry.run(context=context)
