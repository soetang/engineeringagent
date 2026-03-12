from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
        / "check_bootstrap_runtime_surface.py"
    )


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


def test_bootstrap_runtime_surface_rule_passes_for_bootstrap_owned_exports(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Pass when bootstrap __init__ only exports bootstrap-owned helpers."""
    init_path = tmp_path / "src" / "engineeringagent" / "bootstrap" / "__init__.py"
    init_path.parent.mkdir(parents=True, exist_ok=True)
    init_path.write_text(
        "\n".join(
            [
                "from importlib import import_module",
                "",
                '__all__ = ["AppFactory", "publish_iteration_report"]',
                "",
                "def __getattr__(name: str):",
                '    if name == "AppFactory":',
                '        return import_module("engineeringagent.bootstrap.app_factory").AppFactory',
                '    if name == "publish_iteration_report":',
                '        return import_module("engineeringagent.bootstrap.iteration_reporting").publish_iteration_report',
                '    raise AttributeError(name)',
                "",
            ]
        ),
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.bootstrap-runtime-surface"
    assert payload["status"] == "pass"
    assert payload["violations"] == []


def test_bootstrap_runtime_surface_rule_fails_for_adapter_runtime_proxy_exports(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when bootstrap __init__ proxies adapter runtime exports."""
    init_path = tmp_path / "src" / "engineeringagent" / "bootstrap" / "__init__.py"
    init_path.parent.mkdir(parents=True, exist_ok=True)
    init_path.write_text(
        "\n".join(
            [
                "from importlib import import_module",
                "",
                '__all__ = ["AppFactory", "build_loop_run", "run_loop_controller"]',
                "",
                "def __getattr__(name: str):",
                '    if name == "build_loop_run":',
                '        return getattr(import_module("engineeringagent.adapters.runtime"), name)',
                '    if name == "run_loop_controller":',
                '        return import_module("engineeringagent.adapters.runtime").run_loop_controller',
                '    raise AttributeError(name)',
                "",
            ]
        ),
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.bootstrap-runtime-surface"
    assert payload["status"] == "fail"
    assert payload["violations"] == [
        "src/engineeringagent/bootstrap/__init__.py:3 bootstrap package must not re-export 'build_loop_run'; bootstrap package exports must stay bootstrap-owned; call adapter runtime helpers from the adapter package directly instead of proxying them through engineeringagent.bootstrap.",
        "src/engineeringagent/bootstrap/__init__.py:3 bootstrap package must not re-export 'run_loop_controller'; bootstrap package exports must stay bootstrap-owned; call adapter runtime helpers from the adapter package directly instead of proxying them through engineeringagent.bootstrap.",
        "src/engineeringagent/bootstrap/__init__.py:7 bootstrap package must not proxy 'engineeringagent.adapters.runtime'; bootstrap package exports must stay bootstrap-owned; call adapter runtime helpers from the adapter package directly instead of proxying them through engineeringagent.bootstrap.",
        "src/engineeringagent/bootstrap/__init__.py:9 bootstrap package must not proxy 'engineeringagent.adapters.runtime'; bootstrap package exports must stay bootstrap-owned; call adapter runtime helpers from the adapter package directly instead of proxying them through engineeringagent.bootstrap.",
    ]
