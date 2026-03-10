# Domain Model

## Purpose

Define the durable product concepts that remain stable regardless of CLI framework, adapter choice, or agent vendor.

## Domain Structure

EngineeringAgent has multiple domains, not one monolithic model.

- `shared kernel`: common identifiers, enums, and basic value objects
- `specification domain`: feature specifications, plans, phases, and completion rules
- `quality domain`: checks, validation issues, reviewer policies, and quality outcomes
- `guidance domain`: discoverable operator-facing topics
- `audit domain`: progress events and operational facts

## Shared Kernel

Shared types include:

- `FeatureId`
- `PhaseId`
- `CheckId`
- `TopicId`
- `FeatureStatus`
- `PlanningTier`
- `CheckPhase`
- `BackendId`
- `ReviewDecision`

These types are intentionally small so domains can share language without sharing all behavior.

## Specification Domain

### FeatureSpecification

The primary unit of work.
It owns:

- `feature_id`
- title and problem statement
- type and priority
- status
- scope, constraints, and acceptance criteria
- planning tier
- declared supporting artifacts

This is the unit selected by the application layer.

### Plan

An optional child document of a feature specification that owns execution sequencing.
It contains ordered phases, each with:

- `phase_id`
- goal
- status
- implementation notes
- verification commands

Plans exist only when a feature needs explicit multi-step sequencing.

### Specification domain invariants

- feature status aligns with plan completion state
- planning tier determines required supporting artifacts
- acceptance criteria stay outcome-oriented
- verification commands belong to planned work

## Quality Domain

### CheckCatalog

The repository quality policy.
It contains declared checks with:

- `check_id`
- check type
- run phase
- change-trigger policy
- static configuration for its strategy family

The catalog is declarative. It does not own command execution.

### ValidationIssue

Represents one static rule violation with:

- validator id
- scope
- stable rule code
- path
- message

### ReviewPolicy

Defines when a reviewer is required, what result shapes are valid, and whether approvals may be reused.

### Quality domain invariants

- check planning is deterministic
- quality policy is declarative before execution
- reviewer rules never bypass deterministic validation
- validation ownership is explicit between repository-wide and strategy-local rules

## Guidance Domain

### GuidanceTopic

An operator-facing guidance document with:

- `topic_id`
- aliases
- title
- description
- content reference

Guidance is part of the product because the operator experience depends on predictable discovery and stable topic identity.

## Audit Domain

### ProgressEvent

An append-only operational record such as:

- iteration started
- implementation succeeded
- verification failed
- reviewer requested changes
- accepted iteration commit created

Progress events are not a replacement for feature state.

### Audit domain invariants

- events are append-only
- journals record operations, not product truth
- a failed iteration remains explainable from recorded events and result objects

## Cross-domain Relationships

```text
FeatureSpecification
  -> may own Plan
  -> declares required supporting artifacts

Plan
  -> owns ordered Phase values

CheckCatalog
  -> owns CheckDefinition values

GuidanceCatalog
  -> owns GuidanceTopic values

ProgressJournal
  -> stores ProgressEvent values outside the source-of-truth model
```

## Invariants

- topic identifiers are stable even if content wording changes
- domains communicate through explicit value objects and application-service contracts
- storage shape is never the same thing as domain meaning

## What Belongs Outside the Domain Layer

- YAML parsing
- markdown frontmatter parsing
- filesystem path rules
- git operations
- subprocess execution
- JSON Schema rendering
- terminal formatting

## Ports Around the Domain

The domain is loaded and persisted through ports such as:

- `FeatureSpecificationRepository`
- `ChecksCatalogRepository`
- `GuidanceTopicRepository`
- `ProgressJournal`

These ports protect the domain from storage details while keeping the model explicit.

## Suggested Document Shapes

The domain is storage-agnostic, but the default product shape assumes:

- `specification.yaml` is the canonical feature specification document
- `plan.md` stores ordered phase metadata plus human-readable notes
- `research.md` is optional supporting context except when `planning_mode=researched`
- `harness/checks.yaml` defines the check catalog

Those are default representations, not domain requirements.

## Why This Layer Matters

EngineeringAgent is most stable when each domain is small and explicit.
If work definition, quality, guidance, and audit are cleanly separated, the outer layers can evolve without blurring responsibilities.
