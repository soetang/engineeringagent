from __future__ import annotations

import re
from pathlib import Path

from .config import resolve_docs_root
from .fitness import build_rule_catalog
from .specs import (
    ValidationIssue,
    feature_contract_issues,
    feature_schema_from_model,
    gate_contract_issues,
    iter_feature_files,
    load_schema,
    load_yaml,
    potential_features_contract_issues,
)


DONE_TRANSITION_ALLOWLIST = ".allow-done-active.txt"
LEGACY_DONE_OPTIONAL_FIELDS = {"type", "expected_commit_subject"}
AGENTS_DOCS_MAP_SECTION_TITLE = "Documentation Layout Reference"
AGENTS_PATH = Path("AGENTS.md")

_BACKTICK_TOKEN_PATTERN = re.compile(r"`([^`]+)`")


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
    docs_root = resolve_docs_root(project_root)
    spec_root = docs_root / "spec"
    features_dir = spec_root / "features"
    features_done_dir = spec_root / "features_done"
    schema_path = spec_root / "schemas" / "feature.schema.json"
    potential_features_path = spec_root / "potential_features.yaml"
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
                    expected_archive_path = features_done_dir / feature_name
                    allowlist_path = features_dir / DONE_TRANSITION_ALLOWLIST
                    messages.append(
                        f"{file_path}:status: completed feature specs must be archived under "
                        f"{expected_archive_path.relative_to(project_root)}; move this file there or "
                        f"add '{feature_name}' to {allowlist_path.relative_to(project_root)} "
                        "as a temporary transition exception"
                    )

    for file_path in done_files:
        try:
            feature = load_yaml(file_path)
        except Exception as exc:  # noqa: BLE001
            messages.append(f"{file_path}: failed to parse YAML: {exc}")
            continue

        contract_issues = _filter_legacy_done_contract_issues(
            feature_contract_issues(feature, file_path)
        )
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

    docs_map_section_line = _agents_docs_map_section_line(project_root)
    docs_map_references = _iter_agents_docs_map_references(project_root)
    if docs_map_section_line is not None and not docs_map_references:
        messages.append(
            f"AGENTS.md:{docs_map_section_line}: docs-map section is present but contains no docs/* references"
        )

    for line_number, reference in docs_map_references:
        if _is_glob_reference(reference):
            if any(project_root.glob(reference)):
                continue
            messages.append(
                f"AGENTS.md:{line_number}: docs-map glob matches no paths: {reference}"
            )
            continue

        if not (project_root / reference).exists():
            messages.append(
                f"AGENTS.md:{line_number}: docs-map path does not exist: {reference}"
            )

    try:
        build_rule_catalog(project_root)
    except ValueError as exc:
        messages.append(str(exc))

    return messages


def _iter_agents_docs_map_references(project_root: Path) -> list[tuple[int, str]]:
    """Extract documentation map references from AGENTS.md only.

    Args:
        project_root: Repository root containing AGENTS.md.

    Returns:
        Sorted list of (line number, docs reference) tuples from the documentation map
        section only.
    """
    agents_path = project_root / AGENTS_PATH
    if not agents_path.exists():
        return []

    lines = agents_path.read_text(encoding="utf-8").splitlines()
    section_start = _find_agents_docs_map_section_start(lines)
    if section_start is None:
        return []

    references: list[tuple[int, str]] = []
    for line_number, line in enumerate(
        lines[section_start + 1 :], start=section_start + 2
    ):
        if line.startswith("## "):
            break
        references.extend((line_number, token) for token in _iter_docs_references(line))

    return sorted(references, key=lambda entry: (entry[0], entry[1]))


def _agents_docs_map_section_line(project_root: Path) -> int | None:
    agents_path = project_root / AGENTS_PATH
    if not agents_path.exists():
        return None

    lines = agents_path.read_text(encoding="utf-8").splitlines()
    section_start = _find_agents_docs_map_section_start(lines)
    if section_start is None:
        return None
    return section_start + 1


def _find_agents_docs_map_section_start(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if _is_agents_docs_map_header(line):
            return index
    return None


def _is_agents_docs_map_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("## "):
        return False

    heading = stripped[3:].strip()
    numbered_prefix, separator, remainder = heading.partition(")")
    if separator and numbered_prefix.isdigit():
        heading = remainder.strip()
    return heading == AGENTS_DOCS_MAP_SECTION_TITLE


def _iter_docs_references(line: str) -> list[str]:
    return [
        token
        for token in _BACKTICK_TOKEN_PATTERN.findall(line)
        if token.startswith("docs/")
    ]


def _is_glob_reference(reference: str) -> bool:
    return any(char in reference for char in "*?[]")


def _filter_legacy_done_contract_issues(
    issues: list[ValidationIssue],
) -> list[ValidationIssue]:
    """Drop transitional required-field errors for legacy archived specs."""
    filtered: list = []
    for issue in issues:
        field = issue.path.rsplit(":", maxsplit=1)[-1]
        if field in LEGACY_DONE_OPTIONAL_FIELDS and issue.message == "Field required":
            continue
        filtered.append(issue)
    return filtered
