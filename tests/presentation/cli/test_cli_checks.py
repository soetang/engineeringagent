from __future__ import annotations

from pathlib import Path
import pytest
from typer.testing import CliRunner

from engineeringagent.presentation import cli as cli_module
from engineeringagent.application import RunChecksResult as ApplicationRunChecksResult
from engineeringagent.checks.changed_paths import ChangedPathsResult
from engineeringagent.checks.api import ChecksRunResult
from engineeringagent.checks.strategy_contracts import CheckExecutionRecord


def test_cli_checks_run_requires_checks_yaml(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        ["--project-root", str(tmp_path), "checks", "run"],
    )

    assert result.exit_code == 1
    assert "missing harness/checks.yaml" in result.stdout


def test_cli_checks_run_requires_configured_checks_path(tmp_path: Path) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        "[harness.checks]\npath = \"config/checks.yaml\"\n",
        encoding="utf-8",
    )
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        ["--project-root", str(tmp_path), "checks", "run"],
    )

    assert result.exit_code == 1
    assert "missing config/checks.yaml" in result.stdout


def test_cli_checks_run_executes_command_check(tmp_path: Path) -> None:
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    (harness_dir / "checks.yaml").write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        ["--project-root", str(tmp_path), "checks", "run", "--phase", "iteration_end"],
    )

    assert result.exit_code == 0
    assert "[check:smoke]" in result.stdout
    assert "checks run: ok" in result.stdout


def test_cli_checks_run_accepts_repeatable_checks_groups(tmp_path: Path) -> None:
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    (harness_dir / "checks.yaml").write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "run",
            "--checks",
            "commands",
            "--checks",
            "fitness",
            "--phase",
            "iteration_end",
        ],
    )

    assert result.exit_code == 0
    assert "checks run: ok" in result.stdout


def test_cli_checks_run_rejects_unknown_checks_group(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "run",
            "--checks",
            "nope",
        ],
    )

    assert result.exit_code == 1
    assert "unknown checks groups" in result.stdout
    assert "Supported" in result.stdout


def test_cli_checks_run_reviewers_without_feature_path_delegates_to_handler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_cmd_checks_run(args: object) -> int:
        captured["checks"] = getattr(args, "checks", None)
        captured["feature_path"] = getattr(args, "feature_path", "missing")
        return 0

    monkeypatch.setattr(cli_module, "cmd_checks_run", _fake_cmd_checks_run)

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "run",
            "--checks",
            "reviewers",
        ],
    )

    assert result.exit_code == 0
    assert captured["checks"] == ["reviewers"]
    assert captured["feature_path"] is None


def test_cli_checks_run_reviewers_without_feature_path_is_actionable_error(
    tmp_path: Path,
) -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "run",
            "--checks",
            "reviewers",
        ],
    )

    assert result.exit_code == 1
    assert "checks input error:" in result.stdout
    assert "feature_path is required when reviewers checks are selected" in result.stdout


def test_cli_checks_run_all_phases_reviewers_without_feature_path_is_actionable_error(
    tmp_path: Path,
) -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "run",
            "--checks",
            "reviewers",
            "--all-phases",
        ],
    )

    assert result.exit_code == 1
    assert "checks input error:" in result.stdout
    assert "feature_path is required when reviewers checks are selected" in result.stdout


def test_cli_checks_run_mixed_groups_with_reviewers_requires_feature_path(
    tmp_path: Path,
) -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "run",
            "--checks",
            "commands",
            "--checks",
            "reviewers",
        ],
    )

    assert result.exit_code == 1
    assert "checks input error:" in result.stdout
    assert "feature_path is required when reviewers checks are selected" in result.stdout


def test_cli_checks_run_accepts_check_id_option(tmp_path: Path) -> None:
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    (harness_dir / "checks.yaml").write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "run",
            "--check-id",
            "smoke",
            "--phase",
            "iteration_end",
        ],
    )

    assert result.exit_code == 0
    assert "checks run: ok" in result.stdout


def test_cli_checks_run_delegates_to_checks_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    (harness_dir / "checks.yaml").write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
        encoding="utf-8",
    )

    calls: list[object] = []

    class _FakeChecksService:
        def run(self, request: object) -> ApplicationRunChecksResult:
            calls.append(request)
            result = ChecksRunResult(ok=True, output="delegated")
            return ApplicationRunChecksResult(
                phase_results=((getattr(request, "phase"), result),),
                result=result,
                failed_phase=None,
                failed_runtime_message=None,
            )

    monkeypatch.setattr(
        "engineeringagent.presentation.cli.checks.AppFactory.build_checks_service",
        lambda self: _FakeChecksService(),
    )

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "run",
            "--checks",
            "commands",
            "--check-id",
            "smoke",
            "--feature-path",
            "docs/spec/features/FEAT-177/spec.yaml",
            "--phase",
            "iteration_end",
            "--base",
            "main",
            "--head",
            "HEAD",
            "--verbose-output",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "delegated" in result.stdout
    assert "checks run: ok" in result.stdout
    assert len(calls) == 1
    request = calls[0]
    assert getattr(request, "project_root") == tmp_path.resolve()
    assert getattr(request, "phase") is not None
    assert getattr(request, "selected_checks") == ["commands"]
    assert getattr(request, "check_id") == "smoke"
    assert getattr(request, "feature_path") == "docs/spec/features/FEAT-177/spec.yaml"
    assert getattr(request, "base") == "main"
    assert getattr(request, "head") == "HEAD"
    assert getattr(request, "verbose_output") is True
    assert getattr(request, "dry_run") is True


def test_cli_checks_run_normalizes_feature_path_before_delegating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    (harness_dir / "checks.yaml").write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  doc_review:",
                "    type: reviewer",
                "    prompt_file: harness/reviewers/prompts/doc_review.md",
                "    when:",
                "      phase: feature_done",
                "",
            ]
        ),
        encoding="utf-8",
    )

    calls: list[object] = []

    class _FakeChecksService:
        def run(self, request: object) -> ApplicationRunChecksResult:
            calls.append(request)
            result = ChecksRunResult(ok=True, output="delegated")
            return ApplicationRunChecksResult(
                phase_results=((getattr(request, "phase"), result),),
                result=result,
                failed_phase=None,
                failed_runtime_message=None,
            )

    monkeypatch.setattr(
        "engineeringagent.presentation.cli.checks.AppFactory.build_checks_service",
        lambda self: _FakeChecksService(),
    )

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "run",
            "--checks",
            "reviewers",
            "--feature-path",
            "  docs/spec/features/FEAT-001/spec.yaml  ",
            "--phase",
            "feature_done",
        ],
    )

    assert result.exit_code == 0
    assert len(calls) == 1
    assert getattr(calls[0], "feature_path") == "docs/spec/features/FEAT-001/spec.yaml"


def test_cli_checks_run_dry_run_delegates_and_reports_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    (harness_dir / "checks.yaml").write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "echo ok"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    calls: list[object] = []

    class _FakeChecksService:
        def run(self, request: object) -> ApplicationRunChecksResult:
            calls.append(request)
            result = ChecksRunResult(
                ok=True,
                dry_run=True,
                output="[decision:smoke] type=command phase=iteration_end decision=run reason=manual",
            )
            return ApplicationRunChecksResult(
                phase_results=((getattr(request, "phase"), result),),
                result=result,
                failed_phase=None,
                failed_runtime_message=None,
            )

    monkeypatch.setattr(
        "engineeringagent.presentation.cli.checks.AppFactory.build_checks_service",
        lambda self: _FakeChecksService(),
    )

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "run",
            "--checks",
            "commands",
            "--phase",
            "iteration_end",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "[decision:smoke]" in result.stdout
    assert "checks dry-run: ok" in result.stdout
    assert len(calls) == 1
    assert getattr(calls[0], "dry_run") is True


def test_cli_checks_run_failure_emits_runtime_type_without_failed_group(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    (harness_dir / "checks.yaml").write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"import sys; sys.exit(1)\\""',
                "",
            ]
        ),
        encoding="utf-8",
    )

    class _FakeChecksService:
        def run(self, request: object) -> ApplicationRunChecksResult:
            _ = request
            result = ChecksRunResult(
                ok=False,
                failed_check_id="smoke",
                executions=(
                    CheckExecutionRecord(
                        check_id="smoke",
                        check_type="command",
                        ok=False,
                        output="[check:smoke] failed",
                    ),
                ),
            )
            return ApplicationRunChecksResult(
                phase_results=((cli_module.HarnessCheckPhase.ITERATION_END, result),),
                result=result,
                failed_phase=None,
                failed_runtime_message="checks failed: type=command check_id=smoke",
            )

    monkeypatch.setattr(
        "engineeringagent.presentation.cli.checks.AppFactory.build_checks_service",
        lambda self: _FakeChecksService(),
    )

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "run",
            "--checks",
            "commands",
            "--phase",
            "iteration_end",
        ],
    )

    assert result.exit_code == 1
    assert "checks failed: type=command check_id=smoke" in result.stdout


def test_cli_checks_run_ignores_on_change_for_explicit_phase_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    (harness_dir / "checks.yaml").write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "    when:",
                "      phase: feature_done",
                "      on_change:",
                "        - src/**/*.py",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "engineeringagent.checks.api.collect_changed_paths",
        lambda *_args, **_kwargs: ChangedPathsResult(
            paths=("README.md",),
            run_all=False,
            reason=None,
        ),
        raising=True,
    )

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "run",
            "--checks",
            "commands",
            "--phase",
            "feature_done",
        ],
    )

    assert result.exit_code == 0
    assert "[check:smoke]" in result.stdout
    assert "checks run: ok" in result.stdout


def test_cli_checks_run_all_phases_fans_out_in_deterministic_order(
    tmp_path: Path,
) -> None:
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    (harness_dir / "checks.yaml").write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  phase_iteration:",
                "    type: command",
                '    command: "python -c \\"print(\'iteration\')\\""',
                "    when:",
                "      phase: iteration_end",
                "  phase_feature:",
                "    type: command",
                '    command: "python -c \\"print(\'feature\')\\""',
                "    when:",
                "      phase: feature_done",
                "  phase_manual:",
                "    type: command",
                '    command: "python -c \\"print(\'manual\')\\""',
                "    when:",
                "      phase: manual",
                "",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "run",
            "--checks",
            "commands",
            "--all-phases",
        ],
    )

    assert result.exit_code == 0
    assert "[phase:iteration_end]" in result.stdout
    assert "[phase:feature_done]" in result.stdout
    assert "[phase:manual]" in result.stdout
    assert result.stdout.index("[phase:iteration_end]") < result.stdout.index(
        "[phase:feature_done]"
    )
    assert result.stdout.index("[phase:feature_done]") < result.stdout.index(
        "[phase:manual]"
    )
    assert "[check:phase_iteration]" in result.stdout
    assert "[check:phase_feature]" in result.stdout
    assert "[check:phase_manual]" in result.stdout
    assert "checks run: ok" in result.stdout


def test_cli_checks_run_all_phases_stops_at_first_failed_phase(
    tmp_path: Path,
) -> None:
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    (harness_dir / "checks.yaml").write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  phase_iteration:",
                "    type: command",
                '    command: "python -c \\"print(\'iteration\')\\""',
                "    when:",
                "      phase: iteration_end",
                "  phase_feature_fail:",
                "    type: command",
                '    command: "python -c \\"import sys; sys.exit(1)\\""',
                "    when:",
                "      phase: feature_done",
                "  phase_manual:",
                "    type: command",
                '    command: "python -c \\"print(\'manual\')\\""',
                "    when:",
                "      phase: manual",
                "",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "run",
            "--checks",
            "commands",
            "--all-phases",
        ],
    )

    assert result.exit_code == 1
    assert "[phase:iteration_end]" in result.stdout
    assert "[phase:feature_done]" in result.stdout
    assert "[phase:manual]" not in result.stdout
    assert "[check:phase_iteration]" in result.stdout
    assert "[check:phase_feature_fail]" in result.stdout
    assert "[check:phase_manual]" not in result.stdout
    assert (
        "checks failed: phase=feature_done type=command check_id=phase_feature_fail"
        in result.stdout
    )
