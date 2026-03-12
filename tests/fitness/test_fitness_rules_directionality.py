from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
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
    _write_module(project_root, "application/__init__.py", "")
    _write_module(project_root, "domain/__init__.py", "")
    _write_module(project_root, "ports/__init__.py", "")
    _write_module(project_root, "presentation/cli/__init__.py", "")


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
        module_names = cast(list[str] | None, rule.get("sources"))
        if module_names is None:
            source_layers = cast(list[str] | None, rule.get("source_layers"))
            assert isinstance(source_layers, list)
            module_names = [
                {
                    "application": "engineeringagent.application",
                    "domain": "engineeringagent.domain",
                    "ports": "engineeringagent.ports",
                    "presentation_cli": "engineeringagent.presentation.cli",
                }[layer_id]
                for layer_id in source_layers
            ]
        for module_name in module_names:
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
    """Fail when a policy source imports one of its blocked dependencies."""
    _write_directionality_fixture(tmp_path)
    _write_module(
        tmp_path,
        "application/service.py",
        "import engineeringagent.adapters.progress.paths\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = payload["violations"]

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert isinstance(violations, list)
    assert any(
        "engineeringagent.application.service imports blocked dependency "
        "engineeringagent.adapters.progress.paths"
        in violation
        for violation in violations
    )


def test_directionality_rule_reports_blocked_loop_runtime_import(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when a custom policy guards a specific module path."""
    _write_module(
        tmp_path,
        "adapters/quality/validation/validator.py",
        "import engineeringagent.domain.specification.selection\n",
    )
    policy_file = _write_policy(
        tmp_path,
        [
            {
                "sources": ["engineeringagent.adapters.quality.validation.validator"],
                "blocked_dependencies": [
                    "engineeringagent.domain.specification.selection"
                ],
            }
        ],
    )

    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=policy_file,
    )
    violations = payload["violations"]

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert isinstance(violations, list)
    assert any(
        (
            "engineeringagent.adapters.quality.validation.validator imports blocked dependency "
            "engineeringagent.domain.specification.selection"
        )
        in violation
        for violation in violations
    )


def test_directionality_rule_applies_package_level_application_boundary(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Package rules should scan nested modules instead of requiring explicit entries."""
    _write_repo_policy_fixture(tmp_path, repo_root)
    _write_module(
        tmp_path,
        "application/feature_iteration/service.py",
        "import engineeringagent.adapters.progress.paths\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert (
        "engineeringagent.application.feature_iteration.service imports blocked dependency "
        "engineeringagent.adapters.progress.paths"
    ) in cast(list[str], payload["violations"])


def test_directionality_rule_uses_repo_policy_for_layer_and_cli_boundaries(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Honor the checked-in layer boundaries from the architecture policy."""
    _write_repo_policy_fixture(tmp_path, repo_root)
    _write_module(
        tmp_path,
        "presentation/cli/guidance.py",
        "from engineeringagent.adapters.documents import FilesystemGuidanceTopicRepository\n",
    )
    _write_module(
        tmp_path,
        "ports/version_control.py",
        "import engineeringagent.presentation.cli.app\n",
    )
    _write_module(
        tmp_path,
        "domain/specification/feature_specification.py",
        "import engineeringagent.ports.version_control\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.dep-directionality"
    assert payload["status"] == "fail"
    assert sorted(cast(list[str], payload["violations"])) == sorted(
        [
            (
                "engineeringagent.domain.specification.feature_specification imports blocked dependency "
                "engineeringagent.ports.version_control"
            ),
            (
                "engineeringagent.ports.version_control imports blocked dependency "
                "engineeringagent.presentation.cli.app"
            ),
            (
                "engineeringagent.presentation.cli.guidance imports blocked dependency "
                "engineeringagent.adapters.documents"
            ),
            (
                "engineeringagent.presentation.cli.guidance imports blocked dependency "
                "engineeringagent.adapters.documents.FilesystemGuidanceTopicRepository"
            ),
        ]
    )


def test_repo_directionality_policy_stays_layer_oriented(repo_root: Path) -> None:
    """The checked-in policy should stay focused on architecture layers."""
    rules = _repo_policy_rules(repo_root)
    source_counts = [len(cast(list[object], rule["source_layers"])) for rule in rules]
    blocked_layers = [cast(list[object], rule["blocked_layers"]) for rule in rules]

    assert len(rules) == 4
    assert source_counts == [1, 1, 1, 1]
    assert all("sources" not in rule for rule in rules)
    assert all("blocked_dependencies" not in rule for rule in rules)
    assert blocked_layers == [
        ["adapters", "bootstrap", "presentation"],
        ["adapters", "application", "bootstrap", "presentation_cli"],
        ["adapters", "application", "bootstrap", "ports", "presentation"],
        ["adapters"],
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
                "sources": ["engineeringagent.specs"],
                "blocked_dependencies": ["engineeringagent.checks.contracts"],
            },
            {
                "sources": ["engineeringagent.checks.contracts"],
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
                "sources": ["engineeringagent.domain"],
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
    """Resolve package rules to nested modules under the package root."""
    _write_module(tmp_path, "domain/__init__.py", "")
    _write_module(
        tmp_path,
        "domain/guidance/topic.py",
        "import engineeringagent.presentation.cli\n",
    )
    _write_module(tmp_path, "presentation/cli/__init__.py", "")
    policy_file = _write_policy(
        tmp_path,
        [
            {
                "sources": ["engineeringagent.domain"],
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
        "engineeringagent.domain.guidance.topic imports blocked dependency engineeringagent.presentation.cli"
    ]


def test_directionality_rule_supports_layer_alias_policies(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow canonical layer ids in policy files instead of full package paths."""
    _write_module(tmp_path, "domain/__init__.py", "")
    _write_module(
        tmp_path,
        "domain/specification/feature_specification.py",
        "import engineeringagent.presentation.presenters.terminal\n",
    )
    _write_module(tmp_path, "presentation/presenters/terminal.py", "")
    policy_file = _write_policy(
        tmp_path,
        [{"source_layers": ["domain"], "blocked_layers": ["presentation"]}],
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
            "engineeringagent.domain.specification.feature_specification imports "
            "blocked dependency engineeringagent.presentation.presenters.terminal"
        )
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
    """Return an error result when the policy duplicates one protected source."""
    _write_module(tmp_path, "domain.py", "")
    duplicate_policy = _write_policy(
        tmp_path,
        [
            {
                "sources": ["engineeringagent.domain"],
                "blocked_dependencies": ["engineeringagent.presentation.cli"],
            },
            {
                "sources": ["engineeringagent.domain"],
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


def test_directionality_rule_errors_when_policy_uses_unknown_layer_id(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Return an error result when a policy references an unknown layer alias."""
    invalid_policy = _write_policy(
        tmp_path,
        [{"source_layers": ["domain_model"], "blocked_layers": ["presentation"]}],
    )

    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=invalid_policy,
    )

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.dep-directionality"
    assert payload["status"] == "error"
    assert payload["violations"] == []
    assert (
        _summary(payload)
        == "Dependency directionality scan failed: unknown source layer id "
        "'domain_model'; expected one of: adapters, application, bootstrap, "
        "domain, ports, presentation, presentation_cli"
    )
