import json
import subprocess
import sys
from pathlib import Path


def test_no_facade_varargs_rule_detects_keyword_setattr_signature_masking(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    project_root = tmp_path
    source_root = project_root / "src" / "engineeringagent"
    source_root.mkdir(parents=True)
    (source_root / "loop.py").write_text(
        """
def run_loop() -> int:
    return 0


setattr(run_loop, name="__signature__", value=None)
""".lstrip(),
        encoding="utf-8",
    )

    script_path = (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
        / "check_no_facade_varargs_shims.py"
    )
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    envelope = json.loads(completed.stdout)
    assert envelope["rule_id"] == "architecture.no-facade-varargs-shims"
    assert envelope["status"] == "fail"
    assert any("setattr(run_loop" in violation for violation in envelope["violations"])
