"""
Cartopy-based visualization module for satellite mission planning.

This module provides clean 2D world map visualizations including satellite
ground tracks, target points, and optional day/night terminator shading.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple, Union

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from cartopy.mpl.ticker import LatitudeFormatter, LongitudeFormatter

from .orbit import SatelliteOrbit
from .targets import GroundTarget

logger = logging.getLogger(__name__)


class Visualizer:
    """
    Creates beautiful satellite mission visualizations using Cartopy.

    This class provides methods to create clean 2D world map visualizations
    showing satellite ground tracks, target locations, and coverage areas.
    """

    def __init__(self, figsize: Tuple[float, float] = (15, 10)) -> None:
        """
        Initialize the visualizer.

        Args:
            figsize: Figure size as (width, height) in inches
        """
        self.figsize = figsize
        self.fig = None
        self.ax = None
        self._setup_plot_style()
        logger.info("Initialized Visualizer")

    def _setup_plot_style(self) -> None:
        """Set up matplotlib style for clean plots."""
        plt.style.use("default")
        plt.rcParams.update(
            {
                "font.size": 10,
                "axes.titlesize": 14,
                "axes.labelsize": 12,
                "xtick.labelsize": 10,
                "ytick.labelsize": 10,
                "legend.fontsize": 10,
                "figure.titlesize": 16,
            }
        )

    def create_world_map(
        self, projection: ccrs.Projection = None, extent: Optional[List[float]] = None
    ) -> Tuple[plt.Figure, plt.Axes]:
        """
        Create a world map with Cartopy.

        Args:
            projection: Cartopy projection (default: PlateCarree)
            extent: Map extent as [lon_min, lon_max, lat_min, lat_max]

        Returns:
            Tuple of (figure, axes)
        """
        if projection is None:
            projection = ccrs.PlateCarree()

        self.fig, self.ax = plt.subplots(
            figsize=self.figsize, subplot_kw={"projection": projection}
        )

        # Set map extent
        if extent:
            self.ax.set_extent(extent, crs=ccrs.PlateCarree())
        else:
            self.ax.set_global()

        # Add map features
        self.ax.add_feature(cfeature.COASTLINE, linewidth=0.8, color="black")
        self.ax.add_feature(cfeature.BORDERS, linewidth=0.5, color="gray")
        self.ax.add_feature(cfeature.OCEAN, color="lightblue", alpha=0.5)
        self.ax.add_feature(cfeature.LAND, color="lightgray", alpha=0.5)

        # Add gridlines
        gl = self.ax.gridlines(
            crs=ccrs.PlateCarree(),
            draw_labels=True,
            linewidth=0.5,
            color="gray",
            alpha=0.7,
            linestyle="--",
        )
        gl.top_labels = False
        gl.right_labels = False
        gl.xformatter = LongitudeFormatter()
        gl.yformatter = LatitudeFormatter()

        return self.fig, self.ax

    def plot_ground_track(
        self,
        satellite: SatelliteOrbit,
        start_time: datetime,
        end_time: datetime,
        time_step_minutes: float = 1.0,
        color: str = "red",
        linewidth: float = 2.0,
        alpha: float = 0.8,
        label: Optional[str] = None,
    ) -> None:
        """
        Plot satellite ground track on the map.

        Args:
            satellite: SatelliteOrbit instance
            start_time: Start time for ground track
            end_time: End time for ground track
            time_step_minutes: Time step between points in minutes
            color: Line color
            linewidth: Line width
            alpha: Line transparency
            label: Legend label
        """
        if self.ax is None:
            self.create_world_map()

        # Get ground track data
        ground_track = satellite.get_ground_track(
            start_time, end_time, time_step_minutes
        )

        if not ground_track:
            logger.warning("No ground track data available")
            return

        # Extract coordinates
        lats = [point[1] for point in ground_track]
        lons = [point[2] for point in ground_track]

        # Handle longitude wrapping for continuous plotting
        lons_wrapped, lats_wrapped = self._handle_longitude_wrapping(lons, lats)

        # Plot ground track
        track_label = label or f"{satellite.satellite_name} Ground Track"
        self.ax.plot(
            lons_wrapped,
            lats_wrapped,
            color=color,
            linewidth=linewidth,
            alpha=alpha,
            label=track_label,
            transform=ccrs.PlateCarree(),
        )

        # Mark start and end points
        if ground_track:
            start_lat, start_lon = ground_track[0][1], ground_track[0][2]
            end_lat, end_lon = ground_track[-1][1], ground_track[-1][2]

            self.ax.plot(
                start_lon,
                start_lat,
                "g^",
                markersize=10,
                label="Start",
                transform=ccrs.PlateCarree(),
            )
            self.ax.plot(
                end_lon,
                end_lat,
                "rs",
                markersize=8,
                label="End",
                transform=ccrs.PlateCarree(),
            )

        logger.info(f"Plotted ground track with {len(ground_track)} points")

    def _handle_longitude_wrapping(
        self, lons: List[float], lats: List[float]
    ) -> Tuple[List[float], List[float]]:
        """
        Handle longitude wrapping for continuous ground track plotting.

        Args:
            lons: List of longitude values
            lats: List of latitude values

        Returns:
            Tuple of (wrapped_lons, corresponding_lats)
        """
        wrapped_lons = []
        wrapped_lats = []

        for i, (lon, lat) in enumerate(zip(lons, lats)):
            if i > 0:
                # Check for large longitude jumps (crossing date line)
                lon_diff = abs(lon - lons[i - 1])
                if lon_diff > 180:
                    # Insert NaN to break the line
                    wrapped_lons.append(np.nan)
                    wrapped_lats.append(np.nan)

            wrapped_lons.append(lon)
            wrapped_lats.append(lat)

        return wrapped_lons, wrapped_lats

    def plot_targets(
        self,
        targets: List[GroundTarget],
        marker: str = "o",
        color: str = "blue",
        markersize: float = 8,
        alpha: float = 0.8,
    ) -> None:
        """
        Plot ground targets on the map.

        Args:
            targets: List of GroundTarget instances
            marker: Marker style
            color: Marker color
            markersize: Marker size
            alpha: Marker transparency
        """
        if self.ax is None:
            self.create_world_map()

        for target in targets:
            self.ax.plot(
                target.longitude,
                target.latitude,
                marker=marker,
                color=color,
                markersize=markersize,
                alpha=alpha,
                transform=ccrs.PlateCarree(),
                label=target.name if len(targets) <= 5 else None,
            )

            # Add target name as text annotation
            self.ax.text(
                target.longitude + 2,
                target.latitude + 2,
                target.name,
                fontsize=9,
                transform=ccrs.PlateCarree(),
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7),
            )

        logger.info(f"Plotted {len(targets)} targets")

    def plot_coverage_circles(
        self,
        targets: List[GroundTarget],
        satellite: Optional[SatelliteOrbit] = None,
        satellite_altitude_km: Optional[float] = None,
        color: str = "#1C327B",
        alpha: float = 0.2,
        mission_duration_hours: float = 120,
        start_time: datetime = None,
    ) -> None:
        """
        Plot subsatellite coverage areas around targets using correct coverage formula.

        Args:
            targets: List of GroundTarget instances
            satellite: SatelliteOrbit instance (preferred - gets actual altitude from TLE)
            satellite_altitude_km: Manual altitude override (deprecated - use satellite parameter)
            color: Circle border color
            alpha: Fill transparency
            mission_duration_hours: Mission duration (not used in calculation)
            start_time: Mission start time (not used in calculation)
        """
        if self.ax is None:
            self.create_world_map()

        # Physical constants
        earth_radius = 6371.0  # km

        # Determine satellite altitude - prefer actual TLE data over hardcoded value
        if satellite is not None:
            # Get actual altitude from TLE data at current time or start_time
            reference_time = start_time if start_time else datetime.utcnow()
            try:
                _, _, actual_altitude_km = satellite.get_position(reference_time)
                logger.info(
                    f"Using actual satellite altitude from TLE: {actual_altitude_km:.1f} km"
                )
            except Exception as e:
                logger.warning(f"Could not get altitude from TLE, using fallback: {e}")
                actual_altitude_km = satellite_altitude_km or 600.0
        else:
            actual_altitude_km = satellite_altitude_km or 600.0
            logger.warning(
                f"Using hardcoded altitude: {actual_altitude_km:.1f} km (TLE data not available)"
            )

        for target in targets:
            # Calculate subsatellite coverage footprint using correct formula
            elevation_rad = np.radians(target.elevation_mask)
            Re = earth_radius  # Earth radius
            h = actual_altitude_km  # Actual satellite altitude from TLE

            # CORRECT FORMULA: Subsatellite Coverage Calculation
            # This calculates the coverage radius on Earth's surface from the subsatellite point
            # where communication is possible at the minimum elevation angle.
            #
            # Formula: cos(λ) = (Re/(Re+h)) × cos(ε)
            #          d = Re × λ
            # Where:
            #   λ = central angle from subsatellite point to coverage edge
            #   ε = elevation mask angle
            #   d = coverage radius on Earth's surface

            # Step 1: Calculate central angle
            cos_lambda = (Re / (Re + h)) * np.cos(elevation_rad)
            lambda_rad = np.arccos(cos_lambda)
            lambda_deg = np.degrees(lambda_rad)

            # Step 2: Calculate coverage radius on Earth's surface
            coverage_radius_km = Re * lambda_rad

            # This represents the area on Earth where communication is possible
            # when the satellite passes overhead at or above the elevation mask.
            # Any ground station within this radius can communicate with the satellite
            # when it's directly overhead.

            # Convert to degrees with proper latitude correction
            lat_rad = np.radians(target.latitude)
            coverage_radius_lat = coverage_radius_km / 111.32  # degrees latitude
            coverage_radius_lon = coverage_radius_km / (
                111.32 * np.cos(lat_rad)
            )  # degrees longitude

            # Use average for circular approximation
            coverage_radius_deg = (coverage_radius_lat + coverage_radius_lon) / 2

            # Create filled circle with border
            circle = plt.Circle(
                (target.longitude, target.latitude),
                coverage_radius_deg,
                facecolor=color,
                edgecolor=color,
                alpha=alpha,
                transform=ccrs.PlateCarree(),
                fill=True,
                linewidth=2,
            )
            self.ax.add_patch(circle)

            # Add debug info with subsatellite coverage physics
            logger.info(f"Subsatellite coverage for {target.name}:")
            logger.info(f"  Elevation mask: {target.elevation_mask:.1f}°")
            logger.info(f"  Satellite altitude: {actual_altitude_km:.1f} km")
            logger.info(f"  Central angle: {lambda_deg:.2f}°")
            logger.info(
                f"  Coverage radius: {coverage_radius_km:.1f} km = {coverage_radius_deg:.2f}°"
            )
            logger.info(f"  Formula: cos(λ) = (Re/(Re+h)) × cos(ε), d = Re × λ")

        logger.info(f"Plotted subsatellite coverage areas for {len(targets)} targets")

    def add_day_night_terminator(self, timestamp: datetime) -> None:
        """
        Add day/night terminator line to the map.

        Args:
            timestamp: UTC datetime for terminator calculation
        """
        if self.ax is None:
            self.create_world_map()

        # Simplified terminator calculation
        # Solar declination angle
        day_of_year = timestamp.timetuple().tm_yday
        declination = 23.45 * np.sin(np.radians(360 * (284 + day_of_year) / 365))

        # Hour angle
        hour_angle = 15 * (
            timestamp.hour + timestamp.minute / 60 + timestamp.second / 3600 - 12
        )

        # Create terminator line
        lats = np.linspace(-90, 90, 180)
        lons = []

        for lat in lats:
            try:
                # Calculate longitude where sun is at horizon
                cos_hour_angle = -np.tan(np.radians(lat)) * np.tan(
                    np.radians(declination)
                )

                if abs(cos_hour_angle) <= 1:
                    local_hour_angle = np.degrees(np.arccos(cos_hour_angle))
                    lon = hour_angle - local_hour_angle

                    # Normalize longitude
                    while lon > 180:
                        lon -= 360
                    while lon < -180:
                        lon += 360

                    lons.append(lon)
                else:
                    lons.append(np.nan)
            except Exception:
                lons.append(np.nan)

        # Plot terminator
        self.ax.plot(
            lons,
            lats,
            color="orange",
            linewidth=2,
            alpha=0.7,
            label="Day/Night Terminator",
            transform=ccrs.PlateCarree(),
        )

        logger.info(f"Added day/night terminator for {timestamp}")

    def add_title_and_legend(
        self, title: str, show_legend: bool = True, legend_location: str = "upper right"
    ) -> None:
        """
        Add title and legend to the plot.

        Args:
            title: Plot title
            show_legend: Whether to show legend
            legend_location: Legend location
        """
        if self.ax is None:
            logger.warning("No plot created yet")
            return

        self.ax.set_title(title, fontsize=16, fontweight="bold", pad=20)

        if show_legend:
            self.ax.legend(
                loc=legend_location, frameon=True, fancybox=True, shadow=True
            )

    def save_map(
        self,
        filename: Union[str, Path],
        dpi: int = 300,
        bbox_inches: str = "tight",
        facecolor: str = "white",
    ) -> None:
        """
        Save the map to file.

        Args:
            filename: Output filename
            dpi: Resolution in dots per inch
            bbox_inches: Bounding box setting
            facecolor: Background color
        """
        if self.fig is None:
            logger.error("No figure to save")
            return

        try:
            self.fig.savefig(
                filename,
                dpi=dpi,
                bbox_inches=bbox_inches,
                facecolor=facecolor,
                edgecolor="none",
            )
            logger.info(f"Saved map to {filename}")
        except Exception as e:
            logger.error(f"Error saving map: {e}")
            raise

    def show(self) -> None:
        """Display the plot."""
        if self.fig is None:
            logger.error("No figure to show")
            return

        plt.tight_layout()
        plt.show()

    def clear(self) -> None:
        """Clear the current plot."""
        if self.fig is not None:
            plt.close(self.fig)
            self.fig = None
            self.ax = None
        logger.info("Cleared plot")


def create_mission_overview_plot(
    satellite: SatelliteOrbit,
    targets: List[GroundTarget],
    start_time: datetime,
    duration_hours: float = 24,
    output_file: Optional[str] = None,
) -> None:
    """
    Create a comprehensive mission overview plot.

    Args:
        satellite: SatelliteOrbit instance
        targets: List of ground targets
        start_time: Mission start time
        duration_hours: Mission duration in hours
        output_file: Optional output filename
    """
    end_time = start_time + timedelta(hours=duration_hours)

    # Create visualizer
    viz = Visualizer(figsize=(16, 10))
    viz.create_world_map()

    # Plot ground track
    viz.plot_ground_track(satellite, start_time, end_time, color="#2396EF", linewidth=2)

    # Plot targets
    viz.plot_targets(targets, color="blue", markersize=6)

    # Add coverage circles with mission parameters
    viz.plot_coverage_circles(
        targets,
        satellite=satellite,
        alpha=0.2,
        mission_duration_hours=duration_hours,
        start_time=start_time,
    )

    # Add day/night terminator for start time
    viz.add_day_night_terminator(start_time)

    # Add title and legend
    title = (
        f"Mission Overview: {satellite.satellite_name}\n"
        f"{start_time.strftime('%Y-%m-%d %H:%M UTC')} - "
        f"{end_time.strftime('%Y-%m-%d %H:%M UTC')}"
    )
    viz.add_title_and_legend(title)

    # Save or show
    if output_file:
        viz.save_map(output_file)
    else:
        viz.show()

    logger.info("Created mission overview plot")
