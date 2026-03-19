"""Tests for the import-boundary fitness script."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_absolute_allowed_local_import_passes(tmp_path: Path) -> None:
    """Allow orchestrator-local imports."""
    write_policy(
        tmp_path,
        paths=["src/developer/feature_area/**/*.py"],
        allow_local_prefixes=["developer.feature_area"],
        allow_relative_import_roots=["."],
        deny_local_prefixes=["developer"],
    )
    write_file(
        tmp_path / "src/developer/feature_area/example.py",
        "from developer.feature_area.models import GatePhase\n",
    )

    result = run_import_rules(tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""


def test_absolute_denied_local_import_fails(tmp_path: Path) -> None:
    """Reject non-orchestrator developer imports."""
    write_policy(
        tmp_path,
        paths=["src/developer/feature_area/**/*.py"],
        allow_local_prefixes=["developer.feature_area"],
        allow_relative_import_roots=["."],
        deny_local_prefixes=["developer.ui"],
    )
    write_file(
        tmp_path / "src/developer/feature_area/example.py",
        "from developer.ui.models import Screen\n",
    )

    result = run_import_rules(tmp_path)

    assert result.returncode == 1
    assert "Architectural fitness check failed." in result.stderr
    assert (
        "src/developer/feature_area/example.py:1 imports developer.ui.models"
        in result.stderr
    )


def test_relative_local_import_within_orchestrators_passes(tmp_path: Path) -> None:
    """Allow relative imports that stay inside the package."""
    write_policy(
        tmp_path,
        paths=["src/developer/feature_area/**/*.py"],
        allow_local_prefixes=["developer.feature_area"],
        allow_relative_import_roots=["."],
        deny_local_prefixes=["developer"],
    )
    write_file(
        tmp_path / "src/developer/feature_area/protocols.py",
        "from .models import GatePhase\n",
    )

    result = run_import_rules(tmp_path)

    assert result.returncode == 0


def test_stdlib_import_passes(tmp_path: Path) -> None:
    """Allow stdlib imports."""
    write_policy(
        tmp_path,
        paths=["src/developer/feature_area/**/*.py"],
        allow_local_prefixes=["developer.feature_area"],
        allow_relative_import_roots=["."],
        deny_local_prefixes=["developer"],
    )
    write_file(tmp_path / "src/developer/feature_area/example.py", "import typing\n")

    result = run_import_rules(tmp_path)

    assert result.returncode == 0


def test_third_party_import_passes(tmp_path: Path) -> None:
    """Allow third-party imports."""
    write_policy(
        tmp_path,
        paths=["src/developer/feature_area/**/*.py"],
        allow_local_prefixes=["developer.feature_area"],
        allow_relative_import_roots=["."],
        deny_local_prefixes=["developer"],
    )
    write_file(
        tmp_path / "src/developer/feature_area/example.py",
        "from pydantic import BaseModel\n",
    )

    result = run_import_rules(tmp_path)

    assert result.returncode == 0


def test_multiple_violations_across_files_are_reported(tmp_path: Path) -> None:
    """Report all violations instead of stopping at the first one."""
    write_policy(
        tmp_path,
        paths=["src/developer/feature_area/**/*.py"],
        allow_local_prefixes=["developer.feature_area"],
        allow_relative_import_roots=["."],
        deny_local_prefixes=["developer.ui"],
    )
    write_file(
        tmp_path / "src/developer/feature_area/one.py",
        "import developer.ui.models\n",
    )
    write_file(
        tmp_path / "src/developer/feature_area/two.py",
        "from developer.ui.commands.check import run\n",
    )

    result = run_import_rules(tmp_path)

    assert result.returncode == 1
    assert (
        "src/developer/feature_area/one.py:1 imports developer.ui.models"
        in result.stderr
    )
    assert (
        "src/developer/feature_area/two.py:1 imports developer.ui.commands.check"
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


def write_policy(
    repo_root: Path,
    *,
    paths: list[str],
    allow_local_prefixes: list[str],
    allow_relative_import_roots: list[str],
    deny_local_prefixes: list[str],
) -> None:
    """Write a fictive import-rule policy to a temporary repo."""
    write_file(
        repo_root / "harness/policy/import_rules.yaml",
        build_policy_yaml(
            paths=paths,
            allow_local_prefixes=allow_local_prefixes,
            allow_relative_import_roots=allow_relative_import_roots,
            deny_local_prefixes=deny_local_prefixes,
        ),
    )


def build_policy_yaml(
    *,
    paths: list[str],
    allow_local_prefixes: list[str],
    allow_relative_import_roots: list[str],
    deny_local_prefixes: list[str],
) -> str:
    """Build YAML for a temporary, fictive rule configuration."""
    rendered_paths = "\n".join(f'      - "{path}"' for path in paths)
    rendered_allow_prefixes = "\n".join(
        f'        - "{prefix}"' for prefix in allow_local_prefixes
    )
    rendered_relative_roots = "\n".join(
        f'        - "{root}"' for root in allow_relative_import_roots
    )
    rendered_deny_prefixes = "\n".join(
        f'        - "{prefix}"' for prefix in deny_local_prefixes
    )

    return f"""rules:
  - name: "temporary-import-rule"
    paths:
{rendered_paths}
    allow:
      local_prefixes:
{rendered_allow_prefixes}
      relative_import_roots:
{rendered_relative_roots}
    deny:
      local_prefixes:
{rendered_deny_prefixes}
"""


def write_file(path: Path, content: str) -> None:
    """Create a file and any missing parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
