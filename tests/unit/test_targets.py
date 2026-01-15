"""
Tests for targets module.
"""

import pytest
from mission_planner.targets import GroundTarget


class TestGroundTarget:
    """Tests for GroundTarget dataclass."""

    def test_basic_creation(self) -> None:
        target = GroundTarget(name="Dubai", latitude=25.2048, longitude=55.2708)
        assert target.name == "Dubai"
        assert target.latitude == 25.2048
        assert target.longitude == 55.2708

    def test_default_values(self) -> None:
        target = GroundTarget(name="Test", latitude=0.0, longitude=0.0)
        assert target.elevation_mask == 10.0
        assert target.priority == 1
        assert target.mission_type == "imaging"

    def test_custom_elevation_mask(self) -> None:
        target = GroundTarget(name="Test", latitude=0.0, longitude=0.0, elevation_mask=15.0)
        assert target.elevation_mask == 15.0

    def test_custom_priority(self) -> None:
        target = GroundTarget(name="Test", latitude=0.0, longitude=0.0, priority=5)
        assert target.priority == 5

    def test_negative_coordinates(self) -> None:
        target = GroundTarget(name="Sydney", latitude=-33.8688, longitude=-151.2093)
        assert target.latitude == -33.8688
        assert target.longitude == -151.2093

    def test_boundary_coordinates(self) -> None:
        target_north = GroundTarget(name="North", latitude=90.0, longitude=0.0)
        assert target_north.latitude == 90.0

        target_south = GroundTarget(name="South", latitude=-90.0, longitude=0.0)
        assert target_south.latitude == -90.0

    def test_imaging_mission(self) -> None:
        target = GroundTarget(name="Test", latitude=25.0, longitude=55.0, mission_type="imaging")
        assert target.mission_type == "imaging"
        assert target.sensor_fov_half_angle_deg == 1.0
        assert target.max_spacecraft_roll == 45.0

    def test_communication_mission(self) -> None:
        target = GroundTarget(name="Test", latitude=25.0, longitude=55.0, mission_type="communication")
        assert target.mission_type == "communication"

    def test_custom_sensor_fov(self) -> None:
        target = GroundTarget(
            name="Test", latitude=25.0, longitude=55.0,
            mission_type="imaging", sensor_fov_half_angle_deg=30.0
        )
        assert target.sensor_fov_half_angle_deg == 30.0

    def test_custom_max_roll(self) -> None:
        target = GroundTarget(
            name="Test", latitude=25.0, longitude=55.0,
            mission_type="imaging", max_spacecraft_roll=30.0
        )
        assert target.max_spacecraft_roll == 30.0

    def test_with_description(self) -> None:
        target = GroundTarget(
            name="Test", latitude=25.0, longitude=55.0,
            description="Test target"
        )
        assert target.description == "Test target"

    def test_with_color(self) -> None:
        target = GroundTarget(
            name="Test", latitude=25.0, longitude=55.0,
            color="#EF4444"
        )
        assert target.color == "#EF4444"

    def test_with_altitude(self) -> None:
        target = GroundTarget(
            name="Mountain", latitude=25.0, longitude=55.0,
            altitude=1000.0
        )
        assert target.altitude == 1000.0

    def test_invalid_latitude_high(self) -> None:
        with pytest.raises(ValueError):
            GroundTarget(name="Invalid", latitude=91.0, longitude=0.0)

    def test_invalid_latitude_low(self) -> None:
        with pytest.raises(ValueError):
            GroundTarget(name="Invalid", latitude=-91.0, longitude=0.0)

    def test_invalid_longitude_high(self) -> None:
        with pytest.raises(ValueError):
            GroundTarget(name="Invalid", latitude=0.0, longitude=181.0)

    def test_invalid_longitude_low(self) -> None:
        with pytest.raises(ValueError):
            GroundTarget(name="Invalid", latitude=0.0, longitude=-181.0)
