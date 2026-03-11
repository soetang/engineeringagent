"""Port contracts for application-facing infrastructure seams."""

from engineeringagent.domain.audit import ProgressEvent
from engineeringagent.domain.quality import HarnessCheckPhase
from engineeringagent.domain.quality import ChecksRunResult

from .agent_runner import AgentRunRequest, AgentRunner
from .checks_catalog_repository import (
    ChecksCatalogRepository,
)
from .checks_runner import ChecksRunRequest, ChecksRunner
from .failures import ExecutionFailure, PortFailure, ValidationFailure, WorkspaceFailure
from .guidance_topic_repository import GuidanceTopicRepository
from .init_workspace import (
    BaselineScaffoldOptions,
    DEFAULT_AGENT_MODEL,
    InitWorkspaceDependencies,
)
from .progress_journal import ProgressJournal
from .prompt_definition_repository import (
    PromptDefinition,
    PromptDefinitionRepository,
    PromptInterpolation,
)
from .run_loop_executor import (
    RunLoopExecutionRequest,
    RunLoopExecutor,
)
from .repository_validator import (
    RepositoryValidationRequest,
    RepositoryValidationResult,
    RepositoryValidator,
)
from .shell_runner import CommandResult, ShellRunner
from .version_control import (
    CommitRequest,
    CommitResult,
    DiffSummary,
    ResetRequest,
    ResetResult,
    VersionControlFailure,
    VersionControlGateway,
    WorktreeStatus,
)

__all__ = [
    "AgentRunRequest",
    "AgentRunner",
    "BaselineScaffoldOptions",
    "CommitRequest",
    "CommitResult",
    "ChecksRunRequest",
    "ChecksRunResult",
    "ChecksCatalogRepository",
    "ChecksRunner",
    "CommandResult",
    "DEFAULT_AGENT_MODEL",
    "DiffSummary",
    "ExecutionFailure",
    "GuidanceTopicRepository",
    "HarnessCheckPhase",
    "InitWorkspaceDependencies",
    "PortFailure",
    "ProgressEvent",
    "ProgressJournal",
    "PromptDefinition",
    "PromptDefinitionRepository",
    "PromptInterpolation",
    "RunLoopExecutionRequest",
    "RunLoopExecutor",
    "ResetRequest",
    "ResetResult",
    "RepositoryValidationRequest",
    "RepositoryValidationResult",
    "RepositoryValidator",
    "ShellRunner",
    "ValidationFailure",
    "VersionControlFailure",
    "VersionControlGateway",
    "WorktreeStatus",
    "WorkspaceFailure",
]
