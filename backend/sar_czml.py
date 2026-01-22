"""
SAR CZML Visualization Module.

Generates CZML packets for SAR-specific visualization:
- Left-looking swath polygons
- Right-looking swath polygons
- SAR opportunity markers
- Swath coverage areas

Integrates with the main CZMLGenerator for Cesium rendering.
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Earth parameters
EARTH_RADIUS_KM = 6371.0

# SAR Visualization Colors (RGBA)
SAR_COLORS = {
    "LEFT": {
        "fill": [255, 100, 100, 60],  # Red tint for left-looking
        "outline": [255, 50, 50, 200],
    },
    "RIGHT": {
        "fill": [100, 100, 255, 60],  # Blue tint for right-looking
        "outline": [50, 50, 255, 200],
    },
    "ANY": {
        "fill": [150, 100, 255, 60],  # Purple for undetermined
        "outline": [100, 50, 255, 200],
    },
}


# =============================================================================
# STANDALONE UTILITY FUNCTIONS
# These can be used by the scheduler without instantiating SARCZMLGenerator
# =============================================================================


def _destination_point_util(
    lat: float, lon: float, distance_km: float, bearing_deg: float
) -> Tuple[float, float]:
    """
    Calculate destination point given start, distance, and bearing.
    Uses spherical Earth approximation.
    """
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(bearing_deg)

    angular_dist = distance_km / EARTH_RADIUS_KM

    dest_lat_rad = math.asin(
        math.sin(lat_rad) * math.cos(angular_dist)
        + math.cos(lat_rad) * math.sin(angular_dist) * math.cos(bearing_rad)
    )

    dest_lon_rad = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(angular_dist) * math.cos(lat_rad),
        math.cos(angular_dist) - math.sin(lat_rad) * math.sin(dest_lat_rad),
    )

    return (math.degrees(dest_lat_rad), math.degrees(dest_lon_rad))


def compute_sar_swath_polygon(
    sat_lat: float,
    sat_lon: float,
    sat_alt_km: float,
    track_azimuth_deg: float,
    look_side: str,
    swath_width_km: float,
    scene_length_km: float,
    incidence_deg: float,
) -> List[Tuple[float, float]]:
    """
    Compute SAR swath polygon corners given satellite position and SAR parameters.

    This is a standalone utility function that can be called from the scheduler
    to compute swath polygons for scheduled SAR opportunities.

    Args:
        sat_lat: Satellite latitude in degrees
        sat_lon: Satellite longitude in degrees
        sat_alt_km: Satellite altitude in km
        track_azimuth_deg: Ground track direction (azimuth) in degrees (0=North, 90=East)
        look_side: "LEFT" or "RIGHT"
        swath_width_km: Width of swath perpendicular to track
        scene_length_km: Length of scene along track
        incidence_deg: Center incidence angle in degrees

    Returns:
        List of 4 corner coordinates [(lat, lon), ...] forming a closed polygon
    """
    # Calculate cross-track direction
    if look_side == "LEFT":
        cross_track_azimuth = (track_azimuth_deg - 90) % 360
    else:
        cross_track_azimuth = (track_azimuth_deg + 90) % 360

    # Calculate ground range to swath center
    ground_range_km = sat_alt_km * math.tan(math.radians(incidence_deg))

    # Calculate swath center point
    center_lat, center_lon = _destination_point_util(
        sat_lat, sat_lon, ground_range_km, cross_track_azimuth
    )

    # Calculate four corners
    half_width = swath_width_km / 2
    half_length = scene_length_km / 2

    corners: List[Tuple[float, float]] = []

    # Corner order for proper polygon winding
    for along_sign in [1, 1, -1, -1]:
        for cross_sign in [-1, 1, 1, -1]:
            if len(corners) >= 4:
                break

            # Move along track from center
            temp_lat, temp_lon = _destination_point_util(
                center_lat,
                center_lon,
                along_sign * half_length,
                (
                    track_azimuth_deg
                    if along_sign > 0
                    else (track_azimuth_deg + 180) % 360
                ),
            )

            # Move cross-track
            corner_lat, corner_lon = _destination_point_util(
                temp_lat,
                temp_lon,
                cross_sign * half_width,
                (
                    cross_track_azimuth
                    if cross_sign > 0
                    else (cross_track_azimuth + 180) % 360
                ),
            )

            corners.append((corner_lat, corner_lon))

    # Reorder for correct winding
    return [corners[0], corners[1], corners[3], corners[2]]


def compute_track_azimuth_from_velocity(
    sat_lat1: float, sat_lon1: float, sat_lat2: float, sat_lon2: float, ref_lat: float
) -> float:
    """
    Compute ground track azimuth from two satellite positions.

    Args:
        sat_lat1, sat_lon1: First position (earlier time)
        sat_lat2, sat_lon2: Second position (later time)
        ref_lat: Reference latitude for longitude scaling

    Returns:
        Azimuth in degrees (0=North, 90=East)
    """
    dlat = sat_lat2 - sat_lat1
    dlon = sat_lon2 - sat_lon1

    # Account for longitude scaling with latitude
    dlon_scaled = dlon * math.cos(math.radians(ref_lat))

    # Calculate azimuth
    azimuth_rad = math.atan2(dlon_scaled, dlat)
    return math.degrees(azimuth_rad) % 360


class SARCZMLGenerator:
    """
    Generates CZML packets for SAR visualization in Cesium.

    Creates swath polygons that show left/right looking geometry,
    properly oriented relative to the satellite ground track.
    """

    def __init__(
        self,
        satellite: Any,
        start_time: datetime,
        end_time: datetime,
    ):
        """
        Initialize SAR CZML generator.

        Args:
            satellite: SatelliteOrbit instance
            start_time: Mission start time
            end_time: Mission end time
        """
        self.satellite = satellite
        self.start_time = start_time
        self.end_time = end_time

    def _format_czml_date(self, dt: Optional[datetime]) -> str:
        """Format datetime for CZML. Returns empty string if None (caller should handle)."""
        if dt is None:
            return ""
        # Handle timezone-aware datetimes by converting to naive UTC
        if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt.replace(microsecond=0).isoformat() + "Z"

    def generate_swath_packets(
        self,
        sar_passes: List[Any],
    ) -> List[Dict[str, Any]]:
        """
        Generate CZML packets for SAR swath visualization.

        Creates one swath polygon per SAR opportunity, colored by look side.

        Args:
            sar_passes: List of SARPassDetails objects

        Returns:
            List of CZML packets for swaths
        """
        packets = []

        for idx, sar_pass in enumerate(sar_passes):
            if not hasattr(sar_pass, "sar_data") or sar_pass.sar_data is None:
                continue

            swath_packet = self._create_swath_packet(sar_pass, idx)
            if swath_packet:
                packets.append(swath_packet)

        logger.info(f"Generated {len(packets)} SAR swath CZML packets")
        return packets

    def _create_swath_packet(
        self,
        sar_pass: Any,
        index: int,
        run_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create CZML packet for a single SAR swath polygon.

        The swath is positioned on the correct side of the ground track
        based on the look_side attribute.

        Includes stable opportunity_id and run_id for deterministic picking.
        """
        try:
            sar_data = sar_pass.sar_data
            imaging_time = sar_pass.max_elevation_time

            # Get satellite position and velocity at imaging time
            sat_lat, sat_lon, sat_alt = self.satellite.get_position(imaging_time)

            # Calculate swath polygon corners
            swath_corners = self._compute_swath_corners(
                sat_lat=sat_lat,
                sat_lon=sat_lon,
                sat_alt_km=sat_alt,
                imaging_time=imaging_time,
                look_side=sar_data.look_side.value,
                swath_width_km=sar_data.swath_width_km,
                scene_length_km=sar_data.scene_length_km,
                incidence_deg=sar_data.incidence_center_deg,
            )

            if not swath_corners:
                return None

            # Get colors based on look side
            colors = SAR_COLORS.get(sar_data.look_side.value, SAR_COLORS["ANY"])

            # Build polygon positions (lon, lat, height triplets)
            polygon_positions = []
            for lat, lon in swath_corners:
                polygon_positions.extend([lon, lat, 0])

            # Generate stable opportunity_id from target + time
            target_name = sar_pass.target_name
            time_key = imaging_time.strftime("%Y%m%d%H%M%S")
            opportunity_id = f"{target_name}_{time_key}_{index}"

            # Create packet with deterministic ID
            packet_id = f"sar_swath_{opportunity_id}"
            look_side = sar_data.look_side.value
            pass_dir = sar_data.pass_direction.value
            mode = sar_data.imaging_mode.value
            inc_center = sar_data.incidence_center_deg

            return {
                "id": packet_id,
                "name": f"SAR Swath - {target_name} ({look_side})",
                "description": f"""
                    <div style="background: rgba(17, 24, 39, 0.95); padding: 12px; border-radius: 8px; color: white;">
                        <h3 style="color: {'#FF6666' if look_side == 'LEFT' else '#6666FF'}; margin: 0 0 8px 0;">
                            SAR Swath - {target_name}
                        </h3>
                        <table style="width: 100%; font-size: 13px;">
                            <tr><td style="color: #aaa;">Mode:</td><td>{mode.upper()}</td></tr>
                            <tr><td style="color: #aaa;">Look Side:</td><td>{look_side}</td></tr>
                            <tr><td style="color: #aaa;">Pass Direction:</td><td>{pass_dir}</td></tr>
                            <tr><td style="color: #aaa;">Incidence:</td><td>{inc_center:.1f}°</td></tr>
                            <tr><td style="color: #aaa;">Swath Width:</td><td>{sar_data.swath_width_km:.1f} km</td></tr>
                            <tr><td style="color: #aaa;">Scene Length:</td><td>{sar_data.scene_length_km:.1f} km</td></tr>
                            <tr><td style="color: #aaa;">Time:</td><td>{imaging_time.strftime('%Y-%m-%d %H:%M:%S')} UTC</td></tr>
                        </table>
                    </div>
                """,
                # Use pass times if available, fallback to mission times
                "availability": f"{self._format_czml_date(sar_pass.start_time or self.start_time)}/{self._format_czml_date(sar_pass.end_time or self.end_time)}",
                "polygon": {
                    "positions": {
                        "cartographicDegrees": polygon_positions,
                    },
                    "height": 0,
                    "material": {"solidColor": {"color": {"rgba": colors["fill"]}}},
                    "outline": True,
                    "outlineColor": {"rgba": colors["outline"]},
                    "outlineWidth": 2,
                },
                # Custom properties for deterministic picking
                "properties": {
                    "opportunity_id": {"string": opportunity_id},
                    "run_id": {"string": run_id or "analysis"},
                    "target_id": {"string": target_name},
                    "pass_index": {"number": index},
                    "look_side": {"string": look_side},
                    "pass_direction": {"string": pass_dir},
                    "incidence_deg": {"number": inc_center},
                    "swath_width_km": {"number": sar_data.swath_width_km},
                    "imaging_time": {"string": self._format_czml_date(imaging_time)},
                    "entity_type": {"string": "sar_swath"},
                },
            }

        except Exception as e:
            logger.error(f"Error creating SAR swath packet: {e}")
            return None

    def _compute_swath_corners(
        self,
        sat_lat: float,
        sat_lon: float,
        sat_alt_km: float,
        imaging_time: datetime,
        look_side: str,
        swath_width_km: float,
        scene_length_km: float,
        incidence_deg: float,
    ) -> List[Tuple[float, float]]:
        """
        Compute the four corners of a SAR swath polygon.

        The swath is positioned on the correct side of the ground track
        and oriented along the satellite velocity direction.

        Args:
            sat_lat: Satellite latitude at imaging time
            sat_lon: Satellite longitude at imaging time
            sat_alt_km: Satellite altitude in km
            imaging_time: Time of imaging
            look_side: "LEFT" or "RIGHT"
            swath_width_km: Width of swath perpendicular to track
            scene_length_km: Length of scene along track
            incidence_deg: Center incidence angle

        Returns:
            List of 4 corner coordinates [(lat, lon), ...]
        """
        # Get satellite velocity vector to determine track direction
        velocity = self._get_velocity_vector(imaging_time)

        # Calculate ground track direction (azimuth)
        track_azimuth = self._velocity_to_azimuth(velocity, sat_lat, sat_lon)

        # Calculate cross-track direction (perpendicular to track)
        # LEFT: -90° from track, RIGHT: +90° from track
        if look_side == "LEFT":
            cross_track_azimuth = (track_azimuth - 90) % 360
        else:
            cross_track_azimuth = (track_azimuth + 90) % 360

        # Calculate ground range to swath center
        # ground_range = altitude * tan(incidence)
        ground_range_km = sat_alt_km * math.tan(math.radians(incidence_deg))

        # Calculate swath center point
        center_lat, center_lon = self._destination_point(
            sat_lat, sat_lon, ground_range_km, cross_track_azimuth
        )

        # Calculate four corners relative to swath center
        half_width = swath_width_km / 2
        half_length = scene_length_km / 2

        corners: List[Tuple[float, float]] = []

        # Corner order for proper polygon winding:
        # 1. Along-track forward, cross-track near
        # 2. Along-track forward, cross-track far
        # 3. Along-track back, cross-track far
        # 4. Along-track back, cross-track near

        for along_sign in [1, 1, -1, -1]:
            for cross_sign in [-1, 1, 1, -1]:
                if len(corners) >= 4:
                    break

                # Calculate corner position
                # First move along track from center
                temp_lat, temp_lon = self._destination_point(
                    center_lat,
                    center_lon,
                    along_sign * half_length,
                    track_azimuth if along_sign > 0 else (track_azimuth + 180) % 360,
                )

                # Then move cross-track
                corner_lat, corner_lon = self._destination_point(
                    temp_lat,
                    temp_lon,
                    cross_sign * half_width,
                    (
                        cross_track_azimuth
                        if cross_sign > 0
                        else (cross_track_azimuth + 180) % 360
                    ),
                )

                corners.append((corner_lat, corner_lon))

        # Reorder for correct winding
        return [corners[0], corners[1], corners[3], corners[2]]

    def _get_velocity_vector(self, timestamp: datetime) -> Tuple[float, float, float]:
        """Get satellite velocity vector using finite differencing."""
        dt = timedelta(seconds=1)

        lat1, lon1, _ = self.satellite.get_position(timestamp - dt)
        lat2, lon2, _ = self.satellite.get_position(timestamp + dt)

        # Approximate velocity in degrees per second
        dlat = (lat2 - lat1) / 2.0
        dlon = (lon2 - lon1) / 2.0

        return (dlat, dlon, 0)

    def _velocity_to_azimuth(
        self, velocity: Tuple[float, float, float], lat: float, lon: float
    ) -> float:
        """
        Convert velocity vector to azimuth (heading) in degrees.

        Args:
            velocity: (dlat, dlon, dalt) in degrees/second
            lat: Current latitude
            lon: Current longitude

        Returns:
            Azimuth in degrees (0=North, 90=East)
        """
        dlat, dlon, _ = velocity

        # Account for longitude scaling with latitude
        dlon_scaled = dlon * math.cos(math.radians(lat))

        # Calculate azimuth
        azimuth_rad = math.atan2(dlon_scaled, dlat)
        azimuth_deg = math.degrees(azimuth_rad)

        # Normalize to 0-360
        return azimuth_deg % 360

    def _destination_point(
        self,
        lat: float,
        lon: float,
        distance_km: float,
        bearing_deg: float,
    ) -> Tuple[float, float]:
        """
        Calculate destination point given start, distance, and bearing.

        Uses spherical Earth approximation.

        Args:
            lat: Starting latitude in degrees
            lon: Starting longitude in degrees
            distance_km: Distance in kilometers
            bearing_deg: Bearing in degrees (0=North, 90=East)

        Returns:
            (destination_lat, destination_lon) in degrees
        """
        # Convert to radians
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        bearing_rad = math.radians(bearing_deg)

        # Angular distance
        angular_dist = distance_km / EARTH_RADIUS_KM

        # Calculate destination
        dest_lat_rad = math.asin(
            math.sin(lat_rad) * math.cos(angular_dist)
            + math.cos(lat_rad) * math.sin(angular_dist) * math.cos(bearing_rad)
        )

        dest_lon_rad = lon_rad + math.atan2(
            math.sin(bearing_rad) * math.sin(angular_dist) * math.cos(lat_rad),
            math.cos(angular_dist) - math.sin(lat_rad) * math.sin(dest_lat_rad),
        )

        return (math.degrees(dest_lat_rad), math.degrees(dest_lon_rad))

    def generate_dynamic_swath_packet(
        self,
        look_side: str,
        swath_width_km: float,
        incidence_deg: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a time-dynamic swath that follows the satellite.

        Creates a swath polygon that moves with the satellite throughout
        the mission, useful for showing continuous SAR coverage capability.

        Uses CZML vertexPositions with time-sampled data for proper Cesium rendering.
        Format: [time, lon1, lat1, h1, lon2, lat2, h2, lon3, lat3, h3, lon4, lat4, h4, ...]

        Args:
            look_side: "LEFT" or "RIGHT"
            swath_width_km: Swath width in km
            incidence_deg: Center incidence angle

        Returns:
            CZML packet with time-dynamic polygon
        """
        if self.satellite is None or self.start_time is None or self.end_time is None:
            return None

        colors = SAR_COLORS.get(look_side, SAR_COLORS["ANY"])

        # Generate swath corners at each time step
        # Use larger time step for performance (60 seconds)
        time_step = timedelta(seconds=60)
        current_time = self.start_time

        # Build time-tagged vertex positions for CZML
        # Format: [time0, lon1, lat1, h1, lon2, lat2, h2, ..., time1, lon1, lat1, h1, ...]
        vertex_data: List[float] = []

        sample_count = 0
        while current_time <= self.end_time:
            try:
                sat_lat, sat_lon, sat_alt = self.satellite.get_position(current_time)

                corners = self._compute_swath_corners(
                    sat_lat=sat_lat,
                    sat_lon=sat_lon,
                    sat_alt_km=sat_alt,
                    imaging_time=current_time,
                    look_side=look_side,
                    swath_width_km=swath_width_km,
                    scene_length_km=swath_width_km,  # Square swath for dynamic view
                    incidence_deg=incidence_deg,
                )

                if corners and len(corners) >= 4:
                    seconds_from_start = (
                        current_time - self.start_time
                    ).total_seconds()
                    # Add time offset first
                    vertex_data.append(seconds_from_start)
                    # Then add all 4 corners: lon, lat, height for each
                    for lat, lon in corners:
                        vertex_data.extend([lon, lat, 0])
                    sample_count += 1

            except Exception as e:
                logger.warning(f"Error generating dynamic swath at {current_time}: {e}")

            current_time += time_step

        if not vertex_data or sample_count < 2:
            logger.warning(f"Insufficient data for dynamic {look_side} swath")
            return None

        logger.info(f"Generated dynamic {look_side} swath with {sample_count} samples")

        return {
            "id": f"sar_dynamic_swath_{look_side.lower()}",
            "name": f"SAR Coverage ({look_side})",
            "show": True,
            "availability": f"{self._format_czml_date(self.start_time)}/{self._format_czml_date(self.end_time)}",
            "polygon": {
                "vertexPositions": {
                    "epoch": self._format_czml_date(self.start_time),
                    "cartographicDegrees": vertex_data,
                },
                "height": 0,
                "material": {"solidColor": {"color": {"rgba": colors["fill"]}}},
                "outline": True,
                "outlineColor": {"rgba": colors["outline"]},
                "outlineWidth": 2,
            },
        }


def generate_sar_czml(
    satellite: Any,
    sar_passes: List[Any],
    start_time: datetime,
    end_time: datetime,
    include_dynamic_swath: bool = False,
    sar_params: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Generate all SAR-related CZML packets.

    Main entry point for SAR CZML generation.

    Args:
        satellite: SatelliteOrbit instance
        sar_passes: List of SARPassDetails objects
        start_time: Mission start time
        end_time: Mission end time
        include_dynamic_swath: Include time-dynamic swath following satellite
        sar_params: Optional SARInputParams for dynamic swath configuration

    Returns:
        List of CZML packets
    """
    generator = SARCZMLGenerator(satellite, start_time, end_time)

    packets = []

    # Generate swath packets for each SAR opportunity
    swath_packets = generator.generate_swath_packets(sar_passes)
    packets.extend(swath_packets)

    # Optionally generate dynamic swath that follows satellite
    if include_dynamic_swath and sar_params:
        from mission_planner.sar_config import get_sar_config

        config = get_sar_config()
        swath_width = config.get_swath_width(sar_params.imaging_mode)
        inc_min, inc_max = config.get_default_incidence_range(sar_params.imaging_mode)
        avg_incidence = (inc_min + inc_max) / 2

        look_side = sar_params.look_side.value

        if look_side == "ANY":
            # Generate both left and right swaths
            left_packet = generator.generate_dynamic_swath_packet(
                "LEFT", swath_width, avg_incidence
            )
            right_packet = generator.generate_dynamic_swath_packet(
                "RIGHT", swath_width, avg_incidence
            )
            if left_packet:
                packets.append(left_packet)
            if right_packet:
                packets.append(right_packet)
        else:
            # Generate single swath for specified side
            packet = generator.generate_dynamic_swath_packet(
                look_side, swath_width, avg_incidence
            )
            if packet:
                packets.append(packet)

    logger.info(f"Generated {len(packets)} total SAR CZML packets")
    return packets
