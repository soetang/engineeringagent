from __future__ import annotations

from pathlib import Path

from .specs import (
    feature_contract_issues,
    feature_schema_from_model,
    gate_contract_issues,
    iter_feature_files,
    load_schema,
    load_yaml,
    potential_features_contract_issues,
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
    """Validate active feature files against strict feature contracts.

    Args:
        project_root: Repository root containing docs/spec artifacts.
        schema_only: Whether to skip done-spec archival policy checks.

    Returns:
        Validation error messages; empty list means success.
    """
    features_dir = project_root / "docs" / "spec" / "features"
    features_done_dir = project_root / "docs" / "spec" / "features_done"
    schema_path = project_root / "docs" / "spec" / "schemas" / "feature.schema.json"
    potential_features_path = project_root / "docs" / "spec" / "potential_features.yaml"
    gates_path = project_root / "harness" / "gates.yaml"

    files = iter_feature_files(features_dir)
    done_files = iter_feature_files(features_done_dir)
    messages: list[str] = []
    done_transition_allowlist = _load_done_transition_allowlist(features_dir)

    if schema_path.exists():
        try:
            current_schema = load_schema(schema_path)
        except Exception as exc:  # noqa: BLE001
            messages.append(f"{schema_path}: failed to parse JSON schema: {exc}")
        else:
            generated_schema = feature_schema_from_model()
            if current_schema != generated_schema:
                messages.append(
                    f"{schema_path}:<root>: schema artifact is out of sync with "
                    "FeatureSpec model"
                )

    for file_path in files:
        try:
            feature = load_yaml(file_path)
        except Exception as exc:  # noqa: BLE001
            messages.append(f"{file_path}: failed to parse YAML: {exc}")
            continue

        contract_issues = feature_contract_issues(feature, file_path)
        for issue in contract_issues:
            messages.append(f"{issue.path}: {issue.message}")

        if not schema_only and not contract_issues:
            if feature.get("status") == "done":
                feature_name = file_path.name
                if feature_name not in done_transition_allowlist:
                    messages.append(
                        f"{file_path}:status: completed feature specs must be archived under "
                        f"docs/spec/features_done/{feature_name}; move this file there or "
                        f"add '{feature_name}' to docs/spec/features/{DONE_TRANSITION_ALLOWLIST} "
                        "as a temporary transition exception"
                    )

    for file_path in done_files:
        try:
            feature = load_yaml(file_path)
        except Exception as exc:  # noqa: BLE001
            messages.append(f"{file_path}: failed to parse YAML: {exc}")
            continue

        contract_issues = feature_contract_issues(feature, file_path)
        for issue in contract_issues:
            messages.append(f"{issue.path}: {issue.message}")

    if potential_features_path.exists():
        try:
            potential_features = load_yaml(potential_features_path)
        except Exception as exc:  # noqa: BLE001
            messages.append(f"{potential_features_path}: failed to parse YAML: {exc}")
        else:
            contract_issues = potential_features_contract_issues(
                potential_features,
                potential_features_path,
            )
            for issue in contract_issues:
                messages.append(f"{issue.path}: {issue.message}")

    if gates_path.exists():
        try:
            gates_config = load_yaml(gates_path)
        except Exception as exc:  # noqa: BLE001
            messages.append(f"{gates_path}: failed to parse YAML: {exc}")
        else:
            contract_issues = gate_contract_issues(gates_config, gates_path)
            for issue in contract_issues:
                messages.append(f"{issue.path}: {issue.message}")

    return messages
