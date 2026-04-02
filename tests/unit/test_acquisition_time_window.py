from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.schemas.mission import AcquisitionTimeWindowRequest
from backend.time_windows import DailyTimeWindow, filter_by_daily_time_window


def _utc_dt(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_daily_time_window_filters_same_day_utc_times() -> None:
    window = DailyTimeWindow.from_strings("15:00", "17:00", "UTC")
    opportunities = [
        SimpleNamespace(max_elevation_time=_utc_dt(2026, 4, 2, 14, 30), name="before"),
        SimpleNamespace(max_elevation_time=_utc_dt(2026, 4, 2, 15, 30), name="inside"),
        SimpleNamespace(max_elevation_time=_utc_dt(2026, 4, 2, 17, 30), name="after"),
    ]

    filtered = filter_by_daily_time_window(
        opportunities,
        window=window,
        get_timestamp=lambda item: item.max_elevation_time,
    )

    assert [item.name for item in filtered] == ["inside"]


def test_daily_time_window_supports_midnight_crossing() -> None:
    window = DailyTimeWindow.from_strings("22:00", "02:00", "UTC")

    assert window.contains(_utc_dt(2026, 4, 2, 22, 30))
    assert window.contains(_utc_dt(2026, 4, 3, 1, 15))
    assert not window.contains(_utc_dt(2026, 4, 2, 15, 0))


def test_daily_time_window_converts_from_utc_into_selected_timezone() -> None:
    window = DailyTimeWindow.from_strings("15:00", "17:00", "Asia/Dubai")

    assert window.contains(_utc_dt(2026, 4, 2, 11, 30))
    assert not window.contains(_utc_dt(2026, 4, 2, 9, 30))


def test_acquisition_time_window_request_rejects_equal_start_and_end() -> None:
    with pytest.raises(ValueError, match="must be different"):
        AcquisitionTimeWindowRequest(
            enabled=True,
            start_time="15:00",
            end_time="15:00",
            timezone="UTC",
            reference="off_nadir_time",
        )
