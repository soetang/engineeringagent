---
+schema_version: 1
+task_id: add-vibe-structured-output-retry
+title: Add session-aware structured output retry for the Vibe adapter
+status: ready
+branch: feat/add-vibe-structured-output-retry
+base_branch: main
+phases:
+  - id: adapter
+    title: Add session-aware retry and resume support to the Vibe adapter
+    status: todo
+  - id: parsing
+    title: Tighten structured-output parsing and repair prompting
+    status: todo
+  - id: tests
+    title: Lock retry and resume behavior with targeted adapter tests
+    status: todo
---

# Vibe Structured Output Retry Plan

## Goal

Make `VibeAdapter` recover when Vibe returns plain prose instead of the requested JSON for structured output.

After this change, structured-output calls should:

- make the first Vibe request normally;
- detect JSON parse or model-validation failures;
- resume the exact same Vibe conversation with `--resume <session_id>`;
- ask Vibe to reformat the previous answer as valid JSON matching the schema; and
- either return a valid Pydantic model or fail with a clearer final error.

## Scope

Keep this slice narrow.

Include only:

- changes in `src/developer/agent_backends/adapters/vibe_adapter.py`;
- targeted tests in `tests/agents/adapters/test_vibe_adapter.py`; and
- small helper methods needed to discover the created Vibe session and run the repair retry.

Do not include in this slice:

- retry logic in `AgenticReviewAdapter`;
- protocol changes for `AgentBackendProtocol` or `AgentRunner`;
- config settings for retry counts or repair prompts; or
- a generalized retry framework shared with other backends.

## Current State

- `VibeAdapter.run_agent(...)` prepends JSON schema instructions when `output_format` is a `BaseModel`.
- The adapter runs `vibe -p ... --output json` and parses the CLI transport output as a list of messages.
- It then extracts the last assistant message content and calls `_parse_json_content(...)`.
- `_parse_json_content(...)` only handles raw JSON or fenced ```json blocks.
- If Vibe replies with normal prose, parsing fails immediately.
- Vibe CLI supports both:
  - `-c` / `--continue` to resume the most recent session; and
  - `--resume SESSION_ID` to resume a specific session.

## Problem

The failure is not always a true review failure. Sometimes Vibe understood the task, but ignored the output contract and answered in prose.

That means the current adapter is too brittle for structured output:

1. it does not identify the exact session used for the original answer;
2. it does not retry when the response is almost correct but incorrectly formatted; and
3. it throws away useful conversational context that could be used to repair the output cheaply.

Using `-c` is not safe enough for this flow because another concurrent Vibe run could become the “most recent” session and cause the retry to continue the wrong conversation.

## Decision

Add a session-aware repair retry inside `VibeAdapter`.

Design rules:

1. keep retry logic in the backend adapter, not in `AgenticReviewAdapter`;
2. use `--resume <session_id>`, never `-c`, for repair retries;
3. only retry structured-output calls;
4. retry only once; and
5. include the previous invalid assistant content in the repair prompt.

## Proposed Design

### High-Level Flow

Structured-output execution should become:

```text
build schema prompt
  -> run vibe normally
  -> parse transport JSON messages
  -> extract assistant content
  -> parse content as structured JSON
      -> success: return model
      -> failure: discover exact session_id
          -> resume same conversation with repair prompt
          -> parse repaired content
              -> success: return model
              -> failure: raise clear error
```

### Session Targeting

The repair retry must target the exact session created by the first subprocess.

Recommended approach:

1. snapshot the newest session metadata timestamp before the initial call;
2. run the initial `vibe` subprocess;
3. inspect `~/.vibe/logs/session/*/meta.json` for the newest session created after the snapshot;
4. read its `session_id`; and
5. use that exact id in the repair call.

This avoids the concurrency risk in `-c` and does not require protocol changes.

### Retry Trigger

Retry when either of these happens during structured-output parsing:

- `json.JSONDecodeError`; or
- Pydantic model construction/validation failure.

Do not retry:

- raw string output mode;
- subprocess execution failures; or
- failures to parse the CLI transport envelope itself.

### Repair Prompt Shape

The repair prompt should be short and explicit:

- say the previous response was not valid JSON for the required schema;
- instruct Vibe to return only JSON, with no markdown fences or explanation;
- include the schema; and
- include the previous invalid content.

Example:

```text
Your previous response was not valid JSON for the required schema.

Return only valid JSON matching this schema:
```json
<schema>
```

Do not include markdown fences or explanatory text.

Previous invalid response:
<content>
```

## Required Implementation Work

### Phase 1: Add session-aware resume support to `VibeAdapter`

- extend command building so the adapter can issue both initial and resumed programmatic calls;
- add a helper that discovers the session id created by the initial run;
- keep session discovery internal to the adapter; and
- use `--resume <session_id>` for the repair retry.

Likely helper additions in `src/developer/agent_backends/adapters/vibe_adapter.py`:

- `_build_vibe_command(prompt: str, session_id: str | None = None) -> list[str]`
- `_find_created_session_id(start_time: float) -> str | None`
- `_read_session_id(meta_path: Path) -> str | None`

Concrete implementation sketch:

```python
from pathlib import Path
import time


def _build_vibe_command(self, prompt: str, session_id: str | None = None) -> list[str]:
    cmd = ["vibe", "-p", prompt, "--output", "json"]

    if session_id is not None:
        cmd.extend(["--resume", session_id])

    if self.profile:
        cmd.extend(["--agent", self.profile])

    if self.path:
        cmd.extend(["--workdir", self.path])

    return cmd


def _find_created_session_id(self, started_after: float) -> str | None:
    session_dir = Path.home() / ".vibe" / "logs" / "session"
    meta_paths = sorted(session_dir.glob("*/meta.json"), key=lambda path: path.stat().st_mtime)

    for meta_path in reversed(meta_paths):
        if meta_path.stat().st_mtime < started_after:
            break
        session_id = self._read_session_id(meta_path)
        if session_id:
            return session_id

    return None
```

### Phase 2: Add parse/repair retry flow

- split the structured-output path into smaller helpers;
- parse the initial assistant content once;
- on parse or validation failure, build a repair prompt and retry against the resumed session; and
- preserve the final failing content in the raised error.

Concrete implementation sketch:

```python
def run_agent(
    self,
    prompt: str,
    output_format: Optional[Type[TModel]] = None,
) -> TModel | str:
    if output_format is None or output_format is str:
        messages = self._run_vibe_messages(prompt)
        return self._extract_content(messages)

    schema = self._generate_schema(output_format)
    full_prompt = self._build_structured_prompt(prompt, schema)
    started_after = time.time()
    messages = self._run_vibe_messages(full_prompt)
    content = self._extract_content(messages)

    try:
        return self._model_from_content(output_format, content)
    except Exception as first_error:
        session_id = self._find_created_session_id(started_after)
        if session_id is None:
            raise RuntimeError(
                f"Failed to parse structured Vibe output and could not discover session id for retry. "
                f"Content: {content}"
            ) from first_error

        repair_prompt = self._build_repair_prompt(schema, content)
        repair_messages = self._run_vibe_messages(repair_prompt, session_id=session_id)
        repaired_content = self._extract_content(repair_messages)

        try:
            return self._model_from_content(output_format, repaired_content)
        except Exception as repair_error:
            raise RuntimeError(
                "Failed to parse structured Vibe output after repair retry: "
                f"{repair_error}\nInitial content: {content}\nRepaired content: {repaired_content}"
            ) from repair_error
```

Recommended helper split:

- `_run_vibe_messages(...)`
- `_extract_content(...)`
- `_build_structured_prompt(...)`
- `_build_repair_prompt(...)`
- `_model_from_content(...)`

This keeps `run_agent(...)` readable while avoiding duplicated subprocess logic.

### Phase 3: Keep parsing permissive but not magical

Preserve simple parsing rules:

- raw JSON object content should work;
- fenced ```json blocks should work;
- normal prose should not be heuristically rewritten into JSON locally; use the repair retry instead.

That keeps behavior predictable and lets the model do the reformatting.

Concrete parsing helper sketch:

```python
def _model_from_content(self, output_format: Type[TModel], content: str) -> TModel:
    json_data = self._parse_json_content(content)
    return output_format(**json_data)
```

## Tests

Add or update targeted tests in `tests/agents/adapters/test_vibe_adapter.py`.

### Test 1: command builder uses explicit `--resume`

```python
def test_vibe_adapter_builds_resume_command():
    adapter = VibeAdapter(profile="testagent", path="/tmp/workspace")

    command = adapter._build_vibe_command("repair", session_id="abc123")

    assert command == [
        "vibe",
        "-p",
        "repair",
        "--output",
        "json",
        "--resume",
        "abc123",
        "--agent",
        "testagent",
        "--workdir",
        "/tmp/workspace",
    ]
```

### Test 2: structured output succeeds without retry

This protects the non-error path and ensures the new helpers do not change the happy path.

```python
def test_structured_output_returns_model_without_retry(monkeypatch, tmp_path):
    adapter = VibeAdapter(profile="testagent")

    monkeypatch.setattr(
        adapter,
        "_run_vibe_messages",
        lambda prompt, session_id=None: [
            {"role": "assistant", "content": '{"status":"approved","summary":"ok","actions":[]}'},
        ],
    )

    result = adapter.run_agent("review this", output_format=ReviewOutput)

    assert isinstance(result, ReviewOutput)
    assert result.status is ReviewStatus.APPROVED
    assert result.summary == "ok"
```

### Test 3: prose first response triggers retry against exact session id

This is the main regression test.

```python
def test_structured_output_retries_with_exact_session_id(monkeypatch):
    adapter = VibeAdapter(profile="testagent")
    calls: list[tuple[str, str | None]] = []

    def fake_run(prompt: str, session_id: str | None = None):
        calls.append((prompt, session_id))
        if session_id is None:
            return [{"role": "assistant", "content": "This looks good overall."}]
        return [
            {
                "role": "assistant",
                "content": '{"status":"approved","summary":"ok","actions":[]}',
            }
        ]

    monkeypatch.setattr(adapter, "_run_vibe_messages", fake_run)
    monkeypatch.setattr(adapter, "_find_created_session_id", lambda started_after: "session-123")

    result = adapter.run_agent("review this", output_format=ReviewOutput)

    assert result.status is ReviewStatus.APPROVED
    assert calls[0][1] is None
    assert calls[1][1] == "session-123"
```

### Test 4: missing session id fails clearly

```python
def test_structured_output_retry_fails_when_session_id_missing(monkeypatch):
    adapter = VibeAdapter(profile="testagent")

    monkeypatch.setattr(
        adapter,
        "_run_vibe_messages",
        lambda prompt, session_id=None: [
            {"role": "assistant", "content": "Not JSON"},
        ],
    )
    monkeypatch.setattr(adapter, "_find_created_session_id", lambda started_after: None)

    with pytest.raises(RuntimeError, match="could not discover session id"):
        adapter.run_agent("review this", output_format=ReviewOutput)
```

### Test 5: repair retry still invalid surfaces both contents

```python
def test_structured_output_retry_includes_initial_and_repaired_content(monkeypatch):
    adapter = VibeAdapter(profile="testagent")

    def fake_run(prompt: str, session_id: str | None = None):
        if session_id is None:
            return [{"role": "assistant", "content": "Initial prose"}]
        return [{"role": "assistant", "content": "Still not json"}]

    monkeypatch.setattr(adapter, "_run_vibe_messages", fake_run)
    monkeypatch.setattr(adapter, "_find_created_session_id", lambda started_after: "session-123")

    with pytest.raises(RuntimeError) as exc_info:
        adapter.run_agent("review this", output_format=ReviewOutput)

    assert "Initial content: Initial prose" in str(exc_info.value)
    assert "Repaired content: Still not json" in str(exc_info.value)
```

## Acceptance Criteria

- Structured-output Vibe calls retry once when assistant content is not valid JSON.
- The retry uses `--resume <session_id>`, not `-c`.
- The adapter discovers and resumes the exact session created by the initial call.
- Raw string output behavior is unchanged.
- Existing happy-path structured-output tests still pass.
- New tests cover resume command building, retry success, missing-session failure, and repeated invalid output.

## Risks And Mitigations

### Session discovery may select the wrong session

Mitigation:

- snapshot time before the first call;
- search only sessions newer than that timestamp; and
- prefer the newest matching `meta.json`.

### Vibe logs may be unavailable or change shape

Mitigation:

- keep session discovery in a tiny helper;
- fail clearly when session metadata cannot be read; and
- avoid spreading filesystem assumptions outside the adapter.

### Retry prompts may become verbose or unstable

Mitigation:

- keep the repair prompt minimal;
- require “JSON only”; and
- include the exact schema and previous content.

## Out Of Scope Follow-Ups

Capture separately later if still needed:

- configurable retry counts;
- shared structured-output retry logic across Codex and Vibe;
- protocol-level session support instead of adapter-local session discovery; and
- telemetry on first-pass parse failures versus successful repairs.
