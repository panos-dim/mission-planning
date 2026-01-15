"""
Extended tests for planner module.

Tests cover:
- MissionPlanner initialization
- Target management
- Mission summary generation
- Schedule export functionality
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from mission_planner.orbit import SatelliteOrbit
from mission_planner.planner import MissionPlanner
from mission_planner.targets import GroundTarget


def create_mock_satellite():
    """Create a mock satellite with all required attributes."""
    sat = MagicMock(spec=SatelliteOrbit)
    sat.satellite_name = "TEST-SAT"
    sat.get_position.return_value = (45.0, 10.0, 600.0)
    sat.tle_lines = ["TEST-SAT", "line1", "line2"]
    # Mock predictor for VisibilityCalculator
    sat.predictor = MagicMock()
    sat.predictor.get_position.return_value = MagicMock(
        position_llh=(45.0, 10.0, 600000.0)
    )
    return sat


class TestMissionPlannerInit:
    """Tests for MissionPlanner initialization."""

    @pytest.fixture
    def mock_satellite(self):
        return create_mock_satellite()

    @pytest.fixture
    def sample_targets(self):
        return [
            GroundTarget(name="Target1", latitude=45.0, longitude=10.0),
            GroundTarget(name="Target2", latitude=50.0, longitude=15.0),
        ]

    def test_init_with_satellite(self, mock_satellite) -> None:
        planner = MissionPlanner(mock_satellite)

        assert planner.satellite == mock_satellite

    def test_init_with_targets(self, mock_satellite, sample_targets) -> None:
        planner = MissionPlanner(mock_satellite, sample_targets)

        assert len(list(planner.target_manager.targets)) == 2

    def test_init_without_targets(self, mock_satellite) -> None:
        planner = MissionPlanner(mock_satellite)

        assert len(list(planner.target_manager.targets)) == 0


class TestMissionPlannerTargetManagement:
    """Tests for target management methods."""

    @pytest.fixture
    def mock_satellite(self):
        return create_mock_satellite()

    @pytest.fixture
    def planner(self, mock_satellite):
        return MissionPlanner(mock_satellite)

    def test_add_target(self, planner) -> None:
        target = GroundTarget(name="NewTarget", latitude=40.0, longitude=20.0)

        planner.add_target(target)

        targets = list(planner.target_manager.targets)
        assert len(targets) == 1
        assert targets[0].name == "NewTarget"

    def test_add_multiple_targets(self, planner) -> None:
        target1 = GroundTarget(name="Target1", latitude=40.0, longitude=20.0)
        target2 = GroundTarget(name="Target2", latitude=45.0, longitude=25.0)

        planner.add_target(target1)
        planner.add_target(target2)

        targets = list(planner.target_manager.targets)
        assert len(targets) == 2

    def test_remove_target(self, planner) -> None:
        target = GroundTarget(name="ToRemove", latitude=40.0, longitude=20.0)
        planner.add_target(target)

        planner.remove_target("ToRemove")

        targets = list(planner.target_manager.targets)
        assert len(targets) == 0

    def test_target_manager_exists(self, planner) -> None:
        """Test that planner has target_manager attribute."""
        planner.add_target(GroundTarget(name="T1", latitude=40.0, longitude=20.0))
        planner.add_target(GroundTarget(name="T2", latitude=45.0, longitude=25.0))

        # Verify target manager exists and has targets
        assert hasattr(planner, "target_manager")
        targets = list(planner.target_manager.targets)
        assert len(targets) == 2


class TestMissionPlannerMethods:
    """Tests for MissionPlanner methods existence."""

    @pytest.fixture
    def mock_satellite(self):
        return create_mock_satellite()

    @pytest.fixture
    def planner(self, mock_satellite):
        return MissionPlanner(mock_satellite)

    def test_has_compute_passes_method(self, planner) -> None:
        """Test that compute_passes method exists."""
        assert hasattr(planner, "compute_passes")
        assert callable(planner.compute_passes)

    def test_has_add_target_method(self, planner) -> None:
        """Test that add_target method exists."""
        assert hasattr(planner, "add_target")
        assert callable(planner.add_target)

    def test_has_remove_target_method(self, planner) -> None:
        """Test that remove_target method exists."""
        assert hasattr(planner, "remove_target")
        assert callable(planner.remove_target)


class TestMissionPlannerSummary:
    """Tests for mission summary generation."""

    @pytest.fixture
    def mock_satellite(self):
        return create_mock_satellite()

    @pytest.fixture
    def planner(self, mock_satellite):
        return MissionPlanner(mock_satellite)

    def test_get_mission_summary_exists(self, planner) -> None:
        """Test that get_mission_summary method exists."""
        assert hasattr(planner, "get_mission_summary")

    def test_planner_has_satellite(self, planner) -> None:
        """Test that planner has satellite reference."""
        assert planner.satellite is not None
        assert planner.satellite.satellite_name == "TEST-SAT"


class TestMissionPlannerExport:
    """Tests for schedule export functionality."""

    @pytest.fixture
    def mock_satellite(self):
        return create_mock_satellite()

    @pytest.fixture
    def planner(self, mock_satellite):
        return MissionPlanner(mock_satellite)

    def test_has_export_schedule_method(self, planner) -> None:
        """Test that export_schedule method exists."""
        assert hasattr(planner, "export_schedule")
        assert callable(planner.export_schedule)


class TestMissionPlannerProperties:
    """Tests for MissionPlanner properties."""

    @pytest.fixture
    def mock_satellite(self):
        return create_mock_satellite()

    @pytest.fixture
    def planner_with_targets(self, mock_satellite):
        planner = MissionPlanner(mock_satellite)
        planner.add_target(GroundTarget(name="T1", latitude=45.0, longitude=10.0))
        planner.add_target(GroundTarget(name="T2", latitude=50.0, longitude=15.0))
        return planner

    def test_targets_property(self, planner_with_targets) -> None:
        targets = list(planner_with_targets.target_manager.targets)

        assert len(targets) == 2

    def test_satellite_property(self, planner_with_targets) -> None:
        assert planner_with_targets.satellite.satellite_name == "TEST-SAT"


class TestMissionPlannerEdgeCases:
    """Edge case tests for MissionPlanner."""

    @pytest.fixture
    def mock_satellite(self):
        return create_mock_satellite()

    def test_planner_initialization(self, mock_satellite) -> None:
        """Test basic planner initialization."""
        planner = MissionPlanner(mock_satellite)

        assert planner.satellite is not None
        assert planner.target_manager is not None

    def test_planner_with_target(self, mock_satellite) -> None:
        """Test planner with a target added."""
        planner = MissionPlanner(mock_satellite)
        planner.add_target(GroundTarget(name="T1", latitude=45.0, longitude=10.0))

        targets = list(planner.target_manager.targets)
        assert len(targets) == 1


class TestMissionPlannerAttributes:
    """Tests for MissionPlanner attributes."""

    @pytest.fixture
    def mock_satellite(self):
        return create_mock_satellite()

    @pytest.fixture
    def planner(self, mock_satellite):
        return MissionPlanner(mock_satellite)

    def test_has_visibility_calculator(self, planner) -> None:
        """Test that planner has visibility calculator."""
        assert hasattr(planner, "visibility_calculator")

    def test_has_visualizer(self, planner) -> None:
        """Test that planner has visualizer."""
        assert hasattr(planner, "visualizer")
