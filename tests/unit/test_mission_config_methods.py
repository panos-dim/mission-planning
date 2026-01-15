"""
Tests for mission_config module methods.

Tests cover:
- create_default_mission_config function
- MissionConfig.validate_compatibility method
- Default configurations
"""

import pytest

from mission_planner.mission_config import (
    DEFAULT_OPTICAL_SENSOR,
    DEFAULT_OPTICAL_SPACECRAFT,
    DEFAULT_SAR_SENSOR,
    DEFAULT_SAR_SPACECRAFT,
    ImagingMode,
    MissionConfig,
    MissionTolerances,
    SensorConfig,
    SpacecraftConfig,
    create_default_mission_config,
)


class TestCreateDefaultMissionConfig:
    """Tests for create_default_mission_config function."""

    def test_optical_mode(self) -> None:
        config = create_default_mission_config("optical")

        assert config is not None
        assert config.sensor.mode == ImagingMode.OPTICAL

    def test_sar_mode(self) -> None:
        config = create_default_mission_config("sar")

        assert config is not None
        assert config.sensor.mode == ImagingMode.SAR

    def test_optical_mode_uppercase(self) -> None:
        config = create_default_mission_config("OPTICAL")

        assert config.sensor.mode == ImagingMode.OPTICAL

    def test_sar_mode_uppercase(self) -> None:
        config = create_default_mission_config("SAR")

        assert config.sensor.mode == ImagingMode.SAR

    def test_none_defaults_to_optical(self) -> None:
        config = create_default_mission_config(None)

        assert config.sensor.mode == ImagingMode.OPTICAL

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValueError):
            create_default_mission_config("invalid")


class TestMissionConfigValidateCompatibility:
    """Tests for MissionConfig.validate_compatibility method."""

    def test_valid_config(self) -> None:
        sensor = SensorConfig(sensor_fov_half_angle_deg=10.0)
        spacecraft = SpacecraftConfig(max_spacecraft_roll_deg=45.0)
        config = MissionConfig(sensor=sensor, spacecraft=spacecraft)

        result = config.validate_compatibility()

        assert result is True

    def test_fov_exceeds_roll_warning(self) -> None:
        # FOV > roll limit triggers warning but still returns True
        sensor = SensorConfig(sensor_fov_half_angle_deg=50.0)
        spacecraft = SpacecraftConfig(max_spacecraft_roll_deg=30.0)
        config = MissionConfig(sensor=sensor, spacecraft=spacecraft)

        result = config.validate_compatibility()

        assert result is True


class TestDefaultConfigurations:
    """Tests for default configuration constants."""

    def test_default_optical_sensor(self) -> None:
        assert DEFAULT_OPTICAL_SENSOR is not None
        assert DEFAULT_OPTICAL_SENSOR.mode == ImagingMode.OPTICAL

    def test_default_sar_sensor(self) -> None:
        assert DEFAULT_SAR_SENSOR is not None
        assert DEFAULT_SAR_SENSOR.mode == ImagingMode.SAR

    def test_default_optical_spacecraft(self) -> None:
        assert DEFAULT_OPTICAL_SPACECRAFT is not None
        assert DEFAULT_OPTICAL_SPACECRAFT.max_spacecraft_roll_deg > 0

    def test_default_sar_spacecraft(self) -> None:
        assert DEFAULT_SAR_SPACECRAFT is not None
        assert DEFAULT_SAR_SPACECRAFT.max_spacecraft_roll_deg > 0


class TestMissionConfigPostInit:
    """Tests for MissionConfig __post_init__ method."""

    def test_default_tolerances_set(self) -> None:
        sensor = SensorConfig(sensor_fov_half_angle_deg=10.0)
        spacecraft = SpacecraftConfig(max_spacecraft_roll_deg=45.0)
        config = MissionConfig(sensor=sensor, spacecraft=spacecraft)

        assert config.tolerances is not None
        assert isinstance(config.tolerances, MissionTolerances)

    def test_custom_tolerances_preserved(self) -> None:
        sensor = SensorConfig(sensor_fov_half_angle_deg=10.0)
        spacecraft = SpacecraftConfig(max_spacecraft_roll_deg=45.0)
        tolerances = MissionTolerances(aiming_epsilon_deg=0.5)
        config = MissionConfig(
            sensor=sensor, spacecraft=spacecraft, tolerances=tolerances
        )

        assert config.tolerances.aiming_epsilon_deg == 0.5


class TestMissionTolerancesDefaults:
    """Tests for MissionTolerances default values."""

    def test_default_creation(self) -> None:
        tolerances = MissionTolerances()

        assert tolerances is not None

    def test_has_aiming_epsilon(self) -> None:
        tolerances = MissionTolerances()

        assert hasattr(tolerances, "aiming_epsilon_deg")

    def test_has_time_edge_epsilon(self) -> None:
        tolerances = MissionTolerances()

        assert hasattr(tolerances, "time_edge_epsilon_s")


class TestSensorConfigModes:
    """Tests for SensorConfig imaging modes."""

    def test_optical_mode(self) -> None:
        sensor = SensorConfig(sensor_fov_half_angle_deg=10.0, mode=ImagingMode.OPTICAL)

        assert sensor.mode == ImagingMode.OPTICAL

    def test_sar_mode(self) -> None:
        sensor = SensorConfig(sensor_fov_half_angle_deg=30.0, mode=ImagingMode.SAR)

        assert sensor.mode == ImagingMode.SAR

    def test_default_mode(self) -> None:
        sensor = SensorConfig(sensor_fov_half_angle_deg=10.0)

        # Default should be set
        assert sensor.mode is not None


class TestSpacecraftConfigLimits:
    """Tests for SpacecraftConfig limit values."""

    def test_roll_limit(self) -> None:
        spacecraft = SpacecraftConfig(max_spacecraft_roll_deg=30.0)

        assert spacecraft.max_spacecraft_roll_deg == 30.0

    def test_roll_rate(self) -> None:
        spacecraft = SpacecraftConfig(
            max_spacecraft_roll_deg=45.0, max_roll_rate_dps=2.0
        )

        assert spacecraft.max_roll_rate_dps == 2.0

    def test_settling_time(self) -> None:
        spacecraft = SpacecraftConfig(
            max_spacecraft_roll_deg=45.0, settling_time_s=10.0
        )

        assert spacecraft.settling_time_s == 10.0
