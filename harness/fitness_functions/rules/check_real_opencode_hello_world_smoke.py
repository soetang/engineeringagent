from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Iterable

import os
import yaml

from engineeringagent.domain.specification import iter_feature_files
from engineeringagent.domain.specification import load_markdown_frontmatter
from engineeringagent.checks import emit_fitness_result
from engineeringagent.checks import resolve_harness_bool_setting
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "smoke.opencode-real-hello-world"
_SPEC_TEMPLATE_NAME = "real_opencode_hello_world_feature_template.yaml"
_PLAN_TEMPLATE_PATH = Path("docs/fixtures/real_opencode_hello_world_plan_template.md")
_FEATURE_SPEC_RELATIVE_PATH = Path("docs/specifications/features/FEAT-001-hello-world-smoke/spec.yaml")
_RUNTIME_STATUSES = {"backlog", "in_progress", "done", "blocked"}
_SMOKE_TEMPLATE_ALLOWED_KEYS = frozenset(
    {
        "id",
        "title",
        "type",
        "expected_commit_subject",
        "planning_tier",
        "status",
        "priority",
        "objective",
        "context",
        "constraints",
        "implementation_notes",
        "acceptance",
        "artifacts",
        "updated_at",
    }
)

SPARK_AGENT_MODEL = "openai/gpt-5.3-codex-spark"


def build_init_argv(*, tmp_repo: Path) -> list[str]:
    """Build the init argv used by the real-agent smoke run."""
    return [
        "uv",
        "run",
        "engineeringagent",
        "--project-root",
        str(tmp_repo),
        "init",
        "slim",
        "--model",
        SPARK_AGENT_MODEL,
        "--no-precommit-install",
    ]


def build_run_argv(*, tmp_repo: Path) -> list[str]:
    """Build the loop argv used by the real-agent smoke run."""
    return [
        "uv",
        "run",
        "engineeringagent",
        "--project-root",
        str(tmp_repo),
        "run",
        "--all",
        "--max-iterations",
        "3",
    ]


def _result(
    *,
    status: RuleStatus,
    summary: str,
    violations: list[str] | None = None,
    details: dict[str, object] | None = None,
) -> FitnessRuleResult:
    return FitnessRuleResult(
        contract_version=CONTRACT_VERSION,
        rule_id=RULE_ID,
        status=status,
        severity=RuleSeverity.ERROR,
        summary=summary,
        violations=violations or [],
        details=details,
    )


def _run(
    argv: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    merged_env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    if env:
        merged_env.update(env)
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
        env=merged_env,
    )


def _require_ok(
    proc: subprocess.CompletedProcess[str],
    *,
    label: str,
    violations: list[str],
) -> bool:
    if proc.returncode == 0:
        return True

    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()
    rendered = f"{label}: exited non-zero ({proc.returncode})"
    if stderr:
        rendered = f"{rendered}: {stderr}"
    elif stdout:
        rendered = f"{rendered}: {stdout}"
    violations.append(rendered)
    return False


def _bundle_template_violations(repo_root: Path) -> list[str]:
    fitness_functions_root = Path(__file__).resolve().parent.parent
    spec_path = fitness_functions_root / _SPEC_TEMPLATE_NAME
    spec_payload = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec_payload, dict):
        return [f"{_SPEC_TEMPLATE_NAME} must parse as a mapping"]

    plan_frontmatter = load_markdown_frontmatter(repo_root / _PLAN_TEMPLATE_PATH)
    if not isinstance(plan_frontmatter, dict):
        return [f"{_PLAN_TEMPLATE_PATH.as_posix()} frontmatter must parse as a mapping"]

    violations: list[str] = []
    spec_id = spec_payload.get("id")
    planning_tier = spec_payload.get("planning_tier")
    plan_artifact = spec_payload.get("artifacts", {}).get("plan")
    unexpected_keys = sorted(
        key for key in spec_payload if isinstance(key, str) and key not in _SMOKE_TEMPLATE_ALLOWED_KEYS
    )

    if plan_artifact != "plan.md":
        violations.append("spec artifacts.plan must be plan.md for the smoke bundle")
    if unexpected_keys:
        violations.append(
            "spec template contains unsupported keys for the smoke bundle: "
            + ", ".join(unexpected_keys)
        )
    if not isinstance(spec_id, str):
        violations.append("spec template id must be a string")
    if not isinstance(planning_tier, str):
        violations.append("spec template planning_tier must be a string")

    if isinstance(spec_id, str):
        if plan_frontmatter.get("plan_id") != spec_id:
            violations.append(f"plan frontmatter plan_id must match spec id {spec_id}")
        if plan_frontmatter.get("feature_id") != spec_id:
            violations.append(f"plan frontmatter feature_id must match spec id {spec_id}")
    if plan_frontmatter.get("source_spec") != "spec.yaml":
        violations.append("plan frontmatter source_spec must be spec.yaml")
    if isinstance(planning_tier, str) and (
        plan_frontmatter.get("planning_tier") != planning_tier
    ):
        violations.append(
            "plan frontmatter planning_tier must match spec planning_tier "
            f"{planning_tier}"
        )
    plan_status = plan_frontmatter.get("status")
    if plan_status not in _RUNTIME_STATUSES:
        violations.append("plan frontmatter status must use runtime vocabulary")

    phases = plan_frontmatter.get("phases")
    if not isinstance(phases, list) or not phases:
        violations.append("plan frontmatter must declare at least one phase")
        return violations

    for index, phase in enumerate(phases, start=1):
        if not isinstance(phase, dict):
            violations.append(f"plan phase {index} must be a mapping")
            continue

        phase_status = phase.get("status")
        if phase_status not in _RUNTIME_STATUSES:
            violations.append(f"plan phase {index} status must use runtime vocabulary")

        verification = phase.get("verification")
        if not isinstance(verification, list) or not any(
            isinstance(command, str) and command.strip() for command in verification
        ):
            violations.append(
                f"plan phase {index} must declare at least one verification command"
            )

    return violations


def _write_feature_spec(tmp_repo: Path) -> None:
    fitness_functions_root = Path(__file__).resolve().parent.parent
    spec_payload = (fitness_functions_root / _SPEC_TEMPLATE_NAME).read_text(
        encoding="utf-8"
    )
    repo_root = fitness_functions_root.parents[1]
    plan_payload = (repo_root / _PLAN_TEMPLATE_PATH).read_text(encoding="utf-8")

    target = tmp_repo / _FEATURE_SPEC_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(spec_payload.rstrip("\n") + "\n", encoding="utf-8")
    (target.parent / "plan.md").write_text(
        plan_payload.rstrip("\n") + "\n",
        encoding="utf-8",
    )


def _iter_done_specs(tmp_repo: Path) -> Iterable[Path]:
    root = tmp_repo / "docs/specifications/features_done"
    if not root.exists():
        return ()
    return iter_feature_files(root)


def _parse_feature_statuses(spec_path: Path) -> tuple[str | None, tuple[str, ...]]:
    payload = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return (None, ())

    top_level_status = payload.get("status")
    if not isinstance(top_level_status, str):
        top_level_status = None

    progress_statuses: list[str] = []
    plan_ref = payload.get("artifacts", {}).get("plan")
    if isinstance(plan_ref, str) and spec_path.name == "spec.yaml":
        plan_path = spec_path.parent / plan_ref
        if plan_path.is_file():
            try:
                frontmatter = load_markdown_frontmatter(plan_path)
            except (OSError, ValueError, yaml.YAMLError):
                frontmatter = None
            if isinstance(frontmatter, dict):
                phases = frontmatter.get("phases")
                if isinstance(phases, list):
                    for phase in phases:
                        if not isinstance(phase, dict):
                            continue
                        phase_status = phase.get("status")
                        if isinstance(phase_status, str):
                            progress_statuses.append(phase_status)
                return (top_level_status, tuple(progress_statuses))

    return (top_level_status, tuple(progress_statuses))


def _run_verification_commands(tmp_repo: Path, violations: list[str]) -> bool:
    commands: list[list[str]] = [
        [
            "uv",
            "run",
            "python",
            "-c",
            "from hello_world import hello; assert hello('World') == 'Hello, World!'",
        ],
        [
            "uv",
            "run",
            "python",
            "-c",
            "import subprocess; out=subprocess.check_output(['uv','run','python','-m','hello_world'], text=True); assert out.strip()=='Hello, World!'",
        ],
    ]

    for index, argv in enumerate(commands, start=1):
        proc = _run(
            argv,
            cwd=tmp_repo,
            timeout_seconds=20,
        )
        if not _require_ok(proc, label=f"verification[{index}]", violations=violations):
            return False
    return True


def main() -> int:
    """Run a real OpenCode hello-world smoke loop when enabled."""
    repo_root = Path(__file__).resolve().parents[3]
    try:
        enabled = resolve_harness_bool_setting(
            repo_root,
            table="fitness",
            key="opencode-real-smoke",
            default=False,
        )
    except ValueError as exc:
        emit_fitness_result(
            _result(
                status=RuleStatus.FAIL,
                summary="invalid engineeringagent TOML configuration for smoke rule",
                violations=[
                    str(exc),
                    "remediation: fix engineeringagent.toml / pyproject.toml[tool.engineeringagent] or disable [harness.fitness].opencode-real-smoke",
                ],
            )
        )
        return 0

    if not enabled:
        emit_fitness_result(
            _result(
                status=RuleStatus.PASS,
                summary="skipped (disabled in engineeringagent.toml)",
            )
        )
        return 0

    if shutil.which("opencode") is None:
        emit_fitness_result(
            _result(
                status=RuleStatus.FAIL,
                summary="opencode not installed (enabled in engineeringagent.toml)",
                violations=[
                    "opencode not found on PATH",
                    "remediation: install/configure opencode or disable [harness.fitness].opencode-real-smoke in engineeringagent.toml",
                ],
            )
        )
        return 0

    violations: list[str] = []
    try:
        with tempfile.TemporaryDirectory(
            prefix="engineeringagent-real-opencode-smoke-",
        ) as tmp_dir:
            tmp_repo = Path(tmp_dir)

            init_git = _run(["git", "init"], cwd=tmp_repo, timeout_seconds=30)
            _require_ok(init_git, label="git init", violations=violations)
            _run(
                [
                    "git",
                    "config",
                    "user.email",
                    "engineeringagent-smoke@example.invalid",
                ],
                cwd=tmp_repo,
                timeout_seconds=10,
            )
            _run(
                ["git", "config", "user.name", "EngineeringAgent Smoke"],
                cwd=tmp_repo,
                timeout_seconds=10,
            )

            uv_init_proc = _run(
                [
                    "uv",
                    "init",
                    ".",
                    "--package",
                    "--vcs",
                    "none",
                    "--no-readme",
                    "--no-pin-python",
                ],
                cwd=tmp_repo,
                timeout_seconds=60,
            )
            if not _require_ok(uv_init_proc, label="uv init", violations=violations):
                emit_fitness_result(
                    _result(
                        status=RuleStatus.FAIL,
                        summary="failed to initialize uv project in temp repo",
                        violations=violations,
                    )
                )
                return 0

            init_cmd = build_init_argv(tmp_repo=tmp_repo)
            init_proc = _run(init_cmd, cwd=repo_root, timeout_seconds=180)
            if not _require_ok(
                init_proc, label="engineeringagent init slim", violations=violations
            ):
                emit_fitness_result(
                    _result(
                        status=RuleStatus.FAIL,
                        summary="failed to initialize temp repo with engineeringagent init slim",
                        violations=violations,
                    )
                )
                return 0

            agents_doc = tmp_repo / ".opencode/agents/engineeringagent.md"
            if not agents_doc.exists():
                violations.append(
                    "engineeringagent init slim did not create .opencode/agents/engineeringagent.md"
                )
                emit_fitness_result(
                    _result(
                        status=RuleStatus.FAIL,
                        summary="init scaffold missing required OpenCode agents doc",
                        violations=violations,
                    )
                )
                return 0

            template_violations = _bundle_template_violations(repo_root)
            if template_violations:
                emit_fitness_result(
                    _result(
                        status=RuleStatus.FAIL,
                        summary="real-agent smoke bundle templates are inconsistent",
                        violations=template_violations,
                    )
                )
                return 0

            _write_feature_spec(tmp_repo)

            add_proc = _run(["git", "add", "-A"], cwd=tmp_repo, timeout_seconds=30)
            _require_ok(add_proc, label="git add", violations=violations)
            commit_proc = _run(
                ["git", "commit", "-m", "chore: baseline scaffold"],
                cwd=tmp_repo,
                timeout_seconds=30,
            )
            if not _require_ok(
                commit_proc, label="git commit baseline", violations=violations
            ):
                emit_fitness_result(
                    _result(
                        status=RuleStatus.FAIL,
                        summary="failed to create baseline commit in temp repo",
                        violations=violations,
                    )
                )
                return 0

            run_cmd = build_run_argv(tmp_repo=tmp_repo)
            run_proc = _run(run_cmd, cwd=repo_root, timeout_seconds=780)
            if run_proc.returncode != 0:
                combined = (
                    (run_proc.stdout or "") + "\n" + (run_proc.stderr or "")
                ).lower()
                if "permission" in combined or "requires login" in combined:
                    violations.append(
                        "opencode permission rejected; ensure agent permissions allow this repository"
                    )
                    violations.append(
                        "remediation: review temp repo .opencode/agents/engineeringagent.md (scaffolded by init slim)"
                    )
                else:
                    _require_ok(
                        run_proc, label="engineeringagent run", violations=violations
                    )
                emit_fitness_result(
                    _result(
                        status=RuleStatus.FAIL,
                        summary="engineeringagent run did not complete successfully",
                        violations=violations,
                    )
                )
                return 0

            done_specs = [
                path
                for path in _iter_done_specs(tmp_repo)
                if "FEAT-001" in path.as_posix()
            ]
            if not done_specs:
                violations.append(
                    "expected archived feature spec under docs/specifications/features_done (missing FEAT-001 bundle)"
                )
                emit_fitness_result(
                    _result(
                        status=RuleStatus.FAIL,
                        summary="loop did not archive hello-world feature spec",
                        violations=violations,
                    )
                )
                return 0

            archived = done_specs[0]
            top_status, progress_statuses = _parse_feature_statuses(archived)
            if top_status != "done":
                violations.append(
                    f"archived spec top-level status must be done (got {top_status!r})"
                )
            if not progress_statuses or any(
                status != "done" for status in progress_statuses
            ):
                violations.append(
                    "archived feature progress must have all statuses set to done"
                )

            _run_verification_commands(tmp_repo, violations)

            status = RuleStatus.PASS if not violations else RuleStatus.FAIL
            summary = (
                "Real OpenCode hello-world smoke loop completed."
                if status == RuleStatus.PASS
                else f"Real OpenCode hello-world smoke loop failed ({len(violations)} issue(s))."
            )
            emit_fitness_result(
                _result(
                    status=status,
                    summary=summary,
                    violations=violations,
                )
            )
            return 0
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        emit_fitness_result(
            _result(
                status=RuleStatus.ERROR,
                summary=f"unexpected exception during real-agent smoke run: {exc}",
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
