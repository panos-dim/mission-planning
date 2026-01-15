"""
Core tests for planner.py module.

Tests cover:
- MissionPlanner initialization
- Target management
- Pass computation setup
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from mission_planner.planner import MissionPlanner
from mission_planner.targets import GroundTarget


def create_mock_satellite():
    """Create a mock satellite for testing."""
    sat = MagicMock()
    sat.satellite_name = "TEST-SAT"
    sat.get_position = MagicMock(return_value=(45.0, 10.0, 600.0))
    sat.get_orbital_period = MagicMock(return_value=timedelta(minutes=92))
    sat.get_ground_track = MagicMock(
        return_value=[
            (datetime.utcnow(), 45.0, 10.0, 600.0),
            (datetime.utcnow() + timedelta(minutes=1), 45.1, 10.1, 600.0),
        ]
    )
    return sat


class TestMissionPlannerInit:
    """Tests for MissionPlanner initialization."""

    def test_init_with_satellite(self) -> None:
        sat = create_mock_satellite()
        planner = MissionPlanner(sat)

        assert planner.satellite == sat

    def test_init_with_targets(self) -> None:
        sat = create_mock_satellite()
        targets = [GroundTarget("T1", 45.0, 10.0)]
        planner = MissionPlanner(sat, targets)

        assert len(planner.target_manager) == 1

    def test_init_empty_targets(self) -> None:
        sat = create_mock_satellite()
        planner = MissionPlanner(sat)

        assert len(planner.target_manager) == 0


class TestMissionPlannerTargetManagement:
    """Tests for target management."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        return MissionPlanner(sat)

    def test_add_target(self, planner) -> None:
        target = GroundTarget("Test", 45.0, 10.0)
        planner.add_target(target)

        assert len(planner.target_manager) == 1

    def test_add_multiple_targets(self, planner) -> None:
        planner.add_target(GroundTarget("T1", 45.0, 10.0))
        planner.add_target(GroundTarget("T2", 46.0, 11.0))

        assert len(planner.target_manager) == 2

    def test_target_manager_accessible(self, planner) -> None:
        planner.add_target(GroundTarget("T1", 45.0, 10.0))

        assert planner.target_manager is not None


class TestMissionPlannerAttributes:
    """Tests for MissionPlanner attributes."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        return MissionPlanner(sat)

    def test_has_satellite(self, planner) -> None:
        assert hasattr(planner, "satellite")

    def test_has_target_manager(self, planner) -> None:
        assert hasattr(planner, "target_manager")

    def test_has_visibility_calculator(self, planner) -> None:
        assert hasattr(planner, "visibility_calculator")


class TestMissionPlannerMethods:
    """Tests for MissionPlanner method availability."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        return MissionPlanner(sat)

    def test_has_compute_passes(self, planner) -> None:
        assert hasattr(planner, "compute_passes")
        assert callable(planner.compute_passes)

    def test_has_get_mission_summary(self, planner) -> None:
        assert hasattr(planner, "get_mission_summary")
        assert callable(planner.get_mission_summary)

    def test_has_export_schedule(self, planner) -> None:
        assert hasattr(planner, "export_schedule")
        assert callable(planner.export_schedule)

    def test_has_add_target(self, planner) -> None:
        assert hasattr(planner, "add_target")
        assert callable(planner.add_target)

    def test_has_run_mission_analysis(self, planner) -> None:
        assert hasattr(planner, "run_mission_analysis")
        assert callable(planner.run_mission_analysis)


class TestComputePasses:
    """Tests for compute_passes method."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        targets = [GroundTarget("T1", 45.0, 10.0)]
        return MissionPlanner(sat, targets)

    def test_returns_dict(self, planner) -> None:
        start = datetime.utcnow()
        end = start + timedelta(hours=1)

        result = planner.compute_passes(start, end)

        assert isinstance(result, dict)

    def test_empty_with_no_targets(self) -> None:
        sat = create_mock_satellite()
        planner = MissionPlanner(sat)

        start = datetime.utcnow()
        end = start + timedelta(hours=1)

        result = planner.compute_passes(start, end)

        assert result == {}


class TestGetMissionSummaryExtended:
    """Extended tests for get_mission_summary method."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        return MissionPlanner(sat)

    def test_summary_with_empty_passes(self, planner) -> None:
        summary = planner.get_mission_summary({})

        assert summary["total_passes"] == 0

    def test_summary_contains_satellite_name(self, planner) -> None:
        summary = planner.get_mission_summary({})

        assert summary["satellite_name"] == "TEST-SAT"

    def test_summary_with_targets_no_passes(self, planner) -> None:
        summary = planner.get_mission_summary({"T1": [], "T2": []})

        assert summary["total_passes"] == 0
        assert summary["targets_analyzed"] == 2


class TestMissionPlannerConfig:
    """Tests for MissionPlanner configuration."""

    def test_default_config(self) -> None:
        sat = create_mock_satellite()
        planner = MissionPlanner(sat)

        assert planner.satellite is not None

    def test_with_targets_list(self) -> None:
        sat = create_mock_satellite()
        targets = [
            GroundTarget("T1", 45.0, 10.0),
            GroundTarget("T2", 46.0, 11.0),
        ]
        planner = MissionPlanner(sat, targets)

        assert len(planner.target_manager) == 2
