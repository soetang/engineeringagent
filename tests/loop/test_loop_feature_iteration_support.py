from __future__ import annotations

from pathlib import Path

import yaml

from tests.loop.feature_iteration_support import (
    base_feature,
    make_project_root,
    run_python_script,
)


def test_base_feature_defaults_to_backlog() -> None:
    feature = base_feature()

    assert feature["id"] == "FEAT-900"
    assert feature["status"] == "backlog"
    assert feature["type"] == "feature"
    assert feature["expected_commit_subject"]


def test_make_project_root_keeps_only_valid_gate_commands(tmp_path: Path) -> None:
    project_root, feature_path = make_project_root(
        tmp_path,
        feature_data=base_feature(),
        gates_data={
            "gates": {
                "good_gate": {"run": "uv run pytest -q"},
                "blank_gate": {"run": "   "},
                "non_mapping": "skip-me",
                "missing_command": {"noop": "ignored"},
            }
        },
    )

    checks_path = project_root / "harness" / "checks.yaml"
    checks_payload = yaml.safe_load(checks_path.read_text(encoding="utf-8"))

    assert feature_path.exists()
    assert checks_payload["checks"] == {
        "good_gate": {"type": "command", "command": "uv run pytest -q"}
    }


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

    run_python_script(script_path, output_path, source_path)

    assert output_path.read_text(encoding="utf-8") == "ok\n"
