from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

from agent_harness.cli import build_parser
from agent_harness.loop import build_ralph_opencode_prompt, run_loop


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SOURCE = REPO_ROOT / "docs" / "spec" / "schemas" / "feature.schema.json"


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _make_project_root(
    tmp_path: Path,
    feature_data: dict[str, Any],
    gates_data: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    project_root = tmp_path
    feature_path = project_root / "docs" / "spec" / "features" / "FEAT-900-ralph-test.yaml"

    if gates_data is None:
        gates_data = {
            "profiles": {"loop_fast": []},
            "gates": {},
        }

    _write_yaml(
        project_root / "harness" / "gates.yaml",
        gates_data,
    )
    _write_yaml(feature_path, feature_data)

    return project_root, feature_path


def _read_runs(project_root: Path) -> list[dict[str, Any]]:
    runs_path = project_root / "progress" / "runs.jsonl"
    lines = runs_path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines]


def _base_feature(status: str = "backlog") -> dict[str, Any]:
    return {
        "id": "FEAT-900",
        "title": "Ralph mode smoke test",
        "status": status,
        "priority": "high",
        "objective": "Verify feature-level loop mode does not require subtask selection.",
        "acceptance": ["Ralph mode runs as a feature-level unit."],
        "updated_at": "2026-02-12T00:00:00Z",
    }


def _copy_schema(project_root: Path) -> None:
    target = project_root / "docs" / "spec" / "schemas" / "feature.schema.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(SCHEMA_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")


def test_ralph_mode_runs_without_subtasks_and_logs_telemetry(tmp_path: Path) -> None:
    project_root, feature_path = _make_project_root(tmp_path, feature_data=_base_feature())

    code = run_loop(
        project_root=project_root,
        feature_id="FEAT-900",
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt=None,
        skip_implement=True,
        dry_run=False,
    )

    assert code == 0

    runs = _read_runs(project_root)
    assert len(runs) == 1
    run = runs[0]

    assert {
        "ts",
        "feature_id",
        "subtask_id",
        "result",
        "failed_gate",
        "duration_sec",
        "attempt",
        "commit",
    } <= set(run)
    assert run["feature_id"] == "FEAT-900"
    assert run["subtask_id"] is None
    assert run["result"] == "passed"
    assert run["failed_gate"] is None
    assert run["attempt"] is None

    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    assert feature["status"] == "in_progress"


def test_ralph_prompt_includes_feature_file_path(tmp_path: Path) -> None:
    _, feature_path = _make_project_root(tmp_path, feature_data=_base_feature())
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    prompt = build_ralph_opencode_prompt(feature=feature, feature_path=feature_path)

    assert str(feature_path) in prompt
    assert "Read and use this feature spec from disk" in prompt


def test_ralph_mode_does_not_block_on_blocked_subtask(tmp_path: Path) -> None:
    feature = _base_feature()
    feature["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Blocked detail",
            "status": "blocked",
            "order": 1,
            "verification": ["this would fail if executed"],
        }
    ]
    project_root, _ = _make_project_root(tmp_path, feature_data=feature)

    code = run_loop(
        project_root=project_root,
        feature_id="FEAT-900",
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt=None,
        skip_implement=True,
        dry_run=False,
    )

    assert code == 0
    run = _read_runs(project_root)[0]
    assert run["result"] == "passed"
    assert run["failed_gate"] is None


def test_ralph_mode_reports_failed_gate(tmp_path: Path) -> None:
    gates = {
        "profiles": {"loop_fast": ["always_fail"]},
        "gates": {
            "always_fail": {
                "run": f'"{sys.executable}" -c "import sys; sys.exit(1)"',
            }
        },
    }
    project_root, _ = _make_project_root(tmp_path, feature_data=_base_feature(), gates_data=gates)

    code = run_loop(
        project_root=project_root,
        feature_id="FEAT-900",
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt=None,
        skip_implement=True,
        dry_run=False,
    )

    assert code == 1
    run = _read_runs(project_root)[0]
    assert run["result"] == "failed"
    assert run["failed_gate"] == "always_fail"


def test_done_feature_is_archived(tmp_path: Path) -> None:
    project_root, feature_path = _make_project_root(tmp_path, feature_data=_base_feature(status="done"))

    code = run_loop(
        project_root=project_root,
        feature_id="FEAT-900",
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt=None,
        skip_implement=True,
        dry_run=False,
    )

    assert code == 0
    assert not feature_path.exists()
    archived = project_root / "docs" / "spec" / "features_done" / feature_path.name
    assert archived.exists()

    run = _read_runs(project_root)[0]
    assert run["result"] == "archived"


def test_cli_loop_run_dry_run_skip_implement(tmp_path: Path, capsys: Any) -> None:
    project_root, _ = _make_project_root(tmp_path, feature_data=_base_feature())

    parser = build_parser()
    args = parser.parse_args(
        [
            "--project-root",
            str(project_root),
            "loop",
            "run",
            "--feature-id",
            "FEAT-900",
            "--dry-run",
            "--skip-implement",
        ]
    )

    code = args.func(args)
    output = capsys.readouterr().out

    assert code == 0
    assert "result=dry_run" in output
    assert not (project_root / "progress" / "runs.jsonl").exists()


def test_cli_validate_simple_spec(tmp_path: Path, capsys: Any) -> None:
    project_root, _ = _make_project_root(tmp_path, feature_data=_base_feature())
    _copy_schema(project_root)

    parser = build_parser()
    args = parser.parse_args(["--project-root", str(project_root), "validate"])

    code = args.func(args)
    output = capsys.readouterr().out

    assert code == 0
    assert "spec validation: ok" in output
