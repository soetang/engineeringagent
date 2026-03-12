from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from engineeringagent.adapters.documents import (
    ChecksCatalogLoadOptions,
    FilesystemChecksCatalogRepository,
    load_harness_checks_document,
)
from engineeringagent.ports import ValidationFailure

from tests.checks.run_checks_contract_support import write_checks_yaml


def test_filesystem_checks_catalog_repository_loads_valid_catalog(
    tmp_path: Path,
) -> None:
    """The adapter should return the validated document for a valid catalog."""
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "echo ok"',
                "",
            ]
        ),
    )

    result = FilesystemChecksCatalogRepository().load(tmp_path)

    assert "smoke" in result.checks


def test_filesystem_checks_catalog_repository_returns_deterministic_error(
    tmp_path: Path,
) -> None:
    """The adapter should preserve the shared deterministic missing-file error."""
    with pytest.raises(
        ValidationFailure,
        match="checks config error: missing harness/checks.yaml",
    ):
        FilesystemChecksCatalogRepository().load(tmp_path)


def test_filesystem_checks_catalog_repository_supports_custom_error_context(
    tmp_path: Path,
) -> None:
    """The adapter should support run-loop specific preflight wording."""
    repository = FilesystemChecksCatalogRepository(
        ChecksCatalogLoadOptions(
            error_prefix="run config error",
            missing_context=" (required for --all)",
        )
    )

    with pytest.raises(ValidationFailure) as exc_info:
        repository.load(tmp_path)

    assert (
        exc_info.value.message
        == "run config error: missing harness/checks.yaml "
        "(required for --all). Remediation: run `engineeringagent init`."
    )


def test_load_harness_checks_document_missing_file_returns_actionable_error(
    tmp_path: Path,
) -> None:
    """The shared loader should preserve the actionable missing-file guidance."""
    document, error = load_harness_checks_document(
        tmp_path,
        error_prefix="checks config error",
    )

    assert document is None
    assert error is not None
    assert error.startswith("checks config error:")
    assert "missing harness/checks.yaml" in error
    assert "Remediation: run `engineeringagent init`." in error


def test_load_harness_checks_document_includes_missing_context_when_provided(
    tmp_path: Path,
) -> None:
    """The loader should append caller-provided missing-context wording."""
    document, error = load_harness_checks_document(
        tmp_path,
        error_prefix="run config error",
        missing_context=" (required for --all)",
    )

    assert document is None
    assert error is not None
    assert error.startswith("run config error:")
    assert "missing harness/checks.yaml" in error
    assert "(required for --all)" in error
    assert "Remediation: run `engineeringagent init`." in error


def test_load_harness_checks_document_uses_engineeringagent_toml_path(
    tmp_path: Path,
) -> None:
    """The loader should honor the dedicated config override path."""
    (tmp_path / "engineeringagent.toml").write_text(
        "[harness.checks]\npath = \"repo/checks/custom.yaml\"\n",
        encoding="utf-8",
    )
    checks_path = tmp_path / "repo" / "checks" / "custom.yaml"
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "groups:",
                "  - group_id: smoke",
                "    description: Smoke checks.",
                "    checks: [smoke]",
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "echo ok"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    document, error = load_harness_checks_document(
        tmp_path,
        error_prefix="checks config error",
    )

    assert error is None
    assert document is not None
    assert "smoke" in document.checks


def test_load_harness_checks_document_uses_pyproject_path_when_toml_missing(
    tmp_path: Path,
) -> None:
    """The loader should fall back to the pyproject-backed checks path."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.engineeringagent.harness.checks]\npath = \"repo/checks/custom.yaml\"\n",
        encoding="utf-8",
    )

    document, error = load_harness_checks_document(
        tmp_path,
        error_prefix="checks config error",
    )

    assert document is None
    assert error is not None
    assert "missing repo/checks/custom.yaml" in error


def test_load_harness_checks_document_rejects_parent_traversal(
    tmp_path: Path,
) -> None:
    """The loader should reject config paths that escape the repository root."""
    (tmp_path / "engineeringagent.toml").write_text(
        "[harness.checks]\npath = \"../checks.yaml\"\n",
        encoding="utf-8",
    )

    document, error = load_harness_checks_document(
        tmp_path,
        error_prefix="checks config error",
    )

    assert document is None
    assert error is not None
    assert (
        "checks config error: invalid path in "
        f"{tmp_path / 'engineeringagent.toml'} ([harness.checks]): cannot contain '..'"
    ) in error


def test_load_harness_checks_document_failed_load_is_deterministic(
    tmp_path: Path,
) -> None:
    """The loader should normalize YAML load failures into one stable error line."""
    write_checks_yaml(tmp_path, "- list\n")

    document, error = load_harness_checks_document(
        tmp_path,
        error_prefix="checks config error",
    )

    assert document is None
    assert error is not None
    assert error.startswith("checks config error: failed to load harness/checks.yaml:")


def test_load_harness_checks_document_contract_issues_are_deterministic(
    tmp_path: Path,
) -> None:
    """The loader should render contract issues with deterministic path output."""
    write_checks_yaml(tmp_path, "checks: {}\n")

    document, error = load_harness_checks_document(
        tmp_path,
        error_prefix="checks config error",
    )

    assert document is None
    assert error is not None
    assert "checks config error: invalid harness/checks.yaml" in error
    assert "harness/checks.yaml:contract_version" in error


def test_load_harness_checks_document_reports_group_membership_issues(
    tmp_path: Path,
) -> None:
    """The loader should surface membership violations from the checks contract."""
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "groups:",
                "  - group_id: reviewer",
                "    description: Reviewer checks.",
                "    checks: [doc_review]",
                "checks:",
                "  doc_review:",
                "    type: reviewer",
                "    prompt_file: harness/reviewers/prompts/doc_review.md",
                "    when:",
                "      phase: feature_done",
                "  smoke:",
                "    type: command",
                '    command: "echo ok"',
                "",
            ]
        ),
    )

    document, error = load_harness_checks_document(
        tmp_path,
        error_prefix="checks config error",
    )

    assert document is None
    assert error is not None
    assert "harness/checks.yaml:checks.smoke" in error
    assert "at least one group" in error


def test_load_harness_checks_document_returns_document_on_valid_config(
    tmp_path: Path,
) -> None:
    """The loader should return the validated checks document for valid input."""
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "groups:",
                "  - group_id: smoke",
                "    description: Smoke checks.",
                "    checks: [smoke]",
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "echo ok"',
                "",
            ]
        ),
    )

    document, error = load_harness_checks_document(
        tmp_path,
        error_prefix="checks config error",
    )

    assert error is None
    assert document is not None
    assert "smoke" in document.checks


def test_load_harness_checks_document_model_validation_error_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The loader should convert model validation failures into stable messages."""
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "groups:",
                "  - group_id: smoke",
                "    description: Smoke checks.",
                "    checks: [smoke]",
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "echo ok"',
                "",
            ]
        ),
    )

    class ValidationProbe(BaseModel):
        """Trigger a stable Pydantic validation failure for the loader test."""

        value: int

    validation_error: ValidationError | None = None
    try:
        ValidationProbe.model_validate({"value": "invalid"})
    except ValidationError as exc:
        validation_error = exc
    assert validation_error is not None

    def raise_validation_error(_payload: object) -> object:
        raise validation_error

    monkeypatch.setattr(
        "engineeringagent.adapters.documents.checks_catalog_loader.checks_contract_issues",
        lambda *_args, **_kwargs: [],
        raising=True,
    )
    monkeypatch.setattr(
        "engineeringagent.adapters.documents.checks_catalog_loader.HarnessChecksDocument.model_validate",
        raise_validation_error,
        raising=True,
    )

    document, error = load_harness_checks_document(
        tmp_path,
        error_prefix="checks config error",
    )

    assert document is None
    assert error is not None
    assert "checks config error: failed to validate harness/checks.yaml:" in error
