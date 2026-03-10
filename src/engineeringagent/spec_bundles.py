"""Bundled feature package helpers shared by specs and runtime."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

if TYPE_CHECKING:
    from .specs import ValidationIssue


class _SpecContracts:
    """Mutable registry used to avoid a specs/spec_bundles import cycle."""

    planning_tier: Any = None
    feature_plan_artifact: Any = None
    build_validation_issue: Callable[..., "ValidationIssue"] | None = None
    model_contract_issues: (
        Callable[[type[BaseModel], dict[str, Any], Path], list["ValidationIssue"]] | None
    ) = None


_SPEC_CONTRACTS = _SpecContracts()


class FeaturePackagePaths(BaseModel):
    """Resolved active/archive paths for one feature spec entrypoint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    active_root: Path
    active_spec_path: Path
    archive_root: Path
    archive_spec_path: Path


def configure_spec_contracts(
    *,
    planning_tier: Any,
    build_validation_issue: Callable[..., "ValidationIssue"],
    feature_plan_artifact: Any,
    model_contract_issues: Callable[
        [type[BaseModel], dict[str, Any], Path], list["ValidationIssue"]
    ],
) -> None:
    """Register spec-contract types used by bundled helpers."""

    _SPEC_CONTRACTS.planning_tier = planning_tier
    _SPEC_CONTRACTS.build_validation_issue = build_validation_issue
    _SPEC_CONTRACTS.feature_plan_artifact = feature_plan_artifact
    _SPEC_CONTRACTS.model_contract_issues = model_contract_issues


def reset_spec_contracts_for_testing() -> None:
    """Clear configured contract hooks for focused tests."""

    _SPEC_CONTRACTS.planning_tier = None
    _SPEC_CONTRACTS.build_validation_issue = None
    _SPEC_CONTRACTS.feature_plan_artifact = None
    _SPEC_CONTRACTS.model_contract_issues = None


def _require_spec_contract(name: str, value: Any) -> Any:
    """Return a configured contract object or raise a deterministic error."""

    if value is None:
        _bootstrap_spec_contracts()
        value = getattr(_SPEC_CONTRACTS, name, None)
    if value is None:
        raise RuntimeError(f"bundled spec contract not configured: {name}")
    return value


def _bootstrap_spec_contracts() -> None:
    """Import the spec contract module on demand when helpers run standalone."""

    if (
        _SPEC_CONTRACTS.planning_tier is not None
        and _SPEC_CONTRACTS.feature_plan_artifact is not None
        and _SPEC_CONTRACTS.build_validation_issue is not None
        and _SPEC_CONTRACTS.model_contract_issues is not None
    ):
        return
    specs_module = import_module("engineeringagent.specs")
    model_contract_issues = getattr(specs_module, "model_contract_issues", None)
    if model_contract_issues is None:
        model_contract_issues = getattr(specs_module, "_model_contract_issues", None)
    build_validation_issue = getattr(specs_module, "build_validation_issue", None)
    if build_validation_issue is None and hasattr(specs_module, "ValidationIssue"):
        build_validation_issue = specs_module.ValidationIssue
    if (
        _SPEC_CONTRACTS.planning_tier is None
        and hasattr(specs_module, "PlanningTier")
        and hasattr(specs_module, "FeaturePlanArtifact")
        and build_validation_issue is not None
        and model_contract_issues is not None
    ):
        configure_spec_contracts(
            planning_tier=specs_module.PlanningTier,
            build_validation_issue=build_validation_issue,
            feature_plan_artifact=specs_module.FeaturePlanArtifact,
            model_contract_issues=model_contract_issues,
        )


def bootstrap_spec_contracts() -> None:
    """Expose contract bootstrap for focused tests and standalone callers."""

    _bootstrap_spec_contracts()


def _validation_issue_instance(*, path: str, message: str) -> "ValidationIssue":
    """Create a configured ValidationIssue instance."""

    build_issue = _require_spec_contract(
        "build_validation_issue", _SPEC_CONTRACTS.build_validation_issue
    )
    return build_issue(path=path, message=message)


def model_contract_issues_for_bundle(
    *,
    model_type: type[BaseModel],
    payload: dict[str, Any],
    file_path: Path,
) -> list["ValidationIssue"]:
    """Call the configured model-contract validation helper."""

    issue_fn = _require_spec_contract(
        "model_contract_issues", _SPEC_CONTRACTS.model_contract_issues
    )
    return issue_fn(model_type, payload, file_path)


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML mapping from disk."""

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping at top level")
    return data


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write a YAML mapping to disk."""

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=False)


def iter_feature_files(features_dir: Path) -> list[Path]:
    """Return sorted feature spec files from a directory."""

    if not features_dir.exists():
        return []

    return [
        child / "spec.yaml"
        for child in sorted(features_dir.iterdir())
        if child.is_dir() and (child / "spec.yaml").is_file()
    ]


def feature_storage_root(feature_path: Path) -> Path:
    """Return the file-or-directory root moved for a feature entrypoint."""

    if not is_bundled_feature_spec_path(feature_path):
        raise ValueError("feature entrypoints must use bundled spec.yaml paths")
    return feature_path.parent


def resolve_feature_package_paths(
    active_dir: Path,
    done_dir: Path,
    feature_path: Path,
) -> FeaturePackagePaths:
    """Resolve active/archive roots for a bundled feature entrypoint."""

    active_spec_path = feature_path.resolve()
    active_root = feature_storage_root(active_spec_path)
    if active_root.parent != active_dir:
        raise ValueError(
            "completed feature archive source must be under docs/spec/features"
        )

    archive_root = done_dir / active_root.name
    archive_spec_path = archive_root / active_spec_path.name

    return FeaturePackagePaths(
        active_root=active_root,
        active_spec_path=active_spec_path,
        archive_root=archive_root,
        archive_spec_path=archive_spec_path,
    )


def is_bundled_feature_spec_path(file_path: Path) -> bool:
    """Return whether the path is a bundled package spec entrypoint."""

    return file_path.name == "spec.yaml"


def bundled_feature_artifact_issues(
    feature: dict[str, Any],
    file_path: Path,
) -> list["ValidationIssue"]:
    """Validate tier-specific artifact requirements for bundled feature specs."""

    planning_tier_enum = _require_spec_contract(
        "planning_tier", _SPEC_CONTRACTS.planning_tier
    )
    issues: list["ValidationIssue"] = []
    planning_tier = feature.get("planning_tier")
    artifacts = feature.get("artifacts")
    if not isinstance(planning_tier, str) or not isinstance(artifacts, dict):
        return issues

    required_artifacts = {
        planning_tier_enum.DIRECT.value: (),
        planning_tier_enum.PLANNED.value: ("plan",),
        planning_tier_enum.RESEARCHED.value: ("plan", "research"),
    }.get(planning_tier, ())

    for artifact_key in required_artifacts:
        artifact_value = artifacts.get(artifact_key)
        if not isinstance(artifact_value, str) or not artifact_value.strip():
            issues.append(
                _validation_issue_instance(
                    path=f"{file_path}:artifacts.{artifact_key}",
                    message=(
                        f"planning_tier {planning_tier} requires artifacts.{artifact_key}"
                    ),
                )
            )
            continue
        artifact_path = file_path.parent / artifact_value
        if not artifact_path.is_file():
            issues.append(
                _validation_issue_instance(
                    path=f"{file_path}:artifacts.{artifact_key}",
                    message=f"artifact path does not exist: {artifact_value}",
                )
            )

    plan_ref = artifacts.get("plan")
    if isinstance(plan_ref, str) and plan_ref.strip():
        issues.extend(plan_artifact_issues(file_path, feature, plan_ref))

    return issues


def plan_artifact_issues(
    spec_path: Path,
    feature: dict[str, Any],
    plan_ref: str,
) -> list["ValidationIssue"]:
    """Validate bundled plan.md frontmatter and spec linkage."""

    feature_plan_artifact = _require_spec_contract(
        "feature_plan_artifact", _SPEC_CONTRACTS.feature_plan_artifact
    )
    plan_path = spec_path.parent / plan_ref
    if not plan_path.is_file():
        return []

    try:
        frontmatter = load_markdown_frontmatter(plan_path)
    except ValueError as exc:
        return [_validation_issue_instance(path=str(plan_path), message=str(exc))]

    issues = model_contract_issues_for_bundle(
        model_type=feature_plan_artifact,
        payload=frontmatter,
        file_path=plan_path,
    )
    if issues:
        return issues

    feature_id = feature.get("id")
    if frontmatter.get("feature_id") != feature_id:
        issues.append(
            _validation_issue_instance(
                path=f"{plan_path}:feature_id",
                message=f"plan feature_id must match spec id {feature_id}",
            )
        )
    planning_tier = feature.get("planning_tier")
    if frontmatter.get("planning_tier") != planning_tier:
        issues.append(
            _validation_issue_instance(
                path=f"{plan_path}:planning_tier",
                message=f"plan planning_tier must match spec planning_tier {planning_tier}",
            )
        )
    if frontmatter.get("source_spec") != spec_path.name:
        issues.append(
            _validation_issue_instance(
                path=f"{plan_path}:source_spec",
                message=f"plan source_spec must reference {spec_path.name}",
            )
        )
    issues.extend(
        _plan_phase_status_alignment_issues(
            spec_path=spec_path,
            feature=feature,
            plan_path=plan_path,
            frontmatter=frontmatter,
        )
    )
    return issues


def _plan_phase_status_alignment_issues(
    *,
    spec_path: Path,
    feature: dict[str, Any],
    plan_path: Path,
    frontmatter: dict[str, Any],
) -> list["ValidationIssue"]:
    """Validate feature/plan progress alignment for bundled plan phases."""

    feature_status = feature.get("status")
    raw_phases = frontmatter.get("phases")
    if not isinstance(feature_status, str) or not isinstance(raw_phases, list):
        return []

    phase_statuses = [
        phase.get("status")
        for phase in raw_phases
        if isinstance(phase, dict) and isinstance(phase.get("status"), str)
    ]
    issues: list["ValidationIssue"] = []

    if any(status == "in_progress" for status in phase_statuses) and (
        feature_status != "in_progress"
    ):
        issues.append(
            _validation_issue_instance(
                path=f"{spec_path}:status",
                message="feature with in_progress phase must be in_progress",
            )
        )

    if any(status == "blocked" for status in phase_statuses) and (
        feature_status != "blocked"
    ):
        issues.append(
            _validation_issue_instance(
                path=f"{spec_path}:status",
                message="feature with blocked phase must be blocked",
            )
        )

    if feature_status == "done" and phase_statuses and any(
        status != "done" for status in phase_statuses
    ):
        issues.append(
            _validation_issue_instance(
                path=f"{plan_path}:phases",
                message="feature status done requires all plan phases done",
            )
        )

    return issues


def load_markdown_frontmatter(path: Path) -> dict[str, Any]:
    """Load a markdown document's YAML frontmatter mapping from disk."""

    document = path.read_text(encoding="utf-8")
    if not document.startswith("---\n"):
        raise ValueError("markdown frontmatter must start with '---'")

    frontmatter_end = document.find("\n---", 4)
    if frontmatter_end < 0:
        raise ValueError("markdown frontmatter is missing closing delimiter")

    frontmatter_block = document[4:frontmatter_end].strip()
    if not frontmatter_block:
        raise ValueError("markdown frontmatter block is empty")

    parsed = yaml.safe_load(frontmatter_block)
    if not isinstance(parsed, dict):
        raise ValueError("markdown frontmatter must be a mapping")
    return parsed


def resolve_feature_plan_path(
    spec_path: Path,
    feature: dict[str, Any] | None,
) -> Path | None:
    """Return the bundled plan.md path referenced by a feature spec, if any."""

    if feature is None or not is_bundled_feature_spec_path(spec_path):
        return None
    artifacts = feature.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    plan_ref = artifacts.get("plan")
    if not isinstance(plan_ref, str) or not plan_ref.strip():
        return None
    return spec_path.parent / plan_ref.strip()


def resolve_feature_research_path(
    spec_path: Path,
    feature: dict[str, Any] | None,
) -> Path | None:
    """Return the bundled research.md path referenced by a feature spec, if any."""

    if feature is None or not is_bundled_feature_spec_path(spec_path):
        return None
    artifacts = feature.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    research_ref = artifacts.get("research")
    if not isinstance(research_ref, str) or not research_ref.strip():
        return None
    return spec_path.parent / research_ref.strip()


def load_feature_plan_artifact(
    spec_path: Path,
    feature: dict[str, Any] | None,
):
    """Load bundled plan.md frontmatter as a validated plan artifact."""

    feature_plan_artifact = _require_spec_contract(
        "feature_plan_artifact", _SPEC_CONTRACTS.feature_plan_artifact
    )
    plan_path = resolve_feature_plan_path(spec_path, feature)
    if plan_path is None or not plan_path.is_file():
        return None
    try:
        frontmatter = load_markdown_frontmatter(plan_path)
        return feature_plan_artifact.model_validate(frontmatter)
    except (ValidationError, ValueError, yaml.YAMLError):
        return None


def feature_progress_kind(
    spec_path: Path,
    feature: dict[str, Any] | None,
) -> str:
    """Return the progress surface kind used for a feature."""

    if resolve_feature_plan_path(spec_path, feature) is not None:
        return "phase"
    return "feature"


def progress_kind_label(progress_kind: str | None) -> str:
    """Normalize a progress kind to the user-facing label."""

    if progress_kind == "phase":
        return "phase"
    return "implementation step"
