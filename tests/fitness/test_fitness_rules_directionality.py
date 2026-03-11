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
        / "fitness_functions"
        / "rules"
        / "check_dependency_directionality.py"
    )


def _write_module(project_root: Path, module_path: str, body: str) -> None:
    path = project_root / "src" / "engineeringagent" / module_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _write_directionality_fixture(project_root: Path) -> None:
    _write_module(project_root, "loop.py", "")
    _write_module(project_root, "domain/__init__.py", "")
    _write_module(project_root, "presentation/cli/__init__.py", "")
    _write_module(
        project_root,
        "checks/validate/validator.py",
        "from engineeringagent.specs import FeatureSpec\n",
    )
    _write_module(project_root, "specs.py", "")


def _repo_policy_rules(repo_root: Path) -> list[dict[str, object]]:
    payload = yaml.safe_load(
        (
            repo_root
            / "harness"
            / "fitness_functions"
            / "policies"
            / "dependency_directionality.yaml"
        ).read_text(encoding="utf-8")
    )
    rules = payload.get("rules")
    assert isinstance(rules, list)
    return rules


def _policy_module_target_path(repo_root: Path, module_name: str) -> Path:
    source_root = repo_root / "src" / "engineeringagent"
    _, _, suffix = module_name.partition("engineeringagent.")
    relative_path = Path(*suffix.split(".")) if suffix else Path()
    package_path = source_root / relative_path / "__init__.py"
    if package_path.is_file():
        return Path(*suffix.split(".")) / "__init__.py"
    return Path(*suffix.split(".")).with_suffix(".py")


def _write_repo_policy_fixture(project_root: Path, repo_root: Path) -> None:
    _write_directionality_fixture(project_root)
    for rule in _repo_policy_rules(repo_root):
        module_name = rule.get("module")
        assert isinstance(module_name, str)
        _write_module(
            project_root,
            str(_policy_module_target_path(repo_root, module_name)),
            "",
        )


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
    """Honor the checked-in policy for current layered CLI, contracts, and application boundaries."""
    _write_repo_policy_fixture(tmp_path, repo_root)
    _write_module(
        tmp_path,
        "specs.py",
        "import engineeringagent.checks.contracts\n",
    )
    _write_module(tmp_path, "presentation/cli/checks.py", "")
    _write_module(
        tmp_path,
        "presentation/cli/app.py",
        "import engineeringagent.loop_runtime.selection\n",
    )
    _write_module(
        tmp_path,
        "presentation/cli/typer.py",
        "import engineeringagent.checks.reviewers.engine\n",
    )
    _write_module(
        tmp_path,
        "checks/contracts.py",
        "import engineeringagent.presentation.cli.app\n",
    )
    _write_module(
        tmp_path,
        "application/checks_service.py",
        "import engineeringagent.checks\n",
    )
    _write_module(
        tmp_path,
        "application/guidance_service.py",
        "import engineeringagent.loop_runtime.selection\n",
    )
    _write_module(
        tmp_path,
        "presentation/cli/approach.py",
        "from engineeringagent.adapters.guidance import PackagedGuidanceTopicRepository\n",
    )
    _write_module(
        tmp_path,
        "application/init_workspace_service.py",
        "import engineeringagent.adapters.progress.paths\n",
    )
    _write_module(
        tmp_path,
        "application/prompt_builder.py",
        "import engineeringagent.adapters.progress.paths\n"
        "import engineeringagent.presentation.presenters.prompt_feedback\n"
        "import engineeringagent.presentation.presenters.terminal\n"
        "import engineeringagent.specs\n",
    )
    _write_module(
        tmp_path,
        "application/run_loop_service.py",
        "import engineeringagent.loop_runtime.selection\n",
    )
    _write_module(
        tmp_path,
        "application/validation_service.py",
        "import engineeringagent.checks\n",
    )
    _write_module(
        tmp_path,
        "application/workspace_recovery_service.py",
        "import engineeringagent.bootstrap.app_factory\n",
    )
    _write_module(
        tmp_path,
        "ports/agent_runner.py",
        "import engineeringagent.checks.reviewers.engine\n",
    )
    _write_module(
        tmp_path,
        "ports/checks_runner.py",
        "import engineeringagent.checks\n",
    )
    _write_module(
        tmp_path,
        "ports/version_control.py",
        "import engineeringagent.presentation.cli.app\n",
    )
    _write_module(
        tmp_path,
        "presentation/cli/validate.py",
        "from engineeringagent.application import ValidationService\n",
    )
    _write_module(
        tmp_path,
        "presentation/cli/checks.py",
        "from engineeringagent.application import ChecksService\n",
    )
    _write_module(
        tmp_path,
        "presentation/cli/run.py",
        "import engineeringagent.loop\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.dep-directionality"
    assert payload["status"] == "fail"
    assert payload["violations"] == [
        (
            "engineeringagent.application.checks_service imports blocked dependency "
            "engineeringagent.checks"
        ),
        (
            "engineeringagent.application.guidance_service imports blocked dependency "
            "engineeringagent.loop_runtime.selection"
        ),
        (
            "engineeringagent.application.init_workspace_service imports blocked "
            "dependency engineeringagent.adapters.progress.paths"
        ),
        (
            "engineeringagent.application.prompt_builder imports blocked dependency "
            "engineeringagent.adapters.progress.paths"
        ),
        (
            "engineeringagent.application.prompt_builder imports blocked dependency "
            "engineeringagent.presentation.presenters.prompt_feedback"
        ),
        (
            "engineeringagent.application.prompt_builder imports blocked dependency "
            "engineeringagent.presentation.presenters.terminal"
        ),
        (
            "engineeringagent.application.prompt_builder imports blocked dependency "
            "engineeringagent.specs"
        ),
        (
            "engineeringagent.application.run_loop_service imports blocked dependency "
            "engineeringagent.loop_runtime.selection"
        ),
        (
            "engineeringagent.application.validation_service imports blocked dependency "
            "engineeringagent.checks"
        ),
        (
            "engineeringagent.application.workspace_recovery_service imports blocked "
            "dependency engineeringagent.bootstrap.app_factory"
        ),
        (
            "engineeringagent.checks.contracts imports blocked dependency "
            "engineeringagent.presentation.cli.app"
        ),
        (
            "engineeringagent.ports.agent_runner imports blocked dependency "
            "engineeringagent.checks.reviewers.engine"
        ),
        (
            "engineeringagent.ports.checks_runner imports blocked dependency "
            "engineeringagent.checks"
        ),
        (
            "engineeringagent.ports.version_control imports blocked dependency "
            "engineeringagent.presentation.cli.app"
        ),
        (
            "engineeringagent.presentation.cli.app imports blocked dependency "
            "engineeringagent.loop_runtime.selection"
        ),
        (
            "engineeringagent.presentation.cli.approach imports blocked dependency "
            "engineeringagent.adapters.guidance"
        ),
        (
            "engineeringagent.presentation.cli.approach imports blocked dependency "
            "engineeringagent.adapters.guidance.PackagedGuidanceTopicRepository"
        ),
        (
            "engineeringagent.presentation.cli.run imports blocked dependency "
            "engineeringagent.loop"
        ),
        (
            "engineeringagent.presentation.cli.typer imports blocked dependency "
            "engineeringagent.checks.reviewers.engine"
        ),
        (
            "engineeringagent.specs imports blocked dependency "
            "engineeringagent.checks.contracts"
        ),
    ]


def test_repo_directionality_policy_covers_all_top_level_application_and_port_modules(
    repo_root: Path,
) -> None:
    """Every top-level application and ports module should carry a directionality rule."""

    modules_with_rules = {
        cast(str, rule["module"]) for rule in _repo_policy_rules(repo_root)
    }
    source_root = repo_root / "src" / "engineeringagent"
    expected_modules = {
        f"engineeringagent.{package}.{path.stem}"
        for package in ("application", "ports")
        for path in (source_root / package).glob("*.py")
        if path.name != "__init__.py"
    }

    assert sorted(expected_modules - modules_with_rules) == []


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
        "import engineeringagent.presentation.cli\n",
    )
    _write_module(tmp_path, "presentation/cli/__init__.py", "")
    policy_file = _write_policy(
        tmp_path,
        [
            {
                "module": "engineeringagent.domain",
                "blocked_dependencies": ["engineeringagent.presentation.cli"],
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
        "engineeringagent.domain imports blocked dependency engineeringagent.presentation.cli"
    ]


def test_directionality_rule_supports_package_modules_from_policy(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Resolve package modules declared in policy to their __init__ file."""
    _write_module(
        tmp_path,
        "domain/__init__.py",
        "import engineeringagent.presentation.cli\n",
    )
    _write_module(tmp_path, "presentation/cli/__init__.py", "")
    policy_file = _write_policy(
        tmp_path,
        [
            {
                "module": "engineeringagent.domain",
                "blocked_dependencies": ["engineeringagent.presentation.cli"],
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
        "engineeringagent.domain imports blocked dependency engineeringagent.presentation.cli"
    ]


def test_directionality_rule_uses_repo_policy_for_domain_boundary(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Honor the checked-in policy that keeps domain code inward-only."""
    _write_repo_policy_fixture(tmp_path, repo_root)
    _write_module(
        tmp_path,
        "domain/guidance/__init__.py",
        "import engineeringagent.ports\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.dep-directionality"
    assert payload["status"] == "fail"
    assert payload["violations"] == [
        "engineeringagent.domain.guidance imports blocked dependency engineeringagent.ports"
    ]


def test_directionality_rule_allows_cli_modules_to_import_application_services(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow presentation modules to depend inward on application services."""
    _write_repo_policy_fixture(tmp_path, repo_root)
    _write_module(
        tmp_path,
        "presentation/cli/checks.py",
        "from engineeringagent.application import ChecksService\n",
    )
    _write_module(
        tmp_path,
        "presentation/cli/validate.py",
        "from engineeringagent.application import ValidationService\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.dep-directionality"
    assert payload["status"] == "pass"
    assert payload["violations"] == []


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
                "blocked_dependencies": ["engineeringagent.presentation.cli"],
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
