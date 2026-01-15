"""
Tests for MissionPlanner methods.

Tests cover:
- get_mission_summary
- export_schedule
- _export_json
- _export_csv
"""

import csv
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
    sat.get_position = MagicMock(return_value=(45.0, 10.0, 600.0))
    sat.get_orbital_period = MagicMock(return_value=timedelta(seconds=5400))
    return sat


def create_mock_pass_details(target_name, max_elevation, start_offset_min=0):
    """Create a mock PassDetails object."""
    base_time = datetime(2025, 1, 15, 12, 0, 0)
    start_time = base_time + timedelta(minutes=start_offset_min)

    mock_pass = MagicMock()
    mock_pass.target_name = target_name
    mock_pass.satellite_name = "TEST-SAT"
    mock_pass.start_time = start_time
    mock_pass.max_elevation_time = start_time + timedelta(minutes=5)
    mock_pass.end_time = start_time + timedelta(minutes=10)
    mock_pass.max_elevation = max_elevation
    mock_pass.start_azimuth = 45.0
    mock_pass.max_elevation_azimuth = 90.0
    mock_pass.end_azimuth = 135.0
    mock_pass.to_dict = MagicMock(
        return_value={
            "target_name": target_name,
            "satellite_name": "TEST-SAT",
            "start_time": start_time.isoformat(),
            "max_elevation_time": (start_time + timedelta(minutes=5)).isoformat(),
            "end_time": (start_time + timedelta(minutes=10)).isoformat(),
            "max_elevation": max_elevation,
            "start_azimuth": 45.0,
            "max_elevation_azimuth": 90.0,
            "end_azimuth": 135.0,
        }
    )
    return mock_pass


class TestGetMissionSummary:
    """Tests for get_mission_summary method."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        return MissionPlanner(sat)

    def test_empty_passes(self, planner) -> None:
        passes = {}

        summary = planner.get_mission_summary(passes)

        assert summary["total_passes"] == 0
        assert summary["targets_with_passes"] == 0

    def test_no_passes_for_any_target(self, planner) -> None:
        passes = {"Target1": [], "Target2": []}

        summary = planner.get_mission_summary(passes)

        assert summary["total_passes"] == 0
        assert summary["targets_analyzed"] == 2

    def test_with_passes(self, planner) -> None:
        passes = {
            "Target1": [
                create_mock_pass_details("Target1", 75.0, 0),
                create_mock_pass_details("Target1", 60.0, 100),
            ],
            "Target2": [
                create_mock_pass_details("Target2", 45.0, 50),
            ],
        }

        summary = planner.get_mission_summary(passes)

        assert summary["total_passes"] == 3
        assert summary["targets_with_passes"] == 2
        assert summary["highest_elevation"] == 75.0

    def test_best_pass_identified(self, planner) -> None:
        passes = {
            "Target1": [create_mock_pass_details("Target1", 80.0, 0)],
            "Target2": [create_mock_pass_details("Target2", 50.0, 50)],
        }

        summary = planner.get_mission_summary(passes)

        assert summary["best_pass"]["target"] == "Target1"
        assert summary["best_pass"]["elevation"] == 80.0

    def test_satellite_name_included(self, planner) -> None:
        passes = {"Target1": [create_mock_pass_details("Target1", 60.0, 0)]}

        summary = planner.get_mission_summary(passes)

        assert summary["satellite_name"] == "TEST-SAT"


class TestExportScheduleJson:
    """Tests for export_schedule with JSON format."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        return MissionPlanner(sat)

    def test_export_json_creates_file(self, planner) -> None:
        passes = {"Target1": [create_mock_pass_details("Target1", 60.0, 0)]}

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        planner.export_schedule(passes, filepath)

        assert Path(filepath).exists()

        # Cleanup
        Path(filepath).unlink()

    def test_export_json_valid_structure(self, planner) -> None:
        passes = {"Target1": [create_mock_pass_details("Target1", 60.0, 0)]}

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        planner.export_schedule(passes, filepath)

        with open(filepath, "r") as f:
            data = json.load(f)

        assert "metadata" in data
        assert "passes" in data
        assert data["metadata"]["satellite"] == "TEST-SAT"

        # Cleanup
        Path(filepath).unlink()

    def test_export_json_auto_format(self, planner) -> None:
        passes = {"Target1": [create_mock_pass_details("Target1", 60.0, 0)]}

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        planner.export_schedule(passes, filepath, format="auto")

        with open(filepath, "r") as f:
            data = json.load(f)

        assert "passes" in data

        # Cleanup
        Path(filepath).unlink()


class TestExportScheduleCsv:
    """Tests for export_schedule with CSV format."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        return MissionPlanner(sat)

    def test_export_csv_creates_file(self, planner) -> None:
        passes = {"Target1": [create_mock_pass_details("Target1", 60.0, 0)]}

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            filepath = f.name

        planner.export_schedule(passes, filepath, format="csv")

        assert Path(filepath).exists()

        # Cleanup
        Path(filepath).unlink()

    def test_export_csv_empty_passes(self, planner) -> None:
        passes = {}

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            filepath = f.name

        planner.export_schedule(passes, filepath, format="csv")

        # Should create file with headers
        with open(filepath, "r") as f:
            reader = csv.reader(f)
            headers = next(reader)

        assert "target_name" in headers

        # Cleanup
        Path(filepath).unlink()

    def test_export_csv_auto_format(self, planner) -> None:
        passes = {"Target1": [create_mock_pass_details("Target1", 60.0, 0)]}

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            filepath = f.name

        planner.export_schedule(passes, filepath, format="auto")

        assert Path(filepath).exists()

        # Cleanup
        Path(filepath).unlink()


class TestExportScheduleFormatHandling:
    """Tests for export_schedule format handling."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        return MissionPlanner(sat)

    def test_invalid_format_raises(self, planner) -> None:
        passes = {"Target1": [create_mock_pass_details("Target1", 60.0, 0)]}

        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            filepath = f.name

        with pytest.raises(ValueError):
            planner.export_schedule(passes, filepath, format="invalid")

        # Cleanup
        Path(filepath).unlink()

    def test_auto_format_unknown_extension_defaults_json(self, planner) -> None:
        passes = {"Target1": [create_mock_pass_details("Target1", 60.0, 0)]}

        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            filepath = f.name

        planner.export_schedule(passes, filepath, format="auto")

        # Should be valid JSON
        with open(filepath, "r") as f:
            data = json.load(f)

        assert "passes" in data

        # Cleanup
        Path(filepath).unlink()


class TestExportScheduleDataIntegrity:
    """Tests for data integrity in exports."""

    @pytest.fixture
    def planner(self):
        sat = create_mock_satellite()
        return MissionPlanner(sat)

    def test_multiple_passes_sorted_by_time(self, planner) -> None:
        passes = {
            "Target1": [
                create_mock_pass_details("Target1", 60.0, 100),  # Later pass
            ],
            "Target2": [
                create_mock_pass_details("Target2", 50.0, 0),  # Earlier pass
            ],
        }

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        planner.export_schedule(passes, filepath)

        with open(filepath, "r") as f:
            data = json.load(f)

        # Passes should be sorted by start time
        pass_list = data["passes"]
        assert len(pass_list) == 2
        # Target2 (offset 0) should come before Target1 (offset 100)
        assert pass_list[0]["target_name"] == "Target2"

        # Cleanup
        Path(filepath).unlink()

    def test_pass_count_in_metadata(self, planner) -> None:
        passes = {
            "Target1": [
                create_mock_pass_details("Target1", 60.0, 0),
                create_mock_pass_details("Target1", 55.0, 100),
            ],
            "Target2": [
                create_mock_pass_details("Target2", 50.0, 50),
            ],
        }

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        planner.export_schedule(passes, filepath)

        with open(filepath, "r") as f:
            data = json.load(f)

        assert data["metadata"]["total_passes"] == 3

        # Cleanup
        Path(filepath).unlink()
