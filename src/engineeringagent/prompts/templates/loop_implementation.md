Read and use this feature spec from disk: $feature_path.
Execute one incremental implementation step for feature $feature_id ($feature_title).
Allways focus on the intention of the feature - over specific instructions especially since other features might have been implemented in the mean time. Dont be afraid to change current implementation details if that obviously simplifies the code. 
Objective: $objective
Context: $context
Identify the most important open subtask first from the YAML, make minimal deterministic code/documentation edits, and keep CLI behavior unchanged unless the spec explicitly requires it.
Follow an explicit red-green-refactor TDD loop (red -> green -> refactor) for that subtask: (1) write or adjust a test and observe failure (red), (2) implement minimal code and observe pass (green), (3) refactor while keeping tests green.
Update progress in the same feature YAML by setting relevant subtask/feature status fields and `updated_at`.
Run the chosen subtask's listed verification command(s) after it transitions to done in this iteration, then report concise outcomes covering: what changed, which verification passed/failed, and what remains.
