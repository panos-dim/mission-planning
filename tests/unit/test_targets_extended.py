"""
Extended tests for targets module.

Tests cover:
- GroundTarget dataclass validation
- Coordinate validation
- Mission type validation
- to_dict and from_dict methods
- Distance calculations
"""

import math
from unittest.mock import patch

import pytest

from mission_planner.targets import GroundTarget


class TestGroundTargetBasic:
    """Basic tests for GroundTarget dataclass."""

    def test_minimal_creation(self) -> None:
        target = GroundTarget(
            name="TestTarget",
            latitude=45.0,
            longitude=10.0,
        )

        assert target.name == "TestTarget"
        assert target.latitude == 45.0
        assert target.longitude == 10.0

    def test_default_values(self) -> None:
        target = GroundTarget(
            name="TestTarget",
            latitude=45.0,
            longitude=10.0,
        )

        assert target.elevation_mask == 10.0
        assert target.altitude == 0.0
        assert target.mission_type == "imaging"
        assert target.priority == 5

    def test_custom_values(self) -> None:
        target = GroundTarget(
            name="CustomTarget",
            latitude=50.0,
            longitude=20.0,
            elevation_mask=15.0,
            altitude=100.0,
            mission_type="communication",
            priority=5,
            description="A custom target",
        )

        assert target.elevation_mask == 15.0
        assert target.altitude == 100.0
        assert target.mission_type == "communication"
        assert target.priority == 5
        assert target.description == "A custom target"

    def test_with_color(self) -> None:
        target = GroundTarget(
            name="ColoredTarget",
            latitude=45.0,
            longitude=10.0,
            color="#FF0000",
        )

        assert target.color == "#FF0000"


class TestGroundTargetValidation:
    """Tests for GroundTarget validation."""

    def test_valid_latitude_range(self) -> None:
        # Test boundary values
        target_north = GroundTarget(name="North", latitude=90.0, longitude=0.0)
        target_south = GroundTarget(name="South", latitude=-90.0, longitude=0.0)
        target_equator = GroundTarget(name="Equator", latitude=0.0, longitude=0.0)

        assert target_north.latitude == 90.0
        assert target_south.latitude == -90.0
        assert target_equator.latitude == 0.0

    def test_invalid_latitude_too_high(self) -> None:
        with pytest.raises(ValueError, match="Invalid latitude"):
            GroundTarget(name="Invalid", latitude=91.0, longitude=0.0)

    def test_invalid_latitude_too_low(self) -> None:
        with pytest.raises(ValueError, match="Invalid latitude"):
            GroundTarget(name="Invalid", latitude=-91.0, longitude=0.0)

    def test_valid_longitude_range(self) -> None:
        target_east = GroundTarget(name="East", latitude=0.0, longitude=180.0)
        target_west = GroundTarget(name="West", latitude=0.0, longitude=-180.0)
        target_prime = GroundTarget(name="Prime", latitude=0.0, longitude=0.0)

        assert target_east.longitude == 180.0
        assert target_west.longitude == -180.0
        assert target_prime.longitude == 0.0

    def test_invalid_longitude_too_high(self) -> None:
        with pytest.raises(ValueError, match="Invalid longitude"):
            GroundTarget(name="Invalid", latitude=0.0, longitude=181.0)

    def test_invalid_longitude_too_low(self) -> None:
        with pytest.raises(ValueError, match="Invalid longitude"):
            GroundTarget(name="Invalid", latitude=0.0, longitude=-181.0)

    def test_valid_elevation_mask(self) -> None:
        target_low = GroundTarget(
            name="Low", latitude=0.0, longitude=0.0, elevation_mask=0.0
        )
        target_high = GroundTarget(
            name="High", latitude=0.0, longitude=0.0, elevation_mask=90.0
        )

        assert target_low.elevation_mask == 0.0
        assert target_high.elevation_mask == 90.0

    def test_invalid_elevation_mask_negative(self) -> None:
        with pytest.raises(ValueError, match="Invalid elevation mask"):
            GroundTarget(
                name="Invalid", latitude=0.0, longitude=0.0, elevation_mask=-1.0
            )

    def test_invalid_elevation_mask_too_high(self) -> None:
        with pytest.raises(ValueError, match="Invalid elevation mask"):
            GroundTarget(
                name="Invalid", latitude=0.0, longitude=0.0, elevation_mask=91.0
            )

    def test_valid_mission_types(self) -> None:
        target_imaging = GroundTarget(
            name="Imaging", latitude=0.0, longitude=0.0, mission_type="imaging"
        )
        target_comm = GroundTarget(
            name="Comm", latitude=0.0, longitude=0.0, mission_type="communication"
        )

        assert target_imaging.mission_type == "imaging"
        assert target_comm.mission_type == "communication"

    def test_invalid_mission_type(self) -> None:
        with pytest.raises(ValueError, match="Invalid mission type"):
            GroundTarget(
                name="Invalid", latitude=0.0, longitude=0.0, mission_type="invalid"
            )


class TestGroundTargetSensorFOV:
    """Tests for sensor FOV handling."""

    def test_default_sensor_fov_imaging(self) -> None:
        target = GroundTarget(
            name="Imaging",
            latitude=45.0,
            longitude=10.0,
            mission_type="imaging",
        )

        # Should have default sensor FOV set
        assert target.sensor_fov_half_angle_deg is not None

    def test_custom_sensor_fov(self) -> None:
        target = GroundTarget(
            name="Custom",
            latitude=45.0,
            longitude=10.0,
            sensor_fov_half_angle_deg=5.0,
        )

        assert target.sensor_fov_half_angle_deg == 5.0

    def test_invalid_sensor_fov_zero(self) -> None:
        with pytest.raises(ValueError, match="Invalid sensor_fov_half_angle_deg"):
            GroundTarget(
                name="Invalid",
                latitude=45.0,
                longitude=10.0,
                sensor_fov_half_angle_deg=0.0,
            )

    def test_invalid_sensor_fov_too_high(self) -> None:
        with pytest.raises(ValueError, match="Invalid sensor_fov_half_angle_deg"):
            GroundTarget(
                name="Invalid",
                latitude=45.0,
                longitude=10.0,
                sensor_fov_half_angle_deg=91.0,
            )

    def test_max_spacecraft_roll_default(self) -> None:
        target = GroundTarget(
            name="Roll",
            latitude=45.0,
            longitude=10.0,
            mission_type="imaging",
        )

        # Should have default max_spacecraft_roll set for imaging
        assert target.max_spacecraft_roll is not None


class TestGroundTargetToDict:
    """Tests for to_dict method."""

    def test_to_dict_basic(self) -> None:
        target = GroundTarget(
            name="TestTarget",
            latitude=45.0,
            longitude=10.0,
        )

        result = target.to_dict()

        assert result["name"] == "TestTarget"
        assert result["latitude"] == 45.0
        assert result["longitude"] == 10.0
        assert "elevation_mask" in result
        assert "mission_type" in result

    def test_to_dict_all_fields(self) -> None:
        target = GroundTarget(
            name="FullTarget",
            latitude=50.0,
            longitude=20.0,
            elevation_mask=15.0,
            altitude=500.0,
            mission_type="communication",
            sensor_fov_half_angle_deg=30.0,
            description="Full description",
        )

        result = target.to_dict()

        assert result["altitude"] == 500.0
        assert result["sensor_fov_half_angle_deg"] == 30.0


class TestGroundTargetFromDict:
    """Tests for from_dict class method."""

    def test_from_dict_basic(self) -> None:
        data = {
            "name": "FromDict",
            "latitude": 40.0,
            "longitude": 15.0,
        }

        target = GroundTarget.from_dict(data)

        assert target.name == "FromDict"
        assert target.latitude == 40.0
        assert target.longitude == 15.0

    def test_from_dict_full(self) -> None:
        data = {
            "name": "FullFromDict",
            "latitude": 35.0,
            "longitude": 25.0,
            "elevation_mask": 12.0,
            "mission_type": "communication",
            "priority": 3,
        }

        target = GroundTarget.from_dict(data)

        assert target.elevation_mask == 12.0
        assert target.mission_type == "communication"
        assert target.priority == 3

    def test_roundtrip(self) -> None:
        original = GroundTarget(
            name="Roundtrip",
            latitude=55.0,
            longitude=-5.0,
            elevation_mask=20.0,
            mission_type="imaging",
        )

        data = original.to_dict()
        reconstructed = GroundTarget.from_dict(data)

        assert reconstructed.name == original.name
        assert reconstructed.latitude == original.latitude
        assert reconstructed.longitude == original.longitude


class TestGroundTargetDistanceTo:
    """Tests for distance_to method."""

    def test_same_location_zero_distance(self) -> None:
        target1 = GroundTarget(name="T1", latitude=45.0, longitude=10.0)
        target2 = GroundTarget(name="T2", latitude=45.0, longitude=10.0)

        distance = target1.distance_to(target2)

        assert distance == pytest.approx(0.0, abs=0.01)

    def test_known_distance(self) -> None:
        # London to Paris is approximately 344 km
        london = GroundTarget(name="London", latitude=51.5074, longitude=-0.1278)
        paris = GroundTarget(name="Paris", latitude=48.8566, longitude=2.3522)

        distance = london.distance_to(paris)

        assert 340 < distance < 350  # Allow some tolerance

    def test_antipodal_points(self) -> None:
        # Antipodal points should be half Earth's circumference apart
        north = GroundTarget(name="North", latitude=0.0, longitude=0.0)
        south = GroundTarget(name="South", latitude=0.0, longitude=180.0)

        distance = north.distance_to(south)

        # Half Earth circumference is about 20,000 km
        assert 19000 < distance < 21000

    def test_equatorial_distance(self) -> None:
        # Two points on equator, 90 degrees apart
        p1 = GroundTarget(name="P1", latitude=0.0, longitude=0.0)
        p2 = GroundTarget(name="P2", latitude=0.0, longitude=90.0)

        distance = p1.distance_to(p2)

        # Quarter of Earth circumference is about 10,000 km
        assert 9900 < distance < 10100

    def test_distance_symmetry(self) -> None:
        t1 = GroundTarget(name="T1", latitude=45.0, longitude=10.0)
        t2 = GroundTarget(name="T2", latitude=50.0, longitude=15.0)

        d1 = t1.distance_to(t2)
        d2 = t2.distance_to(t1)

        assert d1 == pytest.approx(d2, rel=0.001)


class TestGroundTargetEdgeCases:
    """Tests for edge cases."""

    def test_polar_target(self) -> None:
        target = GroundTarget(
            name="NorthPole",
            latitude=90.0,
            longitude=0.0,
        )

        assert target.latitude == 90.0

    def test_dateline_crossing(self) -> None:
        # Target near international date line
        target = GroundTarget(
            name="Dateline",
            latitude=0.0,
            longitude=179.9,
        )

        assert target.longitude == 179.9

    def test_very_small_elevation_mask(self) -> None:
        target = GroundTarget(
            name="LowMask",
            latitude=0.0,
            longitude=0.0,
            elevation_mask=0.1,
        )

        assert target.elevation_mask == 0.1

    def test_high_altitude_target(self) -> None:
        # Mountain target
        target = GroundTarget(
            name="MountEverest",
            latitude=27.9881,
            longitude=86.9250,
            altitude=8848.86,  # meters
        )

        assert target.altitude == 8848.86

    def test_unicode_name(self) -> None:
        target = GroundTarget(
            name="東京 Tokyo",
            latitude=35.6762,
            longitude=139.6503,
        )

        assert "Tokyo" in target.name

    def test_empty_description(self) -> None:
        target = GroundTarget(
            name="NoDesc",
            latitude=0.0,
            longitude=0.0,
            description="",
        )

        assert target.description == ""
