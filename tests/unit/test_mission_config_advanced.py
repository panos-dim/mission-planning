"""
Advanced tests for mission_config module.

Tests cover:
- SensorConfig validation
- SpacecraftConfig validation
- MissionTolerances defaults
- MissionConfig composition
- Enum types
"""

from dataclasses import dataclass

import pytest

from mission_planner.mission_config import (
    AimingMode,
    ImagingMode,
    IncidenceMode,
    MissionConfig,
    MissionTolerances,
    SensorConfig,
    SpacecraftConfig,
)


class TestImagingModeEnum:
    """Tests for ImagingMode enum."""

    def test_optical_value(self) -> None:
        assert ImagingMode.OPTICAL.value == "optical"

    def test_sar_value(self) -> None:
        assert ImagingMode.SAR.value == "sar"

    def test_iteration(self) -> None:
        modes = list(ImagingMode)
        assert len(modes) >= 2


class TestAimingModeEnum:
    """Tests for AimingMode enum."""

    def test_target_center_value(self) -> None:
        assert AimingMode.TARGET_CENTER.value == "target_center"

    def test_nadir_value(self) -> None:
        assert AimingMode.NADIR.value == "nadir"


class TestIncidenceModeEnum:
    """Tests for IncidenceMode enum."""

    def test_off_nadir_proxy_value(self) -> None:
        assert IncidenceMode.OFF_NADIR_PROXY.value == "off_nadir_proxy"


class TestSensorConfigInit:
    """Tests for SensorConfig initialization."""

    def test_basic_creation(self) -> None:
        config = SensorConfig(sensor_fov_half_angle_deg=10.0)

        assert config.sensor_fov_half_angle_deg == 10.0
        assert config.mode == ImagingMode.OPTICAL

    def test_with_sar_mode(self) -> None:
        config = SensorConfig(sensor_fov_half_angle_deg=15.0, mode=ImagingMode.SAR)

        assert config.mode == ImagingMode.SAR

    def test_with_optional_fields(self) -> None:
        config = SensorConfig(
            sensor_fov_half_angle_deg=10.0, swath_width_km=100.0, resolution_m=5.0
        )

        assert config.swath_width_km == 100.0
        assert config.resolution_m == 5.0

    def test_optical_sets_default_sun_elevation(self) -> None:
        config = SensorConfig(sensor_fov_half_angle_deg=10.0, mode=ImagingMode.OPTICAL)

        # Should set default sun elevation for optical
        assert config.min_sun_elevation_deg == 30.0


class TestSensorConfigValidation:
    """Tests for SensorConfig validation."""

    def test_invalid_fov_zero(self) -> None:
        with pytest.raises(ValueError):
            SensorConfig(sensor_fov_half_angle_deg=0.0)

    def test_invalid_fov_negative(self) -> None:
        with pytest.raises(ValueError):
            SensorConfig(sensor_fov_half_angle_deg=-10.0)

    def test_invalid_fov_too_large(self) -> None:
        with pytest.raises(ValueError):
            SensorConfig(sensor_fov_half_angle_deg=100.0)

    def test_valid_fov_edge_case(self) -> None:
        # 90 degrees should be valid
        config = SensorConfig(sensor_fov_half_angle_deg=90.0)
        assert config.sensor_fov_half_angle_deg == 90.0

    def test_invalid_incidence_range(self) -> None:
        with pytest.raises(ValueError):
            SensorConfig(
                sensor_fov_half_angle_deg=10.0,
                incidence_angle_range_deg=(50, 30),  # min > max
            )

    def test_valid_incidence_range(self) -> None:
        config = SensorConfig(
            sensor_fov_half_angle_deg=10.0, incidence_angle_range_deg=(20, 45)
        )
        assert config.incidence_angle_range_deg == (20, 45)


class TestSpacecraftConfigInit:
    """Tests for SpacecraftConfig initialization."""

    def test_basic_creation(self) -> None:
        config = SpacecraftConfig(max_spacecraft_roll_deg=45.0)

        assert config.max_spacecraft_roll_deg == 45.0
        assert config.max_roll_rate_dps == 1.0  # default

    def test_with_custom_rates(self) -> None:
        config = SpacecraftConfig(
            max_spacecraft_roll_deg=30.0, max_roll_rate_dps=2.0, max_roll_accel_dps2=0.5
        )

        assert config.max_roll_rate_dps == 2.0
        assert config.max_roll_accel_dps2 == 0.5

    def test_with_pitch_config(self) -> None:
        config = SpacecraftConfig(
            max_spacecraft_roll_deg=45.0, max_pitch_deg=20.0, max_pitch_rate_dps=1.5
        )

        assert config.max_pitch_deg == 20.0
        assert config.max_pitch_rate_dps == 1.5

    def test_settling_time(self) -> None:
        config = SpacecraftConfig(max_spacecraft_roll_deg=45.0, settling_time_s=10.0)

        assert config.settling_time_s == 10.0


class TestSpacecraftConfigValidation:
    """Tests for SpacecraftConfig validation."""

    def test_invalid_roll_zero(self) -> None:
        with pytest.raises(ValueError):
            SpacecraftConfig(max_spacecraft_roll_deg=0.0)

    def test_invalid_roll_negative(self) -> None:
        with pytest.raises(ValueError):
            SpacecraftConfig(max_spacecraft_roll_deg=-10.0)

    def test_invalid_roll_too_large(self) -> None:
        with pytest.raises(ValueError):
            SpacecraftConfig(max_spacecraft_roll_deg=100.0)

    def test_invalid_roll_rate_zero(self) -> None:
        with pytest.raises(ValueError):
            SpacecraftConfig(max_spacecraft_roll_deg=45.0, max_roll_rate_dps=0.0)

    def test_invalid_roll_rate_negative(self) -> None:
        with pytest.raises(ValueError):
            SpacecraftConfig(max_spacecraft_roll_deg=45.0, max_roll_rate_dps=-1.0)

    def test_invalid_accel_zero(self) -> None:
        with pytest.raises(ValueError):
            SpacecraftConfig(max_spacecraft_roll_deg=45.0, max_roll_accel_dps2=0.0)


class TestMissionTolerancesInit:
    """Tests for MissionTolerances initialization."""

    def test_default_creation(self) -> None:
        tolerances = MissionTolerances()

        assert tolerances.aiming_epsilon_deg == 0.1
        assert tolerances.time_edge_epsilon_s == 0.5

    def test_custom_tolerances(self) -> None:
        tolerances = MissionTolerances(aiming_epsilon_deg=0.05, time_edge_epsilon_s=1.0)

        assert tolerances.aiming_epsilon_deg == 0.05
        assert tolerances.time_edge_epsilon_s == 1.0

    def test_default_aiming_mode(self) -> None:
        tolerances = MissionTolerances()

        assert tolerances.aiming_mode == AimingMode.TARGET_CENTER

    def test_default_incidence_mode(self) -> None:
        tolerances = MissionTolerances()

        assert tolerances.incidence_mode == IncidenceMode.OFF_NADIR_PROXY

    def test_coordinate_precision_note(self) -> None:
        tolerances = MissionTolerances()

        assert "float64" in tolerances.coordinate_precision_note


class TestMissionConfigInit:
    """Tests for MissionConfig initialization."""

    def test_basic_creation(self) -> None:
        sensor = SensorConfig(sensor_fov_half_angle_deg=10.0)
        spacecraft = SpacecraftConfig(max_spacecraft_roll_deg=45.0)

        config = MissionConfig(sensor=sensor, spacecraft=spacecraft)

        assert config.sensor == sensor
        assert config.spacecraft == spacecraft

    def test_with_tolerances(self) -> None:
        sensor = SensorConfig(sensor_fov_half_angle_deg=10.0)
        spacecraft = SpacecraftConfig(max_spacecraft_roll_deg=45.0)
        tolerances = MissionTolerances(aiming_epsilon_deg=0.2)

        config = MissionConfig(
            sensor=sensor, spacecraft=spacecraft, tolerances=tolerances
        )

        assert config.tolerances.aiming_epsilon_deg == 0.2

    def test_default_tolerances(self) -> None:
        sensor = SensorConfig(sensor_fov_half_angle_deg=10.0)
        spacecraft = SpacecraftConfig(max_spacecraft_roll_deg=45.0)

        config = MissionConfig(sensor=sensor, spacecraft=spacecraft)

        # tolerances should be set to default in __post_init__
        assert config.tolerances is not None


class TestSensorConfigSARFields:
    """Tests for SAR-specific sensor fields."""

    def test_sar_mode_field(self) -> None:
        config = SensorConfig(
            sensor_fov_half_angle_deg=15.0, mode=ImagingMode.SAR, sar_mode="stripmap"
        )

        assert config.sar_mode == "stripmap"

    def test_polarizations_field(self) -> None:
        config = SensorConfig(
            sensor_fov_half_angle_deg=15.0,
            mode=ImagingMode.SAR,
            polarizations=["VV", "VH"],
        )

        assert "VV" in config.polarizations


class TestSensorConfigOpticalFields:
    """Tests for optical-specific sensor fields."""

    def test_cloud_cover_field(self) -> None:
        config = SensorConfig(
            sensor_fov_half_angle_deg=10.0,
            mode=ImagingMode.OPTICAL,
            max_cloud_cover_percent=20.0,
        )

        assert config.max_cloud_cover_percent == 20.0

    def test_custom_sun_elevation(self) -> None:
        config = SensorConfig(
            sensor_fov_half_angle_deg=10.0,
            mode=ImagingMode.OPTICAL,
            min_sun_elevation_deg=45.0,
        )

        assert config.min_sun_elevation_deg == 45.0
