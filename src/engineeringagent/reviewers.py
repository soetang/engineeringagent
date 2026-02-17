"""Compatibility wrapper for legacy reviewers module.

FEAT-098 migrates production callers to the canonical checks surface.
This module remains for backward compatibility and test coverage.
"""

from __future__ import annotations

from engineeringagent.checks.reviewers.engine import (  # re-export for static imports
    DECISION_APPROVE,
    DECISION_REQUEST_CHANGES,
    FEATURE_DONE_PHASE,
    FIRST_FEATURE_APPROVAL_INVALIDATED_REASON,
    FIRST_FEATURE_APPROVAL_INVALIDATED_RUN_ALL_REASON,
    FIRST_FEATURE_APPROVAL_NOT_CACHED_REASON,
    FIRST_FEATURE_APPROVAL_REUSED_REASON,
    MATCHED_ON_CHANGE_REASON,
    NO_ON_CHANGE_MATCH_REASON,
    PARSER_FAILURE_SUMMARY_PREFIX,
    PHASE_MISMATCH_REASON,
    REVIEWER_RESPONSEFORMAT_PLACEHOLDER,
    ReviewerDecisionEnvelope,
    build_reviewer_sandbox,
    evaluate_cached_reviewer_approval,
    increment_blocking_reviewer_retry_count,
    invalidate_reviewer_approval,
    load_reviewer_config,
    load_reviewers_state,
    parse_reviewer_decision,
    plan_reviewers,
    record_reviewer_approval,
    run_reviewer,
    save_reviewers_state,
)

from engineeringagent.checks.reviewers import engine as _impl

__all__ = [
    "DECISION_APPROVE",
    "DECISION_REQUEST_CHANGES",
    "FEATURE_DONE_PHASE",
    "FIRST_FEATURE_APPROVAL_INVALIDATED_REASON",
    "FIRST_FEATURE_APPROVAL_INVALIDATED_RUN_ALL_REASON",
    "FIRST_FEATURE_APPROVAL_NOT_CACHED_REASON",
    "FIRST_FEATURE_APPROVAL_REUSED_REASON",
    "MATCHED_ON_CHANGE_REASON",
    "NO_ON_CHANGE_MATCH_REASON",
    "PARSER_FAILURE_SUMMARY_PREFIX",
    "PHASE_MISMATCH_REASON",
    "REVIEWER_RESPONSEFORMAT_PLACEHOLDER",
    "ReviewerDecisionEnvelope",
    "build_reviewer_sandbox",
    "evaluate_cached_reviewer_approval",
    "increment_blocking_reviewer_retry_count",
    "invalidate_reviewer_approval",
    "load_reviewer_config",
    "load_reviewers_state",
    "parse_reviewer_decision",
    "plan_reviewers",
    "record_reviewer_approval",
    "run_reviewer",
    "save_reviewers_state",
]


def __getattr__(name: str) -> object:
    return getattr(_impl, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_impl)))
