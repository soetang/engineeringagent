from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from engineeringagent.checks import run_checks
from engineeringagent.checks.config_loader import load_harness_checks_document

from tests.checks.run_checks_contract_support import write_checks_yaml


def test_shared_loader_missing_file_returns_actionable_error(tmp_path: Path) -> None:
    doc, error = load_harness_checks_document(tmp_path, error_prefix="checks config error")

    assert doc is None
    assert error is not None
    assert error.startswith("checks config error:")
    assert "missing harness/checks.yaml" in error
    assert "Remediation: run `engineeringagent init`." in error


def test_shared_loader_includes_missing_context_when_provided(tmp_path: Path) -> None:
    doc, error = load_harness_checks_document(
        tmp_path,
        error_prefix="run config error",
        missing_context=" (required for --all)",
    )

    assert doc is None
    assert error is not None
    assert error.startswith("run config error:")
    assert "missing harness/checks.yaml" in error
    assert "(required for --all)" in error
    assert "Remediation: run `engineeringagent init`." in error


def test_shared_loader_uses_engineeringagent_toml_checks_path(tmp_path: Path) -> None:
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
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "echo ok"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    doc, error = load_harness_checks_document(tmp_path, error_prefix="checks config error")

    assert error is None
    assert doc is not None
    assert "smoke" in doc.checks


def test_shared_loader_uses_pyproject_checks_path_when_toml_missing(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.engineeringagent.harness.checks]\npath = \"repo/checks/custom.yaml\"\n",
        encoding="utf-8",
    )

    doc, error = load_harness_checks_document(tmp_path, error_prefix="checks config error")

    assert doc is None
    assert error is not None
    assert "missing repo/checks/custom.yaml" in error


def test_shared_loader_rejects_checks_path_with_parent_traversal(
    tmp_path: Path,
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        "[harness.checks]\npath = \"../checks.yaml\"\n",
        encoding="utf-8",
    )

    doc, error = load_harness_checks_document(tmp_path, error_prefix="checks config error")

    assert doc is None
    assert error is not None
    assert (
        "checks config error: invalid path in "
        f"{tmp_path / 'engineeringagent.toml'} ([harness.checks]): cannot contain '..'"
    ) in error


def test_shared_loader_failed_load_is_deterministic(tmp_path: Path) -> None:
    write_checks_yaml(tmp_path, "- list\n")

    doc, error = load_harness_checks_document(tmp_path, error_prefix="checks config error")

    assert doc is None
    assert error is not None
    assert error.startswith("checks config error: failed to load harness/checks.yaml:")


def test_shared_loader_contract_issues_are_rendered_deterministically(
    tmp_path: Path,
) -> None:
    write_checks_yaml(tmp_path, "checks: {}\n")

    doc, error = load_harness_checks_document(tmp_path, error_prefix="checks config error")

    assert doc is None
    assert error is not None
    assert "checks config error: invalid harness/checks.yaml" in error
    assert "harness/checks.yaml:contract_version" in error


def test_shared_loader_returns_document_on_valid_config(tmp_path: Path) -> None:
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

    doc, error = load_harness_checks_document(tmp_path, error_prefix="checks config error")

    assert error is None
    assert doc is not None
    assert "smoke" in doc.checks


def test_shared_loader_model_validation_error_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    class ValidationProbe(BaseModel):
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
        "engineeringagent.checks.config_loader.checks_contract_issues",
        lambda *_args, **_kwargs: [],
        raising=True,
    )
    monkeypatch.setattr(
        "engineeringagent.checks.config_loader.HarnessChecksDocument.model_validate",
        raise_validation_error,
        raising=True,
    )

    doc, error = load_harness_checks_document(tmp_path, error_prefix="checks config error")

    assert doc is None
    assert error is not None
    assert "checks config error: failed to validate harness/checks.yaml:" in error


def test_run_checks_check_id_without_harness_doc_fails_deterministically(
    tmp_path: Path,
) -> None:
    result = run_checks(tmp_path, phase="iteration_end", checks=["validate"], check_id="smoke")
    assert not result.ok
    assert result.failed_check_id == "smoke"
