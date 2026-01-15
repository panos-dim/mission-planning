"""
Advanced tests for targets module.

Tests cover:
- TargetManager operations
- File I/O operations
- Region filtering
- Edge cases
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mission_planner.targets import GroundTarget, TargetManager


class TestTargetManagerInit:
    """Tests for TargetManager initialization."""

    def test_empty_initialization(self) -> None:
        tm = TargetManager()

        assert len(tm) == 0
        assert list(tm.targets) == []

    def test_init_with_targets(self) -> None:
        targets = [
            GroundTarget(name="T1", latitude=45.0, longitude=10.0),
            GroundTarget(name="T2", latitude=50.0, longitude=15.0),
        ]

        tm = TargetManager(targets)

        assert len(tm) == 2

    def test_init_with_none(self) -> None:
        tm = TargetManager(None)

        assert len(tm) == 0


class TestTargetManagerAddTarget:
    """Tests for add_target method."""

    @pytest.fixture
    def tm(self):
        return TargetManager()

    def test_add_single_target(self, tm) -> None:
        target = GroundTarget(name="Test", latitude=45.0, longitude=10.0)

        tm.add_target(target)

        assert len(tm) == 1
        assert tm.targets[0].name == "Test"

    def test_add_multiple_targets(self, tm) -> None:
        for i in range(5):
            tm.add_target(
                GroundTarget(name=f"T{i}", latitude=45.0 + i, longitude=10.0 + i)
            )

        assert len(tm) == 5

    def test_add_duplicate_name_warning(self, tm) -> None:
        tm.add_target(GroundTarget(name="Duplicate", latitude=45.0, longitude=10.0))
        tm.add_target(GroundTarget(name="Duplicate", latitude=50.0, longitude=15.0))

        # Both should be added (with warning)
        assert len(tm) == 2

    def test_add_invalid_type_raises(self, tm) -> None:
        with pytest.raises(TypeError):
            tm.add_target("not a target")

    def test_add_none_raises(self, tm) -> None:
        with pytest.raises(TypeError):
            tm.add_target(None)


class TestTargetManagerRemoveTarget:
    """Tests for remove_target method."""

    @pytest.fixture
    def tm_with_targets(self):
        tm = TargetManager()
        tm.add_target(GroundTarget(name="T1", latitude=45.0, longitude=10.0))
        tm.add_target(GroundTarget(name="T2", latitude=50.0, longitude=15.0))
        tm.add_target(GroundTarget(name="T3", latitude=55.0, longitude=20.0))
        return tm

    def test_remove_existing_target(self, tm_with_targets) -> None:
        result = tm_with_targets.remove_target("T2")

        assert result is True
        assert len(tm_with_targets) == 2
        names = [t.name for t in tm_with_targets.targets]
        assert "T2" not in names

    def test_remove_nonexistent_target(self, tm_with_targets) -> None:
        result = tm_with_targets.remove_target("NonExistent")

        assert result is False
        assert len(tm_with_targets) == 3

    def test_remove_first_target(self, tm_with_targets) -> None:
        result = tm_with_targets.remove_target("T1")

        assert result is True
        assert tm_with_targets.targets[0].name == "T2"

    def test_remove_last_target(self, tm_with_targets) -> None:
        result = tm_with_targets.remove_target("T3")

        assert result is True
        assert len(tm_with_targets) == 2


class TestTargetManagerGetTarget:
    """Tests for get_target method."""

    @pytest.fixture
    def tm_with_targets(self):
        tm = TargetManager()
        tm.add_target(GroundTarget(name="Alpha", latitude=45.0, longitude=10.0))
        tm.add_target(GroundTarget(name="Beta", latitude=50.0, longitude=15.0))
        return tm

    def test_get_existing_target(self, tm_with_targets) -> None:
        target = tm_with_targets.get_target("Alpha")

        assert target is not None
        assert target.name == "Alpha"
        assert target.latitude == 45.0

    def test_get_nonexistent_target(self, tm_with_targets) -> None:
        target = tm_with_targets.get_target("Gamma")

        assert target is None


class TestTargetManagerGetTargetsInRegion:
    """Tests for get_targets_in_region method."""

    @pytest.fixture
    def tm_with_spread_targets(self):
        tm = TargetManager()
        # Cluster of nearby targets
        tm.add_target(GroundTarget(name="Near1", latitude=45.0, longitude=10.0))
        tm.add_target(GroundTarget(name="Near2", latitude=45.1, longitude=10.1))
        # Far target
        tm.add_target(GroundTarget(name="Far", latitude=60.0, longitude=30.0))
        return tm

    def test_get_nearby_targets(self, tm_with_spread_targets) -> None:
        nearby = tm_with_spread_targets.get_targets_in_region(45.0, 10.0, 50.0)

        # Should get Near1 and Near2
        names = [t.name for t in nearby]
        assert "Near1" in names
        assert "Near2" in names
        assert "Far" not in names

    def test_get_all_targets_large_radius(self, tm_with_spread_targets) -> None:
        all_targets = tm_with_spread_targets.get_targets_in_region(45.0, 10.0, 5000.0)

        assert len(all_targets) == 3

    def test_get_no_targets_small_radius(self, tm_with_spread_targets) -> None:
        no_targets = tm_with_spread_targets.get_targets_in_region(0.0, 0.0, 1.0)

        assert len(no_targets) == 0


class TestTargetManagerFileIO:
    """Tests for file save/load operations."""

    @pytest.fixture
    def tm_with_targets(self):
        tm = TargetManager()
        tm.add_target(GroundTarget(name="T1", latitude=45.0, longitude=10.0))
        tm.add_target(
            GroundTarget(
                name="T2", latitude=50.0, longitude=15.0, mission_type="imaging"
            )
        )
        return tm

    def test_save_to_file(self, tm_with_targets) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = f.name

        tm_with_targets.save_to_file(filepath)

        # Verify file exists and is valid JSON
        with open(filepath, "r") as f:
            data = json.load(f)

        assert "targets" in data
        assert data["count"] == 2

        # Cleanup
        Path(filepath).unlink()

    def test_load_from_file(self, tm_with_targets) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = f.name

        # Save first
        tm_with_targets.save_to_file(filepath)

        # Load
        loaded_tm = TargetManager.load_from_file(filepath)

        assert len(loaded_tm) == 2

        # Cleanup
        Path(filepath).unlink()

    def test_round_trip_preserves_data(self, tm_with_targets) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = f.name

        tm_with_targets.save_to_file(filepath)
        loaded_tm = TargetManager.load_from_file(filepath)

        # Check data preserved
        original_names = {t.name for t in tm_with_targets.targets}
        loaded_names = {t.name for t in loaded_tm.targets}

        assert original_names == loaded_names

        # Cleanup
        Path(filepath).unlink()


class TestTargetManagerLen:
    """Tests for __len__ method."""

    def test_len_empty(self) -> None:
        tm = TargetManager()

        assert len(tm) == 0

    def test_len_with_targets(self) -> None:
        tm = TargetManager()
        tm.add_target(GroundTarget(name="T1", latitude=45.0, longitude=10.0))
        tm.add_target(GroundTarget(name="T2", latitude=50.0, longitude=15.0))

        assert len(tm) == 2


class TestGroundTargetStr:
    """Tests for GroundTarget string representations."""

    def test_str(self) -> None:
        target = GroundTarget(name="TestTarget", latitude=45.1234, longitude=10.5678)

        result = str(target)

        assert "TestTarget" in result
        assert "45.1234" in result
        assert "10.5678" in result

    def test_repr(self) -> None:
        target = GroundTarget(name="TestTarget", latitude=45.1234, longitude=10.5678)

        result = repr(target)

        assert "GroundTarget" in result
        assert "TestTarget" in result


class TestGroundTargetDistanceTo:
    """Tests for distance_to method."""

    def test_same_location_zero_distance(self) -> None:
        t1 = GroundTarget(name="T1", latitude=45.0, longitude=10.0)
        t2 = GroundTarget(name="T2", latitude=45.0, longitude=10.0)

        distance = t1.distance_to(t2)

        assert distance < 1.0  # Should be essentially zero

    def test_known_distance(self) -> None:
        # Paris to London is approximately 343 km
        paris = GroundTarget(name="Paris", latitude=48.8566, longitude=2.3522)
        london = GroundTarget(name="London", latitude=51.5074, longitude=-0.1278)

        distance = paris.distance_to(london)

        # Should be approximately 343 km (within 10%)
        assert 300 < distance < 400

    def test_antipodal_points(self) -> None:
        # Points on opposite sides of Earth
        t1 = GroundTarget(name="T1", latitude=0.0, longitude=0.0)
        t2 = GroundTarget(name="T2", latitude=0.0, longitude=180.0)

        distance = t1.distance_to(t2)

        # Should be approximately half Earth's circumference (~20,000 km)
        assert 19000 < distance < 21000


class TestGroundTargetToDict:
    """Tests for to_dict method."""

    def test_basic_to_dict(self) -> None:
        target = GroundTarget(name="Test", latitude=45.0, longitude=10.0)

        result = target.to_dict()

        assert result["name"] == "Test"
        assert result["latitude"] == 45.0
        assert result["longitude"] == 10.0

    def test_to_dict_with_all_fields(self) -> None:
        target = GroundTarget(
            name="Test",
            latitude=45.0,
            longitude=10.0,
            elevation_mask=15.0,
            altitude=100.0,
            mission_type="imaging",
        )

        result = target.to_dict()

        assert result["elevation_mask"] == 15.0
        assert result["altitude"] == 100.0
        assert result["mission_type"] == "imaging"


class TestGroundTargetFromDict:
    """Tests for from_dict class method."""

    def test_basic_from_dict(self) -> None:
        data = {"name": "Test", "latitude": 45.0, "longitude": 10.0}

        target = GroundTarget.from_dict(data)

        assert target.name == "Test"
        assert target.latitude == 45.0
        assert target.longitude == 10.0

    def test_from_dict_with_all_fields(self) -> None:
        data = {
            "name": "Test",
            "latitude": 45.0,
            "longitude": 10.0,
            "elevation_mask": 15.0,
            "altitude": 100.0,
            "mission_type": "imaging",
        }

        target = GroundTarget.from_dict(data)

        assert target.elevation_mask == 15.0
        assert target.altitude == 100.0
        assert target.mission_type == "imaging"

    def test_round_trip(self) -> None:
        original = GroundTarget(
            name="Test",
            latitude=45.0,
            longitude=10.0,
            elevation_mask=15.0,
            mission_type="communication",
        )

        data = original.to_dict()
        restored = GroundTarget.from_dict(data)

        assert restored.name == original.name
        assert restored.latitude == original.latitude
        assert restored.longitude == original.longitude
        assert restored.elevation_mask == original.elevation_mask
        assert restored.mission_type == original.mission_type
