from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.adapters.config import load_repository_config


def test_loader_uses_defaults_when_no_config_files_exist(tmp_path: Path) -> None:
    """Loader falls back to the built-in repository defaults."""
    config = load_repository_config(tmp_path)

    assert config.version == 1
    assert config.paths.docs_root == "docs"
    assert config.paths.specifications_root == "docs/specifications"
    assert config.paths.harness_root == "harness"
    assert config.paths.worktree_root == ".engineeringagent/worktrees"
    assert config.paths.harness_checks_path == "harness/checks.yaml"
    assert config.agents.backend is None
    assert config.agents.implementation.prompt_definition == "implementation_default"
    assert config.vcs.integration_branch == "main"
    assert config.execution.mode == "local_worktree"


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
        '[agents.codex]\nprofile = "repo-profile"\n\n'
        '[vcs]\nintegration_branch = "develop"\n',
        encoding="utf-8",
    )
    (tmp_path / "engineeringagent.local.toml").write_text(
        '[paths]\nharness_root = "local-harness"\nworktree_root = ".engineeringagent/custom-worktrees"\n\n'
        '[agents.codex]\nmodel = "gpt-5.4-mini"\n\n'
        '[execution]\nmode = "remote_target"\n',
        encoding="utf-8",
    )

    config = load_repository_config(tmp_path)

    assert config.paths.harness_root == "local-harness"
    assert config.agents.backend == "codex"
    assert config.agents.codex.profile == "repo-profile"
    assert config.agents.codex.model == "gpt-5.4-mini"
    assert config.paths.worktree_root == ".engineeringagent/custom-worktrees"
    assert config.vcs.integration_branch == "develop"
    assert config.execution.mode == "remote_target"


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
    assert config.paths.specifications_root == "product-docs/specifications"


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


def test_loader_reads_canonical_architecture_sections(tmp_path: Path) -> None:
    """Effective config includes the new architecture-owned runtime sections."""
    (tmp_path / "engineeringagent.toml").write_text(
        'version = 1\n\n'
        '[agents.implementation]\nbackend = "opencode"\nmodel = "gpt-5.4"\nprompt_definition = "repo_prompt"\n\n'
        '[agents.reviewer]\nbackend = "opencode"\nmodel = "gpt-5.4-mini"\n\n'
        '[paths]\nworktree_root = ".engineeringagent/feature-worktrees"\n\n'
        '[vcs]\nintegration_branch = "trunk"\n\n'
        '[execution]\nmode = "local_worktree"\n',
        encoding="utf-8",
    )

    config = load_repository_config(tmp_path)

    assert config.version == 1
    assert config.agents.implementation.backend == "opencode"
    assert config.agents.implementation.model == "gpt-5.4"
    assert config.agents.implementation.prompt_definition == "repo_prompt"
    assert config.agents.reviewer.backend == "opencode"
    assert config.agents.reviewer.model == "gpt-5.4-mini"
    assert config.paths.worktree_root == ".engineeringagent/feature-worktrees"
    assert config.vcs.integration_branch == "trunk"
    assert config.execution.mode == "local_worktree"


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


@pytest.mark.parametrize(
    ("payload", "pattern"),
    [
        ("version = 2\n", "version"),
        ('[paths]\nworktree_root = ""\n', "worktree_root"),
        ("[vcs]\nintegration_branch = 1\n", "integration_branch"),
        ("[execution]\nmode = 1\n", "execution.mode"),
        ("[agents.reviewer]\nbackend = 1\n", "agents.reviewer.backend"),
    ],
)
def test_loader_rejects_invalid_architecture_section_values(
    tmp_path: Path,
    payload: str,
    pattern: str,
) -> None:
    """Architecture-owned runtime sections remain strictly typed."""
    (tmp_path / "engineeringagent.toml").write_text(payload, encoding="utf-8")

    with pytest.raises((TypeError, ValueError), match=pattern):
        load_repository_config(tmp_path)
