from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from engineeringagent.init_scaffold import BaselineScaffoldOptions, DEFAULT_AGENT_MODEL
from engineeringagent.ports import InitWorkspaceDependencies


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


class InitWorkspaceResult(BaseModel):
    """Stable application result for repository initialization."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    exit_code: int
    status: Literal["completed", "aborted", "failed"]
    messages: tuple[str, ...] = ()
    docs_dir: str | None = None
    created: int = 0
    skipped: int = 0
    profile: str | None = None
    pack: str | None = None
    agents_launcher: str | None = None
    agents_mode: str | None = None
    agents_backup_name: str | None = None
    merge_spec_output: str | None = None
    notes: tuple[str, ...] = Field(default_factory=tuple)


def _failure_result(error: str | None) -> InitWorkspaceResult:
    return InitWorkspaceResult(
        exit_code=1,
        status="failed",
        messages=(str(error),),
    )


def _resolve_pack_or_fail(
    request: InitWorkspaceRequest,
    dependencies: InitWorkspaceDependencies,
) -> tuple[str, str | None]:
    pack, error = dependencies.resolve_pack(request.pack)
    if error is not None or pack is None:
        return "", error or "init input error"
    return pack, None


def _resolve_backend_or_fail(
    request: InitWorkspaceRequest,
    dependencies: InitWorkspaceDependencies,
) -> tuple[str, str | None]:
    selected_backend, error = dependencies.resolve_backend(
        project_root=request.project_root,
        backend=request.backend,
        force=request.force,
    )
    if error is not None or selected_backend is None:
        return "", error or "init input error"
    return selected_backend, None


def _resolve_docs_dir_or_fail(
    request: InitWorkspaceRequest,
    dependencies: InitWorkspaceDependencies,
) -> tuple[str, str | None]:
    docs_dir, error = dependencies.resolve_docs_dir(
        project_root=request.project_root,
        docs_mode=request.docs_mode,
        scaffold_docs_dir=request.scaffold_docs_dir,
    )
    if error is not None or docs_dir is None:
        return "", error or "init input error"
    return docs_dir, None


def _resolve_agents_mode_or_fail(
    request: InitWorkspaceRequest,
    dependencies: InitWorkspaceDependencies,
) -> tuple[str, str | None]:
    resolved_agents_mode, error = dependencies.resolve_agents_mode(
        project_root=request.project_root,
        agents_mode=request.agents_mode,
    )
    if error is not None or resolved_agents_mode is None:
        return "", error or "init input error"
    return resolved_agents_mode, None


def _resolve_agents_launcher_or_fail(
    request: InitWorkspaceRequest,
    dependencies: InitWorkspaceDependencies,
) -> tuple[str, str | None]:
    resolved_agents_launcher, error = dependencies.resolve_agents_launcher(
        agents_launcher=request.agents_launcher,
    )
    if error is not None or resolved_agents_launcher is None:
        return "", error or "init input error"
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
) -> tuple[bool, str | None]:
    codex_profile_overwrite, error = dependencies.resolve_codex_profile_overwrite(
        project_root=request.project_root,
        selected_backend=selected_backend,
        force=request.force,
    )
    if error is not None:
        return False, error
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


def _collect_precommit_messages(
    request: InitWorkspaceRequest,
    dependencies: InitWorkspaceDependencies,
) -> tuple[str, ...]:
    if request.no_precommit_install:
        return ()
    return dependencies.install_precommit_hooks_best_effort(
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
    ) -> InitWorkspaceResult:
        """Execute init orchestration and return typed application results."""
        pack, error = _resolve_pack_or_fail(request, dependencies)
        if error is not None:
            return _failure_result(error)

        selected_backend, error = _resolve_backend_or_fail(
            request,
            dependencies,
        )
        if error is not None:
            return _failure_result(error)

        docs_dir, error = _resolve_docs_dir_or_fail(request, dependencies)
        if error is not None:
            return _failure_result(error)

        resolved_agents_mode, error = _resolve_agents_mode_or_fail(
            request,
            dependencies,
        )
        if error is not None:
            return _failure_result(error)
        if resolved_agents_mode == "abort":
            return InitWorkspaceResult(
                exit_code=0,
                status="aborted",
                messages=(
                    "init aborted: kept existing AGENTS.md; no scaffold files changed",
                ),
                docs_dir=docs_dir,
                profile=request.scaffold_profile,
                pack=pack,
                agents_mode=resolved_agents_mode,
            )

        agents_launcher, error = _resolve_agents_launcher_or_fail(
            request,
            dependencies,
        )
        if error is not None:
            return _failure_result(error)

        codex_profile_overwrite, error = (
            _resolve_codex_profile_overwrite_or_fail(
                request,
                dependencies,
                selected_backend=selected_backend,
            )
        )
        if error is not None:
            return _failure_result(error)

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

        notes: list[str] = []
        if pack == "standard":
            notes.append(
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

        precommit_messages = _collect_precommit_messages(request, dependencies)

        agents_mode_output = _render_agents_mode_output(
            resolved_agents_mode,
            agents_backup_name,
        )
        summary = (
            f"init scaffold complete: docs_dir={docs_dir} "
            f"created={created} skipped={skipped}"
            f" profile={request.scaffold_profile}"
            f" pack={pack}"
            f" agents_launcher={agents_launcher}"
            f"{agents_mode_output}{merge_spec_output}"
        )
        return InitWorkspaceResult(
            exit_code=0,
            status="completed",
            messages=(*precommit_messages, summary),
            docs_dir=docs_dir,
            created=created,
            skipped=skipped,
            profile=request.scaffold_profile,
            pack=pack,
            agents_launcher=agents_launcher,
            agents_mode=resolved_agents_mode,
            agents_backup_name=agents_backup_name,
            merge_spec_output=merge_spec_output.strip() or None,
            notes=tuple(notes),
        )
