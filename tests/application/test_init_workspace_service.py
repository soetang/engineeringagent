from __future__ import annotations

from pathlib import Path

from engineeringagent.application import (
    InitWorkspaceRequest,
    InitWorkspaceResult,
    InitWorkspaceService,
)
from engineeringagent.ports import InitWorkspaceDependencies


def _build_request(tmp_path: Path, **overrides: object) -> InitWorkspaceRequest:
    fields: dict[str, object] = {
        "project_root": tmp_path,
        "force": False,
        "scaffold_profile": "python_uv",
        "scaffold_docs_dir": "docs",
        "pack": "slim",
        "backend": "codex",
        "docs_mode": None,
        "agents_mode": "overwrite",
        "agents_launcher": "uvx",
        "model": "openai/gpt-5.3-codex",
        "no_precommit_install": False,
    }
    fields.update(overrides)
    return InitWorkspaceRequest.model_validate(fields)


def _build_dependencies(
    tmp_path: Path,
) -> InitWorkspaceDependencies:
    return InitWorkspaceDependencies(
        resolve_pack=lambda _pack: ("slim", None),
        resolve_backend=lambda **_kwargs: ("codex", None),
        resolve_docs_dir=lambda **_kwargs: ("docs", None),
        resolve_agents_mode=lambda **_kwargs: ("overwrite", None),
        resolve_agents_launcher=lambda **_kwargs: ("uvx", None),
        resolve_codex_profile_overwrite=lambda **_kwargs: (False, None),
        next_agents_backup_path=lambda _project_root: tmp_path / "AGENTS.user.md",
        apply_baseline_scaffold=lambda **_kwargs: (2, 3),
        write_init_docs_root_config=lambda **_kwargs: (4, 5),
        write_init_backend_config=lambda **_kwargs: (6, 7),
        build_agents_merge_followup_spec=lambda backup_name: f"merge {backup_name}",
        install_precommit_hooks_best_effort=lambda **_kwargs: ("precommit-installed",),
    )


def test_init_workspace_service_runs_scaffold_flow_and_emits_summary(
    tmp_path: Path,
) -> None:
    """The application service should orchestrate scaffold work without CLI output logic."""
    result = InitWorkspaceService().run(
        _build_request(tmp_path),
        _build_dependencies(tmp_path),
    )

    assert result == InitWorkspaceResult(
        exit_code=0,
        status="completed",
        messages=(
            "precommit-installed",
            "init scaffold complete: docs_dir=docs created=12 skipped=15"
            " profile=python_uv pack=slim agents_launcher=uvx agents_mode=overwrite",
        ),
        docs_dir="docs",
        created=12,
        skipped=15,
        profile="python_uv",
        pack="slim",
        agents_launcher="uvx",
        agents_mode="overwrite",
        notes=(),
    )


def test_init_workspace_service_stops_cleanly_when_agents_preserve_aborts(
    tmp_path: Path,
) -> None:
    """Abort mode should return success after emitting the stable user message."""
    dependencies = InitWorkspaceDependencies(
        **{
            **_build_dependencies(tmp_path).model_dump(),
            "resolve_agents_mode": lambda **_kwargs: ("abort", None),
        }
    )

    result = InitWorkspaceService().run(_build_request(tmp_path), dependencies)

    assert result == InitWorkspaceResult(
        exit_code=0,
        status="aborted",
        messages=(
            "init aborted: kept existing AGENTS.md; no scaffold files changed",
        ),
        docs_dir="docs",
        profile="python_uv",
        pack="slim",
        agents_mode="abort",
        notes=(),
    )
