$artifact_paths
Before doing new work, read prior handoff context from $handoff_path when the file exists.
Because handoff is append-only, read from the bottom first (`tail -n 40 ...`) to get the latest iteration.
Do not write the handoff file directly; loop/runtime owns handoff file appends.

If there is feedback, from previous iterations always address that first.

If no feedback is present:
Execute one incremental implementation step for feature $feature_id ($feature_title). 
Identify the most important open $progress_unit first.
Before making changes - research the code base. You can use multiple parallel subagents to do the reasearch. 
Then implement the most important $progress_unit, using TDD - Write a tests, implement funtionality that passes the test, refactor.

Always focus on the intention of the feature over overly specific instructions, especially since other features might have been implemented in the meantime. Don't be afraid to change current implementation details if that obviously simplifies the code.

After implementing functionality or resolving problems, run the tests for that unit of code that was improved.

Objective: $objective
Context: $context
$current_progress_reference
$progress_context_instruction

Make minimal deterministic code/documentation edits, and keep CLI behavior unchanged unless the spec explicitly requires it.

$progress_update_instruction Validate with: `uv run engineeringagent validate --schema-only`.
Run the chosen $progress_unit's listed verification command(s) only after it transitions to done in this iteration, then report concise outcomes covering: what changed, which verification passed/failed, and what remains.

Your output should be written so that the next developer can easily continue the work. If you discover issues or surprises please clearly note it in the summary with `ISSUE: description of issue..` 
