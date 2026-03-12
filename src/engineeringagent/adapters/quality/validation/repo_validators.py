from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from engineeringagent.specs import (
    ValidationIssue,
    feature_contract_issues,
    feature_storage_root,
    iter_feature_files,
    load_yaml,
    load_markdown_frontmatter,
    potential_features_contract_issues,
    resolve_feature_plan_path,
)
from engineeringagent.adapters.quality.validation.contracts import (
    ValidationContext,
    ValidationIssue as ValidatorIssue,
)
from engineeringagent.adapters.quality.validation.repo_policy_feature_ids import (
    FeatureIdInvariantContext,
    append_feature_id_invariant_issues,
)

DONE_ACTIVE_UNSUPPORTED_FILE = ".allow-done-active.txt"
_FIELD_SEGMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_ORIGINAL_MESSAGE_PREFIX_CODES: tuple[tuple[str, str], ...] = (
    ("validate: duplicate base feature id", "repo.policy.duplicate-base-id"),
    ("validate: git ls-files failed", "repo.policy.git-ls-files"),
)
_MESSAGE_PREFIX_CODES: tuple[tuple[str, str], ...] = (
    ("failed to parse YAML", "repo.policy.parse-yaml"),
    (
        "verification commands must be single-line strings",
        "repo.policy.verification-single-line",
    ),
    ("completed feature specs must be archived", "repo.policy.done-archival"),
    ("unsupported configuration file; remove", "repo.policy.unsupported-config-file"),
)


class _DoneArchivalPolicyContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    features_done_dir: Path
    project_root: Path


class RepoPolicyValidator:
    """Repo-owned static validator adapter for registry-based validate flow."""

    validator_id = "repo.policy"

    def validate(self, *, context: ValidationContext) -> tuple[ValidatorIssue, ...]:
        """Run repo validation and project legacy string messages into issues."""

        messages = run_repo_validation_messages(
            project_root=context.project_root,
            docs_root=context.docs_root,
            schema_only=context.schema_only,
        )
        return tuple(
            _repo_message_to_issue(message, validator_id=self.validator_id)
            for message in messages
        )


def run_repo_validation_messages(
    *,
    project_root: Path,
    docs_root: Path,
    schema_only: bool,
) -> tuple[str, ...]:
    """Return deterministic repo-owned validation messages."""

    messages: list[str] = []
    run_repo_validation(
        messages,
        project_root=project_root,
        docs_root=docs_root,
        schema_only=schema_only,
    )
    return tuple(messages)


def _repo_message_to_issue(message: str, *, validator_id: str) -> ValidatorIssue:
    """Parse legacy repo message lines into structured ValidationIssue values."""

    path, rendered_message = _split_message_path(message)
    return ValidatorIssue(
        validator_id=validator_id,
        scope="repo",
        path=path,
        message=rendered_message,
        code=_repo_issue_code(
            path=path,
            message=rendered_message,
            original_message=message,
        ),
    )


def _repo_issue_code(*, path: str, message: str, original_message: str) -> str:
    """Derive deterministic repo policy issue codes without changing CLI output."""

    code = _first_matching_code(original_message, _ORIGINAL_MESSAGE_PREFIX_CODES)
    if code:
        return code

    code = _first_matching_code(message, _MESSAGE_PREFIX_CODES)
    if code:
        return code

    _, separator, field_segment = path.rpartition(":")
    if separator and _FIELD_SEGMENT_PATTERN.match(field_segment):
        return f"repo.policy.field-{field_segment.lower().replace('_', '-')}"

    return "repo.policy.message"


def _first_matching_code(
    value: str,
    candidates: tuple[tuple[str, str], ...],
) -> str | None:
    """Return the first code whose prefix matches the given value."""

    for prefix, code in candidates:
        if value.startswith(prefix):
            return code
    return None


def _first_contains_code(
    value: str,
    candidates: tuple[tuple[str, str], ...],
) -> str | None:
    """Return the first code whose token is present in the given value."""

    for token, code in candidates:
        if token in value:
            return code
    return None


def _split_message_path(message: str) -> tuple[str, str]:
    """Return structured (path, message) when a repo issue line has a path prefix."""

    if message.startswith("validate: "):
        return "", message

    prefix, separator, detail = message.partition(": ")
    if not separator:
        return "", message
    if not _looks_like_issue_path(prefix):
        return "", message
    return prefix, detail


def _looks_like_issue_path(path_text: str) -> bool:
    """Heuristic matcher for validate path-prefix text."""

    if not path_text:
        return False
    if "/" in path_text:
        return True
    if path_text.endswith((".yaml", ".yml", ".json", ".md", ".txt")):
        return True
    return False


def run_repo_validation(
    messages: list[str],
    *,
    project_root: Path,
    docs_root: Path,
    schema_only: bool,
) -> None:
    """Run repo-owned static validation checks in deterministic order."""

    spec_root = docs_root / "spec"
    features_dir = spec_root / "features"
    features_done_dir = spec_root / "features_done"
    potential_features_path = spec_root / "potential_features.yaml"

    files = iter_feature_files(features_dir)
    done_files = iter_feature_files(features_done_dir)
    archival_context = _DoneArchivalPolicyContext(
        features_done_dir=features_done_dir,
        project_root=project_root,
    )

    _append_flat_feature_entrypoint_issues(messages, features_dir)
    _append_flat_feature_entrypoint_issues(messages, features_done_dir)
    _append_unsupported_done_active_file_issues(messages, features_dir, project_root)
    append_feature_id_invariant_issues(
        messages,
        ctx=FeatureIdInvariantContext(
            active_files=files,
            done_files=done_files,
            project_root=project_root,
            features_dir=features_dir,
            features_done_dir=features_done_dir,
        ),
    )
    _append_active_feature_issues(
        messages,
        files,
        schema_only,
        archival_context,
    )
    _append_done_feature_issues(messages, done_files)
    _append_potential_features_issues(messages, potential_features_path)


def _append_flat_feature_entrypoint_issues(
    messages: list[str],
    features_dir: Path,
) -> None:
    for file_path in sorted(
        path
        for pattern in ("*.yaml", "*.yml")
        for path in features_dir.glob(pattern)
    ):
        messages.append(
            f"{file_path}: feature specs must use bundled spec.yaml entrypoints"
        )


def _append_active_feature_issues(
    messages: list[str],
    files: list[Path],
    schema_only: bool,
    archival_context: _DoneArchivalPolicyContext,
) -> None:
    for file_path in files:
        feature, contract_issues = _append_feature_contract_issues(messages, file_path)
        if feature is None:
            continue

        _append_multiline_verification_command_issues(messages, feature, file_path)

        if schema_only or contract_issues:
            continue
        _append_done_archival_policy_issue(
            messages,
            feature,
            file_path,
            archival_context,
        )


def _append_multiline_verification_command_issues(
    messages: list[str],
    feature: dict[str, object],
    file_path: Path,
) -> None:
    plan_path = resolve_feature_plan_path(file_path, feature)
    if plan_path is None or not plan_path.is_file():
        return

    try:
        frontmatter = load_markdown_frontmatter(plan_path)
    except (OSError, ValueError, yaml.YAMLError):
        return
    if not isinstance(frontmatter, dict):
        return

    phases = frontmatter.get("phases")
    if not isinstance(phases, list):
        return
    for phase_index, phase in enumerate(phases):
        if not isinstance(phase, dict):
            continue
        verification = phase.get("verification")
        _append_multiline_command_messages(
            messages,
            verification=verification,
            file_path=plan_path,
            field_path=f"phases[{phase_index}].verification",
        )


def _append_multiline_command_messages(
    messages: list[str],
    *,
    verification: object,
    file_path: Path,
    field_path: str,
) -> None:
    if not isinstance(verification, list):
        return

    for verify_index, command in enumerate(verification):
        if not isinstance(command, str):
            continue
        if "\n" not in command and "\r" not in command:
            continue

        messages.append(
            f"{file_path}:{field_path}[{verify_index}]: verification commands must be single-line strings (no \\n or \\r); "
            "remediation: rewrite the command as a one-liner (e.g. wrap with `bash -lc ...`)"
            )


def _append_done_feature_issues(messages: list[str], done_files: list[Path]) -> None:
    for file_path in done_files:
        _append_feature_contract_issues(messages, file_path)


def _append_potential_features_issues(
    messages: list[str], potential_features_path: Path
) -> None:
    _append_yaml_contract_issues(
        messages,
        potential_features_path,
        potential_features_contract_issues,
    )


def _append_yaml_contract_issues(
    messages: list[str],
    file_path: Path,
    contract_issue_builder: Callable[[dict[str, object], Path], list[ValidationIssue]],
) -> None:
    if not file_path.exists():
        return

    payload = _load_yaml_or_record_error(messages, file_path)
    if payload is None:
        return

    contract_issues = contract_issue_builder(payload, file_path)
    _extend_messages_with_contract_issues(messages, contract_issues)


def _load_yaml_or_record_error(
    messages: list[str], file_path: Path
) -> dict[str, object] | None:
    try:
        return load_yaml(file_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        messages.append(f"{file_path}: failed to parse YAML: {exc}")
        return None


def _append_feature_contract_issues(
    messages: list[str],
    file_path: Path,
    issue_filter: Callable[[list[ValidationIssue]], list[ValidationIssue]]
    | None = None,
) -> tuple[dict[str, object] | None, list[ValidationIssue]]:
    feature = _load_yaml_or_record_error(messages, file_path)
    if feature is None:
        return None, []

    contract_issues = feature_contract_issues(feature, file_path)
    if issue_filter is not None:
        contract_issues = issue_filter(contract_issues)

    _extend_messages_with_contract_issues(messages, contract_issues)
    return feature, contract_issues


def _extend_messages_with_contract_issues(
    messages: list[str], contract_issues: list[ValidationIssue]
) -> None:
    for issue in contract_issues:
        messages.append(f"{issue.path}: {issue.message}")


def _append_done_archival_policy_issue(
    messages: list[str],
    feature: dict[str, object],
    file_path: Path,
    archival_context: _DoneArchivalPolicyContext,
) -> None:
    if feature.get("status") != "done":
        return

    storage_root = feature_storage_root(file_path)
    if storage_root == file_path:
        expected_archive_path = archival_context.features_done_dir / file_path.name
    else:
        expected_archive_path = archival_context.features_done_dir / storage_root.name
        expected_archive_path = expected_archive_path / file_path.name
    messages.append(
        f"{file_path}:status: completed feature specs must be archived under "
        f"{expected_archive_path.relative_to(archival_context.project_root)}; move this file there"
    )


def _append_unsupported_done_active_file_issues(
    messages: list[str], features_dir: Path, project_root: Path
) -> None:
    unsupported_path = features_dir / DONE_ACTIVE_UNSUPPORTED_FILE
    if not unsupported_path.exists():
        return

    messages.append(
        f"{unsupported_path}: unsupported configuration file; remove "
        f"{unsupported_path.relative_to(project_root)} because completed specs in "
        "active features are never allowlisted"
    )
