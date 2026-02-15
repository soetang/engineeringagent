from __future__ import annotations

import json
import shlex
import shutil
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Iterator

from pydantic import BaseModel, ConfigDict

from .gates import ChangedPathsResult
from .on_change_matcher import path_matches_any_glob
from .opencode.client import DEFAULT_OPENCODE_AGENT
from .specs import load_yaml, reviewer_contract_issues


FALLBACK_CHANGE_DISCOVERY_REASON = "fallback_run_all_change_discovery_failed"
ALWAYS_RUN_NO_ON_CHANGE_REASON = "always_run_no_on_change"
MATCHED_ON_CHANGE_REASON = "matched_on_change"
NO_ON_CHANGE_MATCH_REASON = "no_on_change_match"
PHASE_MISMATCH_REASON = "phase_mismatch"
DECISION_APPROVE = "approve"
DECISION_REQUEST_CHANGES = "request_changes"
DECISION_WARNING = "warning"
_VALID_DECISIONS = {
    DECISION_APPROVE,
    DECISION_REQUEST_CHANGES,
    DECISION_WARNING,
}
PARSER_FAILURE_SUMMARY_PREFIX = "reviewer_output_parse_failure"
FIRST_FEATURE_APPROVAL_REUSED_REASON = "first_feature_approval_reused"
FIRST_FEATURE_APPROVAL_NOT_CACHED_REASON = "first_feature_approval_not_cached"
FIRST_FEATURE_APPROVAL_DISABLED_REASON = "first_feature_approval_disabled"
FIRST_FEATURE_APPROVAL_INVALIDATED_REASON = "first_feature_approval_invalidated"
FIRST_FEATURE_APPROVAL_INVALIDATED_RUN_ALL_REASON = (
    "first_feature_approval_invalidated_run_all"
)
REVIEWERS_STATE_VERSION = "1"
ADVISORY_FOLLOWUP_REQUIRED_KEY = "advisory_followup_required"
BLOCKING_RETRY_COUNT_KEY = "blocking_request_changes_count"
BLOCKING_RETRY_UPDATED_AT_KEY = "blocking_retry_updated_at"
SANDBOX_MODE_TEMP_WORKTREE_SNAPSHOT = "temp_worktree_snapshot"
SANDBOX_MODE_CLEAN_ROOM_README_CLI = "clean_room_readme_cli"
CLEAN_ROOM_ENGINEERINGAGENT_HELPER = ".engineeringagent/bin/engineeringagent"
REVIEWER_RESPONSEFORMAT_PLACEHOLDER = "$responseformat"
REVIEWER_RESPONSEFORMAT_MISSING_MESSAGE = (
    "reviewer prompt must include the $responseformat placeholder"
)
REVIEWER_RESPONSEFORMAT_CONTRACT = "\n".join(
    (
        "Return exactly one strict JSON object and no other text.",
        "Required JSON keys: `decision` and `summary`.",
        "Optional JSON keys: `required_actions`, `confidence`, `scope_notes`.",
        "`decision` must be one of: `approve`, `request_changes`, `warning`.",
        "If `required_actions` is present, it must be a list of strings.",
        "If `confidence` is present, it must be a number in [0, 1].",
    )
)


class ReviewerSandboxHandle(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_root: Path
    cleanup: Callable[[], None]


class ReviewerRunRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_id: str
    feature_path: Path
    changed_paths: ChangedPathsResult
    prior_feedback: str | None
    start_agent_fn: Callable[..., Any]


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
    """Load persisted reviewer state from progress/reviewers-state.json."""
    state_path = project_root / "progress" / "reviewers-state.json"
    if not state_path.exists():
        return _default_reviewers_state()

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_reviewers_state()

    if not isinstance(payload, dict):
        return _default_reviewers_state()
    features = payload.get("features")
    if not isinstance(features, dict):
        return _default_reviewers_state()
    return {
        "version": str(payload.get("version", REVIEWERS_STATE_VERSION)),
        "features": features,
    }


def save_reviewers_state(project_root: Path, state: dict[str, Any]) -> None:
    """Persist reviewer state under progress/reviewers-state.json."""
    state_path = project_root / "progress" / "reviewers-state.json"
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


def set_advisory_followup_required(state: dict[str, Any], *, feature_id: str) -> None:
    """Mark that one implement follow-up pass is required before completion."""
    features = state.setdefault("features", {})
    feature_state = features.setdefault(feature_id, {})
    feature_state[ADVISORY_FOLLOWUP_REQUIRED_KEY] = True
    feature_state["advisory_followup_updated_at"] = _now_iso()


def clear_advisory_followup_required(state: dict[str, Any], *, feature_id: str) -> None:
    """Clear advisory follow-up latch after one subsequent implement pass."""
    features = state.get("features")
    if not isinstance(features, dict):
        return
    feature_state = features.get(feature_id)
    if not isinstance(feature_state, dict):
        return
    feature_state[ADVISORY_FOLLOWUP_REQUIRED_KEY] = False
    feature_state["advisory_followup_updated_at"] = _now_iso()


def advisory_followup_required(state: dict[str, Any], *, feature_id: str) -> bool:
    """Return whether the feature currently requires one follow-up pass."""
    features = state.get("features")
    if not isinstance(features, dict):
        return False
    feature_state = features.get(feature_id)
    if not isinstance(feature_state, dict):
        return False
    return bool(feature_state.get(ADVISORY_FOLLOWUP_REQUIRED_KEY, False))


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


def load_reviewer_config(path: Path) -> dict[str, Any]:
    """Load reviewer configuration from disk.

    Args:
        path: Path to the reviewers YAML file.

    Returns:
        Parsed reviewer configuration mapping.

    Raises:
        ValueError: If the YAML is not a valid reviewer contract.
    """
    if not path.exists():
        return {"contract_version": "1.0", "profiles": {}, "reviewers": {}}

    data = load_yaml(path)
    contract_issues = reviewer_contract_issues(data, path)
    if contract_issues:
        formatted = "; ".join(
            f"{issue.path}: {issue.message}" for issue in contract_issues
        )
        raise ValueError(f"invalid reviewers config: {formatted}")
    config = dict(data)
    config.setdefault("contract_version", "1.0")
    return config


def plan_reviewers(
    config: dict[str, Any],
    profile: str,
    *,
    phase: str,
    changed_paths: ChangedPathsResult,
) -> list[dict[str, str]]:
    """Plan deterministic reviewer run/skip decisions for one profile and phase.

    Args:
        config: Parsed reviewer configuration mapping.
        profile: Profile name to evaluate.
        phase: Review phase (`iteration_end` or `feature_done`).
        changed_paths: Resolved changed-path input and fallback metadata.

    Returns:
        Ordered list of reviewer decision envelopes.

    Raises:
        ValueError: If profile is unknown.
    """
    profiles = config.get("profiles", {})
    reviewers = config.get("reviewers", {})
    if profile not in profiles:
        raise ValueError(f"unknown profile: {profile}")

    fallback_reason = changed_paths.reason or FALLBACK_CHANGE_DISCOVERY_REASON
    decisions: list[dict[str, str]] = []
    for reviewer_id in profiles[profile]:
        reviewer = reviewers.get(reviewer_id, {})
        trigger = reviewer.get("trigger", {})
        trigger_phase = trigger.get("phase")
        if trigger_phase != phase:
            decisions.append(
                {
                    "reviewer": reviewer_id,
                    "decision": "skip",
                    "reason": PHASE_MISMATCH_REASON,
                }
            )
            continue

        on_change = trigger.get("on_change")
        if changed_paths.run_all:
            decisions.append(
                {
                    "reviewer": reviewer_id,
                    "decision": "run",
                    "reason": fallback_reason,
                }
            )
            continue

        if on_change is None:
            decisions.append(
                {
                    "reviewer": reviewer_id,
                    "decision": "run",
                    "reason": ALWAYS_RUN_NO_ON_CHANGE_REASON,
                }
            )
            continue

        if any(path_matches_any_glob(path, on_change) for path in changed_paths.paths):
            decisions.append(
                {
                    "reviewer": reviewer_id,
                    "decision": "run",
                    "reason": MATCHED_ON_CHANGE_REASON,
                }
            )
            continue

        decisions.append(
            {
                "reviewer": reviewer_id,
                "decision": "skip",
                "reason": NO_ON_CHANGE_MATCH_REASON,
            }
        )

    return decisions


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

            try:
                proc = run_request.start_agent_fn(
                    execution_root,
                    composed_prompt,
                    agent=DEFAULT_OPENCODE_AGENT,
                )
            except FileNotFoundError:
                return _parser_failure_decision("opencode executable missing")
    except RuntimeError as exc:
        return _parser_failure_decision(str(exc))

    stdout = (getattr(proc, "stdout", "") or "").strip()
    stderr = (getattr(proc, "stderr", "") or "").strip()
    parse_input = (
        stdout if stdout else "\n".join(part for part in [stdout, stderr] if part)
    )
    if not parse_input:
        return _parser_failure_decision("reviewer produced empty output")
    return parse_reviewer_decision(parse_input)


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

    if sandbox.get("mode") != SANDBOX_MODE_CLEAN_ROOM_README_CLI:
        return None

    return _build_clean_room_readme_cli_sandbox(
        project_root=project_root,
        reviewer_id=reviewer_id,
        reviewer_config=reviewer_config,
    )


def _build_clean_room_readme_cli_sandbox(
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

    workspace = TemporaryDirectory(
        prefix=f"engineeringagent-reviewer-{reviewer_id}-clean-room-"
    )
    execution_root = Path(workspace.name) / "workspace"
    execution_root.mkdir(parents=True, exist_ok=True)
    sandbox_assets = sorted({"README.md", prompt_file})

    try:
        for relative_path in sandbox_assets:
            _copy_clean_room_asset(
                project_root=project_root,
                execution_root=execution_root,
                relative_path=relative_path,
            )
        _write_clean_room_cli_helper(
            project_root=project_root,
            execution_root=execution_root,
        )
    except RuntimeError:
        workspace.cleanup()
        raise
    except OSError as exc:
        workspace.cleanup()
        raise RuntimeError(f"sandbox setup failed: {exc}") from exc

    return ReviewerSandboxHandle(
        execution_root=execution_root,
        cleanup=workspace.cleanup,
    )


def _copy_clean_room_asset(
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

    source_path = project_root / candidate
    if not source_path.exists():
        raise RuntimeError(
            f"sandbox setup failed: required sandbox asset missing: {relative_path}"
        )
    if source_path.is_dir():
        raise RuntimeError(
            f"sandbox setup failed: sandbox asset must be a file: {relative_path}"
        )

    target_path = execution_root / candidate
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)


def _write_clean_room_cli_helper(*, project_root: Path, execution_root: Path) -> None:
    source_root = project_root / "src"
    if not source_root.exists() or not source_root.is_dir():
        raise RuntimeError("sandbox setup failed: required source root missing: src")

    helper_path = execution_root / CLEAN_ROOM_ENGINEERINGAGENT_HELPER
    helper_path.parent.mkdir(parents=True, exist_ok=True)

    helper_script = "\n".join(
        [
            "#!/usr/bin/env sh",
            "set -eu",
            (
                "export PYTHONPATH="
                f"{shlex.quote(str(source_root))}${{PYTHONPATH:+:${{PYTHONPATH}}}}"
            ),
            f'exec {shlex.quote(sys.executable)} -m engineeringagent.cli "$@"',
            "",
        ]
    )
    helper_path.write_text(helper_script, encoding="utf-8")
    helper_path.chmod(0o755)


def parse_reviewer_decision(output: str) -> dict[str, Any]:  # noqa: C901
    """Parse strict reviewer decision JSON; return request_changes on failures."""
    raw = output.strip()
    if not raw:
        return _parser_failure_decision("reviewer produced empty output")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return _parser_failure_decision("output is not valid JSON")

    if not isinstance(payload, dict):
        return _parser_failure_decision("output must be a JSON object")

    decision = payload.get("decision")
    if decision not in _VALID_DECISIONS:
        return _parser_failure_decision(
            "decision must be one of approve, request_changes, warning"
        )

    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return _parser_failure_decision("summary must be a non-empty string")

    required_actions = payload.get("required_actions", [])
    if not isinstance(required_actions, list) or any(
        not isinstance(item, str) for item in required_actions
    ):
        return _parser_failure_decision("required_actions must be a list of strings")

    confidence = payload.get("confidence")
    if confidence is not None:
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            return _parser_failure_decision(
                "confidence must be a number between 0 and 1"
            )

    scope_notes = payload.get("scope_notes")
    if scope_notes is not None and not isinstance(scope_notes, str):
        return _parser_failure_decision("scope_notes must be a string")

    decision_envelope: dict[str, Any] = {
        "decision": decision,
        "summary": summary.strip(),
        "required_actions": required_actions,
    }
    if confidence is not None:
        decision_envelope["confidence"] = float(confidence)
    if scope_notes is not None:
        decision_envelope["scope_notes"] = scope_notes
    return decision_envelope


def _parser_failure_decision(reason: str) -> dict[str, Any]:
    return {
        "decision": DECISION_REQUEST_CHANGES,
        "summary": f"{PARSER_FAILURE_SUMMARY_PREFIX}: {reason}",
        "required_actions": [
            "Return a strict JSON decision envelope with decision and summary fields."
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
    if REVIEWER_RESPONSEFORMAT_PLACEHOLDER not in reviewer_instructions:
        raise ValueError(REVIEWER_RESPONSEFORMAT_MISSING_MESSAGE)
    reviewer_instructions = reviewer_instructions.replace(
        REVIEWER_RESPONSEFORMAT_PLACEHOLDER,
        REVIEWER_RESPONSEFORMAT_CONTRACT,
    )

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
