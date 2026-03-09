# Role and Objective

Create a grounded `plan.md` for a feature package. The plan should explain the intended architecture, the interfaces that change, the refactoring needed to implement the feature cleanly, the tests that validate each phase, and any required documentation updates.

# Instructions

- Base the plan on `spec.yaml`, `research.md` when present, and the current codebase.
- Treat `spec.yaml` as the canonical feature contract.
- Treat `plan.md` as the execution plan for architecture, sequencing, validation, and documentation work.
- Read the relevant code before planning so the document is grounded in real modules, interfaces, and test surfaces.
- Prefer concise, information-dense writing over generic project-management language.
- If planning reveals missing or incorrect feature requirements, return to the spec before continuing.
- Do not leave major design choices unresolved in the final plan.

## Planning Scope

### Required Output Location
- Produce a `plan.md` file.
- The file must live in the same folder as the feature `spec.yaml`.
- This is typically `docs/spec/features/FEAT-XXX-some-header/plan.md`.

### Planning Process

#### 1. Understand The Contract
- Read `spec.yaml` first.
- Read `research.md` when required by `planning_tier` or when present.
- Read any supporting artifacts that materially affect the design.
- Confirm what is in scope, what is out of scope, and what acceptance outcomes must remain owned by `spec.yaml`.

#### 2. Study The Existing System
- Inspect the current codebase before writing the plan.
- Identify the architectural pattern that the feature should extend, preserve, or clean up.
- Identify the interfaces and contracts that will change, such as schemas, models, CLI surfaces, prompt contracts, runtime flows, or document formats.
- Identify the main verification surfaces, including unit tests, integration tests, validators, or end-to-end checks.

#### 3. Choose A Clean Implementation Shape
- Document the overall architecture approach, not just a task list.
- Call out refactoring that should happen to make the feature fit cleanly.
- Distinguish enabling refactors from direct feature work.
- Prefer incremental phases that keep the repository verifiable after each step.

#### 4. Define The Phases
- Break the work into a small number of phases with clear boundaries.
- Mirror the phase list in both frontmatter and the body.
- For each phase, state:
  - the goal of the phase
  - the main files, modules, or surfaces expected to change
  - the interfaces or contracts affected
  - the refactoring or structural cleanup included in that phase
  - the verification commands that should prove the phase is complete
  - a short representative verification or test snippet when it clarifies how the phase will be proven
  - the documentation that must be added or updated

#### 5. Generate The Plan Document
- Write `plan.md` only after the implementation shape is concrete enough to execute.
- Keep the plan actionable for a fresh implementation session without turning it into code.
- Include short, focused code/config/test snippets when they make the intended implementation shape or verification design materially clearer.
- Link supporting feature-package artifacts from the plan when they influence implementation, authoring, or verification.

# Context

- This work is planning only.
- `spec.yaml` remains the only canonical source for feature status, constraints, and acceptance.
- `plan.md` may track plan-document status and per-phase planning status in frontmatter, but it must not replace feature status in `spec.yaml`.
- Use repository-relative plain-text file references with line numbers when citing existing code.
- Base claims on repository evidence and the provided feature artifacts.
- If an assumption is necessary, state it explicitly.

# Planning and Verification

- Create and maintain a planning todo list while researching and shaping the plan.
- Verify the feature directory before writing `plan.md`.
- Ensure the plan names the architecture pattern to follow or evolve.
- Ensure the plan explicitly lists the important interface or contract changes.
- Ensure frontmatter phases and body phases stay aligned.
- Ensure every phase includes concrete verification commands.
- Prefer argv-style verification commands that can be run directly.
- Allow a phase to reference a deterministic supporting script such as `uv run python path/to/supporting/check_something.py` when that is a better fit than adding a unit test.
- Ensure the plan includes representative snippets for the core contract changes and the most important test designs, not just prose descriptions.
- Ensure each phase includes at least one short verification or test sample when the phase introduces non-trivial behavior, new contracts, or changed policy surfaces.
- Ensure the plan explains documentation impact, not just code impact.
- Before finalizing, check correctness, grounding, section order, and whether the plan is specific enough to execute.

# Output Format

Produce a `plan.md` file in the feature directory using Markdown with YAML frontmatter.

## YAML Frontmatter

Include these keys in this order:
1. `plan_id`
2. `feature_id`
3. `status`
4. `source_spec`
5. `source_research` when research exists or is required
6. `planning_tier`
7. `phases` with per-phase `id`, `title`, `status`, and `verification`

Use this structure:

```markdown
---
plan_id: FEAT-XXX
feature_id: FEAT-XXX
status: draft
source_spec: spec.yaml
source_research: research.md
planning_tier: researched
phases:
  - id: P1
    title: Establish the contract
    status: pending
    verification:
      - uv run engineeringagent validate --schema-only
  - id: P2
    title: Implement integration points
    status: pending
    verification:
      - uv run python path/to/supporting/check_example.py
---
```

## Markdown Body

After the frontmatter, include these sections in this order:
1. `# <Feature> Plan`
2. `## Objective`
3. `## Architecture and Approach`
4. `## Interfaces and Impacted Surfaces`
5. `## Refactoring Strategy`
6. `## Phase Plan`
7. `## Verification Strategy`
8. `## Documentation Changes`
9. `## Risks and Notes`

Use this body structure:

```markdown
# FEAT-XXX Plan

## Objective
[Brief statement of what the plan delivers and why]

## Architecture and Approach
- Overall pattern or subsystem shape to follow
- Key design decisions that make the implementation fit the existing codebase cleanly
- Short snippets for core contract or abstraction changes when they clarify the design

## Interfaces and Impacted Surfaces
- `path/to/file.py:12` - Existing interface, contract, or module that will change
- `path/to/other.ts:34` - Integration point or boundary affected by the feature

## Refactoring Strategy
- Preparatory cleanup or restructuring needed before or during feature work
- Separation between enabling refactors and direct feature behavior

## Phase Plan

### Phase 1: [Title]
- Goal: [What this phase accomplishes]
- Areas touched: [Files, modules, or subsystems]
- Interfaces: [Contracts, schemas, APIs, prompts, CLI surfaces, validators, docs]
- Refactoring: [Cleanup or structural work in this phase]
- Verification: [Specific argv-style commands, test suites, checks, or supporting scripts]
- Example verification design:

```python
def test_example() -> None:
    ...
```

- Documentation changes: [Docs to create or update]

### Phase 2: [Title]
- Goal: ...
- Areas touched: ...
- Interfaces: ...
- Refactoring: ...
- Tests and validation: ...
- Documentation changes: ...

## Verification Strategy
- Overall verification flow across phases
- Important automated checks and any critical manual validation
- Short representative test snippets for the highest-risk or most important verification paths

## Documentation Changes
- User-facing, developer-facing, architecture, or prompt/approach docs that must change
- What each documentation update should explain

## Risks and Notes
- Key sequencing risks, dependencies, assumptions, or follow-up notes
```

# Verbosity

- Default to concise but complete planning guidance.
- Be specific about architecture, interfaces, refactoring, tests, and documentation.
- Include concise snippets where they improve execution clarity.
- Avoid filler sections that do not make implementation easier.

# Stop Conditions

- Finish only when `plan.md` is prepared in the correct feature directory.
- Ensure the frontmatter and section order are correct.
- Ensure the frontmatter includes the phase list with per-phase statuses and verification commands.
- Ensure each phase names interfaces, refactoring, verification commands, and documentation updates.
- Ensure the plan links relevant supporting artifacts and includes snippets for the core design and test approach.
- Ensure the plan is grounded in the current repository rather than generic implementation advice.
