from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Annotated, Literal, cast

from typing_extensions import LiteralString
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    model_validator,
)
from pydantic_core import InitErrorDetails, PydanticCustomError

from engineeringagent.checks import HarnessCheckPhase
from engineeringagent.json_schema import JSON_SCHEMA_DRAFT_URL
from engineeringagent import spec_bundles as _spec_bundles

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
ERR_DUP_SUBTASK_ID: LiteralString = "duplicate subtask id: {subtask_id}"
FeaturePackagePaths = _spec_bundles.FeaturePackagePaths
load_yaml = _spec_bundles.load_yaml
dump_yaml = _spec_bundles.dump_yaml
iter_feature_files = _spec_bundles.iter_feature_files
feature_storage_root = _spec_bundles.feature_storage_root
resolve_feature_package_paths = _spec_bundles.resolve_feature_package_paths
load_markdown_frontmatter = _spec_bundles.load_markdown_frontmatter
resolve_feature_plan_path = _spec_bundles.resolve_feature_plan_path
resolve_feature_research_path = _spec_bundles.resolve_feature_research_path
load_feature_plan_artifact = _spec_bundles.load_feature_plan_artifact
feature_progress_kind = _spec_bundles.feature_progress_kind
progress_kind_label = _spec_bundles.progress_kind_label
resolve_compatibility_wrapper_canonical_spec_path = (
    _spec_bundles.resolve_compatibility_wrapper_canonical_spec_path
)
compatibility_wrapper_plan_mirror_issues = (
    _spec_bundles.compatibility_wrapper_plan_mirror_issues
)
_is_bundled_feature_spec_path = _spec_bundles.is_bundled_feature_spec_path
_bundled_feature_artifact_issues = _spec_bundles.bundled_feature_artifact_issues


FeatureId = Annotated[
    str, Field(strict=True, min_length=1, pattern=r"^FEAT-[0-9]{3,}$")
]
SubtaskId = Annotated[str, Field(strict=True, min_length=1, pattern=r"^ST-[0-9]{3,}$")]
NonEmptyStr = Annotated[str, Field(strict=True, min_length=1)]
StrictString = Annotated[str, Field(strict=True)]
CommitSubject = Annotated[
    str,
    Field(
        strict=True,
        pattern=r"^(feat|fix|spec|docs|chore|test): [^\n]+$",
    ),
]


class StrictContractModel(BaseModel):
    """Pydantic base model that forbids unknown fields."""

    model_config = ConfigDict(extra="forbid")


class FeatureStatus(str, Enum):
    """Lifecycle status for a feature spec."""

    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class FeaturePriority(str, Enum):
    """Priority bucket used for feature ordering."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FeatureType(str, Enum):
    """Category of work captured by a feature spec."""

    FEATURE = "feature"
    BUG = "bug"
    SPEC = "spec"
    DOCS = "docs"
    CHORE = "chore"
    TEST = "test"


class PotentialFeatureStatus(str, Enum):
    """Lifecycle status for a potential feature entry."""

    IDEA = "idea"


PotentialFeatureId = Annotated[
    str, Field(strict=True, min_length=1, pattern=r"^POT-[0-9]{3,}$")
]


class PlanningTier(str, Enum):
    """Explicit planning depth for bundled feature packages."""

    DIRECT = "direct"
    PLANNED = "planned"
    RESEARCHED = "researched"


class PotentialFeatureSpec(StrictContractModel):
    """One entry in the potential features backlog document."""

    id: PotentialFeatureId
    title: NonEmptyStr
    status: PotentialFeatureStatus
    context: StrictString | None = None
    value: list[StrictString] | None = None
    acceptance_hint: list[StrictString] | None = None


class PotentialFeaturesDocument(StrictContractModel):
    """Top-level schema for docs/spec/potential_features.yaml."""

    version: Annotated[int, Field(strict=True, ge=1)]
    description: StrictString | None = None
    potential_features: list[PotentialFeatureSpec] = Field(default_factory=list)


class ReviewerSandboxMode(str, Enum):
    """Sandbox strategy for running reviewer agents."""

    TEMP_WORKTREE_SNAPSHOT = "temp_worktree_snapshot"
    EMPTY_FOLDER = "empty_folder"


class ReviewerApprovalDefinition(StrictContractModel):
    """Approval policy for reviewer results."""

    first_feature_approval: bool = True


class ReviewerSandboxDefinition(StrictContractModel):
    """Configuration for reviewer sandbox behavior."""

    mode: ReviewerSandboxMode
    assets: Annotated[list[NonEmptyStr], Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def enforce_assets_support(self) -> "ReviewerSandboxDefinition":
        """Validate that sandbox.assets is only used with empty_folder."""
        if self.assets is None:
            return self
        if self.mode != ReviewerSandboxMode.EMPTY_FOLDER:
            raise ValueError(
                "sandbox.assets is only supported for sandbox.mode=empty_folder"
            )
        return self


def _validate_prompt_file_location(prompt_file: str) -> None:
    """Ensure prompt_file points under harness/reviewers/prompts/."""
    prompt_path = Path(prompt_file)
    normalized_parts = [part for part in prompt_path.parts if part not in {"", "."}]
    if prompt_path.is_absolute() or any(part == ".." for part in prompt_path.parts):
        raise ValueError(
            "prompt_file must be a repo-relative path under harness/reviewers/prompts/"
        )
    if normalized_parts[:3] != ["harness", "reviewers", "prompts"]:
        raise ValueError(
            "prompt_file must be a repo-relative path under harness/reviewers/prompts/"
        )
    if len(normalized_parts) <= 3:
        raise ValueError(
            "prompt_file must reference a file under harness/reviewers/prompts/"
        )


class HarnessCheckWhenDefinition(StrictContractModel):
    """Selection predicates that decide when a check runs."""

    phase: HarnessCheckPhase | None = None
    on_change: Annotated[list[NonEmptyStr], Field(min_length=1)] | None = None


class HarnessCheckDefaultsDefinition(StrictContractModel):
    """Defaults applied to checks that omit explicit fields."""

    when: HarnessCheckWhenDefinition | None = None


class HarnessCheckCommandDefinition(StrictContractModel):
    """A plain command-string check executed as argv by the harness."""

    type: Literal["command"]
    command: NonEmptyStr
    when: HarnessCheckWhenDefinition | None = None


class HarnessCheckFitnessDefinition(StrictContractModel):
    """A fitness-function check executed by the harness."""

    type: Literal["fitness"]
    when: HarnessCheckWhenDefinition | None = None
    scope: Literal["all"] | None = None
    rule_ids: Annotated[list[NonEmptyStr], Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def enforce_fitness_selection(self) -> "HarnessCheckFitnessDefinition":
        """Ensure exactly one of scope or rule_ids selects fitness rules."""
        has_scope = self.scope is not None
        has_rule_ids = self.rule_ids is not None
        if has_scope == has_rule_ids:
            error = PydanticCustomError(
                "value_error",
                "define exactly one of scope: all or rule_ids",
            )
            errors = [
                _init_error_detail(error=error, loc=("scope",), input_value=self.scope),
                _init_error_detail(
                    error=error, loc=("rule_ids",), input_value=self.rule_ids
                ),
            ]
            raise ValidationError.from_exception_data(self.__class__.__name__, errors)
        return self


class HarnessCheckReviewerDefinition(StrictContractModel):
    """A reviewer (LLM) check executed by the harness."""

    type: Literal["reviewer"]
    prompt_file: NonEmptyStr
    feedback_context: StrictString | None = None
    when: HarnessCheckWhenDefinition | None = None
    sandbox: ReviewerSandboxDefinition | None = None
    approval: ReviewerApprovalDefinition = Field(
        default_factory=ReviewerApprovalDefinition
    )

    @model_validator(mode="after")
    def enforce_prompt_file_location(self) -> "HarnessCheckReviewerDefinition":
        """Ensure prompt_file points under harness/reviewers/prompts/."""
        _validate_prompt_file_location(self.prompt_file)
        return self


HarnessCheckDefinition = Annotated[
    HarnessCheckCommandDefinition
    | HarnessCheckFitnessDefinition
    | HarnessCheckReviewerDefinition,
    Field(discriminator="type"),
]


class HarnessChecksDocument(StrictContractModel):
    """Top-level schema for harness/checks.yaml."""

    contract_version: Literal["1.0"]
    defaults: HarnessCheckDefaultsDefinition | None = None
    checks: dict[NonEmptyStr, HarnessCheckDefinition]

    @model_validator(mode="after")
    def enforce_reviewer_phase_restrictions(self) -> "HarnessChecksDocument":
        """Reject reviewer checks scheduled for iteration_end."""
        default_phase = _effective_default_check_phase(self.defaults)
        errors: list[InitErrorDetails] = []
        for check_id, check in self.checks.items():
            if not isinstance(check, HarnessCheckReviewerDefinition):
                continue
            phase = _effective_check_phase(check.when, default_phase)
            if phase == HarnessCheckPhase.ITERATION_END:
                errors.append(
                    _init_error_detail(
                        error=PydanticCustomError(
                            "value_error",
                            "reviewer checks must set when.phase to feature_done or manual",
                        ),
                        loc=("checks", check_id, "when", "phase"),
                        input_value=phase,
                    )
                )
        if errors:
            raise ValidationError.from_exception_data(self.__class__.__name__, errors)
        return self


def _effective_default_check_phase(
    defaults: HarnessCheckDefaultsDefinition | None,
) -> HarnessCheckPhase:
    """Return the effective default phase for checks."""
    if defaults is None or defaults.when is None or defaults.when.phase is None:
        return HarnessCheckPhase.ITERATION_END
    return defaults.when.phase


def _effective_check_phase(
    when: HarnessCheckWhenDefinition | None,
    default_phase: HarnessCheckPhase,
) -> HarnessCheckPhase:
    """Return the effective phase for a single check."""
    if when is None or when.phase is None:
        return default_phase
    return when.phase


class SubtaskSpec(StrictContractModel):
    """Schema for a single subtask within a feature spec."""

    id: SubtaskId
    title: NonEmptyStr
    status: FeatureStatus
    context: StrictString | None = None
    constraints: list[StrictString] | None = None
    verification: Annotated[list[StrictString], Field(min_length=1)]
    attempts: Annotated[int, Field(strict=True, ge=0)] | None = None
    last_error: StrictString | None = None
    notes: list[StrictString] | None = None


class FeatureSpec(StrictContractModel):
    """Top-level schema for docs/spec/features/*.yaml."""

    model_config = ConfigDict(extra="forbid", title="Agent Harness Feature")

    id: FeatureId
    title: NonEmptyStr
    type: FeatureType
    expected_commit_subject: CommitSubject
    status: FeatureStatus
    priority: FeaturePriority
    objective: NonEmptyStr
    context: StrictString | None = None
    constraints: list[StrictString] | None = None
    implementation_notes: StrictString | None = None
    acceptance: Annotated[list[StrictString], Field(min_length=1)]
    subtasks: list[SubtaskSpec] = Field(default_factory=list)
    updated_at: StrictString | None = None

    @model_validator(mode="after")
    def enforce_invariants(self) -> FeatureSpec:
        """Apply repository feature invariants in the model layer."""
        errors, in_progress_count, done_count = _collect_subtask_state(self.subtasks)
        errors.extend(
            _feature_status_alignment_errors(
                self.status,
                len(self.subtasks),
                in_progress_count,
                done_count,
            )
        )

        if errors:
            raise ValidationError.from_exception_data(self.__class__.__name__, errors)

        return self


class FeatureArtifacts(StrictContractModel):
    """Deterministic artifact references for bundled feature packages."""

    plan: StrictString | None = None
    research: StrictString | None = None
    supporting: list[StrictString] | None = None


class BundledFeatureSpec(StrictContractModel):
    """Top-level schema for bundled docs/spec/features/<feature>/spec.yaml."""

    model_config = ConfigDict(extra="forbid", title="Agent Harness Bundled Feature")

    id: FeatureId
    title: NonEmptyStr
    type: FeatureType
    expected_commit_subject: CommitSubject
    planning_tier: PlanningTier
    status: FeatureStatus
    priority: FeaturePriority
    objective: NonEmptyStr
    context: StrictString | None = None
    constraints: list[StrictString] | None = None
    implementation_notes: StrictString | None = None
    acceptance: Annotated[list[StrictString], Field(min_length=1)]
    artifacts: FeatureArtifacts
    updated_at: StrictString | None = None


class PlanPhaseArtifact(StrictContractModel):
    """Structured plan phase metadata stored in plan.md frontmatter."""

    id: NonEmptyStr
    title: NonEmptyStr
    status: StrictString
    verification: list[StrictString] | None = None


class FeaturePlanArtifact(StrictContractModel):
    """Required plan.md frontmatter for bundled planned/researched features."""

    plan_id: NonEmptyStr
    feature_id: FeatureId
    status: StrictString
    source_spec: StrictString
    source_research: StrictString | None = None
    planning_tier: PlanningTier
    phases: Annotated[list[PlanPhaseArtifact], Field(min_length=1)]


FeatureSpecContract = FeatureSpec | BundledFeatureSpec


def _collect_subtask_state(
    subtasks: list[SubtaskSpec],
) -> tuple[
    list[InitErrorDetails],
    int,
    int,
]:
    errors: list[InitErrorDetails] = []
    subtask_ids: set[str] = set()
    in_progress_count = 0
    done_count = 0

    for idx, subtask in enumerate(subtasks):
        if subtask.id in subtask_ids:
            errors.append(
                _init_error_detail(
                    error=PydanticCustomError(
                        "value_error",
                        ERR_DUP_SUBTASK_ID,
                        {"subtask_id": subtask.id},
                    ),
                    loc=("subtasks", idx, "id"),
                    input_value=subtask.id,
                )
            )
        subtask_ids.add(subtask.id)

        if subtask.status == FeatureStatus.IN_PROGRESS:
            in_progress_count += 1
        if subtask.status == FeatureStatus.DONE:
            done_count += 1

    return (
        errors,
        in_progress_count,
        done_count,
    )


def _feature_status_alignment_errors(
    feature_status: FeatureStatus,
    subtask_count: int,
    in_progress_count: int,
    done_count: int,
) -> list[InitErrorDetails]:
    errors: list[InitErrorDetails] = []
    has_subtasks = subtask_count > 0
    all_done = has_subtasks and done_count == subtask_count
    any_in_progress = in_progress_count > 0

    if feature_status == FeatureStatus.DONE and has_subtasks and not all_done:
        errors.append(
            _init_error_detail(
                error=PydanticCustomError(
                    "value_error", "feature status done requires all subtasks done"
                ),
                loc=("status",),
                input_value=feature_status,
            )
        )

    if any_in_progress and feature_status != FeatureStatus.IN_PROGRESS:
        errors.append(
            _init_error_detail(
                error=PydanticCustomError(
                    "value_error",
                    "feature with in_progress subtask must be in_progress",
                ),
                loc=("status",),
                input_value=feature_status,
            )
        )

    return errors


class ValidationIssue(StrictContractModel):
    """One contract validation issue emitted by strict model checks."""

    path: str
    message: str


def feature_schema_from_model() -> dict[str, Any]:
    """Return feature schema generated from the Pydantic feature model."""
    flat_schema = FeatureSpec.model_json_schema(mode="validation")
    bundled_schema = BundledFeatureSpec.model_json_schema(mode="validation")
    schema = TypeAdapter(FeatureSpecContract).json_schema(mode="validation")
    merged_properties = dict(flat_schema["properties"])
    for name, definition in bundled_schema["properties"].items():
        merged_properties.setdefault(name, definition)
    bundled_required = set(bundled_schema.get("required", []))
    schema["type"] = "object"
    schema["properties"] = merged_properties
    schema["required"] = [
        name for name in flat_schema.get("required", []) if name in bundled_required
    ]
    schema["$schema"] = JSON_SCHEMA_DRAFT_URL
    return schema


def checks_schema_from_model() -> dict[str, Any]:
    """Return harness checks schema generated from the Pydantic checks model."""
    schema = HarnessChecksDocument.model_json_schema(mode="validation")
    schema["$schema"] = JSON_SCHEMA_DRAFT_URL
    return schema


def _path_from_pydantic_loc(loc: tuple[Any, ...]) -> str:
    """Convert a Pydantic error location tuple into a dotted path."""
    parts: list[str] = []
    for segment in loc:
        if isinstance(segment, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{segment}]"
            else:
                parts.append(f"[{segment}]")
            continue
        parts.append(str(segment))
    if not parts:
        return "<root>"
    return ".".join(parts).replace(".[", "[")


def _init_error_detail(
    *,
    error: PydanticCustomError,
    loc: tuple[Any, ...],
    input_value: Any,
) -> InitErrorDetails:
    """Build an InitErrorDetails mapping for ValidationError construction."""
    return cast(
        InitErrorDetails,
        {
            "type": error,
            "loc": loc,
            "input": input_value,
        },
    )


def feature_contract_issues(
    feature: dict[str, Any], file_path: Path
) -> list[ValidationIssue]:
    """Collect strict contract validation issues for one feature document.

    Args:
        feature: Feature mapping to validate.
        file_path: Source path used in issue reporting.

    Returns:
        Validation issues produced by strict Pydantic contract checks.
    """
    model_type: type[BaseModel]
    if _is_bundled_feature_spec_path(file_path):
        model_type = BundledFeatureSpec
    else:
        model_type = FeatureSpec

    issues = _model_contract_issues(
        model_type=model_type,
        payload=feature,
        file_path=file_path,
    )
    if issues or not _is_bundled_feature_spec_path(file_path):
        return issues
    return [*issues, *_bundled_feature_artifact_issues(feature, file_path)]


def potential_features_contract_issues(
    document: dict[str, Any], file_path: Path
) -> list[ValidationIssue]:
    """Collect strict contract issues for potential features backlog YAML."""
    return _model_contract_issues(
        model_type=PotentialFeaturesDocument,
        payload=document,
        file_path=file_path,
    )


def checks_contract_issues(
    document: dict[str, Any], file_path: Path
) -> list[ValidationIssue]:
    """Collect strict contract issues for harness/checks.yaml."""
    return _model_contract_issues(
        model_type=HarnessChecksDocument,
        payload=document,
        file_path=file_path,
    )


def _model_contract_issues(
    model_type: type[BaseModel],
    payload: dict[str, Any],
    file_path: Path,
) -> list[ValidationIssue]:
    """Collect deterministic issues produced by strict model validation."""
    try:
        model_type.model_validate(payload)
    except ValidationError as exc:
        issues: list[ValidationIssue] = []
        errors = sorted(
            exc.errors(include_url=False),
            key=lambda err: _path_from_pydantic_loc(tuple(err.get("loc", ()))),
        )
        for error in errors:
            path = _path_from_pydantic_loc(tuple(error.get("loc", ())))
            issues.append(
                ValidationIssue(
                    path=f"{file_path}:{path}",
                    message=str(error.get("msg", "invalid value")),
                )
            )
        return issues
    return []


_spec_bundles.configure_spec_contracts(
    planning_tier=PlanningTier,
    build_validation_issue=ValidationIssue,
    feature_plan_artifact=FeaturePlanArtifact,
    model_contract_issues=_model_contract_issues,
)


def feature_sort_key(feature: dict[str, Any]) -> tuple[int, str]:
    """Build a deterministic sort key for feature priority.

    Args:
        feature: Feature mapping with priority and id fields.

    Returns:
        Tuple used for ascending priority and id ordering.
    """
    priority = feature.get("priority", "medium")
    return (PRIORITY_ORDER.get(priority, 1), str(feature.get("id", "")))
