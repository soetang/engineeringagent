"""Tests for the import-boundary fitness script."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_allow_only_allows_resolved_relative_imports(tmp_path: Path) -> None:
    """Allow relative imports when their resolved module stays in the package."""
    write_policy(
        tmp_path,
        [
            rule(
                name="feature-area-boundary",
                targets=["developer.feature_area"],
                mode="allow_only",
                allow=["developer.feature_area"],
            )
        ],
    )
    write_file(
        tmp_path / "src/developer/feature_area/protocols.py",
        "from .models import GatePhase\n",
    )

    result = run_import_rules(tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""


def test_allow_only_rejects_non_allowed_local_import(tmp_path: Path) -> None:
    """Reject local imports outside the allowlist."""
    write_policy(
        tmp_path,
        [
            rule(
                name="feature-area-boundary",
                description="Feature code stays inside its package boundary.",
                targets=["developer.feature_area"],
                mode="allow_only",
                allow=["developer.feature_area"],
            )
        ],
    )
    write_file(
        tmp_path / "src/developer/feature_area/example.py",
        "from developer.ui.models import Screen\n",
    )

    result = run_import_rules(tmp_path)

    assert result.returncode == 1
    assert (
        "src/developer/feature_area/example.py:1 imports developer.ui.models"
        in result.stderr
    )
    assert "rule: feature-area-boundary" in result.stderr
    assert "reason: Feature code stays inside its package boundary." in result.stderr


def test_deny_only_rejects_matching_local_imports(tmp_path: Path) -> None:
    """Reject imports that match a denied prefix."""
    write_policy(
        tmp_path,
        [
            rule(
                name="application-no-presentation",
                targets=["developer.feature_area"],
                mode="deny_only",
                deny=["developer.ui"],
            )
        ],
    )
    write_file(
        tmp_path / "src/developer/feature_area/example.py",
        "from developer.ui.models import Screen\n",
    )

    result = run_import_rules(tmp_path)

    assert result.returncode == 1
    assert (
        "src/developer/feature_area/example.py:1 imports developer.ui.models"
        in result.stderr
    )


def test_deny_except_allows_configured_exception(tmp_path: Path) -> None:
    """Allow a narrow exception to a broad deny rule."""
    write_policy(
        tmp_path,
        [
            rule(
                name="feature-area-boundary",
                targets=["developer.feature_area"],
                mode="deny_except",
                allow=["developer.feature_area", "developer.shared_protocols"],
                deny=["developer"],
            )
        ],
    )
    write_file(
        tmp_path / "src/developer/feature_area/example.py",
        "from developer.shared_protocols.models import Event\n",
    )

    result = run_import_rules(tmp_path)

    assert result.returncode == 0


def test_package_targets_cover_nested_modules_and_init_files(tmp_path: Path) -> None:
    """Apply package targets recursively, including __init__.py modules."""
    write_policy(
        tmp_path,
        [
            rule(
                name="feature-area-boundary",
                targets=["developer.feature_area"],
                mode="deny_only",
                deny=["developer.ui"],
            )
        ],
    )
    write_file(
        tmp_path / "src/developer/feature_area/__init__.py",
        "from developer.ui.models import Screen\n",
    )
    write_file(
        tmp_path / "src/developer/feature_area/nested/example.py",
        "import developer.ui.models\n",
    )

    result = run_import_rules(tmp_path)

    assert result.returncode == 1
    assert (
        "src/developer/feature_area/__init__.py:1 imports developer.ui.models"
        in result.stderr
    )
    assert (
        "src/developer/feature_area/nested/example.py:1 imports developer.ui.models"
        in result.stderr
    )


def test_exact_module_target_wins_over_parent_package_target(tmp_path: Path) -> None:
    """Use the most specific matching rule when parent and child targets overlap."""
    write_policy(
        tmp_path,
        [
            rule(
                name="feature-area-parent",
                targets=["developer.feature_area"],
                mode="deny_only",
                deny=["developer.shared_protocols"],
            ),
            rule(
                name="feature-area-entrypoint",
                targets=["developer.feature_area.entrypoint"],
                mode="allow_only",
                allow=["developer.shared_protocols"],
            ),
        ],
    )
    write_file(
        tmp_path / "src/developer/feature_area/entrypoint.py",
        "from developer.shared_protocols.models import Event\n",
    )

    result = run_import_rules(tmp_path)

    assert result.returncode == 0


def test_same_specificity_overlap_fails_validation(tmp_path: Path) -> None:
    """Reject overlapping rules when neither target is more specific."""
    write_policy(
        tmp_path,
        [
            rule(
                name="first-boundary",
                targets=["developer.feature_area"],
                mode="deny_only",
                deny=["developer.ui"],
            ),
            rule(
                name="second-boundary",
                targets=["developer.feature_area"],
                mode="allow_only",
                allow=["developer.feature_area"],
            ),
        ],
    )
    write_file(
        tmp_path / "src/developer/feature_area/example.py",
        "import developer.feature_area.models\n",
    )

    result = run_import_rules(tmp_path)

    assert result.returncode == 1
    assert "matches multiple rules with the same specificity" in result.stderr
    assert "first-boundary" in result.stderr
    assert "second-boundary" in result.stderr


def test_nonexistent_target_fails_clearly(tmp_path: Path) -> None:
    """Fail clearly when a dotted target does not resolve under src/."""
    write_policy(
        tmp_path,
        [
            rule(
                name="missing-target",
                targets=["developer.does_not_exist"],
                mode="deny_only",
                deny=["developer.ui"],
            )
        ],
    )
    write_file(tmp_path / "src/developer/feature_area/example.py", "import typing\n")

    result = run_import_rules(tmp_path)

    assert result.returncode == 1
    assert (
        "Target 'developer.does_not_exist' does not resolve to a source module or package under src/"
        in result.stderr
    )


def test_invalid_mode_fails_clearly(tmp_path: Path) -> None:
    """Fail clearly when a rule uses an unsupported mode."""
    write_policy(
        tmp_path,
        [
            {
                "name": "bad-mode",
                "targets": ["developer.feature_area"],
                "mode": "allow",
                "allow": ["developer.feature_area"],
            }
        ],
    )
    write_file(tmp_path / "src/developer/feature_area/example.py", "import typing\n")

    result = run_import_rules(tmp_path)

    assert result.returncode == 1
    assert "Rule 'bad-mode' has invalid mode 'allow'" in result.stderr


def test_missing_targets_fails_clearly(tmp_path: Path) -> None:
    """Fail clearly when a rule omits targets."""
    write_policy(
        tmp_path,
        [{"name": "missing-targets", "mode": "deny_only", "deny": ["developer.ui"]}],
    )
    write_file(tmp_path / "src/developer/feature_area/example.py", "import typing\n")

    result = run_import_rules(tmp_path)

    assert result.returncode == 1
    assert (
        "Rule 'missing-targets' must include a non-empty 'targets' list"
        in result.stderr
    )


def test_invalid_allow_deny_combination_fails_clearly(tmp_path: Path) -> None:
    """Fail clearly when mode-specific allow and deny requirements are violated."""
    write_policy(
        tmp_path,
        [
            rule(
                name="bad-combination",
                targets=["developer.feature_area"],
                mode="allow_only",
                allow=["developer.feature_area"],
                deny=["developer.ui"],
            )
        ],
    )
    write_file(tmp_path / "src/developer/feature_area/example.py", "import typing\n")

    result = run_import_rules(tmp_path)

    assert result.returncode == 1
    assert (
        "Rule 'bad-combination' mode 'allow_only' does not accept 'deny'"
        in result.stderr
    )


def test_malformed_yaml_returns_clear_failure(tmp_path: Path) -> None:
    """Fail clearly when the policy file is invalid YAML."""
    write_file(tmp_path / "harness/policy/import_rules.yaml", "rules: [\n")
    write_file(tmp_path / "src/developer/feature_area/example.py", "import typing\n")

    result = run_import_rules(tmp_path)

    assert result.returncode == 1
    assert "Architectural fitness check failed: Invalid YAML in" in result.stderr


def run_import_rules(repo_root: Path) -> subprocess.CompletedProcess[str]:
    """Execute the import-rules module against a temporary repo."""
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(REPO_ROOT)
        if not pythonpath
        else os.pathsep.join([str(REPO_ROOT), pythonpath])
    )
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "harness.fitness.scripts.import_rules",
            "--config",
            "harness/policy/import_rules.yaml",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def rule(
    *,
    name: str,
    targets: list[str],
    mode: str,
    description: str | None = None,
    allow: list[str] | None = None,
    deny: list[str] | None = None,
) -> dict[str, object]:
    """Build one temporary rule mapping."""
    raw_rule: dict[str, object] = {
        "name": name,
        "targets": targets,
        "mode": mode,
    }
    if description is not None:
        raw_rule["description"] = description
    if allow is not None:
        raw_rule["allow"] = allow
    if deny is not None:
        raw_rule["deny"] = deny
    return raw_rule


def write_policy(repo_root: Path, rules: list[dict[str, object]]) -> None:
    """Write a temporary import-rule policy to a repository."""
    write_file(
        repo_root / "harness/policy/import_rules.yaml",
        build_policy_yaml(rules),
    )


def build_policy_yaml(rules: list[dict[str, object]]) -> str:
    """Build YAML for a temporary rule configuration."""
    return yaml.safe_dump({"rules": rules}, sort_keys=False)


def write_file(path: Path, content: str) -> None:
    """Create a file and any missing parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
