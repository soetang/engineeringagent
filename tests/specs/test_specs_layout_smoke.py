from __future__ import annotations

from pathlib import Path

import pytest


def test_feature_specs_directory_exists(pytestconfig: pytest.Config) -> None:
    repo_root = Path(pytestconfig.rootpath)
    features_dir = repo_root / "docs" / "spec" / "features"
    features_done_dir = repo_root / "docs" / "spec" / "features_done"
    assert features_dir.exists()
    assert any(features_dir.glob("*.yaml")) or any(features_done_dir.glob("*.yaml"))
