"""
Tests for SatelliteOrbit edge cases.

Tests cover:
- TLE parsing edge cases
- from_tle_file error handling
- from_online_source method
- is_above_horizon method
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mission_planner.orbit import SatelliteOrbit

SAMPLE_TLE_LINES = [
    "ISS (ZARYA)",
    "1 25544U 98067A   21275.52531015  .00001296  00000-0  29941-4 0  9998",
    "2 25544  51.6442 208.5455 0003525 319.8489 175.3714 15.48919755305637",
]

TWO_LINE_TLE = [
    "1 25544U 98067A   21275.52531015  .00001296  00000-0  29941-4 0  9998",
    "2 25544  51.6442 208.5455 0003525 319.8489 175.3714 15.48919755305637",
]


class TestSatelliteOrbitInit:
    """Tests for SatelliteOrbit initialization edge cases."""

    def test_init_with_two_line_format(self) -> None:
        sat = SatelliteOrbit(TWO_LINE_TLE, "ISS")

        assert sat.satellite_name == "ISS"

    def test_init_stores_predictor(self) -> None:
        sat = SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

        assert sat.predictor is not None

    def test_init_with_three_lines(self) -> None:
        sat = SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

        assert len(sat.tle_lines) == 3


class TestFromTleFile:
    """Tests for from_tle_file class method."""

    def test_satellite_not_found(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write("\n".join(SAMPLE_TLE_LINES))
            filepath = f.name

        with pytest.raises(ValueError, match="not found"):
            SatelliteOrbit.from_tle_file(filepath, "NONEXISTENT")

        Path(filepath).unlink()

    def test_multiple_satellites_in_file(self) -> None:
        multi_tle = """ISS (ZARYA)
1 25544U 98067A   21275.52531015  .00001296  00000-0  29941-4 0  9998
2 25544  51.6442 208.5455 0003525 319.8489 175.3714 15.48919755305637
NOAA 18
1 28654U 05018A   21275.50000000  .00000050  00000-0  40000-4 0  9999
2 28654  99.0000 200.0000 0014000 100.0000 260.0000 14.12500000000000"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write(multi_tle)
            filepath = f.name

        sat = SatelliteOrbit.from_tle_file(filepath, "ISS")

        assert "ISS" in sat.satellite_name

        Path(filepath).unlink()

    def test_case_insensitive_search(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write("\n".join(SAMPLE_TLE_LINES))
            filepath = f.name

        sat = SatelliteOrbit.from_tle_file(filepath, "iss")

        assert sat is not None

        Path(filepath).unlink()


class TestFromOnlineSource:
    """Tests for from_online_source class method."""

    def test_not_implemented(self) -> None:
        with pytest.raises(ValueError):
            SatelliteOrbit.from_online_source("ISS")

    def test_with_custom_url(self) -> None:
        with pytest.raises(ValueError):
            SatelliteOrbit.from_online_source("ISS", "https://example.com/tle")


class TestIsAboveHorizon:
    """Tests for is_above_horizon method."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_returns_bool(self, satellite) -> None:
        from orbit_predictor.locations import Location

        location = Location("Test", 45.0, 10.0, 0)
        result = satellite.is_above_horizon(location, datetime.utcnow())

        assert isinstance(result, bool)


class TestGetPositionErrors:
    """Tests for get_position error handling."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_position_at_past_date(self, satellite) -> None:
        # Very old date might cause issues
        past_date = datetime(2020, 1, 1, 12, 0, 0)

        # Should still return a position (TLE propagation)
        pos = satellite.get_position(past_date)

        assert pos is not None
        assert len(pos) == 3


class TestGetGroundTrackEdgeCases:
    """Tests for get_ground_track edge cases."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_very_short_duration(self, satellite) -> None:
        start = datetime.utcnow()
        end = start + timedelta(seconds=30)

        track = satellite.get_ground_track(start, end, time_step_minutes=1.0)

        # Should have at least 1 point
        assert len(track) >= 1

    def test_zero_duration(self, satellite) -> None:
        now = datetime.utcnow()

        track = satellite.get_ground_track(now, now)

        # Should have exactly 1 point (start = end)
        assert len(track) == 1


class TestOrbitalPeriodEdgeCases:
    """Tests for get_orbital_period edge cases."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_period_is_timedelta(self, satellite) -> None:
        period = satellite.get_orbital_period()

        assert isinstance(period, timedelta)

    def test_period_in_leo_range(self, satellite) -> None:
        period = satellite.get_orbital_period()

        # LEO satellites have periods between 80-130 minutes
        period_minutes = period.total_seconds() / 60

        assert 80 < period_minutes < 130


class TestSatelliteOrbitAttributes:
    """Tests for SatelliteOrbit attribute access."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_tle_lines_stored(self, satellite) -> None:
        assert satellite.tle_lines == SAMPLE_TLE_LINES

    def test_predictor_available(self, satellite) -> None:
        assert satellite.predictor is not None

    def test_satellite_name_stored(self, satellite) -> None:
        assert satellite.satellite_name == "ISS (ZARYA)"
