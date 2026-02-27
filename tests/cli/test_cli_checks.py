from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from engineeringagent import cli as cli_module
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

    calls: list[tuple[Path, object, list[str] | None, dict[str, object]]] = []

    def _fake_run_checks(
        project_root: str | Path,
        *,
        phase: object,
        checks: list[str] | None = None,
        **kwargs: object,
    ) -> ChecksRunResult:
        calls.append((Path(project_root), phase, checks, dict(kwargs)))
        return ChecksRunResult(ok=True, output="delegated")

    monkeypatch.setattr("engineeringagent.checks.run_checks", _fake_run_checks)

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
            "--phase",
            "iteration_end",
            "--base",
            "main",
            "--head",
            "HEAD",
            "--verbose-output",
        ],
    )

    assert result.exit_code == 0
    assert "delegated" in result.stdout
    assert "checks run: ok" in result.stdout
    assert len(calls) == 1
    project_root, phase, checks, kwargs = calls[0]
    assert project_root == tmp_path.resolve()
    assert phase is not None
    assert checks == ["commands"]
    assert kwargs.get("check_id") == "smoke"
    assert kwargs.get("base") == "main"
    assert kwargs.get("head") == "HEAD"
    assert kwargs.get("verbose_output") is True
    assert "start_agent_fn" not in kwargs
    assert "run_agent_fn" not in kwargs


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

    calls: list[dict[str, object]] = []

    def _fake_run_checks(
        project_root: str | Path,
        *,
        phase: object,
        checks: list[str] | None = None,
        **kwargs: object,
    ) -> ChecksRunResult:
        _ = project_root
        _ = phase
        _ = checks
        calls.append(dict(kwargs))
        return ChecksRunResult(ok=True, output="delegated")

    monkeypatch.setattr("engineeringagent.checks.run_checks", _fake_run_checks)

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
            "  docs/spec/features/FEAT-001.yaml  ",
            "--phase",
            "feature_done",
        ],
    )

    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0].get("feature_path") == "docs/spec/features/FEAT-001.yaml"


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

    calls: list[dict[str, object]] = []

    def _fake_run_checks(
        _project_root: str | Path,
        *,
        phase: object,
        checks: list[str] | None = None,
        **kwargs: object,
    ) -> ChecksRunResult:
        _ = phase
        _ = checks
        calls.append(dict(kwargs))
        return ChecksRunResult(
            ok=True,
            dry_run=True,
            output="[decision:smoke] type=command phase=iteration_end decision=run reason=manual",
        )

    monkeypatch.setattr("engineeringagent.checks.run_checks", _fake_run_checks)

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
    assert calls[0].get("dry_run") is True


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

    def _fake_run_checks(
        _project_root: str | Path,
        *,
        phase: object,
        checks: list[str] | None = None,
        **kwargs: object,
    ) -> ChecksRunResult:
        _ = phase
        _ = checks
        _ = kwargs
        return ChecksRunResult(
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

    monkeypatch.setattr("engineeringagent.checks.run_checks", _fake_run_checks)

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
