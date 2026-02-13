from __future__ import annotations

from pathlib import Path

from .specs import (
    custom_issues,
    iter_feature_files,
    load_schema,
    load_yaml,
    schema_issues,
)


DONE_TRANSITION_ALLOWLIST = ".allow-done-active.txt"


def _load_done_transition_allowlist(features_dir: Path) -> set[str]:
    """Load explicit transition allowlist for done specs in active directory.

    Args:
        features_dir: Active features directory path.

    Returns:
        Basename entries explicitly allowed to remain in active specs temporarily.
    """
    allowlist_path = features_dir / DONE_TRANSITION_ALLOWLIST
    if not allowlist_path.exists():
        return set()

    entries: set[str] = set()
    for raw_line in allowlist_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        entries.add(Path(line).name)
    return entries


def validate(project_root: Path, schema_only: bool = False) -> list[str]:
    """Validate active feature files against schema and custom rules.

    Args:
        project_root: Repository root containing docs/spec artifacts.
        schema_only: Whether to skip repository-specific custom checks.

    Returns:
        Validation error messages; empty list means success.
    """
    features_dir = project_root / "docs" / "spec" / "features"
    schema_path = project_root / "docs" / "spec" / "schemas" / "feature.schema.json"

    schema = load_schema(schema_path)
    files = iter_feature_files(features_dir)
    messages: list[str] = []
    done_transition_allowlist = _load_done_transition_allowlist(features_dir)

    for file_path in files:
        try:
            feature = load_yaml(file_path)
        except Exception as exc:  # noqa: BLE001
            messages.append(f"{file_path}: failed to parse YAML: {exc}")
            continue

        for issue in schema_issues(feature, schema, file_path):
            messages.append(f"{issue.path}: {issue.message}")

        if not schema_only:
            for issue in custom_issues(feature, file_path):
                messages.append(f"{issue.path}: {issue.message}")

            if feature.get("status") == "done":
                feature_name = file_path.name
                if feature_name not in done_transition_allowlist:
                    messages.append(
                        f"{file_path}:status: completed feature specs must be archived under "
                        f"docs/spec/features_done/{feature_name}; move this file there or "
                        f"add '{feature_name}' to docs/spec/features/{DONE_TRANSITION_ALLOWLIST} "
                        "as a temporary transition exception"
                    )

    return messages
