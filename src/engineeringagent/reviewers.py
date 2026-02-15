from __future__ import annotations

import json
import shlex
import shutil
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Iterator, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

import engineeringagent.progress_paths as progress_paths

from .gates import ChangedPathsResult
from .on_change_matcher import path_matches_any_glob
from .opencode.client import DEFAULT_OPENCODE_AGENT
from .specs import load_yaml, reviewer_contract_issues


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

REVIEWER_DECISION_PARSE_MAX_RETRIES = 2

REVIEWER_DECISION_PARSE_RETRY_PROMPT_TEMPLATE = "\n".join(
    (
        "---",
        "Your previous output did not validate as a reviewer decision JSON object.",
        "",
        "Validation error:",
        "{{VALIDATION_ERROR}}",
        "",
        "Return exactly one strict JSON object and no other text.",
        "It MUST validate against the JSON Schema provided in the reviewer instructions.",
        "No Markdown. No code fences. No surrounding commentary.",
        "---",
    )
)


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
    confidence: float | None = Field(default=None, ge=0, le=1)
    scope_notes: str | None = None

    @field_validator("summary")
    @classmethod
    def _summary_must_be_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("summary must be a non-empty string")
        return stripped


REVIEWER_DECISION_JSON_SCHEMA = json.dumps(
    ReviewerDecisionEnvelope.model_json_schema(),
    indent=2,
    sort_keys=True,
    ensure_ascii=True,
)

REVIEWER_RESPONSEFORMAT_CONTRACT = "\n".join(
    (
        "---",
        "Return exactly one strict JSON object and no other text.",
        "No Markdown. No code fences. No surrounding commentary.",
        "",
        "The JSON object MUST validate against the JSON Schema below.",
        "The schema is derived from the reviewer decision envelope model and is emitted with sorted",
        "keys for deterministic prompts.",
        "",
        "JSON Schema:",
        REVIEWER_DECISION_JSON_SCHEMA,
        "",
        "Notes:",
        '- `decision` must be one of: "approve", "request_changes", "warning".',
        "- `summary` must be a non-empty string.",
        "- If present, `required_actions` must be a list of strings.",
        "- If present, `confidence` must be a number between 0 and 1.",
        "",
        "Example output:",
        '{"decision":"approve","summary":"Looks good.","required_actions":[]}',
        "---",
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
        phase: Requested execution phase (`feature_done` in loop runtime).
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
        trigger_phase = _resolve_reviewer_trigger_phase(trigger.get("phase"))
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


def _resolve_reviewer_trigger_phase(phase: Any) -> str:
    """Normalize legacy trigger phases to the feature_done execution contract."""
    normalized_phase = str(phase or "").strip()
    if normalized_phase == ITERATION_END_PHASE:
        return FEATURE_DONE_PHASE
    return normalized_phase


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
                    format="json",
                )
            except FileNotFoundError:
                return _parser_failure_decision("opencode executable missing")

            stdout_raw = getattr(proc, "stdout", "") or ""
            stderr_raw = getattr(proc, "stderr", "") or ""

            session_id, decision_payload = _extract_opencode_json_text_payload(
                stdout_raw
            )
            if session_id and decision_payload:
                decision = parse_reviewer_decision(decision_payload)
                if _is_reviewer_parser_failure(decision):
                    decision = _retry_parse_failure_in_same_session(
                        execution_root,
                        run_request,
                        session_id=session_id,
                        decision=decision,
                    )
                return decision

            return _parse_reviewer_decision_from_stdio(stdout_raw, stderr_raw)
    except RuntimeError as exc:
        return _parser_failure_decision(str(exc))


def _extract_opencode_json_text_payload(stdout: str) -> tuple[str | None, str | None]:
    """Extract (session_id, last text payload) from OpenCode JSON event stream.

    Returns (None, None) on any parsing/extraction failure so callers can fall back
    to legacy stdout/stderr parsing.
    """

    raw = stdout.strip("\n")
    if not raw.strip():
        return None, None

    session_id: str | None = None
    candidates: list[str] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return None, None
        if not isinstance(event, dict):
            continue
        if session_id is None:
            maybe_session = event.get("sessionID")
            if isinstance(maybe_session, str) and maybe_session:
                session_id = maybe_session

        if event.get("type") != "text":
            continue
        part = event.get("part")
        if not isinstance(part, dict):
            continue
        text = part.get("text")
        if isinstance(text, str):
            candidates.append(text)

    if session_id is None or not candidates:
        return None, None
    return session_id, candidates[-1]


def _is_reviewer_parser_failure(decision: dict[str, Any]) -> bool:
    """Return True when decision represents deterministic parse/schema failure."""
    if decision.get("decision") != DECISION_REQUEST_CHANGES:
        return False
    summary = decision.get("summary")
    if not isinstance(summary, str):
        return False
    return summary.startswith(f"{PARSER_FAILURE_SUMMARY_PREFIX}:")


def _extract_reviewer_parser_failure_reason(decision: dict[str, Any]) -> str:
    summary = decision.get("summary")
    if not isinstance(summary, str):
        return "output does not match reviewer decision schema"
    prefix = f"{PARSER_FAILURE_SUMMARY_PREFIX}:"
    if summary.startswith(prefix):
        return (
            summary[len(prefix) :].strip()
            or "output does not match reviewer decision schema"
        )
    return summary.strip() or "output does not match reviewer decision schema"


def _render_reviewer_parse_retry_prompt(*, validation_error: str) -> str:
    return REVIEWER_DECISION_PARSE_RETRY_PROMPT_TEMPLATE.replace(
        "{{VALIDATION_ERROR}}",
        validation_error.strip() or "output does not match reviewer decision schema",
    )


def _retry_parse_failure_in_same_session(
    execution_root: Path,
    request: ReviewerRunRequest,
    *,
    session_id: str,
    decision: dict[str, Any],
) -> dict[str, Any]:
    """Retry parse/schema failures up to a bounded count in the same OpenCode session."""

    current = decision
    for _attempt in range(REVIEWER_DECISION_PARSE_MAX_RETRIES):
        if not _is_reviewer_parser_failure(current):
            return current

        validation_error = _extract_reviewer_parser_failure_reason(current)
        followup_prompt = _render_reviewer_parse_retry_prompt(
            validation_error=validation_error
        )

        try:
            proc = request.start_agent_fn(
                execution_root,
                followup_prompt,
                agent=DEFAULT_OPENCODE_AGENT,
                format="json",
                session=session_id,
            )
        except FileNotFoundError:
            return _parser_failure_decision("opencode executable missing")

        stdout_raw = getattr(proc, "stdout", "") or ""
        stderr_raw = getattr(proc, "stderr", "") or ""

        _, decision_payload = _extract_opencode_json_text_payload(stdout_raw)
        if decision_payload:
            current = parse_reviewer_decision(decision_payload)
            continue

        current = _parse_reviewer_decision_from_stdio(stdout_raw, stderr_raw)

    return current


def _parse_reviewer_decision_from_stdio(
    stdout_raw: str,
    stderr_raw: str,
) -> dict[str, Any]:
    parse_input = stdout_raw.strip() or stderr_raw.strip()
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
    configured_assets: list[str] = []
    sandbox_config = reviewer_config.get("sandbox", {})
    if isinstance(sandbox_config, dict):
        assets = sandbox_config.get("assets", [])
        if isinstance(assets, list):
            configured_assets = [str(asset) for asset in assets]

    sandbox_assets = sorted({"README.md", prompt_file, *configured_assets})

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

    forbidden_roots = {".git", "src", "tests"}
    if candidate.parts and candidate.parts[0] in forbidden_roots:
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
        payload = _extract_reviewer_decision_payload(raw)
        if payload is None:
            return _parser_failure_decision("output is not valid JSON")

    if not isinstance(payload, dict):
        return _parser_failure_decision("output must be a JSON object")

    try:
        envelope = ReviewerDecisionEnvelope.model_validate(payload)
    except ValidationError as exc:
        return _parser_failure_decision(_format_reviewer_decision_validation_error(exc))

    return envelope.model_dump(exclude_none=True)


def _format_reviewer_decision_validation_error(exc: ValidationError) -> str:
    """Return a deterministic one-line validation error summary."""
    parts: list[str] = []
    for error in exc.errors():
        loc = error.get("loc")
        if isinstance(loc, (tuple, list)):
            loc_text = ".".join(str(item) for item in loc) or "root"
        else:
            loc_text = "root"
        message = str(error.get("msg") or "validation error").strip()
        parts.append(f"{loc_text}: {message}")

    # Preserve order while de-duplicating.
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        if part in seen:
            continue
        unique.append(part)
        seen.add(part)

    if not unique:
        return "output does not match reviewer decision schema"
    return "; ".join(unique)


def _extract_reviewer_decision_payload(raw: str) -> dict[str, Any] | None:
    """Best-effort extraction for wrapped/annotated reviewer outputs.

    Reviewers are instructed to emit exactly one JSON object. In practice, some
    runners may wrap the final answer in code fences or add lightweight prefixes.
    To keep the reviewer loop deterministic and resilient, attempt to locate the
    last JSON object embedded in the output and treat it as the decision payload.
    """

    decoder = json.JSONDecoder()
    last_payload: dict[str, Any] | None = None
    pos = raw.find("{")
    while pos != -1:
        try:
            candidate, end = decoder.raw_decode(raw[pos:])
        except json.JSONDecodeError:
            pos = raw.find("{", pos + 1)
            continue

        if isinstance(candidate, dict):
            last_payload = candidate
        # Skip past the decoded JSON object to avoid re-scanning nested braces.
        pos = raw.find("{", pos + max(end, 1))

    return last_payload


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
