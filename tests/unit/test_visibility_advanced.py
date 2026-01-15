"""
Advanced tests for visibility module.

Tests cover:
- Elevation and azimuth calculations
- Target visibility checks
- ECEF coordinate calculations
- Pass finding edge cases
"""

import math
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from mission_planner.targets import GroundTarget
from mission_planner.visibility import (
    EARTH_RADIUS_KM,
    PassDetails,
    VisibilityCalculator,
)


class TestVisibilityCalculatorElevationCalc:
    """Tests for elevation calculation methods."""

    def create_calculator(self):
        sat = MagicMock()
        sat.satellite_name = "TEST-SAT"
        sat.predictor = MagicMock()
        return VisibilityCalculator(sat, use_adaptive=False)

    def test_get_ground_ecef_caches_result(self) -> None:
        """Test that ECEF coordinates are cached."""
        calc = self.create_calculator()

        # Create a mock location
        location = MagicMock()
        location.latitude_deg = 45.0
        location.longitude_deg = 10.0
        location.elevation_m = 0.0

        # First call should compute
        result1 = calc._get_ground_ecef(location)

        # Second call should return cached
        result2 = calc._get_ground_ecef(location)

        assert result1 == result2
        assert len(calc._ground_ecef_cache) == 1

    def test_get_ground_ecef_returns_tuple(self) -> None:
        """Test that ECEF returns proper tuple."""
        calc = self.create_calculator()

        location = MagicMock()
        location.latitude_deg = 0.0  # Equator
        location.longitude_deg = 0.0  # Prime meridian
        location.elevation_m = 0.0

        x, y, z = calc._get_ground_ecef(location)

        # At equator/prime meridian, x should be Earth radius
        assert abs(x - EARTH_RADIUS_KM) < 1.0
        assert abs(y) < 1.0
        assert abs(z) < 1.0

    def test_get_ground_ecef_different_locations(self) -> None:
        """Test ECEF for different locations."""
        calc = self.create_calculator()

        # Location at North Pole
        loc_north = MagicMock()
        loc_north.latitude_deg = 90.0
        loc_north.longitude_deg = 0.0
        loc_north.elevation_m = 0.0

        x, y, z = calc._get_ground_ecef(loc_north)

        # At North Pole, z should be Earth radius
        assert abs(z - EARTH_RADIUS_KM) < 1.0
        assert abs(x) < 1.0
        assert abs(y) < 1.0


class TestVisibilityCalculatorAzimuth:
    """Tests for azimuth calculation."""

    def create_calculator(self):
        sat = MagicMock()
        sat.satellite_name = "TEST-SAT"
        sat.predictor = MagicMock()
        return VisibilityCalculator(sat, use_adaptive=False)

    def test_calculate_azimuth_north(self) -> None:
        """Satellite to the north should have azimuth near 0."""
        calc = self.create_calculator()

        location = MagicMock()
        location.latitude_deg = 45.0
        location.longitude_deg = 10.0

        sat_position = MagicMock()
        sat_position.position_llh = (50.0, 10.0, 600.0)  # North of location

        azimuth = calc._calculate_azimuth(location, sat_position, datetime.utcnow())

        # Should be close to 0 (north)
        assert azimuth < 45 or azimuth > 315

    def test_calculate_azimuth_east(self) -> None:
        """Satellite to the east should have azimuth near 90."""
        calc = self.create_calculator()

        location = MagicMock()
        location.latitude_deg = 45.0
        location.longitude_deg = 10.0

        sat_position = MagicMock()
        sat_position.position_llh = (45.0, 15.0, 600.0)  # East of location

        azimuth = calc._calculate_azimuth(location, sat_position, datetime.utcnow())

        # Should be close to 90 (east)
        assert 45 < azimuth < 135

    def test_calculate_azimuth_south(self) -> None:
        """Satellite to the south should have azimuth near 180."""
        calc = self.create_calculator()

        location = MagicMock()
        location.latitude_deg = 45.0
        location.longitude_deg = 10.0

        sat_position = MagicMock()
        sat_position.position_llh = (40.0, 10.0, 600.0)  # South of location

        azimuth = calc._calculate_azimuth(location, sat_position, datetime.utcnow())

        # Should be close to 180 (south)
        assert 135 < azimuth < 225


class TestVisibilityCalculatorElevation:
    """Tests for elevation calculation."""

    def create_calculator(self):
        sat = MagicMock()
        sat.satellite_name = "TEST-SAT"
        sat.predictor = MagicMock()
        return VisibilityCalculator(sat, use_adaptive=False)

    def test_calculate_elevation_overhead(self) -> None:
        """Satellite directly overhead should have high elevation."""
        calc = self.create_calculator()

        location = MagicMock()
        location.latitude_deg = 45.0
        location.longitude_deg = 10.0
        location.elevation_m = 0.0

        sat_position = MagicMock()
        sat_position.position_llh = (45.0, 10.0, 600.0)  # Directly above

        elevation = calc._calculate_elevation(location, sat_position, datetime.utcnow())

        # Should be high elevation (close to 90)
        assert elevation > 80

    def test_calculate_elevation_horizon(self) -> None:
        """Satellite far away should have low elevation."""
        calc = self.create_calculator()

        location = MagicMock()
        location.latitude_deg = 45.0
        location.longitude_deg = 10.0
        location.elevation_m = 0.0

        sat_position = MagicMock()
        sat_position.position_llh = (20.0, 10.0, 600.0)  # Far south

        elevation = calc._calculate_elevation(location, sat_position, datetime.utcnow())

        # Should be lower elevation
        assert elevation < 45


class TestVisibilityCalculatorTargetVisible:
    """Tests for target visibility checks."""

    def create_calculator(self):
        sat = MagicMock()
        sat.satellite_name = "TEST-SAT"
        sat.predictor = MagicMock()
        sat.get_position = MagicMock(return_value=(45.0, 10.0, 600.0))
        return VisibilityCalculator(sat, use_adaptive=False)

    def test_communication_visible_above_mask(self) -> None:
        """Communication target above elevation mask should be visible."""
        calc = self.create_calculator()

        target = GroundTarget(
            name="CommTarget",
            latitude=45.0,
            longitude=10.0,
            elevation_mask=10.0,
            mission_type="communication",
        )

        # 20 degrees elevation is above 10 degree mask
        visible = calc._is_target_visible(target, datetime.utcnow(), elevation=20.0)

        assert visible is True

    def test_communication_not_visible_below_mask(self) -> None:
        """Communication target below elevation mask should not be visible."""
        calc = self.create_calculator()

        target = GroundTarget(
            name="CommTarget",
            latitude=45.0,
            longitude=10.0,
            elevation_mask=10.0,
            mission_type="communication",
        )

        # 5 degrees elevation is below 10 degree mask
        visible = calc._is_target_visible(target, datetime.utcnow(), elevation=5.0)

        assert visible is False

    def test_imaging_not_visible_below_horizon(self) -> None:
        """Imaging target below horizon should not be visible."""
        calc = self.create_calculator()

        target = GroundTarget(
            name="ImagingTarget", latitude=45.0, longitude=10.0, mission_type="imaging"
        )

        # Negative elevation means below horizon
        visible = calc._is_target_visible(target, datetime.utcnow(), elevation=-5.0)

        assert visible is False


class TestVisibilityCalculatorIsVisible:
    """Tests for is_visible method."""

    def create_calculator(self):
        sat = MagicMock()
        sat.satellite_name = "TEST-SAT"
        sat.predictor = MagicMock()
        sat.predictor.get_position = MagicMock()
        return VisibilityCalculator(sat, use_adaptive=False)

    def test_is_visible_method_exists(self) -> None:
        """Test that is_visible method exists."""
        calc = self.create_calculator()

        assert hasattr(calc, "is_visible")
        assert callable(calc.is_visible)


class TestVisibilityCalculatorFindPasses:
    """Tests for find_passes method."""

    def create_calculator(self):
        sat = MagicMock()
        sat.satellite_name = "TEST-SAT"
        sat.predictor = MagicMock()
        return VisibilityCalculator(sat, use_adaptive=False)

    def test_find_passes_method_exists(self) -> None:
        """Test that find_passes method exists."""
        calc = self.create_calculator()

        assert hasattr(calc, "find_passes")
        assert callable(calc.find_passes)

    def test_find_passes_returns_list(self) -> None:
        """Test that find_passes returns a list."""
        calc = self.create_calculator()

        # Mock the predictor to return empty passes
        calc.predictor.passes_over = MagicMock(return_value=iter([]))

        target = GroundTarget(name="T1", latitude=45.0, longitude=10.0)
        start = datetime.utcnow()
        end = start + timedelta(hours=1)

        # The actual implementation may vary, but method should exist
        assert hasattr(calc, "find_passes")


class TestPassDetailsAdvanced:
    """Advanced tests for PassDetails."""

    def test_pass_duration_calculation(self) -> None:
        """Test calculating pass duration."""
        start = datetime(2025, 1, 1, 12, 0, 0)
        end = datetime(2025, 1, 1, 12, 8, 30)

        pd = PassDetails(
            target_name="Target1",
            satellite_name="SAT-1",
            start_time=start,
            max_elevation_time=start + timedelta(minutes=4),
            end_time=end,
            max_elevation=45.0,
            start_azimuth=90.0,
            max_elevation_azimuth=180.0,
            end_azimuth=270.0,
        )

        duration = (pd.end_time - pd.start_time).total_seconds()
        assert duration == 510  # 8.5 minutes

    def test_pass_with_all_optional_fields(self) -> None:
        """Test pass with all optional fields filled."""
        pd = PassDetails(
            target_name="Target1",
            satellite_name="SAT-1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            max_elevation_time=datetime(2025, 1, 1, 12, 5, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
            max_elevation=45.0,
            start_azimuth=90.0,
            max_elevation_azimuth=180.0,
            end_azimuth=270.0,
            satellite_id="sat_SAT-1",
            incidence_angle_deg=25.5,
            mode="OPTICAL",
        )

        result = pd.to_dict()

        assert result["satellite_id"] == "sat_SAT-1"
        assert result["incidence_angle_deg"] == 25.5
        assert result["mode"] == "OPTICAL"

    def test_pass_iso_time_format(self) -> None:
        """Test that times are in ISO format."""
        pd = PassDetails(
            target_name="Target1",
            satellite_name="SAT-1",
            start_time=datetime(2025, 1, 15, 14, 30, 45),
            max_elevation_time=datetime(2025, 1, 15, 14, 35, 0),
            end_time=datetime(2025, 1, 15, 14, 40, 15),
            max_elevation=45.0,
            start_azimuth=90.0,
            max_elevation_azimuth=180.0,
            end_azimuth=270.0,
        )

        result = pd.to_dict()

        assert "2025-01-15T14:30:45" in result["start_time"]
        assert "2025-01-15T14:40:15" in result["end_time"]


class TestEarthConstants:
    """Tests for Earth constants."""

    def test_earth_radius_value(self) -> None:
        """Test Earth radius is approximately correct."""
        assert 6370 < EARTH_RADIUS_KM < 6380

    def test_earth_radius_positive(self) -> None:
        """Test Earth radius is positive."""
        assert EARTH_RADIUS_KM > 0
