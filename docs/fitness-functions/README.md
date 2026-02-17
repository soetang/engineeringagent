# Fitness Functions

This section is the canonical home for active fitness-function inventory and
execution architecture.

- Rule catalog (generated): `docs/fitness-functions/rules.md`
- Execution architecture diagram: `docs/fitness-functions/architecture.md`

## Harness Authoring Surface

Harness fitness-rule scripts under `harness/fitness-functions/` are allowed to
depend on a small, explicit helper surface from `engineeringagent`.

By default, harness scripts may import only:

- `engineeringagent.fitness.*`

They must not import orchestration/runtime internals (for example
`engineeringagent.loop`, `engineeringagent.cli`, or `engineeringagent.loop_runtime.*`).

For deterministic result emission, use `engineeringagent.fitness.envelope`:

```python
from engineeringagent.fitness.envelope import emit_result_envelope

emit_result_envelope(...)
```

Regenerate the catalog after rule metadata changes:

```bash
uv run engineeringagent fitness catalog --format markdown --output docs/fitness-functions/rules.md
```

## Opt-in Real Agent Smoke Test

The rule `smoke.opencode-real-hello-world` validates the full "real agent" integration path
end-to-end by running the engineering loop inside an isolated temp git repository.

What it does (when enabled):

- Creates a temp git repo.
- Runs `engineeringagent init slim --no-precommit-install` in that repo.
- Writes a tight hello-world Python feature spec (explicit interface + verification).
- Runs `engineeringagent run` (real OpenCode-backed implementation).
- Re-runs stdlib-only verification commands and asserts the archived spec is `status: done`.

Enable/skip behavior:

- Default: PASS with summary `skipped (set ENGINEERINGAGENT_REAL_OPENCODE_SMOKE=1)`.
- If enabled but `opencode` is not on PATH: PASS with summary `skipped (opencode not installed)`.

Run it locally:

```bash
uv run engineeringagent fitness run --format json
ENGINEERINGAGENT_REAL_OPENCODE_SMOKE=1 uv run engineeringagent fitness run --format json
```

Common failure modes:

- OpenCode permission/login rejection: ensure OpenCode is configured and that the repo is allowed.
  Remediation is to review the scaffolded temp repo `.opencode/agents/engineeringagent.md`.
- Loop errors or init scaffold failures: the rule reports which step failed and includes captured output.
