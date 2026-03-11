# EngineeringAgent Product Architecture

This directory defines EngineeringAgent as a new product built from scratch.
It assumes no legacy package structure and no obligation to preserve today's internal coupling.

## Product Goal

EngineeringAgent turns a repository into a specification-first delivery system:

- operators describe work as structured feature specifications
- the system selects one small unit of work
- an implementation agent executes that unit
- deterministic checks and optional reviewers validate the result
- progress is recorded as durable operational evidence

## System Actors

- `operator`: sets priorities, writes specifications, and reviews outcomes
- `workspace`: the repository being changed
- `agent backend`: the implementation or reviewer engine
- `quality system`: validation, checks, fitness rules, and reviewer policies
- `progress journal`: append-only operational history

## Architectural Shape

EngineeringAgent uses a ports-and-adapters architecture with multiple domains.
The key is not avoiding the words `domain`, `ports`, or `adapters`.
The key is making each domain's job obvious.

## Domain Map

- `specification domain`: feature specifications, plans, priorities, status, and acceptance
- `quality domain`: checks, validation rules, fitness policies, reviewer policies, and quality results
- `guidance domain`: operator-facing topics and stable topic identifiers
- `audit domain`: progress events and operational records
- `shared kernel`: identifiers, enums, and small value objects shared across domains

## Layer Vocabulary

- `domain`: the product model and pure business rules
- `application`: use-case orchestration
- `ports`: abstract seams used by application services
- `adapters`: concrete implementations of ports
- `presentation`: CLI and rendered output
- `bootstrap`: runtime wiring and assembly

## Package Sketch

```text
engineeringagent/
  domain/
    shared/
      ids.py
      enums.py
    specification/
      feature_specification.py
      planning.py
    quality/
      checks.py
      validation.py
      review.py
    guidance/
      topic.py
    audit/
      progress_event.py
  application/
    run_loop_service.py
    feature_iteration_service.py
    checks_service.py
    validation_service.py
    init_workspace_service.py
    workspace_recovery_service.py
    guidance_service.py
    prompt_builder.py
  ports/
    feature_specification_repository.py
    checks_catalog_repository.py
    guidance_topic_repository.py
    prompt_definition_repository.py
    progress_journal.py
    agent_runner.py
    shell_runner.py
    version_control.py
    feature_workspace_manager.py
    clock.py
  adapters/
    agents/
      codex.py
      opencode.py
    documents/
      filesystem_feature_specification_repository.py
      filesystem_checks_catalog_repository.py
      filesystem_guidance_topic_repository.py
    prompts/
      filesystem_prompt_definition_repository.py
    progress/
      filesystem_journal.py
    shell/
      subprocess_runner.py
    vcs/
      git_cli.py
      git_worktree_manager.py
  presentation/
    cli/
      run.py
      checks.py
      validate.py
      init.py
      workspace.py
      guidance.py
      schema.py
    presenters/
      terminal.py
      markdown.py
      json_schema.py
  bootstrap/
    app_factory.py
```

## Dependency Rule

```text
presentation -> application -> domain
application -> ports
adapters implement ports
bootstrap wires application to adapters
domain imports nothing from application, ports, adapters, presentation, or bootstrap
```

## Architectural Commitments

- the domain model never knows about Typer, subprocesses, git, or vendor CLIs
- application services return typed results and events; they do not print
- deterministic validation comes before judgment-based review
- structured output stays behind one canonical agent-execution boundary
- progress artifacts are operational records, not the source of truth for feature state
- strategy is the default extension pattern for check types and backend capabilities
- the specification model is rich enough to drive selection, prompting, verification, and completion without hidden operator memory
- prompts declare their allowed interpolations explicitly and default file references to path-only rendering
- execution uses an isolated feature workspace so the integration branch stays clean during iteration work
- the run starts in an orchestration process and may delegate execution to a local or remote target without changing the specification or quality model
- the default Python quality stack is `ruff` for style and linting, `pyright` for type checking, and `pytest` for tests
- Python environment and dependency management use `uv`, and canonical Python tool commands run through `uv run`
- behavior-changing implementation slices are expected to add or update focused unit or integration tests instead of relying only on generic repository checks

## Default Product Shape

The default installation uses a file-backed repository model:

- repository configuration lives in `engineeringagent.toml`
- feature specifications live under `docs/specifications/features/`
- completed feature specifications move under `docs/specifications/features_done/`
- checks configuration lives under `harness/`
- prompt definitions live under `harness/prompts/`
- progress artifacts live under `.engineeringagent/progress/`
- isolated feature worktrees live under `.engineeringagent/worktrees/`

Remote execution targets are optional adapters.
The authoritative feature branch still lives in the isolated workspace unless a stricter remote-first mode is chosen explicitly.

Those paths are adapter defaults, not domain assumptions.

## Document Map

- [`01-architecture-principles.md`](01-architecture-principles.md): design rules and domain boundaries
- [`02-core-information-model.md`](02-core-information-model.md): the multi-domain model
- [`03-workflow-services.md`](03-workflow-services.md): application services and orchestration boundaries
- [`04-checks-and-reviews.md`](04-checks-and-reviews.md): deterministic checks, validation, and reviewer policy
- [`05-gateways-and-surfaces.md`](05-gateways-and-surfaces.md): ports, adapters, and presentation
- [`06-composition-and-operations.md`](06-composition-and-operations.md): bootstrap, runtime sequence, and rollback behavior
- [`07-specification-model.md`](07-specification-model.md): the canonical feature specification package and planning model
- [`08-fitness_functions-and-validation.md`](08-fitness_functions-and-validation.md): structural fitness functions, validations, and harness enforcement
- [`09-prompt-architecture.md`](09-prompt-architecture.md): prompt definitions, interpolation contracts, and minimal-context rendering
- [`10-version-control-and-worktrees.md`](10-version-control-and-worktrees.md): isolated feature workspaces, branch policy, and diff-based review
- [`11-execution-targets-and-remote-runs.md`](11-execution-targets-and-remote-runs.md): local versus remote execution targets, publishing, and result reconciliation
- [`12-harness-contract-examples.md`](12-harness-contract-examples.md): canonical harness examples for checks, prompts, and reviewers
- [`13-loop-driven-build-plan.md`](13-loop-driven-build-plan.md): phased build slices suitable for iterative agent delivery
- [`14-port-contracts.md`](14-port-contracts.md): canonical Protocol signatures, request models, and result envelopes
- [`16-configuration-model.md`](16-configuration-model.md): repository configuration, backend/model selection, and precedence rules
- [`17-handoff-and-resumption.md`](17-handoff-and-resumption.md): internal handoff artifacts and iteration carryover
- [`15-implementation-prompt-and-iteration-example.md`](15-implementation-prompt-and-iteration-example.md): copyable implementation prompt definitions and accepted-iteration flow

## Coverage Matrix

| Concern | Primary docs |
| --- | --- |
| from-scratch product architecture | `README.md`, `01-architecture-principles.md` |
| multiple explicit domains | `02-core-information-model.md` |
| Protocol-based ports | `01-architecture-principles.md`, `05-gateways-and-surfaces.md`, `14-port-contracts.md` |
| specification-driven harness model | `07-specification-model.md` |
| prompt interpolation discipline and structured output | `09-prompt-architecture.md`, `12-harness-contract-examples.md` |
| validations and fitness functions | `08-fitness_functions-and-validation.md` |
| worktrees and diff-based review | `10-version-control-and-worktrees.md` |
| optional future remote execution | `11-execution-targets-and-remote-runs.md` |
| canonical harness examples | `12-harness-contract-examples.md` |
| implementation prompt and accepted iteration example | `15-implementation-prompt-and-iteration-example.md` |
| loop-buildable implementation sequence | `13-loop-driven-build-plan.md` |
| repository configuration and model selection | `16-configuration-model.md` |
| handoff and iteration carryover | `17-handoff-and-resumption.md`, `14-port-contracts.md` |

## Non-goals

- exposing backend-specific behavior to application code
- storing hidden mutable state outside explicit documents and journals
- letting CLI code own business sequencing
- using reviewer agents as the primary quality mechanism

## Intended Outcome

If built this way, EngineeringAgent stays understandable at three levels:

1. product rules live in clearly named domains plus application services
2. vendor churn stays local to adapters
3. operator experience evolves through presentation without reshaping the domain model

Taken together, these documents are intended to be specific enough that a team could rebuild the product from scratch and still arrive at an agent-driven harness with the same core ideas, constraints, and quality guarantees.
