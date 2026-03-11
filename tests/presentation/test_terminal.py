from __future__ import annotations

from engineeringagent.presentation.terminal import stdout_is_tty


def test_stdout_is_tty_accepts_opaque_non_stream_objects() -> None:
    assert stdout_is_tty("tty-sentinel") is False
