"""Helpers for recurring daily time-of-day windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Callable, Iterable, List, TypeVar
from zoneinfo import ZoneInfo

OFF_NADIR_TIME_REFERENCE = "off_nadir_time"

T = TypeVar("T")


def parse_hhmm_time(value: str) -> time:
    """Parse a HH:MM time-of-day string."""
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError("Time must use HH:MM format")

    hour_text, minute_text = parts
    if len(hour_text) != 2 or len(minute_text) != 2:
        raise ValueError("Time must use zero-padded HH:MM format")
    if not hour_text.isdigit() or not minute_text.isdigit():
        raise ValueError("Time must use numeric HH:MM format")

    hour = int(hour_text)
    minute = int(minute_text)
    if hour < 0 or hour > 23:
        raise ValueError("Hour must be between 00 and 23")
    if minute < 0 or minute > 59:
        raise ValueError("Minute must be between 00 and 59")

    return time(hour=hour, minute=minute)


def get_time_zone(timezone_name: str) -> ZoneInfo:
    """Resolve an IANA timezone name."""
    try:
        return ZoneInfo(timezone_name)
    except Exception as exc:  # pragma: no cover - ZoneInfo raises varying subclasses
        raise ValueError(f"Invalid timezone: {timezone_name}") from exc


def ensure_utc_datetime(value: datetime) -> datetime:
    """Normalize datetimes to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class DailyTimeWindow:
    """A recurring daily time-of-day window in a specific timezone."""

    start_time: time
    end_time: time
    timezone_name: str = "UTC"
    reference: str = OFF_NADIR_TIME_REFERENCE

    @classmethod
    def from_strings(
        cls,
        start_time: str,
        end_time: str,
        timezone_name: str = "UTC",
        reference: str = OFF_NADIR_TIME_REFERENCE,
    ) -> "DailyTimeWindow":
        """Build a validated window from request-style strings."""
        start = parse_hhmm_time(start_time)
        end = parse_hhmm_time(end_time)
        get_time_zone(timezone_name)

        if start == end:
            raise ValueError(
                "Acquisition time window start and end must be different"
            )
        if reference != OFF_NADIR_TIME_REFERENCE:
            raise ValueError(
                f"Unsupported acquisition time window reference: {reference}"
            )

        return cls(
            start_time=start,
            end_time=end,
            timezone_name=timezone_name,
            reference=reference,
        )

    @property
    def timezone(self) -> ZoneInfo:
        return get_time_zone(self.timezone_name)

    def contains(self, value: datetime) -> bool:
        """Check whether a UTC datetime falls inside the local daily window."""
        local_time = ensure_utc_datetime(value).astimezone(self.timezone).timetz().replace(
            tzinfo=None
        )
        if self.start_time < self.end_time:
            return self.start_time <= local_time <= self.end_time
        return local_time >= self.start_time or local_time <= self.end_time

    def label(self) -> str:
        """Return a compact operator-facing label."""
        return f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"


def filter_by_daily_time_window(
    items: Iterable[T],
    *,
    window: DailyTimeWindow,
    get_timestamp: Callable[[T], datetime],
) -> List[T]:
    """Keep only items whose timestamp falls inside the local daily window."""
    return [item for item in items if window.contains(get_timestamp(item))]
