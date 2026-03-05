from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from engineeringagent.config import (
    repo_relative_label,
    resolve_harness_checks_config_path,
)
from engineeringagent.specs import (
    HarnessChecksDocument,
    checks_contract_issues,
    load_yaml,
)


def load_harness_checks_document(
    project_root: Path,
    *,
    error_prefix: str,
    missing_context: str = "",
) -> tuple[HarnessChecksDocument | None, str | None]:
    """Load and validate resolved checks config path with deterministic errors."""
    try:
        checks_path = resolve_harness_checks_config_path(project_root)
    except ValueError as exc:
        return None, f"{error_prefix}: {exc}"

    checks_label = repo_relative_label(project_root, checks_path)
    if not checks_path.exists():
        return (
            None,
            f"{error_prefix}: missing {checks_label}{missing_context}. "
            "Remediation: run `engineeringagent init`.",
        )

    try:
        payload = load_yaml(checks_path)
        issues = checks_contract_issues(payload, checks_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return None, f"{error_prefix}: failed to load {checks_label}: {exc}"

    if issues:
        rendered = "\n".join(f"- {issue.path}: {issue.message}" for issue in issues)
        return None, f"{error_prefix}: invalid {checks_label}\n{rendered}"

    try:
        doc = HarnessChecksDocument.model_validate(payload)
    except ValidationError as exc:
        return None, f"{error_prefix}: failed to validate {checks_label}: {exc}"

    return doc, None
