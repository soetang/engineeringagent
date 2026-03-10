# Port Contracts

## Purpose

Define the canonical Protocol signatures that make the architecture implementation-ready.

## Rules

- all ports are Python `Protocol` contracts
- v1 ports are synchronous at the application boundary
- adapters may use async internally, but expose synchronous methods unless the product requires otherwise
- expected outcomes return typed result objects
- external or infrastructure failures raise typed `PortFailure` exceptions
- v1 execution flows through `AgentRunner` for model calls and `ShellRunner` for commands

## Common Domain Types

```python
class FeatureSpecification: ...


class FeatureSelectionCandidate:
    feature_id: str
    status: str
    priority: str
    planning_mode: str
    next_phase_id: str | None
    phase_dependencies_satisfied: bool
    block_reason_code: str | None


class ChecksCatalog: ...


class GuidanceTopic: ...


class ProgressEvent: ...


class RepositoryConfig: ...
```

## Common Prompt Types

```python
from pydantic import BaseModel


class PromptInterpolation(BaseModel):
    name: str
    source: str
    required: bool
    render_as: str
    content_policy: str
    content_bound: dict | None
    rationale: str


class PromptDefinition(BaseModel):
    prompt_id: str
    purpose: str
    target: str
    output_mode: str
    token_budget_hint: int
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    interpolations: list[PromptInterpolation]

    def render(self, data: BaseModel) -> str: ...
```

## Common Failure Envelope

```python
class PortFailure(Exception):
    port_name: str
    message: str


class ValidationFailure(PortFailure):
    pass


class ExecutionFailure(PortFailure):
    pass


class WorkspaceFailure(PortFailure):
    pass


class VersionControlFailure(PortFailure):
    pass
```

## PromptDefinitionRepository

```python
from typing import Protocol


class PromptDefinitionRepository(Protocol):
    def get(self, prompt_id: str) -> PromptDefinition: ...
    def list_ids(self) -> list[str]: ...
```

## ConfigurationProvider

```python
class ConfigurationProvider(Protocol):
    def load(self) -> RepositoryConfig: ...
```

## AgentRunner

```python
from typing import Generic, Protocol, TypeVar


T = TypeVar("T", bound=BaseModel)


class AgentRunRequest(Generic[T]):
    prompt: str
    output_model: type[T]
    backend_id: str
    model_id: str
    workspace_path: str


class AgentRunResult(Generic[T]):
    raw_text: str
    structured_output: T


class AgentRunner(Protocol):
    def run(self, request: AgentRunRequest[T]) -> AgentRunResult[T]: ...
```

This is the single canonical LLM execution seam for v1.

## ShellRunner

```python
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str


class ShellRunner(Protocol):
    def run(self, workspace_path: str, command: list[str]) -> CommandResult: ...
```

## FeatureWorkspaceManager

```python
class WorkspaceHandle:
    feature_id: str
    branch_name: str
    workspace_path: str


class WorkspaceState:
    clean: bool
    changed_paths: list[str]
    has_untracked_files: bool


class FeatureWorkspaceManager(Protocol):
    def acquire(self, feature_id: str, integration_branch: str) -> WorkspaceHandle: ...
    def get_state(self, handle: WorkspaceHandle) -> WorkspaceState: ...
    def reset_to_last_accepted(self, handle: WorkspaceHandle) -> None: ...
    def cleanup(self, handle: WorkspaceHandle) -> None: ...
```

## VersionControlGateway

```python
class CommitRequest:
    workspace_path: str
    message: str
    stage_all: bool
    allow_empty: bool


class CommitResult:
    commit_created: bool
    commit_sha: str | None


class DiffSummary:
    base_branch: str
    changed_paths: list[str]
    summary_text: str


class VersionControlGateway(Protocol):
    def diff_against_base(self, workspace_path: str, base_branch: str) -> DiffSummary: ...
    def head_commit(self, workspace_path: str) -> str | None: ...
    def commit(self, request: CommitRequest) -> CommitResult: ...
```

V1 must call `commit()` with `stage_all=True` and `allow_empty=False`.
If `commit_created` is `False`, the harness must not persist `done` or `archived` state transitions.

## FeatureSpecificationRepository

```python
class FeatureSpecificationRepository(Protocol):
    def list_selection_candidates(self) -> list[FeatureSelectionCandidate]: ...
    def load(self, workspace_path: str, feature_id: str) -> FeatureSpecification: ...
    def save(self, workspace_path: str, feature_id: str, specification: FeatureSpecification) -> None: ...
    def archive(self, workspace_path: str, feature_id: str) -> None: ...
```

`save()` and `archive()` mutate files only inside the isolated feature workspace.
They do not become authoritative product state until the accepted-iteration commit succeeds.
The same provisional rule applies to all spec and plan status mutations, including `ready -> active` and phase-state updates.

## ChecksCatalogRepository

```python
class ChecksCatalogRepository(Protocol):
    def load(self) -> ChecksCatalog: ...
```

`ChecksCatalog` includes resolved reviewer definitions and fitness-manifest metadata in v1.

## GuidanceTopicRepository

```python
class GuidanceTopicRepository(Protocol):
    def list_topics(self) -> list[str]: ...
    def load(self, topic_id: str) -> GuidanceTopic: ...
```

## ProgressJournal

```python
class ProgressJournal(Protocol):
    def append(self, event: ProgressEvent) -> None: ...
    def write_iteration_report(self, feature_id: str, report: object) -> str: ...
    def write_handoff(self, feature_id: str, handoff_markdown: str) -> str: ...
    def latest_iteration_report_path(self, feature_id: str) -> str | None: ...
    def latest_handoff_path(self, feature_id: str) -> str | None: ...
```

`write_iteration_report()` is called for every finalized iteration outcome.
`write_handoff()` is called whenever the feature remains unarchived after finalization.
`latest_handoff_path()` is the canonical way for the run loop to pass the persisted handoff file path into `PromptBuilder` for the next iteration.

## Clock

```python
class Clock(Protocol):
    def now_iso8601(self) -> str: ...
```

## Optional Post-v1 Remote Extension

If remote execution is introduced later, add a separate `ExecutionTarget` Protocol as an orchestration facade over `AgentRunner` and `ShellRunner`.
That extension should not change the v1 application-service contracts.

## Design Goal

These signatures are intentionally small but concrete.
They give an iterative implementation loop enough shape to build adapters, tests, and application services without inventing the contracts mid-flight.
