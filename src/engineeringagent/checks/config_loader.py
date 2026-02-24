from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

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
    """Load and validate `harness/checks.yaml` with deterministic errors."""
    checks_path = project_root / "harness" / "checks.yaml"
    if not checks_path.exists():
        return (
            None,
            f"{error_prefix}: missing harness/checks.yaml{missing_context}. "
            "Remediation: run `engineeringagent init`.",
        )

    try:
        payload = load_yaml(checks_path)
        issues = checks_contract_issues(payload, checks_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return None, f"{error_prefix}: failed to load harness/checks.yaml: {exc}"

    if issues:
        rendered = "\n".join(f"- {issue.path}: {issue.message}" for issue in issues)
        return None, f"{error_prefix}: invalid harness/checks.yaml\n{rendered}"

    try:
        doc = HarnessChecksDocument.model_validate(payload)
    except ValidationError as exc:
        return None, f"{error_prefix}: failed to validate harness/checks.yaml: {exc}"

    return doc, None
