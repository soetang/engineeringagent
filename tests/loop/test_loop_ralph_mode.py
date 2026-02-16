from __future__ import annotations

import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest
import yaml
from typer.testing import CliRunner

from engineeringagent import cli as cli_module
import engineeringagent.loop as loop_module
from engineeringagent.loop import (
    build_loop_run,
    build_run_config,
    run_loop as _run_loop,
)
from engineeringagent.loop_runtime import presentation as presentation_module
from engineeringagent.prompts import build_implementation_prompt


def run_loop(
    *,
    project_root: Path,
    feature_paths: list[str],
    gate_profile: str,
    opencode_prompt: str | None,
    dry_run: bool,
    run_all: bool = False,
    max_iterations: int = 50,
    allow_dirty: bool = False,
    verbose_output: bool = False,
) -> int:
    """Compatibility wrapper for legacy scalar run_loop tests.

    The production contract is `engineeringagent.loop.run_loop(loop_run: LoopRun)`.
    These integration-style tests predate the LoopRun context refactor.
    """

    del opencode_prompt
    del gate_profile
    config = build_run_config(
        project_root=project_root,
        feature_paths=feature_paths,
        run_all=run_all,
        dry_run=dry_run,
        max_iterations=max_iterations,
        allow_dirty=allow_dirty,
        verbose_output=verbose_output,
    )
    return _run_loop(build_loop_run(config))


_OPENCODE_IMPLEMENT_SIDE_EFFECT: Callable[[], None] | None = None
_OPENCODE_IMPLEMENT_FAKE_RESULT: tuple[int, str, str] | None = None


@contextmanager
def _with_opencode_implement_side_effect(
    effect: Callable[[], None],
) -> Iterator[None]:
    global _OPENCODE_IMPLEMENT_SIDE_EFFECT
    previous = _OPENCODE_IMPLEMENT_SIDE_EFFECT
    _OPENCODE_IMPLEMENT_SIDE_EFFECT = effect
    try:
        yield
    finally:
        _OPENCODE_IMPLEMENT_SIDE_EFFECT = previous


@contextmanager
def _with_opencode_implement_result(
    *,
    returncode: int = 0,
    stdout: str = "ok\n",
    stderr: str = "",
) -> Iterator[None]:
    global _OPENCODE_IMPLEMENT_FAKE_RESULT
    previous = _OPENCODE_IMPLEMENT_FAKE_RESULT
    _OPENCODE_IMPLEMENT_FAKE_RESULT = (returncode, stdout, stderr)
    try:
        yield
    finally:
        _OPENCODE_IMPLEMENT_FAKE_RESULT = previous


@pytest.fixture(autouse=True)
def _stub_opencode_start_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_start_agent(
        project_root: Path,
        prompt: str,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        del project_root
        if "Read and use this feature spec from disk:" in prompt:
            effect = _OPENCODE_IMPLEMENT_SIDE_EFFECT
            if effect is not None:
                effect()

        agent = kwargs.get("agent", "engineeringagent")
        override = (
            _OPENCODE_IMPLEMENT_FAKE_RESULT
            if "Read and use this feature spec from disk:" in prompt
            else None
        )
        if override is None:
            override = (0, "ok\n", "")

        returncode, stdout, stderr = override
        return subprocess.CompletedProcess(
            ["opencode", "run", "--agent", str(agent), prompt],
            returncode,
            stdout=stdout,
            stderr=stderr,
        )

    monkeypatch.setattr(loop_module, "start_agent", fake_start_agent)


@pytest.fixture(autouse=True)
def _stub_permission_precheck(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        loop_module,
        "_run_opencode_permission_precheck",
        lambda **_: True,
    )


def _invoke_cli(args: list[str]) -> Any:
    runner = CliRunner(mix_stderr=False)
    return runner.invoke(cli_module.build_typer_app(), args)


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _base_feature(status: str = "backlog") -> dict[str, Any]:
    return {
        "id": "FEAT-900",
        "title": "Ralph mode smoke test",
        "type": "feature",
        "expected_commit_subject": "feat: complete FEAT-900 ralph mode smoke test",
        "status": status,
        "priority": "high",
        "objective": "Verify feature-level loop mode does not require subtask selection.",
        "acceptance": ["Ralph mode runs as a feature-level unit."],
        "updated_at": "2026-02-12T00:00:00Z",
    }


def _make_project_root(
    tmp_path: Path,
    feature_data: dict[str, Any],
    gates_data: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    project_root = tmp_path
    feature_path = (
        project_root / "docs" / "spec" / "features" / "FEAT-900-ralph-test.yaml"
    )

    checks: dict[str, Any] = {}
    if gates_data is not None:
        gates = gates_data.get("gates") if isinstance(gates_data, dict) else None
        if isinstance(gates, dict):
            for gate_id, gate in gates.items():
                if not isinstance(gate_id, str) or not gate_id:
                    continue
                if not isinstance(gate, dict):
                    continue
                command = gate.get("run")
                if not isinstance(command, str) or not command.strip():
                    continue
                checks[gate_id] = {
                    "type": "command",
                    "command": command,
                }

    _write_yaml(
        project_root / "harness" / "checks.yaml",
        {
            "contract_version": "1.0",
            "defaults": {"when": {"phase": "iteration_end"}},
            "checks": checks,
        },
    )
    _write_yaml(feature_path, feature_data)
    return project_root, feature_path


def _read_runs(project_root: Path) -> list[dict[str, Any]]:
    runs_path = project_root / "progress" / "runs.jsonl"
    return [
        json.loads(line) for line in runs_path.read_text(encoding="utf-8").splitlines()
    ]


def _run_git(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=project_root, check=True, capture_output=True, text=True
    )


def _run_python_script(script_path: Path, *args: Path) -> None:
    subprocess.run(
        [sys.executable, str(script_path), *(str(arg) for arg in args)],
        check=True,
        capture_output=True,
        text=True,
    )


def test_run_python_script_executes_with_path_args(tmp_path: Path) -> None:
    script_path = tmp_path / "copy-source-to-output.py"
    source_path = tmp_path / "source.txt"
    output_path = tmp_path / "output.txt"

    source_path.write_text("ok\n", encoding="utf-8")
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "output_path = Path(sys.argv[1])",
                "source_path = Path(sys.argv[2])",
                "output_path.write_text(source_path.read_text(encoding='utf-8'), encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    _run_python_script(script_path, output_path, source_path)

    assert output_path.read_text(encoding="utf-8") == "ok\n"


def _patch_start_agent_with_fake(
    monkeypatch: pytest.MonkeyPatch,
    fake_subprocess_run: Any,
) -> None:
    def fake_start_agent(
        project_root: Path,
        prompt: str,
        *,
        agent: str = "build",
        capture_output: bool = True,
        text: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        del project_root, capture_output, text
        return fake_subprocess_run(["opencode", "run", "--agent", agent, prompt])

    monkeypatch.setattr(loop_module, "start_agent", fake_start_agent)


def _init_git_repo(project_root: Path) -> None:
    _run_git(project_root, "init")
    _run_git(project_root, "add", "-A")
    _run_git(
        project_root,
        "-c",
        "user.name=test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "init",
    )


def _write_set_done_script(script_path: Path) -> Path:
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "import yaml",
                "feature_path = Path(sys.argv[1])",
                "feature = yaml.safe_load(feature_path.read_text(encoding='utf-8'))",
                "feature['status'] = 'done'",
                "feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script_path


def _write_set_subtask_done_script(script_path: Path, subtask_id: str) -> Path:
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "import yaml",
                f"target_subtask_id = {subtask_id!r}",
                "feature_path = Path(sys.argv[1])",
                "feature = yaml.safe_load(feature_path.read_text(encoding='utf-8'))",
                "for subtask in feature.get('subtasks', []):",
                "    if isinstance(subtask, dict) and subtask.get('id') == target_subtask_id:",
                "        subtask['status'] = 'done'",
                "        break",
                "feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script_path


def _write_add_done_subtask_script(
    script_path: Path,
    subtask_id: str,
    verification_command: str,
) -> Path:
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "import yaml",
                f"new_subtask_id = {subtask_id!r}",
                f"verification_command = {verification_command!r}",
                "feature_path = Path(sys.argv[1])",
                "feature = yaml.safe_load(feature_path.read_text(encoding='utf-8'))",
                "subtasks = feature.setdefault('subtasks', [])",
                "subtasks.append({",
                "    'id': new_subtask_id,",
                "    'title': 'Added done subtask',",
                "    'status': 'done',",
                "    'context': 'Created during implement step.',",
                "    'verification': [verification_command],",
                "})",
                "feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script_path


def _write_set_done_and_duplicate_subtask_script(
    script_path: Path,
    subtask_id: str,
    duplicate_verification_command: str,
) -> Path:
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "import yaml",
                f"target_subtask_id = {subtask_id!r}",
                f"duplicate_verification_command = {duplicate_verification_command!r}",
                "feature_path = Path(sys.argv[1])",
                "feature = yaml.safe_load(feature_path.read_text(encoding='utf-8'))",
                "subtasks = feature.get('subtasks', [])",
                "for subtask in subtasks:",
                "    if isinstance(subtask, dict) and subtask.get('id') == target_subtask_id:",
                "        subtask['status'] = 'done'",
                "        subtasks.append({",
                "            'id': target_subtask_id,",
                "            'title': 'Duplicated done subtask',",
                "            'status': 'done',",
                "            'context': 'Duplicate id added during implement step.',",
                "            'verification': [duplicate_verification_command],",
                "        })",
                "        break",
                "feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script_path


def _write_set_done_and_create_feature_script(script_path: Path) -> Path:
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "import yaml",
                "feature_path = Path(sys.argv[1])",
                "created_feature_path = Path(sys.argv[2])",
                "feature = yaml.safe_load(feature_path.read_text(encoding='utf-8'))",
                "feature['status'] = 'done'",
                "feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding='utf-8')",
                "created_feature = {",
                "    'id': 'FEAT-999',",
                "    'title': 'Created after startup snapshot',",
                "    'type': 'feature',",
                "    'status': 'backlog',",
                "    'priority': 'high',",
                "    'objective': 'Ensure run --all startup snapshot remains stable.',",
                "    'acceptance': ['Feature can be selected in a later run.'],",
                "    'updated_at': '2026-02-14T00:00:00Z',",
                "}",
                "created_feature_path.parent.mkdir(parents=True, exist_ok=True)",
                "created_feature_path.write_text(",
                "    yaml.safe_dump(created_feature, sort_keys=False),",
                "    encoding='utf-8',",
                ")",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script_path


def _write_move_to_done_script(script_path: Path) -> Path:
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "import yaml",
                "project_root = Path(sys.argv[1])",
                "feature_path = Path(sys.argv[2])",
                "feature = yaml.safe_load(feature_path.read_text(encoding='utf-8'))",
                "feature['status'] = 'done'",
                "done_path = project_root / 'docs' / 'spec' / 'features_done' / feature_path.name",
                "done_path.parent.mkdir(parents=True, exist_ok=True)",
                "done_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding='utf-8')",
                "feature_path.unlink()",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script_path


def _write_delete_selected_feature_script(script_path: Path) -> Path:
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "feature_path = Path(sys.argv[1])",
                "feature_path.unlink()",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script_path


def _move_feature_to_done(project_root: Path, feature_path: Path) -> None:
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    feature["status"] = "done"
    done_path = project_root / "docs" / "spec" / "features_done" / feature_path.name
    done_path.parent.mkdir(parents=True, exist_ok=True)
    done_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding="utf-8")
    feature_path.unlink()


def test_verification_is_not_run_without_done_transition(tmp_path: Path) -> None:
    verification_marker = "verification-ran.txt"
    verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{verification_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = _base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Run verification command",
            "status": "backlog",
            "context": "Verify selected subtask commands run under loop control.",
            "verification": [verification_command],
        }
    ]
    project_root, feature_path = _make_project_root(tmp_path, feature_data=feature_data)

    outcome = loop_module._run_feature_iteration(
        project_root=project_root,
        feature_path=feature_path,
        run_all=False,
        opencode_prompt=None,
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )

    assert outcome.result == "passed"
    assert outcome.verification_status == "not_run"
    assert outcome.verification_failed_command is None
    assert not (project_root / verification_marker).exists()


def test_verification_failure_for_newly_done_subtask_marks_iteration_non_pass(
    tmp_path: Path,
) -> None:
    verification_command = (
        f'"{sys.executable}" -c "import sys; print(\'verification failure\'); '
        'sys.exit(1)"'
    )
    feature_data = _base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Fail verification command",
            "status": "backlog",
            "context": "Ensure failed verification marks iteration as failed.",
            "verification": [verification_command],
        }
    ]
    project_root, feature_path = _make_project_root(tmp_path, feature_data=feature_data)
    script_path = _write_set_subtask_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-subtask-done.py",
        "ST-001",
    )

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        outcome = loop_module._run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            opencode_prompt=None,
            attempt=1,
            hook_feedback=None,
            verbose_output=False,
        )

    assert outcome.result == "failed"
    assert outcome.failed_gate is None
    assert outcome.next_action == "retry_same_feature"
    assert outcome.verification_status == f"failed:{verification_command}"
    assert outcome.verification_failed_command == verification_command

    runs = _read_runs(project_root)
    assert runs[-1]["result"] == "failed"
    assert runs[-1]["verification_status"] == f"failed:{verification_command}"
    assert runs[-1]["verification_failed_command"] == verification_command


def test_verification_selection_ignores_non_string_commands(
    tmp_path: Path,
) -> None:
    verification_marker = "verification-valid-ran.txt"
    valid_verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{verification_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = _base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Ignore non-string verification entries",
            "status": "backlog",
            "context": "Ensure done-transition verification ignores non-command values.",
            "verification": [123, valid_verification_command],
        }
    ]
    project_root, feature_path = _make_project_root(tmp_path, feature_data=feature_data)
    script_path = _write_set_subtask_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-subtask-done-ignore-invalid.py",
        "ST-001",
    )

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        outcome = loop_module._run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            opencode_prompt=None,
            attempt=1,
            hook_feedback=None,
            verbose_output=False,
        )

    assert outcome.result == "passed"
    assert outcome.verification_status == "passed"
    assert outcome.verification_failed_command is None
    assert (project_root / verification_marker).exists()


def test_verification_selection_ignores_blank_string_commands(
    tmp_path: Path,
) -> None:
    verification_marker = "verification-blank-filter-ran.txt"
    valid_verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{verification_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = _base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Ignore blank verification entries",
            "status": "backlog",
            "context": "Ensure done-transition verification ignores blank commands.",
            "verification": ["   ", valid_verification_command],
        }
    ]
    project_root, feature_path = _make_project_root(tmp_path, feature_data=feature_data)
    script_path = _write_set_subtask_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-subtask-done-ignore-blank.py",
        "ST-001",
    )

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        outcome = loop_module._run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            opencode_prompt=None,
            attempt=1,
            hook_feedback=None,
            verbose_output=False,
        )

    runs = _read_runs(project_root)
    feature_log = project_root / str(runs[-1]["log_path"])
    log_text = feature_log.read_text(encoding="utf-8")

    assert outcome.result == "passed"
    assert outcome.verification_status == "passed"
    assert outcome.verification_failed_command is None
    assert (project_root / verification_marker).exists()
    assert "[verification] command=   " not in log_text
    assert f"[verification] command={valid_verification_command}" in log_text


def test_verification_selection_normalizes_command_whitespace(
    tmp_path: Path,
) -> None:
    verification_marker = "verification-whitespace-normalized-ran.txt"
    trimmed_verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{verification_marker}').write_text('ok', encoding='utf-8')\""
    )
    padded_verification_command = f"  {trimmed_verification_command}  "
    feature_data = _base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Normalize command whitespace",
            "status": "backlog",
            "context": "Ensure done-transition verification trims command whitespace.",
            "verification": [padded_verification_command],
        }
    ]
    project_root, feature_path = _make_project_root(tmp_path, feature_data=feature_data)
    script_path = _write_set_subtask_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-subtask-done-normalize-whitespace.py",
        "ST-001",
    )

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        outcome = loop_module._run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            opencode_prompt=None,
            attempt=1,
            hook_feedback=None,
            verbose_output=False,
        )

    runs = _read_runs(project_root)
    feature_log = project_root / str(runs[-1]["log_path"])
    log_text = feature_log.read_text(encoding="utf-8")

    assert outcome.result == "passed"
    assert outcome.verification_status == "passed"
    assert (project_root / verification_marker).exists()
    assert f"[verification] command={trimmed_verification_command}" in log_text
    assert f"[verification] command={padded_verification_command}" not in log_text


def test_verification_ignores_new_done_subtasks_without_pre_snapshot_status(
    tmp_path: Path,
) -> None:
    verification_marker = "verification-added-subtask-ran.txt"
    verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{verification_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = _base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Leave existing subtask untouched",
            "status": "backlog",
            "context": "Ensure only stable-id status transitions drive verification.",
            "verification": [verification_command],
        }
    ]
    project_root, feature_path = _make_project_root(tmp_path, feature_data=feature_data)
    script_path = _write_add_done_subtask_script(
        tmp_path.parent / f"{tmp_path.name}-add-done-subtask.py",
        "ST-NEW",
        verification_command,
    )

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        outcome = loop_module._run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            opencode_prompt=None,
            attempt=1,
            hook_feedback=None,
            verbose_output=False,
        )

    assert outcome.result == "passed"
    assert outcome.verification_status == "not_run"
    assert outcome.verification_failed_command is None
    assert not (project_root / verification_marker).exists()


def test_verification_selection_uses_first_post_entry_for_duplicate_subtask_ids(
    tmp_path: Path,
) -> None:
    primary_marker = "verification-primary-ran.txt"
    duplicate_marker = "verification-duplicate-ran.txt"
    primary_verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{primary_marker}').write_text('ok', encoding='utf-8')\""
    )
    duplicate_verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{duplicate_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = _base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Preserve one stable-id transition",
            "status": "backlog",
            "context": "Ensure duplicate post-implement IDs do not duplicate verification.",
            "verification": [primary_verification_command],
        }
    ]
    project_root, feature_path = _make_project_root(tmp_path, feature_data=feature_data)
    script_path = _write_set_done_and_duplicate_subtask_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-and-duplicate-id.py",
        "ST-001",
        duplicate_verification_command,
    )

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        outcome = loop_module._run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            opencode_prompt=None,
            attempt=1,
            hook_feedback=None,
            verbose_output=False,
        )

    assert outcome.result == "passed"
    assert outcome.verification_status == "passed"
    assert (project_root / primary_marker).exists()
    assert not (project_root / duplicate_marker).exists()


def test_verification_selection_uses_first_pre_status_for_duplicate_subtask_ids(
    tmp_path: Path,
) -> None:
    verification_marker = "verification-first-pre-status-ran.txt"
    verification_command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{verification_marker}').write_text('ok', encoding='utf-8')\""
    )
    feature_data = _base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Primary pre-implement entry",
            "status": "backlog",
            "context": "Use first pre-implement status for done-transition diffing.",
            "verification": [verification_command],
        },
        {
            "id": "ST-001",
            "title": "Duplicate pre-implement entry",
            "status": "done",
            "context": "Duplicate id should not mask first-entry transition.",
            "verification": ["true"],
        },
    ]
    project_root, feature_path = _make_project_root(tmp_path, feature_data=feature_data)
    script_path = _write_set_subtask_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-first-duplicate-id-done.py",
        "ST-001",
    )

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        outcome = loop_module._run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            opencode_prompt=None,
            attempt=1,
            hook_feedback=None,
            verbose_output=False,
        )

    assert outcome.result == "passed"
    assert outcome.verification_status == "passed"
    assert (project_root / verification_marker).exists()


def test_verification_failure_restores_feature_archived_during_iteration(
    tmp_path: Path,
) -> None:
    verification_command = f'"{sys.executable}" -c "import sys; sys.exit(1)"'
    feature_data = _base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Fail verification after archive move",
            "status": "backlog",
            "context": "Ensure verification failure restores active feature path.",
            "verification": [verification_command],
        }
    ]
    project_root, feature_path = _make_project_root(tmp_path, feature_data=feature_data)
    set_subtask_done_script = _write_set_subtask_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-subtask-done-before-archive.py",
        "ST-001",
    )
    move_to_done_script = _write_move_to_done_script(
        tmp_path.parent / f"{tmp_path.name}-move-to-done-before-verification.py"
    )

    def implement_effect() -> None:
        _run_python_script(set_subtask_done_script, feature_path)
        _run_python_script(move_to_done_script, project_root, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        outcome = loop_module._run_feature_iteration(
            project_root=project_root,
            feature_path=feature_path,
            run_all=False,
            opencode_prompt=None,
            attempt=1,
            hook_feedback=None,
            verbose_output=False,
        )

    archived_path = project_root / "docs" / "spec" / "features_done" / feature_path.name

    assert outcome.result == "failed"
    assert outcome.failed_gate is None
    assert outcome.next_action == "retry_same_feature"
    assert outcome.verification_status == f"failed:{verification_command}"
    assert feature_path.exists()
    assert not archived_path.exists()


def test_ralph_prompt_includes_feature_file_path(tmp_path: Path) -> None:
    _, feature_path = _make_project_root(tmp_path, feature_data=_base_feature())
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    prompt = build_implementation_prompt(
        feature=feature,
        feature_path=feature_path,
        hook_feedback=None,
    )

    expected_prompt_phrases = (
        str(feature_path),
        "Read and use this feature spec from disk",
        "most important open subtask",
        "most important open subtask first",
        "red-green-refactor TDD loop",
        "red -> green -> refactor",
        "only after it transitions to done in this iteration",
    )
    for phrase in expected_prompt_phrases:
        assert phrase in prompt


def test_cli_run_dry_run_path_first(tmp_path: Path) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )

    result = _invoke_cli(
        [
            "--project-root",
            str(project_root),
            "run",
            str(feature_path),
            "--dry-run",
        ]
    )

    assert result.exit_code == 0
    assert "result=dry_run" in result.stdout
    assert not (project_root / "progress" / "runs.jsonl").exists()


def test_cli_run_all_dry_run(tmp_path: Path) -> None:
    project_root, _ = _make_project_root(tmp_path, feature_data=_base_feature())

    result = _invoke_cli(
        [
            "--project-root",
            str(project_root),
            "run",
            "--all",
            "--dry-run",
        ]
    )

    assert result.exit_code == 0
    assert "result=dry_run" in result.stdout


def test_cli_run_rejects_combined_all_and_paths(tmp_path: Path) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )

    result = _invoke_cli(
        [
            "--project-root",
            str(project_root),
            "run",
            "--all",
            str(feature_path),
            "--dry-run",
        ]
    )

    assert result.exit_code == 1
    assert "cannot be used with --all" in result.stdout


def test_cli_run_requires_paths_or_all(tmp_path: Path) -> None:
    project_root, _ = _make_project_root(tmp_path, feature_data=_base_feature())

    result = _invoke_cli(
        [
            "--project-root",
            str(project_root),
            "run",
            "--dry-run",
        ]
    )

    assert result.exit_code == 1
    assert "provide one or more feature paths, or use --all" in result.stdout


def test_run_loop_all_discovers_backlog_and_in_progress_only(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, _ = _make_project_root(tmp_path, feature_data=_base_feature())
    features_dir = project_root / "docs" / "spec" / "features"

    backlog_feature = _base_feature(status="backlog")
    backlog_feature["id"] = "FEAT-901"
    _write_yaml(features_dir / "FEAT-901-backlog.yaml", backlog_feature)

    in_progress_feature = _base_feature(status="in_progress")
    in_progress_feature["id"] = "FEAT-902"
    _write_yaml(features_dir / "FEAT-902-in-progress.yaml", in_progress_feature)

    blocked_feature = _base_feature(status="blocked")
    blocked_feature["id"] = "FEAT-903"
    _write_yaml(features_dir / "FEAT-903-blocked.yaml", blocked_feature)

    done_feature = _base_feature(status="done")
    done_feature["id"] = "FEAT-904"
    _write_yaml(features_dir / "FEAT-904-done.yaml", done_feature)

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=True,
        run_all=True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "[dry-run] Resolved 3 feature file(s)." in output
    assert "feature=FEAT-902" in output
    assert "FEAT-903" not in output
    assert "FEAT-904" not in output


def test_run_all_uses_configured_docs_root(tmp_path: Path, capsys: Any) -> None:
    configured_docs_root = tmp_path / "docs.engineeringagent"
    configured_features_dir = configured_docs_root / "spec" / "features"
    default_features_dir = tmp_path / "docs" / "spec" / "features"

    (tmp_path / "engineeringagent.toml").write_text(
        'docs-root = "docs.engineeringagent"\n',
        encoding="utf-8",
    )
    _write_yaml(
        tmp_path / "harness" / "gates.yaml",
        {
            "profiles": {"loop_fast": []},
            "gates": {},
        },
    )

    configured_feature = _base_feature(status="backlog")
    configured_feature["id"] = "FEAT-910"
    _write_yaml(
        configured_features_dir / "FEAT-910-configured-docs-root.yaml",
        configured_feature,
    )

    default_feature = _base_feature(status="backlog")
    default_feature["id"] = "FEAT-911"
    _write_yaml(
        default_features_dir / "FEAT-911-default-docs-root.yaml", default_feature
    )

    code = run_loop(
        project_root=tmp_path,
        feature_paths=[],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=True,
        run_all=True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "[dry-run] Resolved 1 feature file(s)." in output
    assert "feature=FEAT-910" in output
    assert "FEAT-911" not in output


def test_run_loop_all_excludes_blocked_and_done_from_startup_snapshot(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, _ = _make_project_root(
        tmp_path, feature_data=_base_feature(status="done")
    )
    features_dir = project_root / "docs" / "spec" / "features"

    blocked_feature = _base_feature(status="blocked")
    blocked_feature["id"] = "FEAT-903"
    _write_yaml(features_dir / "FEAT-903-blocked.yaml", blocked_feature)

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=True,
        run_all=True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "No runnable active features found for --all startup snapshot" in output


def test_run_loop_all_exits_zero_when_no_runnable_features(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, _ = _make_project_root(
        tmp_path, feature_data=_base_feature(status="blocked")
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=False,
        run_all=True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "No runnable active features found for --all startup snapshot" in output
    assert "result=no_work" in output


def test_run_loop_all_does_not_include_specs_created_after_startup(
    tmp_path: Path,
) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    features_dir = project_root / "docs" / "spec" / "features"
    created_feature_path = features_dir / "FEAT-999-created-after-startup.yaml"
    script_path = _write_set_done_and_create_feature_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-and-create-feature.py"
    )
    _init_git_repo(project_root)

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path, created_feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            run_all=True,
            max_iterations=3,
        )

    archived_path = project_root / "docs" / "spec" / "features_done" / feature_path.name
    runs = _read_runs(project_root)

    assert code == 0
    assert not feature_path.exists()
    assert archived_path.exists()
    assert created_feature_path.exists()
    assert [run["feature_id"] for run in runs] == ["FEAT-900"]


def test_run_loop_all_dry_run_reports_snapshot_selection(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, _ = _make_project_root(tmp_path, feature_data=_base_feature())

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=True,
        run_all=True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "Startup snapshot captured" in output
    assert "Selection is taken from the startup snapshot" in output


def test_run_loop_completes_feature_and_commits(tmp_path: Path) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    script_path = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done.py"
    )
    _init_git_repo(project_root)

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=5,
        )

    assert code == 0
    runs = _read_runs(project_root)
    assert len(runs) >= 1
    assert runs[-1]["feature_id"] == "FEAT-900"
    assert runs[-1]["result"] == "passed"
    assert runs[-1]["failed_gate"] is None

    archived_path = project_root / "docs" / "spec" / "features_done" / feature_path.name
    assert not feature_path.exists()
    assert archived_path.exists()

    feature = yaml.safe_load(archived_path.read_text(encoding="utf-8"))
    assert feature["status"] == "done"

    log = _run_git(project_root, "log", "--oneline").stdout.strip().splitlines()
    assert len(log) >= 2


def test_archive_path_uses_configured_docs_root(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs.engineeringagent"
    feature_path = docs_root / "spec" / "features" / "FEAT-910-configured-archive.yaml"
    feature = _base_feature(status="backlog")
    feature["id"] = "FEAT-910"

    (tmp_path / "engineeringagent.toml").write_text(
        'docs-root = "docs.engineeringagent"\n',
        encoding="utf-8",
    )
    _write_yaml(
        tmp_path / "harness" / "gates.yaml",
        {
            "profiles": {"loop_fast": []},
            "gates": {},
        },
    )
    _write_yaml(feature_path, feature)

    script_path = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-configured-archive.py"
    )
    _init_git_repo(tmp_path)

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=tmp_path,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=5,
        )

    archived_path = (
        docs_root / "spec" / "features_done" / "FEAT-910-configured-archive.yaml"
    )
    assert code == 0
    assert not feature_path.exists()
    assert archived_path.exists()


def test_run_loop_commit_ignores_runs_jsonl_when_gitignored(tmp_path: Path) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    script_path = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done.py"
    )
    (project_root / ".gitignore").write_text("progress/runs.jsonl\n", encoding="utf-8")
    _init_git_repo(project_root)

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=5,
        )

    assert code == 0
    assert (project_root / "progress" / "runs.jsonl").exists()
    status = _run_git(project_root, "status", "--short").stdout
    assert "progress/runs.jsonl" not in status


def test_run_loop_writes_per_feature_progress_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(presentation_module, "_stdout_is_tty", lambda _stdout: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    script_path = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-progress-log.py"
    )
    _init_git_repo(project_root)

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=5,
        )

    assert code == 0
    feature_log_path = project_root / "progress" / "run-feature-FEAT-900.txt"
    assert feature_log_path.exists()
    log_text = feature_log_path.read_text(encoding="utf-8")
    assert "attempt=1" in log_text
    assert "feature_id=FEAT-900" in log_text
    assert "result=passed" in log_text
    assert "\x1b[" not in log_text


def test_run_loop_progress_logs_are_gitignored(tmp_path: Path) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    script_path = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-progress-log-ignore.py"
    )
    (project_root / ".gitignore").write_text(
        "progress/runs.jsonl\nprogress/run-feature-*.txt\n",
        encoding="utf-8",
    )
    _init_git_repo(project_root)

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=5,
        )

    assert code == 0
    assert (project_root / "progress" / "run-feature-FEAT-900.txt").exists()
    status = _run_git(project_root, "status", "--short").stdout
    assert "progress/runs.jsonl" not in status
    assert "progress/run-feature-FEAT-900.txt" not in status


def test_run_loop_concise_mode_hides_raw_implement_and_gate_output(
    tmp_path: Path, capsys: Any
) -> None:
    implement_stdout_token = "IMPLEMENT_RAW_STDOUT_TOKEN"
    implement_stderr_token = "IMPLEMENT_RAW_STDERR_TOKEN"
    gate_stdout_token = "GATE_RAW_STDOUT_TOKEN"
    gate_stderr_token = "GATE_RAW_STDERR_TOKEN"

    gate_script = tmp_path.parent / f"{tmp_path.name}-emit-gate-output.py"
    gate_script.write_text(
        "\n".join(
            [
                "import sys",
                f"print({gate_stdout_token!r})",
                f"print({gate_stderr_token!r}, file=sys.stderr)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    gates_data = {
        "profiles": {"loop_fast": ["emit_gate_output"]},
        "gates": {"emit_gate_output": {"run": f'"{sys.executable}" "{gate_script}"'}},
    }
    project_root, feature_path = _make_project_root(
        tmp_path,
        feature_data=_base_feature(),
        gates_data=gates_data,
    )
    _init_git_repo(project_root)

    def implement_effect() -> None:
        feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
        feature["status"] = "done"
        feature_path.write_text(
            yaml.safe_dump(feature, sort_keys=False),
            encoding="utf-8",
        )

    with (
        _with_opencode_implement_side_effect(implement_effect),
        _with_opencode_implement_result(
            stdout=f"{implement_stdout_token}\n",
            stderr=f"{implement_stderr_token}\n",
        ),
    ):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=5,
            verbose_output=False,
        )

    output = capsys.readouterr().out
    assert code == 0
    assert implement_stdout_token not in output
    assert gate_stdout_token not in output

    feature_log_path = project_root / "progress" / "run-feature-FEAT-900.txt"
    log_text = feature_log_path.read_text(encoding="utf-8")
    assert implement_stdout_token in log_text
    assert implement_stderr_token in log_text
    assert gate_stdout_token in log_text
    assert gate_stderr_token in log_text
    assert "command_timing phase=gates gate=emit_gate_output" in log_text


def test_run_loop_verbose_output_streams_raw_implement_and_gate_output(
    tmp_path: Path, capsys: Any
) -> None:
    implement_stdout_token = "IMPLEMENT_VERBOSE_STDOUT_TOKEN"
    implement_stderr_token = "IMPLEMENT_VERBOSE_STDERR_TOKEN"
    gate_stdout_token = "GATE_VERBOSE_STDOUT_TOKEN"
    gate_stderr_token = "GATE_VERBOSE_STDERR_TOKEN"

    gate_script = tmp_path.parent / f"{tmp_path.name}-emit-gate-verbose-output.py"
    gate_script.write_text(
        "\n".join(
            [
                "import sys",
                f"print({gate_stdout_token!r})",
                f"print({gate_stderr_token!r}, file=sys.stderr)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    gates_data = {
        "profiles": {"loop_fast": ["emit_gate_output"]},
        "gates": {"emit_gate_output": {"run": f'"{sys.executable}" "{gate_script}"'}},
    }
    project_root, feature_path = _make_project_root(
        tmp_path,
        feature_data=_base_feature(),
        gates_data=gates_data,
    )
    _init_git_repo(project_root)

    def implement_effect() -> None:
        feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
        feature["status"] = "done"
        feature_path.write_text(
            yaml.safe_dump(feature, sort_keys=False),
            encoding="utf-8",
        )

    with (
        _with_opencode_implement_side_effect(implement_effect),
        _with_opencode_implement_result(
            stdout=f"{implement_stdout_token}\n",
            stderr=f"{implement_stderr_token}\n",
        ),
    ):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=5,
            verbose_output=True,
        )

    captured = capsys.readouterr()
    merged_output = captured.out + captured.err
    assert code == 0
    assert implement_stdout_token in merged_output
    assert implement_stderr_token in merged_output
    assert gate_stdout_token in merged_output
    assert gate_stderr_token in merged_output


def test_run_loop_plain_output_when_not_tty(
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    monkeypatch.setattr(presentation_module, "_stdout_is_tty", lambda _stdout: False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    loop_module.print_summary(
        feature_id="FEAT-900",
        result="passed",
        failed_gate=None,
        attempt=1,
        next_action="continue_same_feature",
    )

    output = capsys.readouterr().out
    assert "\x1b[" not in output
    assert "Loop summary: result=passed" in output
    assert "next=continue_same_feature" in output


def test_run_loop_styled_output_when_tty(
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    monkeypatch.setattr(presentation_module, "_stdout_is_tty", lambda _stdout: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    loop_module.print_summary(
        feature_id="FEAT-900",
        result="passed",
        failed_gate=None,
        attempt=1,
        next_action="continue_same_feature",
    )

    output = capsys.readouterr().out
    assert "\x1b[" in output
    assert "Loop summary: result=passed" in output
    assert "next=continue_same_feature" in output


def test_run_loop_no_color_env_disables_styling(
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    monkeypatch.setattr(presentation_module, "_stdout_is_tty", lambda _stdout: True)
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "xterm-256color")

    loop_module.print_summary(
        feature_id="FEAT-900",
        result="failed",
        failed_gate="spec_validate",
        attempt=1,
        next_action="retry_same_feature",
    )

    output = capsys.readouterr().out
    assert "\x1b[" not in output
    assert "Loop summary: result=failed" in output
    assert "Failed gate: spec_validate" in output


def test_run_loop_iteration_output_uses_emoji_contract(
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    monkeypatch.setattr(presentation_module, "_stdout_is_tty", lambda _stdout: False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    loop_module.print_summary(
        feature_id="FEAT-900",
        result="passed",
        failed_gate=None,
        attempt=1,
        next_action="continue_same_feature",
        selected_path="docs/spec/features/FEAT-900.yaml",
        implement_step="opencode run --agent engineeringagent",
    )
    loop_module.print_summary(
        feature_id="FEAT-900",
        result="failed",
        failed_gate="spec_validate",
        attempt=2,
        next_action="retry_same_feature",
        selected_path="docs/spec/features/FEAT-900.yaml",
        implement_step="opencode run --agent engineeringagent",
        log_path="progress/run-feature-FEAT-900.txt",
    )
    loop_module.print_summary(
        feature_id="FEAT-900",
        result="passed",
        failed_gate=None,
        attempt=3,
        next_action="select_next_feature",
        selected_path="docs/spec/features/FEAT-900.yaml",
        implement_step="opencode run --agent engineeringagent",
        archived_selection_path="docs/spec/features_done/FEAT-900.yaml",
    )

    output = capsys.readouterr().out
    assert "🔁 Iteration 1 · FEAT-900" in output
    assert "🎯 Selected: docs/spec/features/FEAT-900.yaml" in output
    assert "🛠 Implement: opencode run --agent engineeringagent" in output
    assert "✅ Passed" in output
    assert "➡️ Next: continue_same_feature" in output
    assert "🔁 Iteration 2 · FEAT-900" in output
    assert "❌ Failed: gate=spec_validate" in output
    assert "📄 Log: progress/run-feature-FEAT-900.txt" in output
    assert "➡️ Next: retry_same_feature" in output
    assert "♻️ Selected archived counterpart:" in output
    assert "➡️ Next: select_next_feature" in output


def test_run_loop_passed_iteration_not_completed_records_continue_next_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    monkeypatch.setattr(presentation_module, "_stdout_is_tty", lambda _stdout: False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature(status="backlog")
    )
    _init_git_repo(project_root)

    with _with_opencode_implement_result(returncode=0, stdout="ok\n", stderr=""):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=1,
        )

    output = capsys.readouterr().out
    assert code == 1
    assert "Reached max iteration cap (1) before completion." in output
    assert "next=continue_same_feature" in output

    runs = _read_runs(project_root)
    assert runs
    assert runs[-1]["result"] == "passed"
    assert runs[-1]["next_action"] == "continue_same_feature"


def test_run_loop_telemetry_includes_log_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(presentation_module, "_stdout_is_tty", lambda _stdout: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    script_path = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-log-path.py"
    )
    _init_git_repo(project_root)

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=5,
        )

    assert code == 0
    runs = _read_runs(project_root)
    assert runs
    assert runs[-1]["log_path"] == "progress/run-feature-FEAT-900.txt"
    assert "\x1b[" not in (project_root / "progress" / "runs.jsonl").read_text(
        encoding="utf-8"
    )


def test_run_loop_failure_prints_detailed_log_pointer(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    _init_git_repo(project_root)

    with _with_opencode_implement_result(
        returncode=1, stdout="", stderr="opencode failed"
    ):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=1,
        )

    output = capsys.readouterr().out
    assert code == 1
    assert "result=failed" in output
    assert "Detailed log: progress/run-feature-FEAT-900.txt" in output


def test_run_loop_requires_clean_worktree_by_default(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    _init_git_repo(project_root)

    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    feature["context"] = "dirty change"
    _write_yaml(feature_path, feature)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=False,
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "Precondition failed" in output
    assert "--allow-dirty" in output


def test_run_loop_archives_done_active_feature(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path,
        feature_data=_base_feature(status="done"),
    )
    _init_git_repo(project_root)

    monkeypatch.setattr(
        loop_module,
        "run_implement_step",
        lambda *_args, **_kwargs: (True, None, ""),
    )
    monkeypatch.setattr(
        loop_module,
        "_run_opencode_permission_precheck",
        lambda **_: True,
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=False,
        max_iterations=2,
    )

    archived_path = project_root / "docs" / "spec" / "features_done" / feature_path.name
    assert code == 0
    assert not feature_path.exists()
    assert archived_path.exists()


def test_run_loop_requires_git_repo_before_allow_dirty_hint(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=False,
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "Precondition failed" in output
    assert "run inside a git repository" in output
    assert "--allow-dirty" not in output
    assert "git init" in output


def test_enforce_worktree_precondition_reads_git_status_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def fake_status_porcelain(project_root: Path) -> subprocess.CompletedProcess[str]:
        calls.append(project_root)
        return subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(loop_module, "status_porcelain", fake_status_porcelain)

    code = loop_module._enforce_worktree_precondition(tmp_path, allow_dirty=False)

    assert code is None
    assert calls == [tmp_path]


def test_run_loop_allows_uncommitted_changes_with_allow_dirty(
    tmp_path: Path, capsys: Any
) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    script_path = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-allow-dirty.py"
    )
    _init_git_repo(project_root)

    (project_root / "notes.txt").write_text("restart with edits\n", encoding="utf-8")

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            allow_dirty=True,
            max_iterations=5,
        )

    output = capsys.readouterr().out
    assert code == 0
    assert "Allow-dirty override enabled" in output


def test_run_loop_moves_completed_feature_to_features_done(tmp_path: Path) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    script_path = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-archive.py"
    )
    _init_git_repo(project_root)

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=5,
        )

    archived_path = project_root / "docs" / "spec" / "features_done" / feature_path.name
    assert code == 0
    assert not feature_path.exists()
    assert archived_path.exists()


def test_run_loop_selected_feature_moved_to_features_done_does_not_crash(
    tmp_path: Path,
    capsys: Any,
) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    _init_git_repo(project_root)
    script_path = _write_move_to_done_script(
        tmp_path.parent / f"{tmp_path.name}-move-selected-to-done.py"
    )

    def implement_effect() -> None:
        _run_python_script(script_path, project_root, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=3,
        )

    archived_path = project_root / "docs" / "spec" / "features_done" / feature_path.name
    output = capsys.readouterr().out
    assert code == 0
    assert not feature_path.exists()
    assert archived_path.exists()
    assert (
        "Selected feature path missing after iteration; using archived counterpart"
        in output
    )
    assert "Loop summary: result=passed" in output
    assert "next=select_next_feature" in output
    runs = _read_runs(project_root)
    assert runs
    assert runs[-1]["result"] == "passed"
    assert runs[-1]["failed_gate"] is None
    assert runs[-1]["next_action"] == "select_next_feature"


def test_run_loop_archived_done_without_completion_commit_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    _init_git_repo(project_root)

    def fake_choose_feature_with_selector(
        project_root: Path,
        pending: list[tuple[Path, dict[str, Any]]],
    ) -> tuple[Path, dict[str, Any]]:
        chosen_path, chosen_feature = pending[0]
        _move_feature_to_done(project_root, chosen_path)
        return chosen_path, chosen_feature

    monkeypatch.setattr(
        loop_module,
        "_choose_feature_with_selector",
        fake_choose_feature_with_selector,
    )
    monkeypatch.setattr(
        loop_module,
        "_run_opencode_permission_precheck",
        lambda **_: True,
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=False,
        run_all=True,
        max_iterations=3,
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "already archived with status=done" in output
    assert "next=retry_same_feature" in output

    runs = _read_runs(project_root)
    assert runs
    assert runs[-1]["result"] == "failed"
    assert runs[-1]["failed_gate"] == "feature_missing"
    assert runs[-1]["next_action"] == "retry_same_feature"
    assert all(run["next_action"] != "select_next_feature" for run in runs)


def test_run_loop_all_selected_feature_moved_to_features_done_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    project_root, first_feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    second_feature = _base_feature(status="backlog")
    second_feature["id"] = "FEAT-901"
    second_feature_path = (
        project_root / "docs" / "spec" / "features" / "FEAT-901-secondary.yaml"
    )
    _write_yaml(second_feature_path, second_feature)
    _init_git_repo(project_root)

    def fake_run_implement_step(
        project_root: Path,
        feature: dict[str, Any],
        feature_path: Path,
        hook_feedback: str | None,
        verbose_output: bool,
    ) -> tuple[bool, str | None, str]:
        del hook_feedback, verbose_output
        if str(feature.get("id", "")) == "FEAT-900":
            _move_feature_to_done(project_root, feature_path)
            return (True, None, "")
        feature["status"] = "done"
        _write_yaml(feature_path, feature)
        return (True, None, "")

    monkeypatch.setattr(loop_module, "run_implement_step", fake_run_implement_step)
    monkeypatch.setattr(
        loop_module,
        "_run_opencode_permission_precheck",
        lambda **_: True,
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=False,
        run_all=True,
        max_iterations=5,
    )

    archived_first = (
        project_root / "docs" / "spec" / "features_done" / first_feature_path.name
    )
    archived_second = (
        project_root / "docs" / "spec" / "features_done" / second_feature_path.name
    )
    output = capsys.readouterr().out
    assert code == 0
    assert not first_feature_path.exists()
    assert not second_feature_path.exists()
    assert archived_first.exists()
    assert archived_second.exists()
    assert (
        "Selected feature path missing after iteration; using archived counterpart"
        in output
    )
    assert "All provided features are done and committed." in output
    run_feature_ids = [run["feature_id"] for run in _read_runs(project_root)]
    assert "FEAT-900" in run_feature_ids
    assert "FEAT-901" in run_feature_ids


def test_run_loop_missing_selected_feature_without_archive_fails_cleanly(
    tmp_path: Path,
    capsys: Any,
) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    _init_git_repo(project_root)
    script_path = _write_delete_selected_feature_script(
        tmp_path.parent / f"{tmp_path.name}-delete-selected-feature.py"
    )

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=3,
        )

    output = capsys.readouterr().out
    assert code == 1
    assert (
        "Stopping loop: selected feature path is missing and not recoverable." in output
    )
    assert "selected feature path disappeared during loop iteration" in output
    assert str(feature_path) in output

    runs = _read_runs(project_root)
    assert runs
    assert runs[-1]["result"] == "failed"
    assert runs[-1]["failed_gate"] == "feature_missing"


def test_run_loop_archives_preexisting_done_target_after_pending_completes(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    preexisting_done_path = (
        project_root / "docs" / "spec" / "features" / "FEAT-901-preexisting-done.yaml"
    )
    preexisting_done_feature = _base_feature(status="done")
    preexisting_done_feature["id"] = "FEAT-901"
    _write_yaml(preexisting_done_path, preexisting_done_feature)

    _init_git_repo(project_root)

    def fake_run_implement_step(
        project_root: Path,
        feature: dict[str, Any],
        feature_path: Path,
        hook_feedback: str | None,
        verbose_output: bool,
    ) -> tuple[bool, str | None, str]:
        del project_root, hook_feedback, verbose_output
        if str(feature.get("id", "")) == "FEAT-900":
            feature["status"] = "done"
            _write_yaml(feature_path, feature)
        return (True, None, "")

    monkeypatch.setattr(loop_module, "run_implement_step", fake_run_implement_step)
    monkeypatch.setattr(
        loop_module,
        "_run_opencode_permission_precheck",
        lambda **_: True,
    )
    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path), str(preexisting_done_path)],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=False,
        max_iterations=5,
    )

    archived_selected_path = (
        project_root / "docs" / "spec" / "features_done" / feature_path.name
    )
    archived_preexisting_done_path = (
        project_root / "docs" / "spec" / "features_done" / preexisting_done_path.name
    )

    assert code == 0
    assert archived_selected_path.exists()
    assert not feature_path.exists()
    assert not preexisting_done_path.exists()
    assert archived_preexisting_done_path.exists()


def test_run_loop_archives_done_feature_before_gate_execution(tmp_path: Path) -> None:
    gate_script = tmp_path.parent / f"{tmp_path.name}-assert-pre-gate-archive.py"
    gate_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "active = Path(sys.argv[1])",
                "archived = Path(sys.argv[2])",
                "if active.exists() or not archived.exists():",
                "    raise SystemExit(1)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    feature_data = _base_feature()
    gates_data = {
        "profiles": {"loop_fast": ["assert_pre_gate_archive"]},
        "gates": {
            "assert_pre_gate_archive": {
                "run": (
                    f'"{sys.executable}" "{gate_script}" '
                    "docs/spec/features/FEAT-900-ralph-test.yaml "
                    "docs/spec/features_done/FEAT-900-ralph-test.yaml"
                )
            }
        },
    }
    project_root, feature_path = _make_project_root(
        tmp_path,
        feature_data=feature_data,
        gates_data=gates_data,
    )
    script_path = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-pre-gate-archive.py"
    )
    _init_git_repo(project_root)

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=5,
        )

    archived_path = project_root / "docs" / "spec" / "features_done" / feature_path.name
    assert code == 0
    assert not feature_path.exists()
    assert archived_path.exists()


def test_run_loop_restores_archived_feature_when_gate_fails_after_prearchive(
    tmp_path: Path,
) -> None:
    gate_script = tmp_path.parent / f"{tmp_path.name}-fail-after-pre-gate-archive.py"
    gate_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "active = Path(sys.argv[1])",
                "archived = Path(sys.argv[2])",
                "if active.exists() or not archived.exists():",
                "    raise SystemExit('pre-gate archive ordering check failed')",
                "raise SystemExit('forced gate failure after pre-archive')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    feature_data = _base_feature()
    gates_data = {
        "profiles": {"loop_fast": ["spec_validate"]},
        "gates": {
            "spec_validate": {
                "run": (
                    f'"{sys.executable}" "{gate_script}" '
                    "docs/spec/features/FEAT-900-ralph-test.yaml "
                    "docs/spec/features_done/FEAT-900-ralph-test.yaml"
                )
            }
        },
    }
    project_root, feature_path = _make_project_root(
        tmp_path,
        feature_data=feature_data,
        gates_data=gates_data,
    )
    script_path = _write_move_to_done_script(
        tmp_path.parent / f"{tmp_path.name}-move-done-rollback.py"
    )
    _init_git_repo(project_root)

    def implement_effect() -> None:
        _run_python_script(script_path, project_root, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=1,
        )

    archived_path = project_root / "docs" / "spec" / "features_done" / feature_path.name
    restored_feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    runs = _read_runs(project_root)

    assert code == 1
    assert feature_path.exists()
    assert not archived_path.exists()
    assert restored_feature["status"] == "done"
    assert runs[-1]["result"] == "failed"
    assert runs[-1]["failed_gate"] == "spec_validate"
    assert runs[-1]["next_action"] == "retry_same_feature"


def test_run_loop_spec_validate_no_longer_blocks_done_archive_ordering(
    tmp_path: Path,
) -> None:
    gate_script = (
        tmp_path.parent / f"{tmp_path.name}-spec-validate-done-in-active-check.py"
    )
    gate_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "import yaml",
                "active = Path(sys.argv[1])",
                "if active.exists():",
                "    feature = yaml.safe_load(active.read_text(encoding='utf-8'))",
                "    if feature.get('status') == 'done':",
                "        raise SystemExit('spec_validate blocked: done feature remained in active dir')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    feature_data = _base_feature()
    gates_data = {
        "profiles": {"loop_fast": ["spec_validate"]},
        "gates": {
            "spec_validate": {
                "run": (
                    f'"{sys.executable}" "{gate_script}" '
                    "docs/spec/features/FEAT-900-ralph-test.yaml"
                )
            }
        },
    }
    project_root, feature_path = _make_project_root(
        tmp_path,
        feature_data=feature_data,
        gates_data=gates_data,
    )
    script_path = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-spec-validate-ordering.py"
    )
    _init_git_repo(project_root)

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=5,
        )

    archived_path = project_root / "docs" / "spec" / "features_done" / feature_path.name
    runs = _read_runs(project_root)

    assert code == 0
    assert not feature_path.exists()
    assert archived_path.exists()
    assert len(runs) == 1
    assert runs[0]["result"] == "passed"
    assert runs[0]["failed_gate"] is None


def test_run_loop_completion_commit_includes_archive_move(tmp_path: Path) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    script_path = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-commit-move.py"
    )
    _init_git_repo(project_root)

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=5,
        )

    assert code == 0
    changed_paths = _run_git(
        project_root,
        "show",
        "--name-status",
        "--pretty=format:",
        "HEAD",
    ).stdout.splitlines()
    expected_rename_suffix = (
        f"\tdocs/spec/features/{feature_path.name}"
        f"\tdocs/spec/features_done/{feature_path.name}"
    )
    assert any(
        line.startswith("R") and line.endswith(expected_rename_suffix)
        for line in changed_paths
    )


def test_loop_uses_expected_commit_subject(tmp_path: Path) -> None:
    feature_data = _base_feature()
    feature_data["expected_commit_subject"] = "docs: publish FEAT-900 release notes"
    project_root, feature_path = _make_project_root(tmp_path, feature_data=feature_data)
    script_path = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-expected-subject.py"
    )
    _init_git_repo(project_root)

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=5,
        )

    assert code == 0
    subject = _run_git(project_root, "log", "-1", "--pretty=%s").stdout.strip()
    assert subject == "docs: publish FEAT-900 release notes"


def test_loop_commit_subject_fallback_uses_type_mapping(tmp_path: Path) -> None:
    feature_data = _base_feature()
    feature_data.pop("expected_commit_subject")
    feature_data["type"] = "bug"
    project_root, feature_path = _make_project_root(tmp_path, feature_data=feature_data)
    script_path = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done-fallback-subject.py"
    )
    _init_git_repo(project_root)

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=5,
        )

    assert code == 0
    subject = _run_git(project_root, "log", "-1", "--pretty=%s").stdout.strip()
    assert subject.startswith("fix: complete FEAT-900")


def test_git_add_failure_exits_immediately(tmp_path: Path) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    script_path = _write_set_done_script(
        tmp_path.parent / f"{tmp_path.name}-set-done.py"
    )
    _init_git_repo(project_root)

    (project_root / ".git" / "index.lock").write_text("locked\n", encoding="utf-8")

    def implement_effect() -> None:
        _run_python_script(script_path, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=6,
        )

    assert code == 1
    runs = _read_runs(project_root)
    assert len(runs) == 1
    assert runs[0]["result"] == "failed"
    assert runs[0]["failed_gate"] == "git_add"
    assert runs[0]["attempt"] == 1


def test_run_loop_commit_failure_preserves_retryable_feature_path(
    tmp_path: Path,
) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    script_path = tmp_path.parent / f"{tmp_path.name}-set-done-allow.py"
    attempted_paths_path = project_root / ".attempted_feature_paths"
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "import yaml",
                "project_root = Path(sys.argv[1])",
                "feature_path = Path(sys.argv[2])",
                "counter_path = project_root / '.attempt_count'",
                "count = int(counter_path.read_text(encoding='utf-8')) if counter_path.exists() else 0",
                "count += 1",
                "counter_path.write_text(str(count), encoding='utf-8')",
                "attempted_paths_path = project_root / '.attempted_feature_paths'",
                "with attempted_paths_path.open('a', encoding='utf-8') as f:",
                "    f.write(str(feature_path) + '\\n')",
                "feature = yaml.safe_load(feature_path.read_text(encoding='utf-8'))",
                "feature['status'] = 'done'",
                "done_path = project_root / 'docs' / 'spec' / 'features_done' / feature_path.name",
                "done_path.parent.mkdir(parents=True, exist_ok=True)",
                "done_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding='utf-8')",
                "feature_path.unlink()",
                "if count >= 2:",
                "    (project_root / '.allow_commit').write_text('ok\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _init_git_repo(project_root)

    hook_path = project_root / ".git" / "hooks" / "pre-commit"
    hook_path.write_text(
        "#!/usr/bin/env bash\n"
        "if [ ! -f .allow_commit ]; then\n"
        "  echo hook blocked\n"
        "  exit 1\n"
        "fi\n",
        encoding="utf-8",
    )
    hook_path.chmod(0o755)

    def implement_effect() -> None:
        _run_python_script(script_path, project_root, feature_path)

    with _with_opencode_implement_side_effect(implement_effect):
        code = run_loop(
            project_root=project_root,
            feature_paths=[str(feature_path)],
            gate_profile="loop_fast",
            opencode_prompt=None,
            dry_run=False,
            max_iterations=6,
        )

    assert code == 0
    runs = _read_runs(project_root)
    assert len(runs) >= 2
    assert runs[0]["failed_gate"] == "git_commit"
    assert runs[-1]["result"] == "passed"
    archived_path = project_root / "docs" / "spec" / "features_done" / feature_path.name
    assert archived_path.exists()
    attempted_paths = attempted_paths_path.read_text(encoding="utf-8").splitlines()
    assert attempted_paths
    assert all(path == str(feature_path) for path in attempted_paths)


def test_cli_legacy_loop_command_removed() -> None:
    result = _invoke_cli(["loop", "run", "--feature-id", "FEAT-900"])

    assert result.exit_code == 2
    assert "No such command" in result.stderr


def test_cli_run_help_includes_allow_dirty_flag() -> None:
    result = _invoke_cli(["run", "--help"])

    assert result.exit_code == 0
    assert "--allow-dirty" in result.stdout


def test_cli_run_help_includes_verbose_output_flag() -> None:
    result = _invoke_cli(["run", "--help"])

    assert result.exit_code == 0
    assert "--verbose-output" in result.stdout


def test_run_loop_reports_invalid_feature_path(tmp_path: Path, capsys: Any) -> None:
    project_root, _ = _make_project_root(tmp_path, feature_data=_base_feature())
    _init_git_repo(project_root)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(project_root / "missing.yaml")],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=False,
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "does not exist" in output


def test_commit_failure_feedback_still_injected_into_next_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, feature_path = _make_project_root(
        tmp_path, feature_data=_base_feature()
    )
    _init_git_repo(project_root)

    hook_path = project_root / ".git" / "hooks" / "pre-commit"
    hook_path.write_text(
        "#!/usr/bin/env bash\n"
        "if [ ! -f .allow_commit ]; then\n"
        "  echo hook blocked\n"
        "  exit 1\n"
        "fi\n",
        encoding="utf-8",
    )
    hook_path.chmod(0o755)

    real_run = subprocess.run
    prompts: list[str] = []

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if isinstance(command, list) and command[:3] == ["opencode", "run", "--agent"]:
            prompt = command[4]
            prompts.append(prompt)

            feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
            feature["status"] = "done"
            feature_path.write_text(
                yaml.safe_dump(feature, sort_keys=False), encoding="utf-8"
            )

            if len(prompts) >= 2:
                (project_root / ".allow_commit").write_text("ok\n", encoding="utf-8")

            return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

        return real_run(command, **kwargs)

    _patch_start_agent_with_fake(monkeypatch, fake_subprocess_run)
    monkeypatch.setattr(
        loop_module,
        "_run_opencode_permission_precheck",
        lambda **_: True,
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 2
    assert "Previous retry feedback is available" in prompts[1]
    assert "hook blocked" in prompts[1]


def test_verification_failure_feedback_is_injected_into_next_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verification_command = "uv run pytest -q tests/test_verification_feedback.py"
    feature_data = _base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Inject verification failures into retry prompt",
            "status": "backlog",
            "order": 1,
            "context": "Ensure failed verification output appears in next prompt.",
            "verification": [verification_command],
        }
    ]
    project_root, feature_path = _make_project_root(tmp_path, feature_data=feature_data)
    _init_git_repo(project_root)

    real_run = subprocess.run
    prompts: list[str] = []

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if isinstance(command, list) and command[:3] == ["opencode", "run", "--agent"]:
            prompt = command[4]
            prompts.append(prompt)
            feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
            subtasks = feature.get("subtasks", [])
            if len(prompts) == 1 and subtasks and isinstance(subtasks[0], dict):
                subtasks[0]["status"] = "done"
                feature["status"] = "in_progress"
            else:
                feature["status"] = "done"
            feature_path.write_text(
                yaml.safe_dump(feature, sort_keys=False), encoding="utf-8"
            )
            return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")
        return real_run(command, **kwargs)

    verification_results = iter(
        [
            subprocess.CompletedProcess(
                ["verify", "attempt-1"],
                1,
                stdout="VERIFICATION_FAILURE_TOKEN\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                ["verify", "attempt-2"],
                0,
                stdout="verification passed\n",
                stderr="",
            ),
        ]
    )

    def fake_run_shell_command(
        project_root: Path, command: str
    ) -> subprocess.CompletedProcess[str]:
        del project_root, command
        return next(verification_results)

    _patch_start_agent_with_fake(monkeypatch, fake_subprocess_run)
    monkeypatch.setattr(
        loop_module,
        "_run_opencode_permission_precheck",
        lambda **_: True,
    )
    monkeypatch.setattr(loop_module, "run_shell_command", fake_run_shell_command)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 2
    assert "VERIFICATION_FAILURE_TOKEN" in prompts[1]


def test_gate_failure_feedback_includes_fitness_remediation_guidance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remediation = (
        "Replace forbidden in-repo uvx self-invocations with source-first forms; "
        "prefer uv run python -m engineeringagent.cli ..."
    )
    counter_path = tmp_path / ".check-attempt"
    check_script = tmp_path.parent / f"{tmp_path.name}-check-fail-once.py"
    check_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "counter = Path(sys.argv[1])",
                "count = int(counter.read_text(encoding='utf-8')) if counter.exists() else 0",
                "count += 1",
                "counter.write_text(str(count), encoding='utf-8')",
                "if count == 1:",
                f"    print({remediation!r})",
                "    raise SystemExit(1)",
                "print('ok')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    project_root, feature_path = _make_project_root(
        tmp_path,
        feature_data=_base_feature(),
        gates_data={
            "gates": {
                "fitness_validate": {
                    "run": f'"{sys.executable}" "{check_script}" "{counter_path}"'
                }
            }
        },
    )
    _init_git_repo(project_root)

    real_run = subprocess.run
    prompts: list[str] = []

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if isinstance(command, list) and command[:3] == ["opencode", "run", "--agent"]:
            prompt = command[4]
            prompts.append(prompt)
            feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
            feature["status"] = "done"
            feature_path.write_text(
                yaml.safe_dump(feature, sort_keys=False), encoding="utf-8"
            )
            return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")
        return real_run(command, **kwargs)

    _patch_start_agent_with_fake(monkeypatch, fake_subprocess_run)
    monkeypatch.setattr(
        loop_module,
        "_run_opencode_permission_precheck",
        lambda **_: True,
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 2
    assert remediation in prompts[1]


def test_spec_validate_failure_feedback_round_trips_to_retry_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "SPEC_VALIDATE_ROUND_TRIP_TOKEN"
    counter_path = tmp_path / ".check-attempt"
    check_script = tmp_path.parent / f"{tmp_path.name}-check-spec-validate-fail-once.py"
    check_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "counter = Path(sys.argv[1])",
                "count = int(counter.read_text(encoding='utf-8')) if counter.exists() else 0",
                "count += 1",
                "counter.write_text(str(count), encoding='utf-8')",
                "if count == 1:",
                f"    print({token!r})",
                "    raise SystemExit(1)",
                "print('ok')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    project_root, feature_path = _make_project_root(
        tmp_path,
        feature_data=_base_feature(),
        gates_data={
            "gates": {
                "spec_validate": {
                    "run": f'"{sys.executable}" "{check_script}" "{counter_path}"'
                }
            }
        },
    )
    _init_git_repo(project_root)

    real_run = subprocess.run
    prompts: list[str] = []

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if isinstance(command, list) and command[:3] == ["opencode", "run", "--agent"]:
            prompt = command[4]
            prompts.append(prompt)
            feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
            feature["status"] = "done"
            feature_path.write_text(
                yaml.safe_dump(feature, sort_keys=False), encoding="utf-8"
            )
            return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")
        return real_run(command, **kwargs)

    _patch_start_agent_with_fake(monkeypatch, fake_subprocess_run)
    monkeypatch.setattr(
        loop_module,
        "_run_opencode_permission_precheck",
        lambda **_: True,
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 2
    assert token in prompts[1]


def test_non_validation_gate_failure_feedback_round_trips_to_retry_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "NON_VALIDATION_GATE_ROUND_TRIP_TOKEN"
    counter_path = tmp_path / ".check-attempt"
    check_script = tmp_path.parent / f"{tmp_path.name}-check-pytest-fail-once.py"
    check_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "counter = Path(sys.argv[1])",
                "count = int(counter.read_text(encoding='utf-8')) if counter.exists() else 0",
                "count += 1",
                "counter.write_text(str(count), encoding='utf-8')",
                "if count == 1:",
                f"    print({token!r})",
                "    raise SystemExit(1)",
                "print('ok')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    project_root, feature_path = _make_project_root(
        tmp_path,
        feature_data=_base_feature(),
        gates_data={
            "gates": {
                "pytest_validate": {
                    "run": f'"{sys.executable}" "{check_script}" "{counter_path}"'
                }
            }
        },
    )
    _init_git_repo(project_root)

    real_run = subprocess.run
    prompts: list[str] = []

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if isinstance(command, list) and command[:3] == ["opencode", "run", "--agent"]:
            prompt = command[4]
            prompts.append(prompt)
            feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
            feature["status"] = "done"
            feature_path.write_text(
                yaml.safe_dump(feature, sort_keys=False), encoding="utf-8"
            )
            return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")
        return real_run(command, **kwargs)

    _patch_start_agent_with_fake(monkeypatch, fake_subprocess_run)
    monkeypatch.setattr(
        loop_module,
        "_run_opencode_permission_precheck",
        lambda **_: True,
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 2
    assert token in prompts[1]


def test_gate_failure_feedback_replaces_previous_feedback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_token = "FIRST_GATE_FAILURE_TOKEN"
    second_token = "SECOND_GATE_FAILURE_TOKEN"
    counter_path = tmp_path / ".check-attempt"
    check_script = tmp_path.parent / f"{tmp_path.name}-check-fail-twice.py"
    check_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "counter = Path(sys.argv[1])",
                "count = int(counter.read_text(encoding='utf-8')) if counter.exists() else 0",
                "count += 1",
                "counter.write_text(str(count), encoding='utf-8')",
                "if count == 1:",
                f"    print({first_token!r})",
                "    raise SystemExit(1)",
                "if count == 2:",
                f"    print({second_token!r})",
                "    raise SystemExit(1)",
                "print('ok')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    project_root, feature_path = _make_project_root(
        tmp_path,
        feature_data=_base_feature(),
        gates_data={
            "gates": {
                "spec_validate": {
                    "run": f'"{sys.executable}" "{check_script}" "{counter_path}"'
                }
            }
        },
    )
    _init_git_repo(project_root)

    real_run = subprocess.run
    prompts: list[str] = []

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if isinstance(command, list) and command[:3] == ["opencode", "run", "--agent"]:
            prompt = command[4]
            prompts.append(prompt)
            feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
            feature["status"] = "done"
            feature_path.write_text(
                yaml.safe_dump(feature, sort_keys=False), encoding="utf-8"
            )
            return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")
        return real_run(command, **kwargs)

    _patch_start_agent_with_fake(monkeypatch, fake_subprocess_run)
    monkeypatch.setattr(
        loop_module,
        "_run_opencode_permission_precheck",
        lambda **_: True,
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 3
    assert first_token in prompts[1]
    assert second_token not in prompts[1]
    assert second_token in prompts[2]
    assert first_token not in prompts[2]


def test_verification_failure_feedback_replaces_previous_feedback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verification_command = "uv run pytest -q tests/test_verification_feedback.py"
    feature_data = _base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Replace verification feedback between retries",
            "status": "backlog",
            "order": 1,
            "context": "Ensure latest verification output replaces stale feedback.",
            "verification": [verification_command],
        },
        {
            "id": "ST-002",
            "title": "Trigger second verification failure",
            "status": "backlog",
            "order": 2,
            "context": "Ensure second retry carries newer verification feedback.",
            "verification": [verification_command],
        },
    ]
    project_root, feature_path = _make_project_root(tmp_path, feature_data=feature_data)
    _init_git_repo(project_root)

    real_run = subprocess.run
    prompts: list[str] = []

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if isinstance(command, list) and command[:3] == ["opencode", "run", "--agent"]:
            prompt = command[4]
            prompts.append(prompt)
            feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
            subtasks = feature.get("subtasks", [])
            if (
                len(prompts) == 1
                and len(subtasks) >= 1
                and isinstance(subtasks[0], dict)
            ):
                subtasks[0]["status"] = "done"
                feature["status"] = "in_progress"
            elif (
                len(prompts) == 2
                and len(subtasks) >= 2
                and isinstance(subtasks[1], dict)
            ):
                subtasks[1]["status"] = "done"
                feature["status"] = "in_progress"
            else:
                feature["status"] = "done"
            feature_path.write_text(
                yaml.safe_dump(feature, sort_keys=False), encoding="utf-8"
            )
            return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")
        return real_run(command, **kwargs)

    verification_results = iter(
        [
            subprocess.CompletedProcess(
                ["verify", "attempt-1"],
                1,
                stdout="FIRST_VERIFICATION_FAILURE_TOKEN\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                ["verify", "attempt-2"],
                1,
                stdout="SECOND_VERIFICATION_FAILURE_TOKEN\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                ["verify", "attempt-3"],
                0,
                stdout="verification passed\n",
                stderr="",
            ),
        ]
    )

    def fake_run_shell_command(
        project_root: Path, command: str
    ) -> subprocess.CompletedProcess[str]:
        del project_root, command
        return next(verification_results)

    _patch_start_agent_with_fake(monkeypatch, fake_subprocess_run)
    monkeypatch.setattr(
        loop_module,
        "_run_opencode_permission_precheck",
        lambda **_: True,
    )
    monkeypatch.setattr(loop_module, "run_shell_command", fake_run_shell_command)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 3
    assert "FIRST_VERIFICATION_FAILURE_TOKEN" in prompts[1]
    assert "SECOND_VERIFICATION_FAILURE_TOKEN" not in prompts[1]
    assert "SECOND_VERIFICATION_FAILURE_TOKEN" in prompts[2]
    assert "FIRST_VERIFICATION_FAILURE_TOKEN" not in prompts[2]


def test_gate_failure_feedback_is_truncated_before_prompt_injection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter_path = tmp_path / ".check-attempt"
    check_script = (
        tmp_path.parent / f"{tmp_path.name}-check-large-feedback-fail-once.py"
    )
    check_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "counter = Path(sys.argv[1])",
                "count = int(counter.read_text(encoding='utf-8')) if counter.exists() else 0",
                "count += 1",
                "counter.write_text(str(count), encoding='utf-8')",
                "if count == 1:",
                "    print('BEGIN_GATE_FEEDBACK')",
                "    print('A' * 8200)",
                "    print('END_GATE_FEEDBACK')",
                "    raise SystemExit(1)",
                "print('ok')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    project_root, feature_path = _make_project_root(
        tmp_path,
        feature_data=_base_feature(),
        gates_data={
            "gates": {
                "spec_validate": {
                    "run": f'"{sys.executable}" "{check_script}" "{counter_path}"'
                }
            }
        },
    )
    _init_git_repo(project_root)

    real_run = subprocess.run
    prompts: list[str] = []

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if isinstance(command, list) and command[:3] == ["opencode", "run", "--agent"]:
            prompt = command[4]
            prompts.append(prompt)
            feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
            feature["status"] = "done"
            feature_path.write_text(
                yaml.safe_dump(feature, sort_keys=False), encoding="utf-8"
            )
            return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")
        return real_run(command, **kwargs)

    _patch_start_agent_with_fake(monkeypatch, fake_subprocess_run)
    monkeypatch.setattr(
        loop_module,
        "_run_opencode_permission_precheck",
        lambda **_: True,
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        gate_profile="loop_fast",
        opencode_prompt=None,
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 2
    assert "BEGIN_GATE_FEEDBACK" in prompts[1]
    assert "END_GATE_FEEDBACK" not in prompts[1]
    assert "...[truncated]" in prompts[1]
