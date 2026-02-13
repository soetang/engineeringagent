from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .gates import load_gate_config, run_profile
from .git.client import (
    add_all,
    commit as git_commit,
    head_short as git_head,
    status_porcelain,
)
from .opencode.client import run_shell_command, start_agent
from .opencode_permissions import (
    PERMISSION_REMEDIATION_HINT,
    output_has_permission_rejection,
    run_permission_probe,
)
from .prompts import (
    build_implementation_prompt,
    build_selector_prompt,
    inject_retry_feedback,
)
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


def _requires_opencode_permission_precheck(
    implement_command: str | None,
    skip_implement: bool,
) -> bool:
    return implement_command is None and not skip_implement


def _run_opencode_permission_precheck(
    project_root: Path,
    implement_command: str | None,
    skip_implement: bool,
) -> bool:
    if not _requires_opencode_permission_precheck(
        implement_command=implement_command,
        skip_implement=skip_implement,
    ):
        return True

    print("Running pre-run OpenCode permission precheck (default implement mode).")
    result = run_permission_probe(project_root)
    if result.ok:
        print("OpenCode permission precheck passed.")
        return True

    print(f"Precondition failed: OpenCode permission precheck failed ({result.reason})")
    if result.output:
        print(result.output, end="" if result.output.endswith("\n") else "\n")
    print(PERMISSION_REMEDIATION_HINT)
    print(
        "Hint: use --skip-implement or --implement-command to bypass default OpenCode implement mode."
    )
    return False


@dataclass(frozen=True)
class IterationOutcome:
    completed: bool
    result: str
    failed_gate: str | None
    next_action: str
    hook_feedback: str | None
    log_path: str | None


@dataclass(frozen=True)
class InitialFeatureLoadOutcome:
    feature: dict[str, Any] | None
    loaded_from_archive: bool
    result: str
    failed_gate: str | None
    hook_feedback: str | None


@dataclass(frozen=True)
class PostImplementFeatureOutcome:
    feature: dict[str, Any] | None
    loaded_from_archive: bool
    archived_in_iteration: bool
    archived_path: Path | None
    result: str
    failed_gate: str | None
    hook_feedback: str | None


@dataclass(frozen=True)
class ImplementStepInputs:
    project_root: Path
    feature: dict[str, Any]
    feature_path: Path
    implement_command: str | None
    opencode_prompt: str | None
    skip_implement: bool
    hook_feedback: str | None
    verbose_output: bool


@dataclass(frozen=True)
class FeatureIterationInputs:
    project_root: Path
    feature_path: Path
    gate_profile: str
    implement_command: str | None
    opencode_prompt: str | None
    skip_implement: bool
    attempt: int
    hook_feedback: str | None
    verbose_output: bool


@dataclass(frozen=True)
class GatePhaseOutcome:
    result: str
    failed_gate: str | None
    gate_status: str
    gate_output: str
    hook_feedback: str | None


@dataclass(frozen=True)
class CompletionCommitOutcome:
    completed: bool
    completion_commit_succeeded: bool
    result: str
    failed_gate: str | None
    next_action: str
    hook_feedback: str | None


@dataclass(frozen=True)
class IterationTelemetryInputs:
    iteration_inputs: FeatureIterationInputs
    started: float
    feature_id: str
    result: str
    failed_gate: str | None
    next_action: str
    implement_status: str
    gate_status: str
    implement_output: str
    gate_output: str
    hook_feedback: str | None


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


def _archived_feature_mismatch_feedback(
    feature: dict[str, Any] | None,
    feature_path: Path,
    *,
    missing_message: str,
    done_message: str,
) -> str:
    if feature is None:
        return f"{missing_message} path={feature_path}"
    if feature.get("status") != "done":
        return (
            "selected feature was archived but archived status is not done; "
            "restore the active spec path and rerun. "
            f"path={feature_path}"
        )
    return f"{done_message} path={feature_path}"


def _evaluate_initial_feature_load(
    project_root: Path,
    feature_path: Path,
) -> InitialFeatureLoadOutcome:
    feature, loaded_from_archive, load_error = (
        _load_selected_feature_with_archive_fallback(project_root, feature_path)
    )
    if load_error:
        return InitialFeatureLoadOutcome(
            feature=feature,
            loaded_from_archive=loaded_from_archive,
            result="failed",
            failed_gate="feature_missing",
            hook_feedback=load_error,
        )
    if loaded_from_archive:
        return InitialFeatureLoadOutcome(
            feature=feature,
            loaded_from_archive=loaded_from_archive,
            result="failed",
            failed_gate="feature_missing",
            hook_feedback=_archived_feature_mismatch_feedback(
                feature,
                feature_path,
                missing_message=(
                    "selected feature path is missing and only archived fallback was "
                    "found without a same-iteration completion commit; restore the "
                    "active spec path and rerun."
                ),
                done_message=(
                    "selected feature path is already archived with status=done, but "
                    "this iteration did not create a completion commit for that "
                    "feature; restore the active feature spec or commit the intended "
                    "completion changes, then rerun."
                ),
            ),
        )
    return InitialFeatureLoadOutcome(
        feature=feature,
        loaded_from_archive=loaded_from_archive,
        result="passed",
        failed_gate=None,
        hook_feedback=None,
    )


def _refresh_feature_after_implement(
    project_root: Path,
    feature_path: Path,
    *,
    selected_started_active: bool,
) -> PostImplementFeatureOutcome:
    post_feature, loaded_post_from_archive, post_load_error = (
        _load_selected_feature_with_archive_fallback(project_root, feature_path)
    )
    if post_load_error:
        return PostImplementFeatureOutcome(
            feature=post_feature,
            loaded_from_archive=loaded_post_from_archive,
            archived_in_iteration=False,
            archived_path=None,
            result="failed",
            failed_gate="feature_missing",
            hook_feedback=post_load_error,
        )

    if loaded_post_from_archive:
        if selected_started_active and post_feature is not None:
            if post_feature.get("status") == "done":
                try:
                    archived_path = _resolve_archive_path(project_root, feature_path)
                except ValueError:
                    return PostImplementFeatureOutcome(
                        feature=post_feature,
                        loaded_from_archive=loaded_post_from_archive,
                        archived_in_iteration=False,
                        archived_path=None,
                        result="failed",
                        failed_gate="feature_archive",
                        hook_feedback=(
                            "selected feature path moved to archive during loop "
                            "iteration but archive path could not be resolved; "
                            "restore the active spec path and rerun. "
                            f"path={feature_path}"
                        ),
                    )
                return PostImplementFeatureOutcome(
                    feature=post_feature,
                    loaded_from_archive=loaded_post_from_archive,
                    archived_in_iteration=True,
                    archived_path=archived_path,
                    result="passed",
                    failed_gate=None,
                    hook_feedback=None,
                )
            return PostImplementFeatureOutcome(
                feature=post_feature,
                loaded_from_archive=loaded_post_from_archive,
                archived_in_iteration=False,
                archived_path=None,
                result="failed",
                failed_gate="feature_missing",
                hook_feedback=(
                    "selected feature was archived but archived status is not done; "
                    "restore the active spec path and rerun. "
                    f"path={feature_path}"
                ),
            )

        return PostImplementFeatureOutcome(
            feature=post_feature,
            loaded_from_archive=loaded_post_from_archive,
            archived_in_iteration=False,
            archived_path=None,
            result="failed",
            failed_gate="feature_missing",
            hook_feedback=_archived_feature_mismatch_feedback(
                post_feature,
                feature_path,
                missing_message=(
                    "selected feature path disappeared during loop iteration and only "
                    "archived fallback was found without a same-iteration completion "
                    "commit; restore the active spec path and rerun."
                ),
                done_message=(
                    "selected feature path was moved to docs/spec/features_done with "
                    "status=done before completion commit in this iteration; restore "
                    "the active feature spec or commit the intended completion "
                    "changes, then rerun."
                ),
            ),
        )

    return PostImplementFeatureOutcome(
        feature=post_feature,
        loaded_from_archive=loaded_post_from_archive,
        archived_in_iteration=False,
        archived_path=None,
        result="passed",
        failed_gate=None,
        hook_feedback=None,
    )


def _ready_for_active_iteration(
    *,
    result: str,
    feature: dict[str, Any] | None,
    loaded_from_archive: bool,
) -> bool:
    return result == "passed" and feature is not None and not loaded_from_archive


def _should_archive_selected_feature(
    *,
    result: str,
    selected_feature: dict[str, Any] | None,
    loaded_from_archive: bool,
) -> bool:
    return (
        result == "passed"
        and selected_feature is not None
        and selected_feature.get("status") == "done"
        and not loaded_from_archive
    )


def _touch_active_feature_for_iteration(
    feature: dict[str, Any],
    feature_path: Path,
) -> None:
    if feature.get("status") == "backlog":
        set_status(feature, "in_progress")
    feature["updated_at"] = now_iso()
    dump_yaml(feature_path, feature)


def _deterministic_feature_choice(
    pending: Sequence[tuple[Path, dict[str, Any]]],
) -> tuple[Path, dict[str, Any]]:
    def sort_key(item: tuple[Path, dict[str, Any]]) -> tuple[int, int, str, str]:
        feature_path, feature = item
        status_rank = STATUS_ORDER.get(str(feature.get("status", "")), 99)
        priority_rank, feature_id = feature_sort_key(feature)
        return (status_rank, priority_rank, feature_id, str(feature_path))

    return sorted(pending, key=sort_key)[0]


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

    prompt = build_selector_prompt(pending)
    try:
        proc = start_agent(project_root, prompt)
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
    proc = git_head(project_root)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _truncate_feedback(text: str, max_chars: int = 8_000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


def run_implement_step(  # noqa: PLR0913 - compatibility seam for tests; delegates via ImplementStepInputs.
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
    implement_inputs = ImplementStepInputs(
        project_root=project_root,
        feature=feature,
        feature_path=feature_path,
        implement_command=implement_command,
        opencode_prompt=opencode_prompt,
        skip_implement=skip_implement,
        hook_feedback=hook_feedback,
        verbose_output=verbose_output,
    )
    return _run_implement_step_from_inputs(implement_inputs)


def _run_implement_step_from_inputs(
    implement_inputs: ImplementStepInputs,
) -> tuple[bool, str | None, str]:
    if implement_inputs.skip_implement:
        print("Implement step: skipped")
        return (True, None, "[implement] skipped")

    if implement_inputs.implement_command:
        print(f"Implement step: custom command ({implement_inputs.implement_command})")
        proc = run_shell_command(
            implement_inputs.project_root,
            implement_inputs.implement_command,
        )
        if implement_inputs.verbose_output:
            if proc.stdout:
                print(proc.stdout, end="")
            if proc.stderr:
                print(proc.stderr, end="", file=sys.stderr)

        output = (proc.stdout or "") + (proc.stderr or "")
        command_output = (
            f"[implement] command={implement_inputs.implement_command}\n"
            f"[implement] returncode={proc.returncode}\n"
            f"{output}"
        )
        if proc.returncode != 0:
            return (False, "implement_command", command_output)
        return (True, None, command_output)

    prompt = implement_inputs.opencode_prompt or build_implementation_prompt(
        feature=implement_inputs.feature,
        feature_path=implement_inputs.feature_path,
        hook_feedback=implement_inputs.hook_feedback,
    )
    if implement_inputs.opencode_prompt:
        prompt = inject_retry_feedback(
            implement_inputs.opencode_prompt,
            implement_inputs.hook_feedback,
        )

    print("Implement step: opencode run --agent build")
    try:
        proc = start_agent(implement_inputs.project_root, prompt)
    except FileNotFoundError:
        return (False, "opencode_missing", "[implement] opencode executable missing")

    if implement_inputs.verbose_output:
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
    proc = status_porcelain(project_root)
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

    add_proc = add_all(project_root)
    if add_proc.returncode != 0:
        output = (add_proc.stdout or "") + (add_proc.stderr or "")
        return (False, "git_add", output)

    commit_proc = git_commit(project_root, message)
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


def _iteration_cap_reached(total_iterations: int, max_iterations: int) -> bool:
    if total_iterations >= max_iterations:
        print(f"Reached max iteration cap ({max_iterations}) before completion.")
        return True
    return False


def _update_retry_feedback_for_feature(
    retry_feedback_by_path: dict[Path, str],
    selected_feature_path: Path,
    outcome: IterationOutcome,
) -> None:
    if outcome.hook_feedback:
        retry_feedback_by_path[selected_feature_path] = outcome.hook_feedback
        return
    retry_feedback_by_path.pop(selected_feature_path, None)


def _drop_completed_feature_from_snapshot(
    resolved_feature_paths: list[Path],
    completed_feature_path: Path,
) -> list[Path]:
    if completed_feature_path.exists():
        return resolved_feature_paths
    return [
        feature_path
        for feature_path in resolved_feature_paths
        if feature_path != completed_feature_path
    ]


def _terminal_iteration_failure_exit_code(outcome: IterationOutcome) -> int | None:
    if outcome.failed_gate == "git_add":
        print("Stopping loop: git_add failure requires operator intervention.")
        if outcome.log_path:
            print(f"Detailed log: {outcome.log_path}")
        return 1

    if outcome.failed_gate == "feature_missing":
        print("Stopping loop: selected feature path is missing and not recoverable.")
        if outcome.log_path:
            print(f"Detailed log: {outcome.log_path}")
        if outcome.hook_feedback:
            print(f"Detail: {outcome.hook_feedback}")
        return 1

    return None


def _run_gate_phase(
    iteration_inputs: FeatureIterationInputs,
    gates_path: Path,
    *,
    archived_in_iteration: bool,
    archived_path: Path | None,
) -> GatePhaseOutcome:
    gate_config = load_gate_config(gates_path)
    ok, failed, gate_output = run_profile(
        gate_config,
        iteration_inputs.gate_profile,
        iteration_inputs.project_root,
        capture_output=True,
    )
    if iteration_inputs.verbose_output and gate_output:
        print(gate_output)

    if ok:
        return GatePhaseOutcome(
            result="passed",
            failed_gate=None,
            gate_status="passed",
            gate_output=gate_output,
            hook_feedback=None,
        )

    if archived_in_iteration and archived_path is not None:
        restored_ok, restore_error = _restore_archived_feature(
            archived_path,
            iteration_inputs.feature_path,
        )
        if not restored_ok:
            rollback_output = f"\narchive rollback failed: {restore_error}"
            gate_output = f"{gate_output}{rollback_output}".strip()

    return GatePhaseOutcome(
        result="failed",
        failed_gate=failed,
        gate_status=f"failed:{failed or 'unknown'}",
        gate_output=gate_output,
        hook_feedback=gate_output
        or (f"gate '{failed or 'unknown'}' failed with no captured output"),
    )


def _run_completion_commit_phase(
    iteration_inputs: FeatureIterationInputs,
    *,
    post_feature: dict[str, Any] | None,
    archived_in_iteration: bool,
    archived_path: Path | None,
) -> CompletionCommitOutcome:
    if not archived_in_iteration:
        return CompletionCommitOutcome(
            completed=False,
            completion_commit_succeeded=False,
            result="passed",
            failed_gate=None,
            next_action="retry_same_feature",
            hook_feedback=None,
        )

    if post_feature is None:
        return CompletionCommitOutcome(
            completed=False,
            completion_commit_succeeded=False,
            result="failed",
            failed_gate="feature_archive",
            next_action="retry_same_feature",
            hook_feedback="archived feature payload missing before completion commit",
        )

    commit_ok, commit_failed_gate, commit_output = _commit_feature_completion(
        iteration_inputs.project_root,
        post_feature,
    )
    if commit_ok:
        return CompletionCommitOutcome(
            completed=True,
            completion_commit_succeeded=True,
            result="passed",
            failed_gate=None,
            next_action="select_next_feature",
            hook_feedback=None,
        )

    rollback_output = ""
    if archived_path is not None:
        restored_ok, restore_error = _restore_archived_feature(
            archived_path,
            iteration_inputs.feature_path,
        )
        if not restored_ok:
            rollback_output = f"\narchive rollback failed: {restore_error}"
    return CompletionCommitOutcome(
        completed=False,
        completion_commit_succeeded=False,
        result="failed",
        failed_gate=commit_failed_gate,
        next_action="retry_same_feature",
        hook_feedback=f"{commit_output}{rollback_output}".strip(),
    )


def _write_iteration_telemetry(
    telemetry_inputs: IterationTelemetryInputs,
) -> str:
    runs_log = (
        telemetry_inputs.iteration_inputs.project_root / "progress" / "runs.jsonl"
    )
    feature_progress_log_path = _resolve_feature_progress_log_path(
        telemetry_inputs.iteration_inputs.project_root,
        telemetry_inputs.feature_id or "unknown-feature",
    )
    try:
        feature_progress_log_reference = str(
            feature_progress_log_path.relative_to(
                telemetry_inputs.iteration_inputs.project_root
            )
        )
    except ValueError:
        feature_progress_log_reference = str(feature_progress_log_path)

    run_payload: dict[str, Any] = {
        "ts": now_iso(),
        "feature_id": telemetry_inputs.feature_id,
        "subtask_id": None,
        "result": telemetry_inputs.result,
        "failed_gate": telemetry_inputs.failed_gate,
        "duration_sec": int(time.time() - telemetry_inputs.started),
        "attempt": telemetry_inputs.iteration_inputs.attempt,
        "commit": git_head_short(telemetry_inputs.iteration_inputs.project_root),
        "next_action": telemetry_inputs.next_action,
        "log_path": feature_progress_log_reference,
    }

    feature_progress_log_lines = [
        "ts="
        f"{run_payload['ts']} attempt={telemetry_inputs.iteration_inputs.attempt} "
        f"feature_id={telemetry_inputs.feature_id or 'unknown-feature'}",
        f"feature_path={telemetry_inputs.iteration_inputs.feature_path}",
        f"implement={telemetry_inputs.implement_status}",
        f"gates={telemetry_inputs.gate_status}",
        "result="
        f"{telemetry_inputs.result} failed_gate={telemetry_inputs.failed_gate or '-'} "
        f"next_action={telemetry_inputs.next_action}",
    ]
    if telemetry_inputs.implement_output:
        feature_progress_log_lines.extend(
            [
                "implement_output_begin",
                telemetry_inputs.implement_output.rstrip("\n"),
                "implement_output_end",
            ]
        )
    if telemetry_inputs.gate_output:
        feature_progress_log_lines.extend(
            [
                "gate_output_begin",
                telemetry_inputs.gate_output.rstrip("\n"),
                "gate_output_end",
            ]
        )
    if telemetry_inputs.hook_feedback:
        feature_progress_log_lines.append(
            f"detail={_truncate_feedback(telemetry_inputs.hook_feedback)}"
        )
    _append_feature_progress_log(feature_progress_log_path, feature_progress_log_lines)
    append_run(runs_log, run_payload)
    return feature_progress_log_reference


def _run_feature_iteration(  # noqa: PLR0913 - orchestration seam monkeypatched by loop tests.
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
    iteration_inputs = FeatureIterationInputs(
        project_root=project_root,
        feature_path=feature_path,
        gate_profile=gate_profile,
        implement_command=implement_command,
        opencode_prompt=opencode_prompt,
        skip_implement=skip_implement,
        attempt=attempt,
        hook_feedback=hook_feedback,
        verbose_output=verbose_output,
    )
    return _run_feature_iteration_with_inputs(iteration_inputs)


def _run_feature_iteration_with_inputs(
    iteration_inputs: FeatureIterationInputs,
) -> IterationOutcome:
    gates_path = iteration_inputs.project_root / "harness" / "gates.yaml"
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
    selected_started_active = False

    initial_load = _evaluate_initial_feature_load(
        iteration_inputs.project_root,
        iteration_inputs.feature_path,
    )
    feature = initial_load.feature
    loaded_from_archive = initial_load.loaded_from_archive
    feature_id = str(feature.get("id", "")) if feature else ""
    if initial_load.result == "failed":
        result = initial_load.result
        failed_gate = initial_load.failed_gate
        next_hook_feedback = initial_load.hook_feedback

    if _ready_for_active_iteration(
        result=result,
        feature=feature,
        loaded_from_archive=loaded_from_archive,
    ):
        assert feature is not None
        selected_started_active = True
        _touch_active_feature_for_iteration(feature, iteration_inputs.feature_path)

    if _ready_for_active_iteration(
        result=result,
        feature=feature,
        loaded_from_archive=loaded_from_archive,
    ):
        assert feature is not None
        implement_status = "skipped" if iteration_inputs.skip_implement else "passed"
        ok, implement_failed_gate, implement_output = run_implement_step(
            project_root=iteration_inputs.project_root,
            feature=feature,
            feature_path=iteration_inputs.feature_path,
            implement_command=iteration_inputs.implement_command,
            opencode_prompt=iteration_inputs.opencode_prompt,
            skip_implement=iteration_inputs.skip_implement,
            hook_feedback=iteration_inputs.hook_feedback,
            verbose_output=iteration_inputs.verbose_output,
        )
        if not ok:
            result = "failed"
            failed_gate = implement_failed_gate
            implement_status = f"failed:{implement_failed_gate or 'unknown'}"

    post_feature = feature
    loaded_post_from_archive = loaded_from_archive
    if _ready_for_active_iteration(
        result=result,
        feature=feature,
        loaded_from_archive=loaded_from_archive,
    ):
        assert feature is not None
        post_refresh = _refresh_feature_after_implement(
            iteration_inputs.project_root,
            iteration_inputs.feature_path,
            selected_started_active=selected_started_active,
        )
        post_feature = post_refresh.feature
        loaded_post_from_archive = post_refresh.loaded_from_archive
        archived_in_iteration = post_refresh.archived_in_iteration
        archived_path = post_refresh.archived_path
        if post_refresh.result == "failed":
            result = post_refresh.result
            failed_gate = post_refresh.failed_gate
            next_hook_feedback = post_refresh.hook_feedback
        elif post_feature is not None and not loaded_post_from_archive:
            _touch_active_feature_for_iteration(
                post_feature,
                iteration_inputs.feature_path,
            )

    if _should_archive_selected_feature(
        result=result,
        selected_feature=post_feature,
        loaded_from_archive=loaded_post_from_archive,
    ):
        archived_ok, archived_path, archive_error = _archive_completed_feature(
            iteration_inputs.project_root,
            iteration_inputs.feature_path,
        )
        if not archived_ok:
            result = "failed"
            failed_gate = "feature_archive"
            next_hook_feedback = archive_error
        else:
            archived_in_iteration = True

    if result == "passed":
        gate_phase = _run_gate_phase(
            iteration_inputs,
            gates_path,
            archived_in_iteration=archived_in_iteration,
            archived_path=archived_path,
        )
        gate_output = gate_phase.gate_output
        if gate_phase.result == "failed":
            result = gate_phase.result
            failed_gate = gate_phase.failed_gate
            gate_status = gate_phase.gate_status
            next_hook_feedback = gate_phase.hook_feedback
        else:
            gate_status = gate_phase.gate_status

    if result == "passed" and archived_in_iteration:
        completion_phase = _run_completion_commit_phase(
            iteration_inputs,
            post_feature=post_feature,
            archived_in_iteration=archived_in_iteration,
            archived_path=archived_path,
        )
        result = completion_phase.result
        failed_gate = completion_phase.failed_gate
        next_hook_feedback = completion_phase.hook_feedback
        next_action = completion_phase.next_action
        completed = completion_phase.completed
        completion_commit_succeeded = completion_phase.completion_commit_succeeded

    if result == "passed" and not completion_commit_succeeded:
        completed = False
        next_action = "retry_same_feature"

    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=started,
        feature_id=feature_id,
        result=result,
        failed_gate=failed_gate,
        next_action=next_action,
        implement_status=implement_status,
        gate_status=gate_status,
        implement_output=implement_output,
        gate_output=gate_output,
        hook_feedback=next_hook_feedback,
    )
    feature_progress_log_reference = _write_iteration_telemetry(telemetry_inputs)
    print_summary(
        feature_id,
        result,
        failed_gate,
        iteration_inputs.attempt,
        next_action,
    )
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


def run_loop(  # noqa: PLR0913 - public CLI facade signature must remain stable.
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

    if not _run_opencode_permission_precheck(
        project_root=project_root,
        implement_command=implement_command,
        skip_implement=skip_implement,
    ):
        return 1

    total_iterations = 0
    retry_feedback_by_path: dict[Path, str] = {}

    while True:
        pending = _pending_features(resolved_paths)
        if not pending:
            print("All provided features are done and committed.")
            return 0

        if _iteration_cap_reached(total_iterations, max_iterations):
            return 1

        selected_feature_path, selected_feature = _choose_feature_with_selector(
            project_root, pending
        )
        selected_feature_id = str(selected_feature.get("id", ""))
        print(f"Selected feature={selected_feature_id} path={selected_feature_path}")

        while True:
            if _iteration_cap_reached(total_iterations, max_iterations):
                return 1

            total_iterations += 1
            outcome = _run_feature_iteration(
                project_root=project_root,
                feature_path=selected_feature_path,
                gate_profile=gate_profile,
                implement_command=implement_command,
                opencode_prompt=opencode_prompt,
                skip_implement=skip_implement,
                attempt=total_iterations,
                hook_feedback=retry_feedback_by_path.get(selected_feature_path),
                verbose_output=verbose_output,
            )

            _update_retry_feedback_for_feature(
                retry_feedback_by_path,
                selected_feature_path,
                outcome,
            )

            if outcome.completed:
                resolved_paths = _drop_completed_feature_from_snapshot(
                    resolved_paths,
                    selected_feature_path,
                )
                break

            terminal_failure_exit_code = _terminal_iteration_failure_exit_code(outcome)
            if terminal_failure_exit_code is not None:
                return terminal_failure_exit_code
