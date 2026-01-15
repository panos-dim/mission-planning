"""
SAR Visibility Analysis Module.

Computes SAR-specific imaging opportunities with:
- Look side determination (LEFT/RIGHT)
- Pass direction (ASCENDING/DESCENDING)
- Incidence angle calculations (near/center/far)
- Swath geometry computation

This module extends the base visibility calculations with SAR-specific
logic aligned with ICEYE tasking concepts.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .sar_config import (
    LookSide,
    PassDirection,
    SARInputParams,
    SARMode,
    SARModeSpec,
    SAROpportunityData,
    get_sar_config,
)
from .visibility import PassDetails, VisibilityCalculator

logger = logging.getLogger(__name__)

# Constants
EARTH_RADIUS_KM = 6371.0


@dataclass
class SARPassDetails(PassDetails):
    """
    Extended pass details with SAR-specific attributes.

    Inherits from PassDetails and adds SAR-specific fields for
    swath visualization and ICEYE-parity reporting.
    """

    # SAR-specific attributes
    sar_data: Optional[SAROpportunityData] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary including SAR data."""
        result = super().to_dict()

        if self.sar_data is not None:
            result["sar"] = self.sar_data.to_dict()
            # Also add key fields at top level for easy access
            result["look_side"] = self.sar_data.look_side.value
            result["pass_direction"] = self.sar_data.pass_direction.value
            result["incidence_center_deg"] = self.sar_data.incidence_center_deg
            result["swath_width_km"] = self.sar_data.swath_width_km
            result["imaging_mode"] = self.sar_data.imaging_mode.value

        return result


class SARVisibilityCalculator:
    """
    SAR-specific visibility and opportunity analysis.

    Extends base visibility calculations with SAR-specific logic:
    - Look side determination based on satellite-target geometry
    - Pass direction from satellite velocity vector
    - Incidence angle model (near/center/far)
    - Swath polygon computation
    """

    def __init__(
        self,
        base_calculator: VisibilityCalculator,
        sar_params: SARInputParams,
    ):
        """
        Initialize SAR visibility calculator.

        Args:
            base_calculator: Base visibility calculator with satellite orbit
            sar_params: SAR mission parameters
        """
        self.base_calc = base_calculator
        self.satellite = base_calculator.satellite
        self.sar_params = sar_params
        self.sar_config = get_sar_config()

        # Get mode specification
        self.mode_spec = self.sar_config.get_mode_spec(sar_params.imaging_mode)

        # Determine effective incidence range
        self.incidence_min, self.incidence_max = self._get_effective_incidence_range()

        logger.info(
            f"SAR visibility calculator initialized: "
            f"mode={sar_params.imaging_mode.value}, "
            f"incidence=[{self.incidence_min:.1f}°, {self.incidence_max:.1f}°], "
            f"look_side={sar_params.look_side.value}, "
            f"pass_direction={sar_params.pass_direction.value}"
        )

    def _get_effective_incidence_range(self) -> Tuple[float, float]:
        """Get effective incidence range (user-specified or mode default)."""
        if self.sar_params.incidence_min_deg is not None:
            inc_min = self.sar_params.incidence_min_deg
        else:
            inc_min = self.mode_spec.incidence_angle.recommended_min

        if self.sar_params.incidence_max_deg is not None:
            inc_max = self.sar_params.incidence_max_deg
        else:
            inc_max = self.mode_spec.incidence_angle.recommended_max

        return (inc_min, inc_max)

    def compute_sar_passes(
        self,
        target_lat: float,
        target_lon: float,
        target_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[SARPassDetails]:
        """
        Compute SAR imaging opportunities for a target.

        This filters base visibility passes through SAR-specific constraints:
        - Incidence angle within specified range
        - Look side matches constraint (or determines optimal)
        - Pass direction matches constraint (or accepts any)

        Args:
            target_lat: Target latitude in degrees
            target_lon: Target longitude in degrees
            target_name: Name of the target
            start_time: Analysis start time (UTC)
            end_time: Analysis end time (UTC)

        Returns:
            List of SAR-specific pass details
        """
        from .targets import GroundTarget

        # Create temporary target for base visibility
        target = GroundTarget(
            name=target_name,
            latitude=target_lat,
            longitude=target_lon,
            mission_type="imaging",
            # Use wide FOV for SAR initial pass detection
            sensor_fov_half_angle_deg=self.sar_config.get_spacecraft_spec().max_roll_deg,
            max_spacecraft_roll=self.sar_config.get_spacecraft_spec().max_roll_deg,
        )

        # Get base visibility passes (get_visibility_windows takes a list)
        passes_dict = self.base_calc.get_visibility_windows(
            [target], start_time, end_time
        )
        base_passes = passes_dict.get(target_name, [])

        logger.info(f"Found {len(base_passes)} base visibility passes for SAR analysis")

        # Process each pass with SAR-specific analysis
        sar_passes: List[SARPassDetails] = []

        for base_pass in base_passes:
            sar_pass = self._analyze_sar_pass(base_pass, target)

            if sar_pass is not None:
                sar_passes.append(sar_pass)

        logger.info(
            f"SAR analysis complete: {len(sar_passes)} valid SAR opportunities "
            f"(filtered from {len(base_passes)} base passes)"
        )

        return sar_passes

    def _analyze_sar_pass(
        self,
        base_pass: PassDetails,
        target: Any,
    ) -> Optional[SARPassDetails]:
        """
        Analyze a base visibility pass for SAR-specific attributes.

        Returns None if the pass doesn't meet SAR constraints.
        """
        # Determine optimal imaging time (use max elevation time)
        imaging_time = base_pass.max_elevation_time

        # Calculate satellite position and velocity at imaging time
        sat_pos = self._get_satellite_ecef(imaging_time)
        sat_vel = self._get_satellite_velocity(imaging_time)
        target_pos = self._get_target_ecef(target.latitude, target.longitude)

        # Determine pass direction from velocity
        pass_direction = self._compute_pass_direction(sat_vel, sat_pos)

        # Check pass direction constraint
        if not self._matches_pass_direction(pass_direction):
            logger.debug(
                f"Pass {base_pass.start_time} rejected: "
                f"direction {pass_direction.value} doesn't match constraint"
            )
            return None

        # Determine look side from geometry
        actual_look_side = self._compute_look_side(sat_pos, sat_vel, target_pos)

        # Check look side constraint
        if not self._matches_look_side(actual_look_side):
            logger.debug(
                f"Pass {base_pass.start_time} rejected: "
                f"look side {actual_look_side.value} doesn't match constraint"
            )
            return None

        # Calculate incidence angle at target
        incidence_center = self._compute_incidence_angle(sat_pos, target_pos)

        # Check incidence angle constraint
        if not self._matches_incidence_range(incidence_center):
            logger.debug(
                f"Pass {base_pass.start_time} rejected: "
                f"incidence {incidence_center:.1f}° outside range "
                f"[{self.incidence_min:.1f}°, {self.incidence_max:.1f}°]"
            )
            return None

        # Calculate near/far incidence (swath edges)
        incidence_near, incidence_far = self._compute_swath_incidence(incidence_center)

        # Calculate quality score
        quality_score = self._compute_sar_quality(incidence_center)

        # Create SAR opportunity data
        sar_data = SAROpportunityData(
            look_side=actual_look_side,
            pass_direction=pass_direction,
            incidence_center_deg=incidence_center,
            incidence_near_deg=incidence_near,
            incidence_far_deg=incidence_far,
            swath_width_km=self.mode_spec.scene.width_km,
            scene_length_km=self.mode_spec.scene.length_km,
            imaging_mode=self.sar_params.imaging_mode,
            quality_score=quality_score,
        )

        # Create SAR pass details
        sar_pass = SARPassDetails(
            target_name=base_pass.target_name,
            satellite_name=base_pass.satellite_name,
            start_time=base_pass.start_time,
            max_elevation_time=base_pass.max_elevation_time,
            end_time=base_pass.end_time,
            max_elevation=base_pass.max_elevation,
            start_azimuth=base_pass.start_azimuth,
            max_elevation_azimuth=base_pass.max_elevation_azimuth,
            end_azimuth=base_pass.end_azimuth,
            satellite_id=base_pass.satellite_id,
            pass_index=base_pass.pass_index,
            incidence_angle_deg=incidence_center,
            mode="SAR",
            sar_data=sar_data,
        )

        logger.debug(
            f"SAR pass accepted: {base_pass.start_time}, "
            f"look_side={actual_look_side.value}, "
            f"direction={pass_direction.value}, "
            f"incidence={incidence_center:.1f}°"
        )

        return sar_pass

    def _get_satellite_ecef(self, timestamp: datetime) -> np.ndarray:
        """Get satellite position in ECEF coordinates (km)."""
        lat, lon, alt = self.satellite.get_position(timestamp)

        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)

        r = EARTH_RADIUS_KM + alt
        x = r * math.cos(lat_rad) * math.cos(lon_rad)
        y = r * math.cos(lat_rad) * math.sin(lon_rad)
        z = r * math.sin(lat_rad)

        return np.array([x, y, z])

    def _get_satellite_velocity(self, timestamp: datetime) -> np.ndarray:
        """
        Estimate satellite velocity vector in ECEF.

        Uses finite differencing over a small time step.
        """
        dt = timedelta(seconds=1)
        pos1 = self._get_satellite_ecef(timestamp - dt)
        pos2 = self._get_satellite_ecef(timestamp + dt)

        velocity: np.ndarray = (pos2 - pos1) / 2.0  # km/s
        return velocity

    def _get_target_ecef(
        self, lat: float, lon: float, alt_km: float = 0.0
    ) -> np.ndarray:
        """Get target position in ECEF coordinates (km)."""
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)

        r = EARTH_RADIUS_KM + alt_km
        x = r * math.cos(lat_rad) * math.cos(lon_rad)
        y = r * math.cos(lat_rad) * math.sin(lon_rad)
        z = r * math.sin(lat_rad)

        return np.array([x, y, z])

    def _compute_pass_direction(
        self, velocity: np.ndarray, position: np.ndarray
    ) -> PassDirection:
        """
        Determine pass direction (ascending/descending) from velocity.

        Ascending: Satellite moving northward (positive Z component in ECI-like frame)
        Descending: Satellite moving southward (negative Z component)
        """
        # Project velocity onto local vertical (radial) direction
        radial = position / np.linalg.norm(position)

        # Cross product with Earth's rotation axis gives east direction
        earth_axis = np.array([0, 0, 1])
        east = np.cross(earth_axis, radial)
        east_norm = np.linalg.norm(east)

        if east_norm < 1e-10:
            # Near poles, use alternative method
            return PassDirection.ASCENDING

        east = east / east_norm
        north = np.cross(radial, east)

        # Project velocity onto north direction
        north_velocity = np.dot(velocity, north)

        return (
            PassDirection.ASCENDING if north_velocity > 0 else PassDirection.DESCENDING
        )

    def _compute_look_side(
        self,
        sat_pos: np.ndarray,
        sat_vel: np.ndarray,
        target_pos: np.ndarray,
    ) -> LookSide:
        """
        Determine look side (LEFT/RIGHT) based on geometry.

        Uses cross product of velocity with satellite-to-target vector
        to determine which side of the ground track the target is on.
        """
        # Vector from satellite to target
        sat_to_target = target_pos - sat_pos

        # Cross product: velocity × sat_to_target
        cross = np.cross(sat_vel, sat_to_target)

        # Project onto radial (up) direction
        radial = sat_pos / np.linalg.norm(sat_pos)
        up_component = np.dot(cross, radial)

        # Positive: target is on right side of ground track
        # Negative: target is on left side of ground track
        return LookSide.RIGHT if up_component > 0 else LookSide.LEFT

    def _compute_incidence_angle(
        self, sat_pos: np.ndarray, target_pos: np.ndarray
    ) -> float:
        """
        Compute incidence angle (off-nadir angle) to target.

        This is the angle between the satellite's nadir direction
        and the line of sight to the target.
        """
        # Nadir direction (toward Earth center)
        nadir = -sat_pos / np.linalg.norm(sat_pos)

        # Line of sight to target
        los = target_pos - sat_pos
        los_norm = los / np.linalg.norm(los)

        # Angle between nadir and LOS
        cos_angle = np.dot(nadir, los_norm)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)

        incidence_rad = math.acos(cos_angle)
        return math.degrees(incidence_rad)

    def _compute_swath_incidence(self, center_incidence: float) -> Tuple[float, float]:
        """
        Compute near and far edge incidence angles.

        Based on swath geometry model from configuration.
        """
        # Get offset from config (default 2.5°)
        swath_config = self.sar_config._config.get("swath_geometry", {})
        inc_model = swath_config.get("incidence_model", {})
        offset = inc_model.get("swath_half_angle_offset_deg", 2.5)

        # Compute near/far
        incidence_near = max(0.0, center_incidence - offset)
        incidence_far = min(90.0, center_incidence + offset)

        return (incidence_near, incidence_far)

    def _compute_sar_quality(self, incidence_deg: float) -> float:
        """
        Compute SAR imaging quality score based on incidence angle.

        Uses band model centered on optimal incidence for the mode.
        """
        optimal = self.mode_spec.quality.optimal_incidence_deg

        # Band model: quality peaks at optimal, decreases with distance
        # Quality = 100 * exp(-((inc - optimal) / sigma)^2)
        sigma = 15.0  # Width of quality band in degrees

        quality = 100.0 * math.exp(-(((incidence_deg - optimal) / sigma) ** 2))
        return max(0.0, min(100.0, quality))

    def _matches_pass_direction(self, direction: PassDirection) -> bool:
        """Check if pass direction matches constraint."""
        if self.sar_params.pass_direction == PassDirection.ANY:
            return True
        return direction == self.sar_params.pass_direction

    def _matches_look_side(self, side: LookSide) -> bool:
        """Check if look side matches constraint."""
        if self.sar_params.look_side == LookSide.ANY:
            return True
        return side == self.sar_params.look_side

    def _matches_incidence_range(self, incidence: float) -> bool:
        """Check if incidence angle is within specified range."""
        return self.incidence_min <= incidence <= self.incidence_max

    def compute_swath_polygon(
        self,
        sat_pos: np.ndarray,
        sat_vel: np.ndarray,
        look_side: LookSide,
        swath_width_km: float,
        scene_length_km: float,
    ) -> List[Tuple[float, float]]:
        """
        Compute swath polygon coordinates on Earth's surface.

        Returns list of (lat, lon) tuples forming the swath polygon.

        Args:
            sat_pos: Satellite ECEF position (km)
            sat_vel: Satellite velocity vector (km/s)
            look_side: Which side of track (LEFT/RIGHT)
            swath_width_km: Width of swath (km)
            scene_length_km: Length of scene (km)

        Returns:
            List of (lat, lon) corner points
        """
        # Get local coordinate frame at satellite position
        radial = sat_pos / np.linalg.norm(sat_pos)

        # Along-track direction (velocity projected to horizontal)
        vel_horizontal = sat_vel - np.dot(sat_vel, radial) * radial
        along_track = vel_horizontal / np.linalg.norm(vel_horizontal)

        # Cross-track direction (perpendicular to velocity, in horizontal plane)
        cross_track = np.cross(radial, along_track)
        cross_track = cross_track / np.linalg.norm(cross_track)

        # Flip cross track direction based on look side
        if look_side == LookSide.LEFT:
            cross_track = -cross_track

        # Calculate satellite altitude
        sat_alt_km = np.linalg.norm(sat_pos) - EARTH_RADIUS_KM

        # Calculate ground nadir point
        nadir_point = radial * EARTH_RADIUS_KM

        # Calculate swath center offset from nadir
        # Use average incidence angle for center
        avg_incidence = (self.incidence_min + self.incidence_max) / 2
        ground_range_km = sat_alt_km * math.tan(math.radians(avg_incidence))

        # Swath center on ground
        swath_center = nadir_point + cross_track * ground_range_km

        # Calculate four corners of swath
        half_width = swath_width_km / 2
        half_length = scene_length_km / 2

        corners = []
        for along_sign in [-1, 1]:
            for cross_sign in [-1, 1]:
                # Order: -along/-cross, -along/+cross, +along/+cross, +along/-cross
                corner = (
                    swath_center
                    + along_track * (along_sign * half_length)
                    + cross_track * (cross_sign * half_width)
                )
                # Project to Earth surface
                corner_norm = corner / np.linalg.norm(corner) * EARTH_RADIUS_KM

                # Convert to lat/lon
                lat, lon = self._ecef_to_latlon(corner_norm)
                corners.append((lat, lon))

        # Reorder for proper polygon winding (counterclockwise)
        return [corners[0], corners[1], corners[3], corners[2]]

    def _ecef_to_latlon(self, pos: np.ndarray) -> Tuple[float, float]:
        """Convert ECEF position to lat/lon in degrees."""
        x, y, z = pos

        lon = math.degrees(math.atan2(y, x))
        lat = math.degrees(math.asin(z / np.linalg.norm(pos)))

        return (lat, lon)


def analyze_sar_opportunities(
    satellite: Any,
    targets: List[Any],
    start_time: datetime,
    end_time: datetime,
    sar_params: SARInputParams,
    use_adaptive: bool = True,
) -> Dict[str, List[SARPassDetails]]:
    """
    Analyze SAR imaging opportunities for multiple targets.

    Main entry point for SAR visibility analysis.

    Args:
        satellite: SatelliteOrbit instance
        targets: List of GroundTarget instances
        start_time: Analysis start time
        end_time: Analysis end time
        sar_params: SAR mission parameters
        use_adaptive: Use adaptive time stepping

    Returns:
        Dict mapping target name to list of SAR opportunities
    """
    # Create base visibility calculator
    base_calc = VisibilityCalculator(satellite, use_adaptive=use_adaptive)

    # Create SAR calculator
    sar_calc = SARVisibilityCalculator(base_calc, sar_params)

    results: Dict[str, List[SARPassDetails]] = {}

    for target in targets:
        passes = sar_calc.compute_sar_passes(
            target.latitude,
            target.longitude,
            target.name,
            start_time,
            end_time,
        )
        results[target.name] = passes

        logger.info(f"Target '{target.name}': {len(passes)} SAR opportunities found")

    return results
