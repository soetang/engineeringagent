In this repository, run EngineeringAgent CLI commands with `uvx engineeringagent ...`.

Use `engineeringagent approach` for the overall workflow and guidance map.

Use `engineeringagent approach list` to discover topics, then open one (for example `engineeringagent approach specifications`).

Runtime progress artifacts are emitted under `.engineeringagent/progress/`. Keep this path out of git unless you intentionally share it.
Recommended ignore entry: `/.engineeringagent/progress/`.
Paths are materialized only when the loop/runtime writes for the first non-dry execution.
