from __future__ import annotations

from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from ..application import (
    InitWorkspaceDependencies,
    InitWorkspaceRequest,
    InitWorkspaceService,
)
from ..agents import default_backend_id, list_backends
from ..config import (
    resolve_agents_backend_id,
    resolve_agents_codex_profile_in_engineeringagent_toml,
    write_init_backend_config,
    write_init_docs_root_config,
)
from ..init_cli_support import (
    InitAgentsLauncherResolverDeps,
    InitBackendResolverDeps,
    InitCodexProfileResolverDeps,
    InitPromptContext,
    install_precommit_hooks_best_effort as _install_precommit_hooks_best_effort_impl,
    next_agents_backup_path,
    resolve_init_agents_launcher,
    resolve_init_agents_mode,
    resolve_init_backend,
    resolve_init_codex_profile_overwrite,
    resolve_init_docs_dir,
    resolve_init_pack,
)
from ..init_scaffold import (
    AGENTS_LAUNCHER_CHOICES,
    DEFAULT_AGENT_MODEL,
    DEFAULT_AGENTS_LAUNCHER,
    apply_baseline_scaffold,
    build_agents_merge_followup_spec,
)
from ..presentation.terminal import stdout_is_tty

_HandlerArgs = SimpleNamespace
_AdapterValue = TypeVar("_AdapterValue")
_DEFAULT_INIT_WORKSPACE_RUNNER = InitWorkspaceService().run


class InitCliTerminalAdapters(BaseModel):
    """Terminal-facing init overrides owned by the CLI package."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", arbitrary_types_allowed=True
    )

    emit: Callable[[str], None] | None = None
    stdout_is_tty_fn: Callable[[object], bool] | None = None


class InitCliCommandAdapters(BaseModel):
    """Top-level init command overrides owned by the CLI package."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", arbitrary_types_allowed=True
    )

    run_init_command_fn: Callable[
        [InitWorkspaceRequest, InitWorkspaceDependencies],
        int,
    ] | None = None


class InitCliBackendAdapters(BaseModel):
    """Backend selection overrides owned by the CLI package."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", arbitrary_types_allowed=True
    )

    list_backends_fn: Callable[[], tuple[str, ...]] | None = None
    resolve_agents_backend_id_fn: Callable[[Path], str | None] | None = None
    default_backend_id_fn: Callable[[], str] | None = None


class InitCliSelectionAdapters(BaseModel):
    """Init prompt and selection overrides owned by the CLI package."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", arbitrary_types_allowed=True
    )

    resolve_docs_dir_fn: Callable[
        [Path, str | None, str], tuple[str | None, str | None]
    ] | None = None
    resolve_agents_mode_fn: Callable[
        [Path, str | None], tuple[str | None, str | None]
    ] | None = None
    resolve_agents_launcher_fn: Callable[..., tuple[str | None, str | None]] | None = None
    resolve_codex_profile_overwrite_fn: Callable[
        ..., tuple[bool, str | None]
    ] | None = None


class InitCliScaffoldAdapters(BaseModel):
    """Scaffold and config writer overrides owned by the CLI package."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", arbitrary_types_allowed=True
    )

    next_agents_backup_path_fn: Callable[[Path], Path] | None = None
    build_agents_merge_followup_spec_fn: Callable[[str], str] | None = None
    apply_baseline_scaffold_fn: Callable[..., tuple[int, int]] | None = None
    write_init_docs_root_config_fn: Callable[..., tuple[int, int]] | None = None
    write_init_backend_config_fn: Callable[..., tuple[int, int]] | None = None


class InitCliAdapters(BaseModel):
    """Explicit CLI-owned adapter groups for init command composition."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", arbitrary_types_allowed=True
    )

    terminal: InitCliTerminalAdapters = Field(
        default_factory=InitCliTerminalAdapters
    )
    command: InitCliCommandAdapters = Field(default_factory=InitCliCommandAdapters)
    backend: InitCliBackendAdapters = Field(default_factory=InitCliBackendAdapters)
    selection: InitCliSelectionAdapters = Field(
        default_factory=InitCliSelectionAdapters
    )
    scaffold: InitCliScaffoldAdapters = Field(
        default_factory=InitCliScaffoldAdapters
    )


def _coalesce_adapter(
    override: _AdapterValue | None,
    default: _AdapterValue,
) -> _AdapterValue:
    """Prefer a caller override while keeping default behavior deterministic."""
    return default if override is None else override


__all__ = [
    "AGENTS_LAUNCHER_CHOICES",
    "DEFAULT_AGENT_MODEL",
    "InitCliAdapters",
    "InitCliBackendAdapters",
    "InitCliCommandAdapters",
    "InitCliScaffoldAdapters",
    "InitCliSelectionAdapters",
    "InitCliTerminalAdapters",
    "cmd_init",
]


def build_init_request(args: _HandlerArgs) -> InitWorkspaceRequest:
    """Build an immutable init request from CLI arguments."""

    return InitWorkspaceRequest(
        project_root=Path(args.project_root).resolve(),
        force=bool(args.force),
        scaffold_profile=args.scaffold_profile,
        scaffold_docs_dir=args.scaffold_docs_dir,
        pack=getattr(args, "pack", None),
        backend=getattr(args, "backend", None),
        docs_mode=args.docs_mode,
        agents_mode=getattr(args, "agents_mode", None),
        agents_launcher=getattr(args, "agents_launcher", None),
        model=getattr(args, "model", DEFAULT_AGENT_MODEL),
        no_precommit_install=bool(getattr(args, "no_precommit_install", False)),
    )


def build_init_dependencies(
    adapters: InitCliAdapters | None = None,
) -> InitWorkspaceDependencies:
    """Assemble dependency implementations for init execution."""
    adapter_bundle = adapters or InitCliAdapters()
    emit = _coalesce_adapter(adapter_bundle.terminal.emit, print)
    stdout_is_tty_fn = _coalesce_adapter(
        adapter_bundle.terminal.stdout_is_tty_fn, stdout_is_tty
    )
    list_backends_fn = _coalesce_adapter(
        adapter_bundle.backend.list_backends_fn,
        list_backends,
    )
    resolve_agents_backend_id_fn = _coalesce_adapter(
        adapter_bundle.backend.resolve_agents_backend_id_fn,
        resolve_agents_backend_id,
    )
    default_backend_id_fn = _coalesce_adapter(
        adapter_bundle.backend.default_backend_id_fn,
        default_backend_id,
    )
    resolve_docs_dir_fn = _coalesce_adapter(
        adapter_bundle.selection.resolve_docs_dir_fn,
        resolve_init_docs_dir,
    )
    resolve_agents_mode_fn = _coalesce_adapter(
        adapter_bundle.selection.resolve_agents_mode_fn,
        resolve_init_agents_mode,
    )
    resolve_agents_launcher_fn = _coalesce_adapter(
        adapter_bundle.selection.resolve_agents_launcher_fn,
        resolve_init_agents_launcher,
    )
    resolve_codex_profile_overwrite_fn = _coalesce_adapter(
        adapter_bundle.selection.resolve_codex_profile_overwrite_fn,
        resolve_init_codex_profile_overwrite,
    )
    next_agents_backup_path_fn = _coalesce_adapter(
        adapter_bundle.scaffold.next_agents_backup_path_fn,
        next_agents_backup_path,
    )
    build_agents_merge_followup_spec_fn = _coalesce_adapter(
        adapter_bundle.scaffold.build_agents_merge_followup_spec_fn,
        build_agents_merge_followup_spec,
    )
    apply_baseline_scaffold_fn = _coalesce_adapter(
        adapter_bundle.scaffold.apply_baseline_scaffold_fn,
        apply_baseline_scaffold,
    )
    write_init_docs_root_config_fn = _coalesce_adapter(
        adapter_bundle.scaffold.write_init_docs_root_config_fn,
        write_init_docs_root_config,
    )
    write_init_backend_config_fn = _coalesce_adapter(
        adapter_bundle.scaffold.write_init_backend_config_fn,
        write_init_backend_config,
    )
    prompt_context = InitPromptContext(stdout_is_tty_fn=stdout_is_tty_fn)

    return InitWorkspaceDependencies(
        emit=emit,
        resolve_pack=partial(
            resolve_init_pack,
            stdout_is_tty_fn=stdout_is_tty_fn,
        ),
        resolve_backend=partial(
            resolve_init_backend,
            prompt_context=prompt_context,
            deps=InitBackendResolverDeps(
                list_backends_fn=list_backends_fn,
                resolve_agents_backend_id_fn=resolve_agents_backend_id_fn,
                default_backend_id_fn=default_backend_id_fn,
            ),
        ),
        resolve_docs_dir=lambda *, project_root, docs_mode, scaffold_docs_dir: (
            resolve_docs_dir_fn(project_root, docs_mode, scaffold_docs_dir)
        ),
        resolve_agents_mode=lambda *, project_root, agents_mode: (
            resolve_agents_mode_fn(project_root, agents_mode)
        ),
        resolve_agents_launcher=partial(
            resolve_agents_launcher_fn,
            prompt_context=prompt_context,
            deps=InitAgentsLauncherResolverDeps(
                launcher_choices=AGENTS_LAUNCHER_CHOICES,
                default_launcher=DEFAULT_AGENTS_LAUNCHER,
            ),
        ),
        resolve_codex_profile_overwrite=partial(
            resolve_codex_profile_overwrite_fn,
            prompt_context=prompt_context,
            deps=InitCodexProfileResolverDeps(
                resolve_codex_profile_fn=resolve_agents_codex_profile_in_engineeringagent_toml
            ),
        ),
        next_agents_backup_path=next_agents_backup_path_fn,
        apply_baseline_scaffold=apply_baseline_scaffold_fn,
        write_init_docs_root_config=write_init_docs_root_config_fn,
        write_init_backend_config=write_init_backend_config_fn,
        build_agents_merge_followup_spec=build_agents_merge_followup_spec_fn,
        install_precommit_hooks_best_effort=partial(
            _install_precommit_hooks_best_effort_impl,
            emit=emit,
        ),
    )


def cmd_init(
    args: _HandlerArgs,
    *,
    adapters: InitCliAdapters | None = None,
) -> int:
    """Scaffold baseline harness files for a repository."""
    adapter_bundle = adapters or InitCliAdapters()
    request = build_init_request(args)
    deps = build_init_dependencies(adapter_bundle)
    run_init_command_fn = _coalesce_adapter(
        adapter_bundle.command.run_init_command_fn,
        _DEFAULT_INIT_WORKSPACE_RUNNER,
    )
    return run_init_command_fn(request, deps)
