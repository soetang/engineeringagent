# Fitness Framework Architecture

```mermaid
flowchart LR
    A[CLI: fitness list/run/catalog] --> B[Registry build_rule_catalog]
    B --> C[Built-in Python rules]
    B --> D[Custom manifest harness/fitness-functions/rules.yaml]
    C --> E[Rule metadata + adapter contract]
    D --> E
    E --> F[Runner run_rule_catalog]
    F --> G[Python adapter]
    F --> H[Command adapter]
    G --> I[Deterministic result envelope]
    H --> I
    I --> J[Gate integration + generated docs]
```
