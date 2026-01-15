"""
Advanced tests for orbit module.

Tests cover:
- SatelliteOrbit initialization
- Position and velocity calculations
- Orbital period calculations
- Ground track generation
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mission_planner.orbit import SatelliteOrbit

# Sample TLE data for testing
SAMPLE_TLE = """ISS (ZARYA)
1 25544U 98067A   21275.52531015  .00001296  00000-0  29941-4 0  9998
2 25544  51.6442 208.5455 0003525 319.8489 175.3714 15.48919755305637"""

SAMPLE_TLE_LINES = [
    "ISS (ZARYA)",
    "1 25544U 98067A   21275.52531015  .00001296  00000-0  29941-4 0  9998",
    "2 25544  51.6442 208.5455 0003525 319.8489 175.3714 15.48919755305637",
]


class TestSatelliteOrbitInit:
    """Tests for SatelliteOrbit initialization."""

    def test_init_with_tle_lines(self) -> None:
        sat = SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

        assert sat.satellite_name == "ISS (ZARYA)"

    def test_satellite_name_stored(self) -> None:
        sat = SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

        assert hasattr(sat, "satellite_name")
        assert sat.satellite_name is not None

    def test_predictor_created(self) -> None:
        sat = SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

        assert hasattr(sat, "predictor")
        assert sat.predictor is not None


class TestSatelliteOrbitFromTleFile:
    """Tests for from_tle_file class method."""

    def test_load_from_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write(SAMPLE_TLE)
            filepath = f.name

        sat = SatelliteOrbit.from_tle_file(filepath, "ISS (ZARYA)")

        assert sat.satellite_name == "ISS (ZARYA)"

        # Cleanup
        Path(filepath).unlink()

    def test_load_specific_satellite(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write(SAMPLE_TLE)
            filepath = f.name

        sat = SatelliteOrbit.from_tle_file(filepath, satellite_name="ISS (ZARYA)")

        assert sat.satellite_name == "ISS (ZARYA)"

        # Cleanup
        Path(filepath).unlink()


class TestSatelliteOrbitGetPosition:
    """Tests for get_position method."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_get_position_returns_tuple(self, satellite) -> None:
        pos = satellite.get_position(datetime.utcnow())

        assert isinstance(pos, tuple)
        assert len(pos) == 3  # lat, lon, alt

    def test_position_values_in_range(self, satellite) -> None:
        lat, lon, alt = satellite.get_position(datetime.utcnow())

        # Latitude should be -90 to 90
        assert -90 <= lat <= 90

        # Longitude should be -180 to 180
        assert -180 <= lon <= 180

        # Altitude should be positive (in km, ISS ~400km)
        assert alt > 0

    def test_position_changes_over_time(self, satellite) -> None:
        now = datetime.utcnow()
        later = now + timedelta(minutes=10)

        pos1 = satellite.get_position(now)
        pos2 = satellite.get_position(later)

        # Position should change
        assert pos1 != pos2


class TestSatelliteOrbitGetOrbitalPeriod:
    """Tests for get_orbital_period method."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_orbital_period_returns_timedelta(self, satellite) -> None:
        period = satellite.get_orbital_period()

        assert isinstance(period, timedelta)

    def test_orbital_period_reasonable_value(self, satellite) -> None:
        period = satellite.get_orbital_period()

        # ISS orbital period is about 92 minutes
        period_minutes = period.total_seconds() / 60

        # Should be between 80 and 120 minutes for LEO
        assert 80 < period_minutes < 120


class TestSatelliteOrbitGetGroundTrack:
    """Tests for get_ground_track method."""

    @pytest.fixture
    def satellite(self):
        return SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

    def test_ground_track_returns_list(self, satellite) -> None:
        start = datetime.utcnow()
        end = start + timedelta(hours=1)

        track = satellite.get_ground_track(start, end)

        assert isinstance(track, list)

    def test_ground_track_has_points(self, satellite) -> None:
        start = datetime.utcnow()
        end = start + timedelta(hours=1)

        track = satellite.get_ground_track(start, end)

        assert len(track) > 0

    def test_ground_track_point_format(self, satellite) -> None:
        start = datetime.utcnow()
        end = start + timedelta(minutes=10)

        track = satellite.get_ground_track(start, end)

        # Each point should be (time, lat, lon, alt)
        if track:
            point = track[0]
            assert len(point) == 4


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
        assert hasattr(satellite, "tle_line1") or hasattr(satellite, "tle_lines")


class TestSatelliteOrbitEdgeCases:
    """Edge case tests for SatelliteOrbit."""

    def test_position_at_epoch(self) -> None:
        sat = SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

        # Position at current time should work
        pos = sat.get_position(datetime.utcnow())

        assert pos is not None

    def test_multiple_position_calls(self) -> None:
        sat = SatelliteOrbit(SAMPLE_TLE_LINES, "ISS (ZARYA)")

        # Multiple calls should all work
        for i in range(10):
            t = datetime.utcnow() + timedelta(minutes=i * 10)
            pos = sat.get_position(t)
            assert pos is not None
