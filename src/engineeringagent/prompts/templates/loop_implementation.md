Read and use this feature spec from disk: $feature_path.
Execute one incremental implementation step for feature $feature_id ($feature_title).
Objective: $objective
Context: $context
Identify the next eligible subtask directly from the YAML, make minimal deterministic code/documentation edits, and keep CLI behavior unchanged unless the spec explicitly requires it.
Update progress in the same feature YAML by setting relevant subtask/feature status fields and `updated_at`.
Run the subtask's listed verification command(s), then report concise outcomes covering: what changed, which verification passed/failed, and what remains.
