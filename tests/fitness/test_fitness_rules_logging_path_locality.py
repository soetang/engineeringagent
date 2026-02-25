from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import cast


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root / "harness" / "fitness-functions" / "check_progress_log_locality.py"
    )


def _write_module(project_root: Path, relative_path: str, body: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _write_progress_paths(project_root: Path) -> None:
    _write_module(project_root, "src/engineeringagent/progress/__init__.py", "")
    _write_module(
        project_root,
        "src/engineeringagent/progress/paths.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "",
                "def runs_jsonl_path(project_root: Path) -> Path:",
                "    return project_root / 'progress' / 'runs' / 'runs.jsonl'",
                "",
                "def run_feature_log_path(project_root: Path, feature_id: str) -> Path:",
                "    return project_root / 'progress' / 'features' / feature_id / 'run.txt'",
            ]
        )
        + "\n",
    )


def _violations(result: dict[str, object]) -> list[str]:
    return cast(list[str], result["violations"])


def _run_checker(
    project_root: Path,
    *,
    checker_path: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    proc = subprocess.run(
        [sys.executable, str(checker_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    return proc, payload


def test_logging_path_locality_checker_emits_expected_rule_id(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Emit the stable rule id from the harness command adapter."""
    _write_progress_paths(tmp_path)

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.progress-log-path-locality"


def test_logging_path_locality_rule_fails_on_inline_progress_path_literal(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail with deterministic diagnostics when progress path literals appear outside helpers."""
    _write_progress_paths(tmp_path)
    _write_module(
        tmp_path,
        "src/engineeringagent/loop_runtime/telemetry.py",
        "PATH = 'progress/runs/runs.jsonl'\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(payload)

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert violations == sorted(violations)
    assert any(
        "src/engineeringagent/loop_runtime/telemetry.py:1 contains progress artifact path literal 'progress/runs/runs.jsonl'"
        in violation
        for violation in violations
    )


def test_logging_path_locality_rule_fails_on_open_keyword_file_write(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when builtin open(file=..., mode='a') targets a loop log sink."""
    _write_progress_paths(tmp_path)
    _write_module(
        tmp_path,
        "src/engineeringagent/loop_runtime/telemetry.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "",
                "from engineeringagent.progress.paths import runs_jsonl_path",
                "",
                "def emit() -> None:",
                "    with open(file=runs_jsonl_path(Path('.')), mode='a', encoding='utf-8') as handle:",
                "        handle.write('ok')",
            ]
        )
        + "\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(payload)

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert any(
        violation.startswith("src/engineeringagent/loop_runtime/telemetry.py:")
        and "writes to loop log sink via direct file I/O (open)" in violation
        for violation in violations
    )


def test_logging_path_locality_rule_passes_when_helpers_are_used_without_direct_writes(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Pass when only helper APIs are referenced (no literals, no direct file I/O)."""
    _write_progress_paths(tmp_path)
    _write_module(
        tmp_path,
        "src/engineeringagent/loop_runtime/telemetry.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "",
                "from engineeringagent.progress.paths import runs_jsonl_path",
                "",
                "def resolve() -> str:",
                "    return str(runs_jsonl_path(Path('.')))",
            ]
        )
        + "\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert not _violations(payload)
