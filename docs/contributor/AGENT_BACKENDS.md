# Agent Backends

Agent backend settings use the same meaning across the system, regardless of the CLI adapter.

## Shared Fields

- `backend`: selects the backend family, such as `codex` or `vibe`
- `profile`: selects a backend preset, profile, or persona; this may bundle model choice, prompts, tools, and permissions
- `model`: selects the underlying LLM only when the backend supports direct model selection

These semantics apply in `[agents]` config and in per-check overrides such as `AgenticReviewCheck`.

`path` is different: it is a runtime execution input, not part of `[agents]` TOML configuration.

## Backend Mapping

### Codex

- `profile` -> Codex profile resolution / `--profile`
- `model` -> `--model`
- `path` -> `--cd`

Example:

```toml
[agents]
backend = "codex"
profile = "implementation"
model = "gpt-5.3-codex-spark"
```

### Vibe

- `profile` -> `--agent`
- `model` -> invalid

Example:

```toml
[agents]
backend = "vibe"
profile = "testagent"
```

If Vibe receives `model`, selection fails with a clear validation error. Use `profile` instead.

## Runtime Path Override

- `path` is accepted by backend adapters and selection APIs at execution time
- Codex maps it to `--cd`
- Vibe maps it to `--workdir`
- do not add `path` under `[agents]` in `engineeringagent.toml`

## Testing Guidance

- Prefer `profile = "testagent"` for Vibe-backed integration tests and fixtures
- Configure `.vibe/agents/testagent.toml` locally to point at a smaller model such as `devstral-small`
- Keep fixture semantics aligned with production config: Vibe agent selection goes through `profile`, not `model`

## Code Layout

Shared backend settings, protocols, adapters, and selection code live under `engineeringagent.agent_backends`.
