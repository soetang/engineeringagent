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
        / "check_dependency_directionality.py"
    )


def _write_module(project_root: Path, module_path: str, body: str) -> None:
    path = project_root / "src" / "engineeringagent" / module_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _write_directionality_fixture(project_root: Path) -> None:
    _write_module(project_root, "cli.py", "")
    _write_module(project_root, "loop.py", "")
    _write_module(
        project_root,
        "checks/validate/validator.py",
        "from engineeringagent.specs import FeatureSpec\n",
    )
    _write_module(project_root, "specs.py", "")


def _write_policy(project_root: Path, rules: list[dict[str, object]]) -> Path:
    policy_path = project_root / "dependency-directionality-policy.yaml"
    policy_path.write_text(
        yaml.safe_dump({"rules": rules}, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return policy_path


def _run_checker(
    project_root: Path,
    *,
    checker_path: Path,
    config_file: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    command = [sys.executable, str(checker_path)]
    if config_file is not None:
        command.extend(["--config-file", str(config_file)])

    proc = subprocess.run(
        command,
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    return proc, payload


def _summary(payload: dict[str, object]) -> str:
    return cast(str, payload["summary"])


def test_directionality_checker_emits_expected_rule_id(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Emit the stable rule id from the harness command adapter."""
    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.dep-directionality"


def test_directionality_rule_reports_blocked_import(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when a protected module imports a blocked dependency."""
    _write_directionality_fixture(tmp_path)
    _write_module(tmp_path, "specs.py", "import engineeringagent.loop\n")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = payload["violations"]

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert isinstance(violations, list)
    assert any(
        "engineeringagent.specs imports blocked dependency engineeringagent.loop"
        in violation
        for violation in violations
    )


def test_directionality_rule_reports_blocked_loop_runtime_import(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when protected modules import loop_runtime internals directly."""
    _write_directionality_fixture(tmp_path)
    _write_module(
        tmp_path,
        "checks/validate/validator.py",
        "import engineeringagent.loop_runtime.selection\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = payload["violations"]

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert isinstance(violations, list)
    assert any(
        (
            "engineeringagent.checks.validate.validator imports blocked dependency "
            "engineeringagent.loop_runtime.selection"
        )
        in violation
        for violation in violations
    )


def test_directionality_rule_uses_repo_policy_for_cli_and_contract_boundaries(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Honor the checked-in policy for CLI, contracts, and application boundaries."""
    _write_directionality_fixture(tmp_path)
    _write_module(
        tmp_path,
        "specs.py",
        "import engineeringagent.checks.contracts\n",
    )
    _write_module(tmp_path, "cli/checks.py", "")
    _write_module(
        tmp_path,
        "cli/app.py",
        "import engineeringagent.loop_runtime.selection\n",
    )
    _write_module(
        tmp_path,
        "cli/typer.py",
        "import engineeringagent.checks.reviewers.engine\n",
    )
    _write_module(
        tmp_path,
        "checks/contracts.py",
        "import engineeringagent.cli.app\n",
    )
    _write_module(
        tmp_path,
        "application/checks_service.py",
        "import engineeringagent.adapters.prompts\n",
    )
    _write_module(
        tmp_path,
        "application/implementation_prompt.py",
        "import engineeringagent.progress.paths\n",
    )
    _write_module(
        tmp_path,
        "application/guidance_service.py",
        "import engineeringagent.loop_runtime.selection\n",
    )
    _write_module(
        tmp_path,
        "cli/approach.py",
        "from engineeringagent.adapters.guidance import PackagedGuidanceTopicRepository\n",
    )
    _write_module(
        tmp_path,
        "application/prompt_builder.py",
        "import engineeringagent.progress.paths\n",
    )
    _write_module(
        tmp_path,
        "cli/validate.py",
        "from engineeringagent.application import DefaultValidationService\n",
    )
    _write_module(
        tmp_path,
        "cli/checks.py",
        "from engineeringagent.application import DefaultChecksService\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.dep-directionality"
    assert payload["status"] == "fail"
    assert payload["violations"] == [
        (
            "engineeringagent.application.checks_service imports blocked dependency "
            "engineeringagent.adapters.prompts"
        ),
        (
            "engineeringagent.application.guidance_service imports blocked dependency "
            "engineeringagent.loop_runtime.selection"
        ),
        (
            "engineeringagent.application.implementation_prompt imports blocked dependency "
            "engineeringagent.progress.paths"
        ),
        (
            "engineeringagent.application.prompt_builder imports blocked dependency "
            "engineeringagent.progress.paths"
        ),
        (
            "engineeringagent.checks.contracts imports blocked dependency "
            "engineeringagent.cli.app"
        ),
        (
            "engineeringagent.cli.app imports blocked dependency "
            "engineeringagent.loop_runtime.selection"
        ),
        (
            "engineeringagent.cli.approach imports blocked dependency "
            "engineeringagent.adapters.guidance"
        ),
        (
            "engineeringagent.cli.approach imports blocked dependency "
            "engineeringagent.adapters.guidance.PackagedGuidanceTopicRepository"
        ),
        (
            "engineeringagent.cli.checks imports blocked dependency "
            "engineeringagent.application.DefaultChecksService"
        ),
        (
            "engineeringagent.cli.typer imports blocked dependency "
            "engineeringagent.checks.reviewers.engine"
        ),
        (
            "engineeringagent.cli.validate imports blocked dependency "
            "engineeringagent.application.DefaultValidationService"
        ),
        (
            "engineeringagent.specs imports blocked dependency "
            "engineeringagent.checks.contracts"
        ),
    ]


def test_directionality_rule_supports_reverse_direction_specs_contract_boundaries(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Support policies that declare both sides of a forbidden dependency edge."""
    _write_module(
        tmp_path,
        "specs.py",
        "import engineeringagent.checks.contracts\n",
    )
    _write_module(
        tmp_path,
        "checks/contracts.py",
        "import engineeringagent.specs\n",
    )
    policy_file = _write_policy(
        tmp_path,
        [
            {
                "module": "engineeringagent.specs",
                "blocked_dependencies": ["engineeringagent.checks.contracts"],
            },
            {
                "module": "engineeringagent.checks.contracts",
                "blocked_dependencies": ["engineeringagent.specs"],
            },
        ],
    )

    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=policy_file,
    )

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.dep-directionality"
    assert payload["status"] == "fail"
    assert payload["violations"] == [
        (
            "engineeringagent.checks.contracts imports blocked dependency "
            "engineeringagent.specs"
        ),
        (
            "engineeringagent.specs imports blocked dependency "
            "engineeringagent.checks.contracts"
        ),
    ]


def test_directionality_rule_loads_blocked_boundaries_from_policy(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Load arbitrary blocked dependency rules from a supplied policy file."""
    _write_module(
        tmp_path,
        "domain.py",
        "import engineeringagent.cli\n",
    )
    _write_module(tmp_path, "cli.py", "")
    policy_file = _write_policy(
        tmp_path,
        [
            {
                "module": "engineeringagent.domain",
                "blocked_dependencies": ["engineeringagent.cli"],
            }
        ],
    )

    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=policy_file,
    )

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.dep-directionality"
    assert payload["status"] == "fail"
    assert payload["violations"] == [
        "engineeringagent.domain imports blocked dependency engineeringagent.cli"
    ]


def test_directionality_rule_supports_package_modules_from_policy(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Resolve package modules declared in policy to their __init__ file."""
    _write_module(
        tmp_path,
        "domain/__init__.py",
        "import engineeringagent.cli\n",
    )
    _write_module(tmp_path, "cli.py", "")
    policy_file = _write_policy(
        tmp_path,
        [
            {
                "module": "engineeringagent.domain",
                "blocked_dependencies": ["engineeringagent.cli"],
            }
        ],
    )

    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=policy_file,
    )

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.dep-directionality"
    assert payload["status"] == "fail"
    assert payload["violations"] == [
        "engineeringagent.domain imports blocked dependency engineeringagent.cli"
    ]


def test_directionality_rule_errors_when_policy_is_invalid(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Return an error result when the policy payload cannot be parsed."""
    invalid_policy = tmp_path / "invalid-policy.yaml"
    invalid_policy.write_text("rules: bad\n", encoding="utf-8")

    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=invalid_policy,
    )

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.dep-directionality"
    assert payload["status"] == "error"
    assert payload["violations"] == []
    assert _summary(payload).startswith("Dependency directionality scan failed:")


def test_directionality_rule_errors_when_policy_repeats_module_boundary(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Return an error result when the policy duplicates one protected module."""
    _write_module(tmp_path, "domain.py", "")
    duplicate_policy = _write_policy(
        tmp_path,
        [
            {
                "module": "engineeringagent.domain",
                "blocked_dependencies": ["engineeringagent.cli"],
            },
            {
                "module": "engineeringagent.domain",
                "blocked_dependencies": ["engineeringagent.loop"],
            },
        ],
    )

    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=duplicate_policy,
    )

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.dep-directionality"
    assert payload["status"] == "error"
    assert payload["violations"] == []
    assert (
        _summary(payload)
        == "Dependency directionality scan failed: duplicate policy module: "
        "engineeringagent.domain"
    )
