# Application Services

## Purpose

Describe the application layer that turns domain objects into repository-changing behavior.

## Service Set

### RunLoopService

Owns the long-running control loop:

- resolve eligible targets
- enforce repository preconditions
- select the next feature specification
- carry retry feedback across iterations
- stop on limits or terminal failure

### FeatureIterationService

Owns one feature attempt:

- load feature and plan state
- load the selected feature specification and its plan state
- prepare implementation input
- run the implementation agent
- reload source documents
- determine whether the specification is a completion candidate
- trigger validation, verification, checks, and review while the specification is still active
- record confirmed completion when applicable, archive when done, and create the accepted-iteration commit
- finalize every outcome by appending progress events and writing one structured iteration report
- write handoff artifacts for internal carryover whenever the final feature state remains unarchived

### ChecksService

Owns deterministic planning and execution of declared checks for one phase.
It returns a stable result that the run loop can consume without branching on check type.

### ValidationService

Owns static repository validation.
It runs side-effect-free validators over documents and configuration.

### InitWorkspaceService

Owns repository setup:

- scaffold baseline files
- select default adapter configuration
- write initial product configuration
- install optional helper automation

### WorkspaceRecoveryService

Owns deterministic reset of a failed feature workspace back to the last accepted iteration commit and explicit continuity validation against the persisted handoff artifact.

### GuidanceService

Owns topic discovery and topic rendering for operator guidance.

### PromptBuilder

Owns prompt-template selection, interpolation policy, and deterministic prompt rendering.
It should work with Python-authored prompt definitions that expose typed input and output models.
When a persisted handoff artifact exists, it should pass the handoff file path to the next iteration agent.

## Workflow Contracts

Each workflow has its own request and result objects:

- `RunLoopRequest` / `RunLoopResult`
- `FeatureIterationRequest` / `IterationReport`
- `RunChecksRequest` / `ChecksResult`
- `ValidateRepositoryRequest` / `ValidationResult`
- `InitWorkspaceRequest` / `InitWorkspaceResult`
- `RecoverWorkspaceRequest` / `RecoverWorkspaceResult`
- `GuidanceQuery` / `GuidanceResult`

These are application contracts, not presentation models.

## Authoring Prerequisite

`FeatureIterationService` starts only after the artifact flow has reached an executable state:

- specification
- research when required
- plan when required
- `ready` or `active` status before implementation begins

## One Iteration Sequence

1. load the selected feature specification
2. acquire or refresh the isolated feature workspace
3. resolve the active plan phase, if any
4. run blocking startup validation for selected specifications plus global harness rules
5. if the selected specification is `ready`, write provisional `active` status in the workspace; if it is already `active`, continue; otherwise stop with a blocked result to be finalized through report and handoff emission
6. derive implementation instructions, including `ProgressJournal.latest_handoff_path(feature_id)` when one exists, and build the prompt
7. invoke the implementation agent through `AgentRunner`
8. reload feature state from the source documents
9. determine whether completion conditions appear satisfied
10. derive verification commands only from plan units whose `done` transition will be persisted by this accepted iteration and normalize them into generated command checks
11. run those generated checks through the same quality pipeline as catalog checks
12. run `feature_done` check groups when completion policy requires them, including reviewer checks when configured
13. if completion is confirmed, prepare `done` and archive changes inside the feature workspace
14. create one accepted-iteration commit containing both implementation changes and any completion-state updates
15. finalize the outcome by appending progress events, writing one iteration report, writing handoff when the feature remains unarchived, and returning an `IterationReport`

## Ports Used by Application Services

- `FeatureSpecificationRepository`
- `ChecksCatalogRepository`
- `GuidanceTopicRepository`
- `PromptDefinitionRepository`
- `AgentRunner`
- `ShellRunner`
- `VersionControlGateway`
- `FeatureWorkspaceManager`
- `ProgressJournal`
- `Clock`

## Boundary Rules

- application services do not print
- application services do not parse raw YAML or markdown
- application services do not import adapter-specific code
- application services do not know how terminal output is formatted
- application services may assemble strategies, but they do not implement vendor side effects

## Events and Feedback

Application services should return both structured status and concise operator feedback:

- machine-readable result objects for automation and tests
- prompt-ready feedback strings for retry loops
- progress events for audit-friendly journaling

This keeps the system explainable without leaking presentation concerns into domain logic.

## Prompt Assembly Rule

- application services decide which facts are needed for the current step
- `PromptBuilder` renders only declared interpolations
- file-derived values default to path-only rendering
- file content is included only when the prompt definition explicitly asks for excerpts or full content

## Service Collaboration

```text
RunLoopService
  -> FeatureIterationService
  -> ValidationService

FeatureIterationService
  -> ChecksService
  -> PromptBuilder
  -> AgentRunner
  -> FeatureSpecificationRepository
  -> VersionControlGateway
  -> FeatureWorkspaceManager
  -> ProgressJournal
```

## Design Goal

This layer is successful when every major service can be tested with fake ports and in-memory repositories, while keeping the sequencing rules identical to production.
