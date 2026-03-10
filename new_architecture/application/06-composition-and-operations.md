# Composition and Operations

## Purpose

Define how the product is assembled at runtime and how one execution loop behaves under success and failure.

## Bootstrap Layer

`bootstrap/app_factory.py` is the composition root.
It is the only place allowed to import across all layers in order to wire the runtime.

Bootstrap responsibilities:

- load repository configuration
- apply configuration precedence and defaults
- select concrete adapters
- register check strategies
- register available agent adapters
- build application services
- expose ready-to-run CLI application services

Effective-config load algorithm:

1. start from built-in defaults
2. if `engineeringagent.toml` or `engineeringagent.local.toml` exists, load only the dedicated files in order `engineeringagent.toml` then `engineeringagent.local.toml`
3. otherwise, load `[tool.engineeringagent]` from `pyproject.toml` when present
4. apply CLI flags last

## Runtime Bootstrap Example

```text
AppFactory
  -> RepositoryConfig = load effective merged config
  -> FeatureSpecificationRepository = FilesystemFeatureSpecificationRepository
  -> ChecksCatalogRepository = FilesystemChecksCatalogRepository
  -> GuidanceTopicRepository = FilesystemGuidanceTopicRepository
  -> PromptDefinitionRepository = FilesystemPromptDefinitionRepository
  -> AgentRunner = CodexConnector | OpenCodeConnector
  -> ShellRunner = SubprocessShellRunner
  -> VersionControlGateway = GitCliGateway
  -> FeatureWorkspaceManager = GitWorktreeManager
  -> ProgressJournal = FilesystemProgressJournal
  -> PromptBuilder
  -> RunLoopService
  -> FeatureIterationService
  -> ChecksService
  -> ValidationService
  -> WorkspaceRecoveryService
```

## Run Sequence

V1 runs against the local isolated feature workspace.
Remote execution is a future optional mode documented separately.

### Startup

1. load configuration
2. build the adapter set
3. validate startup assumptions
4. resolve eligible feature specifications
5. start the run loop

### One Feature Iteration

1. select the next eligible feature specification
2. acquire or refresh the isolated feature workspace and branch
3. load feature and plan state inside the authoritative workspace
4. run blocking startup validation for selected specifications plus global harness rules
5. if the selected specification is `ready`, write provisional `active` status in the workspace; if it is already `active`, continue; otherwise stop with a blocked result to be finalized through report and handoff emission
6. render the implementation prompt from the selected prompt definition and interpolation contract, including the latest persisted `handoff.md` path when one exists
7. run the implementation step through `AgentRunner`
8. reload state from source documents
9. determine whether completion conditions appear satisfied
10. run validation, verification, and checks inside the feature workspace
11. run `feature_done` check groups against the diff from the configured integration branch when completion policy requires them
12. if completion is confirmed, prepare `done` and archive changes inside the feature workspace
13. create one accepted-iteration commit containing both implementation changes and any completion-state updates
14. finalize the outcome by appending progress events, writing one iteration report, and writing handoff when the feature remains unarchived
15. return the iteration report to the presentation layer

## Failure and Rollback Policy

| Step | Failure effect | Automatic rollback |
| --- | --- | --- |
| feature load | stop the iteration before side effects | none |
| workspace acquisition | stop the iteration before implementation begins | best-effort cleanup of newly created workspace |
| implement step | stop the iteration, preserve dirty workspace for inspection, and store retry feedback | none |
| validation, verification, or runtime checks | stop the iteration, preserve dirty workspace for inspection, and keep only provisional workspace-local status changes | none |
| feature_done checks | stop the iteration, preserve dirty workspace for inspection, and keep only provisional workspace-local status changes | none |
| prepare completion-state updates | keep the workspace dirty but do not persist completion state | none |
| iteration commit | keep the workspace dirty and do not treat the feature as completed until commit succeeds | none |

The system only rolls back state transitions it owns directly.
It does not silently discard repository edits produced during implementation or checks.
Completion state becomes authoritative only when the accepted-iteration commit succeeds.
V1 does not auto-resume from a dirty failed workspace; the next iteration is blocked until the workspace is explicitly cleaned or reset.
Iteration finalization still appends progress events and writes one machine-readable report for every outcome.
It also writes `handoff.md` whenever the feature remains unarchived, including failed, blocked, and no-op iterations.

## Operational Guarantees

- one iteration produces one structured report
- progress journals are append-only
- feature state is reloaded from source documents after implementation
- the loop can restart from documents and journals without hidden memory
- backend-specific behavior stays behind adapter boundaries
- the authoritative branch state remains identifiable throughout local iteration work

## Observability Model

Every major application service emits:

- result objects for test and automation use
- prompt-ready feedback for retry loops
- progress events for operational traceability

Presenters may derive summaries from these outputs, but the outputs themselves remain the stable contract.

## Design Goal

The system is operationally healthy when a failed iteration is explainable from:

1. source documents
2. one iteration report
3. append-only progress events

No hidden terminal-only state should be required.
