from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.adapters.checks import (
    ChecksCatalogLoadOptions,
    FilesystemChecksCatalogRepository,
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
