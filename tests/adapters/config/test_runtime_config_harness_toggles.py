from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

import engineeringagent.adapters.config as config_module
import engineeringagent.checks.fitness.config as fitness_config_module
from engineeringagent.checks.fitness.config import (
    resolve_harness_fitness_opencode_real_smoke_enabled,
)
from engineeringagent.checks.pytest.config import (
    resolve_harness_pytest_opencode_integration_enabled,
)
from engineeringagent.adapters.config import resolve_harness_bool_setting


def test_harness_fitness_opencode_real_smoke_defaults_to_false(tmp_path: Path) -> None:
    assert resolve_harness_fitness_opencode_real_smoke_enabled(tmp_path) is False


def test_harness_pytest_opencode_integration_defaults_to_false(tmp_path: Path) -> None:
    assert resolve_harness_pytest_opencode_integration_enabled(tmp_path) is False


def test_harness_toggles_prefer_engineeringagent_toml_over_pyproject(
    tmp_path: Path,
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        "[harness.fitness]\nopencode-real-smoke = true\n\n"
        "[harness.pytest]\nopencode-integration = false\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        "[tool.engineeringagent.harness.fitness]\nopencode-real-smoke = false\n\n"
        "[tool.engineeringagent.harness.pytest]\nopencode-integration = true\n",
        encoding="utf-8",
    )

    assert resolve_harness_fitness_opencode_real_smoke_enabled(tmp_path) is True
    assert resolve_harness_pytest_opencode_integration_enabled(tmp_path) is False


def test_harness_toggles_read_pyproject_tool_engineeringagent(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.engineeringagent.harness.fitness]\nopencode-real-smoke = true\n\n"
        "[tool.engineeringagent.harness.pytest]\nopencode-integration = true\n",
        encoding="utf-8",
    )

    assert resolve_harness_fitness_opencode_real_smoke_enabled(tmp_path) is True
    assert resolve_harness_pytest_opencode_integration_enabled(tmp_path) is True


def test_harness_toggle_defaults_when_setting_key_is_missing(tmp_path: Path) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        "[harness.fitness]\n",
        encoding="utf-8",
    )

    assert resolve_harness_fitness_opencode_real_smoke_enabled(tmp_path) is False


def test_resolve_harness_bool_setting_returns_explicit_default_when_unset(
    tmp_path: Path,
) -> None:
    assert (
        resolve_harness_bool_setting(
            tmp_path,
            table="fitness",
            key="opencode-real-smoke",
            default=True,
        )
        is True
    )


@pytest.mark.parametrize(
    ("payload", "resolver"),
    [
        (
            "[harness.fitness]\nopencode-real-smoke = 1\n",
            resolve_harness_fitness_opencode_real_smoke_enabled,
        ),
        (
            "[harness.fitness]\nopencode-real-smoke = 'true'\n",
            resolve_harness_fitness_opencode_real_smoke_enabled,
        ),
        (
            "[harness.pytest]\nopencode-integration = 0\n",
            resolve_harness_pytest_opencode_integration_enabled,
        ),
        (
            "[harness.pytest]\nopencode-integration = 'false'\n",
            resolve_harness_pytest_opencode_integration_enabled,
        ),
    ],
)
def test_harness_toggles_reject_invalid_values(
    tmp_path: Path,
    payload: str,
    resolver: Callable[[Path], bool],
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="harness"):
        resolver(tmp_path)


def test_config_module_does_not_export_backend_specific_harness_resolvers() -> None:
    assert not hasattr(
        config_module,
        "resolve_harness_fitness_opencode_real_smoke_enabled",
    )
    assert not hasattr(
        config_module,
        "resolve_harness_pytest_opencode_integration_enabled",
    )


def test_fitness_config_only_exports_fitness_resolver() -> None:
    assert not hasattr(
        fitness_config_module,
        "resolve_harness_pytest_opencode_integration_enabled",
    )
