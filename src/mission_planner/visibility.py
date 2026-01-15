"""
Satellite visibility calculations and pass prediction.

This module provides functionality to compute satellite visibility windows
over ground targets with configurable elevation masks.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from orbit_predictor.locations import Location  # type: ignore[import-untyped]
from orbit_predictor.predictors import TLEPredictor  # type: ignore[import-untyped]

from .orbit import SatelliteOrbit
from .sunlight import is_target_illuminated
from .targets import GroundTarget

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS - Extracted from magic numbers for clarity and maintainability
# =============================================================================

# Earth parameters
EARTH_RADIUS_KM = 6371.0

# Visibility calculation constants
VISIBILITY_MARGIN_KM = 800.0  # Conservative margin for visibility prefilter
PASS_GAP_THRESHOLD_SECONDS = 300  # 5 minutes - gap threshold for grouping passes
ORBITAL_SKIP_DISTANCE_KM = (
    10000.0  # Distance threshold for orbital skip-ahead optimization
)
MAX_ORBITAL_SKIP_SECONDS = 1200.0  # Maximum skip ahead time (20 minutes)

# Cache configuration
SATELLITE_POSITION_CACHE_SIZE = 10000  # LRU cache size for satellite positions


@dataclass
class PassGeometry:
    """Geometry data at a specific moment during a pass."""

    elevation_deg: float
    azimuth_deg: float
    range_km: float
    incidence_angle_deg: float  # Off-nadir / look angle
    ground_sample_distance_m: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "elevation_deg": round(self.elevation_deg, 2),
            "azimuth_deg": round(self.azimuth_deg, 2),
            "range_km": round(self.range_km, 2),
            "incidence_angle_deg": round(self.incidence_angle_deg, 2),
        }
        if self.ground_sample_distance_m is not None:
            result["ground_sample_distance_m"] = round(self.ground_sample_distance_m, 2)
        return result


@dataclass
class PassLighting:
    """Lighting conditions during a pass."""

    target_sunlit: bool
    satellite_sunlit: bool
    sun_elevation_deg: float
    solar_phase_angle_deg: Optional[float] = None
    local_solar_time: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "target_sunlit": self.target_sunlit,
            "satellite_sunlit": self.satellite_sunlit,
            "sun_elevation_deg": round(self.sun_elevation_deg, 2),
        }
        if self.solar_phase_angle_deg is not None:
            result["solar_phase_angle_deg"] = round(self.solar_phase_angle_deg, 2)
        if self.local_solar_time is not None:
            result["local_solar_time"] = self.local_solar_time
        return result


@dataclass
class PassQuality:
    """Quality metrics for imaging passes."""

    quality_score: float  # 0-100
    imaging_feasible: bool
    feasibility_reason: Optional[str] = None
    cloud_probability: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "quality_score": round(self.quality_score, 1),
            "imaging_feasible": self.imaging_feasible,
        }
        if self.feasibility_reason:
            result["feasibility_reason"] = self.feasibility_reason
        if self.cloud_probability is not None:
            result["cloud_probability"] = round(self.cloud_probability, 1)
        return result


@dataclass
class PassManeuver:
    """Maneuver requirements for a pass."""

    roll_angle_deg: float  # Signed roll angle
    pitch_angle_deg: float  # Signed pitch angle
    slew_angle_deg: float  # Total slew from nadir
    slew_time_s: Optional[float] = None
    from_previous_slew_deg: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "roll_angle_deg": round(self.roll_angle_deg, 2),
            "pitch_angle_deg": round(self.pitch_angle_deg, 2),
            "slew_angle_deg": round(self.slew_angle_deg, 2),
        }
        if self.slew_time_s is not None:
            result["slew_time_s"] = round(self.slew_time_s, 2)
        if self.from_previous_slew_deg is not None:
            result["from_previous_slew_deg"] = round(self.from_previous_slew_deg, 2)
        return result


@dataclass
class PassDetails:
    """STK-like comprehensive details about a satellite pass over a target."""

    # Core identification
    target_name: str
    satellite_name: str
    start_time: datetime
    max_elevation_time: datetime
    end_time: datetime
    max_elevation: float  # degrees
    start_azimuth: float  # degrees
    max_elevation_azimuth: float  # degrees
    end_azimuth: float  # degrees

    # Constellation support
    satellite_id: str = ""
    pass_index: int = 0

    # Enhanced STK-like data
    geometry_aos: Optional[PassGeometry] = None  # Geometry at AOS
    geometry_tca: Optional[PassGeometry] = None  # Geometry at TCA (max elevation)
    geometry_los: Optional[PassGeometry] = None  # Geometry at LOS
    lighting: Optional[PassLighting] = None
    quality: Optional[PassQuality] = None
    maneuver: Optional[PassManeuver] = None

    # Legacy fields for backward compatibility
    incidence_angle_deg: Optional[float] = None
    mode: Optional[str] = None

    # SAR-specific data (populated for SAR missions)
    sar_data: Optional[Any] = None  # SAROpportunityData when SAR mission

    # Internal storage for imaging pass processing (used by find_imaging_passes)
    _imaging_opportunities: Optional[List[Any]] = None
    _imaging_window: Optional[List[Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert pass details to dictionary with STK-like structure."""
        duration_s = (self.end_time - self.start_time).total_seconds()

        result = {
            # Identity
            "target": self.target_name,  # Frontend expects 'target' not 'target_name'
            "target_name": self.target_name,
            "satellite_name": self.satellite_name,
            "satellite_id": self.satellite_id or f"sat_{self.satellite_name}",
            "pass_index": self.pass_index,
            # Timing
            "start_time": self.start_time.isoformat(),
            "max_elevation_time": self.max_elevation_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_s": round(duration_s, 1),
            # Pass characteristics
            "max_elevation": round(self.max_elevation, 2),
            "pass_type": self._determine_pass_type(),
            # Azimuths (backward compatibility)
            "start_azimuth": round(self.start_azimuth, 2),
            "max_elevation_azimuth": round(self.max_elevation_azimuth, 2),
            "end_azimuth": round(self.end_azimuth, 2),
        }

        # Add geometry at key moments
        if self.geometry_aos:
            result["geometry_aos"] = self.geometry_aos.to_dict()
        if self.geometry_tca:
            result["geometry_tca"] = self.geometry_tca.to_dict()
        if self.geometry_los:
            result["geometry_los"] = self.geometry_los.to_dict()

        # Add lighting conditions
        if self.lighting:
            result["lighting"] = self.lighting.to_dict()

        # Add quality metrics
        if self.quality:
            result["quality"] = self.quality.to_dict()

        # Add maneuver requirements
        if self.maneuver:
            result["maneuver"] = self.maneuver.to_dict()

        # Legacy fields
        if self.incidence_angle_deg is not None:
            result["incidence_angle_deg"] = round(self.incidence_angle_deg, 2)
        if self.mode is not None:
            result["mode"] = self.mode

        # SAR-specific data
        if self.sar_data is not None:
            if hasattr(self.sar_data, "to_dict"):
                result["sar"] = self.sar_data.to_dict()
            # Also add key SAR fields at top level for easy access
            result["look_side"] = getattr(self.sar_data, "look_side", None)
            if hasattr(result["look_side"], "value"):
                result["look_side"] = result["look_side"].value
            result["pass_direction"] = getattr(self.sar_data, "pass_direction", None)
            if hasattr(result["pass_direction"], "value"):
                result["pass_direction"] = result["pass_direction"].value
            result["incidence_center_deg"] = getattr(
                self.sar_data, "incidence_center_deg", None
            )
            result["swath_width_km"] = getattr(self.sar_data, "swath_width_km", None)
            result["imaging_mode"] = getattr(self.sar_data, "imaging_mode", None)
            if hasattr(result["imaging_mode"], "value"):
                result["imaging_mode"] = result["imaging_mode"].value

        return result

    def _determine_pass_type(self) -> str:
        """Determine if pass is ascending or descending based on azimuth."""
        # Ascending: satellite moving roughly north (azimuth near 0/360)
        # Descending: satellite moving roughly south (azimuth near 180)
        mid_azimuth = self.max_elevation_azimuth
        if 45 < mid_azimuth < 135 or 225 < mid_azimuth < 315:
            return "ascending" if mid_azimuth < 180 else "descending"
        return "ascending" if self.start_azimuth < 180 else "descending"

    def __str__(self) -> str:
        """String representation of the pass."""
        return (
            f"Pass over {self.target_name}: "
            f"{self.start_time.strftime('%Y-%m-%d %H:%M')} - "
            f"{self.end_time.strftime('%H:%M')} UTC, "
            f"Max Elev: {self.max_elevation:.1f}°"
        )

    @classmethod
    def from_window(
        cls,
        target_name: str,
        satellite_name: str,
        start_time: datetime,
        end_time: datetime,
        max_elevation: float,
        max_elevation_time: datetime,
        start_azimuth: float,
        max_elevation_azimuth: float,
        end_azimuth: float,
        incidence_angle_deg: Optional[float] = None,
        mode: Optional[str] = None,
    ) -> "PassDetails":
        """
        Factory method to create PassDetails from visibility window data.

        This consolidates the common pattern of creating PassDetails objects
        from various sources (adaptive algorithm, fixed-step, imaging processing).

        Args:
            target_name: Name of the ground target
            satellite_name: Name of the satellite
            start_time: Pass start time (AOS)
            end_time: Pass end time (LOS)
            max_elevation: Maximum elevation angle in degrees
            max_elevation_time: Time of maximum elevation
            start_azimuth: Azimuth at pass start
            max_elevation_azimuth: Azimuth at maximum elevation
            end_azimuth: Azimuth at pass end
            incidence_angle_deg: Optional signed incidence angle for imaging
            mode: Optional imaging mode (OPTICAL, SAR, IMAGING, COMMUNICATION)

        Returns:
            PassDetails instance
        """
        return cls(
            target_name=target_name,
            satellite_name=satellite_name,
            start_time=start_time,
            max_elevation_time=max_elevation_time,
            end_time=end_time,
            max_elevation=max_elevation,
            start_azimuth=start_azimuth,
            max_elevation_azimuth=max_elevation_azimuth,
            end_azimuth=end_azimuth,
            incidence_angle_deg=incidence_angle_deg,
            mode=mode,
        )


class VisibilityCalculator:
    """
    Calculates satellite visibility windows over ground targets.

    This class provides methods to compute when satellites are visible
    from ground locations, taking into account elevation masks and
    other constraints.

    Supports both fixed-step and adaptive time-stepping algorithms.
    """

    # Adaptive time-stepping configuration constants
    # Note: These can be tuned for accuracy vs speed tradeoff
    # Ultra-high accuracy preset (validated to match STK 100%):
    ADAPTIVE_INITIAL_STEP_SECONDS = (
        10.0  # Start with 10s steps (matches STK resolution)
    )
    ADAPTIVE_MIN_STEP_SECONDS = 1  # Finer minimum step (catch brief passes)
    ADAPTIVE_MAX_STEP_SECONDS = (
        30.0  # Conservative max step (ensure brief opportunities not missed)
    )
    ADAPTIVE_REFINEMENT_TOLERANCE = 0.5  # Tighter accuracy ±0.5 second
    ADAPTIVE_CHANGE_THRESHOLD = (
        0.05  # Very sensitive to changes (detect all transitions)
    )
    ADAPTIVE_STEP_SHRINK_FACTOR = 0.3  # Shrink aggressively near transitions
    ADAPTIVE_STEP_GROW_FACTOR = 1.2  # Grow conservatively (stay cautious)
    ADAPTIVE_MAX_REFINEMENT_ITERS = 30  # More iterations for accuracy

    # Speed-optimized preset (use only after validation):
    # ADAPTIVE_INITIAL_STEP_SECONDS = 60.0
    # ADAPTIVE_MIN_STEP_SECONDS = 0.5
    # ADAPTIVE_MAX_STEP_SECONDS = 120.0
    # ADAPTIVE_REFINEMENT_TOLERANCE = 1.0
    # ADAPTIVE_CHANGE_THRESHOLD = 0.1
    # ADAPTIVE_STEP_SHRINK_FACTOR = 0.5
    # ADAPTIVE_STEP_GROW_FACTOR = 1.5
    # ADAPTIVE_MAX_REFINEMENT_ITERS = 20

    def __init__(self, satellite: "SatelliteOrbit", use_adaptive: bool = False) -> None:
        """
        Initialize visibility calculator with satellite orbit predictor.

        Args:
            satellite: SatelliteOrbit instance with predictor
            use_adaptive: Enable adaptive time-stepping (default: False for backward compatibility)
        """
        self.satellite = satellite
        self.predictor = satellite.predictor
        self.use_adaptive = use_adaptive
        self._all_imaging_opportunities: List[Any] = (
            []
        )  # Store all imaging opportunities for visualization
        self._ground_ecef_cache: Dict[
            Tuple[float, float, float], Tuple[float, float, float]
        ] = {}  # Cache ECEF coordinates per target for performance
        self._location_cache: Dict[Tuple[float, float, float], Location] = (
            {}
        )  # Cache Location objects per target

        # Create a bound LRU-cached method for satellite positions
        # This prevents unbounded memory growth during long mission analyses
        self._get_satellite_position = lru_cache(maxsize=SATELLITE_POSITION_CACHE_SIZE)(
            self._get_satellite_position_impl
        )

        # OPTIMIZATION: Calculate adaptive step sizes based on orbital period
        if use_adaptive:
            orbital_period_seconds = satellite.get_orbital_period().total_seconds()

            # For coarse scan: use larger steps scaled to orbital period
            # Start with 0.03 × period (~160s for LEO) - balances speed and accuracy
            # Reduced from 0.05 to avoid missing brief passes
            self.ADAPTIVE_INITIAL_STEP_SECONDS = min(
                orbital_period_seconds * 0.03, 30.0
            )

            # Max step: 0.06 × period (~320s for LEO) - allows fast scanning of empty regions
            # Reduced from 0.1 to ensure brief passes (>10s) are not skipped
            self.ADAPTIVE_MAX_STEP_SECONDS = min(orbital_period_seconds * 0.06, 60.0)

            # Keep conservative refinement settings
            self.ADAPTIVE_MIN_STEP_SECONDS = 1
            self.ADAPTIVE_REFINEMENT_TOLERANCE = 0.5
            self.ADAPTIVE_CHANGE_THRESHOLD = 0.05
            self.ADAPTIVE_STEP_SHRINK_FACTOR = 0.3
            self.ADAPTIVE_STEP_GROW_FACTOR = 1.2
            self.ADAPTIVE_MAX_REFINEMENT_ITERS = 30

            logger.info(
                f"Adaptive steps: initial={self.ADAPTIVE_INITIAL_STEP_SECONDS:.1f}s, "
                f"max={self.ADAPTIVE_MAX_STEP_SECONDS:.1f}s (period={orbital_period_seconds:.0f}s)"
            )

        method = "adaptive" if use_adaptive else "fixed-step"
        logger.info(
            f"Initialized VisibilityCalculator for {satellite.satellite_name} (method: {method})"
        )

    def _get_location(self, target: GroundTarget) -> Location:
        """
        Get cached Location object for target.

        Args:
            target: Ground target

        Returns:
            Location object
        """
        key = (target.latitude, target.longitude, target.altitude)
        if key not in self._location_cache:
            self._location_cache[key] = Location(
                "target",
                target.latitude,
                target.longitude,
                target.altitude / 1000.0,  # Convert to km
            )
        return self._location_cache[key]

    def _get_satellite_position_impl(self, timestamp_rounded: datetime) -> Any:
        """
        Get satellite position for timestamp (implementation for LRU cache).

        Note: This method is wrapped by LRU cache in __init__.
        The timestamp should be pre-rounded for consistent cache hits.

        Args:
            timestamp_rounded: UTC datetime (rounded to nearest second)

        Returns:
            Satellite position object
        """
        return self.predictor.get_position(timestamp_rounded)

    def calculate_elevation_azimuth(
        self, target: GroundTarget, timestamp: datetime
    ) -> Tuple[float, float]:
        """
        Calculate elevation and azimuth angles from target to satellite.

        Args:
            target: Ground target
            timestamp: UTC datetime

        Returns:
            Tuple of (elevation_degrees, azimuth_degrees)
        """
        try:
            # Get cached location object
            location = self._get_location(target)

            # Get cached satellite position (round to nearest second for cache hits)
            sat_position = self._get_satellite_position(
                timestamp.replace(microsecond=0)
            )

            # Calculate elevation and azimuth
            elevation = self._calculate_elevation(location, sat_position, timestamp)
            azimuth = self._calculate_azimuth(location, sat_position, timestamp)

            return elevation, azimuth

        except Exception as e:
            logger.error(f"Error calculating elevation/azimuth: {e}")
            return 0.0, 0.0

    def _get_ground_ecef(self, location: Location) -> Tuple[float, float, float]:
        """
        Get cached ECEF coordinates for ground location.

        Args:
            location: Ground location

        Returns:
            Tuple of (x, y, z) in km
        """
        # Create cache key from location coordinates
        key = (location.latitude_deg, location.longitude_deg, location.elevation_m)

        if key not in self._ground_ecef_cache:
            # Calculate and cache ECEF coordinates
            earth_radius = EARTH_RADIUS_KM
            lat_rad = math.radians(location.latitude_deg)
            lon_rad = math.radians(location.longitude_deg)
            ground_alt_km = location.elevation_m / 1000.0

            x = (earth_radius + ground_alt_km) * math.cos(lat_rad) * math.cos(lon_rad)
            y = (earth_radius + ground_alt_km) * math.cos(lat_rad) * math.sin(lon_rad)
            z = (earth_radius + ground_alt_km) * math.sin(lat_rad)

            self._ground_ecef_cache[key] = (x, y, z)

        return self._ground_ecef_cache[key]

    def _calculate_elevation(
        self, location: Location, sat_position: Any, timestamp: datetime
    ) -> float:
        """
        Calculate elevation angle from ground location to satellite.

        Args:
            location: Ground location
            sat_position: Satellite position
            timestamp: UTC datetime

        Returns:
            Elevation angle in degrees
        """
        # Earth radius in km
        earth_radius = EARTH_RADIUS_KM

        # Extract satellite position from position_llh
        sat_lat, sat_lon, sat_alt_km = sat_position.position_llh

        # Calculate satellite ECEF coordinates
        sat_lat_rad = math.radians(sat_lat)
        sat_lon_rad = math.radians(sat_lon)
        sat_x = (
            (earth_radius + sat_alt_km) * math.cos(sat_lat_rad) * math.cos(sat_lon_rad)
        )
        sat_y = (
            (earth_radius + sat_alt_km) * math.cos(sat_lat_rad) * math.sin(sat_lon_rad)
        )
        sat_z = (earth_radius + sat_alt_km) * math.sin(sat_lat_rad)

        # Get cached ground location ECEF coordinates
        ground_x, ground_y, ground_z = self._get_ground_ecef(location)

        # Vector from ground to satellite
        dx = sat_x - ground_x
        dy = sat_y - ground_y
        dz = sat_z - ground_z

        # Range to satellite
        range_km = math.sqrt(dx * dx + dy * dy + dz * dz)

        # Calculate elevation angle correctly using local horizon
        if range_km > 0:
            # Local up vector (from Earth center to ground station)
            up_x = ground_x / earth_radius
            up_y = ground_y / earth_radius
            up_z = ground_z / earth_radius

            # Dot product of satellite vector with local up vector
            dot_product = dx * up_x + dy * up_y + dz * up_z

            # Elevation angle relative to local horizon
            elevation_rad = math.asin(dot_product / range_km)
            elevation_deg = math.degrees(elevation_rad)
            return max(elevation_deg, -90.0)  # Clamp to valid range

        return 0.0

    def _calculate_azimuth(
        self, location: Location, sat_position: Any, timestamp: datetime
    ) -> float:
        """
        Calculate azimuth angle from ground location to satellite.

        Args:
            location: Ground location
            sat_position: Satellite position
            timestamp: UTC datetime

        Returns:
            Azimuth angle in degrees (0° = North, 90° = East)
        """
        # Extract satellite position from position_llh
        sat_lat, sat_lon, sat_alt_km = sat_position.position_llh

        # Convert to radians
        lat_rad = math.radians(location.latitude_deg)
        lon_rad = math.radians(location.longitude_deg)
        sat_lat_rad = math.radians(sat_lat)
        sat_lon_rad = math.radians(sat_lon)

        # Calculate azimuth using spherical trigonometry
        dlon = sat_lon_rad - lon_rad

        y = math.sin(dlon) * math.cos(sat_lat_rad)
        x = math.cos(lat_rad) * math.sin(sat_lat_rad) - math.sin(lat_rad) * math.cos(
            sat_lat_rad
        ) * math.cos(dlon)

        azimuth_rad = math.atan2(y, x)
        azimuth_deg = math.degrees(azimuth_rad)

        # Convert to 0-360 range
        azimuth_deg = (azimuth_deg + 360) % 360

        return azimuth_deg

    def _is_target_visible(
        self, target: GroundTarget, timestamp: datetime, elevation: float
    ) -> bool:
        """
        Check if target is visible based on mission type constraints.

        Args:
            target: Ground target with mission type
            timestamp: UTC datetime
            elevation: Elevation angle in degrees

        Returns:
            True if target is visible for the specified mission type
        """
        # Communication constraint: elevation mask
        comm_visible = elevation >= target.elevation_mask

        if target.mission_type == "communication":
            return comm_visible

        # Imaging constraint: pointing cone (needs satellite position)
        if target.mission_type == "imaging":
            # First check if target is above horizon (elevation > 0)
            if elevation <= 0:
                return False

            # Get satellite position for imaging visibility check
            sat_lat, sat_lon, sat_alt = self.satellite.get_position(timestamp)

            # Get spacecraft roll limit for visibility (NOT sensor FOV!)
            # For visibility analysis, we need max spacecraft roll, not the narrow sensor FOV
            sensor_fov = getattr(target, "max_spacecraft_roll", None) or 45.0

            imaging_visible = self._is_within_pointing_cone(
                target,
                timestamp,
                sat_lat,
                sat_lon,
                sat_alt,
                sensor_fov_half_angle_deg=sensor_fov,
            )

            return imaging_visible

        # Default to communication
        return comm_visible

    def _is_within_pointing_cone(
        self,
        target: GroundTarget,
        timestamp: datetime,
        sat_lat: float,
        sat_lon: float,
        sat_alt: float,
        sensor_fov_half_angle_deg: Optional[float] = None,
        aiming_epsilon_deg: float = 0.1,
    ) -> bool:
        """
        Check if target is within satellite's sensor FOV cone (for imaging missions).

        AIMING MODEL: Boresight tracks target center during imaging acquisition.
        The sensor FOV cone is centered on the boresight direction (satellite → target center),
        not fixed at nadir.

        For imaging missions, verifies:
        1. Target is above satellite's local horizon
        2. Target center is within sensor FOV cone from boresight
        3. For OPTICAL missions: target is illuminated by sun (sun elevation > 0°)

        Args:
            target: Ground target (assumed point target at lat/lon center)
            timestamp: UTC datetime
            sat_lat, sat_lon, sat_alt: Satellite position (degrees, km)
            sensor_fov_half_angle_deg: Sensor FOV half-angle (defaults to target.max_spacecraft_roll)
            aiming_epsilon_deg: Tolerance for within-cone checks (default 0.1°)

        Returns:
            True if target is within sensor FOV and visible for imaging
        """
        # Note: Horizon check is done in _is_target_visible using elevation angle
        # (more accurate than geometric approximation)

        # Calculate look angle (off-nadir angle from satellite nadir to target)
        # NOTE: With target-center aiming, the boresight points at the target,
        # so for a point target, the look angle IS the boresight angle from nadir.
        look_angle = self._calculate_look_angle(
            sat_lat, sat_lon, sat_alt, target.latitude, target.longitude
        )

        # Get spacecraft roll limit for visibility
        # Use max spacecraft agility (default 45°), NOT the narrow sensor FOV
        if sensor_fov_half_angle_deg is None:
            sensor_fov_half_angle_deg = (
                getattr(target, "max_spacecraft_roll", None) or 45.0
            )

        # Check if target is within sensor FOV cone (with tolerance)
        # For target-center aiming on a point target, this is always satisfied
        # (the boresight aims at the target center by definition).
        # The constraint is whether we can physically point the boresight this far off-nadir.
        within_cone = look_angle <= (sensor_fov_half_angle_deg + aiming_epsilon_deg)

        if not within_cone:
            return False

        # For OPTICAL imaging, require target to be illuminated by sunlight
        # SAR imaging works day and night, so no sunlight constraint
        imaging_type = getattr(target, "imaging_type", "optical")
        if imaging_type == "optical":
            illuminated = is_target_illuminated(
                target.latitude, target.longitude, timestamp, min_sun_elevation=0.0
            )
            if not illuminated:
                return False

        return True

    def _calculate_look_angle(
        self,
        sat_lat: float,
        sat_lon: float,
        sat_alt: float,
        target_lat: float,
        target_lon: float,
    ) -> float:
        """
        Calculate the look angle from satellite to target.

        The look angle is the angle between the nadir vector (straight down from satellite)
        and the vector from satellite to target.

        Args:
            sat_lat, sat_lon, sat_alt: Satellite position (degrees, km)
            target_lat, target_lon: Target position (degrees)

        Returns:
            Look angle in degrees
        """
        # Earth radius
        earth_radius = EARTH_RADIUS_KM

        # Convert to radians
        sat_lat_rad = math.radians(sat_lat)
        sat_lon_rad = math.radians(sat_lon)
        target_lat_rad = math.radians(target_lat)
        target_lon_rad = math.radians(target_lon)

        # Convert to Cartesian coordinates
        # Satellite position
        sat_r = earth_radius + sat_alt
        sat_x = sat_r * math.cos(sat_lat_rad) * math.cos(sat_lon_rad)
        sat_y = sat_r * math.cos(sat_lat_rad) * math.sin(sat_lon_rad)
        sat_z = sat_r * math.sin(sat_lat_rad)

        # Target position on Earth surface
        target_x = earth_radius * math.cos(target_lat_rad) * math.cos(target_lon_rad)
        target_y = earth_radius * math.cos(target_lat_rad) * math.sin(target_lon_rad)
        target_z = earth_radius * math.sin(target_lat_rad)

        # Nadir vector: points from satellite toward Earth center
        # This is simply the negative of the satellite's position vector from Earth center
        nadir_vec = np.array([-sat_x, -sat_y, -sat_z])
        nadir_vec = nadir_vec / np.linalg.norm(nadir_vec)

        # Vector from satellite to target
        target_vec = np.array([target_x - sat_x, target_y - sat_y, target_z - sat_z])
        target_vec = target_vec / np.linalg.norm(target_vec)

        # Calculate angle between vectors (off-nadir angle)
        cos_angle = np.dot(nadir_vec, target_vec)
        # Clamp to avoid numerical errors
        cos_angle = max(-1.0, min(1.0, cos_angle))
        look_angle_rad = math.acos(cos_angle)
        off_nadir_deg = math.degrees(look_angle_rad)

        # Return off-nadir angle (used for 45° cone filtering)
        return off_nadir_deg

    def _calculate_signed_roll_angle(
        self,
        sat_lat: float,
        sat_lon: float,
        sat_alt: float,
        target_lat: float,
        target_lon: float,
        timestamp: datetime,
    ) -> float:
        """
        Calculate SIGNED roll angle from satellite to target using aerospace convention.

        AEROSPACE CONVENTION: When pilot looks forward along velocity vector:
        - Positive roll = bank/roll to the RIGHT (right wing down)
        - Negative roll = bank/roll to the LEFT (left wing down)

        For satellite pointing:
        - Target on LEFT of ground track → satellite rolls RIGHT (positive angle)
        - Target on RIGHT of ground track → satellite rolls LEFT (negative angle)

        This is critical for maneuver delta calculations: going from -20° to +20° requires 40° slew!

        Args:
            sat_lat, sat_lon, sat_alt: Satellite position (degrees, km)
            target_lat, target_lon: Target position (degrees)
            timestamp: Time for velocity calculation

        Returns:
            Signed roll angle in degrees (positive = target on left → roll right, negative = target on right → roll left)
        """
        # First get the magnitude (unsigned look angle)
        roll_magnitude = self._calculate_look_angle(
            sat_lat, sat_lon, sat_alt, target_lat, target_lon
        )

        # Get satellite velocity vector (approximate using position 1 second later)
        try:
            sat_pos_future = self.satellite.get_position(
                timestamp + timedelta(seconds=1)
            )
            sat_lat_future, sat_lon_future, _ = sat_pos_future
        except Exception:
            # Fallback: assume north-south velocity for polar orbit
            sat_lat_future = sat_lat + 0.01
            sat_lon_future = sat_lon

        # Velocity vector components (in degrees/second)
        vel_lat = sat_lat_future - sat_lat
        vel_lon = sat_lon_future - sat_lon

        # Normalize velocity vector
        vel_mag = math.sqrt(vel_lat**2 + vel_lon**2)
        if vel_mag > 0:
            vel_lat_norm = vel_lat / vel_mag
            vel_lon_norm = vel_lon / vel_mag
        else:
            # Fallback: assume northward for polar orbit
            vel_lat_norm = 1.0
            vel_lon_norm = 0.0

        # Vector from satellite to target (in degrees)
        target_vec_lat = target_lat - sat_lat
        target_vec_lon = target_lon - sat_lon

        # Determine "right side" of ground track using cross product
        # AEROSPACE CONVENTION: When looking along velocity vector
        # - Target on LEFT → roll RIGHT → POSITIVE angle
        # - Target on RIGHT → roll LEFT → NEGATIVE angle
        #
        # Use 2D cross product to determine which side of velocity vector the target is on:
        # cross_track = vel × target_vec (in 2D: vel_x * target_y - vel_y * target_x)
        #
        # Based on testing:
        # Positive cross_track = target is to the LEFT of velocity vector (west)
        # Negative cross_track = target is to the RIGHT of velocity vector (east)
        #
        # This works correctly for BOTH ascending and descending passes
        cross_track = target_vec_lon * vel_lat_norm - target_vec_lat * vel_lon_norm

        # Cross-track sign determines left/right of ground track

        # Apply AEROSPACE ROLL CONVENTION
        # FLIP ALL SIGNS - USER CONFIRMED BOTH PASSES WERE BACKWARDS
        #
        # FINAL MAPPING:
        # Positive cross_track → NEGATIVE roll angle
        # Negative cross_track → POSITIVE roll angle
        if cross_track >= 0:
            signed_roll = -roll_magnitude  # NEGATIVE angle
            side = "RIGHT"
        else:
            signed_roll = roll_magnitude  # POSITIVE angle
            side = "LEFT"

        return signed_roll

    def _calculate_pitch_angle(
        self,
        satellite_position: Tuple[float, float, float],
        target_position: Tuple[float, float],
        time_offset_seconds: float,
        max_pitch_deg: float = 30.0,
    ) -> float:
        """
        Calculate dynamic pitch angle based on satellite geometry.

        Unlike roll (which is calculated from incidence angle), pitch is determined by
        the along-track position of the target relative to the satellite's nadir point.

        Physics-based approach:
        - Satellite moves along its orbital track at ~7.5 km/s
        - Time offset determines along-track distance from nadir point
        - Pitch angle calculated from geometry (altitude and along-track distance)
        - Respects spacecraft pitch constraint

        Args:
            satellite_position: Satellite (lat, lon, alt_km) at imaging time
            target_position: Target (lat, lon) in degrees
            time_offset_seconds: Time before/after max elevation
                               negative = early (backward looking)
                               positive = late (forward looking)
            max_pitch_deg: Maximum spacecraft pitch capability (default: 30°)

        Returns:
            pitch_angle: SIGNED degrees
                        negative = backward looking (early in pass)
                        zero = overhead (at max elevation)
                        positive = forward looking (late in pass)
        """
        # At max elevation (time_offset=0), pitch is always zero
        if abs(time_offset_seconds) < 0.1:
            return 0.0

        sat_lat, sat_lon, sat_alt = satellite_position
        target_lat, target_lon = target_position

        # Calculate along-track distance based on orbital velocity and time offset
        # Approximate orbital velocity: v = sqrt(GM/r)
        earth_radius_km = 6371.0
        GM = 3.986004418e5  # km³/s²
        orbital_radius_km = earth_radius_km + sat_alt
        orbital_velocity_km_s = math.sqrt(GM / orbital_radius_km)  # ~7.5 km/s at 600km

        # Along-track distance the satellite travels in time_offset
        along_track_distance_km = orbital_velocity_km_s * abs(time_offset_seconds)

        # Calculate pitch angle from geometry
        # tan(pitch) = along_track_distance / altitude
        pitch_rad = math.atan2(along_track_distance_km, sat_alt)
        pitch_deg = math.degrees(pitch_rad)

        # Apply sign based on time offset
        # Negative time offset (early) → backward looking → negative pitch
        # Positive time offset (late) → forward looking → positive pitch
        if time_offset_seconds < 0:
            pitch_deg = -pitch_deg

        # Clamp to spacecraft capability
        pitch_deg = max(-max_pitch_deg, min(max_pitch_deg, pitch_deg))

        logger.debug(
            f"Pitch calculation: time_offset={time_offset_seconds}s, "
            f"along_track={along_track_distance_km:.1f}km, "
            f"altitude={sat_alt:.1f}km, "
            f"pitch={pitch_deg:.2f}°"
        )

        return pitch_deg

    def _is_target_above_horizon(
        self,
        sat_lat: float,
        sat_lon: float,
        sat_alt: float,
        target_lat: float,
        target_lon: float,
    ) -> bool:
        """
        Check if target is above the horizon from satellite's perspective.

        Args:
            sat_lat, sat_lon, sat_alt: Satellite position (degrees, km)
            target_lat, target_lon: Target position (degrees)

        Returns:
            True if target is visible from satellite (above horizon)
        """
        # Earth radius
        earth_radius = EARTH_RADIUS_KM

        # Convert to radians
        sat_lat_rad = math.radians(sat_lat)
        sat_lon_rad = math.radians(sat_lon)
        target_lat_rad = math.radians(target_lat)
        target_lon_rad = math.radians(target_lon)

        # Convert to Cartesian coordinates
        # Satellite position
        sat_r = earth_radius + sat_alt
        sat_x = sat_r * math.cos(sat_lat_rad) * math.cos(sat_lon_rad)
        sat_y = sat_r * math.cos(sat_lat_rad) * math.sin(sat_lon_rad)
        sat_z = sat_r * math.sin(sat_lat_rad)
        sat_pos = np.array([sat_x, sat_y, sat_z])

        # Target position on Earth surface
        target_x = earth_radius * math.cos(target_lat_rad) * math.cos(target_lon_rad)
        target_y = earth_radius * math.cos(target_lat_rad) * math.sin(target_lon_rad)
        target_z = earth_radius * math.sin(target_lat_rad)
        target_pos = np.array([target_x, target_y, target_z])

        # Vector from Earth center to satellite
        sat_vec = sat_pos / np.linalg.norm(sat_pos)

        # Vector from satellite to target
        target_vec = target_pos - sat_pos
        target_vec = target_vec / np.linalg.norm(target_vec)

        # For target to be above horizon, angle between satellite radial vector
        # and target vector must be > 90 degrees (cos < 0)
        # But we need to account for Earth's curvature

        # Calculate the horizon angle
        horizon_angle_rad = math.acos(earth_radius / sat_r)

        # Calculate angle between satellite position vector and target vector
        angle_to_target = math.acos(np.dot(sat_vec, target_vec))

        # Target is above horizon if angle is less than (90° + horizon angle)
        return angle_to_target < (math.pi / 2 + horizon_angle_rad)

    def _compute_event_function(
        self, target: GroundTarget, timestamp: datetime
    ) -> float:
        """
        Compute the event function g(t) for visibility detection.

        The event function changes sign at visibility window boundaries:
        - g(t) > 0: Target is visible
        - g(t) < 0: Target is not visible
        - g(t) = 0: Transition point (AOS/LOS)

        For OPTICAL missions: combines elevation, pointing cone, and sunlight
        For SAR missions: combines elevation and pointing cone
        For COMMUNICATION: only elevation mask

        Args:
            target: Ground target
            timestamp: UTC datetime

        Returns:
            Event function value (positive = visible, negative = not visible)
        """
        try:
            # OPTIMIZATION: Fast ground-track prefilter (avoids 80-90% of expensive calculations)
            sat_lat, sat_lon, sat_alt = self.satellite.get_position(timestamp)
            if not self._is_satellite_near_target(
                target, timestamp, sat_lat, sat_lon, sat_alt
            ):
                return -90.0  # Far away - fast rejection without full 3D calculation

            elevation, _ = self.calculate_elevation_azimuth(target, timestamp)

            # Communication missions: simple elevation check
            if target.mission_type == "communication":
                return elevation - target.elevation_mask

            # Imaging missions: more complex constraints
            if target.mission_type == "imaging":
                # Must be above horizon
                if elevation <= 0:
                    return -90.0  # Large negative value

                # Check pointing cone (reuse sat position from prefilter)
                look_angle = self._calculate_look_angle(
                    sat_lat, sat_lon, sat_alt, target.latitude, target.longitude
                )

                # Get spacecraft roll limit for visibility - CRITICAL for finding passes!
                # Use max spacecraft agility (default 45°), NOT the narrow sensor FOV
                sensor_fov_half_angle_deg = (
                    getattr(target, "max_spacecraft_roll", None) or 45.0
                )

                # Pointing cone constraint
                cone_margin = sensor_fov_half_angle_deg - look_angle

                if cone_margin <= 0:
                    return cone_margin  # Negative = not in cone

                # For OPTICAL imaging, require target to be illuminated by sunlight
                imaging_type = getattr(target, "imaging_type", "optical")
                if imaging_type == "optical":
                    illuminated = is_target_illuminated(
                        target.latitude,
                        target.longitude,
                        timestamp,
                        min_sun_elevation=0.0,
                    )
                    if not illuminated:
                        return (
                            -90.0
                        )  # Target in darkness - not valid for optical imaging

                # All constraints satisfied - return margin
                return cone_margin

            # Default: elevation check
            return elevation - target.elevation_mask

        except Exception as e:
            logger.warning(f"Error computing event function at {timestamp}: {e}")
            return -90.0  # Conservative: assume not visible

    def _estimate_geometry_change_rate(
        self, target: GroundTarget, t1: datetime, g1: float, t2: datetime, g2: float
    ) -> float:
        """
        Estimate rate of change in visibility geometry between two time points.

        Args:
            target: Ground target
            t1: First timestamp
            g1: Event function value at t1
            t2: Second timestamp
            g2: Event function value at t2

        Returns:
            Normalized change rate (0 = no change, 1 = rapid change)
        """
        dt_seconds = (t2 - t1).total_seconds()
        if dt_seconds <= 0:
            return 0.0

        # Rate of change in degrees per second
        dg_dt = abs(g2 - g1) / dt_seconds

        # Normalize: typical satellite elevation changes are 0.1-0.5 deg/s near horizon
        # Rapid changes near transition points can be 1-5 deg/s
        normalized_rate = min(dg_dt / 2.0, 1.0)  # Clamp to [0, 1]

        return normalized_rate

    def _adaptive_step_size(self, current_step: float, change_rate: float) -> float:
        """
        Calculate adaptive step size based on geometry change rate.

        Args:
            current_step: Current step size in seconds
            change_rate: Geometry change rate [0, 1]

        Returns:
            New step size in seconds, clamped to [MIN, MAX] bounds
        """
        # High change rate: shrink step
        if change_rate > self.ADAPTIVE_CHANGE_THRESHOLD:
            new_step = current_step * self.ADAPTIVE_STEP_SHRINK_FACTOR
        else:
            # Low change rate: grow step
            new_step = current_step * self.ADAPTIVE_STEP_GROW_FACTOR

        # Clamp to bounds
        new_step = max(
            self.ADAPTIVE_MIN_STEP_SECONDS,
            min(self.ADAPTIVE_MAX_STEP_SECONDS, new_step),
        )

        return new_step

    def _refine_edge_time(
        self,
        target: GroundTarget,
        t_before: datetime,
        t_after: datetime,
        g_before: float,
        g_after: float,
    ) -> datetime:
        """
        Refine edge time using bisection root-finding.

        Finds the time when event function crosses zero between t_before and t_after.

        Args:
            target: Ground target
            t_before: Time before transition (known sign)
            t_after: Time after transition (opposite sign)
            g_before: Event function value at t_before
            g_after: Event function value at t_after

        Returns:
            Refined edge time (accurate to ADAPTIVE_REFINEMENT_TOLERANCE)
        """
        # Ensure we have a sign change
        if (g_before * g_after) > 0:
            # No sign change - return midpoint
            return t_before + (t_after - t_before) / 2

        # Bisection method
        t_left = t_before
        t_right = t_after
        g_left = g_before
        g_right = g_after

        for iteration in range(self.ADAPTIVE_MAX_REFINEMENT_ITERS):
            # Check convergence
            dt = (t_right - t_left).total_seconds()
            if dt <= self.ADAPTIVE_REFINEMENT_TOLERANCE:
                break

            # Bisect
            t_mid = t_left + (t_right - t_left) / 2
            g_mid = self._compute_event_function(target, t_mid)

            # Update interval
            if (g_left * g_mid) < 0:
                # Zero is in left half
                t_right = t_mid
                g_right = g_mid
            else:
                # Zero is in right half
                t_left = t_mid
                g_left = g_mid

        # Return midpoint of final interval
        return t_left + (t_right - t_left) / 2

    def _find_visibility_windows_adaptive(
        self, target: GroundTarget, start_time: datetime, end_time: datetime
    ) -> List[Tuple[datetime, datetime]]:
        """
        Find visibility windows using adaptive coarse→refine algorithm.

        Phase 1 (Coarse): Scan with adaptive steps to bracket transitions
        Phase 2 (Refine): Refine each bracket to high accuracy using bisection

        Args:
            target: Ground target
            start_time: Search window start
            end_time: Search window end

        Returns:
            List of (aos_time, los_time) tuples for each visibility window
        """
        windows = []
        current_time = start_time
        step_seconds = self.ADAPTIVE_INITIAL_STEP_SECONDS

        # Initial evaluation
        g_current = self._compute_event_function(target, current_time)
        in_window = g_current > 0

        window_start = current_time if in_window else None

        # Statistics for logging
        total_evaluations = 1
        coarse_evaluations = 1

        # Coarse scan with adaptive stepping
        while current_time < end_time:
            # Calculate next time point
            next_time = current_time + timedelta(seconds=step_seconds)
            if next_time > end_time:
                next_time = end_time

            # Evaluate at next point
            g_next = self._compute_event_function(target, next_time)
            total_evaluations += 1
            coarse_evaluations += 1

            # Detect sign change (transition)
            transition_detected = (g_current > 0) != (g_next > 0)

            if transition_detected:
                # OPTIMIZATION: Expand search window with margin for safety
                # This prevents missing brief passes when using large coarse steps
                margin_seconds = (
                    step_seconds * 3
                )  # Look 3 steps back/forward (increased for safety)

                search_start = max(
                    start_time, current_time - timedelta(seconds=margin_seconds)
                )
                search_end = min(
                    end_time, next_time + timedelta(seconds=margin_seconds)
                )

                # Re-evaluate at expanded boundaries
                g_search_start = self._compute_event_function(target, search_start)
                g_search_end = self._compute_event_function(target, search_end)
                total_evaluations += 2

                # Refine the edge within expanded window
                edge_time = self._refine_edge_time(
                    target, search_start, search_end, g_search_start, g_search_end
                )
                total_evaluations += self.ADAPTIVE_MAX_REFINEMENT_ITERS  # Approximate

                if g_next > 0:
                    # Rising edge: AOS (acquisition of signal)
                    window_start = edge_time
                else:
                    # Falling edge: LOS (loss of signal)
                    if window_start is not None:
                        windows.append((window_start, edge_time))
                        window_start = None

                # After transition, use smaller step
                step_seconds = self.ADAPTIVE_MIN_STEP_SECONDS * 2
            else:
                # No transition: adjust step based on change rate
                change_rate = self._estimate_geometry_change_rate(
                    target, current_time, g_current, next_time, g_next
                )
                step_seconds = self._adaptive_step_size(step_seconds, change_rate)

                # OPTIMIZATION: Orbital skip ahead when satellite is very far away
                # Check if we can skip ahead by a large time interval
                if (
                    g_next < -50.0
                ):  # Very negative = definitely not visible and far away
                    sat_lat, sat_lon, sat_alt = self.satellite.get_position(next_time)
                    skip_seconds = self._calculate_orbital_skip_ahead(
                        target, next_time, sat_lat, sat_lon, sat_alt
                    )
                    if skip_seconds > 0:
                        # Skip ahead - satellite is on opposite side of Earth
                        step_seconds = max(step_seconds, skip_seconds)

            # Move to next point
            current_time = next_time
            g_current = g_next

        # Handle ongoing window at end
        if window_start is not None:
            windows.append((window_start, end_time))

        # Log statistics
        total_duration = (end_time - start_time).total_seconds()
        logger.debug(
            f"Adaptive search: {total_evaluations} evaluations "
            f"({coarse_evaluations} coarse) over {total_duration/3600:.1f}h, "
            f"found {len(windows)} windows"
        )

        return windows

    def _calculate_ground_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate great circle distance between two points on Earth.

        Args:
            lat1, lon1: First point (degrees)
            lat2, lon2: Second point (degrees)

        Returns:
            Distance in kilometers
        """
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return EARTH_RADIUS_KM * c

    def _is_satellite_near_target(
        self,
        target: GroundTarget,
        timestamp: datetime,
        sat_lat: float,
        sat_lon: float,
        sat_alt: float,
    ) -> bool:
        """
        Fast 2D ground-track prefilter before expensive 3D calculations.

        This performs a simple great-circle distance check to quickly reject
        time points where the satellite is obviously too far from the target.
        This avoids expensive ECEF coordinate transformations and elevation
        calculations for ~80-90% of time steps in typical scenarios.

        Args:
            target: Ground target
            timestamp: UTC datetime
            sat_lat, sat_lon, sat_alt: Satellite position (degrees, km)

        Returns:
            True if satellite ground track is within possible visibility range
        """
        # Quick great circle distance (2D, cheap calculation)
        ground_distance = self._calculate_ground_distance(
            sat_lat, sat_lon, target.latitude, target.longitude
        )

        # Calculate maximum possible visibility range (line-of-sight to horizon)
        max_range_km = math.sqrt((EARTH_RADIUS_KM + sat_alt) ** 2 - EARTH_RADIUS_KM**2)

        # Add generous margin for:
        # - Off-nadir pointing angles (for imaging missions)
        # - Atmospheric refraction effects
        # - Computational safety buffer
        # - Edge cases with grazing angles
        margin_km = VISIBILITY_MARGIN_KM

        if target.mission_type == "imaging":
            # For imaging, add extra margin based on max spacecraft roll
            max_roll = getattr(target, "max_spacecraft_roll", None) or 45.0
            pointing_margin = sat_alt * math.tan(math.radians(max_roll))
            margin_km = max(margin_km, pointing_margin * 1.5)  # Extra 50% safety factor

        # Fast rejection: if ground track is too far, skip 3D calculations
        return ground_distance <= (max_range_km + margin_km)

    def _calculate_orbital_skip_ahead(
        self,
        target: GroundTarget,
        timestamp: datetime,
        sat_lat: float,
        sat_lon: float,
        sat_alt: float,
    ) -> float:
        """
        Calculate safe time to skip ahead when satellite is very far from target.

        When satellite is on the opposite side of Earth (>8000km away), we can
        safely skip ahead by a large time interval instead of taking small steps.
        This provides 5-10x additional speedup on top of the prefilter optimization.

        Args:
            target: Ground target
            timestamp: UTC datetime
            sat_lat, sat_lon, sat_alt: Satellite position (degrees, km)

        Returns:
            Number of seconds to skip ahead (0 = no skip, continue normal stepping)
        """
        # Calculate ground distance
        ground_distance = self._calculate_ground_distance(
            sat_lat, sat_lon, target.latitude, target.longitude
        )

        # Only skip if satellite is VERY far away (more than 1/3 of Earth circumference)
        # This means satellite is definitely on opposite side of Earth from target
        # Increased threshold from 8000 to 10000 for extra safety
        if ground_distance < ORBITAL_SKIP_DISTANCE_KM:
            return 0.0  # No skip - use normal adaptive stepping

        # Get orbital period
        orbital_period_seconds = self.satellite.get_orbital_period().total_seconds()

        # Calculate approximate time for satellite to travel the distance
        # Average ground track velocity for LEO: ~7 km/s
        # Very conservative estimate: use 0.2 × orbital period as skip time
        # Reduced from 0.3 to ensure we don't overshoot and miss approaches
        skip_seconds = orbital_period_seconds * 0.2

        # Cap the skip to a maximum to prevent overshooting
        max_skip_seconds = MAX_ORBITAL_SKIP_SECONDS
        skip_seconds = min(skip_seconds, max_skip_seconds)

        return skip_seconds

    def _apply_imaging_separation_filter(
        self, passes: List[PassDetails], target: GroundTarget
    ) -> List[PassDetails]:
        """
        Filter imaging passes based on satellite agility.

        For imaging missions, satellite passes are grouped by orbital periods.
        This method doesn't filter passes anymore - all passes are kept.
        Filtering is now handled by satellite agility parameter during
        opportunity detection.

        Args:
            passes: List of all detected passes
            target: Ground target

        Returns:
            All passes (no filtering applied)
        """
        logger.info(
            f"Imaging passes: {len(passes)} total (no separation filtering - using satellite agility)"
        )
        return passes

    def _process_imaging_opportunities(
        self,
        target: GroundTarget,
        start_time: datetime,
        end_time: datetime,
        time_step_seconds: int,
    ) -> List[PassDetails]:
        """
        Process imaging opportunities with proper separation filtering within each orbital pass.

        For imaging missions, this method:
        1. Finds all moments when target is within pointing cone
        2. Groups opportunities by orbital pass
        3. Applies minimum separation filtering within each pass
        4. Stores all potential opportunities for visualization

        Args:
            target: Ground target with imaging constraints
            start_time: Start of search window (UTC)
            end_time: End of search window (UTC)
            time_step_seconds: Time step for calculations

        Returns:
            List of filtered imaging opportunities
        """
        imaging_opportunities: List[Any] = []
        all_potential_opportunities: List[Any] = []  # Store for visualization
        current_time = start_time
        time_step = timedelta(seconds=time_step_seconds)

        logger.info(
            f"Processing imaging opportunities for {target.name} from {start_time} to {end_time}"
        )

        # Find all imaging opportunities
        while current_time <= end_time:
            try:
                elevation, azimuth = self.calculate_elevation_azimuth(
                    target, current_time
                )

                # Check if target is visible for imaging (within pointing cone)
                if self._is_target_visible(target, current_time, elevation):
                    # Get satellite position for this opportunity
                    sat_lat, sat_lon, sat_alt = self.satellite.get_position(
                        current_time
                    )

                    # Calculate look angle (off-nadir) for STK comparison
                    look_angle = self._calculate_look_angle(
                        sat_lat, sat_lon, sat_alt, target.latitude, target.longitude
                    )

                    opportunity = {
                        "time": current_time,
                        "elevation": elevation,
                        "look_angle": look_angle,  # Off-nadir angle for STK reporting
                        "azimuth": azimuth,
                        "sat_lat": sat_lat,
                        "sat_lon": sat_lon,
                        "sat_alt": sat_alt,
                    }
                    all_potential_opportunities.append(opportunity)

                current_time += time_step

            except Exception as e:
                logger.warning(
                    f"Error processing imaging opportunity at {current_time}: {e}"
                )
                current_time += time_step
                continue

        logger.info(
            f"Found {len(all_potential_opportunities)} potential imaging opportunities"
        )

        # Store all opportunities for visualization (we'll need this later)
        self._all_imaging_opportunities = all_potential_opportunities

        # Group opportunities by orbital pass and apply separation filtering
        if not all_potential_opportunities:
            return []

        # Group consecutive opportunities into passes
        passes = self._group_opportunities_into_passes(
            all_potential_opportunities, target
        )

        # Apply separation filtering within each pass
        filtered_passes = []
        for pass_opportunities in passes:
            filtered_opportunities = self._filter_opportunities_within_pass(
                pass_opportunities, target
            )

            if filtered_opportunities:
                # Create ONE PassDetails per orbital pass (not per opportunity)
                # Use the opportunity with BEST look angle (minimum off-nadir = closest to nadir)
                best_opp = min(filtered_opportunities, key=lambda x: x["look_angle"])

                # Calculate imaging window from FILTERED opportunities (after separation filtering)
                # This ensures the window only includes valid imaging times
                imaging_window_start = min(
                    opp["time"] for opp in filtered_opportunities
                )
                imaging_window_end = max(opp["time"] for opp in filtered_opportunities)

                # DEBUG: Log window calculation
                logger.info(
                    f"TARGET {target.name}: best_opp time={best_opp['time']}, window=[{imaging_window_start} to {imaging_window_end}], in_window={imaging_window_start <= best_opp['time'] <= imaging_window_end}"
                )

                # Convert off-nadir angle to STK format (from local horizontal)
                # STK measures from horizontal, not nadir: STK_angle = 90° - off_nadir
                stk_elevation = 90.0 - best_opp["look_angle"]

                # Compute SIGNED roll angle (critical for scheduler maneuver calculations!)
                # Must compute at pass start (or best opportunity) for clear left/right geometry
                try:
                    sat_lat, sat_lon, sat_alt = self.satellite.get_position(
                        best_opp["time"]
                    )
                    local_incidence_deg = self._calculate_signed_roll_angle(
                        sat_lat,
                        sat_lon,
                        sat_alt,
                        target.latitude,
                        target.longitude,
                        best_opp[
                            "time"
                        ],  # Use best opportunity time for clear geometry
                    )
                except Exception as e:
                    logger.warning(
                        f"Could not calculate signed roll angle, using unsigned proxy: {e}"
                    )
                    local_incidence_deg = best_opp["look_angle"]  # Fallback to unsigned

                # PassDetails stores FULL window for visualization (start to end of pass)
                # but max_elevation_time stores the optimal imaging time (min incidence angle)
                # Scheduler will use max_elevation_time, visualization uses start/end
                pass_details = PassDetails(
                    target_name=target.name,
                    satellite_name=self.satellite.satellite_name,
                    start_time=imaging_window_start,  # Full window start for visualization
                    max_elevation_time=best_opp[
                        "time"
                    ],  # Optimal imaging time for scheduler
                    end_time=imaging_window_end,  # Full window end for visualization
                    max_elevation=stk_elevation,  # STK-style angle (from horizontal)
                    start_azimuth=best_opp["azimuth"],
                    max_elevation_azimuth=best_opp["azimuth"],
                    end_azimuth=best_opp["azimuth"],
                    incidence_angle_deg=local_incidence_deg,  # Best off-nadir (proxy for incidence) for quality planning
                    mode="IMAGING",  # Imaging mission type
                )

                # Store both filtered opportunities and full imaging window
                pass_details._imaging_opportunities = filtered_opportunities
                pass_details._imaging_window = (
                    pass_opportunities  # All potential opportunities
                )
                filtered_passes.append(pass_details)

        logger.info(
            f"After separation filtering: {len(filtered_passes)} imaging opportunities"
        )
        return filtered_passes

    def _group_opportunities_into_passes(
        self, opportunities: List[dict], target: GroundTarget
    ) -> List[List[dict]]:
        """
        Group consecutive imaging opportunities into orbital passes.

        Args:
            opportunities: List of imaging opportunity dictionaries
            target: Ground target

        Returns:
            List of passes, each containing a list of opportunities
        """
        if not opportunities:
            return []

        passes = []
        current_pass = [opportunities[0]]

        for i in range(1, len(opportunities)):
            curr_opp = opportunities[i]
            prev_opp = opportunities[i - 1]

            # Check time gap between opportunities
            time_gap = (curr_opp["time"] - prev_opp["time"]).total_seconds()

            # If gap is more than 5 minutes, start a new pass
            if time_gap > PASS_GAP_THRESHOLD_SECONDS:
                passes.append(current_pass)
                current_pass = [curr_opp]
            else:
                current_pass.append(curr_opp)

        # Add the last pass
        if current_pass:
            passes.append(current_pass)

        # Logging removed from hot path for performance
        return passes

    def _filter_opportunities_within_pass(
        self, opportunities: List[dict], target: GroundTarget
    ) -> List[dict]:
        """
        Filter imaging opportunities within a single pass based on satellite agility.

        Satellite agility determines how quickly the satellite can slew between targets.
        This is handled during opportunity detection, so this method returns all opportunities.

        Args:
            opportunities: List of opportunities within a single pass
            target: Ground target

        Returns:
            All opportunities (filtering handled by satellite agility during detection)
        """
        # Logging removed from hot path for performance
        return opportunities

    def get_all_imaging_opportunities(self) -> List[dict]:
        """
        Get all potential imaging opportunities found during the last imaging analysis.

        Returns:
            List of all imaging opportunity dictionaries for visualization
        """
        return getattr(self, "_all_imaging_opportunities", [])

    def find_passes(
        self,
        target: GroundTarget,
        start_time: datetime,
        end_time: datetime,
        time_step_seconds: int = 1,
    ) -> List[PassDetails]:
        """
        Find all satellite passes over a target within time window.

        Uses adaptive time-stepping if enabled (self.use_adaptive), otherwise
        uses traditional fixed-step method.

        For imaging missions, applies minimum separation distance filtering
        to ensure realistic imaging intervals.

        Args:
            target: Ground target
            start_time: Start of search window (UTC)
            end_time: End of search window (UTC)
            time_step_seconds: Time step for calculations (fixed-step mode only)

        Returns:
            List of PassDetails objects
        """
        # Route to adaptive method if enabled
        if self.use_adaptive:
            return self._find_passes_adaptive(target, start_time, end_time)

        # Traditional fixed-step method (unchanged)
        passes = []
        current_time = start_time
        time_step = timedelta(seconds=time_step_seconds)

        in_pass = False
        pass_start_time: Optional[datetime] = None
        pass_elevations: List[float] = []
        pass_times: List[datetime] = []
        pass_azimuths: List[float] = []

        logger.info(
            f"Finding passes for {target.name} from {start_time} to {end_time} (fixed-step)"
        )

        while current_time <= end_time:
            try:
                elevation, azimuth = self.calculate_elevation_azimuth(
                    target, current_time
                )

                # Check visibility based on mission type
                is_visible = self._is_target_visible(target, current_time, elevation)

                if is_visible:
                    if not in_pass:
                        # Start of new pass
                        in_pass = True
                        pass_start_time = current_time
                        pass_elevations = [elevation]
                        pass_times = [current_time]
                        pass_azimuths = [azimuth]
                    else:
                        # Continue current pass
                        pass_elevations.append(elevation)
                        pass_times.append(current_time)
                        pass_azimuths.append(azimuth)
                else:
                    if in_pass:
                        # End of current pass
                        in_pass = False

                        if len(pass_elevations) > 0:
                            # Find maximum elevation
                            max_elev_idx = np.argmax(pass_elevations)
                            max_elevation = pass_elevations[max_elev_idx]
                            max_elev_time = pass_times[max_elev_idx]
                            max_elev_azimuth = pass_azimuths[max_elev_idx]

                            # Calculate SIGNED incidence angle at PASS START (not max elevation!)
                            # CRITICAL: Must compute at pass start when target is at edge of FOV
                            # At max elevation, satellite is overhead and left/right is ambiguous!
                            # Use pass_times[0] which is guaranteed to exist
                            actual_start_time = pass_times[0]
                            try:
                                sat_lat, sat_lon, sat_alt = self.satellite.get_position(
                                    actual_start_time
                                )
                                incidence_angle = self._calculate_signed_roll_angle(
                                    sat_lat,
                                    sat_lon,
                                    sat_alt,
                                    target.latitude,
                                    target.longitude,
                                    actual_start_time,  # Use pass START for clear left/right geometry
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Could not calculate signed incidence angle: {e}"
                                )
                                incidence_angle = None

                            # Create pass details
                            pass_details = PassDetails(
                                target_name=target.name,
                                satellite_name=self.satellite.satellite_name,
                                start_time=actual_start_time,
                                max_elevation_time=max_elev_time,
                                end_time=pass_times[-1],
                                max_elevation=max_elevation,
                                start_azimuth=pass_azimuths[0],
                                max_elevation_azimuth=max_elev_azimuth,
                                end_azimuth=pass_azimuths[-1],
                                incidence_angle_deg=incidence_angle,
                                mode=getattr(
                                    target, "mission_type", "COMMUNICATION"
                                ).upper(),
                            )

                            passes.append(pass_details)
                            # Logging removed from hot path for performance

                current_time += time_step

            except Exception as e:
                logger.warning(f"Error calculating visibility at {current_time}: {e}")
                current_time += time_step
                continue

        # Handle case where pass is ongoing at end of time window
        if in_pass and len(pass_elevations) > 0:
            max_elev_idx = np.argmax(pass_elevations)
            max_elevation = pass_elevations[max_elev_idx]
            max_elev_time = pass_times[max_elev_idx]
            max_elev_azimuth = pass_azimuths[max_elev_idx]

            # Calculate SIGNED incidence angle at PASS START (not max elevation!)
            # CRITICAL: Must compute at pass start when target is at edge of FOV
            # At max elevation, satellite is overhead and left/right is ambiguous!
            # Use pass_times[0] which is guaranteed to exist when we have pass_elevations
            actual_start = pass_times[0]
            try:
                sat_lat, sat_lon, sat_alt = self.satellite.get_position(actual_start)
                incidence_angle = self._calculate_signed_roll_angle(
                    sat_lat,
                    sat_lon,
                    sat_alt,
                    target.latitude,
                    target.longitude,
                    actual_start,  # Use pass START for clear left/right geometry
                )
            except Exception as e:
                logger.warning(f"Could not calculate signed incidence angle: {e}")
                incidence_angle = None

            pass_details = PassDetails(
                target_name=target.name,
                satellite_name=self.satellite.satellite_name,
                start_time=actual_start,
                max_elevation_time=max_elev_time,
                end_time=pass_times[-1],
                max_elevation=max_elevation,
                start_azimuth=pass_azimuths[0],
                max_elevation_azimuth=max_elev_azimuth,
                end_azimuth=pass_azimuths[-1],
                incidence_angle_deg=incidence_angle,
                mode=getattr(target, "mission_type", "COMMUNICATION").upper(),
            )

            passes.append(pass_details)

        # For imaging missions, find all imaging opportunities and apply separation filtering
        if target.mission_type == "imaging":
            passes = self._process_imaging_opportunities(
                target, start_time, end_time, time_step_seconds
            )
            logger.info(f"Found {len(passes)} imaging opportunities for {target.name}")
        else:
            logger.info(f"Found {len(passes)} passes for {target.name}")

        return passes

    def _find_passes_adaptive(
        self, target: GroundTarget, start_time: datetime, end_time: datetime
    ) -> List[PassDetails]:
        """
        Find passes using adaptive time-stepping algorithm.

        This method uses coarse→refine bracketing to efficiently find visibility
        windows with high accuracy.

        Args:
            target: Ground target
            start_time: Start of search window (UTC)
            end_time: End of search window (UTC)

        Returns:
            List of PassDetails objects
        """
        logger.info(
            f"Finding passes for {target.name} from {start_time} to {end_time} (adaptive)"
        )

        # Find visibility windows using adaptive algorithm
        windows = self._find_visibility_windows_adaptive(target, start_time, end_time)

        if not windows:
            return []

        # For imaging missions, use detailed imaging opportunity processing
        if target.mission_type == "imaging":
            # Use existing imaging opportunity processor but with adaptive windows
            passes = self._process_imaging_opportunities_adaptive(target, windows)
            logger.info(
                f"Found {len(passes)} imaging opportunities for {target.name} (adaptive)"
            )
            return passes

        # For communication missions, convert windows to PassDetails
        passes = []
        for window_start, window_end in windows:
            # Sample the window to find peak elevation and azimuths
            pass_details = self._create_pass_details_from_window(
                target, window_start, window_end
            )
            if pass_details:
                passes.append(pass_details)

        logger.info(f"Found {len(passes)} passes for {target.name} (adaptive)")
        return passes

    def _create_pass_details_from_window(
        self, target: GroundTarget, window_start: datetime, window_end: datetime
    ) -> Optional[PassDetails]:
        """
        Create PassDetails from a visibility window by sampling to find peak.

        Args:
            target: Ground target
            window_start: Window start time
            window_end: Window end time

        Returns:
            PassDetails object or None if window is invalid
        """
        # Sample window at regular intervals to find peak
        duration = (window_end - window_start).total_seconds()
        num_samples = max(5, int(duration / 10))  # At least 5 samples, every 10 seconds
        sample_step = duration / num_samples

        elevations = []
        azimuths = []
        times = []

        for i in range(num_samples + 1):
            sample_time = window_start + timedelta(seconds=i * sample_step)
            if sample_time > window_end:
                sample_time = window_end

            elevation, azimuth = self.calculate_elevation_azimuth(target, sample_time)
            elevations.append(elevation)
            azimuths.append(azimuth)
            times.append(sample_time)

        if not elevations:
            return None

        # Find maximum elevation
        max_idx = np.argmax(elevations)
        max_elevation = elevations[max_idx]
        max_elev_time = times[max_idx]
        max_elev_azimuth = azimuths[max_idx]

        # Create pass details
        return PassDetails(
            target_name=target.name,
            satellite_name=self.satellite.satellite_name,
            start_time=window_start,
            max_elevation_time=max_elev_time,
            end_time=window_end,
            max_elevation=max_elevation,
            start_azimuth=azimuths[0],
            max_elevation_azimuth=max_elev_azimuth,
            end_azimuth=azimuths[-1],
        )

    def _process_imaging_opportunities_adaptive(
        self, target: GroundTarget, windows: List[Tuple[datetime, datetime]]
    ) -> List[PassDetails]:
        """
        Process imaging opportunities using adaptive windows.

        Args:
            target: Ground target
            windows: List of (start, end) visibility windows

        Returns:
            List of PassDetails for imaging opportunities
        """
        all_potential_opportunities = []

        # For each window, sample to find imaging opportunities
        for window_start, window_end in windows:
            duration = (window_end - window_start).total_seconds()
            # Sample at 10-second intervals within each window
            sample_step = 10.0
            current_time = window_start

            while current_time <= window_end:
                try:
                    elevation, azimuth = self.calculate_elevation_azimuth(
                        target, current_time
                    )

                    # Check if visible (pointing cone constraints already in event function)
                    if self._is_target_visible(target, current_time, elevation):
                        sat_lat, sat_lon, sat_alt = self.satellite.get_position(
                            current_time
                        )

                        # Calculate look angle (off-nadir) for STK comparison
                        look_angle = self._calculate_look_angle(
                            sat_lat, sat_lon, sat_alt, target.latitude, target.longitude
                        )

                        opportunity = {
                            "time": current_time,
                            "elevation": elevation,
                            "look_angle": look_angle,  # Off-nadir angle for STK reporting
                            "azimuth": azimuth,
                            "sat_lat": sat_lat,
                            "sat_lon": sat_lon,
                            "sat_alt": sat_alt,
                        }
                        all_potential_opportunities.append(opportunity)

                    current_time += timedelta(seconds=sample_step)

                except Exception as e:
                    logger.warning(
                        f"Error processing imaging opportunity at {current_time}: {e}"
                    )
                    current_time += timedelta(seconds=sample_step)
                    continue

        logger.info(
            f"Found {len(all_potential_opportunities)} potential imaging opportunities (adaptive)"
        )

        # Store for visualization
        self._all_imaging_opportunities = all_potential_opportunities

        if not all_potential_opportunities:
            return []

        # Group into passes and apply separation filtering (reuse existing logic)
        passes = self._group_opportunities_into_passes(
            all_potential_opportunities, target
        )

        filtered_passes = []
        for pass_opportunities in passes:
            filtered_opportunities = self._filter_opportunities_within_pass(
                pass_opportunities, target
            )

            if filtered_opportunities:
                # Use the opportunity with BEST look angle (minimum off-nadir = closest to nadir)
                best_opp = min(filtered_opportunities, key=lambda x: x["look_angle"])
                # Calculate imaging window from FILTERED opportunities (after separation filtering)
                imaging_window_start = min(
                    opp["time"] for opp in filtered_opportunities
                )
                imaging_window_end = max(opp["time"] for opp in filtered_opportunities)

                # DEBUG: Log window calculation
                logger.info(
                    f"TARGET {target.name} (adaptive): best_opp time={best_opp['time']}, window=[{imaging_window_start} to {imaging_window_end}], in_window={imaging_window_start <= best_opp['time'] <= imaging_window_end}"
                )

                # Convert off-nadir angle to STK format (from local horizontal)
                # STK measures from horizontal, not nadir: STK_angle = 90° - off_nadir
                stk_elevation = 90.0 - best_opp["look_angle"]

                # Compute SIGNED roll angle (critical for scheduler maneuver calculations!)
                # Must compute at pass start (or best opportunity) for clear left/right geometry
                try:
                    sat_lat, sat_lon, sat_alt = self.satellite.get_position(
                        best_opp["time"]
                    )
                    local_incidence_deg = self._calculate_signed_roll_angle(
                        sat_lat,
                        sat_lon,
                        sat_alt,
                        target.latitude,
                        target.longitude,
                        best_opp[
                            "time"
                        ],  # Use best opportunity time for clear geometry
                    )
                except Exception as e:
                    logger.warning(
                        f"Could not calculate signed roll angle, using unsigned proxy: {e}"
                    )
                    local_incidence_deg = best_opp["look_angle"]  # Fallback to unsigned

                # PassDetails stores FULL window for visualization (start to end of pass)
                # but max_elevation_time stores the optimal imaging time (min incidence angle)
                # Scheduler will use max_elevation_time, visualization uses start/end
                pass_details = PassDetails(
                    target_name=target.name,
                    satellite_name=self.satellite.satellite_name,
                    start_time=imaging_window_start,  # Full window start for visualization
                    max_elevation_time=best_opp[
                        "time"
                    ],  # Optimal imaging time for scheduler
                    end_time=imaging_window_end,  # Full window end for visualization
                    max_elevation=stk_elevation,  # STK-style angle (from horizontal)
                    start_azimuth=best_opp["azimuth"],
                    max_elevation_azimuth=best_opp["azimuth"],
                    end_azimuth=best_opp["azimuth"],
                    incidence_angle_deg=local_incidence_deg,  # Best off-nadir (proxy for incidence) for quality planning
                    mode="IMAGING",  # Imaging mission type
                )

                pass_details._imaging_opportunities = filtered_opportunities
                pass_details._imaging_window = pass_opportunities
                filtered_passes.append(pass_details)

        logger.info(
            f"After separation filtering: {len(filtered_passes)} imaging opportunities (adaptive)"
        )
        return filtered_passes

    def get_next_pass(
        self, target: GroundTarget, start_time: datetime, max_search_hours: int = 48
    ) -> Optional[PassDetails]:
        """
        Get the next satellite pass over a target.

        Args:
            target: Ground target
            start_time: Start search time (UTC)
            max_search_hours: Maximum hours to search ahead

        Returns:
            Next PassDetails or None if no pass found
        """
        end_time = start_time + timedelta(hours=max_search_hours)
        passes = self.find_passes(target, start_time, end_time)

        if passes:
            return passes[0]  # Return first (earliest) pass

        return None

    def is_visible(self, target: GroundTarget, timestamp: datetime) -> bool:
        """
        Check if satellite is visible from target at specific time.

        Args:
            target: Ground target
            timestamp: UTC datetime

        Returns:
            True if satellite is visible (above elevation mask)
        """
        try:
            elevation, _ = self.calculate_elevation_azimuth(target, timestamp)
            return elevation >= target.elevation_mask
        except Exception as e:
            logger.error(f"Error checking visibility: {e}")
            return False

    def find_passes_vectorized(
        self,
        target: GroundTarget,
        start_time: datetime,
        end_time: datetime,
        time_step_seconds: int = 1,
    ) -> List[PassDetails]:
        """
        Find satellite passes using NumPy vectorization for performance.

        This is a vectorized implementation that processes all timestamps at once
        using NumPy operations, providing 5-10x speedup over the loop-based approach.

        Args:
            target: Ground target to analyze
            start_time: Start of search window
            end_time: End of search window
            time_step_seconds: Time step in seconds (default: 1)

        Returns:
            List of PassDetails for all passes in the time window
        """
        import pandas as pd  # type: ignore[import-untyped]

        logger.info(
            f"Finding passes (vectorized) for {target.name} from {start_time} to {end_time}"
        )

        # Generate all timestamps
        time_delta = timedelta(seconds=time_step_seconds)
        num_steps = int((end_time - start_time).total_seconds() / time_step_seconds) + 1

        # Create timestamp array
        timestamps = [start_time + i * time_delta for i in range(num_steps)]
        n = len(timestamps)

        # Get cached location for target
        location = self._get_location(target)
        earth_radius = EARTH_RADIUS_KM

        # Pre-compute ground station ECEF (constant)
        ground_x, ground_y, ground_z = self._get_ground_ecef(location)
        ground_up_x = ground_x / earth_radius
        ground_up_y = ground_y / earth_radius
        ground_up_z = ground_z / earth_radius

        # Get all satellite positions (vectorized via caching)
        sat_positions_list = []
        for ts in timestamps:
            pos = self._get_satellite_position(ts)
            sat_lat, sat_lon, sat_alt = pos.position_llh
            sat_positions_list.append((sat_lat, sat_lon, sat_alt))

        # Convert to NumPy arrays
        sat_positions_arr = np.array(sat_positions_list)
        sat_lats = sat_positions_arr[:, 0]
        sat_lons = sat_positions_arr[:, 1]
        sat_alts = sat_positions_arr[:, 2]

        # Vectorized ECEF conversion
        sat_lat_rad = np.radians(sat_lats)
        sat_lon_rad = np.radians(sat_lons)

        sat_x = (earth_radius + sat_alts) * np.cos(sat_lat_rad) * np.cos(sat_lon_rad)
        sat_y = (earth_radius + sat_alts) * np.cos(sat_lat_rad) * np.sin(sat_lon_rad)
        sat_z = (earth_radius + sat_alts) * np.sin(sat_lat_rad)

        # Vectorized vector from ground to satellite
        dx = sat_x - ground_x
        dy = sat_y - ground_y
        dz = sat_z - ground_z

        # Vectorized range calculation
        ranges = np.sqrt(dx * dx + dy * dy + dz * dz)

        # Vectorized elevation calculation
        dot_products = dx * ground_up_x + dy * ground_up_y + dz * ground_up_z
        elevation_rads = np.arcsin(np.clip(dot_products / ranges, -1.0, 1.0))
        elevations = np.degrees(elevation_rads)

        # Vectorized azimuth calculation
        ground_lat = location.latitude_deg
        ground_lon = location.longitude_deg
        ground_lat_rad = np.radians(ground_lat)
        ground_lon_rad = np.radians(ground_lon)

        dlon = sat_lon_rad - ground_lon_rad
        y_az = np.sin(dlon) * np.cos(sat_lat_rad)
        x_az = np.cos(ground_lat_rad) * np.sin(sat_lat_rad) - np.sin(
            ground_lat_rad
        ) * np.cos(sat_lat_rad) * np.cos(dlon)

        azimuth_rads = np.arctan2(y_az, x_az)
        azimuths = np.degrees(azimuth_rads)
        azimuths = (azimuths + 360) % 360  # Convert to 0-360 range

        # Find passes using vectorized operations
        above_mask = elevations >= target.elevation_mask

        # Detect pass boundaries
        diff = np.diff(above_mask.astype(int))
        pass_starts = np.where(diff == 1)[0] + 1  # Rising edge
        pass_ends = np.where(diff == -1)[0] + 1  # Falling edge

        # Handle edge cases
        if above_mask[0]:
            pass_starts = np.concatenate([[0], pass_starts])
        if above_mask[-1]:
            pass_ends = np.concatenate([pass_ends, [n - 1]])

        # Build pass details
        passes = []
        for start_idx, end_idx in zip(pass_starts, pass_ends):
            if start_idx >= end_idx:
                continue

            # Extract pass data
            pass_elevations = elevations[start_idx : end_idx + 1]
            pass_azimuths = azimuths[start_idx : end_idx + 1]
            pass_times = timestamps[start_idx : end_idx + 1]

            # Find maximum elevation
            max_idx_in_pass = np.argmax(pass_elevations)
            max_elevation = pass_elevations[max_idx_in_pass]
            max_elev_time = pass_times[max_idx_in_pass]
            max_elev_azimuth = pass_azimuths[max_idx_in_pass]

            # Create pass details
            pass_details = PassDetails(
                target_name=target.name,
                satellite_name=self.satellite.satellite_name,
                start_time=pass_times[0],
                max_elevation_time=max_elev_time,
                end_time=pass_times[-1],
                max_elevation=float(max_elevation),
                start_azimuth=float(pass_azimuths[0]),
                max_elevation_azimuth=float(max_elev_azimuth),
                end_azimuth=float(pass_azimuths[-1]),
            )

            passes.append(pass_details)

        logger.info(f"Found {len(passes)} passes for {target.name} (vectorized)")
        return passes

    def get_visibility_windows(
        self,
        targets: List[GroundTarget],
        start_time: datetime,
        end_time: datetime,
        use_parallel: bool = False,
        max_workers: Optional[int] = None,
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, List[PassDetails]]:
        """
        Get visibility windows for multiple targets.

        Args:
            targets: List of ground targets
            start_time: Start of search window (UTC)
            end_time: End of search window (UTC)
            use_parallel: Enable parallel processing for multiple targets
            max_workers: Maximum parallel workers (None = auto-detect)
            progress_callback: Optional callback(completed, total) for progress

        Returns:
            Dictionary mapping target names to lists of passes
        """
        # Use parallel processing if enabled and we have multiple targets
        if use_parallel and len(targets) > 1:
            try:
                from .parallel import ParallelVisibilityCalculator

                logger.info(f"Using parallel processing for {len(targets)} targets")
                parallel_calc = ParallelVisibilityCalculator(
                    self.satellite,
                    max_workers=max_workers,
                    use_adaptive=self.use_adaptive,
                )

                # Get results as dictionaries
                results_dict = parallel_calc.get_visibility_windows(
                    targets, start_time, end_time, progress_callback=progress_callback
                )

                # Convert dictionary results back to PassDetails objects
                visibility_windows = {}
                for target_name, passes_dicts in results_dict.items():
                    passes = []
                    for p_dict in passes_dicts:
                        # Reconstruct PassDetails from dict
                        pass_detail = PassDetails(
                            target_name=p_dict["target_name"],
                            satellite_name=p_dict["satellite_name"],
                            start_time=datetime.fromisoformat(p_dict["start_time"]),
                            max_elevation_time=datetime.fromisoformat(
                                p_dict["max_elevation_time"]
                            ),
                            end_time=datetime.fromisoformat(p_dict["end_time"]),
                            max_elevation=p_dict["max_elevation"],
                            start_azimuth=p_dict["start_azimuth"],
                            max_elevation_azimuth=p_dict["max_elevation_azimuth"],
                            end_azimuth=p_dict["end_azimuth"],
                            incidence_angle_deg=p_dict.get(
                                "incidence_angle_deg"
                            ),  # Quality metric
                            mode=p_dict.get("mode"),  # OPTICAL, SAR, or IMAGING
                        )
                        passes.append(pass_detail)
                    visibility_windows[target_name] = passes

                total_passes = sum(
                    len(passes) for passes in visibility_windows.values()
                )
                logger.info(
                    f"Found {total_passes} total passes across {len(targets)} targets (parallel)"
                )

                return visibility_windows

            except ImportError as e:
                logger.warning(
                    f"Parallel processing not available: {e}. Falling back to serial."
                )
            except Exception as e:
                logger.error(
                    f"Parallel processing failed: {e}. Falling back to serial."
                )

        # Serial processing (original implementation)
        visibility_windows = {}

        for i, target in enumerate(targets):
            passes = self.find_passes(target, start_time, end_time)
            visibility_windows[target.name] = passes

            if progress_callback:
                progress_callback(i + 1, len(targets))

        total_passes = sum(len(passes) for passes in visibility_windows.values())
        logger.info(f"Found {total_passes} total passes across {len(targets)} targets")

        return visibility_windows

    def enrich_pass_with_stk_data(
        self,
        pass_details: PassDetails,
        target: GroundTarget,
        max_roll_rate_dps: float = 1.0,
        sensor_gsd_base_m: Optional[float] = None,
    ) -> PassDetails:
        """
        Enrich a PassDetails object with comprehensive STK-like metrics.

        Computes geometry, lighting, quality, and maneuver data for the pass.

        Args:
            pass_details: The basic pass details to enrich
            target: Ground target object
            max_roll_rate_dps: Maximum roll rate in deg/sec for slew time calc
            sensor_gsd_base_m: Base GSD at nadir (if None, GSD not computed)

        Returns:
            The same PassDetails object with enhanced fields populated
        """
        try:
            # Compute geometry at AOS, TCA, and LOS
            pass_details.geometry_aos = self._compute_geometry_at_time(
                target, pass_details.start_time, sensor_gsd_base_m
            )
            pass_details.geometry_tca = self._compute_geometry_at_time(
                target, pass_details.max_elevation_time, sensor_gsd_base_m
            )
            pass_details.geometry_los = self._compute_geometry_at_time(
                target, pass_details.end_time, sensor_gsd_base_m
            )

            # Compute lighting at TCA (most relevant moment)
            pass_details.lighting = self._compute_lighting_at_time(
                target, pass_details.max_elevation_time
            )

            # Compute quality score
            pass_details.quality = self._compute_quality_score(pass_details, target)

            # Compute maneuver requirements
            pass_details.maneuver = self._compute_maneuver_requirements(
                target, pass_details.max_elevation_time, max_roll_rate_dps
            )

            # Update legacy incidence angle from geometry
            if pass_details.geometry_tca:
                pass_details.incidence_angle_deg = (
                    pass_details.geometry_tca.incidence_angle_deg
                )

        except Exception as e:
            logger.warning(f"Failed to enrich pass with STK data: {e}")

        return pass_details

    def _compute_geometry_at_time(
        self,
        target: GroundTarget,
        timestamp: datetime,
        sensor_gsd_base_m: Optional[float] = None,
    ) -> PassGeometry:
        """Compute full geometry data at a specific time."""
        # Get satellite position
        sat_lat, sat_lon, sat_alt = self.satellite.get_position(timestamp)

        # Calculate elevation and azimuth
        elevation, azimuth = self.calculate_elevation_azimuth(target, timestamp)

        # Calculate range (slant distance)
        range_km = self._calculate_range(
            sat_lat, sat_lon, sat_alt, target.latitude, target.longitude
        )

        # Calculate incidence angle (off-nadir/look angle)
        incidence_angle = self._calculate_look_angle(
            sat_lat, sat_lon, sat_alt, target.latitude, target.longitude
        )

        # Calculate GSD if base GSD is provided
        gsd_m = None
        if sensor_gsd_base_m is not None and incidence_angle < 70:
            # GSD increases with off-nadir angle: GSD = base_GSD / cos(incidence)
            cos_inc = math.cos(math.radians(incidence_angle))
            if cos_inc > 0.1:  # Avoid extreme values
                gsd_m = sensor_gsd_base_m / cos_inc

        return PassGeometry(
            elevation_deg=elevation,
            azimuth_deg=azimuth,
            range_km=range_km,
            incidence_angle_deg=incidence_angle,
            ground_sample_distance_m=gsd_m,
        )

    def _calculate_range(
        self,
        sat_lat: float,
        sat_lon: float,
        sat_alt: float,
        target_lat: float,
        target_lon: float,
    ) -> float:
        """Calculate slant range from satellite to target in km."""
        # Convert to radians
        sat_lat_rad = math.radians(sat_lat)
        sat_lon_rad = math.radians(sat_lon)
        target_lat_rad = math.radians(target_lat)
        target_lon_rad = math.radians(target_lon)

        # Satellite position in ECEF
        sat_r = EARTH_RADIUS_KM + sat_alt
        sat_x = sat_r * math.cos(sat_lat_rad) * math.cos(sat_lon_rad)
        sat_y = sat_r * math.cos(sat_lat_rad) * math.sin(sat_lon_rad)
        sat_z = sat_r * math.sin(sat_lat_rad)

        # Target position in ECEF (on surface)
        target_x = EARTH_RADIUS_KM * math.cos(target_lat_rad) * math.cos(target_lon_rad)
        target_y = EARTH_RADIUS_KM * math.cos(target_lat_rad) * math.sin(target_lon_rad)
        target_z = EARTH_RADIUS_KM * math.sin(target_lat_rad)

        # Calculate distance
        dx = sat_x - target_x
        dy = sat_y - target_y
        dz = sat_z - target_z

        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def _compute_lighting_at_time(
        self,
        target: GroundTarget,
        timestamp: datetime,
    ) -> PassLighting:
        """Compute lighting conditions at a specific time."""
        from .sunlight import get_sun_elevation, is_target_illuminated

        # Get sun elevation at target
        sun_elevation = get_sun_elevation(target.latitude, target.longitude, timestamp)

        # Check if target is illuminated
        target_sunlit = is_target_illuminated(
            target.latitude, target.longitude, timestamp, min_sun_elevation=0.0
        )

        # Check if satellite is in sunlight (simplified - assume sunlit if sun elevation > -18°)
        # A more accurate calculation would check satellite position vs Earth shadow
        satellite_sunlit = sun_elevation > -18  # Civil twilight approximation

        # Calculate local solar time
        # LST = UTC + longitude/15 (hours)
        utc_hour = timestamp.hour + timestamp.minute / 60 + timestamp.second / 3600
        lst_hour = (utc_hour + target.longitude / 15) % 24
        lst_minutes = int((lst_hour % 1) * 60)
        lst_hour_int = int(lst_hour)
        local_solar_time = f"{lst_hour_int:02d}:{lst_minutes:02d}"

        return PassLighting(
            target_sunlit=target_sunlit,
            satellite_sunlit=satellite_sunlit,
            sun_elevation_deg=sun_elevation,
            local_solar_time=local_solar_time,
        )

    def _compute_quality_score(
        self,
        pass_details: PassDetails,
        target: GroundTarget,
    ) -> PassQuality:
        """Compute imaging quality score for a pass."""
        score = 100.0
        feasible = True
        reasons = []

        # Factor 1: Elevation (higher is better, max at 90°)
        # Below 20° is poor, above 60° is excellent
        elevation = pass_details.max_elevation
        if elevation < 10:
            score -= 40
            reasons.append("Very low elevation")
        elif elevation < 20:
            score -= 25
            reasons.append("Low elevation")
        elif elevation < 40:
            score -= 10
        elif elevation > 70:
            score += 5  # Bonus for high elevation

        # Factor 2: Incidence angle (lower is better for most applications)
        if pass_details.geometry_tca:
            incidence = pass_details.geometry_tca.incidence_angle_deg
            if incidence > 50:
                score -= 30
                reasons.append("High incidence angle")
            elif incidence > 40:
                score -= 15
            elif incidence > 30:
                score -= 5

        # Factor 3: Lighting (for optical imaging)
        if pass_details.lighting:
            if not pass_details.lighting.target_sunlit:
                if getattr(target, "imaging_type", "optical") == "optical":
                    feasible = False
                    reasons.append("Target not illuminated")
                    score -= 50
            elif pass_details.lighting.sun_elevation_deg < 15:
                score -= 10
                reasons.append("Low sun angle")

        # Factor 4: Pass duration (longer is better for more imaging options)
        duration_s = (pass_details.end_time - pass_details.start_time).total_seconds()
        if duration_s < 60:
            score -= 20
            reasons.append("Very short pass")
        elif duration_s < 120:
            score -= 10
            reasons.append("Short pass")
        elif duration_s > 300:
            score += 5  # Bonus for long passes

        # Clamp score to 0-100
        score = max(0, min(100, score))

        return PassQuality(
            quality_score=score,
            imaging_feasible=feasible,
            feasibility_reason="; ".join(reasons) if reasons else None,
        )

    def _compute_maneuver_requirements(
        self,
        target: GroundTarget,
        timestamp: datetime,
        max_roll_rate_dps: float = 1.0,
    ) -> PassManeuver:
        """Compute maneuver requirements for imaging at a specific time."""
        sat_lat, sat_lon, sat_alt = self.satellite.get_position(timestamp)

        # Calculate roll angle (signed)
        roll_angle = self._calculate_signed_roll_angle(
            sat_lat,
            sat_lon,
            sat_alt,
            target.latitude,
            target.longitude,
            timestamp,
        )

        # Pitch is typically 0 at max elevation
        pitch_angle = 0.0

        # Total slew from nadir
        slew_angle = abs(roll_angle)

        # Calculate slew time based on roll rate
        slew_time_s = slew_angle / max_roll_rate_dps if max_roll_rate_dps > 0 else None

        return PassManeuver(
            roll_angle_deg=roll_angle,
            pitch_angle_deg=pitch_angle,
            slew_angle_deg=slew_angle,
            slew_time_s=slew_time_s,
        )
