from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _uses_explicit_test_selection(args: tuple[str, ...]) -> bool:
    return any(
        not arg.startswith("-")
        and (arg.endswith(".py") or "/" in arg or arg.startswith("tests"))
        for arg in args
    )


def pytest_configure(config) -> None:  # type: ignore[no-untyped-def]
    if not _uses_explicit_test_selection(config.invocation_params.args):
        return

    cov_plugin = config.pluginmanager.getplugin("_cov")
    if cov_plugin is None:
        return

    config.option.cov_fail_under = 0
    cov_plugin.options.cov_fail_under = 0


@pytest.fixture
def repo_root(pytestconfig: pytest.Config) -> Path:
    """Return the repository root for stable path resolution in tests."""

    return Path(pytestconfig.rootpath)
