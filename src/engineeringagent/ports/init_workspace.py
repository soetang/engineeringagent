"""Init workspace dependency contracts owned by the ports layer."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, NamedTuple, Protocol

from pydantic import BaseModel, ConfigDict, SkipValidation

DEFAULT_AGENT_MODEL = "openai/gpt-5.3-codex"


class BaselineScaffoldOptions(NamedTuple):
    """Options controlling init scaffold generation."""

    force: bool = False
    docs_dir: str = "docs"
    profile: str = "core"
    pack: str = "slim"
    backend_id: str | None = None
    agents_launcher: str = "uvx"
    agent_model: str = DEFAULT_AGENT_MODEL

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
    ) -> tuple[str, ...]: ...


class InitWorkspaceDependencies(BaseModel):  # pylint: disable=too-many-instance-attributes
    """Injected side-effect operations required by init orchestration."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

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
