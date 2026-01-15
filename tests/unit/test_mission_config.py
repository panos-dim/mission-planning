"""
Tests for mission_config module.
"""

import pytest
from mission_planner.mission_config import (
    ImagingMode,
    AimingMode,
    IncidenceMode,
    SensorConfig,
    SpacecraftConfig,
)


class TestImagingMode:
    """Tests for ImagingMode enum."""

    def test_optical_value(self) -> None:
        assert ImagingMode.OPTICAL.value == "optical"

    def test_sar_value(self) -> None:
        assert ImagingMode.SAR.value == "sar"


class TestAimingMode:
    """Tests for AimingMode enum."""

    def test_target_center(self) -> None:
        assert AimingMode.TARGET_CENTER.value == "target_center"

    def test_nadir(self) -> None:
        assert AimingMode.NADIR.value == "nadir"


class TestIncidenceMode:
    """Tests for IncidenceMode enum."""

    def test_off_nadir_proxy(self) -> None:
        assert IncidenceMode.OFF_NADIR_PROXY.value == "off_nadir_proxy"


class TestSensorConfig:
    """Tests for SensorConfig dataclass."""

    def test_basic_creation(self) -> None:
        config = SensorConfig(sensor_fov_half_angle_deg=30.0)
        assert config.sensor_fov_half_angle_deg == 30.0
        assert config.mode == ImagingMode.OPTICAL

    def test_optical_mode(self) -> None:
        config = SensorConfig(
            sensor_fov_half_angle_deg=1.0,
            mode=ImagingMode.OPTICAL,
        )
        assert config.mode == ImagingMode.OPTICAL
        assert config.min_sun_elevation_deg == 30.0  # Default

    def test_sar_mode(self) -> None:
        config = SensorConfig(
            sensor_fov_half_angle_deg=30.0,
            mode=ImagingMode.SAR,
        )
        assert config.mode == ImagingMode.SAR

    def test_invalid_fov_zero(self) -> None:
        with pytest.raises(ValueError):
            SensorConfig(sensor_fov_half_angle_deg=0.0)

    def test_invalid_fov_negative(self) -> None:
        with pytest.raises(ValueError):
            SensorConfig(sensor_fov_half_angle_deg=-10.0)

    def test_invalid_fov_over_90(self) -> None:
        with pytest.raises(ValueError):
            SensorConfig(sensor_fov_half_angle_deg=100.0)

    def test_valid_incidence_range(self) -> None:
        config = SensorConfig(
            sensor_fov_half_angle_deg=30.0,
            incidence_angle_range_deg=(20.0, 50.0),
        )
        assert config.incidence_angle_range_deg == (20.0, 50.0)

    def test_invalid_incidence_range(self) -> None:
        with pytest.raises(ValueError):
            SensorConfig(
                sensor_fov_half_angle_deg=30.0,
                incidence_angle_range_deg=(50.0, 20.0),  # min > max
            )

    def test_with_swath_width(self) -> None:
        config = SensorConfig(
            sensor_fov_half_angle_deg=30.0,
            swath_width_km=100.0,
        )
        assert config.swath_width_km == 100.0

    def test_with_resolution(self) -> None:
        config = SensorConfig(
            sensor_fov_half_angle_deg=1.0,
            resolution_m=0.5,
        )
        assert config.resolution_m == 0.5


class TestSpacecraftConfig:
    """Tests for SpacecraftConfig dataclass."""

    def test_basic_creation(self) -> None:
        config = SpacecraftConfig(max_spacecraft_roll_deg=45.0)
        assert config.max_spacecraft_roll_deg == 45.0

    def test_default_rates(self) -> None:
        config = SpacecraftConfig(max_spacecraft_roll_deg=45.0)
        assert config.max_roll_rate_dps == 1.0
        assert config.settling_time_s == 5.0

    def test_with_custom_rates(self) -> None:
        config = SpacecraftConfig(
            max_spacecraft_roll_deg=45.0,
            max_roll_rate_dps=2.0,
            max_pitch_deg=30.0,
        )
        assert config.max_roll_rate_dps == 2.0
        assert config.max_pitch_deg == 30.0

    def test_invalid_roll_zero(self) -> None:
        with pytest.raises(ValueError):
            SpacecraftConfig(max_spacecraft_roll_deg=0.0)

    def test_invalid_roll_over_90(self) -> None:
        with pytest.raises(ValueError):
            SpacecraftConfig(max_spacecraft_roll_deg=100.0)

    def test_invalid_roll_rate(self) -> None:
        with pytest.raises(ValueError):
            SpacecraftConfig(max_spacecraft_roll_deg=45.0, max_roll_rate_dps=0.0)
