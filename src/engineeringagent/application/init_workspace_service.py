from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

from pydantic import BaseModel, ConfigDict, SkipValidation

from engineeringagent.init_scaffold import BaselineScaffoldOptions, DEFAULT_AGENT_MODEL

ResolveInitPack = Callable[[str | None], tuple[str | None, str | None]]


class ResolveInitBackend(Protocol):
    """Resolve init backend selection and return backend id or error."""

    def __call__(
        self,
        *,
        project_root: Path,
        backend: str | None,
        force: bool,
    ) -> tuple[str | None, str | None]: ...


class ResolveInitDocsDir(Protocol):
    """Resolve init docs directory selection and return docs dir or error."""

    def __call__(
        self,
        *,
        project_root: Path,
        docs_mode: str | None,
        scaffold_docs_dir: str,
    ) -> tuple[str | None, str | None]: ...


class ResolveInitAgentsMode(Protocol):
    """Resolve AGENTS.md handling mode and return mode or error."""

    def __call__(
        self,
        *,
        project_root: Path,
        agents_mode: str | None,
    ) -> tuple[str | None, str | None]: ...


class ResolveInitAgentsLauncher(Protocol):
    """Resolve AGENTS launcher wording and return launcher id or error."""

    def __call__(
        self,
        *,
        agents_launcher: str | None,
    ) -> tuple[str | None, str | None]: ...


class ResolveInitCodexProfileOverwrite(Protocol):
    """Resolve codex profile conflict behavior and return overwrite flag or error."""

    def __call__(
        self,
        *,
        project_root: Path,
        selected_backend: str,
        force: bool,
    ) -> tuple[bool, str | None]: ...


class ApplyBaselineScaffold(Protocol):
    """Apply baseline scaffold and return created/skipped counters."""

    def __call__(
        self,
        *,
        project_root: Path,
        options: BaselineScaffoldOptions,
    ) -> tuple[int, int]: ...


class WriteInitDocsRootConfig(Protocol):
    """Write docs-root config and return created/skipped counters."""

    def __call__(
        self,
        *,
        project_root: Path,
        docs_dir: str,
        force: bool,
    ) -> tuple[int, int]: ...


class WriteInitBackendConfig(Protocol):
    """Write backend config and return created/skipped counters."""

    def __call__(
        self,
        *,
        project_root: Path,
        backend_id: str,
        force: bool,
        codex_profile_force: bool,
    ) -> tuple[int, int]: ...


class InstallPrecommitHooksBestEffort(Protocol):
    """Install pre-commit hooks for scaffold profile when available."""

    def __call__(
        self,
        *,
        project_root: Path,
        scaffold_profile: str,
    ) -> None: ...


class InitWorkspaceRequest(BaseModel):  # pylint: disable=too-many-instance-attributes
    """User-provided init command inputs resolved at CLI boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    force: bool
    scaffold_profile: str
    scaffold_docs_dir: str
    pack: str | None = None
    backend: str | None = None
    docs_mode: str | None = None
    agents_mode: str | None = None
    agents_launcher: str | None = None
    model: str = DEFAULT_AGENT_MODEL
    no_precommit_install: bool = False


class InitWorkspaceDependencies(BaseModel):  # pylint: disable=too-many-instance-attributes
    """Injected side-effect operations required by init orchestration."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    emit: Callable[[str], None]
    resolve_pack: ResolveInitPack
    resolve_backend: SkipValidation[ResolveInitBackend]
    resolve_docs_dir: SkipValidation[ResolveInitDocsDir]
    resolve_agents_mode: SkipValidation[ResolveInitAgentsMode]
    resolve_agents_launcher: SkipValidation[ResolveInitAgentsLauncher]
    resolve_codex_profile_overwrite: SkipValidation[ResolveInitCodexProfileOverwrite]
    next_agents_backup_path: Callable[[Path], Path]
    apply_baseline_scaffold: SkipValidation[ApplyBaselineScaffold]
    write_init_docs_root_config: SkipValidation[WriteInitDocsRootConfig]
    write_init_backend_config: SkipValidation[WriteInitBackendConfig]
    build_agents_merge_followup_spec: Callable[[str], str]
    install_precommit_hooks_best_effort: SkipValidation[InstallPrecommitHooksBestEffort]


def _emit_error_and_fail(
    dependencies: InitWorkspaceDependencies,
    error: str | None,
) -> int:
    dependencies.emit(str(error))
    return 1


def _resolve_pack_or_fail(
    request: InitWorkspaceRequest,
    dependencies: InitWorkspaceDependencies,
) -> tuple[str, int | None]:
    pack, error = dependencies.resolve_pack(request.pack)
    if error is not None or pack is None:
        return "", _emit_error_and_fail(dependencies, error)
    return pack, None


def _resolve_backend_or_fail(
    request: InitWorkspaceRequest,
    dependencies: InitWorkspaceDependencies,
) -> tuple[str, int | None]:
    selected_backend, error = dependencies.resolve_backend(
        project_root=request.project_root,
        backend=request.backend,
        force=request.force,
    )
    if error is not None or selected_backend is None:
        return "", _emit_error_and_fail(dependencies, error)
    return selected_backend, None


def _resolve_docs_dir_or_fail(
    request: InitWorkspaceRequest,
    dependencies: InitWorkspaceDependencies,
) -> tuple[str, int | None]:
    docs_dir, error = dependencies.resolve_docs_dir(
        project_root=request.project_root,
        docs_mode=request.docs_mode,
        scaffold_docs_dir=request.scaffold_docs_dir,
    )
    if error is not None or docs_dir is None:
        return "", _emit_error_and_fail(dependencies, error)
    return docs_dir, None


def _resolve_agents_mode_or_fail(
    request: InitWorkspaceRequest,
    dependencies: InitWorkspaceDependencies,
) -> tuple[str, int | None]:
    resolved_agents_mode, error = dependencies.resolve_agents_mode(
        project_root=request.project_root,
        agents_mode=request.agents_mode,
    )
    if error is not None or resolved_agents_mode is None:
        return "", _emit_error_and_fail(dependencies, error)
    return resolved_agents_mode, None


def _resolve_agents_launcher_or_fail(
    request: InitWorkspaceRequest,
    dependencies: InitWorkspaceDependencies,
) -> tuple[str, int | None]:
    resolved_agents_launcher, error = dependencies.resolve_agents_launcher(
        agents_launcher=request.agents_launcher,
    )
    if error is not None or resolved_agents_launcher is None:
        return "", _emit_error_and_fail(dependencies, error)
    return resolved_agents_launcher, None


def _maybe_backup_agents_file(
    request: InitWorkspaceRequest,
    dependencies: InitWorkspaceDependencies,
    resolved_agents_mode: str,
) -> str | None:
    if resolved_agents_mode != "preserve":
        return None
    agents_backup_path = dependencies.next_agents_backup_path(request.project_root)
    (request.project_root / "AGENTS.md").rename(agents_backup_path)
    return agents_backup_path.name


def _maybe_remove_existing_agents_for_overwrite(
    request: InitWorkspaceRequest,
    resolved_agents_mode: str,
) -> None:
    if resolved_agents_mode != "overwrite":
        return
    agents_path = request.project_root / "AGENTS.md"
    if agents_path.exists():
        agents_path.unlink()


def _apply_init_config_writes(
    request: InitWorkspaceRequest,
    dependencies: InitWorkspaceDependencies,
    *,
    docs_dir: str,
    selected_backend: str,
    codex_profile_overwrite: bool,
) -> tuple[int, int]:
    config_created, config_skipped = dependencies.write_init_docs_root_config(
        project_root=request.project_root,
        docs_dir=docs_dir,
        force=request.force,
    )
    backend_created, backend_skipped = dependencies.write_init_backend_config(
        project_root=request.project_root,
        backend_id=selected_backend,
        force=request.force,
        codex_profile_force=codex_profile_overwrite,
    )
    return config_created + backend_created, config_skipped + backend_skipped


def _resolve_codex_profile_overwrite_or_fail(
    request: InitWorkspaceRequest,
    dependencies: InitWorkspaceDependencies,
    *,
    selected_backend: str,
) -> tuple[bool, int | None]:
    codex_profile_overwrite, error = dependencies.resolve_codex_profile_overwrite(
        project_root=request.project_root,
        selected_backend=selected_backend,
        force=request.force,
    )
    if error is not None:
        return False, _emit_error_and_fail(dependencies, error)
    return codex_profile_overwrite, None


def _maybe_write_merge_followup_spec(
    request: InitWorkspaceRequest,
    dependencies: InitWorkspaceDependencies,
    *,
    docs_dir: str,
    resolved_agents_mode: str,
    agents_backup_name: str | None,
) -> tuple[int, int, str]:
    if resolved_agents_mode != "preserve" or agents_backup_name is None:
        return 0, 0, ""

    merge_spec_relative = (
        Path(docs_dir)
        / "spec"
        / "features"
        / "FEAT-900-merge-preserved-agents-guidance.yaml"
    )
    merge_spec_path = request.project_root / merge_spec_relative
    if not merge_spec_path.exists() or request.force:
        merge_spec_path.parent.mkdir(parents=True, exist_ok=True)
        merge_spec_path.write_text(
            dependencies.build_agents_merge_followup_spec(agents_backup_name),
            encoding="utf-8",
        )
        return 1, 0, f" merge_spec={merge_spec_relative}"

    return 0, 1, f" merge_spec_skipped={merge_spec_relative}"


def _maybe_install_precommit_hooks(
    request: InitWorkspaceRequest,
    dependencies: InitWorkspaceDependencies,
) -> None:
    if request.no_precommit_install:
        return
    dependencies.install_precommit_hooks_best_effort(
        project_root=request.project_root,
        scaffold_profile=request.scaffold_profile,
    )


def _render_agents_mode_output(
    resolved_agents_mode: str,
    agents_backup_name: str | None,
) -> str:
    agents_mode_output = f" agents_mode={resolved_agents_mode}"
    if agents_backup_name is not None:
        return agents_mode_output + f" agents_backup={agents_backup_name}"
    return agents_mode_output


class InitWorkspaceService:
    """Owns repository initialization and baseline scaffold setup."""

    def run(
        self,
        request: InitWorkspaceRequest,
        dependencies: InitWorkspaceDependencies,
    ) -> int:
        """Execute init orchestration with injected dependencies and stable CLI semantics."""
        pack, failure_code = _resolve_pack_or_fail(request, dependencies)
        if failure_code is not None:
            return failure_code

        selected_backend, failure_code = _resolve_backend_or_fail(
            request,
            dependencies,
        )
        if failure_code is not None:
            return failure_code

        docs_dir, failure_code = _resolve_docs_dir_or_fail(request, dependencies)
        if failure_code is not None:
            return failure_code

        resolved_agents_mode, failure_code = _resolve_agents_mode_or_fail(
            request,
            dependencies,
        )
        if failure_code is not None:
            return failure_code
        if resolved_agents_mode == "abort":
            dependencies.emit(
                "init aborted: kept existing AGENTS.md; no scaffold files changed"
            )
            return 0

        agents_launcher, failure_code = _resolve_agents_launcher_or_fail(
            request,
            dependencies,
        )
        if failure_code is not None:
            return failure_code

        codex_profile_overwrite, failure_code = (
            _resolve_codex_profile_overwrite_or_fail(
                request,
                dependencies,
                selected_backend=selected_backend,
            )
        )
        if failure_code is not None:
            return failure_code

        agents_backup_name = _maybe_backup_agents_file(
            request,
            dependencies,
            resolved_agents_mode,
        )
        _maybe_remove_existing_agents_for_overwrite(request, resolved_agents_mode)

        created, skipped = dependencies.apply_baseline_scaffold(
            project_root=request.project_root,
            options=BaselineScaffoldOptions(
                force=request.force,
                docs_dir=docs_dir,
                profile=request.scaffold_profile,
                pack=pack,
                backend_id=selected_backend,
                agents_launcher=agents_launcher,
                agent_model=request.model,
            ),
        )

        if pack == "standard":
            dependencies.emit(
                "init pack standard: wired a demo failing fitness rule into precommit (expected to fail)"
            )

        config_created, config_skipped = _apply_init_config_writes(
            request,
            dependencies,
            docs_dir=docs_dir,
            selected_backend=selected_backend,
            codex_profile_overwrite=codex_profile_overwrite,
        )
        created += config_created
        skipped += config_skipped

        merge_created, merge_skipped, merge_spec_output = (
            _maybe_write_merge_followup_spec(
                request,
                dependencies,
                docs_dir=docs_dir,
                resolved_agents_mode=resolved_agents_mode,
                agents_backup_name=agents_backup_name,
            )
        )
        created += merge_created
        skipped += merge_skipped

        _maybe_install_precommit_hooks(request, dependencies)

        agents_mode_output = _render_agents_mode_output(
            resolved_agents_mode,
            agents_backup_name,
        )
        dependencies.emit(
            f"init scaffold complete: docs_dir={docs_dir} "
            f"created={created} skipped={skipped}"
            f" profile={request.scaffold_profile}"
            f" pack={pack}"
            f" agents_launcher={agents_launcher}"
            f"{agents_mode_output}{merge_spec_output}"
        )
        return 0
