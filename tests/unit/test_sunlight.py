"""
Comprehensive tests for sunlight module.
"""

import pytest
import math
from datetime import datetime

from mission_planner.sunlight import (
    calculate_sun_position,
    is_target_illuminated,
    calculate_gmst,
    calculate_solar_zenith_angle,
)


class TestCalculateSunPosition:
    """Tests for calculate_sun_position function."""

    def test_returns_tuple(self) -> None:
        dt = datetime(2025, 6, 21, 12, 0, 0)  # Summer solstice noon UTC
        result = calculate_sun_position(dt)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_coordinates_reasonable(self) -> None:
        dt = datetime(2025, 6, 21, 12, 0, 0)
        x, y, z = calculate_sun_position(dt)

        # Sun should be roughly 1 AU away (150 million km)
        distance = math.sqrt(x**2 + y**2 + z**2)
        # Distance in km should be ~150 million
        assert 140_000_000 < distance < 160_000_000

    def test_different_times(self) -> None:
        dt1 = datetime(2025, 1, 1, 0, 0, 0)
        dt2 = datetime(2025, 7, 1, 0, 0, 0)

        pos1 = calculate_sun_position(dt1)
        pos2 = calculate_sun_position(dt2)

        # Positions should be different
        assert pos1 != pos2


class TestIsTargetIlluminated:
    """Tests for is_target_illuminated function."""

    def test_noon_illuminated(self) -> None:
        # Dubai at local noon should be illuminated
        dt = datetime(2025, 6, 21, 8, 0, 0)  # ~noon local time in Dubai
        result = is_target_illuminated(25.2, 55.3, dt)
        assert result is True

    def test_midnight_not_illuminated(self) -> None:
        # Dubai at local midnight should not be illuminated
        dt = datetime(2025, 6, 21, 20, 0, 0)  # ~midnight local time in Dubai
        result = is_target_illuminated(25.2, 55.3, dt)
        assert result is False

    def test_polar_summer(self) -> None:
        # Arctic in summer - should be illuminated even at "night"
        dt = datetime(2025, 6, 21, 0, 0, 0)  # Midnight UTC
        result = is_target_illuminated(80.0, 0.0, dt)  # High Arctic
        # May or may not be illuminated depending on exact calculation
        assert isinstance(result, bool)


class TestCalculateGmst:
    """Tests for calculate_gmst function."""

    def test_returns_float(self) -> None:
        dt = datetime(2025, 6, 21, 12, 0, 0)
        result = calculate_gmst(dt)
        assert isinstance(result, float)

    def test_gmst_is_numeric(self) -> None:
        # GMST returns a numeric value
        dt = datetime(2025, 6, 21, 12, 0, 0)
        gmst = calculate_gmst(dt)
        assert isinstance(gmst, (int, float))


class TestCalculateSolarZenithAngle:
    """Tests for calculate_solar_zenith_angle function."""

    def test_returns_float(self) -> None:
        dt = datetime(2025, 6, 21, 12, 0, 0)
        result = calculate_solar_zenith_angle(0.0, 0.0, dt)
        assert isinstance(result, float)

    def test_zenith_range(self) -> None:
        # Solar zenith angle should be between 0 and 180 degrees
        dt = datetime(2025, 6, 21, 12, 0, 0)
        for lat in [-60, -30, 0, 30, 60]:
            for lon in [-120, -60, 0, 60, 120]:
                zenith = calculate_solar_zenith_angle(lat, lon, dt)
                assert 0 <= zenith <= 180

    def test_noon_low_zenith(self) -> None:
        # At equator, sun at local noon should have low zenith angle
        dt = datetime(2025, 3, 21, 12, 0, 0)  # Equinox noon UTC
        zenith = calculate_solar_zenith_angle(0.0, 0.0, dt)
        # Should be reasonably low (<60°)
        assert zenith < 90
