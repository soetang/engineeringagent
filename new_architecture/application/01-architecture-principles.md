# Architecture Principles

## Purpose

Define the structural rules for EngineeringAgent as a clean, document-centered product.

## Product View

EngineeringAgent is not mainly a chat wrapper.
It is a workflow engine that turns structured work descriptions into verified repository changes through short, recoverable execution loops.

## Primary Principles

### 1. Documents are the source of truth

- feature specifications define desired outcomes
- plan phases define execution order when sequencing matters
- checks definitions define repository quality policy
- progress journals record what happened, but never replace source documents

### 2. The domain stays pure

- the domain owns entities, value objects, invariants, and pure policy helpers
- the domain does not import CLI frameworks, subprocess helpers, filesystem code, or vendor SDKs
- the domain may define typed events, but not event transport or storage

### 3. Workflows own sequencing

- workflows coordinate multi-step use cases
- workflows depend on capability interfaces for side effects
- workflows return typed results and failure details
- workflows never print or format terminal output

### 4. Determinism first, judgment second

- schema validation, config validation, and command checks run before reviewer agents
- reviewer agents are optional complements for judgment-heavy decisions
- deterministic failures should always be explainable without model interpretation

### 5. Strategy is the extension pattern

Use strategy objects when the sequence is stable but behavior families vary:

- check types
- backend-specific structured-output behavior
- selection policies that may change without altering workflow shape

### 6. Adapters own vendor behavior

- git behavior belongs in the version-control adapter
- subprocess behavior belongs in the shell adapter
- YAML and markdown parsing belong in document-store adapters
- backend-specific prompting or schema transport belongs in agent adapters

### 7. Presentation stays thin

- CLI commands parse input and choose a presenter
- presenters render typed application results
- schema export is a public representation concern, not a business rule

## Multi-domain Rule

There is not one giant domain module.
There are several small, explicit domains with a shared kernel.

Recommended domain split:

- `specification`
- `quality`
- `guidance`
- `audit`
- `shared kernel`

This keeps responsibilities obvious while still using standard ports-and-adapters naming for the outer layers.

## Dependency Rules

Ports should be defined as Python `Protocol` contracts.
That keeps them lightweight, structurally typed, and easy to fake in tests.

### Allowed direction

```text
presentation -> application -> domain
application -> ports
adapters -> ports
bootstrap -> all layers for wiring only
```

### Forbidden direction

- domain importing ports, adapters, or presentation
- application importing concrete vendors
- adapters deciding application sequencing
- presentation deciding feature-selection or quality policy

## Glossary

- `feature specification`: a structured description of one change outcome
- `plan phase`: one planned execution slice inside a feature specification
- `check`: a declared quality gate with deterministic planning and execution rules
- `reviewer`: an agent-driven quality gate for judgment-heavy cases
- `port`: an abstract dependency used by application services
- `adapter`: a concrete implementation of a port
- `presentation`: a user-facing or machine-facing representation layer

## Design Test

The architecture is healthy when the following statements stay true:

- an application-service test can run with fake ports only
- a new backend can be added without editing the run loop
- a new presenter can be added without editing domain policy
- a failed check can be explained from structured records alone
