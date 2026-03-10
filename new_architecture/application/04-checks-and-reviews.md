# Checks and Reviews

## Purpose

Define the quality system for EngineeringAgent: static validation, deterministic runtime checks, fitness rules, and optional reviewer agents.

## Quality Domain Role

The quality domain answers one question: can the repository state produced by an iteration be trusted?

It does that through three distinct mechanisms:

- static validation of declared contracts
- deterministic runtime checks planned from policy
- reviewer decisions for judgment-heavy cases

## Quality Philosophy

- deterministic validation is the foundation
- runtime checks are planned from declarative policy
- reviewer agents are explicit, auditable complements
- the run loop consumes one stable quality result contract

## Main Lanes

### Validation lane

Static, side-effect-free validation of repository contracts.

Owns:

- schema conformance
- feature-specification structure rules
- documentation integrity
- checks-catalog integrity
- guidance-topic integrity

### Runtime checks lane

Side-effecting checks planned and executed during a loop phase.

Owns:

- deterministic run or skip decisions
- ordered execution
- failure capture
- prompt-ready retry feedback

### Reviewer lane

Judgment-based review for cases that deterministic checks cannot fully cover.

Owns:

- review prompts
- structured review decisions
- approval-state persistence
- optional repository sandboxing

## Strategy Families

Each runtime check type is a strategy with the same lifecycle:

- `plan(context) -> CheckDecision[]`
- `execute(context, decisions) -> CheckExecutionRecord[]`
- `render_feedback(failure) -> str | None`

Recommended strategy families:

- `command`
- `fitness`
- `reviewer`

Static validation is a sibling workflow, not just another command strategy.

## Quality Contracts

### CheckContext

Contains the execution context for planning and running checks:

- project root
- phase
- changed paths
- optional feature identity
- optional retry feedback

### CheckDecision

One deterministic planner output:

- `check_id`
- `check_type`
- `phase`
- `decision`
- `reason`

### CheckExecutionRecord

One executed check outcome:

- `check_id`
- `ok`
- `output`
- optional structured payload
- timing metadata when relevant

### ChecksResult

The stable workflow-facing output:

- overall success flag
- decision list
- execution list
- first failure metadata
- human-readable output
- prompt-ready feedback

### ValidationIssue

One static rule violation with:

- validator id
- scope
- path
- stable rule code
- message

## Ownership Rules

### Repo validators own

- feature specification and plan invariants
- archive and active-state rules
- repository-level documentation rules
- product-wide configuration contracts

### Strategy validators own

- reviewer prompt hygiene
- fitness manifest integrity
- strategy-local configuration rules

## Boundary Rules

- the run loop never branches on check type
- planners do not execute commands
- executors do not decide repository policy outside their strategy family
- feedback rendering explains failures without mutating workflow state
- reviewer adapters do not decide whether review is required

## Reviewer Safeguards

- review prompts must be deterministic and auditable
- review output must be schema-validated
- approvals may be cached only under explicit policy
- non-approval results must produce actionable feedback
- reviewer agents never bypass deterministic validation

## Default Execution Order

1. blocking startup validation runs before `run` performs any side effects
2. the `validate` command runs full repository validation on demand
3. command and fitness checks run for the active phase
4. reviewer checks run only after deterministic checks pass

## Design Goal

The quality system is successful when a new check type can be added by introducing one strategy family and one adapter set, without changing the run loop.
