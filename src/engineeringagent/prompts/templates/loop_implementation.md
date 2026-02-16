Read and use this feature spec from disk: $feature_path.
Execute one incremental implementation step for feature $feature_id ($feature_title).
Allways focus on the intention of the feature - over specific instructions especially since other features might have been implemented in the mean time. Dont be afraid to change current implementation details if that obviously simplifies the code. 
Objective: $objective
Context: $context
Identify the most important open subtask first from the YAML, make minimal deterministic code/documentation edits, and keep CLI behavior unchanged unless the spec explicitly requires it.
Update progress in the same feature YAML by setting relevant subtask/feature status fields and `updated_at`. Edits of the spec/feature should adhere to the spec for features. Please validate with: `uv run engineeringagent validate`.
Run the chosen subtask's listed verification command(s) only after it transitions to done in this iteration, then report concise outcomes covering: what changed, which verification passed/failed, and what remains.
