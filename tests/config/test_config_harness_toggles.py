from __future__ import annotations

from pathlib import Path

import pytest

import engineeringagent.config as config_module
import engineeringagent.checks.fitness.config as fitness_config_module
from engineeringagent.checks.fitness.config import (
    resolve_harness_fitness_opencode_real_smoke_enabled,
)
from engineeringagent.checks.pytest.config import (
    resolve_harness_pytest_opencode_integration_enabled,
)


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


@pytest.mark.parametrize(
    "payload",
    [
        "[harness.fitness]\nopencode-real-smoke = 1\n",
        "[harness.fitness]\nopencode-real-smoke = 'true'\n",
        "[harness.pytest]\nopencode-integration = 0\n",
        "[harness.pytest]\nopencode-integration = 'false'\n",
    ],
)
def test_harness_toggles_reject_invalid_values(tmp_path: Path, payload: str) -> None:
    (tmp_path / "engineeringagent.toml").write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="harness"):
        resolve_harness_fitness_opencode_real_smoke_enabled(tmp_path)
        resolve_harness_pytest_opencode_integration_enabled(tmp_path)


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
