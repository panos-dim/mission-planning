"""
Tests for orbit.py calculation methods.

Tests cover:
- Position calculations
- Ground track generation
- Orbital period
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


class TestSatelliteOrbitPosition:
    """Tests for position calculation."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_get_position_returns_tuple(self, satellite) -> None:
        now = datetime.utcnow()

        result = satellite.get_position(now)

        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_position_lat_in_range(self, satellite) -> None:
        now = datetime.utcnow()

        lat, lon, alt = satellite.get_position(now)

        assert -90 <= lat <= 90

    def test_position_lon_in_range(self, satellite) -> None:
        now = datetime.utcnow()

        lat, lon, alt = satellite.get_position(now)

        assert -180 <= lon <= 180

    def test_position_alt_positive(self, satellite) -> None:
        now = datetime.utcnow()

        lat, lon, alt = satellite.get_position(now)

        assert alt > 0

    def test_iss_altitude_range(self, satellite) -> None:
        now = datetime.utcnow()

        lat, lon, alt = satellite.get_position(now)

        # ISS altitude typically 400-420 km
        assert 350 < alt < 450


class TestSatelliteOrbitGroundTrack:
    """Tests for ground track generation."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_ground_track_returns_list(self, satellite) -> None:
        start = datetime.utcnow()
        end = start + timedelta(minutes=10)

        result = satellite.get_ground_track(start, end)

        assert isinstance(result, list)

    def test_ground_track_has_points(self, satellite) -> None:
        start = datetime.utcnow()
        end = start + timedelta(minutes=10)

        result = satellite.get_ground_track(start, end)

        assert len(result) > 0

    def test_ground_track_point_structure(self, satellite) -> None:
        start = datetime.utcnow()
        end = start + timedelta(minutes=5)

        result = satellite.get_ground_track(start, end)

        # Each point should have (time, lat, lon, alt)
        assert len(result[0]) >= 3

    def test_short_duration(self, satellite) -> None:
        start = datetime.utcnow()
        end = start + timedelta(seconds=30)

        result = satellite.get_ground_track(start, end)

        assert len(result) >= 1


class TestSatelliteOrbitPeriod:
    """Tests for orbital period calculation."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_period_returns_timedelta(self, satellite) -> None:
        result = satellite.get_orbital_period()

        assert isinstance(result, timedelta)

    def test_iss_period_range(self, satellite) -> None:
        result = satellite.get_orbital_period()

        # ISS period ~92 minutes
        period_min = result.total_seconds() / 60
        assert 85 < period_min < 100


class TestSatelliteOrbitRepr:
    """Tests for string representation."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_repr_contains_name(self, satellite) -> None:
        result = repr(satellite)

        assert "ISS" in result

    def test_str_contains_name(self, satellite) -> None:
        result = str(satellite)

        assert "ISS" in result or "SatelliteOrbit" in result


class TestSatelliteOrbitFromTLE:
    """Tests for from_tle_file class method."""

    def test_from_tle_file_success(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write("\n".join(SAMPLE_TLE_LINES))
            filepath = f.name

        sat = SatelliteOrbit.from_tle_file(filepath, "ISS")

        assert sat.satellite_name is not None

        Path(filepath).unlink()

    def test_from_tle_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            SatelliteOrbit.from_tle_file("/nonexistent/file.tle", "TEST")

    def test_from_tle_file_satellite_not_found(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write("\n".join(SAMPLE_TLE_LINES))
            filepath = f.name

        with pytest.raises(ValueError, match="not found"):
            SatelliteOrbit.from_tle_file(filepath, "NONEXISTENT")

        Path(filepath).unlink()


class TestSatelliteOrbitTLEParsing:
    """Tests for TLE parsing."""

    def test_three_line_format(self) -> None:
        tle = [
            "SATELLITE NAME",
            "1 25544U 98067A   21275.52531015  .00001296  00000-0  29941-4 0  9998",
            "2 25544  51.6442 208.5455 0003525 319.8489 175.3714 15.48919755305637",
        ]

        sat = SatelliteOrbit(tle, "TEST")

        assert sat.tle_lines == tle

    def test_two_line_format(self) -> None:
        tle = [
            "1 25544U 98067A   21275.52531015  .00001296  00000-0  29941-4 0  9998",
            "2 25544  51.6442 208.5455 0003525 319.8489 175.3714 15.48919755305637",
        ]

        sat = SatelliteOrbit(tle, "TEST")

        assert sat.tle_lines == tle
