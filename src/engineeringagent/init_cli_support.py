from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field

from .agents import default_backend_id, list_backends
from .config import (
    DEFAULT_CODEX_PROFILE,
    resolve_agents_backend_id,
    resolve_agents_codex_profile_in_engineeringagent_toml,
)
from .git import client as git_client
from .init_scaffold import AGENTS_LAUNCHER_CHOICES, DEFAULT_AGENTS_LAUNCHER
from .terminal import stdout_is_tty

InputFn = Callable[[str], str]

_INIT_PACK_DEFAULT = "slim"
_INIT_PACK_CHOICES: tuple[str, ...] = ("slim", "standard")


class InitPromptContext(BaseModel):
    """IO hooks for init prompt resolution."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", arbitrary_types_allowed=True
    )

    stdout: object = Field(default_factory=lambda: sys.stdout)
    input_fn: InputFn | None = None
    stdout_is_tty_fn: Callable[[object], bool] = Field(
        default_factory=lambda: stdout_is_tty
    )

    def prompt(self, prompt: str) -> str:
        """Read a prompt through the configured input hook."""
        prompt_reader = input if self.input_fn is None else self.input_fn
        return prompt_reader(prompt)

    def is_tty(self) -> bool:
        """Return whether the configured stdio stream is interactive."""
        return self.stdout_is_tty_fn(self.stdout)


class InitBackendResolverDeps(BaseModel):
    """Dependency hooks for backend selection."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", arbitrary_types_allowed=True
    )

    list_backends_fn: Callable[[], tuple[str, ...]] = Field(
        default_factory=lambda: list_backends
    )
    resolve_agents_backend_id_fn: Callable[[Path], str | None] = Field(
        default_factory=lambda: resolve_agents_backend_id
    )
    default_backend_id_fn: Callable[[], str] = Field(
        default_factory=lambda: default_backend_id
    )


class InitCodexProfileResolverDeps(BaseModel):
    """Dependency hooks for codex profile resolution."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", arbitrary_types_allowed=True
    )

    resolve_codex_profile_fn: Callable[[Path], str | None] = Field(
        default_factory=lambda: resolve_agents_codex_profile_in_engineeringagent_toml
    )


class InitAgentsLauncherResolverDeps(BaseModel):
    """Dependency hooks for AGENTS launcher selection."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", arbitrary_types_allowed=True
    )

    launcher_choices: tuple[str, ...] = AGENTS_LAUNCHER_CHOICES
    default_launcher: str = DEFAULT_AGENTS_LAUNCHER


def resolve_init_pack(
    pack: str | None,
    *,
    stdout: object | None = None,
    input_fn: InputFn | None = None,
    stdout_is_tty_fn: Callable[[object], bool] = stdout_is_tty,
) -> tuple[str | None, str | None]:
    """Resolve the init pack (slim|standard), prompting only on TTY when omitted."""
    prompt_reader = input if input_fn is None else input_fn
    active_stdout = sys.stdout if stdout is None else stdout
    if pack is not None:
        return pack, None

    if not stdout_is_tty_fn(active_stdout):
        return _INIT_PACK_DEFAULT, None

    prompt = "init pack: choose [slim/standard] (default slim): "
    selected = prompt_reader(prompt).strip().lower()
    if selected == "":
        return _INIT_PACK_DEFAULT, None
    if selected in _INIT_PACK_CHOICES:
        return selected, None

    return (
        None,
        "init input error: pack must be 'slim' or 'standard'",
    )


def backend_choice_error(backend_ids: tuple[str, ...]) -> str:
    """Return deterministic backend input error text."""
    return f"init input error: backend must be one of: {', '.join(backend_ids)}"


def resolve_configured_backend(
    *,
    project_root: Path,
    force: bool,
    resolve_agents_backend_id_fn: Callable[[Path], str | None] = resolve_agents_backend_id,
) -> str | None:
    """Resolve a previously configured backend unless force bypasses it."""
    if force:
        return None
    return resolve_agents_backend_id_fn(project_root)


def resolve_init_backend_candidate(
    candidate: str,
    available_backends: tuple[str, ...],
) -> tuple[str | None, str | None]:
    """Validate a backend candidate against the registered backend ids."""
    if candidate in available_backends:
        return candidate, None
    return None, backend_choice_error(available_backends)


def resolve_init_backend_interactive(
    available_backends: tuple[str, ...],
    *,
    default_backend_id_fn: Callable[[], str] = default_backend_id,
    prompt_context: InitPromptContext | None = None,
) -> tuple[str | None, str | None]:
    """Resolve backend selection from interactive defaults when needed."""
    prompt_io = InitPromptContext() if prompt_context is None else prompt_context
    if len(available_backends) == 1:
        return available_backends[0], None

    default_backend = default_backend_id_fn()
    if not prompt_io.is_tty():
        return default_backend, None

    prompt = (
        f"init backend: choose [{'/'.join(available_backends)}] "
        f"(default {default_backend}): "
    )
    try:
        selected = prompt_io.prompt(prompt).strip()
    except EOFError:
        selected = ""
    if selected == "":
        return default_backend, None
    if selected in available_backends:
        return selected, None
    return None, backend_choice_error(available_backends)


def resolve_init_backend(
    *,
    project_root: Path,
    backend: str | None,
    force: bool,
    prompt_context: InitPromptContext | None = None,
    deps: InitBackendResolverDeps | None = None,
) -> tuple[str | None, str | None]:
    """Resolve init backend choice from CLI args/config/prompt defaults."""
    prompt_io = InitPromptContext() if prompt_context is None else prompt_context
    resolver_deps = InitBackendResolverDeps() if deps is None else deps
    available_backends = tuple(sorted(resolver_deps.list_backends_fn()))
    if not available_backends:
        return None, "init backend error: no registered backends"

    if backend is not None:
        return resolve_init_backend_candidate(backend, available_backends)

    configured_backend = resolve_configured_backend(
        project_root=project_root,
        force=force,
        resolve_agents_backend_id_fn=resolver_deps.resolve_agents_backend_id_fn,
    )
    if configured_backend is not None:
        return resolve_init_backend_candidate(configured_backend, available_backends)

    return resolve_init_backend_interactive(
        available_backends,
        default_backend_id_fn=resolver_deps.default_backend_id_fn,
        prompt_context=prompt_io,
    )


def resolve_init_codex_profile_overwrite(
    *,
    project_root: Path,
    selected_backend: str,
    force: bool,
    prompt_context: InitPromptContext | None = None,
    deps: InitCodexProfileResolverDeps | None = None,
) -> tuple[bool, str | None]:
    """Resolve whether init should overwrite an existing codex profile value."""
    prompt_io = InitPromptContext() if prompt_context is None else prompt_context
    resolver_deps = InitCodexProfileResolverDeps() if deps is None else deps
    if selected_backend != "codex":
        return False, None
    if force:
        return True, None

    configured_profile = resolver_deps.resolve_codex_profile_fn(project_root)
    if configured_profile is None or configured_profile == DEFAULT_CODEX_PROFILE:
        return False, None
    if not prompt_io.is_tty():
        return False, None

    prompt = (
        f'init conflict: [agents.codex].profile is "{configured_profile}". '
        "Choose codex profile handling [keep/overwrite]: "
    )
    try:
        selected = prompt_io.prompt(prompt).strip().lower()
    except EOFError:
        selected = "keep"
    if selected in {"", "keep"}:
        return False, None
    if selected == "overwrite":
        return True, None

    return (
        False,
        "init input error: codex profile handling must be 'keep' or "
        "'overwrite' when [agents.codex].profile differs",
    )


def resolve_init_docs_dir(
    project_root: Path,
    docs_mode: str | None,
    scaffold_docs_dir: str,
    input_fn: InputFn | None = None,
) -> tuple[str | None, str | None]:
    """Resolve the docs target for scaffold output."""
    prompt_reader = input if input_fn is None else input_fn
    normalized_scaffold_docs_dir = scaffold_docs_dir.strip("/")
    docs_exists = (project_root / "docs").is_dir()

    if not normalized_scaffold_docs_dir:
        return None, "init input error: --scaffold-docs-dir cannot be empty"

    if not docs_exists:
        return "docs", None

    selected_mode = docs_mode
    if selected_mode is None:
        prompt = (
            "init conflict: docs/ already exists. Choose docs handling "
            "[reuse/separate]: "
        )
        selected_mode = prompt_reader(prompt).strip().lower()

    if selected_mode == "reuse":
        return "docs", None
    if selected_mode == "separate":
        if normalized_scaffold_docs_dir == "docs":
            return (
                None,
                "init input error: --scaffold-docs-dir must differ from docs "
                "when using --docs-mode separate",
            )
        return normalized_scaffold_docs_dir, None

    return (
        None,
        "init input error: docs mode must be 'reuse' or 'separate' when docs/ exists",
    )


def resolve_init_agents_mode(
    project_root: Path,
    agents_mode: str | None,
    input_fn: InputFn | None = None,
) -> tuple[str | None, str | None]:
    """Resolve AGENTS.md conflict behavior."""
    prompt_reader = input if input_fn is None else input_fn
    agents_path = project_root / "AGENTS.md"
    if not agents_path.exists():
        return "create", None

    selected_mode = agents_mode
    if selected_mode is None:
        prompt = (
            "init conflict: AGENTS.md already exists. Choose AGENTS handling "
            "[overwrite/preserve/abort]: "
        )
        selected_mode = prompt_reader(prompt).strip().lower()

    if selected_mode in {"overwrite", "preserve", "abort"}:
        return selected_mode, None

    return (
        None,
        "init input error: AGENTS mode must be 'overwrite', 'preserve', or 'abort' "
        "when AGENTS.md exists",
    )


def resolve_init_agents_launcher(
    *,
    agents_launcher: str | None,
    prompt_context: InitPromptContext | None = None,
    deps: InitAgentsLauncherResolverDeps | None = None,
) -> tuple[str | None, str | None]:
    """Resolve AGENTS scaffold launcher wording."""
    prompt_io = InitPromptContext() if prompt_context is None else prompt_context
    resolver_deps = InitAgentsLauncherResolverDeps() if deps is None else deps
    choices_csv = ", ".join(resolver_deps.launcher_choices)
    error_message = "init input error: AGENTS launcher must be one of: " + choices_csv

    if agents_launcher is not None:
        if agents_launcher in resolver_deps.launcher_choices:
            return agents_launcher, None
        return None, error_message

    if not prompt_io.is_tty():
        return resolver_deps.default_launcher, None

    prompt_choices = "/".join(resolver_deps.launcher_choices)
    prompt = (
        f"init AGENTS launcher: choose [{prompt_choices}] "
        f"(default {resolver_deps.default_launcher}): "
    )
    try:
        selected = prompt_io.prompt(prompt).strip().lower()
    except EOFError:
        selected = ""
    if selected == "":
        return resolver_deps.default_launcher, None
    if selected in resolver_deps.launcher_choices:
        return selected, None
    return None, error_message


def next_agents_backup_path(project_root: Path) -> Path:
    """Select the next available AGENTS backup path."""
    candidate = project_root / "AGENTS.user.md"
    suffix = 1
    while candidate.exists():
        suffix += 1
        candidate = project_root / f"AGENTS.user.{suffix}.md"
    return candidate


def precommit_remediation_commands(*, scaffold_profile: str) -> list[str]:
    """Return deterministic remediation commands for hook installation."""
    commands = ["pre-commit install"]
    if scaffold_profile == "python_uv":
        commands.append("pre-commit install --hook-type commit-msg")
    return commands


def install_precommit_hooks_best_effort(
    *,
    project_root: Path,
    scaffold_profile: str,
    emit: Callable[[str], None] = print,
) -> None:
    """Best-effort install pre-commit hooks when prerequisites are met."""
    if not (project_root / ".git").exists():
        remediation = " && ".join(
            ["git init", *precommit_remediation_commands(scaffold_profile=scaffold_profile)]
        )
        emit(
            "init hint: skipped pre-commit hook install (no .git directory). "
            f"To enable later: {remediation}"
        )
        return

    if shutil.which("pre-commit") is None:
        remediation = " && ".join(
            precommit_remediation_commands(scaffold_profile=scaffold_profile)
        )
        emit(
            "init hint: skipped pre-commit hook install (pre-commit not found on PATH). "
            f"To enable later: {remediation}"
        )
        return

    hook_types: list[str | None] = [None]
    if scaffold_profile == "python_uv":
        hook_types.append("commit-msg")

    for hook_type in hook_types:
        retry_command = "pre-commit install"
        if hook_type is not None:
            retry_command = f"pre-commit install --hook-type {hook_type}"

        try:
            result = git_client.precommit_install(project_root, hook_type=hook_type)
        except OSError as exc:
            emit(
                "init warning: pre-commit hook install failed "
                f"(error={exc.__class__.__name__}). To retry: {retry_command}"
            )
            continue
        if result.returncode == 0:
            continue
        emit(
            "init warning: pre-commit hook install failed "
            f"(exit_code={result.returncode}). To retry: {retry_command}"
        )
