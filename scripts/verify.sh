#!/usr/bin/env bash
set -euo pipefail

uv run python scripts/gates.py run --profile loop_fast
