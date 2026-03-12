"""Port contracts for application-facing infrastructure seams."""

from engineeringagent.domain.audit import ProgressEvent
from engineeringagent.domain.quality import HarnessCheckPhase
from engineeringagent.domain.quality import ChecksRunResult

from .agent_backend import (
    AgentBackend,
    AgentBackendError,
    AgentBackendFailureDetails,
    AgentBackendRunResult,
    AgentOutputValidationError,
    RequestRunAgentBackend,
)
from .agent_runner import AgentRunRequest, AgentRunner
from .checks_catalog_repository import (
    ChecksCatalogRepository,
)
from .checks_runner import ChecksRunRequest, ChecksRunner
from .clock import Clock
from .configuration_provider import ConfigurationProvider
from .feature_workspace_manager import (
    FeatureWorkspaceFailure,
    FeatureWorkspaceManager,
    WorkspaceState,
    WorkspaceResetRequest,
    WorkspaceResetResult,
)
from .feature_specification_repository import FeatureSpecificationRepository
from .failures import ExecutionFailure, PortFailure, ValidationFailure, WorkspaceFailure
from .guidance_topic_repository import GuidanceTopicRepository
from .init_workspace import (
    BaselineScaffoldOptions,
    DEFAULT_AGENT_MODEL,
    InitWorkspaceDependencies,
)
from .progress_journal import ProgressJournal
from .prompt_definition_repository import PromptDefinitionRepository
from .run_loop_executor import RunLoopExecutionRequest, RunLoopExecutor
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
    VersionControlFailure,
    VersionControlGateway,
    WorktreeStatus,
)

__all__ = [
    "AgentRunRequest",
    "AgentRunner",
    "AgentBackend",
    "AgentBackendError",
    "AgentBackendFailureDetails",
    "AgentBackendRunResult",
    "AgentOutputValidationError",
    "BaselineScaffoldOptions",
    "CommitRequest",
    "CommitResult",
    "ChecksRunRequest",
    "ChecksRunResult",
    "ChecksCatalogRepository",
    "ChecksRunner",
    "Clock",
    "CommandResult",
    "ConfigurationProvider",
    "DEFAULT_AGENT_MODEL",
    "DiffSummary",
    "ExecutionFailure",
    "FeatureWorkspaceFailure",
    "FeatureWorkspaceManager",
    "FeatureSpecificationRepository",
    "GuidanceTopicRepository",
    "HarnessCheckPhase",
    "InitWorkspaceDependencies",
    "PortFailure",
    "ProgressEvent",
    "ProgressJournal",
    "PromptDefinitionRepository",
    "RequestRunAgentBackend",
    "RunLoopExecutionRequest",
    "RunLoopExecutor",
    "RepositoryValidationRequest",
    "RepositoryValidationResult",
    "RepositoryValidator",
    "ShellRunner",
    "ValidationFailure",
    "VersionControlFailure",
    "VersionControlGateway",
    "WorkspaceState",
    "WorkspaceResetRequest",
    "WorkspaceResetResult",
    "WorktreeStatus",
    "WorkspaceFailure",
]
