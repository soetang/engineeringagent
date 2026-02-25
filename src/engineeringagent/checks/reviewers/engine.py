from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp
from typing import Any, Callable, Iterator, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.agents import (
    AgentBackendError,
    AgentOutputValidationError,
    run_agent,
)
from engineeringagent.progress import paths as progress_paths

from ..on_change_matcher import path_matches_any_glob


FALLBACK_CHANGE_DISCOVERY_REASON = "fallback_run_all_change_discovery_failed"
ALWAYS_RUN_NO_ON_CHANGE_REASON = "always_run_no_on_change"
MATCHED_ON_CHANGE_REASON = "matched_on_change"
NO_ON_CHANGE_MATCH_REASON = "no_on_change_match"
PHASE_MISMATCH_REASON = "phase_mismatch"
FEATURE_DONE_PHASE = "feature_done"
ITERATION_END_PHASE = "iteration_end"
DECISION_APPROVE = "approve"
DECISION_REQUEST_CHANGES = "request_changes"
DECISION_WARNING = "warning"
PARSER_FAILURE_SUMMARY_PREFIX = "reviewer_output_parse_failure"
FIRST_FEATURE_APPROVAL_REUSED_REASON = "first_feature_approval_reused"
FIRST_FEATURE_APPROVAL_NOT_CACHED_REASON = "first_feature_approval_not_cached"
FIRST_FEATURE_APPROVAL_DISABLED_REASON = "first_feature_approval_disabled"
FIRST_FEATURE_APPROVAL_INVALIDATED_REASON = "first_feature_approval_invalidated"
FIRST_FEATURE_APPROVAL_INVALIDATED_RUN_ALL_REASON = (
    "first_feature_approval_invalidated_run_all"
)
REVIEWERS_STATE_VERSION = "1"
BLOCKING_RETRY_COUNT_KEY = "blocking_request_changes_count"
BLOCKING_RETRY_UPDATED_AT_KEY = "blocking_retry_updated_at"
SANDBOX_MODE_TEMP_WORKTREE_SNAPSHOT = "temp_worktree_snapshot"
SANDBOX_MODE_EMPTY_FOLDER = "empty_folder"

REVIEWER_DECISION_PARSE_MAX_RETRIES = 2


class ReviewerDecisionEnvelope(BaseModel):
    """Schema-validated reviewer decision envelope.

    This is the single output object reviewers are instructed to emit. The harness
    uses this model both to derive the JSON Schema contract injected into prompts
    and to validate the extracted decision payload.
    """

    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "request_changes", "warning"]
    summary: str
    required_actions: list[str] = Field(default_factory=list)
    scope_notes: str | None = None

    @field_validator("summary")
    @classmethod
    def _summary_must_be_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("summary must be a non-empty string")
        return stripped


class ReviewerSandboxHandle(BaseModel):
    """Handle for a reviewer sandbox execution root.

    Reviewers may run in a temp worktree snapshot; this model captures where the
    reviewer executed and how to clean up any associated resources.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_root: Path
    cleanup: Callable[[], None]


class ReviewerRunRequest(BaseModel):
    """Inputs required to run a single reviewer deterministically."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    feature_id: str
    feature_path: Path
    changed_paths: ChangedPathsResult
    prior_feedback: str | None
    run_agent_fn: Callable[..., Any] | None = None


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _default_reviewers_state() -> dict[str, Any]:
    return {
        "version": REVIEWERS_STATE_VERSION,
        "features": {},
    }


def load_reviewers_state(project_root: Path) -> dict[str, Any]:
    """Load persisted reviewer state from the progress state file."""

    default = _default_reviewers_state()

    state_path = progress_paths.reviewers_state_path(project_root)
    if not state_path.exists():
        return default

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default

    if not isinstance(payload, dict):
        return default
    features = payload.get("features")
    if not isinstance(features, dict):
        return default
    return {
        "version": str(payload.get("version", REVIEWERS_STATE_VERSION)),
        "features": features,
    }


def save_reviewers_state(project_root: Path, state: dict[str, Any]) -> None:
    """Persist reviewer state under the progress state file."""

    state_path = progress_paths.reviewers_state_path(project_root)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def record_reviewer_approval(
    state: dict[str, Any],
    *,
    feature_id: str,
    reviewer_id: str,
    decision: str,
) -> None:
    """Record first-approval cache metadata for one reviewer decision."""
    features = state.setdefault("features", {})
    feature_state = features.setdefault(feature_id, {})
    reviewers = feature_state.setdefault("reviewers", {})

    if decision == DECISION_APPROVE:
        reviewer_state = reviewers.get(reviewer_id, {})
        if not isinstance(reviewer_state, dict):
            reviewer_state = {}
        reviewer_state["approved"] = True
        reviewer_state["approved_at"] = _now_iso()
        reviewer_state[BLOCKING_RETRY_COUNT_KEY] = 0
        reviewer_state[BLOCKING_RETRY_UPDATED_AT_KEY] = _now_iso()
        reviewers[reviewer_id] = reviewer_state
        return

    reviewer_state = reviewers.get(reviewer_id)
    if isinstance(reviewer_state, dict):
        reviewer_state["approved"] = False
        reviewer_state["updated_at"] = _now_iso()


def increment_blocking_reviewer_retry_count(
    state: dict[str, Any], *, feature_id: str, reviewer_id: str
) -> int:
    """Increment and return blocking retry count for reviewer request_changes."""
    features = state.setdefault("features", {})
    feature_state = features.setdefault(feature_id, {})
    reviewers = feature_state.setdefault("reviewers", {})
    reviewer_state = reviewers.get(reviewer_id)
    if not isinstance(reviewer_state, dict):
        reviewer_state = {}
        reviewers[reviewer_id] = reviewer_state

    count = int(reviewer_state.get(BLOCKING_RETRY_COUNT_KEY, 0)) + 1
    reviewer_state[BLOCKING_RETRY_COUNT_KEY] = count
    reviewer_state[BLOCKING_RETRY_UPDATED_AT_KEY] = _now_iso()
    reviewer_state["approved"] = False
    return count


def invalidate_reviewer_approval(
    state: dict[str, Any], *, feature_id: str, reviewer_id: str
) -> None:
    """Invalidate cached first approval for one feature/reviewer."""
    features = state.get("features")
    if not isinstance(features, dict):
        return
    feature_state = features.get(feature_id)
    if not isinstance(feature_state, dict):
        return
    reviewers = feature_state.get("reviewers")
    if not isinstance(reviewers, dict):
        return
    reviewer_state = reviewers.get(reviewer_id)
    if not isinstance(reviewer_state, dict):
        return
    reviewer_state["approved"] = False
    reviewer_state["invalidated_at"] = _now_iso()


def evaluate_cached_reviewer_approval(
    state: dict[str, Any],
    *,
    feature_id: str,
    reviewer_id: str,
    reviewer: dict[str, Any],
    changed_paths: ChangedPathsResult,
) -> tuple[bool, str]:
    """Return whether first-approval cache can be reused and deterministic reason.

    When scoped changes invalidate a cached approval, this function also marks the
    cached approval as invalid in state so the transition is auditable on disk.
    """
    approval = reviewer.get("approval", {})
    if not approval.get("first_feature_approval", True):
        return False, FIRST_FEATURE_APPROVAL_DISABLED_REASON

    features = state.get("features", {})
    feature_state = features.get(feature_id, {}) if isinstance(features, dict) else {}
    reviewers = (
        feature_state.get("reviewers", {}) if isinstance(feature_state, dict) else {}
    )
    cached = reviewers.get(reviewer_id, {}) if isinstance(reviewers, dict) else {}
    if not isinstance(cached, dict) or not cached.get("approved"):
        return False, FIRST_FEATURE_APPROVAL_NOT_CACHED_REASON

    trigger = reviewer.get("trigger", {})
    on_change = trigger.get("on_change")
    if changed_paths.run_all:
        invalidate_reviewer_approval(
            state,
            feature_id=feature_id,
            reviewer_id=reviewer_id,
        )
        return False, FIRST_FEATURE_APPROVAL_INVALIDATED_RUN_ALL_REASON

    if on_change is None:
        if changed_paths.paths:
            invalidate_reviewer_approval(
                state,
                feature_id=feature_id,
                reviewer_id=reviewer_id,
            )
            return False, FIRST_FEATURE_APPROVAL_INVALIDATED_REASON
        return True, FIRST_FEATURE_APPROVAL_REUSED_REASON

    if any(path_matches_any_glob(path, on_change) for path in changed_paths.paths):
        invalidate_reviewer_approval(
            state,
            feature_id=feature_id,
            reviewer_id=reviewer_id,
        )
        return False, FIRST_FEATURE_APPROVAL_INVALIDATED_REASON
    return True, FIRST_FEATURE_APPROVAL_REUSED_REASON


def run_reviewer(
    project_root: Path,
    reviewer_id: str,
    reviewer: dict[str, Any],
    request: ReviewerRunRequest | None = None,
    **legacy_request_kwargs: Any,
) -> dict[str, Any]:
    """Run one reviewer and return a deterministic decision envelope."""
    run_request = _coerce_reviewer_run_request(request, legacy_request_kwargs)
    try:
        with _reviewer_execution_root(
            project_root, reviewer_id, reviewer
        ) as execution_root:
            prompt_file = str(reviewer.get("prompt_file", "")).strip()
            if not prompt_file:
                return _parser_failure_decision("reviewer prompt_file is required")

            prompt_path = execution_root / prompt_file
            if not prompt_path.exists():
                return _parser_failure_decision(
                    f"reviewer prompt file not found: {prompt_file}"
                )

            reviewer_prompt = prompt_path.read_text(encoding="utf-8")
            try:
                composed_prompt = _compose_reviewer_prompt(
                    reviewer_prompt=reviewer_prompt,
                    reviewer_id=reviewer_id,
                    request=run_request,
                )
            except ValueError as exc:
                return _parser_failure_decision(str(exc))

            agent_runner = run_request.run_agent_fn or run_agent

            try:
                envelope = agent_runner(
                    execution_root,
                    composed_prompt,
                    output_type=ReviewerDecisionEnvelope,
                    max_validation_retries=REVIEWER_DECISION_PARSE_MAX_RETRIES,
                )
            except FileNotFoundError:
                return _parser_failure_decision("opencode executable missing")
            except AgentBackendError as exc:
                return _parser_failure_decision(str(exc))
            except AgentOutputValidationError as exc:
                return _parser_failure_decision(exc.error_summary)

            if isinstance(envelope, ReviewerDecisionEnvelope):
                return envelope.model_dump(exclude_none=True)
            return ReviewerDecisionEnvelope.model_validate(envelope).model_dump(
                exclude_none=True
            )
    except RuntimeError as exc:
        return _parser_failure_decision(str(exc))


def _coerce_reviewer_run_request(
    request: ReviewerRunRequest | None,
    legacy_request_kwargs: dict[str, Any],
) -> ReviewerRunRequest:
    if request is not None:
        if legacy_request_kwargs:
            return ReviewerRunRequest.model_validate(
                {
                    **request.model_dump(),
                    **legacy_request_kwargs,
                }
            )
        return request

    return ReviewerRunRequest.model_validate(legacy_request_kwargs)


def build_reviewer_sandbox(
    project_root: Path,
    reviewer_id: str,
    reviewer_config: dict[str, Any],
) -> ReviewerSandboxHandle | None:
    """Build and return a reviewer sandbox handle when mode requires one."""
    sandbox = reviewer_config.get("sandbox", {})
    if not isinstance(sandbox, dict):
        sandbox = {}

    if sandbox.get("mode") != SANDBOX_MODE_EMPTY_FOLDER:
        return None

    return _build_empty_folder_sandbox(
        project_root=project_root,
        reviewer_id=reviewer_id,
        reviewer_config=reviewer_config,
    )


def _build_empty_folder_sandbox(
    *,
    project_root: Path,
    reviewer_id: str,
    reviewer_config: dict[str, Any],
) -> ReviewerSandboxHandle:
    prompt_file = str(reviewer_config.get("prompt_file", "")).strip()
    if not prompt_file:
        raise RuntimeError(
            f"sandbox setup failed: reviewer {reviewer_id} prompt_file is required"
        )

    workspace_root = Path(mkdtemp(prefix=f"engineeringagent-reviewer-{reviewer_id}-"))
    execution_root = workspace_root / "workspace"
    execution_root.mkdir(parents=True, exist_ok=True)

    def _cleanup() -> None:
        shutil.rmtree(workspace_root, ignore_errors=True)

    configured_assets: list[str] = []
    sandbox_config = reviewer_config.get("sandbox", {})
    if isinstance(sandbox_config, dict):
        assets = sandbox_config.get("assets", [])
        if isinstance(assets, list):
            configured_assets = [str(asset) for asset in assets]

    sandbox_assets = [prompt_file]
    for asset in configured_assets:
        if asset and asset != prompt_file:
            sandbox_assets.append(asset)

    try:
        for relative_path in sandbox_assets:
            _copy_sandbox_asset(
                project_root=project_root,
                execution_root=execution_root,
                relative_path=relative_path,
            )
    except RuntimeError:
        _cleanup()
        raise
    except OSError as exc:
        _cleanup()
        raise RuntimeError(f"sandbox setup failed: {exc}") from exc

    return ReviewerSandboxHandle(
        execution_root=execution_root,
        cleanup=_cleanup,
    )


def _copy_sandbox_asset(
    *,
    project_root: Path,
    execution_root: Path,
    relative_path: str,
) -> None:
    candidate = Path(relative_path)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        raise RuntimeError(
            f"sandbox setup failed: invalid sandbox asset path: {relative_path}"
        )

    if candidate.parts and candidate.parts[0] == ".git":
        raise RuntimeError(
            f"sandbox setup failed: forbidden sandbox asset root: {relative_path}"
        )
    if candidate.parts[:2] == (".opencode", "node_modules"):
        raise RuntimeError(
            f"sandbox setup failed: forbidden sandbox asset path: {relative_path}"
        )

    source_path = project_root / candidate
    if not source_path.exists():
        raise RuntimeError(
            f"sandbox setup failed: required sandbox asset missing: {relative_path}"
        )
    target_path = execution_root / candidate
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if source_path.is_dir():
        ignore_names = {".git", "__pycache__", ".pytest_cache", ".mypy_cache"}

        ignore_opencode_node_modules = candidate.parts[:1] == (".opencode",)

        def _ignore(_dir_path: str, contents: list[str]) -> set[str]:
            ignored = ignore_names.intersection(contents)
            if ignore_opencode_node_modules and "node_modules" in contents:
                ignored.add("node_modules")
            return ignored

        shutil.copytree(
            source_path,
            target_path,
            dirs_exist_ok=True,
            ignore=_ignore,
        )
        return

    shutil.copy2(source_path, target_path)


def _parser_failure_decision(reason: str) -> dict[str, Any]:
    return {
        "decision": DECISION_REQUEST_CHANGES,
        "summary": f"{PARSER_FAILURE_SUMMARY_PREFIX}: {reason}",
        "required_actions": [
            "Return a strict JSON object that validates against the reviewer decision JSON Schema in the reviewer instructions."
        ],
    }


def _compose_reviewer_prompt(
    *,
    reviewer_prompt: str,
    reviewer_id: str,
    request: ReviewerRunRequest,
) -> str:
    """Compose deterministic reviewer context and repository-local prompt text."""
    reviewer_instructions = reviewer_prompt.strip()

    changed = "\n".join(f"- {path}" for path in request.changed_paths.paths)
    if not changed:
        changed = "- (none)"
    feedback = request.prior_feedback.strip() if request.prior_feedback else "(none)"
    return (
        "You are a reviewer agent.\n\n"
        f"Reviewer: {reviewer_id}\n"
        f"Feature ID: {request.feature_id}\n"
        f"Feature path: {request.feature_path}\n"
        "Changed paths:\n"
        f"{changed}\n\n"
        "Prior feedback:\n"
        f"{feedback}\n\n"
        "Reviewer instructions:\n"
        f"{reviewer_instructions}\n"
    )


@contextmanager
def _reviewer_execution_root(
    project_root: Path,
    reviewer_id: str,
    reviewer: dict[str, Any],
) -> Iterator[Path]:
    """Yield execution root, optionally isolated via temp worktree snapshot."""
    sandbox = reviewer.get("sandbox", {})
    if not isinstance(sandbox, dict):
        sandbox = {}

    sandbox_handle = build_reviewer_sandbox(
        project_root=project_root,
        reviewer_id=reviewer_id,
        reviewer_config=reviewer,
    )
    if sandbox_handle is not None:
        try:
            yield sandbox_handle.execution_root
        finally:
            sandbox_handle.cleanup()
        return

    if sandbox.get("mode") != SANDBOX_MODE_TEMP_WORKTREE_SNAPSHOT:
        yield project_root
        return

    with TemporaryDirectory(prefix="engineeringagent-reviewer-") as temp_dir:
        snapshot_root = Path(temp_dir) / "snapshot"
        try:
            shutil.copytree(
                project_root,
                snapshot_root,
                ignore=shutil.ignore_patterns(
                    ".git",
                    "__pycache__",
                    ".pytest_cache",
                    ".mypy_cache",
                ),
            )
        except OSError as exc:
            raise RuntimeError(f"sandbox setup failed: {exc}") from exc
        yield snapshot_root
