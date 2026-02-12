from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class ValidationIssue:
    path: str
    message: str


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping at top level")
    return data


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=False)


def iter_feature_files(features_dir: Path) -> list[Path]:
    return sorted(features_dir.glob("*.yaml"))


def load_schema(schema_path: Path) -> dict[str, Any]:
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def schema_issues(feature: dict[str, Any], schema: dict[str, Any], file_path: Path) -> list[ValidationIssue]:
    validator = Draft202012Validator(schema)
    issues: list[ValidationIssue] = []
    for error in sorted(validator.iter_errors(feature), key=lambda e: str(e.path)):
        path_parts = [str(p) for p in error.absolute_path]
        path = ".".join(path_parts) if path_parts else "<root>"
        issues.append(ValidationIssue(path=f"{file_path}:{path}", message=error.message))
    return issues


def custom_issues(feature: dict[str, Any], file_path: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    subtasks = feature.get("subtasks", [])

    subtask_ids: set[str] = set()
    subtask_orders: set[int] = set()
    in_progress_count = 0
    done_count = 0

    for idx, subtask in enumerate(subtasks):
        sid = subtask.get("id")
        status = subtask.get("status")
        order = subtask.get("order")
        prefix = f"subtasks[{idx}]"

        if sid in subtask_ids:
            issues.append(ValidationIssue(path=f"{file_path}:{prefix}.id", message=f"duplicate subtask id: {sid}"))
        subtask_ids.add(sid)

        if order in subtask_orders:
            issues.append(ValidationIssue(path=f"{file_path}:{prefix}.order", message=f"duplicate order: {order}"))
        subtask_orders.add(order)

        if status == "in_progress":
            in_progress_count += 1
        if status == "done":
            done_count += 1

    if in_progress_count > 1:
        issues.append(
            ValidationIssue(
                path=f"{file_path}:subtasks",
                message="at most one subtask can be in_progress per feature",
            )
        )

    feature_status = feature.get("status")
    subtask_count = len(subtasks)
    all_done = subtask_count > 0 and done_count == subtask_count
    any_in_progress = in_progress_count > 0

    if feature_status == "done" and not all_done:
        issues.append(
            ValidationIssue(
                path=f"{file_path}:status",
                message="feature status done requires all subtasks done",
            )
        )

    if any_in_progress and feature_status != "in_progress":
        issues.append(
            ValidationIssue(
                path=f"{file_path}:status",
                message="feature with in_progress subtask must be in_progress",
            )
        )

    if all_done and feature_status != "done":
        issues.append(
            ValidationIssue(
                path=f"{file_path}:status",
                message="feature with all subtasks done must be done",
            )
        )

    return issues


def feature_sort_key(feature: dict[str, Any]) -> tuple[int, str]:
    priority = feature.get("priority", "medium")
    return (PRIORITY_ORDER.get(priority, 1), str(feature.get("id", "")))


def find_subtask(feature: dict[str, Any], status: str) -> dict[str, Any] | None:
    subtasks = feature.get("subtasks", [])
    matches = [s for s in subtasks if s.get("status") == status]
    if not matches:
        return None
    return sorted(matches, key=lambda s: int(s.get("order", 1_000_000)))[0]
