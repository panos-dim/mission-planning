#!/usr/bin/env python3
"""
Advanced Visualization Example

This example demonstrates advanced visualization capabilities including
custom map projections, coverage circles, and day/night terminator.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mission_planner import SatelliteOrbit, GroundTarget, Visualizer
from mission_planner.utils import setup_logging, create_sample_tle_file
import cartopy.crs as ccrs


def create_custom_visualization():
    """Create advanced visualization with custom features."""
    
    setup_logging("INFO")
    
    print("=== Advanced Visualization Example ===\n")
    
    # Create sample data
    tle_file = Path(__file__).parent.parent / "data" / "sample_satellites.tle"
    tle_file.parent.mkdir(exist_ok=True)
    create_sample_tle_file(tle_file)
    
    # Load satellite
    satellite = SatelliteOrbit.from_tle_file(tle_file, "ISS (ZARYA)")
    
    # Define targets in different regions
    targets = [
        GroundTarget("New York", 40.7128, -74.0060, 10.0),
        GroundTarget("London", 51.5074, -0.1278, 10.0),
        GroundTarget("Tokyo", 35.6762, 139.6503, 10.0),
        GroundTarget("Sydney", -33.8688, 151.2093, 10.0),
        GroundTarget("Cape Town", -33.9249, 18.4241, 10.0),
        GroundTarget("São Paulo", -23.5505, -46.6333, 10.0),
    ]
    
    # Time setup
    start_time = datetime.utcnow()
    duration_hours = 3  # Shorter duration for cleaner visualization
    
    print(f"Creating visualization for {satellite.satellite_name}")
    print(f"Time period: {duration_hours} hours from {start_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Targets: {len(targets)} locations worldwide\n")
    
    # Create output directory
    output_dir = Path(__file__).parent.parent / "output" / "advanced_viz"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Example 1: Global view with Mollweide projection
    print("Creating global view (Mollweide projection)...")
    viz1 = Visualizer(figsize=(16, 10))
    viz1.create_world_map(projection=ccrs.Mollweide())
    
    # Plot ground track
    viz1.plot_ground_track(
        satellite, start_time, start_time + timedelta(hours=duration_hours),
        color='red', linewidth=2.5, alpha=0.8
    )
    
    # Plot targets
    viz1.plot_targets(targets, color='blue', markersize=10)
    
    # Add coverage circles
    viz1.plot_coverage_circles(targets, satellite_altitude_km=400, alpha=0.2)
    
    # Add day/night terminator
    viz1.add_day_night_terminator(start_time)
    
    viz1.add_title_and_legend(
        f"Global Satellite Coverage: {satellite.satellite_name}\n"
        f"Mollweide Projection - {start_time.strftime('%Y-%m-%d %H:%M UTC')}"
    )
    
    viz1.save_map(output_dir / "global_mollweide.png")
    viz1.clear()
    
    # Example 2: North America focus with Lambert Conformal Conic
    print("Creating North America focus...")
    viz2 = Visualizer(figsize=(14, 10))
    viz2.create_world_map(
        projection=ccrs.LambertConformal(central_longitude=-100, central_latitude=45),
        extent=[-140, -60, 20, 70]  # North America bounds
    )
    
    # Filter targets for North America
    na_targets = [t for t in targets if -140 <= t.longitude <= -60 and 20 <= t.latitude <= 70]
    na_targets.append(GroundTarget("Houston", 29.7604, -95.3698, 10.0))
    na_targets.append(GroundTarget("Vancouver", 49.2827, -123.1207, 10.0))
    
    viz2.plot_ground_track(
        satellite, start_time, start_time + timedelta(hours=duration_hours),
        color='darkred', linewidth=3, alpha=0.9
    )
    
    viz2.plot_targets(na_targets, color='darkblue', markersize=12)
    viz2.plot_coverage_circles(na_targets, satellite_altitude_km=400, alpha=0.25, color='green')
    
    viz2.add_title_and_legend(
        f"North America Coverage: {satellite.satellite_name}\n"
        f"Lambert Conformal Conic - {start_time.strftime('%Y-%m-%d %H:%M UTC')}"
    )
    
    viz2.save_map(output_dir / "north_america_lambert.png")
    viz2.clear()
    
    # Example 3: Polar view (North Pole)
    print("Creating polar view...")
    viz3 = Visualizer(figsize=(12, 12))
    viz3.create_world_map(
        projection=ccrs.NorthPolarStereo(),
        extent=[-180, 180, 60, 90]  # Arctic region
    )
    
    # Add some Arctic targets
    arctic_targets = [
        GroundTarget("Svalbard", 78.2232, 15.6267, 5.0),
        GroundTarget("Barrow", 71.2906, -156.7886, 5.0),
        GroundTarget("Alert", 82.5018, -62.3481, 5.0),
    ]
    
    viz3.plot_ground_track(
        satellite, start_time, start_time + timedelta(hours=duration_hours),
        color='purple', linewidth=2, alpha=0.8
    )
    
    viz3.plot_targets(arctic_targets, color='orange', markersize=10)
    viz3.plot_coverage_circles(arctic_targets, satellite_altitude_km=400, alpha=0.3, color='red')
    
    viz3.add_title_and_legend(
        f"Arctic Coverage: {satellite.satellite_name}\n"
        f"North Polar Stereographic - {start_time.strftime('%Y-%m-%d %H:%M UTC')}"
    )
    
    viz3.save_map(output_dir / "arctic_polar.png")
    viz3.clear()
    
    # Example 4: Multi-orbit ground track
    print("Creating extended ground track...")
    viz4 = Visualizer(figsize=(18, 10))
    viz4.create_world_map()
    
    # Plot multiple orbital periods
    orbital_period = satellite.get_orbital_period()
    extended_duration = orbital_period * 3  # 3 orbits
    
    viz4.plot_ground_track(
        satellite, start_time, start_time + extended_duration,
        time_step_minutes=0.5,  # Higher resolution
        color='red', linewidth=1.5, alpha=0.7
    )
    
    # Plot all targets
    viz4.plot_targets(targets, color='blue', markersize=8)
    
    # Add terminator for start time
    viz4.add_day_night_terminator(start_time)
    
    viz4.add_title_and_legend(
        f"Extended Ground Track: {satellite.satellite_name}\n"
        f"3 Orbital Periods (~{extended_duration.total_seconds()/3600:.1f} hours) from {start_time.strftime('%Y-%m-%d %H:%M UTC')}"
    )
    
    viz4.save_map(output_dir / "extended_ground_track.png")
    viz4.clear()
    
    print(f"\n✓ Advanced visualizations created!")
    print(f"✓ Output directory: {output_dir}")
    print("Files created:")
    print("  • global_mollweide.png - Global view with Mollweide projection")
    print("  • north_america_lambert.png - North America with Lambert Conformal Conic")
    print("  • arctic_polar.png - Arctic region with North Polar Stereographic")
    print("  • extended_ground_track.png - Multi-orbit ground track")
    
    print("\n=== Advanced Visualization Complete ===")


if __name__ == "__main__":
    create_custom_visualization()
