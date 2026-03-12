---
plan_id: FEAT-010
feature_id: FEAT-010
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add Ruff and pytest tooling configuration
  status: done
  verification:
  - uv sync
  - uv run ruff --version
  - uv run pytest --version
- id: ST-002
  title: Add Ruff and pytest gates to precommit profile
  status: done
  verification:
  - python3 -c "from pathlib import Path; import yaml; cfg=yaml.safe_load(Path('harness/gates.yaml').read_text(encoding='utf-8'));
    pre=cfg['profiles']['precommit']; assert 'ruff_validate' in pre and 'pytest_validate'
    in pre; assert cfg['gates']['ruff_validate']['run'] == 'uv run ruff check src/engineeringagent';
    assert cfg['gates']['pytest_validate']['run'] == 'uv run pytest -q'; print('ok')"
  - uvx --from . engineeringagent gates list
- id: ST-003
  title: Enforce Google docstrings for exported src functions via Ruff
  status: done
  verification:
  - uv run ruff check src/engineeringagent --select D103,D417
  - uv run ruff check src/engineeringagent
- id: ST-004
  title: Add Python uv+Ruff guide and AGENTS reference
  status: done
  verification:
  - python3 -c "from pathlib import Path; guide=Path('docs/references/python-uv-ruff.md');
    agents=Path('AGENTS.md'); assert guide.exists(); gt=guide.read_text(encoding='utf-8').lower();
    at=agents.read_text(encoding='utf-8').lower(); assert 'uv' in gt and 'ruff' in
    gt and 'pytest' in gt; assert 'python-uv-ruff.md' in at; print('ok')"
- id: ST-005
  title: Update README and uv workflow docs for new checks
  status: done
  verification:
  - python3 -c "from pathlib import Path; files=['README.md','docs/references/uv-workflow.md'];
    text='\n'.join(Path(f).read_text(encoding='utf-8').lower() for f in files); assert
    'ruff' in text and 'pytest' in text and 'precommit' in text; print('ok')"
- id: ST-006
  title: Run full precommit profile verification
  status: done
  verification:
  - uvx --from . engineeringagent gates run --profile precommit
  - uv run ruff check src/engineeringagent
  - uv run pytest -q
- id: ST-007
  title: Scaffold default harness gates file for users
  status: done
  verification:
  - python3 -c "import tempfile, shutil; from pathlib import Path; root=Path(tempfile.mkdtemp());
    src=Path('.'); shutil.copytree(src/'src', root/'src', dirs_exist_ok=True); shutil.copy2(src/'pyproject.toml',
    root/'pyproject.toml'); result=__import__('subprocess').run(['uvx','--refresh','--from','.','engineeringagent','--project-root',str(root),'gates','list'],
    cwd='.', capture_output=True, text=True); assert result.returncode == 0; cfg=root/'harness'/'gates.yaml';
    assert cfg.exists(); txt=cfg.read_text(encoding='utf-8').lower(); assert 'precommit'
    in txt and 'loop_fast' in txt; print('ok')"
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add Ruff and pytest tooling configuration

Ensure project tooling includes Ruff and pytest and that lock/sync workflows remain uv-native.

## ST-002 Add Ruff and pytest gates to precommit profile

Extend `harness/gates.yaml` with `ruff_validate` and `pytest_validate`, then include both in `profiles.precommit`.

## ST-003 Enforce Google docstrings for exported src functions via Ruff

Configure Ruff pydocstyle with Google convention and required rules for public functions, then add missing docstrings in `src/engineeringagent` until clean.

## ST-004 Add Python uv+Ruff guide and AGENTS reference

Add a concise Python contributor guide covering uv workflow, Ruff usage, and docstring expectations, then link it from AGENTS.md so it is discoverable in the default read order.

## ST-005 Update README and uv workflow docs for new checks

Update README.md and docs/references/uv-workflow.md to reflect Ruff + pytest checks and command usage within precommit and daily workflow docs.

## ST-006 Run full precommit profile verification

Confirm all configured precommit gates run successfully with the new checks enabled.

## ST-007 Scaffold default harness gates file for users

Define and implement a bootstrap path that creates harness/gates.yaml with default profiles and gate commands when the file is absent, so new users can run documented gate workflows immediately.
