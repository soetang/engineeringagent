from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.checks.validate.contracts import ValidationContext, ValidationIssue
from engineeringagent.checks.validate.repo_validators import RepoPolicyValidator
from engineeringagent.checks.validate.validator import (
    _build_validation_registry,
    validate,
)


def test_build_validation_registry_registers_repo_and_strategy_validators() -> None:
    """Registry builder composes repo + strategy validators with deterministic IDs."""

    registry = _build_validation_registry()

    assert tuple(validator.validator_id for validator in registry.repo_validators) == (
        "repo.policy",
    )
    assert tuple(
        (validator.strategy_type, validator.validator_id)
        for validator in registry.strategy_validators
    ) == (
        ("fitness", "fitness.catalog"),
        ("reviewer", "reviewer.prompt-policy"),
    )


def test_validate_renders_registry_issues_in_deterministic_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validate renders registry issues without altering issue order or content."""

    context_calls: list[ValidationContext] = []

    class _FakeRegistry:
        def run(self, *, context: ValidationContext) -> tuple[ValidationIssue, ...]:
            context_calls.append(context)
            return (
                ValidationIssue(
                    validator_id="repo.policy",
                    scope="repo",
                    path="",
                    message="validate: repo message",
                    code="repo.policy.message",
                ),
                ValidationIssue(
                    validator_id="reviewer.prompt-policy",
                    scope="strategy",
                    path="harness/reviewers/prompts/demo.md",
                    message="reviewer policy failure",
                    code="reviewer.prompt.deprecated-responseformat",
                ),
            )

    monkeypatch.setattr(
        "engineeringagent.checks.validate.validator._build_validation_registry",
        lambda: _FakeRegistry(),
    )

    messages = validate(project_root=tmp_path, schema_only=True)

    assert context_calls == [
        ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=True,
        )
    ]
    assert messages == [
        "validate: repo message",
        "harness/reviewers/prompts/demo.md: reviewer policy failure",
    ]


def test_repo_policy_validator_projects_messages_to_validation_issues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repo adapter converts legacy message lines into canonical ValidationIssue values."""

    calls: list[tuple[Path, Path, bool]] = []

    def _fake_run_repo_validation(
        messages: list[str],
        *,
        project_root: Path,
        docs_root: Path,
        schema_only: bool,
    ) -> None:
        calls.append((project_root, docs_root, schema_only))
        messages.extend(
            [
                "first issue",
                "docs/spec/features/FEAT-100-example.yaml:status: invalid status value",
            ]
        )

    monkeypatch.setattr(
        "engineeringagent.checks.validate.repo_validators.run_repo_validation",
        _fake_run_repo_validation,
    )

    context = ValidationContext(
        project_root=tmp_path,
        docs_root=tmp_path / "docs",
        schema_only=False,
    )
    issues = RepoPolicyValidator().validate(context=context)

    assert calls == [(tmp_path, tmp_path / "docs", False)]
    assert issues == (
        ValidationIssue(
            validator_id="repo.policy",
            scope="repo",
            path="",
            message="first issue",
            code="repo.policy.message",
        ),
        ValidationIssue(
            validator_id="repo.policy",
            scope="repo",
            path="docs/spec/features/FEAT-100-example.yaml:status",
            message="invalid status value",
            code="repo.policy.field-status",
        ),
    )


def test_repo_policy_validator_derives_semantic_issue_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repo adapter emits deterministic semantic rule codes for stable ownership."""

    def _fake_run_repo_validation(
        messages: list[str],
        *,
        project_root: Path,
        docs_root: Path,
        schema_only: bool,
    ) -> None:
        del project_root, docs_root, schema_only
        messages.extend(
            [
                "validate: duplicate base feature id FEAT-101 found in active specs",
                "validate: git ls-files failed: test failure",
                "README.md: forbidden token present (purge invariant): readme_process",
                "docs/spec/features/FEAT-101-example.yaml:id: filename id token FEAT-101 does not match frontmatter id FEAT-102",
            ]
        )

    monkeypatch.setattr(
        "engineeringagent.checks.validate.repo_validators.run_repo_validation",
        _fake_run_repo_validation,
    )

    issues = RepoPolicyValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert tuple(issue.code for issue in issues) == (
        "repo.policy.duplicate-base-id",
        "repo.policy.git-ls-files",
        "repo.policy.purge-invariant",
        "repo.policy.field-id",
    )
