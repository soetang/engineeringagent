from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.checks.validate.contracts import ValidationContext, ValidationIssue
from engineeringagent.checks.validate.repo_architecture_validator import (
    RepoArchitectureValidator,
)


def _write_port_module(project_root: Path, relative_path: str, body: str) -> None:
    module_path = project_root / relative_path
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text(body, encoding="utf-8")


def test_repo_architecture_validator_accepts_ports_modules_with_protocol_contracts(
    tmp_path: Path,
) -> None:
    """Ports modules stay valid when they declare at least one Protocol contract."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/ports/agent_runner.py",
        "from typing import Protocol\n\nclass AgentRunner(Protocol):\n    pass\n",
    )
    _write_port_module(
        tmp_path,
        "src/engineeringagent/ports/repository_validator.py",
        "from typing import Protocol\n\nclass RepositoryValidator(Protocol):\n    pass\n",
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == ()


def test_repo_architecture_validator_reports_ports_modules_without_protocol_contracts(
    tmp_path: Path,
) -> None:
    """Ports modules without Protocol contracts should fail architecture validation."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/ports/agent_runner.py",
        "class AgentRunRequest:\n    pass\n",
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/ports/agent_runner.py",
            message="ports modules must declare at least one Protocol contract",
            code="repo.architecture.ports-protocol-contract",
        ),
    )


def test_repo_architecture_validator_reports_ports_parse_failures(tmp_path: Path) -> None:
    """Syntax errors in ports modules should surface as deterministic repo issues."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/ports/agent_runner.py",
        "class Broken(:\n    pass\n",
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/ports/agent_runner.py",
            message="failed to parse ports module: invalid syntax",
            code="repo.architecture.parse-failure",
        ),
    )


def test_repo_architecture_validator_reports_ports_importing_application_modules(
    tmp_path: Path,
) -> None:
    """Ports modules must not import application-layer modules."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/ports/prompt_contracts.py",
        "from typing import Protocol\n"
        "from engineeringagent.application.prompt_builder import ImplementationPromptRequest\n\n"
        "class PromptBuilder(Protocol):\n"
        "    def build(self, request: ImplementationPromptRequest) -> str: ...\n",
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/ports/prompt_contracts.py",
            message="ports modules must not import application modules",
            code="repo.architecture.ports-application-import",
        ),
    )


def test_repo_architecture_validator_reports_application_protocol_contracts(
    tmp_path: Path,
) -> None:
    """Application-layer Protocols should be rejected by repo architecture validation."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/application/checks_service.py",
        "from typing import Protocol\n\nclass ChecksPort(Protocol):\n    pass\n",
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/application/checks_service.py",
            message="application modules must not declare Protocol contracts",
            code="repo.architecture.application-protocol-contract",
        ),
    )


def test_repo_architecture_validator_reports_application_importing_checks_modules(
    tmp_path: Path,
) -> None:
    """Application modules must stay off the concrete checks package surface."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/application/checks_service.py",
        "from engineeringagent.checks.runtime import run\n",
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/application/checks_service.py",
            message="application modules must not import checks modules",
            code="repo.architecture.application-checks-import",
        ),
    )


def test_repo_architecture_validator_reports_application_importing_legacy_prompts(
    tmp_path: Path,
) -> None:
    """Application modules must not depend on legacy top-level prompt modules."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/application/prompt_builder.py",
        "from engineeringagent.prompts.feedback_envelope import parse_feedback_envelope\n",
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/application/prompt_builder.py",
            message="application modules must not import legacy top-level prompts modules",
            code="repo.architecture.application-legacy-prompts-import",
        ),
    )


@pytest.mark.parametrize(
    "import_line",
    [
        "from engineeringagent.adapters.progress import FilesystemProgressJournal\n",
        "from engineeringagent.agents.runtime import run_agent\n",
        "from engineeringagent.bootstrap.app_factory import AppFactory\n",
        "from engineeringagent.cli.app import create_cli\n",
        "from engineeringagent.presentation.presenters.terminal import TerminalPresenter\n",
    ],
)
def test_repo_architecture_validator_reports_application_importing_outer_layers(
    tmp_path: Path,
    *,
    import_line: str,
) -> None:
    """Application modules must depend on ports and domain, not outer layers."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/application/checks_service.py",
        import_line,
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/application/checks_service.py",
            message=(
                "application modules must not import adapters, agents, bootstrap, "
                "cli, or presentation modules"
            ),
            code="repo.architecture.application-outer-layer-import",
        ),
    )


@pytest.mark.parametrize(
    "import_line",
    [
        "from engineeringagent.application.checks_service import ChecksService\n",
        "from engineeringagent.ports.agent_runner import AgentRunner\n",
        "from engineeringagent.adapters.progress import FilesystemProgressJournal\n",
        "from engineeringagent.presentation.presenters.terminal import RunOutputPresenter\n",
        "from engineeringagent.bootstrap.app_factory import AppFactory\n",
        "from engineeringagent.specs import BundledFeatureSpec\n",
    ],
)
def test_repo_architecture_validator_reports_domain_importing_forbidden_layers(
    tmp_path: Path,
    *,
    import_line: str,
) -> None:
    """Domain modules must stay isolated from outer-layer implementation modules."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/domain/specification/progress.py",
        import_line,
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/domain/specification/progress.py",
            message=(
                "domain modules must not import application, ports, adapters, "
                "presentation, bootstrap, or legacy specs modules"
            ),
            code="repo.architecture.domain-import",
        ),
    )


def test_repo_architecture_validator_reports_ports_importing_init_scaffold_modules(
    tmp_path: Path,
) -> None:
    """Ports must not reach through to the init scaffold implementation surface."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/ports/init_workspace.py",
        "from typing import Protocol\n"
        "from engineeringagent.init_scaffold import scaffold\n\n"
        "class InitWorkspace(Protocol):\n"
        "    def run(self) -> None: ...\n",
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/ports/init_workspace.py",
            message="application and ports modules must not import init_scaffold modules",
            code="repo.architecture.init-scaffold-import",
        ),
    )


def test_repo_architecture_validator_reports_deleted_legacy_module_paths(
    tmp_path: Path,
) -> None:
    """Deleted legacy module paths should surface as deterministic architecture issues."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/validator.py",
        "value = 1\n",
    )
    _write_port_module(
        tmp_path,
        "src/engineeringagent/git/client.py",
        "value = 1\n",
    )
    _write_port_module(
        tmp_path,
        "src/engineeringagent/ports/prompt_builder.py",
        "value = 1\n",
    )
    _write_port_module(
        tmp_path,
        "src/engineeringagent/prompts/feedback_envelope.py",
        "value = 1\n",
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/git/client.py",
            message="deleted legacy module path must remain absent",
            code="repo.architecture.deleted-path",
        ),
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/ports/prompt_builder.py",
            message="deleted legacy module path must remain absent",
            code="repo.architecture.deleted-path",
        ),
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/prompts/feedback_envelope.py",
            message="deleted legacy module path must remain absent",
            code="repo.architecture.deleted-path",
        ),
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/validator.py",
            message="deleted legacy module path must remain absent",
            code="repo.architecture.deleted-path",
        ),
    )


def test_repo_architecture_validator_reports_legacy_imports_in_production_modules(
    tmp_path: Path,
) -> None:
    """Production modules must not import removed legacy git or progress surfaces."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/adapters/progress/filesystem_journal.py",
        "from engineeringagent import progress_logging\n"
        "import engineeringagent.git.client\n",
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/adapters/progress/filesystem_journal.py",
            message="production modules must not import deleted legacy member engineeringagent.progress_logging",
            code="repo.architecture.legacy-import",
        ),
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/adapters/progress/filesystem_journal.py",
            message="production modules must not import deleted legacy module engineeringagent.git.client",
            code="repo.architecture.legacy-import",
        ),
    )


def test_repo_architecture_validator_reports_start_agent_imports_outside_opencode_backend(
    tmp_path: Path,
) -> None:
    """Only the opencode backend adapter may import the raw start_agent helper."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/adapters/agents/configured_agent_runner.py",
        "from engineeringagent.agents.backends.opencode.client import start_agent\n",
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/adapters/agents/configured_agent_runner.py",
            message=(
                "production modules must not import start_agent outside the "
                "opencode backend adapter"
            ),
            code="repo.architecture.start-agent-boundary",
        ),
    )


def test_repo_architecture_validator_reports_start_agent_calls_outside_opencode_backend(
    tmp_path: Path,
) -> None:
    """Direct start_agent calls should stay inside the opencode backend adapter."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/loop.py",
        "def run() -> None:\n    start_agent('prompt')\n",
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/loop.py",
            message=(
                "production modules must not call start_agent outside the "
                "opencode backend adapter"
            ),
            code="repo.architecture.start-agent-boundary",
        ),
    )


def test_repo_architecture_validator_reports_json_format_calls_outside_agents(
    tmp_path: Path,
) -> None:
    """Structured backend format flags stay behind the agents boundary."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/application/checks_service.py",
        "def run() -> None:\n    execute(format='json')\n",
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/application/checks_service.py",
            message='production modules must not pass format="json" outside agents modules',
            code="repo.architecture.json-format-boundary",
        ),
    )


def test_repo_architecture_validator_reports_configured_agent_runner_imports_outside_allowed_layers(
    tmp_path: Path,
) -> None:
    """ConfiguredAgentRunner imports stay in bootstrap wiring or agent adapters."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/config.py",
        "from engineeringagent.adapters.agents import ConfiguredAgentRunner\n",
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/config.py",
            message=(
                "production modules must not import ConfiguredAgentRunner "
                "outside bootstrap or adapters.agents"
            ),
            code="repo.architecture.configured-agent-runner-boundary",
        ),
    )


def test_repo_architecture_validator_reports_loop_runtime_importing_bootstrap(
    tmp_path: Path,
) -> None:
    """Loop runtime wiring must not compose services through bootstrap."""

    _write_port_module(
        tmp_path,
        "src/engineeringagent/loop_runtime/selection.py",
        "from engineeringagent.bootstrap.app_factory import AppFactory\n",
    )

    issues = RepoArchitectureValidator().validate(
        context=ValidationContext(
            project_root=tmp_path,
            docs_root=tmp_path / "docs",
            schema_only=False,
        )
    )

    assert issues == (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path="src/engineeringagent/loop_runtime/selection.py",
            message="loop runtime modules must not import bootstrap modules",
            code="repo.architecture.loop-runtime-bootstrap-import",
        ),
    )
