from __future__ import annotations

import importlib
import importlib.util

import pytest


def test_legacy_checks_packages_are_removed() -> None:
    assert importlib.util.find_spec("engineeringagent.fitness") is None


@pytest.mark.parametrize(
    "module_name",
    [
        "engineeringagent.progress_paths",
        "engineeringagent.progress_logging",
    ],
)
def test_legacy_progress_shim_modules_are_not_discoverable(module_name: str) -> None:
    assert importlib.util.find_spec(module_name) is None


@pytest.mark.parametrize(
    "module_name",
    [
        "engineeringagent.progress_paths",
        "engineeringagent.progress_logging",
    ],
)
def test_legacy_progress_shim_module_imports_fail(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


@pytest.mark.parametrize("module_name", ["progress_paths", "progress_logging"])
def test_legacy_package_level_shim_imports_fail(module_name: str) -> None:
    with pytest.raises(ImportError):
        exec(f"from engineeringagent import {module_name}")
