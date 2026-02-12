"""
CZML generation module for Cesium visualization.

Generates time-dynamic CZML data for:
- Satellite orbital tracks (single or constellation)
- Target markers
- Visibility windows and coverage areas
- Mission timeline visualization

Updated 2025: Supports satellite constellation visualization with
distinct colors per satellite.
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from backend.constants.colors import get_satellite_color_rgba_by_index, hex_to_rgba

logger = logging.getLogger(__name__)


class CZMLGenerator:
    """Generate CZML data for satellite mission visualization.

    Supports both single satellite and constellation modes.
    """

    def __init__(
        self,
        satellite: Optional[Any] = None,  # Single satellite (backward compatible)
        satellites: Optional[
            Dict[str, Any]
        ] = None,  # Dict of satellite_id -> SatelliteOrbit
        satellite_colors: Optional[
            Dict[str, str]
        ] = None,  # Dict of satellite_id -> hex color
        targets: Optional[List[Any]] = None,
        passes: Optional[List[Any]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        mission_type: Optional[str] = None,
        sensor_fov_half_angle_deg: Optional[float] = None,
        max_spacecraft_roll_deg: Optional[float] = None,
        imaging_type: Optional[str] = None,  # "optical" or "sar"
    ) -> None:
        # Constellation support: satellites dict takes precedence
        if satellites:
            self.satellites = satellites
            self.satellite = list(satellites.values())[0] if satellites else None
            self.is_constellation = len(satellites) > 1
        else:
            self.satellites = (
                {f"sat_{getattr(satellite, 'satellite_name', 'Satellite')}": satellite}
                if satellite
                else {}
            )
            self.satellite = satellite
            self.is_constellation = False

        self.satellite_colors = satellite_colors or {}
        self.targets = targets or []
        self.passes = passes or []
        self.start_time = start_time
        self.end_time = end_time
        self.mission_type = mission_type
        self.imaging_type = imaging_type  # "optical" or "sar"

        # Sensor FOV half-angle for footprint visualization
        self.sensor_fov_half_angle_deg: Optional[float] = sensor_fov_half_angle_deg

        # Max spacecraft roll (agility limit) for showing possible pointing envelope
        self.max_spacecraft_roll_deg = (
            max_spacecraft_roll_deg if max_spacecraft_roll_deg is not None else 45.0
        )

    def _format_czml_date(self, dt: Union[datetime, str, None]) -> str:
        """Format datetime for CZML in Cesium-compatible ISO 8601 format.

        Cesium requires dates without microseconds and with 'Z' suffix.
        Format: YYYY-MM-DDTHH:MM:SSZ
        """
        if dt is None:
            return ""

        # Handle string input (in case datetime is already a string)
        if isinstance(dt, str):
            return dt if dt.endswith("Z") else dt + "Z"

        try:
            pass  # Continue to datetime handling below

            # Ensure datetime is timezone-naive UTC before formatting
            if dt.tzinfo is not None:
                # Convert to UTC and remove timezone info
                dt_utc = dt.utctimetuple()
                dt = datetime(*dt_utc[:6])  # Reconstruct as naive datetime
                logger.debug(f"Converted timezone-aware datetime to naive UTC: {dt}")

            # Remove microseconds and ensure proper ISO format
            formatted = dt.replace(microsecond=0).isoformat() + "Z"
            logger.debug(f"Formatted datetime: {formatted}")
            return formatted

        except Exception as e:
            logger.error(f"Error formatting datetime {dt}: {e}")
            # Fallback to a simple format
            if hasattr(dt, "strftime"):
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            return str(dt)

    def generate(self) -> List[Dict[str, Any]]:
        """Generate complete CZML document.

        Supports both single satellite and constellation modes.
        For constellations, generates separate packets for each satellite
        with distinct colors.
        """
        czml = []

        # Document packet
        czml.append(self._create_document_packet())

        # Generate packets for each satellite in constellation
        for idx, (sat_id, sat_orbit) in enumerate(self.satellites.items()):
            # Get color for this satellite (default to palette)
            sat_color_rgba = self._get_satellite_color_rgba(sat_id, idx)

            # Satellite packet with constellation-aware coloring
            czml.append(
                self._create_satellite_packet_for(sat_id, sat_orbit, sat_color_rgba)
            )

            # Ground track for this satellite
            czml.append(
                self._create_ground_track_for(sat_id, sat_orbit, sat_color_rgba)
            )

            # Sensor footprint for imaging missions (primary satellite only for performance)
            # Only generate sensor cone for optical missions, not SAR
            # SAR missions use swath polygons instead (generated in sar_czml.py)
            if (
                idx == 0
                and self.mission_type == "imaging"
                and self.imaging_type != "sar"  # Skip cone for SAR missions
                and self.sensor_fov_half_angle_deg
            ):
                logger.info(
                    f"Generating sensor footprint for {sat_id} with FOV={self.sensor_fov_half_angle_deg}°"
                )
                pointing_cone_packet = self._create_pointing_cone_packet()
                if pointing_cone_packet:
                    czml.append(pointing_cone_packet)

            # Agility envelope for EACH satellite in constellation with matching colors
            # Only for optical missions - SAR uses swath polygons instead
            if (
                self.mission_type == "imaging"
                and self.imaging_type != "sar"
                and self.max_spacecraft_roll_deg
            ):
                agility_envelope_packet = self._create_agility_envelope_packet_for(
                    sat_id, sat_orbit, sat_color_rgba, idx
                )
                if agility_envelope_packet:
                    czml.append(agility_envelope_packet)

        # Target packets
        for i, target in enumerate(self.targets):
            czml.append(self._create_target_packet(target, i))

        # Optical pass packets (per-pass pickable entities for lock mode)
        # SAR missions use sar_czml.py swath polygons instead
        if (
            self.mission_type == "imaging"
            and self.imaging_type != "sar"
            and self.passes
        ):
            optical_packets = self._create_optical_pass_packets()
            czml.extend(optical_packets)
            logger.info(f"📸 Added {len(optical_packets)} optical pass CZML packets")

        # Log the complete CZML for debugging
        logger.info(f"Generated CZML with {len(czml)} packets")
        for i, packet in enumerate(czml):
            if "availability" in packet:
                logger.info(f"Packet {i} availability: {packet['availability']}")
            if "position" in packet and "epoch" in packet["position"]:
                logger.info(f"Packet {i} epoch: {packet['position']['epoch']}")

        return czml

    def _create_document_packet(self) -> Dict[str, Any]:
        """Create CZML document packet without clock settings to avoid conflicts"""
        return {
            "id": "document",
            "name": "Satellite Mission Planning",
            "version": "1.0",
            # NOTE: Removed clock configuration to prevent conflicts with React component clock
            # The React CesiumViewer component will handle all clock/timeline configuration
        }

    def _hex_to_rgba(self, hex_color: str) -> List[int]:
        """Convert hex color to RGBA list for CZML."""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return [r, g, b, 255]
        return [255, 215, 0, 255]  # Default gold

    def _get_satellite_color_rgba(self, sat_id: str, index: int) -> List[int]:
        """Get RGBA color for a satellite.

        Uses assigned color from satellite_colors dict, or falls back to palette.
        Supports any constellation size with automatic color generation for 9+ satellites.
        """
        if sat_id in self.satellite_colors:
            return self._hex_to_rgba(self.satellite_colors[sat_id])
        # Fall back to shared color palette (handles any constellation size)
        return get_satellite_color_rgba_by_index(index)

    def _generate_positions_for_satellite(self, sat_orbit: Any) -> List[float]:
        """Generate position array for a specific satellite orbit."""
        positions: List[float] = []
        if self.start_time is None or self.end_time is None:
            return positions

        time_step = timedelta(minutes=2)
        current_time: datetime = self.start_time

        while current_time <= self.end_time:
            try:
                lat, lon, alt = sat_orbit.get_position(current_time)
                seconds_from_start = (current_time - self.start_time).total_seconds()
                positions.extend([seconds_from_start, lon, lat, alt * 1000])
            except Exception as e:
                logger.warning(f"Failed to get position at {current_time}: {e}")
            current_time = current_time + time_step

        return positions

    def _create_satellite_packet_for(
        self, sat_id: str, sat_orbit: Any, color_rgba: List[int]
    ) -> Dict[str, Any]:
        """Create satellite packet for a specific satellite with custom color.

        2025 Best Practice: Each satellite in constellation gets distinct visualization.
        """
        positions = self._generate_positions_for_satellite(sat_orbit)
        satellite_name = getattr(
            sat_orbit,
            "satellite_name",
            getattr(sat_orbit, "name", sat_id.replace("sat_", "")),
        )

        # Create semi-transparent version for path
        path_color = color_rgba[:3] + [180]  # Reduce alpha for path

        return {
            "id": sat_id,
            "name": satellite_name,
            "position": {
                "epoch": self._format_czml_date(self.start_time),
                "cartographicDegrees": positions,
            },
            "point": {
                "pixelSize": 12,
                "color": {"rgba": color_rgba},
                "outlineColor": {"rgba": [0, 0, 0, 255]},
                "outlineWidth": 2,
                "heightReference": "NONE",
                "scaleByDistance": {"nearFarScalar": [1000000, 1.0, 10000000, 0.5]},
            },
            "label": {
                "text": satellite_name,
                "font": "18px sans-serif",
                "style": "FILL_AND_OUTLINE",
                "fillColor": {"rgba": [255, 255, 255, 255]},
                "outlineColor": {"rgba": [0, 0, 0, 255]},
                "outlineWidth": 3,
                "pixelOffset": {"cartesian2": [0, -40]},
                "horizontalOrigin": "CENTER",
                "verticalOrigin": "BOTTOM",
                "scaleByDistance": {"nearFarScalar": [1000000, 1.0, 10000000, 0.5]},
            },
            "path": {
                "material": {"solidColor": {"color": {"rgba": path_color}}},
                "width": 2,
                "leadTime": 3600,
                "trailTime": 3600,
                "resolution": 120,
            },
        }

    def _create_ground_track_for(
        self, sat_id: str, sat_orbit: Any, color_rgba: List[int]
    ) -> Dict[str, Any]:
        """Create ground track for a specific satellite.

        Ground track is the satellite position projected onto Earth's surface.
        """
        positions: List[float] = []
        if self.start_time is None or self.end_time is None:
            return {"id": f"{sat_id}_ground_track", "name": "Ground Track"}

        time_step = timedelta(minutes=2)
        current_time: datetime = self.start_time

        while current_time <= self.end_time:
            try:
                lat, lon, _ = sat_orbit.get_position(current_time)
                seconds_from_start = (current_time - self.start_time).total_seconds()
                positions.extend(
                    [seconds_from_start, lon, lat, 0]
                )  # Altitude 0 for ground track
            except Exception as e:
                logger.warning(
                    f"Failed to get ground track position at {current_time}: {e}"
                )
            current_time = current_time + time_step

        # Semi-transparent ground track
        track_color = color_rgba[:3] + [100]

        satellite_name = getattr(
            sat_orbit, "satellite_name", sat_id.replace("sat_", "")
        )

        return {
            "id": f"{sat_id}_ground_track",
            "name": f"{satellite_name} Ground Track",
            "position": {
                "epoch": self._format_czml_date(self.start_time),
                "cartographicDegrees": positions,
            },
            "path": {
                "material": {"solidColor": {"color": {"rgba": track_color}}},
                "width": 1,
                "leadTime": 1800,
                "trailTime": 3600,
                "resolution": 120,
            },
        }

    def _create_satellite_packet(self) -> Dict[str, Any]:
        """Create satellite packet with orbital track"""
        # Generate satellite positions over time
        positions = self._generate_satellite_positions()

        satellite_name = getattr(
            self.satellite,
            "satellite_name",
            getattr(self.satellite, "name", "Satellite"),
        )

        return {
            "id": f"sat_{satellite_name}",
            "name": satellite_name,
            "position": {
                "epoch": self._format_czml_date(self.start_time),
                "cartographicDegrees": positions,
            },
            "point": {
                "pixelSize": 12,
                "color": {"rgba": [255, 255, 0, 255]},  # Yellow
                "outlineColor": {"rgba": [0, 0, 0, 255]},
                "outlineWidth": 2,
                "heightReference": "NONE",
                "scaleByDistance": {"nearFarScalar": [1000000, 1.0, 10000000, 0.5]},
            },
            "label": {
                "text": satellite_name,
                "font": "18px sans-serif",
                "style": "FILL_AND_OUTLINE",
                "fillColor": {"rgba": [255, 255, 255, 255]},
                "outlineColor": {"rgba": [0, 0, 0, 255]},
                "outlineWidth": 3,
                "pixelOffset": {"cartesian2": [0, -40]},
                "horizontalOrigin": "CENTER",
                "verticalOrigin": "BOTTOM",
                "scaleByDistance": {"nearFarScalar": [1000000, 1.0, 10000000, 0.5]},
            },
            "path": {
                "material": {
                    "solidColor": {
                        "color": {"rgba": [255, 255, 0, 180]}
                    }  # Solid yellow
                },
                "width": 3,
                "leadTime": 3600,  # 1 hour lead
                "trailTime": 3600,  # 1 hour trail
                "resolution": 120,
                "show": False,  # Hide 3D orbital path, will show ground-clamped polyline instead
            },
        }

    def _create_ground_track_dynamic(self) -> Dict[str, Any]:
        """Create dynamic ground track with lead/trail time (shadow satellite at ground level)"""
        satellite_name = getattr(
            self.satellite,
            "satellite_name",
            getattr(self.satellite, "name", "Satellite"),
        )

        # Generate ground positions (same as satellite positions but at altitude 0)
        ground_positions: List[float] = []
        if self.start_time is None or self.end_time is None or self.satellite is None:
            return {
                "id": "satellite_ground_track",
                "name": f"{satellite_name} Ground Track",
            }

        current_time: datetime = self.start_time
        time_step = timedelta(minutes=1)  # 1-minute intervals for smoother polar tracks

        while current_time <= self.end_time:
            try:
                lat, lon, alt = self.satellite.get_position(current_time)
                seconds_from_epoch = (current_time - self.start_time).total_seconds()
                ground_positions.extend(
                    [seconds_from_epoch, lon, lat, 0]
                )  # Altitude = 0
            except Exception as e:
                logger.warning(f"Failed to get ground position at {current_time}: {e}")

            current_time = current_time + time_step

        logger.info(
            f"Generated dynamic ground track with {len(ground_positions)//4} position samples"
        )

        return {
            "id": "satellite_ground_track",
            "name": f"{satellite_name} Ground Track",
            "position": {
                "epoch": self._format_czml_date(self.start_time),
                "cartographicDegrees": ground_positions,
            },
            "path": {
                "material": {
                    "solidColor": {"color": {"rgba": [255, 255, 0, 180]}}  # Yellow
                },
                "width": 2,
                "leadTime": 3600,  # 1 hour lead (same as satellite)
                "trailTime": 3600,  # 1 hour trail
                "resolution": 120,
            },
        }

    def _create_pointing_cone_packet(self) -> Optional[Dict[str, Any]]:
        """
        Create CZML packet for satellite sensor footprint (imaging missions).

        IMPORTANT: This visualizes the SENSOR FOV (field of view), NOT spacecraft pointing limits.
        The footprint radius is calculated from sensor_fov_half_angle_deg, which is the
        payload characteristic, independent of spacecraft bus agility.

        Returns:
            CZML packet for sensor footprint ellipse, or None if not applicable
        """
        if (
            self.mission_type != "imaging"
            or not self.sensor_fov_half_angle_deg
            or self.sensor_fov_half_angle_deg <= 0
        ):
            logger.debug(
                f"⏭️ Skipping footprint: mission_type={self.mission_type}, sensor_fov_half_angle_deg={self.sensor_fov_half_angle_deg}"
            )
            return None

        if self.start_time is None or self.end_time is None or self.satellite is None:
            return None

        logger.debug(
            f"🛰️ Creating sensor footprint visualization: FOV half-angle={self.sensor_fov_half_angle_deg}°"
        )

        # Generate footprint positions at same time points as satellite
        polygon_positions: List[float] = []
        current_time: datetime = self.start_time
        time_step = timedelta(minutes=2)  # Match satellite sampling
        sample_count = 0

        while current_time <= self.end_time:
            try:
                # Get satellite position
                sat_lat, sat_lon, alt_km = self.satellite.get_position(current_time)
                seconds_from_epoch = (current_time - self.start_time).total_seconds()

                # Calculate footprint based on sensor FOV and altitude
                footprint_points = self._calculate_sensor_footprint(
                    sat_lat, sat_lon, alt_km, self.sensor_fov_half_angle_deg
                )

                # For time-dynamic polygon, format: [time, lon1, lat1, height1, lon2, lat2, height2, ...]
                polygon_positions.append(seconds_from_epoch)
                polygon_positions.extend(footprint_points)
                sample_count += 1

            except Exception as e:
                logger.error(f"❌ Failed to generate footprint at {current_time}: {e}")

            current_time = current_time + time_step

        if not polygon_positions:
            logger.warning("⚠️ No valid footprint positions generated")
            return None

        logger.info(
            f"✅ Generated sensor footprint: {sample_count} samples, {self.sensor_fov_half_angle_deg}° angle"
        )

        # Create simplified ellipse footprint that follows satellite
        # Extract satellite positions for ellipse center
        ellipse_positions = []
        radius_data = []  # Time-dynamic radius based on altitude
        current_time = self.start_time
        time_step = timedelta(minutes=2)

        while current_time <= self.end_time:
            sat_lat, sat_lon, alt_km = self.satellite.get_position(current_time)
            seconds_from_epoch = (current_time - self.start_time).total_seconds()
            ellipse_positions.extend([seconds_from_epoch, sat_lon, sat_lat, 0])

            # Calculate footprint radius dynamically based on current altitude
            # IMPORTANT: Uses SENSOR FOV, not spacecraft roll limit!
            # Radius = altitude * tan(sensor_fov_half_angle_deg)
            current_radius_m = (
                alt_km * 1000 * math.tan(math.radians(self.sensor_fov_half_angle_deg))
            )
            current_radius_m = min(current_radius_m, 700000)  # Cap at 700km

            # Add time-tagged radius values
            radius_data.extend([seconds_from_epoch, current_radius_m])

            current_time += time_step

        # Log the actual radius being used for debugging
        sample_radius_km = radius_data[1] / 1000 if len(radius_data) > 1 else 0
        logger.info(
            f"📏 Sensor footprint: {self.sensor_fov_half_angle_deg}° FOV half-angle → ~{sample_radius_km:.0f}km radius at {alt_km:.0f}km altitude"
        )

        return {
            "id": "pointing_cone",
            "name": "Sensor Footprint",
            "show": True,
            "allowPicking": False,
            "availability": f"{self._format_czml_date(self.start_time)}/{self._format_czml_date(self.end_time)}",
            "position": {
                "epoch": self._format_czml_date(self.start_time),
                "cartographicDegrees": ellipse_positions,
            },
            "ellipse": {
                "semiMajorAxis": {
                    "epoch": self._format_czml_date(self.start_time),
                    "number": radius_data,  # Time-dynamic radius
                },
                "semiMinorAxis": {
                    "epoch": self._format_czml_date(self.start_time),
                    "number": radius_data,  # Same as major axis for circle
                },
                "height": 0,
                "material": {
                    "solidColor": {
                        "color": {"rgba": [255, 165, 0, 40]}  # Semi-transparent orange
                    }
                },
                "outline": True,
                "outlineColor": {"rgba": [255, 140, 0, 200]},
                "outlineWidth": 2,
                "numberOfVerticalLines": 0,
            },
        }

    def _create_agility_envelope_packet_for(
        self, sat_id: str, sat_orbit: Any, color_rgba: List[int], idx: int
    ) -> Optional[Dict[str, Any]]:
        """
        Create CZML packet for satellite agility envelope (max pointing capability).

        This visualizes the MAX SPACECRAFT ROLL limit - the full area where the satellite
        can slew and point its sensor. This is larger than the sensor FOV and shows
        all POSSIBLE imaging opportunities.

        Each satellite in a constellation gets its own envelope with matching color.

        Args:
            sat_id: Satellite identifier
            sat_orbit: Satellite orbit object
            color_rgba: RGBA color matching satellite ground track
            idx: Index of satellite in constellation

        Returns:
            CZML packet for agility envelope ellipse, or None if not applicable
        """
        if (
            self.mission_type != "imaging"
            or not self.max_spacecraft_roll_deg
            or self.max_spacecraft_roll_deg <= 0
        ):
            logger.debug(
                f"⏭️ Skipping agility envelope for {sat_id}: mission_type={self.mission_type}, max_roll={self.max_spacecraft_roll_deg}"
            )
            return None

        if self.start_time is None or self.end_time is None:
            return None

        satellite_name = getattr(
            sat_orbit, "satellite_name", sat_id.replace("sat_", "")
        )
        logger.debug(
            f"🎯 Creating agility envelope for {satellite_name}: Max roll={self.max_spacecraft_roll_deg}°"
        )

        # Generate envelope positions at same time points as satellite
        ellipse_positions: List[float] = []
        radius_data: List[float] = []  # Time-dynamic radius based on altitude
        current_time: datetime = self.start_time
        time_step = timedelta(minutes=2)
        alt_km: float = 0.0

        while current_time <= self.end_time:
            sat_lat, sat_lon, alt_km = sat_orbit.get_position(current_time)
            seconds_from_epoch = (current_time - self.start_time).total_seconds()
            ellipse_positions.extend([seconds_from_epoch, sat_lon, sat_lat, 0])

            # Calculate envelope radius based on max spacecraft roll
            # Radius = altitude * tan(max_spacecraft_roll_deg)
            current_radius_m = (
                alt_km * 1000 * math.tan(math.radians(self.max_spacecraft_roll_deg))
            )
            current_radius_m = min(current_radius_m, 700000)  # Cap at 700km

            # Add time-tagged radius values
            radius_data.extend([seconds_from_epoch, current_radius_m])

            current_time = current_time + time_step

        # Log the actual radius being used
        sample_radius_km = radius_data[1] / 1000 if len(radius_data) > 1 else 0
        logger.info(
            f"📏 Agility envelope for {satellite_name}: {self.max_spacecraft_roll_deg}° max roll → ~{sample_radius_km:.0f}km radius at {alt_km:.0f}km altitude"
        )

        # Create color variants from satellite color
        # Fill: very transparent (alpha=30), Outline: semi-transparent (alpha=150)
        fill_color = [color_rgba[0], color_rgba[1], color_rgba[2], 30]
        outline_color = [color_rgba[0], color_rgba[1], color_rgba[2], 150]

        return {
            "id": f"agility_envelope_{sat_id}",
            "name": f"{satellite_name} Pointing Envelope",
            "show": True,
            "allowPicking": False,
            "availability": f"{self._format_czml_date(self.start_time)}/{self._format_czml_date(self.end_time)}",
            "position": {
                "epoch": self._format_czml_date(self.start_time),
                "cartographicDegrees": ellipse_positions,
            },
            "ellipse": {
                "semiMajorAxis": {
                    "epoch": self._format_czml_date(self.start_time),
                    "number": radius_data,  # Time-dynamic radius
                },
                "semiMinorAxis": {
                    "epoch": self._format_czml_date(self.start_time),
                    "number": radius_data,  # Same as major axis for circle
                },
                "height": 0,
                "material": {
                    "solidColor": {
                        "color": {"rgba": fill_color}  # Satellite color, transparent
                    }
                },
                "outline": True,
                "outlineColor": {"rgba": outline_color},
                "outlineWidth": 1,
                "numberOfVerticalLines": 0,
            },
        }

    def _optical_pass_description(
        self,
        target_name: str,
        sat_name: str,
        max_elevation: float,
        start_time: Any,
        max_elev_time: Any,
        end_time: Any,
    ) -> str:
        """Build HTML description for an optical pass CZML entity."""
        td = '<td style="color:#aaa">'
        start_s = self._format_czml_date(start_time)
        peak_s = self._format_czml_date(max_elev_time)
        end_s = self._format_czml_date(end_time)
        return (
            '<div style="background:rgba(17,24,39,.95);'
            'padding:12px;border-radius:8px;color:#fff">'
            '<h3 style="color:#00C8FF;margin:0 0 8px">'
            f"Optical Pass - {target_name}</h3>"
            '<table style="width:100%;font-size:13px">'
            f"<tr>{td}Satellite:</td><td>{sat_name}</td></tr>"
            f"<tr>{td}Max Elev:</td><td>{max_elevation:.1f}°</td></tr>"
            f"<tr>{td}Start:</td><td>{start_s}</td></tr>"
            f"<tr>{td}Peak:</td><td>{peak_s}</td></tr>"
            f"<tr>{td}End:</td><td>{end_s}</td></tr>"
            "</table></div>"
        )

    def _create_optical_pass_packets(self) -> List[Dict[str, Any]]:
        """
        Create CZML packets for optical pass visualization (one per pass).

        Each packet is a small highlighted circle at the target location,
        visible only during the pass window, with custom properties for
        deterministic picking and lock-mode integration.

        The opportunity_id follows the same format as the scheduler:
        {satellite_name}_{target_name}_{pass_index}_max
        """
        packets: List[Dict[str, Any]] = []

        # Build target lookup by name
        target_map = {t.name: t for t in self.targets}

        for idx, pass_detail in enumerate(self.passes):
            try:
                # Extract pass data (handles both object and dict forms)
                if isinstance(pass_detail, dict):
                    sat_name = pass_detail.get("satellite_name", "")
                    target_name = pass_detail.get("target_name", "")
                    start_time = pass_detail.get("start_time")
                    end_time = pass_detail.get("end_time")
                    max_elev_time = pass_detail.get("max_elevation_time")
                    max_elevation = pass_detail.get("max_elevation", 0)
                else:
                    sat_name = getattr(pass_detail, "satellite_name", "")
                    target_name = getattr(pass_detail, "target_name", "")
                    start_time = getattr(pass_detail, "start_time", None)
                    end_time = getattr(pass_detail, "end_time", None)
                    max_elev_time = getattr(pass_detail, "max_elevation_time", None)
                    max_elevation = getattr(pass_detail, "max_elevation", 0)

                target = target_map.get(target_name)
                if not target or not start_time or not end_time:
                    continue

                # Generate opportunity_id matching scheduler format
                opportunity_id = f"{sat_name}_{target_name}_{idx}_max"
                packet_id = f"optical_pass_{opportunity_id}"

                # Cyan/teal color for optical passes
                fill_rgba = [0, 200, 255, 50]
                outline_rgba = [0, 200, 255, 160]

                packet: Dict[str, Any] = {
                    "id": packet_id,
                    "name": f"Optical Pass - {target_name} ({sat_name})",
                    "description": self._optical_pass_description(
                        target_name,
                        sat_name,
                        max_elevation,
                        start_time,
                        max_elev_time,
                        end_time,
                    ),
                    "availability": (
                        f"{self._format_czml_date(start_time)}"
                        f"/{self._format_czml_date(end_time)}"
                    ),
                    "position": {
                        "cartographicDegrees": [
                            target.longitude,
                            target.latitude,
                            0,
                        ]
                    },
                    "ellipse": {
                        "semiMajorAxis": 15000,  # 15 km radius highlight
                        "semiMinorAxis": 15000,
                        "height": 0,
                        "material": {"solidColor": {"color": {"rgba": fill_rgba}}},
                        "outline": True,
                        "outlineColor": {"rgba": outline_rgba},
                        "outlineWidth": 2,
                    },
                    # Custom properties for deterministic picking
                    "properties": {
                        "opportunity_id": {"string": opportunity_id},
                        "target_id": {"string": target_name},
                        "satellite_id": {"string": sat_name},
                        "pass_index": {"number": idx},
                        "entity_type": {"string": "optical_pass"},
                        "imaging_time": {
                            "string": self._format_czml_date(
                                max_elev_time or start_time
                            )
                        },
                    },
                }

                packets.append(packet)

            except Exception as e:
                logger.error(f"Error creating optical pass packet {idx}: {e}")
                continue

        return packets

    def _calculate_sensor_footprint(
        self,
        sat_lat: float,
        sat_lon: float,
        alt_km: float,
        sensor_fov_half_angle_deg: float,
    ) -> list:
        """Calculate sensor footprint polygon on Earth's surface.

        IMPORTANT: This calculates the SENSOR FOV footprint, NOT spacecraft pointing limits.
        The footprint represents the area visible to the sensor payload.

        Args:
            sat_lat: Satellite latitude in degrees
            sat_lon: Satellite longitude in degrees
            alt_km: Satellite altitude in kilometers
            sensor_fov_half_angle_deg: Sensor field of view half-angle in degrees

        Returns:
            List of lon,lat,height triplets forming footprint polygon (54 values = 18 points)
        """
        import numpy as np

        # Earth radius in km
        earth_radius = 6371.0

        # Calculate footprint radius using spherical Earth approximation
        # For off-nadir pointing, use the slant range calculation
        sensor_fov_rad = math.radians(sensor_fov_half_angle_deg)

        # Maximum ground range for the given sensor FOV
        # Using spherical Earth and accounting for Earth curvature
        satellite_radius = earth_radius + alt_km

        # Calculate the angular radius of footprint on Earth's surface
        # This accounts for Earth curvature and sensor FOV angle
        cos_ground_angle = (earth_radius / satellite_radius) * math.cos(sensor_fov_rad)

        if cos_ground_angle > 1.0:  # No visibility
            ground_angle_rad: float = 0.0
        else:
            ground_angle_rad = math.acos(cos_ground_angle) - sensor_fov_rad

        # Convert to degrees
        ground_angle_deg = math.degrees(ground_angle_rad)

        # Generate circular footprint (18 points for smooth circle)
        footprint = []
        for i in range(18):
            azimuth = i * 20  # 20 degree increments
            azimuth_rad = math.radians(azimuth)

            # Calculate point on circle using great circle distance
            lat_rad = math.radians(sat_lat)
            lon_rad = math.radians(sat_lon)

            # Destination point given distance and bearing
            dest_lat = math.asin(
                math.sin(lat_rad) * math.cos(ground_angle_rad)
                + math.cos(lat_rad) * math.sin(ground_angle_rad) * math.cos(azimuth_rad)
            )

            dest_lon = lon_rad + math.atan2(
                math.sin(azimuth_rad) * math.sin(ground_angle_rad) * math.cos(lat_rad),
                math.cos(ground_angle_rad) - math.sin(lat_rad) * math.sin(dest_lat),
            )

            # Convert back to degrees and add to footprint with height=0
            footprint.extend([math.degrees(dest_lon), math.degrees(dest_lat), 0])

        return footprint

    def _create_target_packet(self, target: Any, index: int) -> Dict[str, Any]:
        """Create target marker packet with customizable color"""
        import base64

        # Get target color (default red if not specified)
        target_color = getattr(target, "color", None) or "#EF4444"

        # Convert hex color to RGB for SVG
        hex_color = target_color.lstrip("#")
        fill_color = f"#{hex_color}"

        # Calculate darker stroke color
        r = max(0, int(hex_color[0:2], 16) - 40)
        g = max(0, int(hex_color[2:4], 16) - 40)
        b = max(0, int(hex_color[4:6], 16) - 40)
        stroke_color = f"#{r:02x}{g:02x}{b:02x}"

        # Create simple map pin icon SVG with custom color
        targeting_svg = f"""<svg width="32" height="40" viewBox="0 0 32 40" xmlns="http://www.w3.org/2000/svg">
          <!-- Map Pin Icon -->
          <path d="M16 0C9.4 0 4 5.4 4 12c0 8 12 28 12 28s12-20 12-28c0-6.6-5.4-12-12-12z"
                fill="{fill_color}" stroke="{stroke_color}" stroke-width="2"/>
          <circle cx="16" cy="12" r="5" fill="#FFF"/>
        </svg>"""

        svg_base64 = base64.b64encode(targeting_svg.encode("utf-8")).decode("utf-8")

        return {
            "id": f"target_{index}",
            "name": target.name,
            "position": {"cartographicDegrees": [target.longitude, target.latitude, 0]},
            "billboard": {
                "image": f"data:image/svg+xml;base64,{svg_base64}",
                "width": 20,
                "height": 25,
                "verticalOrigin": "BOTTOM",  # Pin points to the ground
            },
            "point": {
                "pixelSize": 12,
                "color": {"rgba": [0, 120, 255, 255]},  # Blue
                "outlineColor": {"rgba": [255, 255, 255, 255]},
                "outlineWidth": 2,
                "show": False,  # Show billboard instead
            },
            "label": {
                "text": target.name,
                "font": "14px sans-serif",  # Match ground station font
                "style": "FILL_AND_OUTLINE",  # Match ground station text shadow
                "fillColor": {"rgba": [255, 255, 255, 255]},
                "outlineColor": {"rgba": [0, 0, 0, 255]},
                "outlineWidth": 3,  # Match ground station outline
                "pixelOffset": {
                    "cartesian2": [0, -30]
                },  # Adjusted for smaller pin icon
                "horizontalOrigin": "CENTER",
                "verticalOrigin": "BOTTOM",
            },
            "description": f"""
              <div style="background: rgba(17, 24, 39, 0.9); padding: 10px; border-radius: 5px;">
                <h3 style="color: #FF6B6B; margin: 0 0 10px 0;">{target.name}</h3>
                <p style="color: #FFF; margin: 5px 0;"><strong>Type:</strong> {getattr(target, 'type', 'Target Point')}</p>
                <p style="color: #FFF; margin: 5px 0;"><strong>Location:</strong> {target.latitude:.4f}°, {target.longitude:.4f}°</p>
                <p style="color: #FFF; margin: 5px 0;"><strong>Description:</strong> {getattr(target, 'description', 'Mission target location')}</p>
                <p style="color: #FFF; margin: 5px 0;"><strong>Target Type:</strong> {getattr(target, 'type', 'Unknown')}</p>
              </div>
            """,
        }

    def _generate_satellite_positions(self) -> List[float]:
        """Generate satellite positions over mission timeline"""
        positions: List[float] = []
        if self.start_time is None or self.end_time is None or self.satellite is None:
            return positions

        current_time: datetime = self.start_time
        time_step = timedelta(minutes=2)  # 2-minute intervals for smooth animation

        logger.info(
            f"Generating satellite positions from {self.start_time} to {self.end_time}"
        )

        while current_time <= self.end_time:
            try:
                lat, lon, alt = self.satellite.get_position(current_time)
                seconds_from_epoch = (current_time - self.start_time).total_seconds()

                # Validate all values are finite numbers
                if not all(
                    isinstance(x, (int, float))
                    and not (x != x or x == float("inf") or x == float("-inf"))
                    for x in [seconds_from_epoch, lon, lat, alt]
                ):
                    logger.error(
                        f"Invalid position values at {current_time}: seconds={seconds_from_epoch}, lon={lon}, lat={lat}, alt={alt}"
                    )
                    continue

                position_values = [
                    seconds_from_epoch,
                    lon,
                    lat,
                    alt * 1000,  # Convert km to meters
                ]
                positions.extend(position_values)

                if len(positions) <= 8:  # Log first 2 position entries
                    logger.info(f"Position at {current_time}: {position_values}")

            except Exception as e:
                logger.error(f"Failed to get satellite position at {current_time}: {e}")

            current_time = current_time + time_step

        logger.info(
            f"Generated {len(positions)//4} position samples, total array length: {len(positions)}"
        )
        return positions


def generate_mission_czml(
    satellite: Any,
    targets: Any,
    passes: Any,
    start_time: Any,
    end_time: Any,
    mission_type: Optional[str] = None,
    sensor_fov_half_angle_deg: Optional[float] = None,
    max_spacecraft_roll_deg: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Convenience function to generate CZML for a mission.

    Args:
        satellite: Satellite orbit object
        targets: List of ground targets
        passes: List of pass details
        start_time: Mission start time
        end_time: Mission end time
        mission_type: 'imaging' or 'communication'
        sensor_fov_half_angle_deg: Sensor FOV half-angle in degrees (actual camera FOV)
        max_spacecraft_roll_deg: Max spacecraft roll angle limit in degrees (agility envelope)

    Returns:
        List of CZML packets
    """
    logger.info(
        f"generate_mission_czml called with: mission_type={mission_type}, sensor_fov_half_angle_deg={sensor_fov_half_angle_deg}, max_roll={max_spacecraft_roll_deg}"
    )
    generator = CZMLGenerator(
        satellite=satellite,
        targets=targets,
        passes=passes,
        start_time=start_time,
        end_time=end_time,
        mission_type=mission_type,
        sensor_fov_half_angle_deg=sensor_fov_half_angle_deg,
        max_spacecraft_roll_deg=max_spacecraft_roll_deg,
    )
    return generator.generate()
