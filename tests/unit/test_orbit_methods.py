"""
Tests for SatelliteOrbit methods.

Tests cover:
- get_position method
- get_ground_track method
- get_orbital_period method
- is_above_horizon method
- __repr__ method
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

SAMPLE_TLE = "\n".join(SAMPLE_TLE_LINES)


class TestGetPosition:
    """Tests for get_position method."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_returns_tuple(self, satellite) -> None:
        pos = satellite.get_position(datetime.utcnow())

        assert isinstance(pos, tuple)
        assert len(pos) == 3

    def test_latitude_in_range(self, satellite) -> None:
        lat, lon, alt = satellite.get_position(datetime.utcnow())

        assert -90 <= lat <= 90

    def test_longitude_in_range(self, satellite) -> None:
        lat, lon, alt = satellite.get_position(datetime.utcnow())

        assert -180 <= lon <= 180

    def test_altitude_positive(self, satellite) -> None:
        lat, lon, alt = satellite.get_position(datetime.utcnow())

        assert alt > 0

    def test_position_changes_over_time(self, satellite) -> None:
        t1 = datetime.utcnow()
        t2 = t1 + timedelta(minutes=10)

        pos1 = satellite.get_position(t1)
        pos2 = satellite.get_position(t2)

        assert pos1 != pos2


class TestGetGroundTrack:
    """Tests for get_ground_track method."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_returns_list(self, satellite) -> None:
        start = datetime.utcnow()
        end = start + timedelta(minutes=10)

        track = satellite.get_ground_track(start, end)

        assert isinstance(track, list)

    def test_has_points(self, satellite) -> None:
        start = datetime.utcnow()
        end = start + timedelta(minutes=10)

        track = satellite.get_ground_track(start, end)

        assert len(track) > 0

    def test_point_format(self, satellite) -> None:
        start = datetime.utcnow()
        end = start + timedelta(minutes=5)

        track = satellite.get_ground_track(start, end)

        # Each point should be (timestamp, lat, lon, alt)
        if track:
            point = track[0]
            assert len(point) == 4
            assert isinstance(point[0], datetime)

    def test_custom_time_step(self, satellite) -> None:
        start = datetime.utcnow()
        end = start + timedelta(minutes=10)

        track_1min = satellite.get_ground_track(start, end, time_step_minutes=1.0)
        track_5min = satellite.get_ground_track(start, end, time_step_minutes=5.0)

        # Smaller time step should have more points
        assert len(track_1min) > len(track_5min)


class TestGetOrbitalPeriod:
    """Tests for get_orbital_period method."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_returns_timedelta(self, satellite) -> None:
        period = satellite.get_orbital_period()

        assert isinstance(period, timedelta)

    def test_reasonable_value(self, satellite) -> None:
        period = satellite.get_orbital_period()

        # ISS orbital period is about 92 minutes
        period_minutes = period.total_seconds() / 60

        # Should be between 80 and 120 minutes for LEO
        assert 80 < period_minutes < 120


class TestRepr:
    """Tests for __repr__ method."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_repr_contains_name(self, satellite) -> None:
        result = repr(satellite)

        assert "ISS (ZARYA)" in result

    def test_repr_contains_class_name(self, satellite) -> None:
        result = repr(satellite)

        assert "SatelliteOrbit" in result

    def test_repr_contains_period(self, satellite) -> None:
        result = repr(satellite)

        assert "period" in result


class TestSatelliteOrbitInit:
    """Tests for SatelliteOrbit initialization."""

    def test_init_stores_name(self) -> None:
        sat = SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

        assert sat.satellite_name == "ISS (ZARYA)"

    def test_init_creates_predictor(self) -> None:
        sat = SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

        assert sat.predictor is not None

    def test_init_stores_tle_lines(self) -> None:
        sat = SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

        assert sat.tle_lines == SAMPLE_TLE_LINES


class TestSatelliteOrbitFromFile:
    """Tests for from_tle_file class method."""

    def test_loads_from_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write(SAMPLE_TLE)
            filepath = f.name

        sat = SatelliteOrbit.from_tle_file(filepath, "ISS (ZARYA)")

        assert sat.satellite_name == "ISS (ZARYA)"

        Path(filepath).unlink()

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            SatelliteOrbit.from_tle_file("/nonexistent/file.tle", "TEST")


class TestSatelliteOrbitAttributes:
    """Tests for SatelliteOrbit attributes."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_has_satellite_name(self, satellite) -> None:
        assert hasattr(satellite, "satellite_name")

    def test_has_predictor(self, satellite) -> None:
        assert hasattr(satellite, "predictor")

    def test_has_tle_lines(self, satellite) -> None:
        assert hasattr(satellite, "tle_lines")
