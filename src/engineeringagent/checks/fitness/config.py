from __future__ import annotations

from pathlib import Path

from engineeringagent.config import resolve_harness_bool_setting


def resolve_harness_fitness_opencode_real_smoke_enabled(project_root: Path) -> bool:
    """Resolve whether the OpenCode smoke fitness rule is enabled."""

    return resolve_harness_bool_setting(
        project_root,
        table="fitness",
        key="opencode-real-smoke",
        default=False,
    )


__all__ = [
    "resolve_harness_fitness_opencode_real_smoke_enabled",
]
