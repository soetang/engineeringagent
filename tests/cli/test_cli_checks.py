from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from engineeringagent import cli as cli_module


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


def test_cli_checks_run_reviewers_requires_feature_path(tmp_path: Path) -> None:
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
    assert "--feature-path" in result.stdout
    assert "required" in result.stdout


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

    from engineeringagent.checks.api import ChecksRunResult

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
    assert callable(kwargs.get("start_agent_fn"))


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

    from engineeringagent.checks.api import ChecksRunResult

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
