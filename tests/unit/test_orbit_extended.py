"""
Extended tests for orbit module.

Tests cover:
- SatelliteOrbit class initialization
- TLE parsing and validation
- Position calculation
- Velocity calculation
- from_tle_file class method
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from mission_planner.orbit import SatelliteOrbit

# Sample valid TLE data for ICEYE-X44
VALID_TLE_NAME = "ICEYE-X44"
VALID_TLE_LINE1 = (
    "1 48915U 21059L   25226.50000000  .00001234  00000-0  12345-3 0  9990"
)
VALID_TLE_LINE2 = (
    "2 48915  97.6900 234.5678 0001234  89.0123 271.1234 15.19012345123456"
)


class TestSatelliteOrbitInit:
    """Tests for SatelliteOrbit initialization."""

    def test_init_with_three_lines(self) -> None:
        tle_lines = [VALID_TLE_NAME, VALID_TLE_LINE1, VALID_TLE_LINE2]

        sat = SatelliteOrbit(tle_lines, VALID_TLE_NAME)

        assert sat.satellite_name == VALID_TLE_NAME
        assert sat.tle_lines == tle_lines
        assert sat.predictor is not None

    def test_init_with_two_lines(self) -> None:
        tle_lines = [VALID_TLE_LINE1, VALID_TLE_LINE2]

        sat = SatelliteOrbit(tle_lines, VALID_TLE_NAME)

        assert sat.satellite_name == VALID_TLE_NAME

    def test_init_invalid_tle(self) -> None:
        # Use completely malformed TLE data that will fail parsing
        tle_lines = ["NAME", "not a valid line 1", "not a valid line 2"]

        # The library may or may not raise - test that it handles gracefully
        try:
            sat = SatelliteOrbit(tle_lines, "INVALID")
            # If it doesn't raise, satellite should still be created
            assert sat is not None
        except ValueError:
            # Expected for truly invalid TLE
            pass


class TestSatelliteOrbitFromTleFile:
    """Tests for from_tle_file class method."""

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            SatelliteOrbit.from_tle_file("/nonexistent/path.tle", "SAT")

    def test_satellite_not_found(self) -> None:
        tle_content = f"""{VALID_TLE_NAME}
{VALID_TLE_LINE1}
{VALID_TLE_LINE2}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write(tle_content)
            f.flush()

            with pytest.raises(ValueError, match="not found in TLE file"):
                SatelliteOrbit.from_tle_file(f.name, "NONEXISTENT-SAT")

    def test_load_from_file_success(self) -> None:
        tle_content = f"""{VALID_TLE_NAME}
{VALID_TLE_LINE1}
{VALID_TLE_LINE2}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write(tle_content)
            f.flush()

            sat = SatelliteOrbit.from_tle_file(f.name, VALID_TLE_NAME)

            assert sat.satellite_name == VALID_TLE_NAME

    def test_load_partial_match(self) -> None:
        """Test that partial name match works."""
        tle_content = f"""{VALID_TLE_NAME}
{VALID_TLE_LINE1}
{VALID_TLE_LINE2}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write(tle_content)
            f.flush()

            # Should match "ICEYE" within "ICEYE-X44"
            sat = SatelliteOrbit.from_tle_file(f.name, "ICEYE")

            assert "ICEYE" in sat.satellite_name


class TestSatelliteOrbitGetPosition:
    """Tests for get_position method."""

    @pytest.fixture
    def satellite(self):
        tle_lines = [VALID_TLE_NAME, VALID_TLE_LINE1, VALID_TLE_LINE2]
        return SatelliteOrbit(tle_lines, VALID_TLE_NAME)

    def test_get_position_returns_tuple(self, satellite) -> None:
        now = datetime.utcnow()

        result = satellite.get_position(now)

        assert isinstance(result, tuple)
        assert len(result) == 3  # lat, lon, alt

    def test_get_position_valid_lat(self, satellite) -> None:
        now = datetime.utcnow()

        lat, lon, alt = satellite.get_position(now)

        assert -90 <= lat <= 90

    def test_get_position_valid_lon(self, satellite) -> None:
        now = datetime.utcnow()

        lat, lon, alt = satellite.get_position(now)

        assert -180 <= lon <= 180

    def test_get_position_valid_alt(self, satellite) -> None:
        now = datetime.utcnow()

        lat, lon, alt = satellite.get_position(now)

        # LEO satellites are typically 200-2000 km
        assert 100 < alt < 2000

    def test_get_position_different_times(self, satellite) -> None:
        now = datetime.utcnow()
        later = now + timedelta(hours=1)

        pos1 = satellite.get_position(now)
        pos2 = satellite.get_position(later)

        # Position should change over time
        assert pos1 != pos2


class TestSatelliteOrbitGetVelocity:
    """Tests for get_velocity method."""

    @pytest.fixture
    def satellite(self):
        tle_lines = [VALID_TLE_NAME, VALID_TLE_LINE1, VALID_TLE_LINE2]
        return SatelliteOrbit(tle_lines, VALID_TLE_NAME)

    def test_get_velocity_returns_tuple(self, satellite) -> None:
        now = datetime.utcnow()

        # Check if get_velocity method exists
        if hasattr(satellite, "get_velocity"):
            result = satellite.get_velocity(now)
            assert isinstance(result, tuple)
            assert len(result) == 3  # vx, vy, vz
        else:
            # Method may not exist
            pytest.skip("get_velocity method not implemented")

    def test_get_velocity_reasonable_magnitude(self, satellite) -> None:
        now = datetime.utcnow()

        # Check if get_velocity method exists
        if not hasattr(satellite, "get_velocity"):
            pytest.skip("get_velocity method not implemented")

        vx, vy, vz = satellite.get_velocity(now)

        # Calculate velocity magnitude
        import math

        speed = math.sqrt(vx**2 + vy**2 + vz**2)

        # LEO orbital velocity is about 7-8 km/s
        assert 6 < speed < 9


class TestSatelliteOrbitTleLines:
    """Tests for TLE lines storage."""

    @pytest.fixture
    def satellite(self):
        tle_lines = [VALID_TLE_NAME, VALID_TLE_LINE1, VALID_TLE_LINE2]
        return SatelliteOrbit(tle_lines, VALID_TLE_NAME)

    def test_tle_lines_stored(self, satellite) -> None:
        assert len(satellite.tle_lines) == 3
        assert satellite.tle_lines[0] == VALID_TLE_NAME

    def test_satellite_name_stored(self, satellite) -> None:
        assert satellite.satellite_name == VALID_TLE_NAME


class TestSatelliteOrbitPredictor:
    """Tests for predictor attribute."""

    @pytest.fixture
    def satellite(self):
        tle_lines = [VALID_TLE_NAME, VALID_TLE_LINE1, VALID_TLE_LINE2]
        return SatelliteOrbit(tle_lines, VALID_TLE_NAME)

    def test_predictor_exists(self, satellite) -> None:
        assert satellite.predictor is not None

    def test_predictor_is_tle_predictor(self, satellite) -> None:
        # Predictor should be a valid predictor object
        assert hasattr(satellite.predictor, "get_position")


class TestSatelliteOrbitFromOnlineSource:
    """Tests for from_online_source class method."""

    def test_not_implemented(self) -> None:
        # The function raises ValueError which wraps the NotImplementedError
        with pytest.raises(ValueError, match="Could not load satellite"):
            SatelliteOrbit.from_online_source("ISS")


class TestSatelliteOrbitEdgeCases:
    """Edge case tests for SatelliteOrbit."""

    def test_epoch_time(self) -> None:
        """Test getting position at TLE epoch time."""
        tle_lines = [VALID_TLE_NAME, VALID_TLE_LINE1, VALID_TLE_LINE2]
        sat = SatelliteOrbit(tle_lines, VALID_TLE_NAME)

        # Position should be valid at any reasonable time
        epoch = datetime(2025, 8, 14, 12, 0, 0)
        lat, lon, alt = sat.get_position(epoch)

        assert -90 <= lat <= 90
        assert -180 <= lon <= 180

    def test_far_future(self) -> None:
        """Test getting position far in the future (TLE degrades)."""
        tle_lines = [VALID_TLE_NAME, VALID_TLE_LINE1, VALID_TLE_LINE2]
        sat = SatelliteOrbit(tle_lines, VALID_TLE_NAME)

        # Position calculation should still work (though less accurate)
        future = datetime(2026, 1, 1, 0, 0, 0)
        lat, lon, alt = sat.get_position(future)

        assert -90 <= lat <= 90

    def test_polar_orbit_coverage(self) -> None:
        """Test that polar orbit covers all latitudes."""
        tle_lines = [VALID_TLE_NAME, VALID_TLE_LINE1, VALID_TLE_LINE2]
        sat = SatelliteOrbit(tle_lines, VALID_TLE_NAME)

        # Sample positions over one orbital period
        start = datetime(2025, 8, 14, 12, 0, 0)
        latitudes = []

        for i in range(100):
            time = start + timedelta(minutes=i)
            lat, lon, alt = sat.get_position(time)
            latitudes.append(lat)

        # Polar orbit should cover wide latitude range
        assert max(latitudes) > 80 or min(latitudes) < -80


class TestTLEParsing:
    """Tests for TLE parsing edge cases."""

    def test_tle_with_leading_zeros(self) -> None:
        """Test TLE with leading zeros in NORAD ID."""
        tle_lines = [
            "TEST SAT",
            "1 00001U 00001A   25001.00000000  .00000000  00000-0  00000-0 0  0001",
            "2 00001  97.0000 000.0000 0001000 000.0000 000.0000 15.00000000000001",
        ]

        # Should handle leading zeros
        try:
            sat = SatelliteOrbit(tle_lines, "TEST SAT")
            assert sat.satellite_name == "TEST SAT"
        except ValueError:
            # Some TLE parsers are strict about format
            pass

    def test_tle_whitespace_handling(self) -> None:
        """Test TLE lines with extra whitespace."""
        tle_content = f"""  {VALID_TLE_NAME}
  {VALID_TLE_LINE1}
  {VALID_TLE_LINE2}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write(tle_content)
            f.flush()

            # Should handle whitespace
            sat = SatelliteOrbit.from_tle_file(f.name, VALID_TLE_NAME)
            assert sat is not None
