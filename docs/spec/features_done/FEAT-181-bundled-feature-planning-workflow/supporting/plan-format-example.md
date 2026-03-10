---
plan_id: FEAT-999
feature_id: FEAT-999
status: backlog
source_spec: spec.yaml
planning_tier: planned
phases:
  - id: P1
    title: Define bundled feature contract
    status: backlog
    verification:
      - uv run engineeringagent validate --schema-only
  - id: P2
    title: Implement discovery and validation
    status: backlog
    verification:
      - uv run pytest -q tests/specs/test_bundled_feature_discovery.py
      - uv run python docs/spec/features/FEAT-999-example-bundled-feature-package/supporting/validate_artifact_requirements.py
  - id: P3
    title: Update guidance, reviewers, and examples
    status: backlog
    verification:
      - uv run pytest -q tests/cli/test_cli.py -k approach
      - uv run python docs/spec/features/FEAT-999-example-bundled-feature-package/supporting/validate_example_bundle.py
---

# FEAT-999 Plan

## Objective

- Implement the bundled feature package workflow described by `spec.yaml` without turning `plan.md` into a second canonical feature-status system.

## Architecture and Approach

- Treat each feature folder as the unit of discovery, with `spec.yaml` as the canonical contract and companion artifacts referenced through deterministic relative paths.
- Keep ownership boundaries explicit: discovery and validation logic belong in the feature-spec workflow, while planning and research remain companion documents.

```yaml
id: FEAT-999
planning_tier: planned
status: backlog
artifacts:
  plan: plan.md
```

```yaml
plan_id: FEAT-999
status: in_progress
phases:
  - id: P2
    status: in_progress
```

## Interfaces and Impacted Surfaces

- `docs/spec/features/**/spec.yaml` - feature discovery entrypoint moves from flat files to bundled feature folders.
- feature-spec schema and validators - add `planning_tier`, `artifacts`, and plan-artifact presence checks.
- planning artifact parsing - require `plan.md` frontmatter with plan metadata and per-phase status data.
- approach and prompt documentation - explain spec-first, research, planning, and fresh-session guidance.

## Refactoring Strategy

- Separate bundled feature discovery from legacy flat-file assumptions before expanding validation rules.
- Keep artifact validation isolated from feature execution status so `plan.md` metadata cannot override `spec.yaml`.
- Update examples and guidance after contract enforcement is stable so documentation reflects the actual workflow.

## Phase Plan

### Phase 1: Define bundled feature contract
- Goal: Lock the package layout, ownership boundaries, and machine-readable metadata expectations.
- Areas touched: feature-spec models, schema definitions, artifact metadata handling.
- Interfaces: `spec.yaml` contract, `plan.md` frontmatter contract, artifact reference rules.
- Refactoring: Split contract definition work from runtime discovery changes.
- Verification:
  - `uv run engineeringagent validate --schema-only`
- Example verification design:

```python
def test_planned_tier_requires_plan_artifact(tmp_path: Path) -> None:
    write_spec(tmp_path, planning_tier="planned", artifacts={})
    assert "plan.md" in validate(project_root=tmp_path)[0]
```

- Documentation changes: update spec-writing and package-contract guidance to explain canonical ownership and required artifacts.

### Phase 2: Implement discovery and validation
- Goal: Discover active features from bundled folders and enforce tier-based artifact requirements.
- Areas touched: active feature discovery, validator logic, fixture coverage.
- Interfaces: discovery path rules, validator outputs, `planned` vs `researched` artifact requirements.
- Refactoring: Remove or isolate flat-file assumptions so bundled discovery becomes the primary path.
- Verification:
  - `uv run pytest -q tests/specs/test_bundled_feature_discovery.py`
  - `uv run python docs/spec/features/FEAT-999-example-bundled-feature-package/supporting/validate_artifact_requirements.py`
- Example verification design:

```python
def test_discovery_returns_spec_entrypoint_for_bundle(tmp_path: Path) -> None:
    create_feature_package(tmp_path, "FEAT-999-example", status="backlog")
    assert discover_active_feature_paths(tmp_path) == [
        tmp_path / "docs/spec/features/FEAT-999-example/spec.yaml"
    ]
```

- Documentation changes: document the new discovery behavior and validator expectations.

### Phase 3: Update guidance, reviewers, and examples
- Goal: Bring prompts, reviewer guidance, examples, and approach docs in line with the bundled workflow.
- Areas touched: supporting prompt docs, reviewer prompts, example spec and plan artifacts, workflow guidance.
- Interfaces: planning-session guidance, research-session guidance, author-facing examples, reviewer expectations, and CLI approach labels.
- Refactoring: consolidate duplicate guidance so the examples mirror the enforced contract.
- Verification:
  - `uv run pytest -q tests/cli/test_cli.py -k approach`
  - `uv run python docs/spec/features/FEAT-999-example-bundled-feature-package/supporting/validate_example_bundle.py`
- Example verification design:

```python
def test_approach_list_marks_task_specific_topics() -> None:
    output = run_cli("approach", "list")
    assert "only when creating plan.md" in output
```

- Documentation changes: explain the expected session sequence, the role of planning artifacts, reviewer expectations, and how documentation changes with the new workflow.

## Verification Strategy

- Validate schema and artifact contracts before testing runtime discovery behavior.
- Add focused regression coverage for bundled feature discovery and tier-based artifact enforcement.
- Verify examples and guidance stay consistent with the validator-backed contract.

## Documentation Changes

- Update planning and research guidance to explain when each artifact is created and what it owns.
- Update examples to show that active bundled specs do not contain `subtasks` and that plan phases own sequencing.
- Update examples so authors can copy a valid bundled feature package shape.
- Update reviewer and CLI approach guidance so task-specific session docs are discoverable without becoming default reading.
- Clarify that fresh sessions are recommended workflow guidance, not validator-enforced runtime state.

## Risks and Notes

- Discovery changes may expose older flat-file assumptions in docs or prompts outside the immediate feature package.
- Plan frontmatter status and per-phase status must remain document metadata only, not canonical feature execution state.
- Task-specific approach descriptions should come from frontmatter metadata while `engineeringagent approach <topic>` continues to show the body without frontmatter.
