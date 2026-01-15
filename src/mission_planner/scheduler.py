"""
Mission planning scheduler with multiple greedy algorithms.

This module provides scheduling algorithms that select from opportunities
produced by visibility analysis, applying satellite agility constraints
and optimizing for different objectives (chronological, priority, value-density).
"""

import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

# Import for satellite position tracking
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from .orbit import SatelliteOrbit

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS - Extracted from magic numbers for clarity and maintainability
# =============================================================================

# Earth parameters
EARTH_RADIUS_KM = 6371.0

# Scheduling constants
MIN_GAP_SECONDS = 10.0  # Minimum gap between scheduled opportunities
PITCH_THRESHOLD_DEG = 0.1  # Below this, pitch is considered negligible
ROLL_ONLY_PITCH_THRESHOLD_DEG = 1.0  # Below this, opportunity is roll-only
DELTA_PITCH_THRESHOLD_DEG = 5.0  # Below this delta, no pitch reset needed


class AlgorithmType(Enum):
    """Supported scheduling algorithms."""

    FIRST_FIT = "first_fit"
    BEST_FIT = "best_fit"
    ROLL_PITCH_FIRST_FIT = "roll_pitch_first_fit"  # 2D slew (roll+pitch) greedy chronological with pitch fallback
    ROLL_PITCH_BEST_FIT = (
        "roll_pitch_best_fit"  # 2D slew (roll+pitch) global best geometry
    )


@dataclass
class Opportunity:
    """
    A single imaging or communication opportunity.

    This represents a time window when a satellite can observe/communicate
    with a target, as produced by visibility analysis.
    """

    id: str
    satellite_id: str
    target_id: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float = 0.0

    # Optional metadata
    max_elevation: Optional[float] = None  # degrees
    azimuth: Optional[float] = None  # degrees
    orbit_direction: Optional[str] = None  # ascending/descending

    # Pointing angles - IMPORTANT: These are SIGNED values!
    # incidence_angle: Off-nadir angle from satellite to target
    #   - Magnitude: absolute angle from nadir (0° = directly below satellite)
    #   - Sign: indicates left (-) or right (+) of ground track (aerospace convention)
    #   - Used for: roll maneuver calculations in scheduler
    incidence_angle: Optional[float] = None  # SIGNED degrees

    # pitch_angle: Along-track pointing angle
    #   - Negative: backward looking (imaging early in pass)
    #   - Zero: overhead/nadir (at max elevation)
    #   - Positive: forward looking (imaging late in pass)
    pitch_angle: Optional[float] = None  # SIGNED degrees

    # Priority/value for optimization (default: uniform)
    value: float = 1.0
    priority: int = 1

    # SAR-specific fields (threaded from SAROpportunityData)
    mission_mode: Optional[str] = None  # "SAR" | "OPTICAL"
    sar_mode: Optional[str] = None  # "spot" | "strip" | "scan" | "dwell"
    look_side: Optional[str] = None  # "LEFT" | "RIGHT"
    pass_direction: Optional[str] = None  # "ASCENDING" | "DESCENDING"
    incidence_center_deg: Optional[float] = None  # Center incidence for SAR
    incidence_near_deg: Optional[float] = None  # Near edge incidence
    incidence_far_deg: Optional[float] = None  # Far edge incidence
    swath_width_km: Optional[float] = None  # Mode-derived swath width
    scene_length_km: Optional[float] = None  # Mode-derived scene length
    sar_quality_score: Optional[float] = None  # Band model quality (0-1)

    def __post_init__(self) -> None:
        """Calculate duration if not provided."""
        if self.duration_seconds == 0.0:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()


@dataclass
class ScheduledOpportunity:
    """
    A selected opportunity with scheduling metadata.

    Includes computed agility maneuver parameters and slack time.
    """

    opportunity_id: str
    satellite_id: str
    target_id: str
    start_time: datetime
    end_time: datetime

    # Agility maneuver details
    delta_roll: float  # degrees (SIGNED change from previous: can be negative)
    delta_pitch: float = 0.0  # degrees (SIGNED change from previous)
    roll_angle: float = (
        0.0  # degrees (SIGNED absolute roll from nadir: negative=left, positive=right)
    )
    pitch_angle: float = 0.0  # degrees (SIGNED absolute pitch from nadir)
    maneuver_time: float = 0.0  # seconds (slew time)
    slack_time: float = 0.0  # seconds (available - required)

    # Optimization metrics
    value: float = 1.0
    density: float = 0.0  # value / maneuver_time (or infinity for zero slew)
    incidence_angle: Optional[float] = (
        None  # Off-nadir angle in degrees (for imaging quality)
    )

    # Satellite position at opportunity start time (for visualization)
    satellite_lat: Optional[float] = None  # degrees
    satellite_lon: Optional[float] = None  # degrees
    satellite_alt: Optional[float] = None  # km

    # SAR-specific fields (copied from Opportunity)
    mission_mode: Optional[str] = None  # "SAR" | "OPTICAL"
    sar_mode: Optional[str] = None  # "spot" | "strip" | "scan" | "dwell"
    look_side: Optional[str] = None  # "LEFT" | "RIGHT"
    pass_direction: Optional[str] = None  # "ASCENDING" | "DESCENDING"
    incidence_center_deg: Optional[float] = None  # Center incidence for SAR
    swath_width_km: Optional[float] = None  # Mode-derived swath width
    scene_length_km: Optional[float] = None  # Mode-derived scene length
    swath_polygon: Optional[List[Tuple[float, float]]] = (
        None  # Computed polygon [(lat, lon), ...]
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {
            "opportunity_id": self.opportunity_id,
            "satellite_id": self.satellite_id,
            "target_id": self.target_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "delta_roll": round(self.delta_roll, 2),
            "delta_pitch": round(self.delta_pitch, 2),
            "roll_angle": round(self.roll_angle, 2),
            "pitch_angle": round(self.pitch_angle, 2),
            "maneuver_time": round(self.maneuver_time, 3),
            "slack_time": round(self.slack_time, 3),
            "value": round(self.value, 2),
            "density": (
                round(self.density, 3) if self.density != float("inf") else "inf"
            ),
        }

        # Add incidence angle if available (for imaging missions)
        if self.incidence_angle is not None:
            result["incidence_angle"] = round(self.incidence_angle, 2)

        # Add satellite position if available (for visualization)
        if self.satellite_lat is not None:
            result["satellite_lat"] = round(self.satellite_lat, 6)
            if self.satellite_lon is not None:
                result["satellite_lon"] = round(self.satellite_lon, 6)
            if self.satellite_alt is not None:
                result["satellite_alt"] = round(self.satellite_alt, 3)

        # Add SAR-specific fields if this is a SAR opportunity
        if self.mission_mode:
            result["mission_mode"] = self.mission_mode
        if self.sar_mode:
            result["sar_mode"] = self.sar_mode
        if self.look_side:
            result["look_side"] = self.look_side
        if self.pass_direction:
            result["pass_direction"] = self.pass_direction
        if self.incidence_center_deg is not None:
            result["incidence_center_deg"] = round(self.incidence_center_deg, 2)
        if self.swath_width_km is not None:
            result["swath_width_km"] = round(self.swath_width_km, 2)
        if self.scene_length_km is not None:
            result["scene_length_km"] = round(self.scene_length_km, 2)
        if self.swath_polygon:
            result["swath_polygon"] = [
                [round(lat, 6), round(lon, 6)] for lat, lon in self.swath_polygon
            ]

        return result


@dataclass
class ScheduleMetrics:
    """Performance metrics for a schedule."""

    algorithm: str
    runtime_ms: float

    # Opportunity statistics
    opportunities_evaluated: int
    opportunities_accepted: int
    opportunities_rejected: int

    # Value metrics
    total_value: float
    mean_value: float

    # Time metrics
    total_imaging_time: float  # seconds
    total_maneuver_time: float  # seconds
    schedule_span: float  # seconds (first to last opportunity)
    utilization: float  # (imaging + maneuver) / span

    # Density metrics
    mean_density: float
    median_density: float

    # Quality metrics
    mean_incidence_deg: Optional[float] = None  # Average incidence angle

    # Pitch usage metrics (for roll+pitch algorithms)
    total_pitch_used_deg: Optional[float] = None  # Sum of absolute pitch angles
    max_pitch_deg: Optional[float] = None  # Maximum absolute pitch angle used
    opportunities_saved_by_pitch: Optional[int] = (
        None  # Opportunities accepted due to pitch capability
    )

    # Determinism
    seed: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {
            "algorithm": self.algorithm,
            "runtime_ms": round(self.runtime_ms, 2),
            "opportunities_evaluated": self.opportunities_evaluated,
            "opportunities_accepted": self.opportunities_accepted,
            "opportunities_rejected": self.opportunities_rejected,
            "total_value": round(self.total_value, 2),
            "mean_value": round(self.mean_value, 2),
            "total_imaging_time_s": round(self.total_imaging_time, 2),
            "total_maneuver_time_s": round(self.total_maneuver_time, 2),
            "schedule_span_s": round(self.schedule_span, 2),
            "utilization": round(self.utilization, 4),
            "mean_density": round(self.mean_density, 3),
            "median_density": round(self.median_density, 3),
            "seed": self.seed,
        }

        # Add optional quality metrics
        if self.mean_incidence_deg is not None:
            result["mean_incidence_deg"] = round(self.mean_incidence_deg, 2)

        # Add optional pitch metrics
        if self.total_pitch_used_deg is not None:
            result["total_pitch_used_deg"] = round(self.total_pitch_used_deg, 2)
        if self.max_pitch_deg is not None:
            result["max_pitch_deg"] = round(self.max_pitch_deg, 2)
        if self.opportunities_saved_by_pitch is not None:
            result["opportunities_saved_by_pitch"] = self.opportunities_saved_by_pitch

        return result


@dataclass
class SchedulerConfig:
    """Configuration for mission planning scheduler."""

    # Imaging/observation time
    imaging_time_s: float = 5.0  # tau - time on target

    # Spacecraft bus agility limits (NOTE: These are bus limits, NOT sensor FOV!)
    # Sensor FOV is configured separately in SensorConfig
    max_spacecraft_roll_deg: float = (
        90.0  # Maximum roll angle from nadir (bus mechanical/thermal limit)
    )
    max_roll_rate_dps: float = 1.0  # degrees per second
    max_roll_accel_dps2: float = 10000.0  # degrees per second squared
    max_spacecraft_pitch_deg: float = (
        0.0  # Maximum pitch angle from nadir (forward/backward looking)
    )
    max_pitch_rate_dps: float = 1.0  # Pitch slew rate (degrees per second)
    max_pitch_accel_dps2: float = (
        10000.0  # Pitch acceleration (degrees per second squared)
    )

    # Algorithm parameters
    look_window_s: float = 600.0  # candidate window for Best-Fit/Value-Density

    # Value source
    value_source: str = "uniform"  # uniform | target_priority | custom
    default_value: float = 1.0

    def __post_init__(self) -> None:
        """Validate configuration."""
        # Validate configuration to prevent runtime errors
        if self.max_roll_rate_dps <= 0:
            raise ValueError(
                f"max_roll_rate_dps must be positive, got {self.max_roll_rate_dps}"
            )
        if self.max_roll_accel_dps2 <= 0:
            raise ValueError(
                f"max_roll_accel_dps2 must be positive, got {self.max_roll_accel_dps2}"
            )
        if self.imaging_time_s < 0:
            raise ValueError(
                f"imaging_time_s must be non-negative, got {self.imaging_time_s}"
            )
        if self.max_spacecraft_roll_deg < 0:
            raise ValueError(
                f"max_spacecraft_roll_deg must be non-negative, got {self.max_spacecraft_roll_deg}"
            )
        if self.max_spacecraft_pitch_deg < 0:
            raise ValueError(
                f"max_spacecraft_pitch_deg must be non-negative, got {self.max_spacecraft_pitch_deg}"
            )


class FeasibilityKernel:
    """
    Shared feasibility kernel for agility constraint checking.

    Computes required maneuver time and checks if a transition
    from one opportunity to another is kinematically feasible.

    Supports constellation operations with per-satellite attitude tracking.
    """

    def __init__(
        self, config: SchedulerConfig, satellite: Optional["SatelliteOrbit"] = None
    ):
        """Initialize with scheduler configuration and satellite object.

        Args:
            config: Scheduler configuration
            satellite: SatelliteOrbit object for getting actual altitude (production-ready)
        """
        self.config = config
        self.satellite = satellite

        # Track current satellite attitude (persistent across passes)
        # Legacy single-satellite mode
        self.current_roll = 0.0  # degrees from nadir
        self.current_pitch = 0.0  # degrees from nadir

        # NEW: Per-satellite attitude tracking for constellation support
        self._satellite_attitudes: Dict[str, Dict[str, float]] = {}

        # Earth radius in km
        self.R_EARTH = EARTH_RADIUS_KM

    def get_satellite_attitude(self, satellite_id: str) -> Tuple[float, float]:
        """
        Get current attitude state for a specific satellite.

        Args:
            satellite_id: Unique satellite identifier (e.g., "sat_ICEYE-X44")

        Returns:
            Tuple of (roll, pitch) in degrees
        """
        if satellite_id not in self._satellite_attitudes:
            self._satellite_attitudes[satellite_id] = {"roll": 0.0, "pitch": 0.0}
        attitude = self._satellite_attitudes[satellite_id]
        return attitude["roll"], attitude["pitch"]

    def update_satellite_attitude(
        self, satellite_id: str, roll: float, pitch: float
    ) -> None:
        """
        Update attitude state for a specific satellite.

        Args:
            satellite_id: Unique satellite identifier
            roll: New roll angle in degrees
            pitch: New pitch angle in degrees
        """
        self._satellite_attitudes[satellite_id] = {"roll": roll, "pitch": pitch}

        # Also update legacy fields for backward compatibility
        self.current_roll = roll
        self.current_pitch = pitch

    def reset_all_attitudes(self) -> None:
        """Reset attitude state for all satellites (start of new scheduling run)."""
        self._satellite_attitudes.clear()
        self.current_roll = 0.0
        self.current_pitch = 0.0

    def compute_maneuver_time(
        self, delta_roll: float, delta_pitch: float = 0.0
    ) -> float:
        """
        Compute minimum time required for a roll/pitch maneuver.

        Uses trapezoidal velocity profile with acceleration/deceleration phases.

        Args:
            delta_roll: Roll angle change in degrees
            delta_pitch: Pitch angle change in degrees (future)

        Returns:
            Maneuver time in seconds
        """
        # Compute roll and pitch maneuver times independently
        # Total time = MAX(roll_time, pitch_time) since they can happen simultaneously

        # Roll parameters
        max_roll_rate = self.config.max_roll_rate_dps
        max_roll_accel = self.config.max_roll_accel_dps2

        # Compute roll maneuver time
        if abs(delta_roll) > 0:
            t_accel = max_roll_rate / max_roll_accel
            d_accel = 0.5 * max_roll_accel * t_accel * t_accel
            d_total_accel = 2 * d_accel

            if abs(delta_roll) <= d_total_accel:
                roll_time = 2 * math.sqrt(abs(delta_roll) / max_roll_accel)
            else:
                d_cruise = abs(delta_roll) - d_total_accel
                t_cruise = d_cruise / max_roll_rate
                roll_time = 2 * t_accel + t_cruise
        else:
            roll_time = 0.0

        # Pitch parameters (use dedicated pitch agility if configured, otherwise use roll parameters)
        max_pitch_rate = (
            self.config.max_pitch_rate_dps
            if self.config.max_pitch_rate_dps > 0
            else max_roll_rate
        )
        max_pitch_accel = (
            self.config.max_pitch_accel_dps2
            if self.config.max_pitch_accel_dps2 > 0
            else max_roll_accel
        )

        # Compute pitch maneuver time
        if abs(delta_pitch) > 0:
            t_accel = max_pitch_rate / max_pitch_accel
            d_accel = 0.5 * max_pitch_accel * t_accel * t_accel
            d_total_accel = 2 * d_accel

            if abs(delta_pitch) <= d_total_accel:
                pitch_time = 2 * math.sqrt(abs(delta_pitch) / max_pitch_accel)
            else:
                d_cruise = abs(delta_pitch) - d_total_accel
                t_cruise = d_cruise / max_pitch_rate
                pitch_time = 2 * t_accel + t_cruise
        else:
            pitch_time = 0.0

        # Total maneuver time is MAX (simultaneous axes)
        t_maneuver = max(roll_time, pitch_time)

        return t_maneuver

    def compute_roll_angle_from_satellite(
        self,
        target_position: Tuple[float, float],
        satellite_position: Tuple[float, float, float],
        satellite_altitude_km: Optional[float] = None,
    ) -> float:
        """
        Compute roll angle to target from satellite's perspective using proper geometry.

        Uses Law of Sines from satellite perspective (not Earth center):
        β = arcsin((R_Earth + H) / R_Earth × sin(α)) - α

        Where:
        - α is the angular distance from Earth center (Haversine)
        - β is the actual roll angle from satellite
        - H is satellite altitude
        - R_Earth is Earth radius

        Args:
            target_position: (lat, lon) in degrees
            satellite_position: (sat_lat, sat_lon, sat_alt_km)
            satellite_altitude_km: Override altitude (if not using satellite_position[2])

        Returns:
            Roll angle in degrees from nadir to target
        """
        sat_lat, sat_lon, sat_alt = satellite_position
        target_lat, target_lon = target_position

        # Use provided altitude or from satellite position
        H = satellite_altitude_km if satellite_altitude_km is not None else sat_alt

        # Compute angular distance from Earth center (Haversine formula)
        lat1_rad = math.radians(sat_lat)
        lat2_rad = math.radians(target_lat)
        dlon_rad = math.radians(target_lon - sat_lon)

        a = (
            math.sin((lat2_rad - lat1_rad) / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon_rad / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(min(a, 1.0)))  # Clamp for numerical stability
        alpha_rad = c  # Angular distance from Earth center

        # Apply correct geometry from satellite perspective (Law of Sines)
        # β = arcsin((R_Earth + H) / R_Earth × sin(α)) - α
        ratio = (self.R_EARTH + H) / self.R_EARTH
        sin_beta_plus_alpha = ratio * math.sin(alpha_rad)

        # Clamp for numerical stability
        sin_beta_plus_alpha = min(sin_beta_plus_alpha, 1.0)

        beta_plus_alpha = math.asin(sin_beta_plus_alpha)
        beta_rad = beta_plus_alpha - alpha_rad

        roll_angle_deg = math.degrees(beta_rad)

        return abs(roll_angle_deg)  # Return absolute value

    def compute_roll_pitch_from_satellite(
        self,
        target_position: Tuple[float, float],
        satellite_position: Tuple[float, float, float],
        satellite_altitude_km: float,
        timestamp: datetime,
    ) -> Tuple[float, float]:
        """
        Compute roll and pitch angles to target using velocity-aware decomposition.

        Strategy: Pitch is ONLY used if roll alone cannot reach the target.
        1. Decompose target vector into cross-track (roll) and along-track (pitch)
        2. If target reachable with roll-only → use roll, pitch=0
        3. If target needs along-track component → use roll+pitch

        Args:
            target_position: (lat, lon) in degrees
            satellite_position: (sat_lat, sat_lon, sat_alt_km)
            satellite_altitude_km: Satellite altitude in km
            timestamp: Current time (for velocity calculation)

        Returns:
            Tuple of (roll_angle, pitch_angle) in degrees
        """
        sat_lat, sat_lon, sat_alt = satellite_position
        target_lat, target_lon = target_position

        # Get satellite velocity vector by computing position at t+1 second
        if self.satellite is not None:
            try:
                sat_pos_future = self.satellite.get_position(
                    timestamp + timedelta(seconds=1)
                )
                sat_lat_future, sat_lon_future, _ = sat_pos_future
            except Exception:
                # Fallback: assume north-south velocity
                sat_lat_future = sat_lat + 0.01
                sat_lon_future = sat_lon
        else:
            # Fallback: assume north-south velocity
            sat_lat_future = sat_lat + 0.01
            sat_lon_future = sat_lon

        # Velocity vector (approximate, in degrees/second)
        vel_lat = sat_lat_future - sat_lat
        vel_lon = sat_lon_future - sat_lon

        # Normalize velocity vector
        vel_mag = math.sqrt(vel_lat**2 + vel_lon**2)
        if vel_mag > 0:
            vel_lat_norm = vel_lat / vel_mag
            vel_lon_norm = vel_lon / vel_mag
        else:
            # Fallback: assume northward velocity
            vel_lat_norm = 1.0
            vel_lon_norm = 0.0

        # Vector from satellite to target (in degrees)
        target_vec_lat = target_lat - sat_lat
        target_vec_lon = target_lon - sat_lon

        # Decompose into along-track and cross-track components
        # Along-track: component parallel to velocity
        along_track = target_vec_lat * vel_lat_norm + target_vec_lon * vel_lon_norm

        # Cross-track: component perpendicular to velocity
        # Use perpendicular vector: (-vel_lon_norm, vel_lat_norm)
        cross_track = target_vec_lat * (-vel_lon_norm) + target_vec_lon * vel_lat_norm

        # Convert angular distances to actual angles from satellite
        # For cross-track (roll)
        if abs(cross_track) > 1e-6:
            # Compute using Law of Sines
            cross_track_rad = math.radians(abs(cross_track))
            ratio = (self.R_EARTH + satellite_altitude_km) / self.R_EARTH
            sin_roll_plus_cross = ratio * math.sin(cross_track_rad)
            sin_roll_plus_cross = min(sin_roll_plus_cross, 1.0)
            roll_plus_cross = math.asin(sin_roll_plus_cross)
            roll_angle = math.degrees(roll_plus_cross - cross_track_rad)
        else:
            roll_angle = 0.0

        # For along-track (pitch)
        # STRATEGY: Only use pitch if necessary
        # If along-track component is small relative to cross-track, ignore it (pitch=0)
        # PITCH_THRESHOLD_DEG defined at module level

        if abs(along_track) > PITCH_THRESHOLD_DEG:
            # Target has significant along-track component
            # Compute pitch angle using same Law of Sines approach
            along_track_rad = math.radians(abs(along_track))
            sin_pitch_plus_along = ratio * math.sin(along_track_rad)
            sin_pitch_plus_along = min(sin_pitch_plus_along, 1.0)
            pitch_plus_along = math.asin(sin_pitch_plus_along)
            pitch_angle = math.degrees(pitch_plus_along - along_track_rad)

            logger.info(
                f"Using pitch: along-track={along_track:.2f}° → pitch={pitch_angle:.2f}° "
                f"(cross-track={cross_track:.2f}° → roll={roll_angle:.2f}°)"
            )
        else:
            # Target reachable with roll-only
            pitch_angle = 0.0
            logger.debug(
                f"Roll-only sufficient: cross-track={cross_track:.2f}° → roll={roll_angle:.2f}° "
                f"(along-track={along_track:.2f}° ignored)"
            )

        return abs(roll_angle), abs(pitch_angle)

    def compute_target_roll_pitch(
        self,
        target_id: str,
        target_positions: Dict[str, Tuple[float, float]],
        timestamp: datetime,
        satellite_altitude_km: Optional[float] = None,
    ) -> Tuple[float, float]:
        """
        Compute absolute roll and pitch angles required to point at target.

        Args:
            target_id: Target identifier
            target_positions: Dict mapping target_id to (lat, lon)
            timestamp: Time of imaging opportunity
            satellite_altitude_km: Override altitude (if not using satellite TLE)

        Returns:
            Tuple of (roll_angle, pitch_angle) in degrees from nadir
        """
        target_pos = target_positions.get(target_id)
        if target_pos is None:
            logger.warning(f"Missing position data for target {target_id}")
            return 0.0, 0.0

        # Get satellite position at this time
        if self.satellite is not None:
            try:
                sat_pos = self.satellite.get_position(timestamp)
                actual_altitude = sat_pos[2]
                logger.debug(
                    f"Using actual satellite altitude from TLE: {actual_altitude:.1f} km at {timestamp}"
                )
            except Exception as e:
                logger.warning(f"Could not get satellite position from TLE: {e}")
                if satellite_altitude_km is not None:
                    sat_pos = (0, 0, satellite_altitude_km)  # Fallback
                    actual_altitude = satellite_altitude_km
                else:
                    logger.error("No satellite altitude available!")
                    return 0.0, 0.0
        else:
            # No satellite object - use override or error
            if satellite_altitude_km is not None:
                sat_pos = (0, 0, satellite_altitude_km)
                actual_altitude = satellite_altitude_km
                logger.warning(
                    f"Using provided altitude (no satellite object): {actual_altitude:.1f} km"
                )
            else:
                logger.error("No satellite object and no altitude override provided!")
                return 0.0, 0.0

        # NOTE: For imaging missions, roll angle should equal the incidence angle
        # which is computed during visibility analysis at the optimal imaging moment.
        # Computing it here at the imaging time would give wrong results (satellite is overhead).
        # The incidence angle will be passed through from the Opportunity object.
        # For now, return 0 as placeholder - actual angle comes from opportunity.incidence_angle
        roll_angle = 0.0
        pitch_angle = 0.0

        logger.debug(
            f"Target {target_id}: roll={roll_angle:.2f}°, pitch={pitch_angle:.2f}° "
            f"(altitude={actual_altitude:.1f}km)"
        )

        return roll_angle, pitch_angle

    def compute_delta_roll(
        self,
        last_target_id: Optional[str],
        next_target_id: str,
        target_positions: Dict[str, Tuple[float, float]],
        next_timestamp: datetime,
        satellite_altitude_km: Optional[float] = None,
    ) -> Tuple[float, float, float, float]:
        """
        Compute roll angle change and absolute angles between targets.

        This uses production-ready satellite geometry, not simplified approximations.
        Tracks persistent attitude state across passes.

        Args:
            last_target_id: Previous target (None if first)
            next_target_id: Next target
            target_positions: Dict mapping target_id to (lat, lon) in degrees
            next_timestamp: Time of next imaging opportunity (for satellite position)
            satellite_altitude_km: Override altitude (only if satellite object not available)

        Returns:
            Tuple of (delta_roll, delta_pitch, new_roll_angle, new_pitch_angle)
        """
        # Compute absolute roll/pitch for next target
        next_roll, next_pitch = self.compute_target_roll_pitch(
            next_target_id, target_positions, next_timestamp, satellite_altitude_km
        )

        if last_target_id is None:
            # First opportunity - transition from nadir (0, 0)
            delta_roll = next_roll - self.current_roll
            delta_pitch = next_pitch - self.current_pitch
            logger.info(
                f"[ATTITUDE] First target {next_target_id}: "
                f"from ({self.current_roll:.2f}°, {self.current_pitch:.2f}°) -> "
                f"to ({next_roll:.2f}°, {next_pitch:.2f}°), delta=({delta_roll:.2f}°, {delta_pitch:.2f}°)"
            )
        elif last_target_id == next_target_id:
            # Same target - no change
            delta_roll = 0.0
            delta_pitch = 0.0
            logger.info(f"[ATTITUDE] Same target {next_target_id}, no attitude change")
        else:
            # Compute delta from current attitude
            delta_roll = next_roll - self.current_roll
            delta_pitch = next_pitch - self.current_pitch

            target_pos = target_positions.get(next_target_id)
            last_pos = target_positions.get(last_target_id)
            last_lat = last_pos[0] if last_pos else 0.0
            last_lon = last_pos[1] if last_pos else 0.0
            target_lat = target_pos[0] if target_pos else 0.0
            target_lon = target_pos[1] if target_pos else 0.0
            logger.info(
                f"[ATTITUDE] {last_target_id}({last_lat:.2f}, {last_lon:.2f}) -> "
                f"{next_target_id}({target_lat:.2f}, {target_lon:.2f}): "
                f"from ({self.current_roll:.2f}°, {self.current_pitch:.2f}°) -> "
                f"to ({next_roll:.2f}°, {next_pitch:.2f}°), delta=({delta_roll:.2f}°, {delta_pitch:.2f}°)"
            )

        # Update current attitude (persistent across passes)
        self.current_roll = next_roll
        self.current_pitch = next_pitch

        return abs(delta_roll), abs(delta_pitch), next_roll, next_pitch

    def is_feasible(
        self,
        last_opportunity: Optional[ScheduledOpportunity],
        candidate: Opportunity,
        target_positions: Dict[str, Tuple[float, float]],
    ) -> Tuple[bool, float, float, float, float, float, float]:
        """
        Check if candidate opportunity is feasible after last scheduled.

        Args:
            last_opportunity: Last scheduled opportunity (None if first)
            candidate: Candidate opportunity to check
            target_positions: Dict mapping target_id to (lat, lon)

        Returns:
            Tuple of (is_feasible, maneuver_time, slack_time, delta_roll, delta_pitch, roll_angle, pitch_angle)
        """
        # For imaging missions, use incidence_angle from opportunity (computed during visibility)
        # This is the actual off-nadir angle needed to image the target
        roll_angle = (
            candidate.incidence_angle if candidate.incidence_angle is not None else 0.0
        )
        pitch_angle = 0.0  # For now, all pointing is roll (cross-track)

        # Compute delta from previous attitude
        if last_opportunity is None:
            # First opportunity - transition from nadir
            delta_roll = roll_angle
            delta_pitch = 0.0
        else:
            # Delta from previous opportunity's attitude
            delta_roll = roll_angle - last_opportunity.roll_angle
            delta_pitch = pitch_angle - last_opportunity.pitch_angle

        # DO NOT update self.current_roll here! State updates happen when scheduling, not checking feasibility

        # Check spacecraft roll limit for ALL opportunities (including first)
        # NOTE: roll_angle is SIGNED (right-hand rule), so check absolute value against limit
        if abs(roll_angle) > self.config.max_spacecraft_roll_deg:
            logger.debug(
                f"Opportunity {candidate.id} rejected: "
                f"absolute roll {abs(roll_angle):.1f}° exceeds spacecraft limit {self.config.max_spacecraft_roll_deg:.1f}°"
            )
            return False, 0.0, float("-inf"), 0.0, 0.0, 0.0, 0.0

        # First opportunity - compute maneuver time from nadir, but no slack constraint
        if last_opportunity is None:
            # Satellite must slew from nadir (0°, 0°) to first target
            maneuver_time = self.compute_maneuver_time(
                abs(delta_roll), abs(delta_pitch)
            )
            slack = 0.0  # No time constraint for first opportunity
            return (
                True,
                maneuver_time,
                slack,
                abs(delta_roll),
                abs(delta_pitch),
                roll_angle,
                pitch_angle,
            )

        # Compute required maneuver time (both roll and pitch)
        maneuver_time = self.compute_maneuver_time(abs(delta_roll), abs(delta_pitch))

        # Available time window
        # = time between (last_end + imaging_time) and candidate_start
        available_time = (
            candidate.start_time
            - (
                last_opportunity.end_time
                + timedelta(seconds=self.config.imaging_time_s)
            )
        ).total_seconds()

        # Slack time
        slack = available_time - maneuver_time

        # Feasible if slack >= 0
        is_feasible = slack >= 0

        return (
            is_feasible,
            maneuver_time,
            slack,
            abs(delta_roll),
            abs(delta_pitch),
            roll_angle,
            pitch_angle,
        )

    def is_feasible_2d(
        self,
        last_opportunity: Optional[ScheduledOpportunity],
        candidate: Opportunity,
        target_positions: Dict[str, Tuple[float, float]],
    ) -> Tuple[bool, float, float, float, float, float, float]:
        """
        Check if candidate opportunity is feasible using 2D slew (roll + pitch).

        Uses angles from the opportunity:
        - incidence_angle: Roll (cross-track) pointing angle
        - pitch_angle: Pitch (along-track) pointing angle for early/late imaging

        Args:
            last_opportunity: Last scheduled opportunity (None if first)
            candidate: Opportunity to check
            target_positions: Dict mapping target_id to (lat, lon)

        Returns:
            Tuple of (is_feasible, maneuver_time, slack_time, delta_roll, delta_pitch, roll_angle, pitch_angle)
        """
        # Use incidence_angle from opportunity (computed during visibility analysis)
        roll_angle = (
            candidate.incidence_angle if candidate.incidence_angle is not None else 0.0
        )

        # Use pitch_angle from opportunity (for early/late imaging in pass window)
        # negative = backward looking (early in pass), positive = forward looking (late in pass)
        pitch_angle = (
            candidate.pitch_angle if candidate.pitch_angle is not None else 0.0
        )

        # Log the angles being used
        logger.debug(
            f"[2D FEASIBILITY] Candidate {candidate.target_id}: "
            f"roll={roll_angle:.2f}°, pitch={pitch_angle:.2f}° "
            f"(from opportunity: incidence={candidate.incidence_angle}, pitch={candidate.pitch_angle})"
        )

        # Compute delta from previous attitude
        if last_opportunity is None:
            # First opportunity - transition from nadir (0, 0)
            delta_roll = roll_angle
            delta_pitch = pitch_angle
        else:
            # Delta from previous opportunity's attitude
            delta_roll = roll_angle - last_opportunity.roll_angle
            delta_pitch = pitch_angle - last_opportunity.pitch_angle

        # Check spacecraft roll limit
        if abs(roll_angle) > self.config.max_spacecraft_roll_deg:
            logger.debug(
                f"Opportunity {candidate.id} rejected: "
                f"absolute roll {abs(roll_angle):.1f}° exceeds spacecraft limit {self.config.max_spacecraft_roll_deg:.1f}°"
            )
            return False, 0.0, float("-inf"), 0.0, 0.0, 0.0, 0.0

        # Check spacecraft pitch limit
        if abs(pitch_angle) > self.config.max_spacecraft_pitch_deg:
            logger.debug(
                f"Opportunity {candidate.id} rejected: "
                f"absolute pitch {abs(pitch_angle):.1f}° exceeds spacecraft limit {self.config.max_spacecraft_pitch_deg:.1f}°"
            )
            return False, 0.0, float("-inf"), 0.0, 0.0, 0.0, 0.0

        # First opportunity - compute maneuver time from nadir, but no slack constraint
        if last_opportunity is None:
            maneuver_time = self.compute_maneuver_time(
                abs(delta_roll), abs(delta_pitch)
            )
            slack = 0.0  # No time constraint for first opportunity
            return (
                True,
                maneuver_time,
                slack,
                abs(delta_roll),
                abs(delta_pitch),
                roll_angle,
                pitch_angle,
            )

        # Compute required maneuver time (both roll and pitch)
        maneuver_time = self.compute_maneuver_time(abs(delta_roll), abs(delta_pitch))

        # Available time window
        available_time = (
            candidate.start_time
            - (
                last_opportunity.end_time
                + timedelta(seconds=self.config.imaging_time_s)
            )
        ).total_seconds()

        # Slack time
        slack = available_time - maneuver_time

        # Feasible if slack >= 0
        is_feasible = slack >= 0

        return (
            is_feasible,
            maneuver_time,
            slack,
            abs(delta_roll),
            abs(delta_pitch),
            roll_angle,
            pitch_angle,
        )


class MissionScheduler:
    """
    Mission planning scheduler with multiple greedy algorithms.

    Selects opportunities from visibility analysis results, applying
    satellite agility constraints and optimizing for different objectives.
    """

    def __init__(
        self,
        config: SchedulerConfig,
        satellite: Optional["SatelliteOrbit"] = None,
        satellites: Optional[Dict[str, "SatelliteOrbit"]] = None,
    ):
        """Initialize scheduler with configuration and satellite object(s).

        Args:
            config: Scheduler configuration
            satellite: Primary SatelliteOrbit object (legacy, for single-satellite mode)
            satellites: Dictionary of satellite_id -> SatelliteOrbit for constellation mode
        """
        self.config = config
        self.satellite = satellite  # Legacy: single satellite for position queries
        self.satellites = satellites or {}  # Constellation: keyed by satellite_id
        self.kernel = FeasibilityKernel(config, satellite)

    def _get_satellite_for_opportunity(
        self, satellite_id: str
    ) -> Optional["SatelliteOrbit"]:
        """Get the correct satellite object for an opportunity.

        Args:
            satellite_id: The satellite ID from the opportunity (e.g., 'ICEYE-X57' or 'sat_ICEYE-X57')

        Returns:
            SatelliteOrbit object or None if not found
        """
        # Try exact match first
        if satellite_id in self.satellites:
            return self.satellites[satellite_id]

        # Try with 'sat_' prefix (satellites_dict uses 'sat_ICEYE-X57' but opportunity uses 'ICEYE-X57')
        prefixed_id = f"sat_{satellite_id}"
        if prefixed_id in self.satellites:
            return self.satellites[prefixed_id]

        # Try without 'sat_' prefix (in case opportunity has prefix but dict doesn't)
        if satellite_id.startswith("sat_"):
            unprefixed_id = satellite_id[4:]
            if unprefixed_id in self.satellites:
                return self.satellites[unprefixed_id]

        # Fallback to legacy single satellite
        logger.warning(
            f"Could not find satellite for ID '{satellite_id}' in satellites dict (keys: {list(self.satellites.keys())[:3]}...)"
        )
        return self.satellite

    def schedule(
        self,
        opportunities: List[Opportunity],
        target_positions: Dict[str, Tuple[float, float]],
        algorithm: AlgorithmType = AlgorithmType.FIRST_FIT,
    ) -> Tuple[List[ScheduledOpportunity], ScheduleMetrics]:
        """
        Run scheduling algorithm on opportunities.

        Args:
            opportunities: List of visibility opportunities
            target_positions: Dict mapping target_id to (lat, lon) in degrees
            algorithm: Algorithm to use

        Returns:
            Tuple of (scheduled_opportunities, metrics)
        """
        start_time = time.perf_counter()

        # Sort opportunities chronologically
        sorted_opps = sorted(opportunities, key=lambda o: o.start_time)

        # Dispatch to algorithm
        if algorithm == AlgorithmType.FIRST_FIT:
            schedule = self._first_fit(sorted_opps, target_positions)
        elif algorithm == AlgorithmType.BEST_FIT:
            schedule = self._best_fit(sorted_opps, target_positions)
        elif algorithm == AlgorithmType.ROLL_PITCH_FIRST_FIT:
            schedule = self._roll_pitch_first_fit(sorted_opps, target_positions)
        elif algorithm == AlgorithmType.ROLL_PITCH_BEST_FIT:
            schedule = self._roll_pitch_best_fit(sorted_opps, target_positions)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

        # Note: Algorithms now handle one-per-target internally during scheduling
        # No post-filtering needed - kept for backwards compatibility
        schedule = self._select_best_per_target(schedule, algorithm)

        # Compute metrics
        runtime_ms = (time.perf_counter() - start_time) * 1000
        metrics = self._compute_metrics(
            algorithm.value, opportunities, schedule, runtime_ms
        )

        logger.info(
            f"{algorithm.value}: Accepted {len(schedule)}/{len(opportunities)} opportunities "
            f"(filtered to {len(schedule)} targets) in {runtime_ms:.2f}ms"
        )

        return schedule, metrics

    def _first_fit(
        self,
        opportunities: List[Opportunity],
        target_positions: Dict[str, Tuple[float, float]],
    ) -> List[ScheduledOpportunity]:
        """
        First-Fit (Chronological Greedy) algorithm.

        Iterate opportunities in time order and accept first feasible opportunity per target.
        Skips opportunities for targets that are already covered.
        O(n) complexity after initial sort.

        CONSTELLATION SUPPORT: Each satellite tracks its own attitude state independently.
        """
        schedule = []
        last_scheduled_by_sat: Dict[str, ScheduledOpportunity] = (
            {}
        )  # Per-satellite attitude tracking
        covered_targets = set()  # Track which targets have been scheduled

        for opp in opportunities:
            # Skip if target is already covered
            if opp.target_id in covered_targets:
                continue

            # Get last scheduled for THIS satellite (not others)
            sat_id = opp.satellite_id or "default"
            last_scheduled = last_scheduled_by_sat.get(sat_id)

            (
                is_feasible,
                maneuver_time,
                slack,
                delta_roll,
                delta_pitch,
                roll_angle,
                pitch_angle,
            ) = self.kernel.is_feasible(last_scheduled, opp, target_positions)

            if is_feasible:
                # Determine side indicator for clarity
                side_indicator = "R" if roll_angle >= 0 else "L"

                logger.info(
                    f"[SCHEDULE] Opp {opp.id}: target={opp.target_id}, "
                    f"roll={roll_angle:+.2f}° ({side_indicator}), "
                    f"delta=({delta_roll:.2f}°, {delta_pitch:.2f}°), "
                    f"maneuver={maneuver_time:.2f}s"
                )

                # Compute density
                density = (
                    opp.value / maneuver_time if maneuver_time > 0 else float("inf")
                )

                # Calculate exact imaging time window
                # For imaging missions, opp.start_time IS the optimal imaging time (max_elevation_time)
                # We use this directly instead of calculating from maneuvers
                imaging_start = opp.start_time

                # Imaging ends after imaging_time_s
                imaging_end = imaging_start + timedelta(
                    seconds=self.config.imaging_time_s
                )

                # Get satellite position at START OF SLEW MANEUVER (before imaging)
                # For the initial slew arc, we want the position when the slew begins, not at imaging time
                sat_lat, sat_lon, sat_alt = None, None, None
                sat_obj = self._get_satellite_for_opportunity(opp.satellite_id)
                if sat_obj:
                    try:
                        # Position at start of maneuver (before imaging)
                        maneuver_start_time = imaging_start - timedelta(
                            seconds=maneuver_time
                        )
                        sat_lat, sat_lon, sat_alt = sat_obj.get_position(
                            maneuver_start_time
                        )
                    except Exception as e:
                        logger.warning(
                            f"Could not get satellite position for {opp.id}: {e}"
                        )

                scheduled_opp = ScheduledOpportunity(
                    opportunity_id=opp.id,
                    satellite_id=opp.satellite_id,
                    target_id=opp.target_id,
                    start_time=imaging_start,
                    end_time=imaging_end,
                    delta_roll=delta_roll,
                    delta_pitch=delta_pitch,
                    roll_angle=roll_angle,
                    pitch_angle=pitch_angle,
                    maneuver_time=maneuver_time,
                    slack_time=slack,
                    value=opp.value,
                    density=density,
                    incidence_angle=opp.incidence_angle,
                    satellite_lat=sat_lat,
                    satellite_lon=sat_lon,
                    satellite_alt=sat_alt,
                    # SAR-specific fields (copied from Opportunity)
                    mission_mode=opp.mission_mode,
                    sar_mode=opp.sar_mode,
                    look_side=opp.look_side,
                    pass_direction=opp.pass_direction,
                    incidence_center_deg=opp.incidence_center_deg,
                    swath_width_km=opp.swath_width_km,
                    scene_length_km=opp.scene_length_km,
                )
                schedule.append(scheduled_opp)
                last_scheduled_by_sat[sat_id] = (
                    scheduled_opp  # Update per-satellite state
                )
                covered_targets.add(opp.target_id)  # Mark target as covered

        return schedule

    def _roll_pitch_first_fit(
        self,
        opportunities: List[Opportunity],
        target_positions: Dict[str, Tuple[float, float]],
    ) -> List[ScheduledOpportunity]:
        """
        Roll+Pitch First-Fit: Greedy chronological with 2D slew and dynamic pitch.

        This algorithm extends First-Fit by allowing both cross-track (roll)
        and along-track (pitch) pointing. This enables the satellite to
        "look ahead" or "look behind" along its orbital path.

        DYNAMIC PITCH CAPABILITY (v2.0):
        When imaging windows are enabled (early/max/late opportunities per pass),
        pitch angles are calculated dynamically based on:
        - Satellite orbital velocity (~7.5 km/s)
        - Time offset from max elevation
        - Actual satellite altitude
        - Spacecraft agility constraints

        This creates multiple opportunities per pass:
        - Early: backward looking (pitch < 0, e.g., -15°)
        - Max: overhead (pitch = 0)
        - Late: forward looking (pitch > 0, e.g., +15°)

        PITCH-AS-FALLBACK STRATEGY:
        Smart sorting implements automatic fallback behavior:
        - Sort by: (time, abs(pitch)) - chronological first, prefer pitch=0 for ties
        - For each opportunity:
          * Check 2D feasibility (roll AND pitch constraints)
          * If feasible: accept, else skip
          * Track which targets are already covered (one per target)

        This prefers better imaging geometry (overhead, pitch=0) while using
        pitch when needed to improve coverage in tight-timing scenarios.

        O(n log n) complexity for sorting.
        """
        # Check if pitch is enabled
        if self.config.max_spacecraft_pitch_deg == 0.0:
            logger.warning(
                "Pitch capability disabled (max_spacecraft_pitch_deg=0). "
                "Roll+Pitch algorithm will behave identically to roll-only First-Fit."
            )
        else:
            logger.info(
                f"Roll+Pitch enabled with max_pitch={self.config.max_spacecraft_pitch_deg}°. "
                f"Using pitch for forward/backward looking when needed."
            )

        # Smart sorting: chronological first, then prefer lower pitch as tiebreaker
        # This naturally prefers pitch=0 when times are close, but allows pitch≠0 when needed
        opportunities_sorted = sorted(
            opportunities,
            key=lambda opp: (
                opp.start_time,  # Primary: chronological order
                (
                    abs(opp.pitch_angle) if opp.pitch_angle is not None else 0.0
                ),  # Secondary: prefer pitch=0
            ),
        )

        logger.debug(
            f"[ROLL+PITCH] Sorted {len(opportunities_sorted)} opportunities "
            f"(chronological, prefer pitch=0 for ties)"
        )

        schedule = []
        last_scheduled_by_sat: Dict[str, ScheduledOpportunity] = (
            {}
        )  # Per-satellite attitude tracking
        covered_targets = set()  # Track which targets have been scheduled

        # Track pitch usage for metrics
        opportunities_saved_by_pitch = 0

        for opp in opportunities_sorted:
            # Skip if target is already covered
            if opp.target_id in covered_targets:
                continue

            # Get last scheduled for THIS satellite (not others)
            sat_id = opp.satellite_id or "default"
            last_scheduled = last_scheduled_by_sat.get(sat_id)

            # Use 2D feasibility check (roll + pitch)
            (
                is_feasible,
                maneuver_time,
                slack,
                delta_roll,
                delta_pitch,
                roll_angle,
                pitch_angle,
            ) = self.kernel.is_feasible_2d(last_scheduled, opp, target_positions)

            if is_feasible:
                # NOTE: For imaging at max elevation, pitch_angle will always be 0
                # Future enhancement: check if pitch saved opportunities when imaging windows are supported

                # Determine side indicator for clarity
                side_indicator = "R" if roll_angle >= 0 else "L"
                pitch_indicator = "F" if pitch_angle >= 0 else "B"  # Forward/Backward

                incidence = (
                    abs(opp.incidence_angle) if opp.incidence_angle is not None else 0.0
                )
                logger.info(
                    f"[SCHEDULE] Opp {opp.id}: target={opp.target_id}, "
                    f"incidence={incidence:.2f}°, "
                    f"roll={roll_angle:+.2f}° ({side_indicator}), pitch={pitch_angle:+.2f}° ({pitch_indicator}), "
                    f"delta=({delta_roll:.2f}°, {delta_pitch:.2f}°), "
                    f"maneuver={maneuver_time:.2f}s, slack={slack:.1f}s"
                )

                # Compute density
                density = (
                    opp.value / maneuver_time if maneuver_time > 0 else float("inf")
                )

                # Calculate exact imaging time window
                imaging_start = opp.start_time
                imaging_end = imaging_start + timedelta(
                    seconds=self.config.imaging_time_s
                )

                # Get satellite position at START OF SLEW MANEUVER
                sat_lat, sat_lon, sat_alt = None, None, None
                sat_obj = self._get_satellite_for_opportunity(opp.satellite_id)
                if sat_obj:
                    try:
                        maneuver_start_time = imaging_start - timedelta(
                            seconds=maneuver_time
                        )
                        sat_lat, sat_lon, sat_alt = sat_obj.get_position(
                            maneuver_start_time
                        )
                    except Exception as e:
                        logger.warning(
                            f"Could not get satellite position for {opp.id}: {e}"
                        )

                scheduled_opp = ScheduledOpportunity(
                    opportunity_id=opp.id,
                    satellite_id=opp.satellite_id,
                    target_id=opp.target_id,
                    start_time=imaging_start,
                    end_time=imaging_end,
                    delta_roll=delta_roll,
                    delta_pitch=delta_pitch,
                    roll_angle=roll_angle,
                    pitch_angle=pitch_angle,
                    maneuver_time=maneuver_time,
                    slack_time=slack,
                    value=opp.value,
                    density=density,
                    incidence_angle=opp.incidence_angle,
                    satellite_lat=sat_lat,
                    satellite_lon=sat_lon,
                    satellite_alt=sat_alt,
                    # SAR-specific fields (copied from Opportunity)
                    mission_mode=opp.mission_mode,
                    sar_mode=opp.sar_mode,
                    look_side=opp.look_side,
                    pass_direction=opp.pass_direction,
                    incidence_center_deg=opp.incidence_center_deg,
                    swath_width_km=opp.swath_width_km,
                    scene_length_km=opp.scene_length_km,
                )
                schedule.append(scheduled_opp)
                last_scheduled_by_sat[sat_id] = (
                    scheduled_opp  # Update per-satellite state
                )
                covered_targets.add(opp.target_id)  # Mark target as covered

        # Summary with pitch vs roll-only breakdownt for metrics
        if hasattr(self, "_pitch_opportunities_saved"):
            self._pitch_opportunities_saved = opportunities_saved_by_pitch
        else:
            self._pitch_opportunities_saved = opportunities_saved_by_pitch

        logger.info(
            f"[ROLL+PITCH] Opportunities saved by pitch: {opportunities_saved_by_pitch}"
        )

        return schedule

    def _roll_pitch_best_fit(
        self,
        opportunities: List[Opportunity],
        target_positions: Dict[str, Tuple[float, float]],
    ) -> List[ScheduledOpportunity]:
        """
        Roll+Pitch Best-Fit (Value-Priority, Minimal Pitch) algorithm.

        Strategy:
        1. Sort ALL opportunities by pitch (prefer 0) then by VALUE (highest first)
        2. Greedily schedule - roll-only opportunities are tried first due to sorting
        3. Within each pitch level, highest value opportunities are preferred
        4. If roll-only conflicts, the algorithm naturally falls back to minimal pitch

        Value is computed as: value = (1-w) × priority + w × quality_score
        Where:
        - priority: Target importance (1-5)
        - quality_score: Geometry quality from incidence angle (0-1)
        - w: quality_weight parameter (0=priority only, 1=quality only)

        This is DIFFERENT from roll_pitch_first_fit:
        - first_fit: Takes first CHRONOLOGICAL opportunity, uses pitch aggressively
        - best_fit: Takes highest VALUE opportunity with minimal pitch

        Both aim for 100% coverage, but best_fit optimizes value while minimizing pitch.

        O(n² log n) complexity.
        """

        if self.config.max_spacecraft_pitch_deg == 0.0:
            logger.warning(
                "Pitch capability disabled. Roll+Pitch Best-Fit will behave like Best-Fit."
            )
            return self._best_fit(opportunities, target_positions)

        logger.info(
            f"[roll_pitch_best_fit] Strategy: VALUE priority with minimal pitch. "
            f"Max pitch={self.config.max_spacecraft_pitch_deg}°"
        )

        # Sort ALL opportunities by: pitch (prefer 0), then by VALUE (highest first)
        # This ensures roll-only opportunities are tried first, AND picks highest value among them
        sorted_opps = sorted(
            opportunities,
            key=lambda opp: (
                abs(opp.pitch_angle or 0),
                -opp.value,
            ),  # Pitch first, then highest value
        )

        roll_only_count = sum(
            1 for opp in opportunities if abs(opp.pitch_angle or 0) < 1.0
        )
        logger.info(
            f"[roll_pitch_best_fit] {len(sorted_opps)} opportunities ({roll_only_count} roll-only)"
        )

        # Show top opportunities with value breakdown
        for i, opp in enumerate(sorted_opps[:5]):
            inc = abs(opp.incidence_angle) if opp.incidence_angle else 90.0
            pitch = abs(opp.pitch_angle) if opp.pitch_angle else 0.0
            logger.info(
                f"[roll_pitch_best_fit] Top {i+1}: {opp.target_id} value={opp.value:.3f} pitch={pitch:.1f}° inc={inc:.1f}°"
            )

        schedule = []
        scheduled_targets = set()
        # Per-satellite schedule tracking for constellation support
        scheduled_items_by_sat: Dict[
            str, List[Tuple[datetime, datetime, ScheduledOpportunity]]
        ] = {}

        for opp in sorted_opps:
            if opp.target_id in scheduled_targets:
                continue

            opp_start = opp.start_time
            opp_end = opp_start + timedelta(seconds=self.config.imaging_time_s)
            opp_pitch = abs(opp.pitch_angle or 0)

            # Get satellite-specific schedule items
            sat_id = opp.satellite_id or "default"
            scheduled_items = scheduled_items_by_sat.get(sat_id, [])

            # Check for conflicts with already scheduled FOR THIS SATELLITE
            conflicts = False
            for sched_start, sched_end, sched_item in scheduled_items:
                if opp_start > sched_end:
                    gap = (opp_start - sched_end).total_seconds()
                    roll_diff = abs(
                        abs(opp.incidence_angle or 0)
                        - abs(sched_item.incidence_angle or 0)
                    )
                    pitch_diff = abs(opp_pitch - abs(sched_item.pitch_angle or 0))
                    roll_time = (
                        roll_diff / self.config.max_roll_rate_dps
                        if self.config.max_roll_rate_dps > 0
                        else 0
                    )
                    pitch_time = (
                        pitch_diff / self.config.max_pitch_rate_dps
                        if self.config.max_pitch_rate_dps > 0
                        else 0
                    )
                    min_gap = max(MIN_GAP_SECONDS, roll_time, pitch_time)
                    if gap < min_gap:
                        conflicts = True
                        break
                elif opp_end < sched_start:
                    gap = (sched_start - opp_end).total_seconds()
                    roll_diff = abs(
                        abs(opp.incidence_angle or 0)
                        - abs(sched_item.incidence_angle or 0)
                    )
                    pitch_diff = abs(opp_pitch - abs(sched_item.pitch_angle or 0))
                    roll_time = (
                        roll_diff / self.config.max_roll_rate_dps
                        if self.config.max_roll_rate_dps > 0
                        else 0
                    )
                    pitch_time = (
                        pitch_diff / self.config.max_pitch_rate_dps
                        if self.config.max_pitch_rate_dps > 0
                        else 0
                    )
                    min_gap = max(MIN_GAP_SECONDS, roll_time, pitch_time)
                    if gap < min_gap:
                        conflicts = True
                        break
                else:
                    conflicts = True
                    break

            if conflicts:
                continue

            # Find previous scheduled for feasibility check
            prev_scheduled = None
            for sched_start, sched_end, sched_item in sorted(
                scheduled_items, key=lambda x: x[0]
            ):
                if sched_start < opp_start:
                    prev_scheduled = sched_item

            # Use 2D feasibility check
            (
                is_feasible,
                maneuver_time,
                slack,
                delta_roll,
                delta_pitch,
                roll_angle,
                pitch_angle,
            ) = self.kernel.is_feasible_2d(prev_scheduled, opp, target_positions)

            if not is_feasible:
                continue

            # Schedule it!
            scheduled_targets.add(opp.target_id)

            density = opp.value / maneuver_time if maneuver_time > 0 else float("inf")
            imaging_start = opp.start_time
            imaging_end = imaging_start + timedelta(seconds=self.config.imaging_time_s)

            sat_lat, sat_lon, sat_alt = None, None, None
            sat_obj = self._get_satellite_for_opportunity(opp.satellite_id)
            if sat_obj:
                try:
                    sat_lat, sat_lon, sat_alt = sat_obj.get_position(
                        imaging_start - timedelta(seconds=maneuver_time)
                    )
                except Exception:
                    pass

            scheduled_opp = ScheduledOpportunity(
                opportunity_id=opp.id,
                satellite_id=opp.satellite_id,
                target_id=opp.target_id,
                start_time=imaging_start,
                end_time=imaging_end,
                delta_roll=delta_roll,
                delta_pitch=delta_pitch,
                roll_angle=roll_angle,
                pitch_angle=pitch_angle,
                maneuver_time=maneuver_time,
                slack_time=slack,
                value=opp.value,
                density=density,
                incidence_angle=opp.incidence_angle,
                satellite_lat=sat_lat,
                satellite_lon=sat_lon,
                satellite_alt=sat_alt,
                # SAR-specific fields (copied from Opportunity)
                mission_mode=opp.mission_mode,
                sar_mode=opp.sar_mode,
                look_side=opp.look_side,
                pass_direction=opp.pass_direction,
                incidence_center_deg=opp.incidence_center_deg,
                swath_width_km=opp.swath_width_km,
                scene_length_km=opp.scene_length_km,
            )
            schedule.append(scheduled_opp)
            # Update per-satellite schedule items
            if sat_id not in scheduled_items_by_sat:
                scheduled_items_by_sat[sat_id] = []
            scheduled_items_by_sat[sat_id].append((opp_start, opp_end, scheduled_opp))

            # Check if this is truly roll-only (no pitch maneuver needed)
            # Roll-only means: target pitch is ~0 AND delta_pitch is small (no pitch reset needed)
            is_roll_only = (
                opp_pitch < ROLL_ONLY_PITCH_THRESHOLD_DEG
                and abs(delta_pitch) < DELTA_PITCH_THRESHOLD_DEG
            )
            if is_roll_only:
                pitch_str = "ROLL-ONLY"
            else:
                pitch_str = f"pitch={pitch_angle:+.1f}° (Δpitch={delta_pitch:.1f}°)"
            logger.info(
                f"[roll_pitch_best_fit] ✅ {opp.target_id}: value={opp.value:.3f} {pitch_str} inc={abs(opp.incidence_angle or 0):.1f}°"
            )

        # Sort schedule chronologically
        schedule.sort(key=lambda x: x.start_time)

        # CRITICAL: Recalculate delta_pitch based on chronological order
        # The initial delta was calculated during pitch-first processing, not chronological
        prev_pitch = 0.0
        prev_roll = 0.0
        for s in schedule:
            # Recalculate actual deltas based on chronological sequence
            actual_delta_pitch = abs((s.pitch_angle or 0) - prev_pitch)
            actual_delta_roll = abs((s.roll_angle or 0) - prev_roll)

            # Update the scheduled opportunity with correct deltas
            s.delta_pitch = actual_delta_pitch
            s.delta_roll = actual_delta_roll

            # Recalculate maneuver time based on actual deltas
            # Use pitch rate if configured, otherwise fall back to roll rate (same as compute_maneuver_time)
            roll_rate = (
                self.config.max_roll_rate_dps
                if self.config.max_roll_rate_dps > 0
                else 1.0
            )
            pitch_rate = (
                self.config.max_pitch_rate_dps
                if self.config.max_pitch_rate_dps > 0
                else roll_rate
            )
            s.maneuver_time = max(
                actual_delta_roll / roll_rate, actual_delta_pitch / pitch_rate
            )

            # Recalculate density with corrected maneuver time
            s.density = (
                s.value / s.maneuver_time if s.maneuver_time > 0 else float("inf")
            )

            prev_pitch = s.pitch_angle or 0
            prev_roll = s.roll_angle or 0

        # Summary - count based on delta_pitch (actual pitch maneuver needed)
        roll_only_count = sum(
            1
            for s in schedule
            if abs(s.pitch_angle or 0) < ROLL_ONLY_PITCH_THRESHOLD_DEG
            and abs(s.delta_pitch or 0) < DELTA_PITCH_THRESHOLD_DEG
        )
        pitch_maneuver_count = len(schedule) - roll_only_count
        total_pitch_used = sum(abs(s.delta_pitch or 0) for s in schedule)
        # Calculate total value for summary
        total_scheduled_value = sum(s.value for s in schedule)
        avg_value = total_scheduled_value / len(schedule) if schedule else 0.0
        logger.info(
            f"[roll_pitch_best_fit] Summary: {len(schedule)} targets (value-priority, total={total_scheduled_value:.2f}, avg={avg_value:.3f}, {roll_only_count} roll-only, {pitch_maneuver_count} pitch, Δpitch={total_pitch_used:.1f}°)"
        )

        return schedule

    def _best_fit(
        self,
        opportunities: List[Opportunity],
        target_positions: Dict[str, Tuple[float, float]],
    ) -> List[ScheduledOpportunity]:
        """
        Best-Fit (Value-Priority Greedy) algorithm.

        Strategy:
        1. Sort ALL opportunities by computed value (highest first)
        2. Greedily schedule in value order, checking feasibility
        3. One opportunity per target (first feasible = highest value for that target)

        Value is computed as: value = (1-w) × priority + w × quality_score
        Where:
        - priority: Target importance (1-5)
        - quality_score: Geometry quality from incidence angle (0-1)
        - w: quality_weight parameter (0=priority only, 1=quality only)

        This is DIFFERENT from First-Fit:
        - First-Fit: Chronological order, takes first available for each target
        - Best-Fit: Value order, takes highest value opportunity for each target

        Trade-offs:
        - Pro: Optimizes for user-defined value function (priority + geometry)
        - Pro: Configurable via quality_weight parameter
        - Con: May not schedule chronologically

        O(n log n) complexity.
        """

        # Sort ALL opportunities by VALUE (highest first = descending)
        # Value incorporates both priority and geometry quality based on quality_weight
        sorted_opps = sorted(
            opportunities,
            key=lambda opp: -opp.value,  # Descending order (highest value first)
        )

        logger.info(
            f"[best_fit] Processing {len(sorted_opps)} opportunities sorted by VALUE (highest first)"
        )

        # Show best few opportunities with value breakdown
        for i, opp in enumerate(sorted_opps[:5]):
            inc = abs(opp.incidence_angle) if opp.incidence_angle else 90.0
            logger.info(
                f"[best_fit] Top {i+1}: {opp.target_id} value={opp.value:.3f} inc={inc:.1f}° at {str(opp.start_time)[11:19]}"
            )

        schedule = []
        scheduled_targets = set()

        # Track timing per satellite to ensure valid chronological schedule
        # Dict: satellite_id -> List of (start_time, end_time, ScheduledOpportunity) tuples
        scheduled_items_by_sat: Dict[
            str, List[Tuple[datetime, datetime, ScheduledOpportunity]]
        ] = {}

        for opp in sorted_opps:
            # Skip if target already scheduled
            if opp.target_id in scheduled_targets:
                continue

            incidence = (
                abs(opp.incidence_angle) if opp.incidence_angle is not None else 90.0
            )

            # Get satellite-specific schedule items
            sat_id = opp.satellite_id or "default"
            scheduled_items = scheduled_items_by_sat.get(sat_id, [])

            # Check if this opportunity conflicts with already-scheduled times FOR THIS SATELLITE
            opp_start = opp.start_time
            opp_end = opp_start + timedelta(seconds=self.config.imaging_time_s)

            # Quick feasibility check - does it fit in the timeline?
            conflicts = False
            for sched_start, sched_end, sched_item in scheduled_items:
                # Calculate required gap (maneuver time based on angle change)
                if opp_start > sched_end:
                    # This opp is after scheduled - need time to maneuver FROM scheduled TO this
                    gap = (opp_start - sched_end).total_seconds()
                    angle_diff = abs(
                        abs(opp.incidence_angle or 0)
                        - abs(sched_item.incidence_angle or 0)
                    )
                    min_gap = max(
                        MIN_GAP_SECONDS, angle_diff / self.config.max_roll_rate_dps
                    )
                    if gap < min_gap:
                        conflicts = True
                        break
                elif opp_end < sched_start:
                    # This opp is before scheduled - need time to maneuver FROM this TO scheduled
                    gap = (sched_start - opp_end).total_seconds()
                    angle_diff = abs(
                        abs(opp.incidence_angle or 0)
                        - abs(sched_item.incidence_angle or 0)
                    )
                    min_gap = max(
                        MIN_GAP_SECONDS, angle_diff / self.config.max_roll_rate_dps
                    )
                    if gap < min_gap:
                        conflicts = True
                        break
                else:
                    # Overlapping times
                    conflicts = True
                    break

            if conflicts:
                logger.debug(
                    f"[best_fit] {opp.target_id}: opp at {str(opp_start)[11:19]} inc={incidence:.1f}° CONFLICTS with schedule"
                )
                continue

            # Find the ScheduledOpportunity that would be BEFORE this one chronologically
            prev_scheduled = None
            for sched_start, sched_end, sched_item in sorted(
                scheduled_items, key=lambda x: x[0]
            ):
                if sched_start < opp_start:
                    prev_scheduled = sched_item
                else:
                    break

            # Full feasibility check using kernel
            (
                is_feasible,
                maneuver_time,
                slack,
                delta_roll,
                delta_pitch,
                roll_angle,
                pitch_angle,
            ) = self.kernel.is_feasible(prev_scheduled, opp, target_positions)

            if not is_feasible:
                logger.debug(
                    f"[best_fit] {opp.target_id}: value={opp.value:.3f} inc={incidence:.1f}° at {str(opp_start)[11:19]} INFEASIBLE from kernel"
                )
                continue

            # Schedule this opportunity!
            scheduled_targets.add(opp.target_id)

            logger.info(
                f"[best_fit] ✅ {opp.target_id}: SCHEDULED value={opp.value:.3f} inc={incidence:.1f}° at {str(opp_start)[11:19]}"
            )

            density = opp.value / maneuver_time if maneuver_time > 0 else float("inf")
            imaging_start = opp.start_time
            imaging_end = imaging_start + timedelta(seconds=self.config.imaging_time_s)

            sat_lat, sat_lon, sat_alt = None, None, None
            sat_obj = self._get_satellite_for_opportunity(opp.satellite_id)
            if sat_obj:
                try:
                    maneuver_start_time = imaging_start - timedelta(
                        seconds=maneuver_time
                    )
                    sat_lat, sat_lon, sat_alt = sat_obj.get_position(
                        maneuver_start_time
                    )
                except Exception:
                    pass

            scheduled_opp = ScheduledOpportunity(
                opportunity_id=opp.id,
                satellite_id=opp.satellite_id,
                target_id=opp.target_id,
                start_time=imaging_start,
                end_time=imaging_end,
                delta_roll=delta_roll,
                delta_pitch=delta_pitch,
                roll_angle=roll_angle,
                pitch_angle=pitch_angle,
                maneuver_time=maneuver_time,
                slack_time=slack,
                value=opp.value,
                density=density,
                incidence_angle=opp.incidence_angle,
                satellite_lat=sat_lat,
                satellite_lon=sat_lon,
                satellite_alt=sat_alt,
                # SAR-specific fields (copied from Opportunity)
                mission_mode=opp.mission_mode,
                sar_mode=opp.sar_mode,
                look_side=opp.look_side,
                pass_direction=opp.pass_direction,
                incidence_center_deg=opp.incidence_center_deg,
                swath_width_km=opp.swath_width_km,
                scene_length_km=opp.scene_length_km,
            )
            schedule.append(scheduled_opp)
            # Update per-satellite schedule items
            if sat_id not in scheduled_items_by_sat:
                scheduled_items_by_sat[sat_id] = []
            scheduled_items_by_sat[sat_id].append((opp_start, opp_end, scheduled_opp))

        # Sort schedule chronologically for output
        schedule.sort(key=lambda x: x.start_time)

        # CRITICAL: Recalculate maneuver times based on chronological order PER SATELLITE
        # The initial deltas were calculated during value-priority insertion, not chronological
        roll_rate = (
            self.config.max_roll_rate_dps if self.config.max_roll_rate_dps > 0 else 1.0
        )
        pitch_rate = (
            self.config.max_pitch_rate_dps
            if self.config.max_pitch_rate_dps > 0
            else roll_rate
        )

        # Group by satellite for proper delta calculation
        schedule_by_sat: Dict[str, List[ScheduledOpportunity]] = {}
        for s in schedule:
            sat_id = s.satellite_id or "default"
            if sat_id not in schedule_by_sat:
                schedule_by_sat[sat_id] = []
            schedule_by_sat[sat_id].append(s)

        # Recalculate deltas per satellite
        for sat_id, sat_schedule in schedule_by_sat.items():
            # Sort by time within this satellite
            sat_schedule.sort(key=lambda x: x.start_time)
            prev_roll = 0.0
            prev_pitch = 0.0

            for s in sat_schedule:
                # Recalculate actual deltas based on chronological sequence for THIS satellite
                actual_delta_roll = abs((s.roll_angle or 0) - prev_roll)
                actual_delta_pitch = abs((s.pitch_angle or 0) - prev_pitch)

                # Update the scheduled opportunity with correct deltas
                s.delta_roll = actual_delta_roll
                s.delta_pitch = actual_delta_pitch

                # Recalculate maneuver time based on actual deltas
                s.maneuver_time = max(
                    actual_delta_roll / roll_rate, actual_delta_pitch / pitch_rate
                )

                # Recalculate density with corrected maneuver time
                s.density = (
                    s.value / s.maneuver_time if s.maneuver_time > 0 else float("inf")
                )

                prev_roll = s.roll_angle or 0
                prev_pitch = s.pitch_angle or 0

        # Calculate total value for summary
        total_scheduled_value = sum(s.value for s in schedule)
        avg_value = total_scheduled_value / len(schedule) if schedule else 0.0
        logger.info(
            f"[best_fit] Summary: {len(scheduled_targets)} targets scheduled (value-priority, total={total_scheduled_value:.2f}, avg={avg_value:.3f})"
        )
        return schedule

    def _optimal(
        self,
        opportunities: List[Opportunity],
        target_positions: Dict[str, Tuple[float, float]],
    ) -> List[ScheduledOpportunity]:
        """
        Optimal Integer Linear Programming algorithm.

        Finds the best opportunity for each target to minimize total maneuver time,
        considering pairwise transition costs in chronological order.

        This formulation accounts for sequencing by modeling transitions between
        chronologically adjacent opportunities.
        """
        try:
            from pulp import (  # type: ignore[import-untyped]
                LpMinimize,
                LpProblem,
                LpStatus,
                LpVariable,
                lpSum,
                value,
            )
        except ImportError:
            logger.error("PuLP library not installed. Run: pip install pulp")
            raise ImportError(
                "PuLP is required for optimal scheduling. Install with: pip install pulp"
            )

        # Group opportunities by target
        target_opps: Dict[str, List[Tuple[int, Opportunity]]] = {}
        for i, opp in enumerate(opportunities):
            if opp.target_id not in target_opps:
                target_opps[opp.target_id] = []
            target_opps[opp.target_id].append((i, opp))

        n_targets = len(target_opps)
        n_opps = len(opportunities)
        logger.info(
            f"[optimal] Solving for {n_targets} targets with {n_opps} opportunities..."
        )

        # Sort opportunities chronologically - this is the order they'll be scheduled
        sorted_indices = sorted(
            range(n_opps), key=lambda i: opportunities[i].start_time
        )

        # Compute pairwise transition costs for chronologically adjacent opportunities
        logger.info(f"[optimal] Computing pairwise transition costs...")
        transition_costs: Dict[Tuple[Optional[int], int], float] = {}

        for idx in range(len(sorted_indices)):
            i = sorted_indices[idx]
            opp_i = opportunities[i]

            if idx == 0:
                # First opportunity: cost is maneuver from nadir
                _, man_time, _, _, _, _, _ = self.kernel.is_feasible(
                    None, opp_i, target_positions
                )
                transition_costs[(None, i)] = man_time
            else:
                # Transition from previous opportunity in chronological order
                prev_idx = sorted_indices[idx - 1]
                opp_prev = opportunities[prev_idx]

                # Create temporary scheduled opportunity for previous
                _, man_prev, _, _, _, roll_prev, pitch_prev = self.kernel.is_feasible(
                    None, opp_prev, target_positions
                )
                temp_prev = ScheduledOpportunity(
                    opportunity_id=opp_prev.id,
                    satellite_id=opp_prev.satellite_id,
                    target_id=opp_prev.target_id,
                    start_time=opp_prev.start_time,
                    end_time=opp_prev.end_time,
                    delta_roll=0,
                    delta_pitch=0,
                    roll_angle=roll_prev,
                    pitch_angle=pitch_prev,
                    maneuver_time=man_prev,
                    slack_time=0,
                    value=opp_prev.value,
                    density=0,
                    incidence_angle=opp_prev.incidence_angle,
                )

                # Check feasibility of transition
                is_feas, man_time, _, _, _, _, _ = self.kernel.is_feasible(
                    temp_prev, opp_i, target_positions
                )

                if is_feas:
                    transition_costs[(prev_idx, i)] = man_time
                else:
                    # Infeasible transition - use large penalty
                    transition_costs[(prev_idx, i)] = 1000.0

        # Create ILP problem
        logger.info(f"[optimal] Setting up ILP...")
        prob = LpProblem("Satellite_Scheduling", LpMinimize)

        # Decision variables: x[i] = 1 if opportunity i is selected
        x = {i: LpVariable(f"x_{i}", cat="Binary") for i in range(n_opps)}

        # Build objective: sum of transition costs for selected opportunities
        # For each pair of consecutive opportunities in chronological order,
        # if both are selected, add their transition cost
        objective_terms = []

        # First opportunity cost (from nadir)
        first_idx = sorted_indices[0]
        if (None, first_idx) in transition_costs:
            objective_terms.append(x[first_idx] * transition_costs[(None, first_idx)])

        # Subsequent transition costs
        for idx in range(1, len(sorted_indices)):
            i = sorted_indices[idx]
            prev_idx = sorted_indices[idx - 1]

            if (prev_idx, i) in transition_costs:
                # If both prev and current are selected, add transition cost
                # Use linearization: cost * x[prev] * x[i] ≈ cost * x[i] (assuming most are selected)
                # Better approximation: just use x[i] * cost as a proxy
                objective_terms.append(x[i] * transition_costs[(prev_idx, i)])

        prob += lpSum(objective_terms)

        # Constraint: Exactly one opportunity per target
        for target_id, opps in target_opps.items():
            prob += lpSum([x[i] for i, _ in opps]) == 1, f"one_per_target_{target_id}"

        # Solve
        logger.info(f"[optimal] Solving ILP...")
        prob.solve()

        status = LpStatus[prob.status]
        logger.info(f"[optimal] ILP Status: {status}")

        if status != "Optimal":
            logger.warning(
                f"[optimal] Could not find optimal solution. Using first_fit fallback."
            )
            return self._first_fit(opportunities, target_positions)

        # Extract solution
        selected_indices = [i for i in range(n_opps) if value(x[i]) > 0.5]
        selected_opps = [opportunities[i] for i in selected_indices]

        logger.info(f"[optimal] ILP selected {len(selected_opps)} opportunities")

        # Build schedule chronologically with real feasibility checks
        schedule = []
        last_scheduled = None
        skipped = []

        for opp in sorted(selected_opps, key=lambda o: o.start_time):
            (
                is_feasible,
                maneuver_time,
                slack,
                delta_roll,
                delta_pitch,
                roll_angle,
                pitch_angle,
            ) = self.kernel.is_feasible(last_scheduled, opp, target_positions)

            if is_feasible:
                # Determine side indicator
                side_indicator = "R" if roll_angle >= 0 else "L"
                incidence = (
                    abs(opp.incidence_angle) if opp.incidence_angle is not None else 0.0
                )

                logger.info(
                    f"[SCHEDULE] Opp {opp.id}: target={opp.target_id}, "
                    f"incidence={incidence:.2f}°, "
                    f"roll={roll_angle:+.2f}° ({side_indicator}), "
                    f"delta=({delta_roll:.2f}°, {delta_pitch:.2f}°), "
                    f"maneuver={maneuver_time:.2f}s, slack={slack:.1f}s"
                )

                density = (
                    opp.value / maneuver_time if maneuver_time > 0 else float("inf")
                )
                imaging_start = opp.start_time
                imaging_end = imaging_start + timedelta(
                    seconds=self.config.imaging_time_s
                )

                sat_lat, sat_lon, sat_alt = None, None, None
                sat_obj = self._get_satellite_for_opportunity(opp.satellite_id)
                if sat_obj:
                    try:
                        maneuver_start_time = imaging_start - timedelta(
                            seconds=maneuver_time
                        )
                        sat_lat, sat_lon, sat_alt = sat_obj.get_position(
                            maneuver_start_time
                        )
                    except Exception as e:
                        logger.warning(f"Could not get satellite position: {e}")

                scheduled = ScheduledOpportunity(
                    opportunity_id=opp.id,
                    satellite_id=opp.satellite_id,
                    target_id=opp.target_id,
                    start_time=imaging_start,
                    end_time=imaging_end,
                    delta_roll=delta_roll,
                    delta_pitch=delta_pitch,
                    roll_angle=roll_angle,
                    pitch_angle=pitch_angle,
                    maneuver_time=maneuver_time,
                    slack_time=slack,
                    value=opp.value,
                    density=density,
                    incidence_angle=opp.incidence_angle,
                    satellite_lat=sat_lat,
                    satellite_lon=sat_lon,
                    satellite_alt=sat_alt,
                    # SAR-specific fields (copied from Opportunity)
                    mission_mode=opp.mission_mode,
                    sar_mode=opp.sar_mode,
                    look_side=opp.look_side,
                    pass_direction=opp.pass_direction,
                    incidence_center_deg=opp.incidence_center_deg,
                    swath_width_km=opp.swath_width_km,
                    scene_length_km=opp.scene_length_km,
                )
                schedule.append(scheduled)
                last_scheduled = scheduled
            else:
                skipped.append(opp.target_id)
                logger.warning(
                    f"[optimal] Selected {opp.target_id} is infeasible, skipping"
                )

        if skipped:
            logger.warning(
                f"[optimal] Skipped {len(skipped)} infeasible opportunities: {skipped}"
            )

        total_maneuver = sum(s.maneuver_time for s in schedule)
        logger.info(
            f"[optimal] Built schedule with {len(schedule)}/{n_targets} targets, maneuver: {total_maneuver:.1f}s"
        )
        return schedule

    def _select_best_per_target(
        self, schedule: List[ScheduledOpportunity], algorithm: AlgorithmType
    ) -> List[ScheduledOpportunity]:
        """
        Filter schedule to keep only the best opportunity per target.

        For each target, select one opportunity based on algorithm criteria:
        - First-Fit: Keep first chronological occurrence
        - Best-Fit: Keep highest value opportunity
        - Value-Density: Keep highest density opportunity

        Args:
            schedule: Full schedule with potentially multiple opportunities per target
            algorithm: Algorithm type to determine selection criteria

        Returns:
            Filtered schedule with one opportunity per target
        """
        if not schedule:
            return schedule

        # Group by target
        target_groups: Dict[str, List[ScheduledOpportunity]] = {}
        for opp in schedule:
            if opp.target_id not in target_groups:
                target_groups[opp.target_id] = []
            target_groups[opp.target_id].append(opp)

        # Select best per target based on algorithm
        filtered_schedule = []
        for target_id, opportunities in target_groups.items():
            if len(opportunities) == 1:
                filtered_schedule.append(opportunities[0])
            else:
                # Select based on algorithm criteria
                if algorithm == AlgorithmType.FIRST_FIT:
                    # Keep earliest (already chronological)
                    best = opportunities[0]
                elif algorithm == AlgorithmType.BEST_FIT:
                    # Keep highest value
                    best = max(opportunities, key=lambda o: o.value)
                else:
                    best = opportunities[0]

                filtered_schedule.append(best)

        # Re-sort chronologically
        filtered_schedule.sort(key=lambda o: o.start_time)

        return filtered_schedule

    def _compute_metrics(
        self,
        algorithm_name: str,
        all_opportunities: List[Opportunity],
        schedule: List[ScheduledOpportunity],
        runtime_ms: float,
    ) -> ScheduleMetrics:
        """Compute performance metrics for a schedule."""
        n_evaluated = len(all_opportunities)
        n_accepted = len(schedule)
        n_rejected = n_evaluated - n_accepted

        if not schedule:
            return ScheduleMetrics(
                algorithm=algorithm_name,
                runtime_ms=runtime_ms,
                opportunities_evaluated=n_evaluated,
                opportunities_accepted=0,
                opportunities_rejected=n_rejected,
                total_value=0.0,
                mean_value=0.0,
                total_imaging_time=0.0,
                total_maneuver_time=0.0,
                schedule_span=0.0,
                utilization=0.0,
                mean_density=0.0,
                median_density=0.0,
                seed=None,
            )

        # Value metrics
        total_value = sum(s.value for s in schedule)
        mean_value = total_value / n_accepted

        # Time metrics
        total_imaging_time = sum(
            (s.end_time - s.start_time).total_seconds() for s in schedule
        )
        total_maneuver_time = sum(s.maneuver_time for s in schedule)

        # Schedule span includes first maneuver (satellite starts maneuvering BEFORE first imaging)
        # Actual timeline: [first_maneuver] -> [first_imaging] -> ... -> [last_imaging_end]
        schedule_span = (
            schedule[-1].end_time - schedule[0].start_time
        ).total_seconds() + schedule[0].maneuver_time
        utilization = (
            (total_imaging_time + total_maneuver_time) / schedule_span
            if schedule_span > 0
            else 0.0
        )

        # Density metrics
        finite_densities = [s.density for s in schedule if s.density != float("inf")]
        if finite_densities:
            mean_density = sum(finite_densities) / len(finite_densities)
            sorted_densities = sorted(finite_densities)
            median_density = sorted_densities[len(sorted_densities) // 2]
        else:
            mean_density = float("inf")
            median_density = float("inf")

        # Quality metrics: compute mean incidence angle (use MAGNITUDE for quality)
        # Build opportunity lookup map
        opp_map = {opp.id: opp for opp in all_opportunities}
        incidence_angles = []
        for scheduled in schedule:
            opp = opp_map.get(scheduled.opportunity_id)
            if opp and opp.incidence_angle is not None:
                # Use absolute value for quality metrics (magnitude matters, not direction)
                incidence_angles.append(abs(opp.incidence_angle))

        mean_incidence_deg = (
            sum(incidence_angles) / len(incidence_angles) if incidence_angles else None
        )

        # Pitch metrics (for roll+pitch algorithms)
        total_pitch_used_deg = None
        max_pitch_deg = None
        opportunities_saved_by_pitch = None

        if algorithm_name in ("roll_pitch_first_fit", "roll_pitch_best_fit"):
            # Calculate pitch usage from schedule
            pitch_angles = [
                abs(s.pitch_angle) for s in schedule if s.pitch_angle != 0.0
            ]
            if pitch_angles:
                total_pitch_used_deg = sum(pitch_angles)
                max_pitch_deg = max(pitch_angles)

            # Get opportunities saved by pitch (set during scheduling)
            if hasattr(self, "_pitch_opportunities_saved"):
                opportunities_saved_by_pitch = self._pitch_opportunities_saved

        return ScheduleMetrics(
            algorithm=algorithm_name,
            runtime_ms=runtime_ms,
            opportunities_evaluated=n_evaluated,
            opportunities_accepted=n_accepted,
            opportunities_rejected=n_rejected,
            total_value=total_value,
            mean_value=mean_value,
            total_imaging_time=total_imaging_time,
            total_maneuver_time=total_maneuver_time,
            schedule_span=schedule_span,
            utilization=utilization,
            mean_density=mean_density,
            median_density=median_density,
            mean_incidence_deg=mean_incidence_deg,
            total_pitch_used_deg=total_pitch_used_deg,
            max_pitch_deg=max_pitch_deg,
            opportunities_saved_by_pitch=opportunities_saved_by_pitch,
            seed=None,
        )
