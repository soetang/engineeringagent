from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.adapters.config import load_repository_config


def test_loader_uses_defaults_when_no_config_files_exist(tmp_path: Path) -> None:
    """Loader falls back to the built-in repository defaults."""
    config = load_repository_config(tmp_path)

    assert config.paths.docs_root == "docs"
    assert config.paths.specifications_root == "docs/spec"
    assert config.paths.harness_root == "harness"
    assert config.paths.harness_checks_path == "harness/checks.yaml"
    assert config.agents.backend is None
    assert config.agents.implementation.prompt_definition == "implementation_default"


def test_loader_ignores_pyproject_when_dedicated_file_exists(tmp_path: Path) -> None:
    """Dedicated config files take precedence over pyproject fallback values."""
    (tmp_path / "engineeringagent.toml").write_text(
        '[paths]\nharness_root = "repo-harness"\n',
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent.paths]\nharness_root = "pyproject-harness"\n',
        encoding="utf-8",
    )

    config = load_repository_config(tmp_path)

    assert config.paths.harness_root == "repo-harness"


def test_loader_merges_local_override_over_repository_defaults(tmp_path: Path) -> None:
    """Local overrides layer on top of repository defaults for effective config."""
    (tmp_path / "engineeringagent.toml").write_text(
        '[paths]\nharness_root = "repo-harness"\n\n'
        '[agents]\nbackend = "codex"\n\n'
        '[agents.codex]\nprofile = "repo-profile"\n',
        encoding="utf-8",
    )
    (tmp_path / "engineeringagent.local.toml").write_text(
        '[paths]\nharness_root = "local-harness"\n\n'
        '[agents.codex]\nmodel = "gpt-5.4-mini"\n',
        encoding="utf-8",
    )

    config = load_repository_config(tmp_path)

    assert config.paths.harness_root == "local-harness"
    assert config.agents.backend == "codex"
    assert config.agents.codex.profile == "repo-profile"
    assert config.agents.codex.model == "gpt-5.4-mini"


def test_loader_derives_specifications_root_from_configured_docs_root(
    tmp_path: Path,
) -> None:
    """Specs root tracks a configured docs root when no explicit override exists."""
    (tmp_path / "engineeringagent.toml").write_text(
        'docs-root = "product-docs"\n',
        encoding="utf-8",
    )

    config = load_repository_config(tmp_path)

    assert config.paths.docs_root == "product-docs"
    assert config.paths.specifications_root == "product-docs/spec"


def test_loader_rejects_invalid_backend_values(tmp_path: Path) -> None:
    """Invalid backend values fail effective config loading."""
    (tmp_path / "engineeringagent.toml").write_text(
        "[agents]\nbackend = 1\n",
        encoding="utf-8",
    )

    with pytest.raises((TypeError, ValueError), match="backend"):
        load_repository_config(tmp_path)


def test_loader_reads_implementation_prompt_definition_from_agents_table(
    tmp_path: Path,
) -> None:
    """Effective config exposes the configured implementation prompt id."""
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents.implementation]\nprompt_definition = "repo_prompt"\n',
        encoding="utf-8",
    )

    config = load_repository_config(tmp_path)

    assert config.agents.implementation.prompt_definition == "repo_prompt"


def test_loader_rejects_invalid_implementation_prompt_definition(
    tmp_path: Path,
) -> None:
    """Implementation prompt definitions must be non-empty strings."""
    (tmp_path / "engineeringagent.toml").write_text(
        "[agents.implementation]\nprompt_definition = 1\n",
        encoding="utf-8",
    )

    with pytest.raises((TypeError, ValueError), match="prompt_definition"):
        load_repository_config(tmp_path)
