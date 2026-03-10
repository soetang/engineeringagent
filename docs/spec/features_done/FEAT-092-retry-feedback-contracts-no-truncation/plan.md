---
plan_id: FEAT-092
feature_id: FEAT-092
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define retry-feedback envelope contract (v1) and serialization rules
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
- id: ST-002
  title: Generate command failure retry feedback (exact failing command + pre-commit
    context)
  status: done
  verification:
  - uv run pytest -q
- id: ST-003
  title: Generate fitness failure retry feedback (failures-only contract)
  status: done
  verification:
  - uv run pytest -q
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-004
  title: Inject full reviewer decision JSON as retry feedback
  status: done
  verification:
  - uv run pytest -q
- id: ST-005
  title: Remove prompt retry-feedback truncation and enforce bounded envelopes
  status: done
  verification:
  - uv run pytest -q
- id: ST-006
  title: Add fitness rule that blocks retry-feedback truncation regressions
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-007
  title: Document retry feedback injection policy for LLM operators
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-008
  title: Remove confidence from reviewer decision contract (model + docs)
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
  - "uv run python - <<'PY'\nimport pathlib\nimport re\nimport sys\n\nroots = [pathlib.Path(\"\
    src\"), pathlib.Path(\"docs\"), pathlib.Path(\"harness\")]\npat = re.compile(r\"\
    \\bconfidence\\b\")\nignore_dirs = {\n    \".git\",\n    \".opencode\",\n    \"\
    .pytest_cache\",\n    \".ruff_cache\",\n    \".venv\",\n    \"__pycache__\",\n\
    \    \"dist\",\n    \"node_modules\",\n    \"output\",\n    \"tmp\",\n}\n\nhits:\
    \ list[str] = []\nfor root in roots:\n    if not root.exists():\n        continue\n\
    \    for p in root.rglob(\"*\"):\n        if p.is_dir():\n            continue\n\
    \        if any(part in ignore_dirs for part in p.parts):\n            continue\n\
    \        if p.parts[:2] == (\"docs\", \"spec\"):\n            continue\n     \
    \   try:\n            text = p.read_text(encoding=\"utf-8\")\n        except Exception:\n\
    \            continue\n        if pat.search(text):\n            hits.append(str(p))\n\
    \nif hits:\n    print(\n        \"confidence token found outside docs/spec:\"\
    ,\n        *[\"- \" + h for h in hits],\n        sep=\"\\n\",\n    )\n    sys.exit(1)\n\
    \nprint(\"confidence token absent outside docs/spec\")\nPY"
- id: ST-009
  title: Fix ruff gate failures introduced by retry-feedback contract work
  status: done
  verification:
  - uv run ruff check src/engineeringagent harness
  - uv run python -m engineeringagent.cli validate
- id: ST-010
  title: Remove non-ignorable Ruff suppression directives (PLR0913)
  status: done
  verification:
  - uv run ruff check src/engineeringagent harness
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run python -m engineeringagent.cli validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define retry-feedback envelope contract (v1) and serialization rules

Add strict models (Pydantic) for injected retry feedback envelopes.

Define envelope kinds:
- command_failure (gates/verification/commit)
- fitness_failure
- reviewer_feedback

Ensure the contract is deterministic and bounded by construction.

## ST-002 Generate command failure retry feedback (exact failing command + pre-commit context)

Update gate and verification failure handling to set hook_feedback to a
serialized command_failure envelope instead of raw stdout/stderr.

Required fields include:
- exact failing command
- phase and gate/check name when available
- pre-commit context when applicable

## ST-003 Generate fitness failure retry feedback (failures-only contract)

For fitness_validate failures, parse fitness JSON and inject only failing
rule ids + remediation + violations/details. Do not inject the full results
array.

## ST-004 Inject full reviewer decision JSON as retry feedback

Ensure reviewer-forwarded feedback injected into the next implement prompt is
the full parsed decision JSON envelope plus reviewer metadata, not raw logs.

## ST-005 Remove prompt retry-feedback truncation and enforce bounded envelopes

Remove _truncate_feedback usage from inject_retry_feedback so prompt injection
does not slice feedback.

Keep retry feedback bounded by envelope caps (counts/lines/bytes) rather than
generic truncation.

## ST-006 Add fitness rule that blocks retry-feedback truncation regressions

Add a new fitness function (architecture rule) that fails if the loop prompt
retry feedback injection uses truncation-by-slicing (e.g. _truncate_feedback
in src/engineeringagent/prompts/renderer.py).

## ST-007 Document retry feedback injection policy for LLM operators

Add an agent-facing reference doc describing:
- what is injected into retry prompts
- the envelope schemas and examples
- pre-commit context rules
- how fitness/reviewer failures differ from command failures

Ensure the new doc is allowlisted in harness/scaffold_policy.yaml.

## ST-008 Remove confidence from reviewer decision contract (model + docs)

Remove the confidence field from the reviewer decision envelope contract.

Scope:
- Update the ReviewerDecisionEnvelope model so confidence is not accepted.
- Update the injected reviewer response-format contract text so confidence is
  not mentioned.
- Update agent-facing docs that describe the reviewer decision envelope so
  confidence is not documented or used in examples.

Rationale:
- Keep reviewer outputs minimal and deterministic.
- Avoid encouraging self-reported confidence scores that are not enforced by
  deterministic checks.

## ST-009 Fix ruff gate failures introduced by retry-feedback contract work

Ensure repo lint gates remain green after implementing retry-feedback
contracts.

This includes resolving unused imports/locals and suppressing stylistic lint
rules (PLR0913/C901) only where refactors would be disproportionate.

## ST-010 Remove non-ignorable Ruff suppression directives (PLR0913)

The architecture.no-non-ignorable-ruff-suppressions fitness rule blocks inline
suppression directives for PLR0913/D103.

Remove any `# noqa: PLR0913` directives in repo code and keep lint green via
refactors or config-level per-file ignores when refactors are disproportionate.
