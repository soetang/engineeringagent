"""Specification-domain helpers."""

from engineeringagent.domain.shared import FeatureStatus, PlanningTier
from .bundles import (
    FeaturePackagePaths,
    dump_yaml,
    feature_contract_issues,
    feature_progress_kind,
    feature_storage_root,
    iter_feature_files,
    load_feature_plan_artifact,
    load_markdown_frontmatter,
    load_yaml,
    progress_kind_label,
    resolve_feature_package_paths,
    resolve_feature_plan_path,
    resolve_feature_research_path,
)
from .contracts import (
    BundledFeatureSpec,
    FeaturePlanArtifact,
    PlanPhaseArtifact,
    PotentialFeatureSpec,
    PotentialFeaturesDocument,
    ValidationIssue,
    checks_contract_issues,
    checks_schema_from_model,
    feature_model_contract_issues,
    feature_schema_from_model,
    feature_sort_key,
    model_contract_issues,
    potential_features_contract_issues,
)

from .commit_policy import feature_completion_commit_subject
from .feature_specification import (
    FeatureArtifacts,
    FeaturePriority,
    FeatureSelectionCandidate,
    FeatureSpecification,
    FeatureType,
)
from .feature_state_outcomes import (
    InitialFeatureLoadOutcome,
    PostImplementFeatureOutcome,
)

from .progress import (
    ProgressUnit,
    current_progress_unit,
    done_transition_verification_commands,
    feature_progress_reference,
    iter_progress_units,
    progress_status_snapshot,
)
from .selection import deterministic_feature_choice, parse_selector_output

__all__ = [
    "BundledFeatureSpec",
    "FeaturePackagePaths",
    "FeatureArtifacts",
    "FeaturePlanArtifact",
    "FeaturePriority",
    "FeatureSelectionCandidate",
    "FeatureSpecification",
    "FeatureStatus",
    "InitialFeatureLoadOutcome",
    "FeatureType",
    "PlanningTier",
    "PlanPhaseArtifact",
    "PostImplementFeatureOutcome",
    "PotentialFeatureSpec",
    "PotentialFeaturesDocument",
    "ProgressUnit",
    "ValidationIssue",
    "checks_contract_issues",
    "checks_schema_from_model",
    "current_progress_unit",
    "dump_yaml",
    "done_transition_verification_commands",
    "feature_contract_issues",
    "feature_model_contract_issues",
    "feature_progress_reference",
    "feature_completion_commit_subject",
    "feature_progress_kind",
    "feature_schema_from_model",
    "feature_sort_key",
    "feature_storage_root",
    "iter_progress_units",
    "iter_feature_files",
    "load_feature_plan_artifact",
    "load_markdown_frontmatter",
    "load_yaml",
    "model_contract_issues",
    "deterministic_feature_choice",
    "parse_selector_output",
    "potential_features_contract_issues",
    "progress_kind_label",
    "progress_status_snapshot",
    "resolve_feature_package_paths",
    "resolve_feature_plan_path",
    "resolve_feature_research_path",
]
