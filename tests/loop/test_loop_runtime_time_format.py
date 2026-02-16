from __future__ import annotations

from datetime import datetime, timezone


def test_utc_iso_from_epoch_sec_formats_utc_z_with_second_precision() -> None:
    from engineeringagent.loop_runtime.time_format import utc_iso_from_epoch_sec

    epoch_sec = int(datetime(2026, 2, 15, 13, 45, 11, tzinfo=timezone.utc).timestamp())
    assert utc_iso_from_epoch_sec(epoch_sec) == "2026-02-15T13:45:11Z"
