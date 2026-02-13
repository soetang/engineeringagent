from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .gates import load_gate_config, run_profile
from .opencode_permissions import output_has_permission_rejection
from .specs import dump_yaml, feature_sort_key, load_yaml

FEATURE_TRANSITIONS: dict[str, set[str]] = {
    "backlog": {"backlog", "in_progress", "done"},
    "in_progress": {"in_progress", "blocked", "done"},
    "blocked": {"blocked", "in_progress", "done"},
    "done": {"done"},
}

STATUS_ORDER: dict[str, int] = {
    "in_progress": 0,
    "backlog": 1,
    "blocked": 2,
}

RUN_ALL_RUNNABLE_STATUSES: set[str] = {"backlog", "in_progress"}

FEATURE_TYPE_COMMIT_PREFIX: dict[str, str] = {
    "feature": "feat",
    "bug": "fix",
    "spec": "spec",
    "docs": "docs",
    "chore": "chore",
    "test": "test",
}


def _print_run_all_snapshot_banner(resolved_paths: Sequence[Path]) -> None:
    print(
        "[run --all] Startup snapshot captured "
        f"{len(resolved_paths)} runnable feature file(s) from docs/spec/features/*.yaml."
    )


def _print_run_all_no_work_message() -> None:
    print(
        "No runnable active features found for --all startup snapshot "
        "(statuses: backlog, in_progress)."
    )
    print_summary(None, "no_work", None, None, "stop")


@dataclass(frozen=True)
class IterationOutcome:
    completed: bool
    result: str
    failed_gate: str | None
    next_action: str
    hook_feedback: str | None
    log_path: str | None


def now_iso() -> str:
    """Return current UTC timestamp in compact ISO-8601 format.

    Returns:
        Current timestamp string with trailing Z suffix.
    """
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def append_run(log_path: Path, payload: dict[str, Any]) -> None:
    """Append a single loop telemetry record as JSONL.

    Args:
        log_path: Destination JSONL path.
        payload: Serializable telemetry mapping to append.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=True) + "\n")


def _sanitize_feature_id_for_log(feature_id: str) -> str:
    sanitized = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_" for char in feature_id
    ).strip("_")
    return sanitized or "unknown-feature"


def _resolve_feature_progress_log_path(project_root: Path, feature_id: str) -> Path:
    safe_feature_id = _sanitize_feature_id_for_log(feature_id)
    return project_root / "progress" / f"run-feature-{safe_feature_id}.txt"


def _append_feature_progress_log(log_path: Path, lines: Sequence[str]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file_handle:
        file_handle.write("\n".join(lines) + "\n")


def set_status(entity: dict[str, Any], target: str, kind: str = "feature") -> None:
    """Transition a feature or subtask status with guardrails.

    Args:
        entity: Mutable mapping containing a status field.
        target: Desired next status.
        kind: Entity label used in error messages.

    Raises:
        ValueError: If current status is unknown or transition is not allowed.
    """
    transitions = FEATURE_TRANSITIONS
    current = str(entity.get("status", ""))
    allowed = transitions.get(current)
    if not allowed:
        raise ValueError(f"{kind} has unknown status: {current}")
    if target not in allowed:
        raise ValueError(f"illegal {kind} status transition: {current} -> {target}")
    entity["status"] = target


def _resolve_feature_paths(
    project_root: Path, feature_paths: Sequence[str | Path]
) -> list[Path]:
    if not feature_paths:
        raise ValueError("at least one feature spec path is required")

    resolved: list[Path] = []
    seen: set[Path] = set()
    for raw_path in feature_paths:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (project_root / candidate).resolve()
        else:
            candidate = candidate.resolve()

        if candidate.suffix not in {".yaml", ".yml"}:
            raise ValueError(f"feature path must end with .yaml or .yml: {raw_path}")
        if not candidate.exists():
            raise ValueError(f"feature path does not exist: {raw_path}")
        if not candidate.is_file():
            raise ValueError(f"feature path is not a file: {raw_path}")

        try:
            load_yaml(candidate)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                f"failed to load feature YAML at {raw_path}: {exc}"
            ) from exc

        if candidate in seen:
            continue
        seen.add(candidate)
        resolved.append(candidate)

    return resolved


def _discover_active_feature_paths(project_root: Path) -> list[Path]:
    features_dir = project_root / "docs" / "spec" / "features"
    resolved: list[Path] = []
    for feature_path in sorted(features_dir.glob("*.yaml")):
        try:
            feature = load_yaml(feature_path)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                f"failed to load feature YAML at {feature_path}: {exc}"
            ) from exc

        if str(feature.get("status", "")) in RUN_ALL_RUNNABLE_STATUSES:
            resolved.append(feature_path)

    return resolved


def _pending_features(
    feature_paths: Sequence[Path],
) -> list[tuple[Path, dict[str, Any]]]:
    pending: list[tuple[Path, dict[str, Any]]] = []
    for feature_path in feature_paths:
        feature = load_yaml(feature_path)
        if feature.get("status") == "done":
            continue
        pending.append((feature_path, feature))
    return pending


def _load_selected_feature_with_archive_fallback(
    project_root: Path,
    feature_path: Path,
) -> tuple[dict[str, Any] | None, bool, str | None]:
    try:
        return (load_yaml(feature_path), False, None)
    except FileNotFoundError:
        try:
            archive_path = _resolve_archive_path(project_root, feature_path)
        except ValueError:
            return (
                None,
                False,
                (
                    "selected feature path disappeared during loop iteration and "
                    f"cannot be archive-resolved: {feature_path}"
                ),
            )

        if not archive_path.exists():
            return (
                None,
                False,
                (
                    "selected feature path disappeared during loop iteration: "
                    f"{feature_path}. Expected archived counterpart at {archive_path}."
                ),
            )

        try:
            archived_feature = load_yaml(archive_path)
        except Exception as exc:  # noqa: BLE001
            return (
                None,
                False,
                f"failed to load archived feature YAML at {archive_path}: {exc}",
            )

        print(
            "Selected feature path missing after iteration; "
            f"using archived counterpart at {archive_path}."
        )
        return (archived_feature, True, None)


def _deterministic_feature_choice(
    pending: Sequence[tuple[Path, dict[str, Any]]],
) -> tuple[Path, dict[str, Any]]:
    def sort_key(item: tuple[Path, dict[str, Any]]) -> tuple[int, int, str, str]:
        feature_path, feature = item
        status_rank = STATUS_ORDER.get(str(feature.get("status", "")), 99)
        priority_rank, feature_id = feature_sort_key(feature)
        return (status_rank, priority_rank, feature_id, str(feature_path))

    return sorted(pending, key=sort_key)[0]


def _build_selector_prompt(pending: Sequence[tuple[Path, dict[str, Any]]]) -> str:
    choices = []
    for feature_path, feature in pending:
        choices.append(
            f"- id={feature.get('id')} status={feature.get('status')} priority={feature.get('priority')} path={feature_path}"
        )

    return (
        "Choose the next feature spec to execute from this pending set. "
        "Reply with exactly one feature path from the list and no extra text.\n"
        + "\n".join(choices)
    )


def _parse_selector_output(
    output: str,
    pending: Sequence[tuple[Path, dict[str, Any]]],
) -> Path | None:
    text = output.strip()
    if not text:
        return None

    path_strings = {str(path): path for path, _ in pending}
    for path_str, path in path_strings.items():
        if path_str in text:
            return path

    by_name: dict[str, list[Path]] = {}
    by_id: dict[str, list[Path]] = {}
    for path, feature in pending:
        by_name.setdefault(path.name, []).append(path)
        feature_id = str(feature.get("id", "")).strip()
        if feature_id:
            by_id.setdefault(feature_id, []).append(path)

    tokens = [token.strip("`'\" ,") for token in text.replace("\n", " ").split(" ")]
    for token in tokens:
        if token in by_name and len(by_name[token]) == 1:
            return by_name[token][0]
        if token in by_id and len(by_id[token]) == 1:
            return by_id[token][0]
    return None


def _choose_feature_with_selector(
    project_root: Path,
    pending: Sequence[tuple[Path, dict[str, Any]]],
) -> tuple[Path, dict[str, Any]]:
    if len(pending) == 1:
        return pending[0]

    prompt = _build_selector_prompt(pending)
    try:
        proc = subprocess.run(
            ["opencode", "run", "--agent", "build", prompt],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        fallback = _deterministic_feature_choice(pending)
        print(f"Selector fallback: opencode missing; selected {fallback[1].get('id')}")
        return fallback

    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        chosen_path = _parse_selector_output(output, pending)
        if chosen_path is not None:
            chosen_feature = next(
                feature for path, feature in pending if path == chosen_path
            )
            return (chosen_path, chosen_feature)

    fallback = _deterministic_feature_choice(pending)
    print(
        f"Selector fallback: parse or command failure; selected {fallback[1].get('id')}"
    )
    return fallback


def git_head_short(project_root: Path) -> str | None:
    """Return short git HEAD hash for a repository.

    Args:
        project_root: Repository root used as command cwd.

    Returns:
        Short commit hash when available, otherwise None.
    """
    proc = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _truncate_feedback(text: str, max_chars: int = 8_000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


def build_ralph_opencode_prompt(
    feature: dict[str, Any],
    feature_path: Path,
    hook_feedback: str | None = None,
) -> str:
    """Build the default Ralph-style implementation prompt.

    Args:
        feature: Loaded feature mapping.
        feature_path: Absolute path to the feature YAML file.
        hook_feedback: Optional prior hook output to include for retries.

    Returns:
        Prompt text for the default OpenCode implement step.
    """
    fid = feature.get("id", "unknown-feature")
    feature_title = feature.get("title", "")
    objective = feature.get("objective", "")
    context = feature.get("context", "")
    prompt = (
        f"Read and use this feature spec from disk: {feature_path}. "
        f"Run one Ralph-style feature loop for {fid} ({feature_title}). "
        f"Objective: {objective}. Context: {context}. "
        "Derive the next step directly from the YAML file, make minimal deterministic changes, "
        "run relevant verification, and report concise results."
    )
    if hook_feedback:
        prompt += (
            " Previous retry feedback is available. "
            "Fix the issues reported below before marking the feature complete:\n"
            f"{_truncate_feedback(hook_feedback)}"
        )
    return prompt


def run_implement_step(
    project_root: Path,
    feature: dict[str, Any],
    feature_path: Path,
    implement_command: str | None,
    opencode_prompt: str | None,
    skip_implement: bool,
    hook_feedback: str | None,
    verbose_output: bool,
) -> tuple[bool, str | None, str]:
    """Run the implement phase for one loop iteration.

    Args:
        project_root: Repository root used for command execution.
        feature: Loaded feature mapping.
        feature_path: Path to feature YAML used in prompt generation.
        implement_command: Optional custom shell command override.
        opencode_prompt: Optional prompt override for OpenCode execution.
        skip_implement: Whether to skip implementation and run gates only.
        hook_feedback: Optional previous hook output to address on retry.
        verbose_output: Whether run-loop should stream full command output.

    Returns:
        Tuple of success flag, failure code, and combined command output.
    """
    if skip_implement:
        print("Implement step: skipped")
        return (True, None, "[implement] skipped")

    if implement_command:
        print(f"Implement step: custom command ({implement_command})")
        proc = subprocess.run(
            implement_command,
            shell=True,
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if verbose_output:
            if proc.stdout:
                print(proc.stdout, end="")
            if proc.stderr:
                print(proc.stderr, end="", file=sys.stderr)

        output = (proc.stdout or "") + (proc.stderr or "")
        command_output = (
            f"[implement] command={implement_command}\n"
            f"[implement] returncode={proc.returncode}\n"
            f"{output}"
        )
        if proc.returncode != 0:
            return (False, "implement_command", command_output)
        return (True, None, command_output)

    prompt = opencode_prompt or build_ralph_opencode_prompt(
        feature, feature_path, hook_feedback=hook_feedback
    )
    if opencode_prompt and hook_feedback:
        prompt = (
            f"{opencode_prompt}\n\n"
            "Previous retry feedback (address before completion):\n"
            f"{_truncate_feedback(hook_feedback)}"
        )

    print("Implement step: opencode run --agent build")
    try:
        proc = subprocess.run(
            ["opencode", "run", "--agent", "build", prompt],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return (False, "opencode_missing", "[implement] opencode executable missing")

    if verbose_output:
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)

    output = (proc.stdout or "") + (proc.stderr or "")
    command_output = (
        "[implement] command=opencode run --agent build <prompt>\n"
        f"[implement] returncode={proc.returncode}\n"
        f"{output}"
    )
    if output_has_permission_rejection(output):
        return (False, "opencode_permission", command_output)

    if proc.returncode != 0:
        return (False, "opencode_build", command_output)
    return (True, None, command_output)


def _require_clean_worktree(project_root: Path) -> tuple[bool, str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return (False, "unable to read git status; run inside a git repository")
    if proc.stdout.strip():
        return (False, "working tree must be clean before running automated loop")
    return (True, "")


def _resolve_archive_path(project_root: Path, feature_path: Path) -> Path:
    active_dir = (project_root / "docs" / "spec" / "features").resolve()
    done_dir = (project_root / "docs" / "spec" / "features_done").resolve()
    resolved_feature = feature_path.resolve()

    if resolved_feature.parent != active_dir:
        raise ValueError(
            "completed feature archive source must be under docs/spec/features"
        )
    return done_dir / resolved_feature.name


def _archive_completed_feature(
    project_root: Path, feature_path: Path
) -> tuple[bool, Path | None, str]:
    try:
        archive_path = _resolve_archive_path(project_root, feature_path)
    except ValueError as exc:
        return (False, None, str(exc))

    if not feature_path.exists():
        return (False, None, f"completed feature spec not found: {feature_path}")
    if archive_path.exists():
        return (
            False,
            None,
            f"archive destination already exists: {archive_path}",
        )

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    feature_path.rename(archive_path)
    return (True, archive_path, "")


def _restore_archived_feature(
    archived_path: Path, original_feature_path: Path
) -> tuple[bool, str]:
    if not archived_path.exists():
        return (True, "")
    if original_feature_path.exists():
        return (
            False,
            "cannot restore archived feature path because source already exists",
        )
    original_feature_path.parent.mkdir(parents=True, exist_ok=True)
    archived_path.rename(original_feature_path)
    return (True, "")


def _commit_feature_completion(
    project_root: Path, feature: dict[str, Any]
) -> tuple[bool, str | None, str]:
    message = _feature_completion_commit_subject(feature)

    add_proc = subprocess.run(
        ["git", "add", "-A", "--", "."],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if add_proc.returncode != 0:
        output = (add_proc.stdout or "") + (add_proc.stderr or "")
        return (False, "git_add", output)

    commit_proc = subprocess.run(
        [
            "git",
            "-c",
            "user.name=engineeringagent",
            "-c",
            "user.email=engineeringagent@local",
            "commit",
            "-m",
            message,
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    output = (commit_proc.stdout or "") + (commit_proc.stderr or "")
    if commit_proc.returncode == 0:
        return (True, None, output)
    return (False, "git_commit", output)


def _feature_completion_commit_subject(feature: dict[str, Any]) -> str:
    expected_subject = str(feature.get("expected_commit_subject", "")).strip()
    if expected_subject:
        return expected_subject

    fid = str(feature.get("id", "unknown-feature"))
    title = str(feature.get("title", "")).strip()
    feature_type = str(feature.get("type", "feature")).strip()
    prefix = FEATURE_TYPE_COMMIT_PREFIX.get(feature_type, "feat")
    message = f"{prefix}: complete {fid}"
    if title:
        message = f"{message} - {title}"
    return message


def print_summary(
    feature_id: str | None,
    result: str,
    failed_gate: str | None,
    attempt: int | None,
    next_action: str,
) -> None:
    """Print a one-line loop summary and optional gate failure.

    Args:
        feature_id: Feature identifier for reporting.
        result: Iteration result label.
        failed_gate: Failed gate name when iteration fails.
        attempt: Iteration attempt number.
        next_action: Suggested next loop action.
    """
    print(
        "Loop summary: "
        f"result={result} feature={feature_id or '-'} "
        f"attempt={attempt if attempt is not None else '-'} next={next_action}"
    )
    if failed_gate:
        print(f"Failed gate: {failed_gate}")


def _run_feature_iteration(
    project_root: Path,
    feature_path: Path,
    gate_profile: str,
    implement_command: str | None,
    opencode_prompt: str | None,
    skip_implement: bool,
    attempt: int,
    hook_feedback: str | None,
    verbose_output: bool,
) -> IterationOutcome:
    runs_log = project_root / "progress" / "runs.jsonl"
    gates_path = project_root / "harness" / "gates.yaml"
    started = time.time()

    failed_gate: str | None = None
    result = "passed"
    completed = False
    next_action = "retry_same_feature"
    next_hook_feedback: str | None = None
    implement_status = "not_run"
    gate_status = "not_run"
    implement_output = ""
    gate_output = ""
    completion_commit_succeeded = False
    archived_path: Path | None = None
    archived_in_iteration = False

    feature, loaded_from_archive, load_error = (
        _load_selected_feature_with_archive_fallback(project_root, feature_path)
    )
    fid = str(feature.get("id", "")) if feature else ""

    if load_error:
        result = "failed"
        failed_gate = "feature_missing"
        next_hook_feedback = load_error
    elif loaded_from_archive:
        result = "failed"
        failed_gate = "feature_missing"
        if feature is None:
            next_hook_feedback = (
                "selected feature path is missing and only archived fallback was found "
                "without a same-iteration completion commit; restore the active spec "
                "path and rerun. "
                f"path={feature_path}"
            )
        elif feature.get("status") != "done":
            next_hook_feedback = (
                "selected feature was archived but archived status is not done; "
                "restore the active spec path and rerun. "
                f"path={feature_path}"
            )
        else:
            next_hook_feedback = (
                "selected feature path is already archived with status=done, but this "
                "iteration did not create a completion commit for that feature; restore "
                "the active feature spec or commit the intended completion changes, then "
                "rerun. "
                f"path={feature_path}"
            )

    if result == "passed" and feature is not None and not loaded_from_archive:
        if feature.get("status") == "backlog":
            set_status(feature, "in_progress")
        feature["updated_at"] = now_iso()
        dump_yaml(feature_path, feature)

    if result == "passed" and feature is not None and not loaded_from_archive:
        implement_status = "skipped" if skip_implement else "passed"
        ok, implement_failed_gate, implement_output = run_implement_step(
            project_root=project_root,
            feature=feature,
            feature_path=feature_path,
            implement_command=implement_command,
            opencode_prompt=opencode_prompt,
            skip_implement=skip_implement,
            hook_feedback=hook_feedback,
            verbose_output=verbose_output,
        )
        if not ok:
            result = "failed"
            failed_gate = implement_failed_gate
            implement_status = f"failed:{implement_failed_gate or 'unknown'}"

    post_feature = feature
    loaded_post_from_archive = loaded_from_archive
    if result == "passed" and feature is not None and not loaded_from_archive:
        post_feature, loaded_post_from_archive, post_load_error = (
            _load_selected_feature_with_archive_fallback(project_root, feature_path)
        )
        if post_load_error:
            result = "failed"
            failed_gate = "feature_missing"
            next_hook_feedback = post_load_error
        elif loaded_post_from_archive:
            result = "failed"
            failed_gate = "feature_missing"
            if post_feature is None:
                next_hook_feedback = (
                    "selected feature path disappeared during loop iteration and only "
                    "archived fallback was found without a same-iteration completion "
                    "commit; restore the active spec path and rerun. "
                    f"path={feature_path}"
                )
            elif post_feature.get("status") != "done":
                next_hook_feedback = (
                    "selected feature was archived but archived status is not done; "
                    "restore the active spec path and rerun. "
                    f"path={feature_path}"
                )
            else:
                next_hook_feedback = (
                    "selected feature path was moved to docs/spec/features_done with "
                    "status=done before completion commit in this iteration; restore the "
                    "active feature spec or commit the intended completion changes, then "
                    "rerun. "
                    f"path={feature_path}"
                )
        elif post_feature is not None:
            if post_feature.get("status") == "backlog":
                set_status(post_feature, "in_progress")
            post_feature["updated_at"] = now_iso()
            dump_yaml(feature_path, post_feature)

    if (
        result == "passed"
        and post_feature is not None
        and post_feature.get("status") == "done"
        and not loaded_post_from_archive
    ):
        archived_ok, archived_path, archive_error = _archive_completed_feature(
            project_root, feature_path
        )
        if not archived_ok:
            result = "failed"
            failed_gate = "feature_archive"
            next_hook_feedback = archive_error
        else:
            archived_in_iteration = True

    if result == "passed":
        gate_config = load_gate_config(gates_path)
        ok, failed, gate_output = run_profile(
            gate_config,
            gate_profile,
            project_root,
            capture_output=True,
        )
        if verbose_output and gate_output:
            print(gate_output)
        if not ok:
            if archived_in_iteration and archived_path is not None:
                restored_ok, restore_error = _restore_archived_feature(
                    archived_path, feature_path
                )
                if not restored_ok:
                    rollback_output = f"\narchive rollback failed: {restore_error}"
                    gate_output = f"{gate_output}{rollback_output}".strip()
            result = "failed"
            failed_gate = failed
            gate_status = f"failed:{failed or 'unknown'}"
            next_hook_feedback = gate_output or (
                f"gate '{failed or 'unknown'}' failed with no captured output"
            )
        else:
            gate_status = "passed"

    if result == "passed" and archived_in_iteration:
        if post_feature is None:
            result = "failed"
            failed_gate = "feature_archive"
            next_hook_feedback = (
                "archived feature payload missing before completion commit"
            )
        else:
            commit_ok, commit_failed_gate, commit_output = _commit_feature_completion(
                project_root, post_feature
            )
            if commit_ok:
                completion_commit_succeeded = True
                completed = True
                next_action = "select_next_feature"
            else:
                rollback_output = ""
                if archived_path is not None:
                    restored_ok, restore_error = _restore_archived_feature(
                        archived_path, feature_path
                    )
                    if not restored_ok:
                        rollback_output = f"\narchive rollback failed: {restore_error}"
                result = "failed"
                failed_gate = commit_failed_gate
                next_hook_feedback = f"{commit_output}{rollback_output}".strip()
                next_action = "retry_same_feature"

    if result == "passed" and not completion_commit_succeeded:
        completed = False
        next_action = "retry_same_feature"

    feature_progress_log_path = _resolve_feature_progress_log_path(
        project_root, fid or "unknown-feature"
    )
    try:
        feature_progress_log_reference = str(
            feature_progress_log_path.relative_to(project_root)
        )
    except ValueError:
        feature_progress_log_reference = str(feature_progress_log_path)

    run_payload: dict[str, Any] = {
        "ts": now_iso(),
        "feature_id": fid,
        "subtask_id": None,
        "result": result,
        "failed_gate": failed_gate,
        "duration_sec": int(time.time() - started),
        "attempt": attempt,
        "commit": git_head_short(project_root),
        "next_action": next_action,
        "log_path": feature_progress_log_reference,
    }

    feature_progress_log_lines = [
        f"ts={run_payload['ts']} attempt={attempt} feature_id={fid or 'unknown-feature'}",
        f"feature_path={feature_path}",
        f"implement={implement_status}",
        f"gates={gate_status}",
        f"result={result} failed_gate={failed_gate or '-'} next_action={next_action}",
    ]
    if implement_output:
        feature_progress_log_lines.extend(
            [
                "implement_output_begin",
                implement_output.rstrip("\n"),
                "implement_output_end",
            ]
        )
    if gate_output:
        feature_progress_log_lines.extend(
            ["gate_output_begin", gate_output.rstrip("\n"), "gate_output_end"]
        )
    if next_hook_feedback:
        feature_progress_log_lines.append(
            f"detail={_truncate_feedback(next_hook_feedback)}"
        )
    _append_feature_progress_log(feature_progress_log_path, feature_progress_log_lines)

    append_run(runs_log, run_payload)
    print_summary(fid, result, failed_gate, attempt, next_action)
    if result != "passed":
        print(f"Detailed log: {feature_progress_log_reference}")
    return IterationOutcome(
        completed=completed,
        result=result,
        failed_gate=failed_gate,
        next_action=next_action,
        hook_feedback=next_hook_feedback,
        log_path=feature_progress_log_reference,
    )


def run_loop(
    project_root: Path,
    feature_paths: Sequence[str | Path],
    gate_profile: str,
    implement_command: str | None,
    opencode_prompt: str | None,
    skip_implement: bool,
    dry_run: bool,
    run_all: bool = False,
    max_iterations: int = 50,
    allow_dirty: bool = False,
    verbose_output: bool = False,
) -> int:
    """Execute feature loops until completion or termination condition.

    Args:
        project_root: Repository root for file and command operations.
        feature_paths: One or more feature spec file paths.
        gate_profile: Gate profile name to run after implementation.
        implement_command: Optional custom shell command for implementation.
        opencode_prompt: Optional prompt override for OpenCode implementation.
        skip_implement: Whether to skip implementation and run gates only.
        dry_run: Whether to resolve and report selection without execution.
        run_all: Whether to auto-discover active feature files.
        max_iterations: Max non-dry iterations across selected features.
        allow_dirty: Whether to permit non-dry execution with uncommitted changes.
        verbose_output: Whether to stream full implement and gate command output.

    Returns:
        Process exit code where 0 indicates success.
    """
    if max_iterations < 1:
        print("max_iterations must be >= 1")
        return 1

    try:
        if run_all:
            resolved_paths = _discover_active_feature_paths(project_root)
        else:
            resolved_paths = _resolve_feature_paths(project_root, feature_paths)
    except ValueError as exc:
        print(exc)
        return 1

    if run_all:
        _print_run_all_snapshot_banner(resolved_paths)
        if not resolved_paths:
            _print_run_all_no_work_message()
            return 0

    if dry_run:
        pending = _pending_features(resolved_paths)
        if not pending:
            if run_all:
                _print_run_all_no_work_message()
            else:
                print("No pending features found in provided paths.")
                print_summary(None, "dry_run", None, None, "stop")
            return 0
        if run_all:
            print("[dry-run] Selection is taken from the startup snapshot (no rescan).")
        feature_path, feature = _deterministic_feature_choice(pending)
        fid = str(feature.get("id", ""))
        print(f"[dry-run] Resolved {len(resolved_paths)} feature file(s).")
        print(f"[dry-run] Selected feature={fid} path={feature_path}")
        print_summary(fid, "dry_run", None, None, "stop")
        return 0

    clean, reason = _require_clean_worktree(project_root)
    if not clean and not allow_dirty:
        print(f"Precondition failed: {reason}")
        print(
            "Hint: re-run with --allow-dirty to explicitly continue with "
            "uncommitted code changes."
        )
        return 1
    if not clean and allow_dirty:
        print(
            "Allow-dirty override enabled: continuing with uncommitted code "
            "changes by explicit user opt-in."
        )

    total_iterations = 0
    hook_feedback_by_path: dict[Path, str] = {}

    while True:
        pending = _pending_features(resolved_paths)
        if not pending:
            print("All provided features are done and committed.")
            return 0

        if total_iterations >= max_iterations:
            print(f"Reached max iteration cap ({max_iterations}) before completion.")
            return 1

        selected_path, selected_feature = _choose_feature_with_selector(
            project_root, pending
        )
        selected_id = str(selected_feature.get("id", ""))
        print(f"Selected feature={selected_id} path={selected_path}")

        while True:
            if total_iterations >= max_iterations:
                print(
                    f"Reached max iteration cap ({max_iterations}) before completion."
                )
                return 1

            total_iterations += 1
            outcome = _run_feature_iteration(
                project_root=project_root,
                feature_path=selected_path,
                gate_profile=gate_profile,
                implement_command=implement_command,
                opencode_prompt=opencode_prompt,
                skip_implement=skip_implement,
                attempt=total_iterations,
                hook_feedback=hook_feedback_by_path.get(selected_path),
                verbose_output=verbose_output,
            )

            if outcome.hook_feedback:
                hook_feedback_by_path[selected_path] = outcome.hook_feedback
            else:
                hook_feedback_by_path.pop(selected_path, None)

            if outcome.completed:
                if not selected_path.exists():
                    resolved_paths = [
                        path for path in resolved_paths if path != selected_path
                    ]
                break

            if outcome.failed_gate == "git_add":
                print("Stopping loop: git_add failure requires operator intervention.")
                if outcome.log_path:
                    print(f"Detailed log: {outcome.log_path}")
                return 1

            if outcome.failed_gate == "feature_missing":
                print(
                    "Stopping loop: selected feature path is missing and not recoverable."
                )
                if outcome.log_path:
                    print(f"Detailed log: {outcome.log_path}")
                if outcome.hook_feedback:
                    print(f"Detail: {outcome.hook_feedback}")
                return 1
