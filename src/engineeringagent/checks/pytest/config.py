from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.config import resolve_harness_bool_setting


def resolve_harness_pytest_opencode_integration_enabled(project_root: Path) -> bool:
    """Resolve whether OpenCode integration tests are enabled."""

    return resolve_harness_bool_setting(
        project_root,
        table="pytest",
        key="opencode-integration",
        default=False,
    )


__all__ = ["resolve_harness_pytest_opencode_integration_enabled"]
