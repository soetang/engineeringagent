from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import cast

import yaml


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness-functions"
        / "check_checks_own_prompt_feedback_rendering.py"
    )


def _write_scope_modules(
    project_root: Path,
    *,
    phases_body: str,
    renderer_body: str,
    loop_body: str = "from __future__ import annotations\n",
) -> None:
    phases_path = project_root / "src/engineeringagent/loop_runtime/phases.py"
    phases_path.parent.mkdir(parents=True, exist_ok=True)
    phases_path.write_text(phases_body, encoding="utf-8")

    loop_path = project_root / "src/engineeringagent/loop.py"
    loop_path.parent.mkdir(parents=True, exist_ok=True)
    loop_path.write_text(loop_body, encoding="utf-8")

    renderer_path = project_root / "src/engineeringagent/prompts/renderer.py"
    renderer_path.parent.mkdir(parents=True, exist_ok=True)
    renderer_path.write_text(renderer_body, encoding="utf-8")


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


def _violations(result: dict[str, object]) -> list[str]:
    return cast(list[str], result["violations"])


def test_checks_owned_prompt_feedback_rule_configuration() -> None:
    manifest_path = Path("harness/fitness-functions/rules.yaml")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    rules = manifest["rules"]
    configured = [
        rule
        for rule in rules
        if isinstance(rule, dict)
        and rule.get("rule_id") == "architecture.checks-own-prompt-feedback-rendering"
    ]

    assert len(configured) == 1
    rule = configured[0]
    assert rule["adapter"] == "command"
    assert rule["severity"] == "error"
    assert rule["command"] == [
        "uv",
        "run",
        "python",
        "harness/fitness-functions/check_checks_own_prompt_feedback_rendering.py",
    ]


def test_checks_owned_prompt_feedback_rule_passes_for_prompt_feedback_forwarding(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_scope_modules(
        tmp_path,
        phases_body="\n".join(
            [
                "from __future__ import annotations",
                "",
                "def run_gate_phase(run_checks):",
                "    result = run_checks()",
                "    return result.prompt_feedback or result.output",
            ]
        )
        + "\n",
        renderer_body="\n".join(
            [
                "from __future__ import annotations",
                "",
                "def inject_feedback(prompt: str, feedback: str | None) -> str:",
                "    if feedback is None:",
                "        return prompt",
                "    return prompt + feedback",
            ]
        )
        + "\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.checks-own-prompt-feedback-rendering"
    assert payload["status"] == "pass"
    assert not _violations(payload)


def test_checks_owned_prompt_feedback_rule_fails_for_checks_specific_shaping(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_scope_modules(
        tmp_path,
        phases_body="\n".join(
            [
                "from __future__ import annotations",
                "from engineeringagent.checks import run_checks",
                "from engineeringagent.prompts.feedback_envelope import build_fitness_failure_feedback",
                "",
                "def run_gate_phase(project_root):",
                "    result = run_checks(project_root, phase='iteration_end')",
                "    if result.ok:",
                "        return result.output",
                "    return build_fitness_failure_feedback(",
                "        gate='fitness',",
                "        command='uv run pytest -q',",
                "        failed_rules=(),",
                "    )",
            ]
        )
        + "\n",
        renderer_body="\n".join(
            [
                "from __future__ import annotations",
                "from engineeringagent.prompts.feedback_envelope import build_reviewer_feedback",
                "",
                "def inject_feedback(prompt: str, feedback: str | None) -> str:",
                "    if feedback:",
                "        return build_reviewer_feedback(",
                "            reviewer_id='reviewer.main',",
                "            reviewer_phase='iteration_end',",
                "            decision={'decision': 'request_changes', 'summary': feedback},",
                "        )",
                "    return prompt",
            ]
        )
        + "\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    violations = _violations(payload)
    assert any(
        "build_fitness_failure_feedback" in violation for violation in violations
    )
    assert any(
        "build_reviewer_feedback" in violation for violation in violations
    )
