from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from engineeringagent.presentation import cli as cli_module
from tests.presentation.cli.init_command_support import (
    ENGINEERINGAGENT_TOKEN,
    UVX_TOKEN,
    invoke_cli,
)


def test_init_agents_conflict_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init can explicitly overwrite an existing AGENTS.md."""
    (tmp_path / "AGENTS.md").write_text("user guidance\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt: "overwrite")

    result = invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "agents_mode=overwrite" in result.stdout
    scaffold_agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "user guidance" not in scaffold_agents
    assert UVX_TOKEN in scaffold_agents


@pytest.mark.parametrize(
    ("agents_mode", "expected_backup"),
    [("overwrite", False), ("preserve", True)],
)
def test_init_agents_conflict_honors_explicit_launcher_option(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    agents_mode: str,
    expected_backup: bool,
) -> None:
    """Verify conflict flows use explicit --agents-launcher wording deterministically."""
    (tmp_path / "AGENTS.md").write_text("legacy guidance\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt: agents_mode)

    result = invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "slim",
            "--agents-launcher",
            "engineeringagent",
            "--no-precommit-install",
        ]
    )

    assert result.exit_code == 0
    assert f"agents_mode={agents_mode}" in result.stdout
    rendered_agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert rendered_agents != "legacy guidance\n"
    assert ENGINEERINGAGENT_TOKEN in rendered_agents
    assert UVX_TOKEN not in rendered_agents
    assert (tmp_path / "AGENTS.user.md").exists() is expected_backup


def test_init_agents_conflict_preserve_and_create_merge_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify preserve mode renames AGENTS and creates a merge follow-up spec."""
    (tmp_path / "AGENTS.md").write_text("legacy guidance\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt: "preserve")

    result = invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "agents_mode=preserve" in result.stdout
    assert "agents_backup=AGENTS.user.md" in result.stdout
    assert (tmp_path / "AGENTS.user.md").read_text(encoding="utf-8") == (
        "legacy guidance\n"
    )

    scaffold_agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "legacy guidance" not in scaffold_agents
    assert UVX_TOKEN in scaffold_agents

    merge_spec_path = (
        tmp_path
        / "docs"
        / "spec"
        / "features"
        / "FEAT-900-merge-preserved-agents-guidance.yaml"
    )
    assert merge_spec_path.exists()
    assert "AGENTS.user.md" in merge_spec_path.read_text(encoding="utf-8")


def test_init_agents_conflict_abort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify abort mode keeps AGENTS and exits without scaffold writes."""
    (tmp_path / "AGENTS.md").write_text("do not touch\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt: "abort")

    result = invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "init aborted" in result.stdout
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == "do not touch\n"
    assert not (tmp_path / "docs" / "spec").exists()


def test_init_attempts_precommit_install_when_git_repo_and_precommit_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init best-effort installs pre-commit hooks when possible."""
    (tmp_path / ".git").mkdir(parents=True)
    calls: list[tuple[Path, str | None]] = []
    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: "/bin/pre-commit")

    def _fake_precommit_install(
        project_root: Path,
        *,
        hook_type: str | None = None,
    ) -> object:
        calls.append((project_root, hook_type))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        cli_module.git_client, "precommit_install", _fake_precommit_install
    )

    result = invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert calls == [(tmp_path.resolve(), None)]


def test_init_attempts_precommit_install_when_git_marker_is_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init treats worktree-style .git files as git repos."""
    (tmp_path / ".git").write_text("gitdir: /tmp/gitdir\n", encoding="utf-8")
    calls: list[tuple[Path, str | None]] = []
    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: "/bin/pre-commit")

    def _fake_precommit_install(
        project_root: Path,
        *,
        hook_type: str | None = None,
    ) -> object:
        calls.append((project_root, hook_type))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        cli_module.git_client, "precommit_install", _fake_precommit_install
    )

    result = invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert calls == [(tmp_path.resolve(), None)]


def test_init_python_uv_attempts_commit_msg_hook_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify python_uv init attempts installing the commit-msg hook type."""
    (tmp_path / ".git").mkdir(parents=True)
    calls: list[tuple[Path, str | None]] = []
    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: "/bin/pre-commit")

    def _fake_precommit_install(
        project_root: Path,
        *,
        hook_type: str | None = None,
    ) -> object:
        calls.append((project_root, hook_type))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        cli_module.git_client, "precommit_install", _fake_precommit_install
    )

    result = invoke_cli(
        ["--project-root", str(tmp_path), "init", "--scaffold-profile", "python_uv"]
    )

    assert result.exit_code == 0
    assert calls == [(tmp_path.resolve(), None), (tmp_path.resolve(), "commit-msg")]


def test_init_non_git_repo_prints_precommit_remediation_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init hints how to wire hooks when not in a git repo."""
    monkeypatch.setattr(
        cli_module.git_client,
        "precommit_install",
        lambda *_args, **_kwargs: pytest.fail("unexpected pre-commit install attempt"),
    )

    result = invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "skipped pre-commit hook install" in result.stdout
    assert "git init" in result.stdout
    assert "pre-commit install" in result.stdout


def test_init_missing_precommit_prints_remediation_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init succeeds and hints when pre-commit is missing."""
    (tmp_path / ".git").mkdir(parents=True)
    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        cli_module.git_client,
        "precommit_install",
        lambda *_args, **_kwargs: pytest.fail("unexpected pre-commit install attempt"),
    )

    result = invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "skipped pre-commit hook install" in result.stdout
    assert "pre-commit not found" in result.stdout
    assert "pre-commit install" in result.stdout


def test_init_precommit_install_failure_is_non_fatal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init does not fail solely due to hook installation failure."""
    (tmp_path / ".git").mkdir(parents=True)
    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: "/bin/pre-commit")

    def _fake_precommit_install(
        _project_root: Path,
        *,
        hook_type: str | None = None,
    ) -> object:
        assert hook_type is None
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(
        cli_module.git_client, "precommit_install", _fake_precommit_install
    )

    result = invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "init warning" in result.stdout
    assert "exit_code=1" in result.stdout
    assert "pre-commit install" in result.stdout


def test_init_precommit_install_exception_is_non_fatal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init survives unexpected subprocess errors during hook install."""
    (tmp_path / ".git").mkdir(parents=True)
    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: "/bin/pre-commit")

    def _boom(_project_root: Path, *, hook_type: str | None = None) -> object:  # noqa: ARG001
        raise FileNotFoundError("pre-commit")

    monkeypatch.setattr(cli_module.git_client, "precommit_install", _boom)

    result = invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "init warning" in result.stdout
    assert "error=FileNotFoundError" in result.stdout
    assert "pre-commit install" in result.stdout


def test_init_no_precommit_install_flag_skips_install_attempts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --no-precommit-install disables all hook installation attempts."""
    (tmp_path / ".git").mkdir(parents=True)
    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: "/bin/pre-commit")
    monkeypatch.setattr(
        cli_module.git_client,
        "precommit_install",
        lambda *_args, **_kwargs: pytest.fail("unexpected pre-commit install attempt"),
    )

    result = invoke_cli(
        ["--project-root", str(tmp_path), "init", "--no-precommit-install"]
    )

    assert result.exit_code == 0
