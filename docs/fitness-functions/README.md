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
uv run python -m engineeringagent.cli fitness catalog --format markdown --output docs/fitness-functions/rules.md
```
