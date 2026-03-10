# Ports, Adapters, and Presentation

## Purpose

Define the ports, adapters, and presentation layers around the domains and application services.

## Ports

All ports should be implemented as Python `Protocol` interfaces.
Use structural typing so adapters and test doubles can satisfy a port without inheritance-heavy hierarchies.
Prefer `typing.Protocol`; use `typing_extensions.Protocol` only when compatibility requires it.

### Work definition ports

- `FeatureSpecificationRepository`

Loads and persists feature specifications, plans, and completion state.

### Quality ports

- `ChecksCatalogRepository`

Loads declared quality policy and related metadata.

### Guidance ports

- `GuidanceTopicRepository`

Loads discoverable guidance topics.

### Prompt ports

- `PromptDefinitionRepository`

Loads Python-authored prompt definitions and their declared interpolation contracts.

### Execution ports

- `AgentRunner`
- `ShellRunner`
- `VersionControlGateway`

Drive external execution without leaking vendor behavior into application services.

### Workspace ports

- `FeatureWorkspaceManager`

Creates, refreshes, and cleans isolated worktrees and branches for active feature specifications.

### Audit ports

- `ProgressJournal`
- `Clock`

Support tracing, timestamps, and audit history.

## Adapters

### Document adapters

- filesystem-backed feature specification repository
- filesystem-backed checks catalog repository
- filesystem-backed guidance topic repository

### Prompt adapters

- filesystem-backed prompt definition repository

Default repository layout:

- repository configuration: `engineeringagent.toml`
- active features: `docs/specifications/features/`
- completed features: `docs/specifications/features_done/`
- checks catalog: `harness/checks.yaml`
- guidance topics: packaged markdown or repository docs
- prompt definitions: `harness/prompts/`

### Agent adapters

- `CodexConnector`
- `OpenCodeConnector`

Both implement the same `AgentRunner` port.
Text and structured output flow through one canonical request path.
Structured results should be validated against Python models rather than parsed ad hoc in application code.

### Repository adapters

- `GitCliGateway`
- `GitWorktreeManager`
- `SubprocessShellRunner`
- `FilesystemProgressJournal`

These adapters own subprocess invocation, diff collection, branch and worktree lifecycle, commit operations, and progress persistence.

The authoritative repository state still belongs to the version-control and workspace adapters.

Future remote execution may add an optional execution-target facade.
That extension is described in `11-execution-targets-and-remote-runs.md`, but it is not required for v1.

## Presentation Layer

### CLI presentation

Commands include:

- `run`
- `checks`
- `validate`
- `init`
- `workspace`
- `guidance`
- `schema`

`workspace` should expose operational actions such as `reset`, but handoff itself is not a CLI surface.

CLI responsibilities:

- parse arguments
- build workflow requests
- invoke application services through the bootstrap layer
- support dry-run inspection of prompt definitions and declared interpolations
- choose presenters
- set exit codes

### Presenter presentation

Presenters render typed results into:

- terminal summaries
- prompt feedback text
- markdown handoff documents
- JSON schema output
- guidance listings and topic content

## Boundary Rules

- adapters do not own application sequencing
- adapters map external failures into typed product errors
- presentation does not own feature-selection or quality policy
- presentation may compose output, but not mutate application state

## Adapter Design Rules

- one adapter implements one port family
- retry logic belongs in the adapter only when it is vendor-specific
- repository-global policy belongs in application services, not in adapters
- adapters should prefer stable request and result objects over positional helper calls

Canonical Protocol signatures live in `14-port-contracts.md`.

## Why This Split Matters

This keeps domain and application policy stable while allowing independent change in:

- backend vendors
- storage format details
- terminal presentation style
- schema-export format
- repository automation strategy
