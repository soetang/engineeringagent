from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.checks import FilesystemChecksCatalogRepository

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

    assert result.error is None
    assert result.document is not None
    assert "smoke" in result.document.checks


def test_filesystem_checks_catalog_repository_returns_deterministic_error(
    tmp_path: Path,
) -> None:
    """The adapter should preserve the shared deterministic missing-file error."""
    result = FilesystemChecksCatalogRepository().load(tmp_path)

    assert result.document is None
    assert result.error is not None
    assert "checks config error: missing harness/checks.yaml" in result.error
