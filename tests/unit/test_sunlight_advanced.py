"""
Advanced tests for sunlight module.

Tests cover:
- Sun position calculation
- Target illumination checks
- GMST calculation
"""

import math
from datetime import datetime, timedelta

import pytest

from mission_planner.sunlight import (
    AU_KM,
    EARTH_RADIUS_KM,
    calculate_gmst,
    calculate_solar_zenith_angle,
    calculate_sun_position,
    is_target_illuminated,
)


class TestSunPositionCalculation:
    """Tests for calculate_sun_position function."""

    def test_returns_tuple(self) -> None:
        timestamp = datetime(2025, 1, 15, 12, 0, 0)

        result = calculate_sun_position(timestamp)

        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_sun_distance_approximately_1_au(self) -> None:
        timestamp = datetime(2025, 1, 15, 12, 0, 0)

        x, y, z = calculate_sun_position(timestamp)

        distance = math.sqrt(x**2 + y**2 + z**2)

        # Should be approximately 1 AU (within 2%)
        assert 0.98 * AU_KM < distance < 1.02 * AU_KM

    def test_different_times_different_positions(self) -> None:
        t1 = datetime(2025, 1, 15, 12, 0, 0)
        t2 = datetime(2025, 7, 15, 12, 0, 0)

        pos1 = calculate_sun_position(t1)
        pos2 = calculate_sun_position(t2)

        # Positions should be different (6 months apart)
        assert pos1 != pos2

    def test_handles_timezone_aware(self) -> None:
        from datetime import timezone

        timestamp = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        # Should not raise
        result = calculate_sun_position(timestamp)

        assert result is not None


class TestCalculateGmst:
    """Tests for calculate_gmst function."""

    def test_returns_float(self) -> None:
        timestamp = datetime(2025, 1, 15, 12, 0, 0)

        result = calculate_gmst(timestamp)

        assert isinstance(result, float)

    def test_gmst_in_valid_range(self) -> None:
        timestamp = datetime(2025, 1, 15, 12, 0, 0)

        result = calculate_gmst(timestamp)

        # GMST should be in degrees (0-360 range, but can be negative)
        assert -360 <= result <= 720

    def test_gmst_changes_with_time(self) -> None:
        t1 = datetime(2025, 1, 15, 0, 0, 0)
        t2 = datetime(2025, 1, 15, 12, 0, 0)

        gmst1 = calculate_gmst(t1)
        gmst2 = calculate_gmst(t2)

        # GMST should change by approximately 180 degrees in 12 hours
        diff = abs(gmst2 - gmst1)
        assert 170 < diff < 190


class TestIsTargetIlluminated:
    """Tests for is_target_illuminated function."""

    def test_returns_bool(self) -> None:
        result = is_target_illuminated(45.0, 10.0, datetime(2025, 6, 21, 12, 0, 0))

        assert isinstance(result, bool)

    def test_summer_noon_illuminated(self) -> None:
        # Summer solstice at noon in Europe - should be illuminated
        result = is_target_illuminated(
            45.0,
            10.0,  # Northern Italy
            datetime(2025, 6, 21, 10, 0, 0),  # ~noon local time
        )

        # High probability of being illuminated
        assert result is True

    def test_winter_midnight_not_illuminated(self) -> None:
        # Midnight in winter - should not be illuminated
        result = is_target_illuminated(
            45.0, 10.0, datetime(2025, 1, 15, 1, 0, 0)  # ~2am local time
        )

        assert result is False

    def test_with_min_sun_elevation(self) -> None:
        # Test with minimum sun elevation requirement
        result = is_target_illuminated(
            45.0, 10.0, datetime(2025, 6, 21, 12, 0, 0), min_sun_elevation=30.0
        )

        assert isinstance(result, bool)


class TestCalculateSolarZenithAngle:
    """Tests for calculate_solar_zenith_angle function."""

    def test_returns_float(self) -> None:
        result = calculate_solar_zenith_angle(
            45.0, 10.0, datetime(2025, 6, 21, 12, 0, 0)
        )

        assert isinstance(result, float)

    def test_zenith_in_valid_range(self) -> None:
        result = calculate_solar_zenith_angle(
            45.0, 10.0, datetime(2025, 6, 21, 12, 0, 0)
        )

        # Zenith angle should be between 0 and 180
        assert 0 <= result <= 180

    def test_noon_summer_low_zenith(self) -> None:
        # Summer noon should have low zenith angle (sun high in sky)
        result = calculate_solar_zenith_angle(
            45.0, 0.0, datetime(2025, 6, 21, 12, 0, 0)  # Prime meridian  # Solar noon
        )

        # Zenith < 90 means sun above horizon
        assert result < 90

    def test_midnight_high_zenith(self) -> None:
        # Midnight should have high zenith angle (sun below horizon)
        result = calculate_solar_zenith_angle(
            45.0, 0.0, datetime(2025, 6, 21, 0, 0, 0)  # Midnight
        )

        # Zenith > 90 means sun below horizon
        assert result > 90


class TestSunlightConstants:
    """Tests for module constants."""

    def test_earth_radius_value(self) -> None:
        assert 6370 < EARTH_RADIUS_KM < 6380

    def test_au_value(self) -> None:
        # 1 AU is approximately 150 million km
        assert 149000000 < AU_KM < 150000000


class TestSunPositionSeasonalVariation:
    """Tests for seasonal variation in sun position."""

    def test_summer_vs_winter_different(self) -> None:
        summer = datetime(2025, 6, 21, 12, 0, 0)
        winter = datetime(2025, 12, 21, 12, 0, 0)

        pos_summer = calculate_sun_position(summer)
        pos_winter = calculate_sun_position(winter)

        # Positions should be different
        assert pos_summer != pos_winter

    def test_equinox_positions(self) -> None:
        spring = datetime(2025, 3, 20, 12, 0, 0)
        fall = datetime(2025, 9, 22, 12, 0, 0)

        pos_spring = calculate_sun_position(spring)
        pos_fall = calculate_sun_position(fall)

        # Both valid positions
        assert all(isinstance(v, float) for v in pos_spring)
        assert all(isinstance(v, float) for v in pos_fall)
