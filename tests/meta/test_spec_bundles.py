from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from pydantic import BaseModel

from engineeringagent import spec_bundles


def _write_bundled_feature(feature_root: Path) -> tuple[Path, dict[str, object]]:
    spec_path = feature_root / "spec.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "id": "FEAT-181",
        "title": "Bundled feature",
        "type": "spec",
        "expected_commit_subject": "spec: bundled feature contract",
        "planning_tier": "planned",
        "status": "backlog",
        "priority": "high",
        "objective": "Validate bundled feature packages.",
        "acceptance": ["Validator enforces bundled feature contracts."],
        "artifacts": {"plan": "plan.md"},
    }
    spec_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    (feature_root / "plan.md").write_text(
        "---\n"
        "plan_id: FEAT-181\n"
        "feature_id: FEAT-181\n"
        "status: backlog\n"
        "source_spec: spec.yaml\n"
        "planning_tier: planned\n"
        "phases:\n"
        "  - id: P1\n"
        "    title: First phase\n"
        "    status: pending\n"
        "    verification:\n"
        "      - uv run pytest -q\n"
        "---\n"
        "# Plan\n",
        encoding="utf-8",
    )
    return spec_path, payload


def test_bundled_only_feature_progress_kind_tracks_plan_artifacts(
    tmp_path: Path,
) -> None:
    bundled_spec_path, bundled_feature_payload = _write_bundled_feature(
        tmp_path / "docs" / "spec" / "features" / "FEAT-181-bundled-feature-contract"
    )

    assert (
        spec_bundles.feature_progress_kind(bundled_spec_path, bundled_feature_payload)
        == "phase"
    )


def test_bundled_only_feature_progress_kind_uses_feature_surface_for_direct_bundles(
    tmp_path: Path,
) -> None:
    feature_root = tmp_path / "docs" / "spec" / "features" / "FEAT-182-direct-bundle"
    spec_path = feature_root / "spec.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "id": "FEAT-182",
        "title": "Direct bundled feature",
        "type": "spec",
        "expected_commit_subject": "spec: direct bundled feature contract",
        "planning_tier": "direct",
        "status": "backlog",
        "priority": "high",
        "objective": "Validate bundled direct feature progress wording.",
        "acceptance": ["Bundled direct features do not fall back to subtasks."],
        "artifacts": {},
    }
    spec_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    assert spec_bundles.feature_progress_kind(spec_path, payload) == "feature"


def test_plan_artifact_issues_validate_plan_linkage_via_shared_module_import(
    tmp_path: Path,
) -> None:
    spec_path, feature_payload = _write_bundled_feature(
        tmp_path / "docs" / "spec" / "features" / "FEAT-181-bundled-feature-contract"
    )

    issues = spec_bundles.plan_artifact_issues(spec_path, feature_payload, "plan.md")

    assert issues == []


def test_plan_artifact_issues_bootstraps_spec_contracts_when_registry_is_empty(
    tmp_path: Path,
) -> None:
    spec_path, feature_payload = _write_bundled_feature(
        tmp_path / "docs" / "spec" / "features" / "FEAT-181-bundled-feature-contract"
    )

    spec_bundles.reset_spec_contracts_for_testing()

    issues = spec_bundles.plan_artifact_issues(spec_path, feature_payload, "plan.md")

    assert issues == []


def test_bootstrap_spec_contracts_accepts_public_model_contract_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class DummyModel(BaseModel):
        pass

    def build_issue(path: str, message: str) -> object:
        return SimpleNamespace(path=path, message=message)

    def model_contract_issues(
        model_type: object,
        payload: dict[str, object],
        file_path: Path,
    ) -> list[object]:
        captured["call"] = {
            "model_type": model_type,
            "payload": payload,
            "file_path": file_path,
        }
        return []

    stub_specs_module = SimpleNamespace(
        PlanningTier=object(),
        ValidationIssue=object(),
        FeaturePlanArtifact=object(),
        build_validation_issue=build_issue,
        model_contract_issues=model_contract_issues,
    )

    def import_specs_module(_name: str) -> SimpleNamespace:
        return stub_specs_module

    spec_bundles.reset_spec_contracts_for_testing()
    monkeypatch.setattr(spec_bundles, "import_module", import_specs_module)

    try:
        spec_bundles.bootstrap_spec_contracts()
        issues = spec_bundles.model_contract_issues_for_bundle(
            model_type=DummyModel,
            payload={"id": "FEAT-181"},
            file_path=Path("docs/spec/features/FEAT-181-example/spec.yaml"),
        )

        assert issues == []
        assert captured["call"] == {
            "model_type": DummyModel,
            "payload": {"id": "FEAT-181"},
            "file_path": Path("docs/spec/features/FEAT-181-example/spec.yaml"),
        }
    finally:
        monkeypatch.undo()
        spec_bundles.reset_spec_contracts_for_testing()
        spec_bundles.bootstrap_spec_contracts()


def test_bundled_only_iter_feature_files_returns_only_bundled_specs(
    tmp_path: Path,
) -> None:
    features_dir = tmp_path / "docs" / "spec" / "features"
    bundled_spec_path, _payload = _write_bundled_feature(
        features_dir / "FEAT-181-example"
    )
    (features_dir / "FEAT-181-example.yaml").write_text(
        "id: FEAT-181\n",
        encoding="utf-8",
    )

    assert spec_bundles.iter_feature_files(features_dir) == [bundled_spec_path]


def test_bundled_only_feature_storage_root_rejects_flat_entrypoints() -> None:
    with pytest.raises(ValueError, match="bundled spec.yaml"):
        spec_bundles.feature_storage_root(
            Path("docs/spec/features/FEAT-181-example.yaml")
        )


def test_resolve_feature_package_paths_reports_configured_active_root(
    tmp_path: Path,
) -> None:
    active_dir = tmp_path / "docs" / "specifications" / "features"
    done_dir = tmp_path / "docs" / "specifications" / "features_done"
    outside_spec = tmp_path / "elsewhere" / "FEAT-181-example" / "spec.yaml"
    outside_spec.parent.mkdir(parents=True)
    outside_spec.write_text("id: FEAT-181\n", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match=(
            "completed feature archive source must be under "
            f"{active_dir.as_posix()}"
        ),
    ):
        spec_bundles.resolve_feature_package_paths(active_dir, done_dir, outside_spec)
