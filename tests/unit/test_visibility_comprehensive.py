"""
Comprehensive tests for visibility module.

Tests cover:
- PassDetails dataclass
- VisibilityCalculator initialization
- Elevation and azimuth calculations
- Pass finding algorithms
- Caching mechanisms
"""

import math
from datetime import datetime, timedelta
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from mission_planner.targets import GroundTarget
from mission_planner.visibility import (
    EARTH_RADIUS_KM,
    PASS_GAP_THRESHOLD_SECONDS,
    VISIBILITY_MARGIN_KM,
    PassDetails,
    VisibilityCalculator,
)


class TestPassDetailsDataclass:
    """Tests for PassDetails dataclass."""

    def test_basic_creation(self) -> None:
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
        )

        assert pd.target_name == "Target1"
        assert pd.satellite_name == "SAT-1"
        assert pd.max_elevation == 45.0

    def test_with_optional_fields(self) -> None:
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
            incidence_angle_deg=25.0,
            mode="OPTICAL",
        )

        assert pd.satellite_id == "sat_SAT-1"
        assert pd.incidence_angle_deg == 25.0
        assert pd.mode == "OPTICAL"

    def test_to_dict_basic(self) -> None:
        pd = PassDetails(
            target_name="Target1",
            satellite_name="SAT-1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            max_elevation_time=datetime(2025, 1, 1, 12, 5, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
            max_elevation=45.123,
            start_azimuth=90.456,
            max_elevation_azimuth=180.789,
            end_azimuth=270.123,
        )

        result = pd.to_dict()

        assert result["target_name"] == "Target1"
        assert result["satellite_name"] == "SAT-1"
        assert result["max_elevation"] == 45.12  # Rounded
        assert result["start_azimuth"] == 90.46  # Rounded
        assert "start_time" in result
        assert "end_time" in result

    def test_to_dict_with_quality_metrics(self) -> None:
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
            incidence_angle_deg=30.5,
            mode="SAR",
        )

        result = pd.to_dict()

        assert result["incidence_angle_deg"] == 30.5
        assert result["mode"] == "SAR"

    def test_to_dict_default_satellite_id(self) -> None:
        pd = PassDetails(
            target_name="Target1",
            satellite_name="MY-SAT",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            max_elevation_time=datetime(2025, 1, 1, 12, 5, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
            max_elevation=45.0,
            start_azimuth=90.0,
            max_elevation_azimuth=180.0,
            end_azimuth=270.0,
        )

        result = pd.to_dict()

        # Should generate default satellite_id from name
        assert result["satellite_id"] == "sat_MY-SAT"

    def test_str_representation(self) -> None:
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
        )

        result = str(pd)

        assert "Target1" in result
        assert "45.0" in result
        assert "12:00" in result

    def test_from_window_factory(self) -> None:
        pd = PassDetails.from_window(
            target_name="Target1",
            satellite_name="SAT-1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
            max_elevation=45.0,
            max_elevation_time=datetime(2025, 1, 1, 12, 5, 0),
            start_azimuth=90.0,
            max_elevation_azimuth=180.0,
            end_azimuth=270.0,
        )

        assert pd.target_name == "Target1"
        assert pd.max_elevation == 45.0

    def test_from_window_with_quality_metrics(self) -> None:
        pd = PassDetails.from_window(
            target_name="Target1",
            satellite_name="SAT-1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
            max_elevation=45.0,
            max_elevation_time=datetime(2025, 1, 1, 12, 5, 0),
            start_azimuth=90.0,
            max_elevation_azimuth=180.0,
            end_azimuth=270.0,
            incidence_angle_deg=25.0,
            mode="OPTICAL",
        )

        assert pd.incidence_angle_deg == 25.0
        assert pd.mode == "OPTICAL"


class TestPassDetailsEdgeCases:
    """Edge case tests for PassDetails."""

    def test_zero_elevation(self) -> None:
        pd = PassDetails(
            target_name="Target1",
            satellite_name="SAT-1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            max_elevation_time=datetime(2025, 1, 1, 12, 5, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
            max_elevation=0.0,  # Horizon pass
            start_azimuth=90.0,
            max_elevation_azimuth=180.0,
            end_azimuth=270.0,
        )

        assert pd.max_elevation == 0.0

    def test_high_elevation(self) -> None:
        pd = PassDetails(
            target_name="Target1",
            satellite_name="SAT-1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            max_elevation_time=datetime(2025, 1, 1, 12, 5, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
            max_elevation=89.5,  # Nearly overhead
            start_azimuth=90.0,
            max_elevation_azimuth=0.0,
            end_azimuth=270.0,
        )

        assert pd.max_elevation == 89.5

    def test_short_duration_pass(self) -> None:
        start = datetime(2025, 1, 1, 12, 0, 0)
        end = start + timedelta(seconds=30)  # 30 second pass

        pd = PassDetails(
            target_name="Target1",
            satellite_name="SAT-1",
            start_time=start,
            max_elevation_time=start + timedelta(seconds=15),
            end_time=end,
            max_elevation=10.0,
            start_azimuth=90.0,
            max_elevation_azimuth=90.0,
            end_azimuth=90.0,
        )

        duration = (pd.end_time - pd.start_time).total_seconds()
        assert duration == 30

    def test_negative_incidence_angle(self) -> None:
        """Negative incidence angle for westward-looking."""
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
            incidence_angle_deg=-30.0,  # Westward look
        )

        assert pd.incidence_angle_deg == -30.0


class TestVisibilityConstants:
    """Tests for visibility module constants."""

    def test_earth_radius(self) -> None:
        assert EARTH_RADIUS_KM == 6371.0

    def test_visibility_margin(self) -> None:
        assert VISIBILITY_MARGIN_KM > 0

    def test_pass_gap_threshold(self) -> None:
        assert PASS_GAP_THRESHOLD_SECONDS == 300  # 5 minutes


class TestVisibilityCalculatorInit:
    """Tests for VisibilityCalculator initialization."""

    def create_mock_satellite(self, use_adaptive=False):
        """Create a mock satellite with all required attributes."""
        sat = MagicMock()
        sat.satellite_name = "TEST-SAT"
        sat.predictor = MagicMock()
        sat.predictor.get_position.return_value = MagicMock(
            position_llh=(45.0, 10.0, 600000.0)
        )
        if use_adaptive:
            # For adaptive mode, need orbital period
            sat.get_orbital_period.return_value = timedelta(seconds=5400)  # 90 min
        return sat

    def test_basic_initialization(self) -> None:
        sat = self.create_mock_satellite()

        calc = VisibilityCalculator(sat, use_adaptive=False)

        assert calc.satellite == sat
        assert calc.predictor == sat.predictor
        assert calc.use_adaptive is False

    def test_adaptive_initialization(self) -> None:
        sat = self.create_mock_satellite(use_adaptive=True)

        calc = VisibilityCalculator(sat, use_adaptive=True)

        assert calc.use_adaptive is True
        # Adaptive mode should adjust step sizes based on orbital period
        assert calc.ADAPTIVE_INITIAL_STEP_SECONDS > 0

    def test_caches_initialized(self) -> None:
        sat = self.create_mock_satellite()

        calc = VisibilityCalculator(sat)

        assert hasattr(calc, "_ground_ecef_cache")
        assert hasattr(calc, "_location_cache")
        assert isinstance(calc._ground_ecef_cache, dict)


class TestVisibilityCalculatorGetLocation:
    """Tests for _get_location method."""

    def create_calculator(self):
        sat = MagicMock()
        sat.satellite_name = "TEST-SAT"
        sat.predictor = MagicMock()
        return VisibilityCalculator(sat, use_adaptive=False)

    def test_get_location_basic(self) -> None:
        calc = self.create_calculator()
        target = GroundTarget(name="T1", latitude=45.0, longitude=10.0)

        location = calc._get_location(target)

        assert location is not None

    def test_get_location_caches(self) -> None:
        calc = self.create_calculator()
        target = GroundTarget(name="T1", latitude=45.0, longitude=10.0)

        location1 = calc._get_location(target)
        location2 = calc._get_location(target)

        # Should return same cached object
        assert location1 is location2

    def test_get_location_different_targets(self) -> None:
        calc = self.create_calculator()
        target1 = GroundTarget(name="T1", latitude=45.0, longitude=10.0)
        target2 = GroundTarget(name="T2", latitude=50.0, longitude=15.0)

        location1 = calc._get_location(target1)
        location2 = calc._get_location(target2)

        # Different targets should have different locations
        assert location1 is not location2


class TestVisibilityCalculatorElevationAzimuth:
    """Tests for calculate_elevation_azimuth method."""

    def create_calculator(self):
        sat = MagicMock()
        sat.satellite_name = "TEST-SAT"
        sat.predictor = MagicMock()
        # Mock satellite position
        sat.predictor.get_position.return_value = MagicMock(
            position_ecef=(4000.0, 3000.0, 4000.0)  # km
        )
        return VisibilityCalculator(sat, use_adaptive=False)

    def test_returns_tuple(self) -> None:
        calc = self.create_calculator()
        target = GroundTarget(name="T1", latitude=45.0, longitude=10.0)

        result = calc.calculate_elevation_azimuth(target, datetime.utcnow())

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_elevation_in_range(self) -> None:
        calc = self.create_calculator()
        target = GroundTarget(name="T1", latitude=45.0, longitude=10.0)

        elevation, azimuth = calc.calculate_elevation_azimuth(target, datetime.utcnow())

        # Elevation should be between -90 and 90
        assert -90 <= elevation <= 90

    def test_azimuth_in_range(self) -> None:
        calc = self.create_calculator()
        target = GroundTarget(name="T1", latitude=45.0, longitude=10.0)

        elevation, azimuth = calc.calculate_elevation_azimuth(target, datetime.utcnow())

        # Azimuth should be between 0 and 360
        assert 0 <= azimuth <= 360


class TestVisibilityCalculatorMethods:
    """Tests for VisibilityCalculator method existence."""

    def create_calculator(self):
        sat = MagicMock()
        sat.satellite_name = "TEST-SAT"
        sat.predictor = MagicMock()
        return VisibilityCalculator(sat, use_adaptive=False)

    def test_has_find_passes_method(self) -> None:
        calc = self.create_calculator()

        assert hasattr(calc, "find_passes")
        assert callable(calc.find_passes)

    def test_has_calculate_elevation_azimuth_method(self) -> None:
        calc = self.create_calculator()

        assert hasattr(calc, "calculate_elevation_azimuth")
        assert callable(calc.calculate_elevation_azimuth)

    def test_has_is_visible_method(self) -> None:
        calc = self.create_calculator()

        assert hasattr(calc, "is_visible")
        assert callable(calc.is_visible)


class TestGroundTargetIntegration:
    """Integration tests with GroundTarget."""

    def test_ground_target_for_imaging(self) -> None:
        target = GroundTarget(
            name="Imaging Target",
            latitude=45.0,
            longitude=10.0,
            mission_type="imaging",
        )

        assert target.mission_type == "imaging"
        assert target.sensor_fov_half_angle_deg is not None

    def test_ground_target_for_communication(self) -> None:
        target = GroundTarget(
            name="Comm Target",
            latitude=45.0,
            longitude=10.0,
            mission_type="communication",
        )

        assert target.mission_type == "communication"


class TestPassDetailsComparison:
    """Tests for comparing pass details."""

    def test_same_pass_attributes(self) -> None:
        pd1 = PassDetails(
            target_name="Target1",
            satellite_name="SAT-1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            max_elevation_time=datetime(2025, 1, 1, 12, 5, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
            max_elevation=45.0,
            start_azimuth=90.0,
            max_elevation_azimuth=180.0,
            end_azimuth=270.0,
        )
        pd2 = PassDetails(
            target_name="Target1",
            satellite_name="SAT-1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            max_elevation_time=datetime(2025, 1, 1, 12, 5, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
            max_elevation=45.0,
            start_azimuth=90.0,
            max_elevation_azimuth=180.0,
            end_azimuth=270.0,
        )

        # Dataclasses with same values should be equal
        assert pd1 == pd2

    def test_different_elevation(self) -> None:
        pd1 = PassDetails(
            target_name="Target1",
            satellite_name="SAT-1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            max_elevation_time=datetime(2025, 1, 1, 12, 5, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
            max_elevation=45.0,
            start_azimuth=90.0,
            max_elevation_azimuth=180.0,
            end_azimuth=270.0,
        )
        pd2 = PassDetails(
            target_name="Target1",
            satellite_name="SAT-1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            max_elevation_time=datetime(2025, 1, 1, 12, 5, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
            max_elevation=50.0,  # Different elevation
            start_azimuth=90.0,
            max_elevation_azimuth=180.0,
            end_azimuth=270.0,
        )

        assert pd1 != pd2
