from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .gates import load_gate_config, run_profile
from .opencode_permissions import output_has_permission_rejection
from .specs import dump_yaml, feature_sort_key, iter_feature_files, load_yaml


FEATURE_TRANSITIONS: dict[str, set[str]] = {
    "backlog": {"backlog", "in_progress", "done"},
    "in_progress": {"in_progress", "blocked", "done"},
    "blocked": {"blocked", "in_progress", "done"},
    "done": {"done"},
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def append_run(log_path: Path, payload: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=True) + "\n")


def set_status(entity: dict[str, Any], target: str, kind: str = "feature") -> None:
    transitions = FEATURE_TRANSITIONS
    current = str(entity.get("status", ""))
    allowed = transitions.get(current)
    if not allowed:
        raise ValueError(f"{kind} has unknown status: {current}")
    if target not in allowed:
        raise ValueError(f"illegal {kind} status transition: {current} -> {target}")
    entity["status"] = target


def choose_feature(features_dir: Path, feature_id: str | None) -> tuple[Path, dict[str, Any]] | None:
    files = iter_feature_files(features_dir)
    features: list[tuple[Path, dict[str, Any]]] = [(f, load_yaml(f)) for f in files]

    if feature_id:
        for path, feature in features:
            if feature.get("id") == feature_id:
                return (path, feature)
        return None

    in_progress = [(p, f) for p, f in features if f.get("status") == "in_progress"]
    if in_progress:
        return sorted(in_progress, key=lambda item: feature_sort_key(item[1]))[0]

    backlog = [(p, f) for p, f in features if f.get("status") == "backlog"]
    if backlog:
        return sorted(backlog, key=lambda item: feature_sort_key(item[1]))[0]

    return None


def archive_feature(feature_path: Path, done_dir: Path) -> Path:
    done_dir.mkdir(parents=True, exist_ok=True)
    target = done_dir / feature_path.name
    shutil.move(str(feature_path), str(target))
    return target


def git_head_short(project_root: Path) -> str | None:
    proc = subprocess.run(
        "git rev-parse --short HEAD",
        shell=True,
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def build_ralph_opencode_prompt(feature: dict[str, Any], feature_path: Path) -> str:
    fid = feature.get("id", "unknown-feature")
    feature_title = feature.get("title", "")
    objective = feature.get("objective", "")
    context = feature.get("context", "")
    return (
        f"Read and use this feature spec from disk: {feature_path}. "
        f"Run one Ralph-style feature loop for {fid} ({feature_title}). "
        f"Objective: {objective}. Context: {context}. "
        "Derive the next step directly from the YAML file, make minimal deterministic changes, "
        "run relevant verification, and report concise results."
    )


def run_implement_step(
    project_root: Path,
    feature: dict[str, Any],
    feature_path: Path,
    implement_command: str | None,
    opencode_prompt: str | None,
    skip_implement: bool,
) -> tuple[bool, str | None]:
    if skip_implement:
        print("Implement step: skipped")
        return (True, None)

    if implement_command:
        print(f"Implement step: custom command ({implement_command})")
        proc = subprocess.run(implement_command, shell=True, cwd=project_root)
        if proc.returncode != 0:
            return (False, "implement_command")
        return (True, None)

    prompt = opencode_prompt or build_ralph_opencode_prompt(feature, feature_path)

    print("Implement step: opencode run --agent build")
    try:
        proc = subprocess.run(
            ["opencode", "run", "--agent", "build", prompt],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return (False, "opencode_missing")

    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)

    output = (proc.stdout or "") + (proc.stderr or "")
    if output_has_permission_rejection(output):
        return (False, "opencode_permission")

    if proc.returncode != 0:
        return (False, "opencode_build")
    return (True, None)


def print_summary(
    feature_id: str | None,
    subtask_id: str | None,
    result: str,
    failed_gate: str | None,
    attempt: int | None,
) -> None:
    print(
        "Loop summary: "
        f"result={result} feature={feature_id or '-'} subtask={subtask_id or '-'} "
        f"attempt={attempt if attempt is not None else '-'}"
    )
    if failed_gate:
        print(f"Failed gate: {failed_gate}")


def run_loop(
    project_root: Path,
    feature_id: str | None,
    gate_profile: str,
    implement_command: str | None,
    opencode_prompt: str | None,
    skip_implement: bool,
    dry_run: bool,
) -> int:
    features_dir = project_root / "docs" / "spec" / "features"
    done_dir = project_root / "docs" / "spec" / "features_done"
    runs_log = project_root / "progress" / "runs.jsonl"
    gates_path = project_root / "harness" / "gates.yaml"

    started = time.time()
    run_payload: dict[str, Any] = {
        "ts": now_iso(),
        "feature_id": None,
        "subtask_id": None,
        "result": "error",
        "failed_gate": None,
        "duration_sec": 0,
        "attempt": None,
        "commit": None,
    }

    try:
        choice = choose_feature(features_dir, feature_id)
        if not choice:
            if feature_id:
                print(f"Feature not found: {feature_id}")
                run_payload["result"] = "feature_not_found"
                return 1
            print("No eligible feature found.")
            run_payload["result"] = "noop"
            print_summary(None, None, "noop", None, None)
            return 0

        feature_path, feature = choice
        fid = str(feature.get("id"))
        run_payload["feature_id"] = fid

        if feature.get("status") == "done":
            feature["updated_at"] = now_iso()
            if dry_run:
                print(f"[dry-run] Feature {fid} already complete. Would archive {feature_path}.")
                run_payload["result"] = "archived"
                print_summary(fid, None, "archived", None, None)
                return 0
            dump_yaml(feature_path, feature)
            target = archive_feature(feature_path, done_dir)
            print(f"Feature {fid} complete; archived to {target}")
            run_payload["result"] = "archived"
            print_summary(fid, None, "archived", None, None)
            return 0

        if feature.get("status") == "backlog":
            set_status(feature, "in_progress")
        feature["updated_at"] = now_iso()

        print(f"Selected feature={fid} mode=ralph")

        if dry_run:
            print("[dry-run] No changes executed.")
            run_payload["result"] = "dry_run"
            print_summary(fid, None, "dry_run", None, None)
            return 0

        dump_yaml(feature_path, feature)

        failed_gate: str | None = None
        result = "passed"

        ok, implement_failed_gate = run_implement_step(
            project_root=project_root,
            feature=feature,
            feature_path=feature_path,
            implement_command=implement_command,
            opencode_prompt=opencode_prompt,
            skip_implement=skip_implement,
        )
        if not ok:
            result = "failed"
            failed_gate = implement_failed_gate

        if result == "passed":
            gate_config = load_gate_config(gates_path)
            ok, failed = run_profile(gate_config, gate_profile, project_root)
            if not ok:
                result = "failed"
                failed_gate = failed

        feature = load_yaml(feature_path)
        if feature.get("status") == "backlog":
            set_status(feature, "in_progress")

        feature["updated_at"] = now_iso()
        dump_yaml(feature_path, feature)

        if feature.get("status") == "done":
            target = archive_feature(feature_path, done_dir)
            print(f"Feature {fid} complete; archived to {target}")

        run_payload["result"] = result
        run_payload["failed_gate"] = failed_gate
        print_summary(fid, None, result, failed_gate, None)
        return 0 if result == "passed" else 1
    finally:
        if not dry_run:
            run_payload["ts"] = now_iso()
            run_payload["duration_sec"] = int(time.time() - started)
            run_payload["commit"] = git_head_short(project_root)
            append_run(runs_log, run_payload)
