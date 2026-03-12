from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from engineeringagent.specs import load_yaml

_SPEC_ID_PATTERN = re.compile(r"^(?P<prefix>[A-Z]+)-(?P<num>[0-9]+)$")


class FeatureIdInvariantContext(BaseModel):
    """Immutable inputs required for feature-id invariant validation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    active_files: list[Path]
    done_files: list[Path]
    project_root: Path
    features_dir: Path
    features_done_dir: Path


def append_feature_id_invariant_issues(
    messages: list[str],
    *,
    ctx: FeatureIdInvariantContext,
) -> None:
    """Enforce feature id uniqueness and filename/frontmatter alignment."""

    entries = _collect_feature_id_entries(messages, ctx)
    duplicates = _duplicate_base_id_occurrences(entries)
    if not duplicates:
        return
    _append_duplicate_base_id_messages(messages, duplicates)


def _collect_feature_id_entries(
    messages: list[str],
    ctx: FeatureIdInvariantContext,
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
    ctx: FeatureIdInvariantContext,
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
    return (base_id, rel, raw_id, is_done)


def _load_yaml_or_record_error(
    messages: list[str], file_path: Path
) -> dict[str, object] | None:
    try:
        return load_yaml(file_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        messages.append(f"{file_path}: failed to parse YAML: {exc}")
        return None


def _duplicate_base_id_occurrences(
    entries: list[tuple[tuple[str, int], str, str, bool]],
) -> dict[tuple[str, int], list[tuple[str, str, bool]]]:
    occurrences: dict[tuple[str, int], list[tuple[str, str, bool]]] = {}
    for base_id, rel, raw_id, is_done in entries:
        specs = occurrences.setdefault(base_id, [])
        specs.append((rel, raw_id, is_done))
    return {base_id: specs for base_id, specs in occurrences.items() if len(specs) > 1}


def _append_duplicate_base_id_messages(
    messages: list[str],
    duplicates: dict[tuple[str, int], list[tuple[str, str, bool]]],
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
            "remediation: rename/re-id active feature specs under docs/specifications/features/ to make ids globally unique"
        )
    return (
        f"validate: duplicate base feature id {base_id_text} found in active specs: {active_labels}; "
        "remediation: rename/re-id active feature specs under docs/specifications/features/ to make ids globally unique"
    )


def _duplicate_base_id_message_done_only(
    base_id_text: str,
    *,
    done_specs: list[tuple[str, str, bool]],
) -> str:
    done_labels = ", ".join(
        f"{rel} (id {raw_id})" for rel, raw_id, _is_done in done_specs
    )
    return (
        f"validate: duplicate base feature id {base_id_text} found in archived done specs: {done_labels}; "
        "remediation: rename/re-id archived specs to remove duplicates"
    )


def _filename_id_token(file_path: Path) -> str | None:
    stem = file_path.name
    if stem == "spec.yaml":
        stem = file_path.parent.name
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
