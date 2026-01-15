"""
Core tests for visibility.py module.

Tests cover:
- VisibilityCalculator initialization
- PassDetails dataclass
- get_visibility_windows method
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from mission_planner.targets import GroundTarget
from mission_planner.visibility import PassDetails, VisibilityCalculator


def create_mock_satellite():
    """Create a mock satellite for testing."""
    sat = MagicMock()
    sat.satellite_name = "TEST-SAT"
    sat.get_position = MagicMock(return_value=(45.0, 10.0, 600.0))
    sat.get_orbital_period = MagicMock(return_value=timedelta(minutes=92))
    return sat


class TestVisibilityCalculatorInit:
    """Tests for VisibilityCalculator initialization."""

    def test_init_with_satellite(self) -> None:
        sat = create_mock_satellite()
        calc = VisibilityCalculator(sat)

        assert calc.satellite == sat

    def test_init_with_adaptive(self) -> None:
        sat = create_mock_satellite()
        calc = VisibilityCalculator(sat, use_adaptive=True)

        assert calc.use_adaptive is True

    def test_init_default_adaptive_false(self) -> None:
        sat = create_mock_satellite()
        calc = VisibilityCalculator(sat)

        assert calc.use_adaptive is False

    def test_has_satellite_attribute(self) -> None:
        sat = create_mock_satellite()
        calc = VisibilityCalculator(sat)

        assert hasattr(calc, "satellite")

    def test_stores_satellite(self) -> None:
        sat = create_mock_satellite()
        calc = VisibilityCalculator(sat)

        assert calc.satellite == sat


class TestPassDetails:
    """Tests for PassDetails dataclass."""

    def test_create_pass_details(self) -> None:
        now = datetime.utcnow()
        pd = PassDetails(
            target_name="Test",
            satellite_name="SAT",
            start_time=now,
            max_elevation_time=now + timedelta(minutes=5),
            end_time=now + timedelta(minutes=10),
            max_elevation=75.0,
            start_azimuth=45.0,
            max_elevation_azimuth=90.0,
            end_azimuth=135.0,
        )

        assert pd.target_name == "Test"
        assert pd.max_elevation == 75.0

    def test_pass_details_to_dict(self) -> None:
        now = datetime.utcnow()
        pd = PassDetails(
            target_name="Test",
            satellite_name="SAT",
            start_time=now,
            max_elevation_time=now + timedelta(minutes=5),
            end_time=now + timedelta(minutes=10),
            max_elevation=75.0,
            start_azimuth=45.0,
            max_elevation_azimuth=90.0,
            end_azimuth=135.0,
        )

        result = pd.to_dict()

        assert isinstance(result, dict)
        assert "target_name" in result
        assert result["target_name"] == "Test"

    def test_pass_details_duration(self) -> None:
        now = datetime.utcnow()
        pd = PassDetails(
            target_name="Test",
            satellite_name="SAT",
            start_time=now,
            max_elevation_time=now + timedelta(minutes=5),
            end_time=now + timedelta(minutes=10),
            max_elevation=75.0,
            start_azimuth=45.0,
            max_elevation_azimuth=90.0,
            end_azimuth=135.0,
        )

        duration = (pd.end_time - pd.start_time).total_seconds()

        assert duration == 600

    def test_pass_details_all_fields(self) -> None:
        now = datetime.utcnow()
        pd = PassDetails(
            target_name="T1",
            satellite_name="S1",
            start_time=now,
            max_elevation_time=now + timedelta(minutes=5),
            end_time=now + timedelta(minutes=10),
            max_elevation=80.0,
            start_azimuth=30.0,
            max_elevation_azimuth=180.0,
            end_azimuth=330.0,
        )

        assert pd.satellite_name == "S1"
        assert pd.start_azimuth == 30.0
        assert pd.max_elevation_azimuth == 180.0
        assert pd.end_azimuth == 330.0


class TestGetVisibilityWindows:
    """Tests for get_visibility_windows method."""

    @pytest.fixture
    def calculator(self):
        sat = create_mock_satellite()
        return VisibilityCalculator(sat)

    def test_empty_targets_returns_empty(self, calculator) -> None:
        result = calculator.get_visibility_windows(
            targets=[],
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(hours=1),
        )

        assert result == {}

    def test_returns_dict(self, calculator) -> None:
        targets = [GroundTarget("Test", 45.0, 10.0)]

        result = calculator.get_visibility_windows(
            targets=targets,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(hours=1),
        )

        assert isinstance(result, dict)

    def test_target_key_in_result(self, calculator) -> None:
        targets = [GroundTarget("TestTarget", 45.0, 10.0)]

        result = calculator.get_visibility_windows(
            targets=targets,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(hours=1),
        )

        assert "TestTarget" in result


class TestVisibilityCalculatorMethods:
    """Tests for VisibilityCalculator method availability."""

    @pytest.fixture
    def calculator(self):
        sat = create_mock_satellite()
        return VisibilityCalculator(sat)

    def test_has_get_visibility_windows(self, calculator) -> None:
        assert hasattr(calculator, "get_visibility_windows")
        assert callable(calculator.get_visibility_windows)

    def test_has_calculate_elevation(self, calculator) -> None:
        assert hasattr(calculator, "_calculate_elevation")

    def test_has_calculate_azimuth(self, calculator) -> None:
        assert hasattr(calculator, "_calculate_azimuth")

    def test_has_calculate_look_angle(self, calculator) -> None:
        assert hasattr(calculator, "_calculate_look_angle")


class TestVisibilityCalculatorConfig:
    """Tests for VisibilityCalculator configuration."""

    def test_adaptive_enabled(self) -> None:
        sat = create_mock_satellite()
        calc = VisibilityCalculator(sat, use_adaptive=True)

        assert calc.use_adaptive is True

    def test_adaptive_disabled(self) -> None:
        sat = create_mock_satellite()
        calc = VisibilityCalculator(sat, use_adaptive=False)

        assert calc.use_adaptive is False

    def test_default_config(self) -> None:
        sat = create_mock_satellite()
        calc = VisibilityCalculator(sat)

        assert calc.satellite is not None
        assert calc.use_adaptive is False
