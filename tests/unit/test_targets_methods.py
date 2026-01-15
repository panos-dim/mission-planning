"""
Tests for targets.py module methods.

Tests cover:
- GroundTarget creation and validation
- TargetManager methods
- Target loading from files
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from mission_planner.targets import GroundTarget, TargetManager


class TestGroundTargetCreation:
    """Tests for GroundTarget creation."""

    def test_basic_creation(self) -> None:
        target = GroundTarget("Test", 45.0, 10.0)

        assert target.name == "Test"
        assert target.latitude == 45.0
        assert target.longitude == 10.0

    def test_with_altitude(self) -> None:
        target = GroundTarget("Test", 45.0, 10.0, altitude=100.0)

        assert target.altitude == 100.0

    def test_with_mission_type(self) -> None:
        target = GroundTarget("Test", 45.0, 10.0, mission_type="imaging")

        assert target.mission_type == "imaging"

    def test_default_mission_type(self) -> None:
        target = GroundTarget("Test", 45.0, 10.0)

        # Should have a default mission type
        assert hasattr(target, "mission_type")

    def test_with_elevation_mask(self) -> None:
        target = GroundTarget("Test", 45.0, 10.0, elevation_mask=15.0)

        assert target.elevation_mask == 15.0


class TestGroundTargetValidation:
    """Tests for GroundTarget validation."""

    def test_valid_latitude(self) -> None:
        target = GroundTarget("Test", 45.0, 10.0)

        assert -90 <= target.latitude <= 90

    def test_valid_longitude(self) -> None:
        target = GroundTarget("Test", 45.0, 10.0)

        assert -180 <= target.longitude <= 180

    def test_equator_target(self) -> None:
        target = GroundTarget("Equator", 0.0, 0.0)

        assert target.latitude == 0.0
        assert target.longitude == 0.0

    def test_north_pole(self) -> None:
        target = GroundTarget("NorthPole", 90.0, 0.0)

        assert target.latitude == 90.0

    def test_south_pole(self) -> None:
        target = GroundTarget("SouthPole", -90.0, 0.0)

        assert target.latitude == -90.0


class TestGroundTargetToDict:
    """Tests for GroundTarget.to_dict() method."""

    def test_basic_to_dict(self) -> None:
        target = GroundTarget("Test", 45.0, 10.0)

        result = target.to_dict()

        assert isinstance(result, dict)
        assert result["name"] == "Test"
        assert result["latitude"] == 45.0
        assert result["longitude"] == 10.0

    def test_to_dict_includes_altitude(self) -> None:
        target = GroundTarget("Test", 45.0, 10.0, altitude=500.0)

        result = target.to_dict()

        assert "altitude" in result
        assert result["altitude"] == 500.0


class TestGroundTargetStr:
    """Tests for GroundTarget string representation."""

    def test_str_representation(self) -> None:
        target = GroundTarget("TestTarget", 45.0, 10.0)

        result = str(target)

        assert "TestTarget" in result
        assert "45" in result

    def test_repr_representation(self) -> None:
        target = GroundTarget("TestTarget", 45.0, 10.0)

        result = repr(target)

        assert "TestTarget" in result


class TestTargetManagerCreation:
    """Tests for TargetManager creation."""

    def test_empty_manager(self) -> None:
        manager = TargetManager()

        assert len(manager) == 0

    def test_with_targets(self) -> None:
        targets = [
            GroundTarget("T1", 45.0, 10.0),
            GroundTarget("T2", 46.0, 11.0),
        ]
        manager = TargetManager(targets)

        assert len(manager) == 2

    def test_single_target(self) -> None:
        targets = [GroundTarget("T1", 45.0, 10.0)]
        manager = TargetManager(targets)

        assert len(manager) == 1


class TestTargetManagerAddRemove:
    """Tests for TargetManager add/remove operations."""

    def test_add_target(self) -> None:
        manager = TargetManager()
        target = GroundTarget("Test", 45.0, 10.0)

        manager.add_target(target)

        assert len(manager) == 1

    def test_add_multiple_targets(self) -> None:
        manager = TargetManager()

        manager.add_target(GroundTarget("T1", 45.0, 10.0))
        manager.add_target(GroundTarget("T2", 46.0, 11.0))

        assert len(manager) == 2

    def test_remove_target(self) -> None:
        targets = [GroundTarget("T1", 45.0, 10.0)]
        manager = TargetManager(targets)

        result = manager.remove_target("T1")

        assert result is True
        assert len(manager) == 0

    def test_remove_nonexistent(self) -> None:
        manager = TargetManager()

        result = manager.remove_target("Nonexistent")

        assert result is False


class TestTargetManagerIteration:
    """Tests for TargetManager iteration."""

    def test_iterate_empty(self) -> None:
        manager = TargetManager()

        targets = list(manager)

        assert targets == []

    def test_iterate_targets(self) -> None:
        targets = [
            GroundTarget("T1", 45.0, 10.0),
            GroundTarget("T2", 46.0, 11.0),
        ]
        manager = TargetManager(targets)

        result = list(manager)

        assert len(result) == 2

    def test_targets_property(self) -> None:
        targets = [GroundTarget("T1", 45.0, 10.0)]
        manager = TargetManager(targets)

        result = manager.targets

        assert len(result) == 1


class TestTargetFromDict:
    """Tests for creating targets from dictionaries."""

    def test_basic_from_dict(self) -> None:
        data = {"name": "Test", "latitude": 45.0, "longitude": 10.0}

        target = GroundTarget(**data)

        assert target.name == "Test"

    def test_from_dict_with_all_fields(self) -> None:
        data = {
            "name": "Test",
            "latitude": 45.0,
            "longitude": 10.0,
            "altitude": 100.0,
            "mission_type": "imaging",
        }

        target = GroundTarget(**data)

        assert target.altitude == 100.0
        assert target.mission_type == "imaging"
