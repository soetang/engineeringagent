from __future__ import annotations

from pathlib import Path

from engineeringagent.fitness.builtin_rules import evaluate_loop_subprocess_boundary
from engineeringagent.fitness.registry import builtin_rule_definitions


def _write_module(project_root: Path, relative_path: str, body: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_builtin_rule_definitions_include_loop_subprocess_boundary_rule() -> None:
    """Expose loop subprocess boundary as a registered built-in rule."""
    rule_ids = {
        definition.metadata.rule_id for definition in builtin_rule_definitions()
    }
    assert "architecture.loop-subprocess-boundary" in rule_ids


def test_loop_subprocess_boundary_rule_reports_direct_subprocess_use(
    tmp_path: Path,
) -> None:
    """Fail when a non-allowlisted module invokes subprocess directly."""
    _write_module(
        tmp_path,
        "src/engineeringagent/loop.py",
        "\n".join(
            [
                "import subprocess",
                "",
                "def run() -> None:",
                "    subprocess.run(['git', 'status'], check=False)",
            ]
        ),
    )

    result = evaluate_loop_subprocess_boundary(tmp_path)
    violations = result["violations"]

    assert result["status"] == "fail"
    assert isinstance(violations, list)
    assert any(
        "src/engineeringagent/loop.py:4 uses subprocess.run" in violation
        for violation in violations
    )


def test_loop_subprocess_boundary_rule_reports_subprocess_alias_pattern(
    tmp_path: Path,
) -> None:
    """Fail when alias import wrappers call blocked subprocess APIs."""
    _write_module(
        tmp_path,
        "src/engineeringagent/process_runner.py",
        "\n".join(
            [
                "import subprocess as sp",
                "",
                "def run_process() -> None:",
                "    sp.run(['git', 'status'], check=False)",
            ]
        ),
    )

    result = evaluate_loop_subprocess_boundary(tmp_path)
    violations = result["violations"]

    assert result["status"] == "fail"
    assert isinstance(violations, list)
    assert any(
        "src/engineeringagent/process_runner.py:4 uses sp.run" in violation
        for violation in violations
    )


def test_loop_subprocess_boundary_rule_reports_from_import_pattern(
    tmp_path: Path,
) -> None:
    """Fail when direct-imported subprocess call aliases are invoked."""
    _write_module(
        tmp_path,
        "src/engineeringagent/loop.py",
        "\n".join(
            [
                "from subprocess import run as run_cmd",
                "",
                "def run() -> None:",
                "    run_cmd(['git', 'status'], check=False)",
            ]
        ),
    )

    result = evaluate_loop_subprocess_boundary(tmp_path)
    violations = result["violations"]

    assert result["status"] == "fail"
    assert isinstance(violations, list)
    assert any(
        "src/engineeringagent/loop.py:4 uses run_cmd(...) from subprocess" in violation
        for violation in violations
    )


def test_loop_subprocess_boundary_rule_allows_approved_command_boundary_modules(
    tmp_path: Path,
) -> None:
    """Pass when subprocess calls stay inside explicit allowlisted modules."""
    _write_module(
        tmp_path,
        "src/engineeringagent/gates.py",
        "\n".join(
            [
                "import subprocess",
                "",
                "def run_gate() -> None:",
                "    subprocess.run(['git', 'status'], check=False)",
            ]
        ),
    )

    result = evaluate_loop_subprocess_boundary(tmp_path)

    assert result["status"] == "pass"
    assert result["violations"] == []


def test_loop_subprocess_boundary_rule_allows_git_client_module(tmp_path: Path) -> None:
    """Pass when subprocess calls stay inside the git client boundary."""
    _write_module(
        tmp_path,
        "src/engineeringagent/git/client.py",
        "\n".join(
            [
                "import subprocess",
                "",
                "def run_git() -> None:",
                "    subprocess.run(['git', 'status'], check=False)",
            ]
        ),
    )

    result = evaluate_loop_subprocess_boundary(tmp_path)

    assert result["status"] == "pass"
    assert result["violations"] == []
