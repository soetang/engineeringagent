# Fitness Functions

This section is the canonical home for active fitness-function inventory and
execution architecture.

- Rule catalog (generated): `docs/fitness-functions/rules.md`
- Execution architecture diagram: `docs/fitness-functions/architecture.md`

Regenerate the catalog after rule metadata changes:

```bash
uv run python -m engineeringagent.cli fitness catalog --format markdown --output docs/fitness-functions/rules.md
```
