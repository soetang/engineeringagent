from __future__ import annotations

from pathlib import Path

from .specs import custom_issues, iter_feature_files, load_schema, load_yaml, schema_issues


def validate(project_root: Path, schema_only: bool = False) -> list[str]:
    features_dir = project_root / "docs" / "spec" / "features"
    schema_path = project_root / "docs" / "spec" / "schemas" / "feature.schema.json"

    schema = load_schema(schema_path)
    files = iter_feature_files(features_dir)
    messages: list[str] = []

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

    return messages
