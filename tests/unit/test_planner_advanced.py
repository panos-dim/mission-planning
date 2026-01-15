"""
Advanced tests for planner module.

Tests cover:
- MissionPlanner initialization
- Target management
- Pass computation
- Mission summary generation
- Schedule export
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mission_planner.planner import MissionPlanner
from mission_planner.targets import GroundTarget


def create_mock_satellite():
    """Create a mock satellite with all required attributes."""
    sat = MagicMock()
    sat.satellite_name = "TEST-SAT"
    sat.predictor = MagicMock()
    sat.predictor.get_position = MagicMock()
    sat.get_position = MagicMock(return_value=(45.0, 10.0, 600.0))
    sat.get_ground_track = MagicMock(return_value=[])
    sat.get_orbital_period = MagicMock(return_value=timedelta(seconds=5400))
    return sat


class TestMissionPlannerInitialization:
    """Tests for MissionPlanner initialization."""

    def test_init_with_satellite_only(self) -> None:
        sat = create_mock_satellite()

        planner = MissionPlanner(sat)

        assert planner.satellite == sat
        assert planner.satellite.satellite_name == "TEST-SAT"

    def test_init_with_targets(self) -> None:
        sat = create_mock_satellite()
        targets = [
            GroundTarget(name="T1", latitude=45.0, longitude=10.0),
            GroundTarget(name="T2", latitude=50.0, longitude=15.0),
        ]

        planner = MissionPlanner(sat, targets)

        assert len(list(planner.target_manager.targets)) == 2

    def test_init_creates_visibility_calculator(self) -> None:
        sat = create_mock_satellite()

        planner = MissionPlanner(sat)

        assert hasattr(planner, "visibility_calculator")
        assert planner.visibility_calculator is not None

    def test_init_creates_visualizer(self) -> None:
        sat = create_mock_satellite()

        planner = MissionPlanner(sat)

        assert hasattr(planner, "visualizer")
        assert planner.visualizer is not None

    def test_init_creates_target_manager(self) -> None:
        sat = create_mock_satellite()

        planner = MissionPlanner(sat)

        assert hasattr(planner, "target_manager")


class TestMissionPlannerTargetOperations:
    """Tests for target management operations."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        return MissionPlanner(sat)

    def test_add_single_target(self, planner) -> None:
        target = GroundTarget(name="NewTarget", latitude=40.0, longitude=20.0)

        planner.add_target(target)

        targets = list(planner.target_manager.targets)
        assert len(targets) == 1
        assert targets[0].name == "NewTarget"

    def test_add_multiple_targets(self, planner) -> None:
        planner.add_target(GroundTarget(name="T1", latitude=40.0, longitude=20.0))
        planner.add_target(GroundTarget(name="T2", latitude=45.0, longitude=25.0))
        planner.add_target(GroundTarget(name="T3", latitude=50.0, longitude=30.0))

        targets = list(planner.target_manager.targets)
        assert len(targets) == 3

    def test_remove_existing_target(self, planner) -> None:
        planner.add_target(GroundTarget(name="ToRemove", latitude=40.0, longitude=20.0))

        result = planner.remove_target("ToRemove")

        assert result is True
        targets = list(planner.target_manager.targets)
        assert len(targets) == 0

    def test_remove_nonexistent_target(self, planner) -> None:
        result = planner.remove_target("NonExistent")

        assert result is False


class TestMissionPlannerComputePasses:
    """Tests for compute_passes method."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        planner = MissionPlanner(sat)
        planner.add_target(GroundTarget(name="T1", latitude=45.0, longitude=10.0))
        return planner

    def test_compute_passes_returns_dict(self, planner) -> None:
        start = datetime.utcnow()
        end = start + timedelta(hours=1)

        # The method should return a dict
        result = planner.compute_passes(start, end)

        assert isinstance(result, dict)

    def test_compute_passes_with_no_targets_returns_empty(self) -> None:
        sat = create_mock_satellite()
        planner = MissionPlanner(sat)  # No targets

        start = datetime.utcnow()
        end = start + timedelta(hours=1)

        result = planner.compute_passes(start, end)

        assert result == {}


class TestMissionPlannerMissionSummary:
    """Tests for get_mission_summary method."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        planner = MissionPlanner(sat)
        planner.add_target(GroundTarget(name="T1", latitude=45.0, longitude=10.0))
        return planner

    def test_get_mission_summary_exists(self, planner) -> None:
        assert hasattr(planner, "get_mission_summary")
        assert callable(planner.get_mission_summary)


class TestMissionPlannerExportSchedule:
    """Tests for export_schedule method."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        return MissionPlanner(sat)

    def test_export_schedule_method_exists(self, planner) -> None:
        assert hasattr(planner, "export_schedule")
        assert callable(planner.export_schedule)


class TestMissionPlannerVisualization:
    """Tests for visualization methods."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        planner = MissionPlanner(sat)
        planner.add_target(GroundTarget(name="T1", latitude=45.0, longitude=10.0))
        return planner

    def test_has_visualizer_attribute(self, planner) -> None:
        assert hasattr(planner, "visualizer")

    def test_visualizer_is_not_none(self, planner) -> None:
        assert planner.visualizer is not None


class TestMissionPlannerAttributes:
    """Tests for MissionPlanner attributes."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        return MissionPlanner(sat)

    def test_satellite_attribute(self, planner) -> None:
        assert hasattr(planner, "satellite")
        assert planner.satellite.satellite_name == "TEST-SAT"

    def test_target_manager_attribute(self, planner) -> None:
        assert hasattr(planner, "target_manager")

    def test_visibility_calculator_attribute(self, planner) -> None:
        assert hasattr(planner, "visibility_calculator")

    def test_visualizer_attribute(self, planner) -> None:
        assert hasattr(planner, "visualizer")


class TestMissionPlannerEdgeCases:
    """Edge case tests for MissionPlanner."""

    def test_empty_target_list(self) -> None:
        sat = create_mock_satellite()
        planner = MissionPlanner(sat, targets=[])

        assert len(list(planner.target_manager.targets)) == 0

    def test_single_target(self) -> None:
        sat = create_mock_satellite()
        targets = [GroundTarget(name="Single", latitude=45.0, longitude=10.0)]

        planner = MissionPlanner(sat, targets)

        assert len(list(planner.target_manager.targets)) == 1

    def test_many_targets(self) -> None:
        sat = create_mock_satellite()
        targets = [
            GroundTarget(name=f"T{i}", latitude=45.0 + i, longitude=10.0 + i)
            for i in range(10)
        ]

        planner = MissionPlanner(sat, targets)

        assert len(list(planner.target_manager.targets)) == 10


class TestMissionPlannerTargetTypes:
    """Tests for different target mission types."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        return MissionPlanner(sat)

    def test_add_imaging_target(self, planner) -> None:
        target = GroundTarget(
            name="ImagingTarget", latitude=45.0, longitude=10.0, mission_type="imaging"
        )

        planner.add_target(target)

        targets = list(planner.target_manager.targets)
        assert targets[0].mission_type == "imaging"

    def test_add_communication_target(self, planner) -> None:
        target = GroundTarget(
            name="CommTarget",
            latitude=45.0,
            longitude=10.0,
            mission_type="communication",
        )

        planner.add_target(target)

        targets = list(planner.target_manager.targets)
        assert targets[0].mission_type == "communication"

    def test_mixed_target_types(self, planner) -> None:
        planner.add_target(
            GroundTarget(
                name="Img", latitude=45.0, longitude=10.0, mission_type="imaging"
            )
        )
        planner.add_target(
            GroundTarget(
                name="Comm", latitude=50.0, longitude=15.0, mission_type="communication"
            )
        )

        targets = list(planner.target_manager.targets)
        mission_types = {t.mission_type for t in targets}

        assert "imaging" in mission_types
        assert "communication" in mission_types


class TestTargetManagerIntegration:
    """Integration tests with TargetManager."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        return MissionPlanner(sat)

    def test_target_manager_iteration(self, planner) -> None:
        planner.add_target(GroundTarget(name="T1", latitude=45.0, longitude=10.0))
        planner.add_target(GroundTarget(name="T2", latitude=50.0, longitude=15.0))

        # Should be iterable
        names = [t.name for t in planner.target_manager.targets]

        assert "T1" in names
        assert "T2" in names

    def test_target_manager_len(self, planner) -> None:
        planner.add_target(GroundTarget(name="T1", latitude=45.0, longitude=10.0))
        planner.add_target(GroundTarget(name="T2", latitude=50.0, longitude=15.0))

        assert len(planner.target_manager) == 2
