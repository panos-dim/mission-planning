"""
Comprehensive tests for visibility module.
"""

import pytest
import math
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from mission_planner.visibility import (
    VisibilityCalculator,
    PassDetails,
)
from mission_planner.orbit import SatelliteOrbit
from mission_planner.targets import GroundTarget


class TestPassDetails:
    """Tests for PassDetails dataclass."""

    def test_basic_creation(self) -> None:
        start = datetime(2025, 1, 1, 12, 0, 0)
        max_elev = datetime(2025, 1, 1, 12, 5, 0)
        end = datetime(2025, 1, 1, 12, 10, 0)

        pass_detail = PassDetails(
            target_name="Dubai",
            satellite_name="SAT-1",
            start_time=start,
            max_elevation_time=max_elev,
            end_time=end,
            max_elevation=45.0,
            start_azimuth=180.0,
            max_elevation_azimuth=90.0,
            end_azimuth=0.0,
        )

        assert pass_detail.start_time == start
        assert pass_detail.end_time == end
        assert pass_detail.max_elevation == 45.0
        assert pass_detail.target_name == "Dubai"


class TestVisibilityCalculator:
    """Tests for VisibilityCalculator class."""

    @pytest.fixture
    def satellite(self, tmp_path):
        """Create a test satellite."""
        tle_content = """ICEYE-X44
1 62707U 25009DC  25306.22031033  .00004207  00000+0  39848-3 0  9995
2 62707  97.7269  23.9854 0002193 135.9671 224.1724 14.94137357 66022"""

        tle_file = tmp_path / "test.tle"
        tle_file.write_text(tle_content)

        return SatelliteOrbit.from_tle_file(str(tle_file), "ICEYE-X44")

    @pytest.fixture
    def target(self):
        """Create a test target."""
        return GroundTarget(
            name="Dubai",
            latitude=25.2048,
            longitude=55.2708,
            elevation_mask=10.0,
        )

    @pytest.fixture
    def calculator(self, satellite):
        """Create a visibility calculator."""
        return VisibilityCalculator(satellite=satellite)

    def test_calculator_creation(self, calculator) -> None:
        """Test calculator is created correctly."""
        assert calculator is not None
        assert calculator.satellite is not None

    def test_find_passes_returns_list(self, calculator, target) -> None:
        """Test find_passes returns a list."""
        start = datetime(2025, 11, 8, 0, 0, 0)
        end = datetime(2025, 11, 8, 12, 0, 0)

        passes = calculator.find_passes(target, start, end)

        assert isinstance(passes, list)

    def test_find_passes_short_period(self, calculator, target) -> None:
        """Test find_passes with short time period."""
        start = datetime(2025, 11, 8, 10, 0, 0)
        end = datetime(2025, 11, 8, 10, 30, 0)

        passes = calculator.find_passes(target, start, end)

        # May or may not find passes in 30 minutes
        assert isinstance(passes, list)

    def test_find_passes_24_hours(self, calculator, target) -> None:
        """Test find_passes over 24 hours."""
        start = datetime(2025, 11, 8, 0, 0, 0)
        end = datetime(2025, 11, 9, 0, 0, 0)

        passes = calculator.find_passes(target, start, end)

        # Should return a list (may be empty if TLE epoch is far from test time)
        assert isinstance(passes, list)


class TestVisibilityCalculatorAdaptive:
    """Tests for adaptive time-stepping."""

    @pytest.fixture
    def satellite(self, tmp_path):
        """Create a test satellite."""
        tle_content = """ICEYE-X44
1 62707U 25009DC  25306.22031033  .00004207  00000+0  39848-3 0  9995
2 62707  97.7269  23.9854 0002193 135.9671 224.1724 14.94137357 66022"""

        tle_file = tmp_path / "test.tle"
        tle_file.write_text(tle_content)

        return SatelliteOrbit.from_tle_file(str(tle_file), "ICEYE-X44")

    def test_default_no_adaptive(self, satellite) -> None:
        """Test default uses fixed-step."""
        calc = VisibilityCalculator(satellite=satellite)
        assert calc.use_adaptive is False

    def test_adaptive_enabled(self, satellite) -> None:
        """Test adaptive mode can be enabled."""
        calc = VisibilityCalculator(satellite=satellite, use_adaptive=True)
        assert calc.use_adaptive is True
