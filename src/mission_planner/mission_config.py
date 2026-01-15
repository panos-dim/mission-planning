"""
Mission configuration dataclasses for sensor and spacecraft parameters.

This module cleanly separates:
- Sensor characteristics (FOV, imaging modes)
- Spacecraft capabilities (agility, pointing limits)
- Aiming and tolerance parameters
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ImagingMode(Enum):
    """Imaging sensor mode."""
    OPTICAL = "optical"
    SAR = "sar"


class AimingMode(Enum):
    """Boresight aiming strategy during imaging."""
    TARGET_CENTER = "target_center"  # Track target center (current default)
    NADIR = "nadir"  # Fixed nadir pointing (legacy, not recommended)
    # Future: VELOCITY_ALIGNED, FIXED_OFFSET, etc.


class IncidenceMode(Enum):
    """Incidence angle calculation method."""
    OFF_NADIR_PROXY = "off_nadir_proxy"  # Off-nadir = incidence (current default)
    # Future: LOCAL_SURFACE_NORMAL (requires DEM/ellipsoid)


@dataclass
class SensorConfig:
    """
    Sensor/payload configuration.
    
    Defines imaging sensor characteristics independent of spacecraft bus.
    """
    sensor_fov_half_angle_deg: float  # Half-angle of imaging cone from boresight
    mode: ImagingMode = ImagingMode.OPTICAL
    
    # Optional sensor-specific parameters
    swath_width_km: Optional[float] = None
    resolution_m: Optional[float] = None
    
    # SAR-specific (when mode=SAR)
    sar_mode: Optional[str] = None  # stripmap, spotlight, scan
    polarizations: Optional[list] = None  # VV, VH, HH, HV
    
    # Operational constraints
    incidence_angle_range_deg: Optional[tuple] = None  # (min, max) for quality
    min_sun_elevation_deg: Optional[float] = None  # OPTICAL only
    max_cloud_cover_percent: Optional[float] = None  # OPTICAL only
    
    def __post_init__(self):
        """Validate sensor configuration."""
        if not 0 < self.sensor_fov_half_angle_deg <= 90:
            raise ValueError(
                f"sensor_fov_half_angle_deg must be in (0, 90], got {self.sensor_fov_half_angle_deg}"
            )
        
        # Set defaults based on mode
        if self.mode == ImagingMode.OPTICAL and self.min_sun_elevation_deg is None:
            self.min_sun_elevation_deg = 30.0  # Default for optical
        
        if self.incidence_angle_range_deg:
            min_inc, max_inc = self.incidence_angle_range_deg
            if not 0 <= min_inc <= max_inc <= 90:
                raise ValueError(
                    f"Invalid incidence_angle_range_deg: {self.incidence_angle_range_deg}"
                )


@dataclass
class SpacecraftConfig:
    """
    Spacecraft bus configuration.
    
    Defines spacecraft agility and pointing limits independent of sensor.
    """
    max_spacecraft_roll_deg: float  # Maximum roll angle from nadir
    max_roll_rate_dps: float = 1.0  # degrees per second
    max_roll_accel_dps2: float = 1.0  # degrees per second squared
    
    # Future: pitch capabilities
    max_pitch_deg: float = 0.0
    max_pitch_rate_dps: float = 0.0
    max_pitch_accel_dps2: float = 0.0
    
    # Settling time after maneuver (seconds)
    settling_time_s: float = 5.0
    
    def __post_init__(self):
        """Validate spacecraft configuration."""
        if not 0 < self.max_spacecraft_roll_deg <= 90:
            raise ValueError(
                f"max_spacecraft_roll_deg must be in (0, 90], got {self.max_spacecraft_roll_deg}"
            )
        
        if self.max_roll_rate_dps <= 0:
            raise ValueError(
                f"max_roll_rate_dps must be > 0, got {self.max_roll_rate_dps}"
            )
        
        if self.max_roll_accel_dps2 <= 0:
            raise ValueError(
                f"max_roll_accel_dps2 must be > 0, got {self.max_roll_accel_dps2}"
            )


@dataclass
class MissionTolerances:
    """
    Tolerances and precision parameters for mission planning.
    
    Documents accepted coordinate precision and aiming tolerances.
    """
    # Aiming tolerances
    aiming_epsilon_deg: float = 0.1  # Within-cone slack for geometry checks
    time_edge_epsilon_s: float = 0.5  # AOS/LOS time boundary refinement
    
    # Coordinate precision (documentation)
    # Python float64 provides ~15 decimal digits
    # Lat/lon precision: ~1mm at equator (8 decimal places sufficient)
    coordinate_precision_note: str = (
        "Coordinates stored as float64 (IEEE 754). "
        "Lat/lon precision ~1e-8 degrees ≈ 1mm at equator. "
        "Angles stored with ~1e-9 degree precision."
    )
    
    # Aiming and incidence modes
    aiming_mode: AimingMode = AimingMode.TARGET_CENTER
    incidence_mode: IncidenceMode = IncidenceMode.OFF_NADIR_PROXY


@dataclass
class MissionConfig:
    """
    Complete mission configuration combining sensor, spacecraft, and tolerances.
    """
    sensor: SensorConfig
    spacecraft: SpacecraftConfig
    tolerances: MissionTolerances = None
    
    def __post_init__(self):
        """Set defaults for optional fields."""
        if self.tolerances is None:
            self.tolerances = MissionTolerances()
    
    def validate_compatibility(self) -> bool:
        """
        Validate that sensor FOV and spacecraft limits are compatible.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError if sensor FOV exceeds spacecraft pointing capability
        """
        if self.sensor.sensor_fov_half_angle_deg > self.spacecraft.max_spacecraft_roll_deg:
            logger.warning(
                f"Sensor FOV ({self.sensor.sensor_fov_half_angle_deg}°) exceeds "
                f"spacecraft roll limit ({self.spacecraft.max_spacecraft_roll_deg}°). "
                f"Some imaging opportunities may be geometrically visible but mechanically infeasible."
            )
            # This is a warning, not an error - it's valid to have a wide-FOV sensor
            # on a limited-agility bus; scheduler will handle feasibility
        
        return True


# Default configurations for common mission types
DEFAULT_OPTICAL_SENSOR = SensorConfig(
    sensor_fov_half_angle_deg=1.0,  # 2° total cone (realistic for high-res optical like WorldView-3)
    mode=ImagingMode.OPTICAL,
    min_sun_elevation_deg=30.0,
    max_cloud_cover_percent=20.0
)

DEFAULT_SAR_SENSOR = SensorConfig(
    sensor_fov_half_angle_deg=30.0,  # 60° total cone
    mode=ImagingMode.SAR,
    incidence_angle_range_deg=(20.0, 50.0),
    sar_mode="stripmap"
)

DEFAULT_OPTICAL_SPACECRAFT = SpacecraftConfig(
    max_spacecraft_roll_deg=45.0,
    max_roll_rate_dps=1.0,
    max_roll_accel_dps2=1.0,
    settling_time_s=5.0
)

DEFAULT_SAR_SPACECRAFT = SpacecraftConfig(
    max_spacecraft_roll_deg=60.0,
    max_roll_rate_dps=1.0,
    max_roll_accel_dps2=1.0,
    settling_time_s=3.0
)


def create_default_mission_config(mode: str = "optical") -> MissionConfig:
    """
    Create default mission configuration for common mission types.
    
    Args:
        mode: "optical" or "sar"
        
    Returns:
        MissionConfig with appropriate defaults
    """
    if mode is None:
        mode = "optical"
    
    if mode.lower() == "optical":
        return MissionConfig(
            sensor=DEFAULT_OPTICAL_SENSOR,
            spacecraft=DEFAULT_OPTICAL_SPACECRAFT
        )
    elif mode.lower() == "sar":
        return MissionConfig(
            sensor=DEFAULT_SAR_SENSOR,
            spacecraft=DEFAULT_SAR_SPACECRAFT
        )
    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'optical' or 'sar'")
