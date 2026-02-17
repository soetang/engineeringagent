"""Canonical checks surface.

This package is introduced as part of a staged refactor to centralize all check
planning and execution behind a stable import surface.
"""

from .api import ChecksRunResult, run_checks
from .fitness_api import emit_fitness_result
from .retry_feedback.builders import (
    build_command_failure_retry_feedback,
    build_fitness_failure_retry_feedback,
    build_reviewer_feedback_retry_feedback,
)
from .retry_feedback.contracts import (
    MAX_FAILED_RULES,
    MAX_REQUIRED_ACTIONS,
    MAX_RULE_VIOLATIONS,
    CommandFailureRetryFeedbackEnvelope,
    FailedFitnessRule,
    FitnessFailureRetryFeedbackEnvelope,
    RetryFeedbackEnvelope,
    ReviewerDecisionPayload,
    ReviewerFeedbackRetryEnvelope,
    parse_retry_feedback_envelope,
    serialize_retry_feedback_envelope,
)
from .validate.runtime import run_validate

from .fitness.adapters import execute_rule_definition
from .fitness.catalog import render_rule_catalog_markdown, write_rule_catalog_markdown
from .fitness.contracts import (
    CONTRACT_VERSION,
    CustomRuleManifest,
    CustomRuleManifestEntry,
    FitnessRuleMetadata,
    FitnessRuleResult,
    RuleAdapter,
    RuleSeverity,
    RuleSource,
    RuleStatus,
    load_custom_rule_manifest,
)
from .fitness.registry import (
    DEFAULT_CUSTOM_RULE_MANIFEST,
    FitnessRuleDefinition,
    build_rule_catalog,
    custom_manifest_path,
    load_custom_rule_definitions,
)
from .fitness.runner import FitnessRunSummary, run_rule_catalog

emit_result_envelope = emit_fitness_result

__all__ = [
    "CONTRACT_VERSION",
    "ChecksRunResult",
    "CommandFailureRetryFeedbackEnvelope",
    "CustomRuleManifest",
    "CustomRuleManifestEntry",
    "DEFAULT_CUSTOM_RULE_MANIFEST",
    "FailedFitnessRule",
    "FitnessRuleDefinition",
    "FitnessRuleMetadata",
    "FitnessRuleResult",
    "FitnessFailureRetryFeedbackEnvelope",
    "FitnessRunSummary",
    "MAX_FAILED_RULES",
    "MAX_REQUIRED_ACTIONS",
    "MAX_RULE_VIOLATIONS",
    "RetryFeedbackEnvelope",
    "ReviewerDecisionPayload",
    "ReviewerFeedbackRetryEnvelope",
    "RuleAdapter",
    "RuleSeverity",
    "RuleSource",
    "RuleStatus",
    "build_command_failure_retry_feedback",
    "build_fitness_failure_retry_feedback",
    "build_reviewer_feedback_retry_feedback",
    "build_rule_catalog",
    "custom_manifest_path",
    "emit_fitness_result",
    "emit_result_envelope",
    "execute_rule_definition",
    "load_custom_rule_definitions",
    "load_custom_rule_manifest",
    "parse_retry_feedback_envelope",
    "render_rule_catalog_markdown",
    "run_checks",
    "run_rule_catalog",
    "run_validate",
    "serialize_retry_feedback_envelope",
    "write_rule_catalog_markdown",
]
