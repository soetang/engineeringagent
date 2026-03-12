from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.config import FilesystemConfigurationProvider
from engineeringagent.domain.shared import RepositoryConfig, RepositoryPaths
from engineeringagent.ports import ConfigurationProvider


def test_filesystem_configuration_provider_loads_effective_config(
    tmp_path: Path,
) -> None:
    """Provider delegates effective config loading for one project root."""
    (tmp_path / "engineeringagent.toml").write_text(
        '[paths]\nharness_root = "custom-harness"\n',
        encoding="utf-8",
    )

    provider = FilesystemConfigurationProvider(tmp_path)

    assert isinstance(provider, ConfigurationProvider)
    assert provider.load() == RepositoryConfig(
        paths=RepositoryPaths(harness_root="custom-harness")
    )
