"""Progress artifact helpers.

This subpackage groups together the shared helpers for constructing progress artifact
paths and for appending to progress artifacts. It is intentionally independent of
loop runtime internals so it can be imported by both loop telemetry and reviewers.
"""

from __future__ import annotations
