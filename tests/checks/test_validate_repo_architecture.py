from __future__ import annotations

from pathlib import Path

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
        "src/engineeringagent/ports/prompt_builder.py",
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
            path="src/engineeringagent/ports/prompt_builder.py",
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
