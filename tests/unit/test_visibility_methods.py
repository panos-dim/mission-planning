"""
Comprehensive tests for visibility.py calculation methods.

Uses mocking to test internal calculation methods without real satellites.
"""

import math
from datetime import datetime, timedelta
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from orbit_predictor.locations import Location

from mission_planner.targets import GroundTarget
from mission_planner.visibility import (
    EARTH_RADIUS_KM,
    PASS_GAP_THRESHOLD_SECONDS,
    VISIBILITY_MARGIN_KM,
    PassDetails,
    VisibilityCalculator,
)


def create_mock_satellite():
    """Create a mock satellite with predictor."""
    sat = MagicMock()
    sat.satellite_name = "TEST-SAT"
    sat.predictor = MagicMock()

    # Mock position return
    mock_position = MagicMock()
    mock_position.position_ecef = (6871.0, 0.0, 0.0)  # ~500km above equator
    mock_position.velocity_ecef = (0.0, 7.5, 0.0)  # ~7.5 km/s orbital velocity
    sat.predictor.get_position = MagicMock(return_value=mock_position)

    sat.get_position = MagicMock(return_value=(0.0, 0.0, 500.0))
    sat.get_orbital_period = MagicMock(return_value=timedelta(minutes=92))

    return sat


class TestVisibilityConstants:
    """Tests for visibility module constants."""

    def test_earth_radius(self) -> None:
        assert EARTH_RADIUS_KM == 6371.0

    def test_visibility_margin(self) -> None:
        assert VISIBILITY_MARGIN_KM > 0

    def test_pass_gap_threshold(self) -> None:
        assert PASS_GAP_THRESHOLD_SECONDS == 300


class TestPassDetailsToDict:
    """Tests for PassDetails.to_dict() method."""

    def test_basic_to_dict(self) -> None:
        now = datetime(2025, 1, 15, 12, 0, 0)
        pd = PassDetails(
            target_name="Target1",
            satellite_name="SAT1",
            start_time=now,
            max_elevation_time=now + timedelta(minutes=5),
            end_time=now + timedelta(minutes=10),
            max_elevation=75.5,
            start_azimuth=45.0,
            max_elevation_azimuth=180.0,
            end_azimuth=315.0,
        )

        result = pd.to_dict()

        assert result["target_name"] == "Target1"
        assert result["satellite_name"] == "SAT1"
        assert result["max_elevation"] == 75.5
        assert "start_time" in result

    def test_to_dict_with_incidence_angle(self) -> None:
        now = datetime(2025, 1, 15, 12, 0, 0)
        pd = PassDetails(
            target_name="Target1",
            satellite_name="SAT1",
            start_time=now,
            max_elevation_time=now + timedelta(minutes=5),
            end_time=now + timedelta(minutes=10),
            max_elevation=60.0,
            start_azimuth=30.0,
            max_elevation_azimuth=90.0,
            end_azimuth=150.0,
            incidence_angle_deg=25.5,
        )

        result = pd.to_dict()

        assert "incidence_angle_deg" in result
        assert result["incidence_angle_deg"] == 25.5

    def test_to_dict_with_mode(self) -> None:
        now = datetime(2025, 1, 15, 12, 0, 0)
        pd = PassDetails(
            target_name="Target1",
            satellite_name="SAT1",
            start_time=now,
            max_elevation_time=now + timedelta(minutes=5),
            end_time=now + timedelta(minutes=10),
            max_elevation=60.0,
            start_azimuth=30.0,
            max_elevation_azimuth=90.0,
            end_azimuth=150.0,
            mode="OPTICAL",
        )

        result = pd.to_dict()

        assert "mode" in result
        assert result["mode"] == "OPTICAL"

    def test_to_dict_satellite_id_default(self) -> None:
        now = datetime(2025, 1, 15, 12, 0, 0)
        pd = PassDetails(
            target_name="Target1",
            satellite_name="SAT1",
            start_time=now,
            max_elevation_time=now + timedelta(minutes=5),
            end_time=now + timedelta(minutes=10),
            max_elevation=60.0,
            start_azimuth=30.0,
            max_elevation_azimuth=90.0,
            end_azimuth=150.0,
        )

        result = pd.to_dict()

        # Default satellite_id should be generated from name
        assert result["satellite_id"] == "sat_SAT1"

    def test_to_dict_satellite_id_custom(self) -> None:
        now = datetime(2025, 1, 15, 12, 0, 0)
        pd = PassDetails(
            target_name="Target1",
            satellite_name="SAT1",
            start_time=now,
            max_elevation_time=now + timedelta(minutes=5),
            end_time=now + timedelta(minutes=10),
            max_elevation=60.0,
            start_azimuth=30.0,
            max_elevation_azimuth=90.0,
            end_azimuth=150.0,
            satellite_id="custom_id_123",
        )

        result = pd.to_dict()

        assert result["satellite_id"] == "custom_id_123"


class TestVisibilityCalculatorInit:
    """Tests for VisibilityCalculator initialization."""

    def test_init_creates_predictor_reference(self) -> None:
        sat = create_mock_satellite()
        calc = VisibilityCalculator(sat)

        assert calc.predictor == sat.predictor

    def test_init_sets_adaptive_mode(self) -> None:
        sat = create_mock_satellite()
        calc = VisibilityCalculator(sat, use_adaptive=True)

        assert calc.use_adaptive is True

    def test_init_fixed_step_mode(self) -> None:
        sat = create_mock_satellite()
        calc = VisibilityCalculator(sat, use_adaptive=False)

        assert calc.use_adaptive is False

    def test_init_creates_caches(self) -> None:
        sat = create_mock_satellite()
        calc = VisibilityCalculator(sat)

        assert hasattr(calc, "_location_cache")
        assert hasattr(calc, "_ground_ecef_cache")


class TestGetLocation:
    """Tests for _get_location method."""

    @pytest.fixture
    def calculator(self):
        sat = create_mock_satellite()
        return VisibilityCalculator(sat)

    def test_creates_location_object(self, calculator) -> None:
        target = GroundTarget("Test", 45.0, 10.0, altitude=100.0)

        location = calculator._get_location(target)

        assert isinstance(location, Location)

    def test_caches_location(self, calculator) -> None:
        target = GroundTarget("Test", 45.0, 10.0)

        loc1 = calculator._get_location(target)
        loc2 = calculator._get_location(target)

        assert loc1 is loc2  # Same object from cache

    def test_different_targets_different_locations(self, calculator) -> None:
        target1 = GroundTarget("T1", 45.0, 10.0)
        target2 = GroundTarget("T2", 46.0, 11.0)

        loc1 = calculator._get_location(target1)
        loc2 = calculator._get_location(target2)

        assert loc1 is not loc2


class TestGetGroundECEF:
    """Tests for _get_ground_ecef method."""

    @pytest.fixture
    def calculator(self):
        sat = create_mock_satellite()
        return VisibilityCalculator(sat)

    def test_returns_tuple(self, calculator) -> None:
        location = Location("test", 0.0, 0.0, 0.0)

        result = calculator._get_ground_ecef(location)

        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_equator_prime_meridian(self, calculator) -> None:
        location = Location("test", 0.0, 0.0, 0.0)

        x, y, z = calculator._get_ground_ecef(location)

        # At equator, prime meridian: x ≈ Earth radius, y ≈ 0, z ≈ 0
        assert x == pytest.approx(EARTH_RADIUS_KM, rel=0.01)
        assert y == pytest.approx(0.0, abs=1.0)
        assert z == pytest.approx(0.0, abs=1.0)

    def test_north_pole(self, calculator) -> None:
        location = Location("test", 90.0, 0.0, 0.0)

        x, y, z = calculator._get_ground_ecef(location)

        # At north pole: x ≈ 0, y ≈ 0, z ≈ Earth radius
        assert x == pytest.approx(0.0, abs=1.0)
        assert y == pytest.approx(0.0, abs=1.0)
        assert z == pytest.approx(EARTH_RADIUS_KM, rel=0.01)

    def test_caches_result(self, calculator) -> None:
        location = Location("test", 45.0, 10.0, 0.0)

        result1 = calculator._get_ground_ecef(location)
        result2 = calculator._get_ground_ecef(location)

        assert result1 == result2


class TestCalculateElevationAzimuth:
    """Tests for calculate_elevation_azimuth method."""

    @pytest.fixture
    def calculator(self):
        sat = create_mock_satellite()
        return VisibilityCalculator(sat)

    def test_returns_tuple(self, calculator) -> None:
        target = GroundTarget("Test", 45.0, 10.0)

        result = calculator.calculate_elevation_azimuth(
            target, datetime(2025, 1, 15, 12, 0, 0)
        )

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_elevation_in_valid_range(self, calculator) -> None:
        target = GroundTarget("Test", 0.0, 0.0)  # Equator

        elev, az = calculator.calculate_elevation_azimuth(
            target, datetime(2025, 1, 15, 12, 0, 0)
        )

        # Elevation should be between -90 and 90
        assert -90 <= elev <= 90

    def test_azimuth_in_valid_range(self, calculator) -> None:
        target = GroundTarget("Test", 45.0, 10.0)

        elev, az = calculator.calculate_elevation_azimuth(
            target, datetime(2025, 1, 15, 12, 0, 0)
        )

        # Azimuth should be between 0 and 360
        assert 0 <= az <= 360


class TestCalculateLookAngle:
    """Tests for _calculate_look_angle method."""

    @pytest.fixture
    def calculator(self):
        sat = create_mock_satellite()
        return VisibilityCalculator(sat)

    def test_nadir_returns_zero(self, calculator) -> None:
        # Satellite directly over target
        angle = calculator._calculate_look_angle(
            sat_lat=45.0, sat_lon=10.0, sat_alt=500.0, target_lat=45.0, target_lon=10.0
        )

        assert angle == pytest.approx(0.0, abs=1.0)

    def test_off_nadir_returns_positive(self, calculator) -> None:
        angle = calculator._calculate_look_angle(
            sat_lat=45.0, sat_lon=10.0, sat_alt=500.0, target_lat=46.0, target_lon=10.0
        )

        assert angle > 0

    def test_larger_offset_larger_angle(self, calculator) -> None:
        angle_small = calculator._calculate_look_angle(
            sat_lat=45.0, sat_lon=10.0, sat_alt=500.0, target_lat=45.5, target_lon=10.0
        )
        angle_large = calculator._calculate_look_angle(
            sat_lat=45.0, sat_lon=10.0, sat_alt=500.0, target_lat=47.0, target_lon=10.0
        )

        assert angle_large > angle_small


class TestCalculateGroundDistance:
    """Tests for _calculate_ground_distance method."""

    @pytest.fixture
    def calculator(self):
        sat = create_mock_satellite()
        return VisibilityCalculator(sat)

    def test_same_point_zero_distance(self, calculator) -> None:
        dist = calculator._calculate_ground_distance(45.0, 10.0, 45.0, 10.0)

        assert dist == pytest.approx(0.0, abs=0.1)

    def test_one_degree_latitude(self, calculator) -> None:
        # 1 degree latitude is approximately 111 km
        dist = calculator._calculate_ground_distance(45.0, 10.0, 46.0, 10.0)

        assert 100 < dist < 120

    def test_equator_one_degree_longitude(self, calculator) -> None:
        # 1 degree longitude at equator is approximately 111 km
        dist = calculator._calculate_ground_distance(0.0, 0.0, 0.0, 1.0)

        assert 100 < dist < 120


class TestVisibilityWindowsEmpty:
    """Tests for get_visibility_windows with edge cases."""

    @pytest.fixture
    def calculator(self):
        sat = create_mock_satellite()
        return VisibilityCalculator(sat)

    def test_empty_targets(self, calculator) -> None:
        result = calculator.get_visibility_windows(
            targets=[],
            start_time=datetime(2025, 1, 15, 0, 0, 0),
            end_time=datetime(2025, 1, 15, 12, 0, 0),
        )

        assert result == {}

    def test_returns_dict_structure(self, calculator) -> None:
        targets = [GroundTarget("T1", 45.0, 10.0)]

        result = calculator.get_visibility_windows(
            targets=targets,
            start_time=datetime(2025, 1, 15, 0, 0, 0),
            end_time=datetime(2025, 1, 15, 1, 0, 0),
        )

        assert isinstance(result, dict)
        assert "T1" in result


class TestAdaptiveTimestepping:
    """Tests for adaptive timestepping configuration."""

    def test_adaptive_constants_set(self) -> None:
        sat = create_mock_satellite()
        calc = VisibilityCalculator(sat, use_adaptive=True)

        assert hasattr(calc, "ADAPTIVE_MIN_STEP_SECONDS")
        assert hasattr(calc, "ADAPTIVE_MAX_STEP_SECONDS")

    def test_adaptive_min_step_positive(self) -> None:
        sat = create_mock_satellite()
        calc = VisibilityCalculator(sat, use_adaptive=True)

        assert calc.ADAPTIVE_MIN_STEP_SECONDS > 0

    def test_adaptive_max_greater_than_min(self) -> None:
        sat = create_mock_satellite()
        calc = VisibilityCalculator(sat, use_adaptive=True)

        assert calc.ADAPTIVE_MAX_STEP_SECONDS > calc.ADAPTIVE_MIN_STEP_SECONDS
