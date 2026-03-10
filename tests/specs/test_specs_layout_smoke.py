from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from engineeringagent.specs import (
    compatibility_wrapper_plan_mirror_issues,
    iter_feature_files,
    resolve_compatibility_wrapper_canonical_spec_path,
)


def _has_feature_entrypoints(features_dir: Path) -> bool:
    return bool(iter_feature_files(features_dir))


def _load_markdown_frontmatter(path: Path) -> dict[str, object]:
    document = path.read_text(encoding="utf-8")
    assert document.startswith("---\n"), f"{path} missing frontmatter"
    _prefix, frontmatter, _body = document.split("---\n", 2)
    payload = yaml.safe_load(frontmatter)
    assert isinstance(payload, dict), f"{path} frontmatter must be a mapping"
    return payload


def test_feature_specs_directory_exists(pytestconfig: pytest.Config) -> None:
    repo_root = Path(pytestconfig.rootpath)
    features_dir = repo_root / "docs" / "spec" / "features"
    features_done_dir = repo_root / "docs" / "spec" / "features_done"
    assert features_dir.exists()
    assert _has_feature_entrypoints(features_dir) or _has_feature_entrypoints(
        features_done_dir
    )


def test_bundled_feature_package_counts_as_feature_layout(tmp_path: Path) -> None:
    features_dir = tmp_path / "docs" / "spec" / "features"
    bundled_dir = features_dir / "FEAT-999-example"
    bundled_dir.mkdir(parents=True)
    (bundled_dir / "spec.yaml").write_text("id: FEAT-999\n", encoding="utf-8")

    assert _has_feature_entrypoints(features_dir)


def test_missing_feature_entrypoints_is_detected(tmp_path: Path) -> None:
    features_dir = tmp_path / "docs" / "spec" / "features"
    features_dir.mkdir(parents=True)

    assert not _has_feature_entrypoints(features_dir)


def test_active_bundled_plan_frontmatter_uses_runtime_status_vocabulary(
    repo_root: Path,
) -> None:
    allowed_statuses = {"backlog", "in_progress", "done", "blocked"}
    features_dir = repo_root / "docs" / "spec" / "features"

    for spec_path in sorted(features_dir.glob("*/spec.yaml")):
        payload = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        plan_ref = payload.get("artifacts", {}).get("plan")
        if not isinstance(plan_ref, str):
            continue

        frontmatter = _load_markdown_frontmatter(spec_path.parent / plan_ref)
        status = frontmatter.get("status")
        assert status in allowed_statuses, (
            f"{spec_path.parent.name} plan status must use runtime vocabulary: {status}"
        )

        phases = frontmatter.get("phases")
        assert isinstance(phases, list), f"{spec_path.parent.name} plan phases missing"
        for index, phase in enumerate(phases):
            assert isinstance(phase, dict), (
                f"{spec_path.parent.name} phase {index} must be a mapping"
            )
            phase_status = phase.get("status")
            assert phase_status in allowed_statuses, (
                f"{spec_path.parent.name} phase {index} status must use runtime "
                f"vocabulary: {phase_status}"
            )


def test_flat_compatibility_wrappers_point_to_canonical_bundled_specs(
    repo_root: Path,
) -> None:
    features_dir = repo_root / "docs" / "spec" / "features"

    for wrapper_path in sorted(features_dir.glob("*.yaml")):
        canonical_spec_path = resolve_compatibility_wrapper_canonical_spec_path(
            wrapper_path
        )
        assert canonical_spec_path is not None
        assert canonical_spec_path.is_file(), (
            f"{wrapper_path.name} must pair with canonical bundled spec "
            f"{canonical_spec_path.relative_to(repo_root)}"
        )


def test_flat_compatibility_wrappers_mirror_canonical_plan_phases(
    repo_root: Path,
) -> None:
    features_dir = repo_root / "docs" / "spec" / "features"

    for wrapper_path in sorted(features_dir.glob("*.yaml")):
        payload = yaml.safe_load(wrapper_path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        issues = compatibility_wrapper_plan_mirror_issues(wrapper_path, payload)
        assert issues == []
