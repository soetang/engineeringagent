---
plan_id: FEAT-009
feature_id: FEAT-009
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Inventory current scripts and define old-to-new command mapping
  status: done
  verification:
  - python3 -c "from pathlib import Path; t=Path('README.md').read_text(encoding='utf-8');
    assert 'Command mapping' in t; print('ok')"
- id: ST-002
  title: Remove generic scripts folder and relocate only purpose-specific automation
  status: done
  verification:
  - python3 -c "from pathlib import Path; assert not Path('scripts').exists(); print('ok')"
  - uvx --from . engineeringagent --help
- id: ST-003
  title: Ensure canonical CLI coverage for workflows previously reached via scripts
  status: done
  verification:
  - uvx --from . engineeringagent validate --schema-only
  - uvx --from . engineeringagent gates list
  - uvx --from . engineeringagent gates run --profile precommit
- id: ST-004
  title: Rewrite docs to scriptless command usage with explicit lint/test/spec sections
  status: done
  verification:
  - python3 -c "from pathlib import Path; files=['README.md','docs/references/uv-workflow.md','AGENTS.md'];
    bad=[f for f in files if 'scripts/' in Path(f).read_text(encoding='utf-8')]; assert
    not bad, bad; print('ok')"
  - python3 -c "from pathlib import Path; t=Path('README.md').read_text(encoding='utf-8').lower();
    assert 'lint' in t and 'test' in t and 'spec' in t; print('ok')"
- id: ST-005
  title: Align CI with documented scriptless commands
  status: done
  verification:
  - python3 -c "from pathlib import Path; wdir=Path('.github/workflows'); files=list(wdir.glob('*.yml'))+list(wdir.glob('*.yaml'));
    assert files, 'missing CI workflow'; txt='\n'.join(p.read_text(encoding='utf-8')
    for p in files); assert 'uvx --from . engineeringagent validate' in txt; assert
    'pytest -q' in txt; print('ok')"
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Inventory current scripts and define old-to-new command mapping

Capture each existing script behavior and map it to either a canonical CLI command or a purpose-owned automation location. This mapping is the migration contract used by docs and CI updates.

Notes:
- Added a README command-mapping table that inventories every current scripts/ entrypoint and maps each one to canonical `uvx --from . engineeringagent ...` usage or a gate-owned profile entrypoint.

Attempts: 1

## ST-002 Remove generic scripts folder and relocate only purpose-specific automation

Delete wrapper-style scripts and move any genuinely needed automation to domain-owned paths with explicit names and ownership.

Notes:
- Removed the generic `scripts/` directory, including thin wrapper entrypoints and cached bytecode artifacts.
- Relocated remaining purpose-owned automation to `harness/` (`harness/fitness-functions/validate_yaml.py` and `harness/fitness-functions/permission_probe.py`) and updated gate/pre-commit invocation paths.

Attempts: 1

## ST-003 Ensure canonical CLI coverage for workflows previously reached via scripts

Any workflow that required a script path must be reachable via stable `engineeringagent` CLI commands so contributors can run functions directly.

Notes:
- Verified canonical CLI coverage by running schema validation and gate profile commands through `uvx --from . engineeringagent ...` with successful results.

Attempts: 1

## ST-004 Rewrite docs to scriptless command usage with explicit lint/test/spec sections

Update README and reference docs to show scriptless usage, including distinct lint, test, and spec validation commands and a migration mapping table.

Notes:
- Updated `README.md`, `docs/references/uv-workflow.md`, and `AGENTS.md` to use canonical `uvx --from . engineeringagent ...` command entrypoints with no `scripts/` paths.
- Added an explicit README validation section that separates lint, test, and spec validation commands.

Attempts: 1

## ST-005 Align CI with documented scriptless commands

Update or add CI workflow definitions so automated checks execute the same command set documented for contributors.

Notes:
- Added `.github/workflows/ci.yaml` using scriptless canonical commands: `uvx --from . engineeringagent gates run --profile precommit`, `pytest -q`, and `uvx --from . engineeringagent validate`.

Attempts: 1
