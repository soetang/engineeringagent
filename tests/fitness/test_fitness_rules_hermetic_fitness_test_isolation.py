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
        / "check_hermetic_fitness_test_isolation.py"
    )


def _policy_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness_functions"
        / "policies"
        / "hermetic_fitness_test_isolation.yaml"
    )


def _write_policy(
    project_root: Path,
    *,
    integration_test_modules: list[str],
) -> Path:
    config_file = project_root / "hermetic_fitness_test_isolation.yaml"
    config_file.write_text(
        "integration_test_modules:\n"
        + "".join(f"  - {module}\n" for module in integration_test_modules),
        encoding="utf-8",
    )
    return config_file


def _run_checker(
    project_root: Path,
    *,
    checker_path: Path,
    config_file: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    proc = subprocess.run(
        [sys.executable, str(checker_path), "--config-file", str(config_file)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    return proc, payload


def _violations(result: dict[str, object]) -> list[str]:
    return cast(list[str], result["violations"])


def _write_file(project_root: Path, relative_path: str, body: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_rule_flags_repo_root_passed_to_run_checker(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "tests/fitness/test_direct_violation.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "",
                "def _run_checker(project_root: Path, *, checker_path: Path) -> None:",
                "    raise NotImplementedError",
                "",
                "def _script_path(repo_root: Path) -> Path:",
                '    return repo_root / "harness" / "fitness_functions" / "check_rule.py"',
                "",
                "def test_violates(repo_root: Path) -> None:",
                "    _run_checker(repo_root, checker_path=_script_path(repo_root))",
                "",
            ]
        ),
    )

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["rule_id"] == "architecture.hermetic-fitness-test-isolation"
    assert result["status"] == "fail"
    assert _violations(result) == [
        "tests/fitness/test_direct_violation.py:12 fitness tests must not use "
        "repo_root as checker scan target (_run_checker project_root)"
    ]


def test_rule_flags_repo_root_alias_passed_to_execute_rule_definition(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "tests/fitness/test_alias_violation.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "",
                "def execute_rule_definition(definition: object, *, project_root: Path) -> None:",
                "    raise NotImplementedError",
                "",
                "def test_violates(repo_root: Path) -> None:",
                '    definition = {"rule_id": "demo.rule"}',
                '    scan_root = repo_root / "src"',
                "    execute_rule_definition(definition, project_root=scan_root)",
                "",
            ]
        ),
    )

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert _violations(result) == [
        "tests/fitness/test_alias_violation.py:11 fitness tests must not use "
        "repo_root as checker scan target (execute_rule_definition project_root)"
    ]


def test_rule_flags_repo_root_passed_to_aliased_subprocess_cwd(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "tests/fitness/test_subprocess_alias_violation.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "import subprocess as sp",
                "",
                "def test_violates(repo_root) -> None:",
                '    sp.run(["git", "status"], cwd=repo_root, check=False)',
                "",
            ]
        ),
    )

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert _violations(result) == [
        "tests/fitness/test_subprocess_alias_violation.py:6 fitness tests must not use "
        "repo_root as checker scan target (subprocess cwd)"
    ]


def test_rule_allows_repo_root_for_checker_script_lookup_only(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "tests/fitness/test_allowed_script_lookup.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "",
                "def _run_checker(project_root: Path, *, checker_path: Path) -> None:",
                "    raise NotImplementedError",
                "",
                "def _script_path(repo_root: Path) -> Path:",
                '    return repo_root / "harness" / "fitness_functions" / "check_rule.py"',
                "",
                "def test_allowed(repo_root: Path, tmp_path: Path) -> None:",
                "    _run_checker(tmp_path, checker_path=_script_path(repo_root))",
                "",
            ]
        ),
    )

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert _violations(result) == []


def test_default_policy_has_no_real_repo_integration_allowlist(repo_root: Path) -> None:
    policy = yaml.safe_load(_policy_path(repo_root).read_text(encoding="utf-8"))

    assert isinstance(policy, dict)
    assert policy.get("integration_test_modules") == []


def test_rule_flags_local_helper_forwarding_repo_root_to_run_checker(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "tests/fitness/test_forwarding_helper_violation.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "",
                "def _run_checker(project_root: Path, *, checker_path: Path) -> None:",
                "    raise NotImplementedError",
                "",
                "def _script_path(repo_root: Path) -> Path:",
                '    return repo_root / "harness" / "fitness_functions" / "check_rule.py"',
                "",
                "def _invoke_checker(project_root: Path, *, checker_path: Path) -> None:",
                "    _run_checker(project_root, checker_path=checker_path)",
                "",
                "def test_violates(repo_root: Path) -> None:",
                "    _invoke_checker(repo_root, checker_path=_script_path(repo_root))",
                "",
            ]
        ),
    )

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert _violations(result) == [
        "tests/fitness/test_forwarding_helper_violation.py:15 fitness tests must not use "
        "repo_root as checker scan target (_run_checker project_root)"
    ]


def test_rule_flags_kwargs_forwarding_repo_root_to_execute_rule_definition(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "tests/fitness/test_kwargs_forwarding_violation.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "",
                "def execute_rule_definition(definition: object, *, project_root: Path) -> None:",
                "    raise NotImplementedError",
                "",
                "def _invoke(definition: object, **kwargs: Path) -> None:",
                "    execute_rule_definition(definition, **kwargs)",
                "",
                "def test_violates(repo_root: Path) -> None:",
                '    definition = {"rule_id": "demo.rule"}',
                '    kwargs = {"project_root": repo_root / "src"}',
                "    _invoke(definition, **kwargs)",
                "",
            ]
        ),
    )

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert _violations(result) == [
        "tests/fitness/test_kwargs_forwarding_violation.py:14 fitness tests must not use "
        "repo_root as checker scan target (execute_rule_definition project_root)"
    ]


def test_rule_flags_local_helper_deriving_repo_root_before_named_sink(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "tests/fitness/test_wrapper_derived_violation.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "",
                "def execute_rule_definition(definition: object, *, project_root: Path) -> None:",
                "    raise NotImplementedError",
                "",
                "def _invoke(project_root: Path) -> None:",
                '    definition = {"rule_id": "demo.rule"}',
                '    scan_root = Path(project_root) / "src"',
                "    execute_rule_definition(definition, project_root=scan_root)",
                "",
                "def test_violates(repo_root: Path) -> None:",
                "    _invoke(repo_root)",
                "",
            ]
        ),
    )

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert _violations(result) == [
        "tests/fitness/test_wrapper_derived_violation.py:14 fitness tests must not use "
        "repo_root as checker scan target (execute_rule_definition project_root)"
    ]


def test_rule_flags_nested_local_helper_deriving_repo_root_before_named_sink(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "tests/fitness/test_nested_wrapper_derived_violation.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "",
                "def execute_rule_definition(definition: object, *, project_root: Path) -> None:",
                "    raise NotImplementedError",
                "",
                "def test_violates(repo_root: Path) -> None:",
                "    def _invoke(project_root: Path) -> None:",
                '        definition = {"rule_id": "demo.rule"}',
                '        scan_root = Path(project_root) / "src"',
                "        execute_rule_definition(definition, project_root=scan_root)",
                "",
                "    _invoke(repo_root)",
                "",
            ]
        ),
    )

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert _violations(result) == [
        "tests/fitness/test_nested_wrapper_derived_violation.py:14 fitness tests must not use "
        "repo_root as checker scan target (execute_rule_definition project_root)"
    ]


def test_rule_flags_class_method_forwarding_repo_root_to_named_sink(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "tests/fitness/test_class_method_forwarding_violation.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "",
                "def execute_rule_definition(definition: object, *, project_root: Path) -> None:",
                "    raise NotImplementedError",
                "",
                "class TestHermeticFitnessIsolation:",
                "    def _invoke(self, project_root: Path) -> None:",
                '        definition = {"rule_id": "demo.rule"}',
                '        scan_root = Path(project_root) / "src"',
                "        execute_rule_definition(definition, project_root=scan_root)",
                "",
                "    def test_violates(self, repo_root: Path) -> None:",
                "        self._invoke(repo_root)",
                "",
            ]
        ),
    )

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert _violations(result) == [
        "tests/fitness/test_class_method_forwarding_violation.py:15 fitness tests must not use "
        "repo_root as checker scan target (execute_rule_definition project_root)"
    ]


def test_rule_skips_allowlisted_real_repo_integration_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "tests/fitness/test_harness_real_repo_integration.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "import subprocess",
                "",
                "def test_allowed(repo_root) -> None:",
                '    subprocess.run(["git", "status"], cwd=repo_root, check=False)',
                "",
            ]
        ),
    )

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_write_policy(
            tmp_path,
            integration_test_modules=[
                "tests/fitness/test_harness_real_repo_integration.py"
            ],
        ),
    )

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert _violations(result) == []


def test_rule_flags_class_kwargs_forwarding_repo_root_to_named_sink(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "tests/fitness/test_class_kwargs_forwarding_violation.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "",
                "def execute_rule_definition(definition: object, *, project_root: Path) -> None:",
                "    raise NotImplementedError",
                "",
                "class TestHermeticFitnessIsolation:",
                "    def _invoke(self, definition: object, **kwargs: Path) -> None:",
                "        execute_rule_definition(definition, **kwargs)",
                "",
                "    def test_violates(self, repo_root: Path) -> None:",
                '        definition = {"rule_id": "demo.rule"}',
                '        kwargs = {"project_root": repo_root / "src"}',
                "        self._invoke(definition, **kwargs)",
                "",
            ]
        ),
    )

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert _violations(result) == [
        "tests/fitness/test_class_kwargs_forwarding_violation.py:15 fitness tests must not use "
        "repo_root as checker scan target (execute_rule_definition project_root)"
    ]
