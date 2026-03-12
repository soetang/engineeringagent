from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from engineeringagent.presentation import cli as cli_module
from engineeringagent.presentation.cli import init as cli_init_module
from engineeringagent.presentation.cli import schema as cli_schema_module
from engineeringagent.presentation.cli import validate as cli_validate_module
from engineeringagent.presentation.cli import workspace as cli_workspace_module
from engineeringagent.application import (
    RunChecksResult as ApplicationRunChecksResult,
    RunLoopRequest,
    RunLoopResult,
)
from engineeringagent.adapters.config import (
    resolve_docs_root,
)
from engineeringagent.domain.quality import ChecksRunResult
from engineeringagent.presentation.presenters import (
    list_schema_ids,
    schema_from_registry,
)
from tests.presentation.cli.approach_fixture_data import (
    APPROACH_TOPIC_IDS,
)

_APPROACH_TOPIC_ID_PREFIX = re.compile(r"^\s*(?P<topic_id>[A-Za-z0-9-]+):")


def _frontmatter_from_markdown(payload: str) -> dict[str, object]:
    assert payload.startswith("---\n")
    parts = payload.split("---\n", 2)
    assert len(parts) == 3
    frontmatter = yaml.safe_load(parts[1])
    assert isinstance(frontmatter, dict)
    return frontmatter


def _parse_approach_topic_ids(payload: str) -> tuple[str, ...]:
    topic_ids: list[str] = []
    for line in payload.splitlines():
        match = _APPROACH_TOPIC_ID_PREFIX.match(line)
        if match is None:
            continue
        topic_ids.append(match.group("topic_id"))
    return tuple(topic_ids)


def _invoke_cli(args: list[str]) -> Any:
    runner = CliRunner(mix_stderr=False)
    return runner.invoke(cli_module.build_typer_app(), args)


def test_cli_surface_inventory_commands() -> None:
    result = _invoke_cli(["--help"])

    assert result.exit_code == 0
    for token in (
        "validate",
        "run",
        "approach",
        "schema",
        "checks",
        "init",
        "workspace",
        "--project-root",
        "--version",
    ):
        assert token in result.stdout


def test_cli_surface_inventory_option_spellings() -> None:
    cases = [
        (["validate", "--help"], ["--schema-only"]),
        (
            ["schema", "--help"],
            ["--format", "--output"],
        ),
        (
            ["schema", "list", "--help"],
            [],
        ),
        (
            ["approach", "--help"],
            ["--output"],
        ),
        (
            ["run", "--help"],
            [
                "--all",
                "--dry-run",
                "--max-iterations",
                "--allow-dirty",
                "--verbose-output",
            ],
        ),
        (
            ["checks", "run", "--help"],
            ["--checks", "--check-id", "--phase", "--all-phases"],
        ),
        (
            ["checks", "catalog", "--help"],
            ["--manifest-path", "--format", "--output"],
        ),
        (
            ["init", "--help"],
            ["--force", "--scaffold-profile", "--docs-mode", "--scaffold-docs-dir"],
        ),
        (
            ["workspace", "reset", "--help"],
            ["--last-accepted-commit"],
        ),
    ]

    for args, expected_options in cases:
        result = _invoke_cli(args)
        assert result.exit_code == 0
        assert "--help" in result.stdout
        for option in expected_options:
            assert option in result.stdout


def test_run_help_does_not_advertise_implement_command() -> None:
    removed_skip_flag = "--skip-" + "implement"
    result = _invoke_cli(["run", "--help"])
    stdout = result.stdout

    assert result.exit_code == 0
    assert "--implement-command" not in stdout
    assert removed_skip_flag not in stdout
    assert "skip implementation and run gates only" not in stdout
    assert "skip the implementation command" not in stdout


def test_run_help_describes_bundled_feature_entrypoints() -> None:
    result = _invoke_cli(["run", "--help"])
    normalized_output = " ".join(result.stdout.split())

    assert result.exit_code == 0
    assert (
        "run feature loops from bundled spec.yaml entrypoint paths"
        in normalized_output
    )
    assert "feature spec.yaml entrypoint paths" in normalized_output
    assert "auto-discover active feature entrypoints" in normalized_output
    assert "under docs/specifications/features" in normalized_output
    assert (
        "auto-discover active feature specs under docs/specifications/features"
        not in normalized_output
    )


def test_run_rejects_removed_skip_flag() -> None:
    removed_skip_flag = "--skip-" + "implement"
    result = _invoke_cli(
        ["run", "docs/specifications/features/FEAT-900/spec.yaml", removed_skip_flag]
    )

    assert result.exit_code != 0
    combined_output = (result.stderr or "") + (result.stdout or "")
    assert removed_skip_flag in combined_output
    assert "No such option" in combined_output


def test_run_rejects_implement_command_option() -> None:
    result = _invoke_cli(["run", "--implement-command", "echo hi"])

    assert result.exit_code != 0
    assert "--implement-command" in (result.stderr or result.stdout)


def test_schema_requires_id_when_no_subcommand_is_provided() -> None:
    result = _invoke_cli(["schema"])

    assert result.exit_code == 1
    assert "provide a schema id or use `engineeringagent schema list`" in result.stdout


def test_run_all_requires_checks_yaml(tmp_path: Path) -> None:
    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "run",
            "--all",
            "--dry-run",
        ]
    )

    assert result.exit_code == 1
    assert "missing harness/checks.yaml" in result.stdout
    assert "engineeringagent init" in result.stdout


def test_run_all_requires_configured_checks_path(tmp_path: Path) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        "[harness.checks]\npath = \"config/checks.yaml\"\n",
        encoding="utf-8",
    )

    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "run",
            "--all",
            "--dry-run",
        ]
    )

    assert result.exit_code == 1
    assert "missing config/checks.yaml" in result.stdout
    assert "required for --all" in result.stdout


def test_run_all_rejects_configured_checks_path_with_parent_traversal(
    tmp_path: Path,
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        "[harness.checks]\npath = \"../checks.yaml\"\n",
        encoding="utf-8",
    )

    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "run",
            "--all",
            "--dry-run",
        ]
    )

    assert result.exit_code == 1
    assert "run config error: invalid path in" in result.stdout
    assert "cannot contain '..'" in result.stdout


def test_run_all_rejects_invalid_checks_yaml(tmp_path: Path) -> None:
    checks_path = tmp_path / "harness" / "checks.yaml"
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.write_text("checks: {}\n", encoding="utf-8")

    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "run",
            "--all",
            "--dry-run",
        ]
    )

    assert result.exit_code == 1
    assert "invalid harness/checks.yaml" in result.stdout
    assert "harness/checks.yaml:contract_version" in result.stdout


@pytest.mark.parametrize("reported_version", ["9.9.9", "3.2.1"])
def test_root_version_flag_uses_distribution_metadata_source(
    reported_version: str,
    monkeypatch: Any,
) -> None:
    requested_distribution_names: list[str] = []

    def _fake_version(distribution_name: str) -> str:
        requested_distribution_names.append(distribution_name)
        return reported_version

    monkeypatch.setattr(cli_module.importlib_metadata, "version", _fake_version)

    result = _invoke_cli(["--version"])

    assert result.exit_code == 0
    assert result.stdout == f"{reported_version}\n"
    assert result.stderr == ""
    assert requested_distribution_names == ["engineeringagent"]


def test_root_parser_still_requires_subcommand_without_version_flag() -> None:
    result = _invoke_cli([])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "Missing command" in result.stderr


def test_main_validate_command_reports_ok_via_real_cli(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    observed: dict[str, object] = {}

    class _FakeValidationService:
        def run(self, request: Any) -> Any:
            observed["project_root"] = str(request.project_root)
            observed["schema_only"] = request.schema_only
            return SimpleNamespace(ok=True, messages=())

    class _FakeAppFactory:
        def __init__(self, project_root: Path) -> None:
            observed["factory_project_root"] = str(project_root)

        def build_validation_service(self) -> Any:
            return _FakeValidationService()

    monkeypatch.setattr(
        cli_validate_module,
        "AppFactory",
        _FakeAppFactory,
    )

    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "validate",
            "--schema-only",
        ]
    )

    assert result.exit_code == 0
    assert result.stdout == "spec validation: ok\n"
    assert observed == {
        "factory_project_root": str(tmp_path.resolve()),
        "project_root": str(tmp_path.resolve()),
        "schema_only": True,
    }


def test_main_run_command_executes_loop_context_via_real_cli(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    captured: dict[str, RunLoopRequest] = {}

    class _FakeRunLoopService:
        def run(self, request: RunLoopRequest) -> RunLoopResult:
            captured["request"] = request
            return RunLoopResult(exit_code=7)

    monkeypatch.setattr(
        "engineeringagent.presentation.cli.run.AppFactory.build_run_loop_service",
        lambda self: _FakeRunLoopService(),
    )

    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "run",
            "docs/specifications/features/FEAT-900/spec.yaml",
            "--dry-run",
            "--max-iterations",
            "7",
            "--allow-dirty",
            "--verbose-output",
        ]
    )

    assert result.exit_code == 7
    request = captured["request"]
    assert request.project_root == tmp_path.resolve()
    assert request.feature_paths == ("docs/specifications/features/FEAT-900/spec.yaml",)
    assert request.run_all is False
    assert request.dry_run is True
    assert request.max_iterations == 7
    assert request.allow_dirty is True
    assert request.verbose_output is True


def test_main_run_command_prints_application_input_errors(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    class _FakeRunLoopService:
        def run(self, request: RunLoopRequest) -> RunLoopResult:
            assert request.project_root == tmp_path.resolve()
            return RunLoopResult(
                exit_code=1,
                message="run input error: provide one or more feature paths, or use --all",
            )

    monkeypatch.setattr(
        "engineeringagent.presentation.cli.run.AppFactory.build_run_loop_service",
        lambda self: _FakeRunLoopService(),
    )

    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "run",
        ]
    )

    assert result.exit_code == 1
    assert (
        result.stdout
        == "run input error: provide one or more feature paths, or use --all\n"
    )


def test_cmd_run_builds_application_request_for_run_entrypoint(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    captured: dict[str, RunLoopRequest] = {}

    class _FakeRunLoopService:
        def run(self, request: RunLoopRequest) -> RunLoopResult:
            captured["request"] = request
            return RunLoopResult(exit_code=7)

    monkeypatch.setattr(
        "engineeringagent.presentation.cli.run.AppFactory.build_run_loop_service",
        lambda self: _FakeRunLoopService(),
    )

    exit_code = cli_module.cmd_run(
        SimpleNamespace(
            project_root=str(tmp_path),
            feature_paths=["docs/specifications/features/FEAT-078/spec.yaml"],
            run_all=False,
            dry_run=True,
            max_iterations=7,
            allow_dirty=True,
            verbose_output=True,
        )
    )

    assert exit_code == 7
    request = captured["request"]
    assert request.project_root == tmp_path.resolve()
    assert request.feature_paths == ("docs/specifications/features/FEAT-078/spec.yaml",)
    assert request.run_all is False
    assert request.dry_run is True
    assert request.max_iterations == 7
    assert request.allow_dirty is True
    assert request.verbose_output is True


def test_cmd_run_builds_application_request_for_run_all_entrypoint(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    captured: dict[str, RunLoopRequest] = {}

    class _FakeRunLoopService:
        def run(self, request: RunLoopRequest) -> RunLoopResult:
            captured["request"] = request
            return RunLoopResult(exit_code=9)

    monkeypatch.setattr(
        "engineeringagent.presentation.cli.run.AppFactory.build_run_loop_service",
        lambda self: _FakeRunLoopService(),
    )

    exit_code = cli_module.cmd_run(
        SimpleNamespace(
            project_root=str(tmp_path),
            feature_paths=[],
            run_all=True,
            dry_run=True,
            max_iterations=5,
            allow_dirty=False,
            verbose_output=False,
        )
    )

    assert exit_code == 9
    request = captured["request"]
    assert request.project_root == tmp_path.resolve()
    assert request.feature_paths == ()
    assert request.run_all is True
    assert request.dry_run is True
    assert request.max_iterations == 5
    assert request.allow_dirty is False
    assert request.verbose_output is False


def test_cmd_run_prints_service_messages(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _FakeRunLoopService:
        def run(self, request: RunLoopRequest) -> RunLoopResult:
            assert request.project_root == tmp_path.resolve()
            return RunLoopResult(exit_code=1, message="run config error: missing harness/checks.yaml")

    monkeypatch.setattr(
        "engineeringagent.presentation.cli.run.AppFactory.build_run_loop_service",
        lambda self: _FakeRunLoopService(),
    )

    exit_code = cli_module.cmd_run(
        SimpleNamespace(
            project_root=str(tmp_path),
            feature_paths=[],
            run_all=True,
            dry_run=True,
            max_iterations=5,
            allow_dirty=False,
            verbose_output=False,
        )
    )

    assert exit_code == 1
    assert capsys.readouterr().out == "run config error: missing harness/checks.yaml\n"


def test_main_schema_command_writes_registry_schema_via_real_cli(tmp_path: Path) -> None:
    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "schema",
            "feature.spec",
            "--format",
            "yaml",
            "--output",
            "tmp/schema.yaml",
        ]
    )

    assert result.exit_code == 0
    assert result.stdout == "schema written: tmp/schema.yaml\n"
    schema_payload = yaml.safe_load(
        (tmp_path / "tmp" / "schema.yaml").read_text(encoding="utf-8")
    )
    assert schema_payload == schema_from_registry("feature.spec")


def test_main_schema_list_command_prints_registry_ids_via_real_cli() -> None:
    result = _invoke_cli(["schema", "list"])

    assert result.exit_code == 0
    assert result.stdout.splitlines() == list(list_schema_ids())


def test_main_checks_run_command_invokes_checks_via_real_cli(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    observed: dict[str, object] = {}

    class _FakeChecksService:
        def run(self, request: object) -> ApplicationRunChecksResult:
            observed["project_root"] = str(Path(getattr(request, "project_root")))
            observed["checks"] = getattr(request, "selected_checks")
            observed["check_id"] = getattr(request, "check_id")
            observed["feature_path"] = getattr(request, "feature_path")
            observed["phase"] = getattr(request, "phase").value
            observed["base"] = getattr(request, "base")
            observed["head"] = getattr(request, "head")
            observed["verbose_output"] = getattr(request, "verbose_output")
            observed["dry_run"] = getattr(request, "dry_run")
            checks_result = ChecksRunResult(
                ok=True,
                output="checks ok",
                dry_run=bool(getattr(request, "dry_run")),
            )
            return ApplicationRunChecksResult(
                phase_results=((getattr(request, "phase"), checks_result),),
                result=checks_result,
                failed_phase=None,
                failed_runtime_message=None,
            )

    monkeypatch.setattr(
        "engineeringagent.presentation.cli.checks.AppFactory.build_checks_service",
        lambda self: _FakeChecksService(),
    )

    result = _invoke_cli(
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
            "feature_done",
            "--base",
            "main",
            "--head",
            "HEAD",
            "--verbose-output",
        ]
    )

    assert result.exit_code == 0
    assert result.stdout == "checks ok\nchecks run: ok\n"
    assert observed["project_root"] == str(tmp_path.resolve())
    assert observed["checks"] == ["commands"]
    assert observed["check_id"] == "smoke"
    assert observed["feature_path"] is None
    assert observed["phase"] == "feature_done"
    assert observed["base"] == "main"
    assert observed["head"] == "HEAD"
    assert observed["verbose_output"] is True
    assert observed["dry_run"] is False


def test_main_approach_root_command_renders_overview_via_real_cli(tmp_path: Path) -> None:
    output_path = tmp_path / "artifacts" / "approach-overview.md"
    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "approach",
            "--output",
            "artifacts/approach-overview.md",
        ]
    )

    assert result.exit_code == 0
    assert result.stdout == "approach overview written: artifacts/approach-overview.md\n"
    rendered = output_path.read_text(encoding="utf-8")
    frontmatter = _frontmatter_from_markdown(rendered)
    assert frontmatter.get("approach_id") == "overview"


def test_main_approach_show_command_renders_topic_via_real_cli(tmp_path: Path) -> None:
    output_path = tmp_path / "artifacts" / "approach-topic.md"
    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "approach",
            "principles",
            "--output",
            "artifacts/approach-topic.md",
        ]
    )

    assert result.exit_code == 0
    assert result.stdout == "approach topic written: artifacts/approach-topic.md\n"
    rendered = output_path.read_text(encoding="utf-8")
    assert rendered.startswith("# Harness Engineering Principles")
    assert not rendered.startswith("---\n")


def test_main_approach_list_command_renders_via_real_cli(tmp_path: Path) -> None:
    output_path = tmp_path / "artifacts" / "approach-list.md"
    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "approach",
            "list",
            "--output",
            "artifacts/approach-list.md",
        ]
    )

    assert result.exit_code == 0
    assert result.stdout == "approach list written: artifacts/approach-list.md\n"
    rendered = output_path.read_text(encoding="utf-8")
    assert _parse_approach_topic_ids(rendered) == APPROACH_TOPIC_IDS
    assert "research-session: Research Session Approach - Task-specific: only when creating research.md." in rendered
    assert "plan-session: Plan Session Approach - Task-specific: only when creating plan.md." in rendered


def test_main_approach_commands_render_expected_markdown() -> None:
    overview = _invoke_cli(["approach"])
    topic_list = _invoke_cli(["approach", "list"])
    topic_page = _invoke_cli(["approach", "specifications"])

    assert overview.exit_code == 0
    assert topic_list.exit_code == 0
    assert topic_page.exit_code == 0

    assert _parse_approach_topic_ids(topic_list.stdout) == APPROACH_TOPIC_IDS
    overview_frontmatter = _frontmatter_from_markdown(overview.stdout)

    assert overview_frontmatter.get("approach_id") == "overview"
    assert topic_page.stdout.startswith("# Spec Writing Guide")
    assert not topic_page.stdout.startswith("---\n")


def test_approach_docs_render_source_first_command_examples() -> None:
    overview = _invoke_cli(["approach"])
    specifications = _invoke_cli(["approach", "specifications"])

    assert overview.exit_code == 0
    assert specifications.exit_code == 0
    assert "`uv run engineeringagent approach`" in overview.stdout
    assert "`uv run engineeringagent approach list`" in overview.stdout
    assert "`uv run engineeringagent approach <topic_id>`" in overview.stdout
    assert "`uv run engineeringagent schema feature.spec --format yaml`" in (
        specifications.stdout
    )
    assert "`uv run engineeringagent schema list`" in specifications.stdout
    assert "`uv run engineeringagent validate --schema-only`" in specifications.stdout


def test_local_approach_bootstrap_fixture_uses_repo_local_command_examples() -> None:
    bootstrap = Path("docs/fixtures/approach_bootstrap.md").read_text(encoding="utf-8")

    assert "`uv run engineeringagent ...`" in bootstrap
    assert "`uvx engineeringagent ...`" not in bootstrap


def test_main_unknown_approach_topic_is_helpful() -> None:
    result = _invoke_cli(["approach", "does-not-exist"])

    assert result.exit_code == 1
    assert "approach input error: unknown approach id or alias: does-not-exist" in result.stdout
    assert "engineeringagent approach list" in result.stdout


def test_fitness_command_is_rejected() -> None:
    result = _invoke_cli(["fitness", "run"])

    assert result.exit_code != 0
    assert "No such command 'fitness'" in (result.stderr or result.stdout)


def test_progress_commands_are_not_listed_in_root_help() -> None:
    result = _invoke_cli(["--help"])

    assert result.exit_code == 0
    assert "progress" not in result.stdout


@pytest.mark.parametrize(
    ("args", "expected_token"),
    [
        (["progress", "--help"], "No such command"),
        (["progress", "handoff-append"], "No such command"),
        (["progress", "feature-prune"], "No such command"),
    ],
)
def test_progress_commands_are_rejected(
    args: list[str],
    expected_token: str,
) -> None:
    result = _invoke_cli(args)

    assert result.exit_code != 0
    combined_output = (result.stderr or "") + (result.stdout or "")
    assert expected_token in combined_output
    assert "progress" in combined_output


def test_main_init_command_uses_typer_handler(monkeypatch: Any, tmp_path: Path) -> None:
    observed: dict[str, object] = {}

    def _fake_run_init_command(request: Any, _deps: Any) -> int:
        observed["project_root"] = str(request.project_root)
        observed["force"] = request.force
        observed["scaffold_profile"] = request.scaffold_profile
        observed["docs_mode"] = request.docs_mode
        observed["scaffold_docs_dir"] = request.scaffold_docs_dir
        return 0

    monkeypatch.setattr(
        cli_init_module,
        "_DEFAULT_INIT_WORKSPACE_RUNNER",
        _fake_run_init_command,
    )

    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "--force",
            "--scaffold-profile",
            "python_uv",
            "--docs-mode",
            "separate",
            "--scaffold-docs-dir",
            "docs.custom",
        ]
    )

    assert result.exit_code == 0
    assert observed == {
        "project_root": str(tmp_path.resolve()),
        "force": True,
        "scaffold_profile": "python_uv",
        "docs_mode": "separate",
        "scaffold_docs_dir": "docs.custom",
    }


def test_validate_allows_custom_agents_content(tmp_path: Path, capsys: Any) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "Custom user-owned guidance.",
                "No bootstrap template lines required.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    code = cli_module.cmd_validate(
        SimpleNamespace(project_root=str(tmp_path), schema_only=False)
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "AGENTS docs bootstrap contract" not in output


def test_cmd_validate_uses_validation_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    recorded: dict[str, object] = {}

    class _FakeValidationService:
        def run(self, request: Any) -> Any:
            recorded["project_root"] = str(request.project_root)
            recorded["schema_only"] = request.schema_only
            return SimpleNamespace(ok=True, messages=())

    class _FakeAppFactory:
        def __init__(self, project_root: Path) -> None:
            recorded["factory_project_root"] = str(project_root)

        def build_validation_service(self) -> Any:
            return _FakeValidationService()

    monkeypatch.setattr(
        cli_validate_module,
        "AppFactory",
        _FakeAppFactory,
    )

    code = cli_module.cmd_validate(
        SimpleNamespace(project_root=str(tmp_path), schema_only=True)
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "spec validation: ok" in output
    assert recorded == {
        "factory_project_root": str(tmp_path.resolve()),
        "project_root": str(tmp_path.resolve()),
        "schema_only": True,
    }


def test_cmd_schema_list_prints_registry_ids(
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    monkeypatch.setattr(
        cli_schema_module,
        "list_schema_ids",
        lambda: ("a.schema", "b.schema"),
    )

    code = cli_module.cmd_schema_list(SimpleNamespace(project_root="."))
    output = capsys.readouterr().out

    assert code == 0
    assert output == "a.schema\nb.schema\n"


def test_cmd_schema_prints_registry_schema_as_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    monkeypatch.setattr(
        cli_schema_module,
        "schema_from_registry",
        lambda _schema_id: {"z": {"a": 1}, "a": 1},
    )

    code = cli_module.cmd_schema(
        SimpleNamespace(project_root=".", schema_id="feature.spec")
    )
    output = capsys.readouterr().out

    assert code == 0
    payload = json.loads(output)
    assert payload == {"a": 1, "z": {"a": 1}}


def test_cmd_schema_prints_registry_schema_as_yaml(
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    monkeypatch.setattr(
        cli_schema_module,
        "schema_from_registry",
        lambda _schema_id: {"z": {"a": 1}, "a": 1},
    )

    code = cli_module.cmd_schema(
        SimpleNamespace(project_root=".", schema_id="feature.spec", output_format="yaml")
    )
    output = capsys.readouterr().out

    assert code == 0
    assert output == "a: 1\nz:\n  a: 1\n"


def test_cmd_schema_writes_to_output_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    monkeypatch.setattr(
        cli_schema_module,
        "schema_from_registry",
        lambda _schema_id: {"z": {"a": 1}, "a": 1},
    )

    code = cli_module.cmd_schema(
        SimpleNamespace(
            project_root=str(tmp_path),
            schema_id="feature.spec",
            output_format="json",
            output="artifacts/schema.json",
        )
    )
    output = capsys.readouterr().out

    assert code == 0
    assert output == "schema written: artifacts/schema.json\n"
    payload = json.loads(
        (tmp_path / "artifacts" / "schema.json").read_text(encoding="utf-8")
    )
    assert payload == {"a": 1, "z": {"a": 1}}


def test_cmd_schema_rejects_unknown_schema_id(
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    def _raise_unknown(_schema_id: str) -> dict[str, object]:
        raise cli_schema_module.UnknownSchemaIdError(
            "unknown schema id: missing; supported ids: feature.spec"
        )

    monkeypatch.setattr(cli_schema_module, "schema_from_registry", _raise_unknown)

    code = cli_module.cmd_schema(SimpleNamespace(project_root=".", schema_id="missing"))
    output = capsys.readouterr().out

    assert code == 1
    assert (
        output
        == "schema input error: unknown schema id: missing; "
        "supported ids: feature.spec\n"
    )


def test_cmd_schema_rejects_empty_schema_id(capsys: Any) -> None:
    code = cli_module.cmd_schema(SimpleNamespace(project_root=".", schema_id=" "))
    output = capsys.readouterr().out

    assert code == 1
    assert (
        output
        == "schema input error: provide a schema id or use "
        "`engineeringagent schema list`\n"
    )


def test_cmd_schema_rejects_invalid_output_format(capsys: Any) -> None:
    code = cli_module.cmd_schema(
        SimpleNamespace(project_root=".", schema_id="feature.spec", output_format="toml")
    )
    output = capsys.readouterr().out

    assert code == 1
    assert output == "schema input error: --format must be one of: json, yaml\n"


def test_cmd_workspace_reset_uses_workspace_recovery_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    recorded: dict[str, object] = {}

    class _FakeWorkspaceRecoveryService:
        def run(self, request: Any) -> Any:
            recorded["project_root"] = str(request.project_root)
            recorded["feature_id"] = request.feature_id
            recorded["last_accepted_commit"] = request.last_accepted_commit
            return SimpleNamespace(
                ok=True,
                message="workspace reset to last accepted commit abc123",
            )

    class _FakeAppFactory:
        def __init__(self, project_root: Path) -> None:
            recorded["factory_project_root"] = str(project_root)

        def build_workspace_recovery_service(self) -> Any:
            return _FakeWorkspaceRecoveryService()

    monkeypatch.setattr(
        cli_workspace_module,
        "AppFactory",
        _FakeAppFactory,
    )

    code = cli_module.cmd_workspace_reset(
        SimpleNamespace(
            project_root=str(tmp_path),
            feature_id="FEAT-100",
            last_accepted_commit="abc123",
        )
    )
    output = capsys.readouterr().out

    assert code == 0
    assert output == "workspace reset to last accepted commit abc123\n"
    assert recorded == {
        "factory_project_root": str(tmp_path.resolve()),
        "project_root": str(tmp_path.resolve()),
        "feature_id": "FEAT-100",
        "last_accepted_commit": "abc123",
    }


def test_workspace_reset_subcommand_routes_to_handler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}

    def _fake_cmd_workspace_reset(args: Any) -> int:
        recorded["project_root"] = args.project_root
        recorded["feature_id"] = args.feature_id
        recorded["last_accepted_commit"] = args.last_accepted_commit
        return 0

    monkeypatch.setattr(cli_module, "cmd_workspace_reset", _fake_cmd_workspace_reset)
    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "workspace",
            "reset",
            "FEAT-100",
            "--last-accepted-commit",
            "abc123",
        ]
    )

    assert result.exit_code == 0
    assert recorded == {
        "project_root": str(tmp_path),
        "feature_id": "FEAT-100",
        "last_accepted_commit": "abc123",
    }


def test_docs_root_resolver_defaults_to_docs(tmp_path: Path) -> None:
    assert resolve_docs_root(tmp_path) == tmp_path / "docs"


def test_docs_root_resolver_prefers_engineeringagent_toml(tmp_path: Path) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        'docs-root = "docs.engineeringagent"\n',
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent]\ndocs-root = "docs.from.pyproject"\n',
        encoding="utf-8",
    )

    assert resolve_docs_root(tmp_path) == tmp_path / "docs.engineeringagent"


def test_docs_root_resolver_reads_pyproject_tool_engineeringagent(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent]\ndocs-root = "docs.from.pyproject"\n',
        encoding="utf-8",
    )

    assert resolve_docs_root(tmp_path) == tmp_path / "docs.from.pyproject"
