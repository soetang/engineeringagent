"""Port contracts for application-facing infrastructure seams."""

from engineeringagent.domain.quality import HarnessCheckPhase
from engineeringagent.domain.quality import ChecksRunResult

from .agent_runner import AgentRunRequest, AgentRunner
from .checks_runner import ChecksRunRequest, ChecksRunner
from .guidance_topic_repository import GuidanceTopicRepository
from .init_workspace import (
    BaselineScaffoldOptions,
    DEFAULT_AGENT_MODEL,
    InitWorkspaceDependencies,
)
from .progress_journal import ProgressJournal
from .prompt_builder import (
    ImplementationPromptFeature,
    ImplementationPromptRequest,
    PromptArtifactPaths,
    PromptBuilder,
    PromptProgressKind,
)
from .prompt_definition_repository import (
    PromptDefinition,
    PromptDefinitionRepository,
    PromptInterpolation,
)
from .repository_validator import (
    RepositoryValidationRequest,
    RepositoryValidationResult,
    RepositoryValidator,
)
from .version_control import (
    CommitRequest,
    CommitResult,
    DiffSummary,
    VersionControlFailure,
    VersionControlGateway,
)

__all__ = [
    "AgentRunRequest",
    "AgentRunner",
    "BaselineScaffoldOptions",
    "CommitRequest",
    "CommitResult",
    "ChecksRunRequest",
    "ChecksRunResult",
    "ChecksRunner",
    "DEFAULT_AGENT_MODEL",
    "DiffSummary",
    "GuidanceTopicRepository",
    "HarnessCheckPhase",
    "ImplementationPromptFeature",
    "ImplementationPromptRequest",
    "InitWorkspaceDependencies",
    "PromptArtifactPaths",
    "ProgressJournal",
    "PromptBuilder",
    "PromptDefinition",
    "PromptDefinitionRepository",
    "PromptInterpolation",
    "PromptProgressKind",
    "RepositoryValidationRequest",
    "RepositoryValidationResult",
    "RepositoryValidator",
    "VersionControlFailure",
    "VersionControlGateway",
]
