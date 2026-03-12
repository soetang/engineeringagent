from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

import engineeringagent.loop as loop_module
from tests.loop._feedback_envelope import parse_feedback_envelope_from_prompt
from tests.loop.feature_iteration_feedback_support import (
    advance_bundled_plan_prompt_state,
    install_stateful_prompt_agent,
)
from tests.loop.feature_iteration_support import (
    base_feature,
    init_git_repo,
    install_prompt_capture_agent,
    install_shell_command_results,
    make_bundled_project_root,
    make_project_root,
    patch_run_agent_with_fake,
    run_loop,
    write_fail_once_script,
    write_yaml,
)


def _mark_feature_done(feature_path: Path) -> None:
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    feature["status"] = "done"
    feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding="utf-8")


def test_commit_failure_feedback_still_injected_into_next_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    init_git_repo(project_root)

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

    def prompt_handler(
        _prompt: str, prompts: list[str]
    ) -> subprocess.CompletedProcess[str]:
        feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
        feature["status"] = "done"
        feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding="utf-8")
        if len(prompts) >= 2:
            (project_root / ".allow_commit").write_text("ok\n", encoding="utf-8")
        return subprocess.CompletedProcess(["opencode"], 0, stdout="ok\n", stderr="")

    prompts = install_prompt_capture_agent(monkeypatch, prompt_handler)
    monkeypatch.setattr(loop_module, "preflight", lambda **_: True)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 2
    assert prompts[1].strip()

    feedback_line = next(
        line for line in prompts[1].splitlines() if line.lstrip().startswith("{")
    )
    envelope = json.loads(feedback_line)
    assert envelope["kind"] == "command_failure"
    assert envelope["phase"] == "completion_commit"
    assert envelope["gate"] == "git_commit"
    assert "git -c user.name=engineeringagent" in envelope["command"]
    assert envelope["rerun"]["cwd"] == "repo_root"


def test_bundled_phase_verification_failure_feedback_is_injected_into_next_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verification_command = "uv run pytest -q tests/test_phase_verification_feedback.py"
    feature_data = {
        **base_feature(status="in_progress"),
        "title": "Bundled feature feedback test",
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    plan_frontmatter = {
        "plan_id": "FEAT-900",
        "feature_id": "FEAT-900",
        "status": "in_progress",
        "source_spec": "spec.yaml",
        "planning_tier": "planned",
        "phases": [
            {
                "id": "P1",
                "title": "Inject bundled verification failures into retry prompt",
                "status": "pending",
                "verification": [verification_command],
            }
        ],
    }
    project_root, feature_path, plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter=plan_frontmatter,
    )
    init_git_repo(project_root)

    prompts = install_stateful_prompt_agent(
        monkeypatch,
        lambda prompt_count: advance_bundled_plan_prompt_state(
            feature_path,
            plan_path,
            prompt_count=prompt_count,
        ),
    )
    monkeypatch.setattr(loop_module, "preflight", lambda **_: True)
    install_shell_command_results(
        monkeypatch,
        [
            subprocess.CompletedProcess(
                ["verify", "attempt-1"],
                1,
                stdout="PLAN_PHASE_FAILURE_TOKEN\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                ["verify", "attempt-2"],
                0,
                stdout="verification passed\n",
                stderr="",
            ),
        ],
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 2
    assert "PLAN_PHASE_FAILURE_TOKEN" in prompts[1]
    feedback = parse_feedback_envelope_from_prompt(prompts[1], phase="verification")
    assert feedback.kind == "command_failure"
    assert feedback.phase == "verification"
    assert feedback.command == verification_command
    assert "PLAN_PHASE_FAILURE_TOKEN" in feedback.message


def test_bundled_phase_verification_failure_feedback_replaces_previous_feedback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verification_command = "uv run pytest -q tests/test_phase_verification_feedback.py"
    feature_data = {
        **base_feature(status="in_progress"),
        "title": "Bundled phase verification retry feedback replacement",
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    plan_frontmatter = {
        "plan_id": "FEAT-900",
        "feature_id": "FEAT-900",
        "status": "in_progress",
        "source_spec": "spec.yaml",
        "planning_tier": "planned",
        "phases": [
            {
                "id": "P1",
                "title": "Trigger first bundled verification failure",
                "status": "pending",
                "verification": [verification_command],
            },
            {
                "id": "P2",
                "title": "Trigger second bundled verification failure",
                "status": "pending",
                "verification": [verification_command],
            },
        ],
    }
    project_root, feature_path, plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter=plan_frontmatter,
    )
    init_git_repo(project_root)

    prompts = install_stateful_prompt_agent(
        monkeypatch,
        lambda prompt_count: advance_bundled_plan_prompt_state(
            feature_path,
            plan_path,
            prompt_count=prompt_count,
        ),
    )
    verification_results = iter(
        [
            subprocess.CompletedProcess(
                ["verify", "attempt-1"],
                1,
                stdout="FIRST_PLAN_PHASE_FAILURE_TOKEN\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                ["verify", "attempt-2"],
                1,
                stdout="SECOND_PLAN_PHASE_FAILURE_TOKEN\n",
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
        _project_root: Path,
        command: str,
    ) -> subprocess.CompletedProcess[str]:
        del command
        return next(verification_results)

    monkeypatch.setattr(loop_module, "preflight", lambda **_: True)
    monkeypatch.setattr(
        "engineeringagent.adapters.runtime.iteration_phases.run_shell_command",
        fake_run_shell_command,
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 3
    first_feedback = parse_feedback_envelope_from_prompt(
        prompts[1],
        phase="verification",
    )
    second_feedback = parse_feedback_envelope_from_prompt(
        prompts[2],
        phase="verification",
    )
    assert first_feedback.kind == "command_failure"
    assert first_feedback.phase == "verification"
    assert first_feedback.command == verification_command
    assert second_feedback.kind == "command_failure"
    assert second_feedback.phase == "verification"
    assert second_feedback.command == verification_command
    assert "FIRST_PLAN_PHASE_FAILURE_TOKEN" in first_feedback.message
    assert "SECOND_PLAN_PHASE_FAILURE_TOKEN" not in first_feedback.message
    assert "FIRST_PLAN_PHASE_FAILURE_TOKEN" not in second_feedback.message
    assert "SECOND_PLAN_PHASE_FAILURE_TOKEN" in second_feedback.message


def test_bundled_phase_verification_failure_feedback_replaces_previous_command_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_verification_command = (
        "python -c \"import sys; print('FIRST_PLAN_PHASE_FAILURE_TOKEN'); sys.exit(1)\""
    )
    second_verification_command = (
        "python -c \"import sys; print('SECOND_PLAN_PHASE_FAILURE_TOKEN'); sys.exit(1)\""
    )
    feature_data = {
        **base_feature(status="in_progress"),
        "title": "Bundled phase verification command retry replacement",
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    project_root, feature_path, plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Replace first bundled verification command",
                    "status": "pending",
                    "verification": [first_verification_command],
                },
                {
                    "id": "P2",
                    "title": "Replace second bundled verification command",
                    "status": "pending",
                    "verification": [second_verification_command],
                },
            ],
        },
    )
    init_git_repo(project_root)

    prompts = install_stateful_prompt_agent(
        monkeypatch,
        lambda prompt_count: advance_bundled_plan_prompt_state(
            feature_path,
            plan_path,
            prompt_count=prompt_count,
        ),
    )
    verification_results = iter(
        [
            subprocess.CompletedProcess(
                ["verify", "attempt-1"],
                1,
                stdout="FIRST_PLAN_PHASE_FAILURE_TOKEN\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                ["verify", "attempt-2"],
                1,
                stdout="SECOND_PLAN_PHASE_FAILURE_TOKEN\n",
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
        _project_root: Path,
        command: str,
    ) -> subprocess.CompletedProcess[str]:
        del command
        return next(verification_results)

    monkeypatch.setattr(loop_module, "preflight", lambda **_: True)
    monkeypatch.setattr(
        "engineeringagent.adapters.runtime.iteration_phases.run_shell_command",
        fake_run_shell_command,
    )

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 3
    first_feedback = parse_feedback_envelope_from_prompt(
        prompts[1],
        phase="verification",
    )
    second_feedback = parse_feedback_envelope_from_prompt(
        prompts[2],
        phase="verification",
    )
    assert first_feedback.kind == "command_failure"
    assert first_feedback.phase == "verification"
    assert first_feedback.command == first_verification_command
    assert second_feedback.kind == "command_failure"
    assert second_feedback.phase == "verification"
    assert second_feedback.command == second_verification_command
    assert "FIRST_PLAN_PHASE_FAILURE_TOKEN" in first_feedback.message
    assert "SECOND_PLAN_PHASE_FAILURE_TOKEN" not in first_feedback.message
    assert "FIRST_PLAN_PHASE_FAILURE_TOKEN" not in second_feedback.message
    assert "SECOND_PLAN_PHASE_FAILURE_TOKEN" in second_feedback.message


def test_gate_failure_feedback_includes_fitness_remediation_guidance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remediation = (
        "Replace forbidden in-repo uvx self-invocations with source-first forms; "
        "prefer uv run engineeringagent ..."
    )
    counter_path = tmp_path / ".check-attempt"
    check_script = write_fail_once_script(
        tmp_path.parent / f"{tmp_path.name}-check-fail-once.py",
        counter_path,
        remediation,
    )

    project_root, feature_path = make_project_root(
        tmp_path,
        feature_data=base_feature(),
        gates_data={
            "gates": {
                "fitness_validate": {
                    "run": f'"{sys.executable}" "{check_script}" "{counter_path}"'
                }
            }
        },
    )
    init_git_repo(project_root)

    prompts = install_stateful_prompt_agent(
        monkeypatch,
        lambda _prompt_count: _mark_feature_done(feature_path),
    )
    monkeypatch.setattr(loop_module, "preflight", lambda **_: True)
    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 2
    assert "fitness_validate" in prompts[1]
    feedback = parse_feedback_envelope_from_prompt(prompts[1], phase="gates")
    assert feedback.kind == "command_failure"
    assert feedback.phase == "gates"
    assert feedback.command == (f'"{sys.executable}" "{check_script}" "{counter_path}"')
    assert remediation in feedback.message


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

    project_root, feature_path = make_project_root(
        tmp_path,
        feature_data=base_feature(),
        gates_data={
            "gates": {
                "spec_validate": {
                    "run": f'"{sys.executable}" "{check_script}" "{counter_path}"'
                }
            }
        },
    )
    init_git_repo(project_root)

    prompts = install_stateful_prompt_agent(
        monkeypatch,
        lambda _prompt_count: _mark_feature_done(feature_path),
    )
    monkeypatch.setattr(loop_module, "preflight", lambda **_: True)
    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 2
    feedback = parse_feedback_envelope_from_prompt(prompts[1], phase="gates")
    assert feedback.kind == "command_failure"
    assert feedback.phase == "gates"
    assert feedback.command == (f'"{sys.executable}" "{check_script}" "{counter_path}"')
    assert token in feedback.message


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

    project_root, feature_path = make_project_root(
        tmp_path,
        feature_data=base_feature(),
        gates_data={
            "gates": {
                "pytest_validate": {
                    "run": f'"{sys.executable}" "{check_script}" "{counter_path}"'
                }
            }
        },
    )
    init_git_repo(project_root)

    prompts = install_stateful_prompt_agent(
        monkeypatch,
        lambda _prompt_count: _mark_feature_done(feature_path),
    )
    monkeypatch.setattr(loop_module, "preflight", lambda **_: True)
    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 2
    feedback = parse_feedback_envelope_from_prompt(prompts[1], phase="gates")
    assert feedback.kind == "command_failure"
    assert feedback.phase == "gates"
    assert feedback.command == (f'"{sys.executable}" "{check_script}" "{counter_path}"')
    assert token in feedback.message


def test_gate_failure_feedback_replaces_previous_feedback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_token = "FIRST_GATE_FAILURE_TOKEN"
    second_token = "SECOND_GATE_FAILURE_TOKEN"
    first_counter_path = tmp_path / ".first-check-attempt"
    second_counter_path = tmp_path / ".second-check-attempt"
    first_check_script = tmp_path.parent / f"{tmp_path.name}-check-fail-once-first.py"
    first_check_script.write_text(
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
                "print('ok')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    second_check_script = tmp_path.parent / f"{tmp_path.name}-check-fail-once-second.py"
    second_check_script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "counter = Path(sys.argv[1])",
                "count = int(counter.read_text(encoding='utf-8')) if counter.exists() else 0",
                "count += 1",
                "counter.write_text(str(count), encoding='utf-8')",
                "if count == 1:",
                f"    print({second_token!r})",
                "    raise SystemExit(1)",
                "print('ok')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    project_root, feature_path = make_project_root(
        tmp_path,
        feature_data=base_feature(),
        gates_data={
            "gates": {
                "spec_validate": {
                    "run": f'"{sys.executable}" "{first_check_script}" "{first_counter_path}"'
                }
            }
        },
    )
    init_git_repo(project_root)

    real_run = subprocess.run
    prompts: list[str] = []

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if isinstance(command, list) and command[:3] == ["opencode", "run", "--agent"]:
            prompt = command[4]
            prompts.append(prompt)
            if len(prompts) == 2:
                write_yaml(
                    project_root / "harness" / "checks.yaml",
                    {
                        "contract_version": "1.0",
                        "defaults": {"when": {"phase": "iteration_end"}},
                        "checks": {
                            "spec_validate": {
                                "type": "command",
                                "command": (
                                    f'"{sys.executable}" "{second_check_script}" '
                                    f'"{second_counter_path}"'
                                ),
                            }
                        },
                    },
                )
            if len(prompts) >= 3:
                feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
                feature["status"] = "done"
                feature_path.write_text(
                    yaml.safe_dump(feature, sort_keys=False), encoding="utf-8"
                )
            return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")
        check = bool(kwargs.pop("check", False))
        return real_run(command, check=check, **kwargs)

    patch_run_agent_with_fake(monkeypatch, fake_subprocess_run)
    monkeypatch.setattr(loop_module, "preflight", lambda **_: True)
    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 3
    first_feedback = parse_feedback_envelope_from_prompt(prompts[1], phase="gates")
    second_feedback = parse_feedback_envelope_from_prompt(prompts[2], phase="gates")
    assert first_feedback.kind == "command_failure"
    assert first_feedback.phase == "gates"
    assert first_feedback.command == (
        f'"{sys.executable}" "{first_check_script}" "{first_counter_path}"'
    )
    assert first_token in first_feedback.message
    assert second_feedback.kind == "command_failure"
    assert second_feedback.phase == "gates"
    assert second_feedback.command == (
        f'"{sys.executable}" "{second_check_script}" "{second_counter_path}"'
    )
    assert second_token in second_feedback.message
    assert first_token not in second_feedback.message
    assert second_token in second_feedback.message


def test_gate_failure_feedback_replaces_previous_output_for_same_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_token = "FIRST_GATE_FAILURE_TOKEN"
    second_token = "SECOND_GATE_FAILURE_TOKEN"
    counter_path = tmp_path / ".check-attempt"
    check_script = tmp_path.parent / f"{tmp_path.name}-check-fail-once-twice.py"
    command = f'"{sys.executable}" "{check_script}" "{counter_path}"'
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

    project_root, feature_path = make_project_root(
        tmp_path,
        feature_data=base_feature(),
        gates_data={
            "gates": {
                "spec_validate": {
                    "run": command
                }
            }
        },
    )
    init_git_repo(project_root)

    real_run = subprocess.run
    prompts: list[str] = []

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if isinstance(command, list) and command[:3] == ["opencode", "run", "--agent"]:
            prompt = command[4]
            prompts.append(prompt)
            if len(prompts) >= 3:
                feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
                feature["status"] = "done"
                feature_path.write_text(
                    yaml.safe_dump(feature, sort_keys=False), encoding="utf-8"
                )
            return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")
        check = bool(kwargs.pop("check", False))
        return real_run(command, check=check, **kwargs)

    patch_run_agent_with_fake(monkeypatch, fake_subprocess_run)
    monkeypatch.setattr(loop_module, "preflight", lambda **_: True)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 3

    first_feedback = parse_feedback_envelope_from_prompt(prompts[1], phase="gates")
    second_feedback = parse_feedback_envelope_from_prompt(prompts[2], phase="gates")

    assert first_feedback.kind == "command_failure"
    assert first_feedback.phase == "gates"
    assert first_feedback.command == command
    assert first_feedback.message is not None
    assert first_token in first_feedback.message
    assert second_feedback.kind == "command_failure"
    assert second_feedback.phase == "gates"
    assert second_feedback.command == command
    assert second_feedback.message is not None
    assert second_token in second_feedback.message
    assert first_token not in second_feedback.message
    assert second_token in second_feedback.message


def test_gate_failure_feedback_is_truncated_before_prompt_injection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter_path = tmp_path / ".check-attempt"
    check_script = tmp_path.parent / f"{tmp_path.name}-check-large-feedback-fail-once.py"
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

    project_root, feature_path = make_project_root(
        tmp_path,
        feature_data=base_feature(),
        gates_data={
            "gates": {
                "spec_validate": {
                    "run": f'"{sys.executable}" "{check_script}" "{counter_path}"'
                }
            }
        },
    )
    init_git_repo(project_root)

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
        check = bool(kwargs.pop("check", False))
        return real_run(command, check=check, **kwargs)

    patch_run_agent_with_fake(monkeypatch, fake_subprocess_run)
    monkeypatch.setattr(loop_module, "preflight", lambda **_: True)

    code = run_loop(
        project_root=project_root,
        feature_paths=[str(feature_path)],
        dry_run=False,
        max_iterations=6,
    )

    assert code == 0
    assert len(prompts) >= 2
    assert "BEGIN_GATE_FEEDBACK" in prompts[1]
    assert "END_GATE_FEEDBACK" in prompts[1]
    assert "...[truncated]" not in prompts[1]
    assert "spec_validate" in prompts[1]
