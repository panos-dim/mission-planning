"""
Command-line interface for the satellite mission planner.

This module provides a CLI for running mission planning operations
from the command line.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
import logging

import click

from .orbit import SatelliteOrbit
from .targets import GroundTarget, TargetManager
from .planner import MissionPlanner
from .utils import (
    setup_logging, parse_datetime, download_tle_file, 
    get_common_tle_sources, create_sample_tle_file,
    get_current_utc, ensure_directory_exists
)

logger = logging.getLogger(__name__)


@click.group()
@click.option('--log-level', default='INFO', 
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              help='Set logging level')
@click.option('--log-file', type=click.Path(), help='Log file path')
def main(log_level: str, log_file: Optional[str]) -> None:
    """Satellite Mission Planning Tool - Plan satellite missions with orbital mechanics."""
    setup_logging(log_level, log_file)
    logger.info("Starting Satellite Mission Planner CLI")


@main.command()
@click.option('--tle', required=True, type=click.Path(exists=True),
              help='Path to TLE file')
@click.option('--satellite', required=True, 
              help='Satellite name (must match name in TLE file)')
@click.option('--target', 'targets', multiple=True, nargs=3,
              metavar='NAME LAT LON',
              help='Ground target: name latitude longitude (can specify multiple)')
@click.option('--elevation-mask', default=10.0, type=float,
              help='Minimum elevation angle in degrees (default: 10.0)')
@click.option('--start-time', type=str,
              help='Start time (YYYY-MM-DD HH:MM:SS UTC, default: now)')
@click.option('--duration', default=24.0, type=float,
              help='Analysis duration in hours (default: 24)')
@click.option('--output', type=click.Path(),
              help='Output directory for results')
@click.option('--format', 'output_format', default='json',
              type=click.Choice(['json', 'csv']),
              help='Schedule output format')
@click.option('--mission-type', default='imaging',
              type=click.Choice(['communication', 'imaging']),
              help='Mission type: communication (elevation only) or imaging (pointing cone)')
@click.option('--pointing-angle', default=5.0, type=float,
              help='Satellite pointing angle in degrees for imaging missions (default: 5.0)')
def plan(
    tle: str,
    satellite: str,
    targets: List[tuple],
    elevation_mask: float,
    start_time: Optional[str],
    duration: float,
    output: Optional[str],
    output_format: str,
    mission_type: str,
    pointing_angle: float
) -> None:
    """Plan a satellite mission with specified targets.
    
    Mission Types:
    - communication: Satellite must be above elevation mask (good for data links)
    - imaging: Target must be within satellite's pointing cone (good for Earth observation)
    
    Example:
    # Communication mission (finds passes for data downlink)
    plan --tle data.tle --satellite "ICEYE-X44" --target "Space42" 24.44 54.83 --mission-type communication
    
    # Imaging mission (finds passes for taking pictures)
    plan --tle data.tle --satellite "ICEYE-X44" --target "Space42" 24.44 54.83 --mission-type imaging --pointing-angle 10.0
    """
    
    try:
        # Parse start time
        if start_time:
            start_dt = parse_datetime(start_time)
        else:
            start_dt = get_current_utc()
        
        # Load satellite
        click.echo(f"Loading satellite '{satellite}' from {tle}")
        sat = SatelliteOrbit.from_tle_file(tle, satellite)
        
        # Create targets
        target_objects = []
        for target_data in targets:
            name, lat_str, lon_str = target_data
            try:
                lat = float(lat_str)
                lon = float(lon_str)
                target = GroundTarget(
                    name=name, 
                    latitude=lat, 
                    longitude=lon, 
                    elevation_mask=elevation_mask,
                    mission_type=mission_type,
                    pointing_angle=pointing_angle
                )
                target_objects.append(target)
                click.echo(f"Added target: {target} (mission: {mission_type})")
            except ValueError as e:
                click.echo(f"Error parsing target {name}: {e}", err=True)
                continue
        
        if not target_objects:
            click.echo("No valid targets specified. Use --target NAME LAT LON", err=True)
            return
        
        # Create mission planner
        planner = MissionPlanner(sat, target_objects)
        
        # Run analysis
        click.echo(f"Analyzing mission from {start_dt} for {duration} hours...")
        results = planner.run_mission_analysis(
            start_dt, duration, output
        )
        
        # Display summary
        summary = results['summary']
        click.echo("\n=== Mission Summary ===")
        click.echo(f"Satellite: {summary['satellite_name']}")
        click.echo(f"Total passes: {summary['total_passes']}")
        click.echo(f"Targets with passes: {summary['targets_with_passes']}/{summary['targets_analyzed']}")
        click.echo(f"Highest elevation: {summary['highest_elevation']}°")
        click.echo(f"Total contact time: {summary['total_contact_time_minutes']:.1f} minutes")
        
        if summary['total_passes'] > 0:
            best = summary['best_pass']
            click.echo(f"Best pass: {best['target']} at {best['time']} ({best['elevation']}°)")
        
        if output:
            click.echo(f"\nResults saved to: {output}")
        
    except Exception as e:
        logger.error(f"Mission planning failed: {e}")
        click.echo(f"Error: {e}", err=True)


@main.command()
@click.option('--tle', required=True, type=click.Path(exists=True),
              help='Path to TLE file')
@click.option('--satellite', required=True,
              help='Satellite name (must match name in TLE file)')
@click.option('--start-time', type=str,
              help='Start time (YYYY-MM-DD HH:MM:SS UTC, default: now)')
@click.option('--duration', default=6.0, type=float,
              help='Visualization duration in hours (default: 6)')
@click.option('--output', required=True, type=click.Path(),
              help='Output image file path')
@click.option('--targets', type=click.Path(exists=True),
              help='JSON file with target definitions')
def visualize(
    tle: str,
    satellite: str,
    start_time: Optional[str],
    duration: float,
    output: str,
    targets: Optional[str]
) -> None:
    """Create satellite ground track visualization."""
    
    try:
        # Parse start time
        if start_time:
            start_dt = parse_datetime(start_time)
        else:
            start_dt = get_current_utc()
        
        # Load satellite
        click.echo(f"Loading satellite '{satellite}' from {tle}")
        sat = SatelliteOrbit.from_tle_file(tle, satellite)
        
        # Load targets if specified
        target_objects = []
        if targets:
            target_manager = TargetManager.load_from_file(targets)
            target_objects = list(target_manager.targets)
            click.echo(f"Loaded {len(target_objects)} targets")
        
        # Create planner and visualization
        planner = MissionPlanner(sat, target_objects)
        
        click.echo(f"Creating visualization for {duration} hours...")
        planner.create_mission_visualization(
            start_dt, duration, output
        )
        
        click.echo(f"Visualization saved to: {output}")
        
    except Exception as e:
        logger.error(f"Visualization failed: {e}")
        click.echo(f"Error: {e}", err=True)


@main.command()
@click.option('--source', default='celestrak_active',
              help='TLE source (use "list-sources" to see available)')
@click.option('--output', required=True, type=click.Path(),
              help='Output TLE file path')
@click.option('--url', type=str,
              help='Custom URL for TLE data')
def download_tle(source: str, output: str, url: Optional[str]) -> None:
    """Download TLE data from online sources."""
    
    try:
        if url:
            download_url = url
        else:
            sources = get_common_tle_sources()
            if source not in sources:
                click.echo(f"Unknown source: {source}")
                click.echo("Available sources:")
                for name in sources.keys():
                    click.echo(f"  {name}")
                return
            download_url = sources[source]
        
        click.echo(f"Downloading TLE data from {download_url}")
        
        if download_tle_file(download_url, output):
            click.echo(f"TLE data saved to: {output}")
        else:
            click.echo("Download failed", err=True)
            
    except Exception as e:
        logger.error(f"TLE download failed: {e}")
        click.echo(f"Error: {e}", err=True)


@main.command()
def list_sources() -> None:
    """List available TLE data sources."""
    sources = get_common_tle_sources()
    
    click.echo("Available TLE sources:")
    for name, url in sources.items():
        click.echo(f"  {name:<20} {url}")


@main.command()
@click.option('--output', required=True, type=click.Path(),
              help='Output TLE file path')
def create_sample_tle(output: str) -> None:
    """Create a sample TLE file with common satellites."""
    
    try:
        create_sample_tle_file(output)
        click.echo(f"Sample TLE file created: {output}")
        click.echo("Contains: ISS, NOAA 18, TERRA, AQUA, LANDSAT 8")
        
    except Exception as e:
        logger.error(f"Sample TLE creation failed: {e}")
        click.echo(f"Error: {e}", err=True)


@main.command()
@click.option('--output', required=True, type=click.Path(),
              help='Output JSON file path')
def create_sample_targets(output: str) -> None:
    """Create a sample targets file with common locations."""
    
    try:
        # Create target manager with predefined targets
        target_manager = TargetManager()
        target_manager.create_predefined_targets()
        
        # Save to file
        target_manager.save_to_file(output)
        
        click.echo(f"Sample targets file created: {output}")
        click.echo(f"Contains {len(target_manager)} predefined targets")
        
    except Exception as e:
        logger.error(f"Sample targets creation failed: {e}")
        click.echo(f"Error: {e}", err=True)


@main.command()
@click.option('--tle', required=True, type=click.Path(exists=True),
              help='Path to TLE file')
@click.option('--satellite', required=True,
              help='Satellite name (must match name in TLE file)')
@click.option('--target', required=True, nargs=3, metavar='NAME LAT LON',
              help='Ground target: name latitude longitude')
@click.option('--elevation-mask', default=10.0, type=float,
              help='Minimum elevation angle in degrees (default: 10.0)')
@click.option('--hours', default=48, type=int,
              help='Hours to search ahead (default: 48)')
def next_pass(
    tle: str,
    satellite: str,
    target: tuple,
    elevation_mask: float,
    hours: int
) -> None:
    """Find the next satellite pass over a target."""
    
    try:
        # Load satellite
        sat = SatelliteOrbit.from_tle_file(tle, satellite)
        
        # Create target
        name, lat_str, lon_str = target
        lat, lon = float(lat_str), float(lon_str)
        target_obj = GroundTarget(name, lat, lon, elevation_mask)
        
        # Find next pass
        from .visibility import VisibilityCalculator
        calc = VisibilityCalculator(sat)
        
        start_time = get_current_utc()
        next_pass = calc.get_next_pass(target_obj, start_time, hours)
        
        if next_pass:
            click.echo(f"\nNext pass of {satellite} over {name}:")
            click.echo(f"Start:    {next_pass.start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            click.echo(f"Max Elev: {next_pass.max_elevation_time.strftime('%Y-%m-%d %H:%M:%S')} UTC ({next_pass.max_elevation:.1f}°)")
            click.echo(f"End:      {next_pass.end_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            click.echo(f"Azimuth:  {next_pass.start_azimuth:.1f}° → {next_pass.max_elevation_azimuth:.1f}° → {next_pass.end_azimuth:.1f}°")
        else:
            click.echo(f"No passes found for {satellite} over {name} in the next {hours} hours")
            
    except Exception as e:
        logger.error(f"Next pass calculation failed: {e}")
        click.echo(f"Error: {e}", err=True)


if __name__ == '__main__':
    main()
