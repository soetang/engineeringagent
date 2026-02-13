from __future__ import annotations

from pathlib import Path

from engineeringagent.fitness.builtin_rules import evaluate_loop_subprocess_boundary
from engineeringagent.fitness.registry import builtin_rule_definitions


def _write_loop_module(project_root: Path, body: str) -> None:
    path = project_root / "src" / "engineeringagent" / "loop.py"
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
    """Fail when loop orchestration code invokes subprocess directly."""
    _write_loop_module(
        tmp_path,
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
