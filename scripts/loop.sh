#!/usr/bin/env bash
set -euo pipefail

uv run python scripts/loop.py "$@"
