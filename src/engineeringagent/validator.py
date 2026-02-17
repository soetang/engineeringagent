from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from .config import resolve_allow_duplicate_done_base_ids_below, resolve_docs_root
from .fitness import build_rule_catalog
from .git import client as git_client
from .reviewers import REVIEWER_RESPONSEFORMAT_PLACEHOLDER
from .specs import (
    ValidationIssue,
    feature_contract_issues,
    feature_schema_from_model,
    gate_contract_issues,
    iter_feature_files,
    load_schema,
    load_yaml,
    potential_features_contract_issues,
    reviewer_contract_issues,
)


DONE_ACTIVE_UNSUPPORTED_FILE = ".allow-done-active.txt"
LEGACY_DONE_OPTIONAL_FIELDS = {"type", "expected_commit_subject"}
AGENTS_DOCS_MAP_SECTION_TITLE = "Documentation Layout Reference"
AGENTS_PATH = Path("AGENTS.md")
REVIEWER_PROMPTS_DIR = Path("harness") / "reviewers" / "prompts"

_BACKTICK_TOKEN_PATTERN = re.compile(r"`([^`]+)`")
_SPEC_ID_PATTERN = re.compile(r"^(?P<prefix>[A-Z]+)-(?P<num>[0-9]+)$")


class _DoneArchivalPolicyContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    features_done_dir: Path
    project_root: Path


class _FeatureIdInvariantContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    active_files: list[Path]
    done_files: list[Path]
    project_root: Path
    features_dir: Path
    features_done_dir: Path
    threshold: int | None


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
    reviewers_path = project_root / "harness" / "reviewers.yaml"
    reviewer_prompts_dir = project_root / REVIEWER_PROMPTS_DIR

    files = iter_feature_files(features_dir)
    done_files = iter_feature_files(features_done_dir)
    messages: list[str] = []
    archival_context = _DoneArchivalPolicyContext(
        features_done_dir=features_done_dir,
        project_root=project_root,
    )

    _append_schema_sync_issues(messages, schema_path)
    _append_unsupported_done_active_file_issues(messages, features_dir, project_root)
    threshold = resolve_allow_duplicate_done_base_ids_below(project_root)
    _append_feature_id_invariant_issues(
        messages,
        ctx=_FeatureIdInvariantContext(
            active_files=files,
            done_files=done_files,
            project_root=project_root,
            features_dir=features_dir,
            features_done_dir=features_done_dir,
            threshold=threshold,
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
    _append_legacy_harness_contract_file_issues(
        messages,
        project_root=project_root,
        gates_path=gates_path,
        reviewers_path=reviewers_path,
    )
    _append_reviewer_prompt_issues(messages, reviewer_prompts_dir)
    _append_agents_docs_map_issues(messages, project_root)
    _append_fitness_catalog_issues(messages, project_root)
    _append_purge_invariant_issues(messages, project_root)
    _append_opencode_config_invariant_issues(messages, project_root)

    return messages


def _append_feature_id_invariant_issues(
    messages: list[str],
    *,
    ctx: _FeatureIdInvariantContext,
) -> None:
    """Enforce feature id uniqueness and filename/frontmatter alignment."""

    entries = _collect_feature_id_entries(messages, ctx)
    duplicates = _duplicate_base_id_occurrences(entries)
    if not duplicates:
        return
    _append_duplicate_base_id_messages(messages, duplicates, ctx.threshold)


def _collect_feature_id_entries(
    messages: list[str],
    ctx: _FeatureIdInvariantContext,
) -> list[tuple[tuple[str, int], str, str, bool]]:
    """Return (base_id, relpath, raw_id, is_done) entries for each feature spec."""

    entries: list[tuple[tuple[str, int], str, str, bool]] = []
    all_files = sorted(
        [*ctx.active_files, *ctx.done_files],
        key=lambda path: path.as_posix(),
    )
    for file_path in all_files:
        entry = _feature_id_entry_from_file(messages, file_path, ctx)
        if entry is None:
            continue
        entries.append(entry)
    return entries


def _feature_id_entry_from_file(
    messages: list[str],
    file_path: Path,
    ctx: _FeatureIdInvariantContext,
) -> tuple[tuple[str, int], str, str, bool] | None:
    payload = _load_yaml_or_record_error(messages, file_path)
    if payload is None:
        return None

    raw_id = payload.get("id")
    if not isinstance(raw_id, str):
        return None

    rel = _relpath(ctx.project_root, file_path)
    filename_token = _filename_id_token(file_path)
    if filename_token is None:
        messages.append(
            f"{rel}:id: failed to extract filename id token (expected '<PREFIX>-<NUM>' prefix)"
        )
    elif filename_token != raw_id:
        messages.append(
            f"{rel}:id: filename id token {filename_token} does not match frontmatter id {raw_id}"
        )

    base_id = _normalized_base_id(raw_id)
    if base_id is None:
        return None

    is_done = _is_under(file_path, ctx.features_done_dir)
    if not is_done and not _is_under(file_path, ctx.features_dir):
        # External path; ignore scope classification.
        is_done = False
    return (base_id, rel, raw_id, is_done)


def _duplicate_base_id_occurrences(
    entries: list[tuple[tuple[str, int], str, str, bool]],
) -> dict[tuple[str, int], list[tuple[str, str, bool]]]:
    occurrences: dict[tuple[str, int], list[tuple[str, str, bool]]] = {}
    for base_id, rel, raw_id, is_done in entries:
        occurrences.setdefault(base_id, []).append((rel, raw_id, is_done))
    return {base_id: specs for base_id, specs in occurrences.items() if len(specs) > 1}


def _append_duplicate_base_id_messages(
    messages: list[str],
    duplicates: dict[tuple[str, int], list[tuple[str, str, bool]]],
    threshold: int | None,
) -> None:
    for base_id in sorted(duplicates, key=lambda entry: (entry[0], entry[1])):
        specs = sorted(duplicates[base_id], key=lambda entry: (entry[0], entry[1]))
        base_id_text = _format_base_id(base_id)

        active_specs = [spec for spec in specs if not spec[2]]
        done_specs = [spec for spec in specs if spec[2]]
        if active_specs:
            messages.append(
                _duplicate_base_id_message_active(
                    base_id_text,
                    active_specs=active_specs,
                    done_specs=done_specs,
                )
            )
            continue

        # Done-only collision.
        numeric_id = base_id[1]
        if threshold is not None and numeric_id < threshold:
            continue
        messages.append(
            _duplicate_base_id_message_done_only(
                base_id_text,
                done_specs=done_specs,
            )
        )


def _duplicate_base_id_message_active(
    base_id_text: str,
    *,
    active_specs: list[tuple[str, str, bool]],
    done_specs: list[tuple[str, str, bool]],
) -> str:
    active_labels = ", ".join(
        f"{rel} (id {raw_id})" for rel, raw_id, _is_done in active_specs
    )
    if done_specs:
        done_labels = ", ".join(
            f"{rel} (id {raw_id})" for rel, raw_id, _is_done in done_specs
        )
        return (
            f"validate: duplicate base feature id {base_id_text} found across active and done specs; "
            f"active: {active_labels}; done: {done_labels}; "
            "remediation: rename/re-id active feature specs under docs/spec/features/ to make ids globally unique"
        )
    return (
        f"validate: duplicate base feature id {base_id_text} found in active specs: {active_labels}; "
        "remediation: rename/re-id active feature specs under docs/spec/features/ to make ids globally unique"
    )


def _duplicate_base_id_message_done_only(
    base_id_text: str,
    *,
    done_specs: list[tuple[str, str, bool]],
) -> str:
    done_labels = ", ".join(
        f"{rel} (id {raw_id})" for rel, raw_id, _is_done in done_specs
    )
    opt_out = "[tool.engineeringagent.specs] allow-duplicate-done-base-ids-below = <N>"
    return (
        f"validate: duplicate base feature id {base_id_text} found in archived done specs: {done_labels}; "
        "remediation: rename/re-id archived specs to remove duplicates; "
        f"legacy opt-out: set `{opt_out}` to allow duplicates for archived specs only "
        "(does not apply to active specs; only ids below the threshold)"
    )


def _filename_id_token(file_path: Path) -> str | None:
    stem = file_path.name
    if stem.endswith(".yaml"):
        stem = stem[: -len(".yaml")]
    parts = stem.split("-")
    if len(parts) < 2:
        return None
    return f"{parts[0]}-{parts[1]}"


def _normalized_base_id(raw_id: str) -> tuple[str, int] | None:
    match = _SPEC_ID_PATTERN.match(raw_id)
    if match is None:
        return None
    try:
        numeric_id = int(match.group("num"))
    except ValueError:
        return None
    return (match.group("prefix"), numeric_id)


def _format_base_id(base_id: tuple[str, int]) -> str:
    prefix, numeric_id = base_id
    return f"{prefix}-{numeric_id}"


def _relpath(project_root: Path, file_path: Path) -> str:
    try:
        return file_path.relative_to(project_root).as_posix()
    except ValueError:
        return file_path.as_posix()


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _append_opencode_config_invariant_issues(
    messages: list[str],
    project_root: Path,
) -> None:
    """Fail validation when repo-root OpenCode config becomes a dependency again.

    Policy/configuration for OpenCode is intentionally shipped via
    `.opencode/agents/engineeringagent.md` and invoked explicitly with
    `opencode run --agent engineeringagent`.

    We enforce two invariants:
    - The repository must not track a repo-root OpenCode config file.
    - Active tracked files outside tests/specs must not reference it.

    Notes:
    - This check is repository hygiene, not a runtime requirement: contributors may
      still keep local untracked files.
    """

    if not (project_root / ".git").exists():
        return

    proc = git_client.ls_files(project_root)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        detail = f": {stderr}" if stderr else ""
        messages.append(f"validate: git ls-files failed{detail}")
        return

    needle = ".".join(["opencode", "json"])
    needle_blob = needle.encode("utf-8")
    allowed_prefixes = (
        "tests/",
        "docs/spec/",
        "progress/",
    )

    for rel in (line.strip() for line in (proc.stdout or "").splitlines()):
        if not rel:
            continue

        if rel == needle:
            messages.append(
                f"{rel}: repo-root OpenCode config is not supported; use .opencode/agents/engineeringagent.md"
            )
            continue

        if rel.startswith(allowed_prefixes):
            continue

        path = project_root / rel
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        if needle_blob in payload:
            messages.append(
                f"{rel}: forbidden token present (opencode config invariant): {needle}"
            )


def _append_purge_invariant_issues(messages: list[str], project_root: Path) -> None:  # noqa: C901
    """Fail validation when removed identifiers reappear in active tracked files."""

    if not (project_root / ".git").exists():
        return

    forbidden_needles = _purge_forbidden_needles()
    if not forbidden_needles:
        return

    proc = git_client.ls_files(project_root)

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        detail = f": {stderr}" if stderr else ""
        messages.append(f"validate: git ls-files failed{detail}")
        return

    excluded_prefixes = (
        "docs/spec/features_done/",
        "progress/",
    )
    needles = tuple(forbidden_needles)
    needle_bytes = tuple(needle.encode("utf-8") for needle in needles)

    for rel in (line.strip() for line in (proc.stdout or "").splitlines()):
        if not rel:
            continue
        if rel.endswith("/"):
            continue
        if rel.startswith(excluded_prefixes):
            continue

        path = project_root / rel
        try:
            payload = path.read_bytes()
        except OSError:
            continue

        for needle, needle_blob in zip(needles, needle_bytes, strict=True):
            if needle_blob in payload:
                messages.append(
                    f"{rel}: forbidden token present (purge invariant): {needle}"
                )
                break


def _purge_forbidden_needles() -> list[str]:
    """Return the forbidden identifiers without embedding them verbatim in source."""

    removed_reviewer_id = "_".join(["readme", "process"])
    removed_sandbox_mode = "_".join(["clean", "room", "readme", "cli"])
    return [removed_reviewer_id, removed_sandbox_mode]


def _append_schema_sync_issues(messages: list[str], schema_path: Path) -> None:
    if not schema_path.exists():
        return

    try:
        current_schema = load_schema(schema_path)
    except Exception as exc:  # noqa: BLE001
        messages.append(f"{schema_path}: failed to parse JSON schema: {exc}")
        return

    generated_schema = feature_schema_from_model()
    if current_schema != generated_schema:
        messages.append(
            f"{schema_path}:<root>: schema artifact is out of sync with "
            "FeatureSpec model"
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

        if schema_only or contract_issues:
            continue
        _append_done_archival_policy_issue(
            messages,
            feature,
            file_path,
            archival_context,
        )


def _append_done_feature_issues(messages: list[str], done_files: list[Path]) -> None:
    for file_path in done_files:
        _append_feature_contract_issues(
            messages,
            file_path,
            issue_filter=_filter_legacy_done_contract_issues,
        )


def _append_potential_features_issues(
    messages: list[str], potential_features_path: Path
) -> None:
    _append_yaml_contract_issues(
        messages,
        potential_features_path,
        potential_features_contract_issues,
    )


def _append_gate_config_issues(messages: list[str], gates_path: Path) -> None:
    _append_yaml_contract_issues(messages, gates_path, gate_contract_issues)


def _append_reviewer_config_issues(messages: list[str], reviewers_path: Path) -> None:
    _append_yaml_contract_issues(messages, reviewers_path, reviewer_contract_issues)


def _append_legacy_harness_contract_file_issues(
    messages: list[str],
    *,
    project_root: Path,
    gates_path: Path,
    reviewers_path: Path,
) -> None:
    """Fail validation when removed harness contract files are present.

    The repo-owned verification contract is `harness/checks.yaml`. Legacy harness
    contract files are intentionally not supported after migration.
    """

    legacy_paths = (gates_path, reviewers_path)
    for legacy_path in legacy_paths:
        if not legacy_path.exists():
            continue
        rel = legacy_path
        try:
            rel = legacy_path.relative_to(project_root)
        except ValueError:
            pass
        rel_text = rel.as_posix()
        messages.append(
            f"{rel_text}: legacy harness contract file is no longer supported; "
            "migrate to harness/checks.yaml and delete this file "
            "(remediation: run `engineeringagent init`)"
        )


def _append_reviewer_prompt_issues(
    messages: list[str], reviewer_prompts_dir: Path
) -> None:
    if not reviewer_prompts_dir.exists():
        return

    for prompt_path in _iter_reviewer_prompt_files(reviewer_prompts_dir):
        try:
            prompt_text = prompt_path.read_text(encoding="utf-8")
        except OSError as exc:
            messages.append(f"{prompt_path}: failed to read reviewer prompt: {exc}")
            continue

        if REVIEWER_RESPONSEFORMAT_PLACEHOLDER in prompt_text:
            continue
        messages.append(
            f"{prompt_path}: reviewer prompt must include `{REVIEWER_RESPONSEFORMAT_PLACEHOLDER}`"
        )


def _iter_reviewer_prompt_files(reviewer_prompts_dir: Path) -> list[Path]:
    return sorted(reviewer_prompts_dir.glob("*.md"), key=lambda path: path.as_posix())


def _append_agents_docs_map_issues(messages: list[str], project_root: Path) -> None:
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


def _append_fitness_catalog_issues(messages: list[str], project_root: Path) -> None:
    try:
        build_rule_catalog(project_root)
    except ValueError as exc:
        messages.append(str(exc))


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
    except Exception as exc:  # noqa: BLE001
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

    feature_name = file_path.name
    expected_archive_path = archival_context.features_done_dir / feature_name
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
