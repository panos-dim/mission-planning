"""
Utility functions for the mission planner.

This module provides common utility functions used throughout
the mission planning tool.
"""

from datetime import datetime, timezone
from typing import Union, Optional
import logging
import requests
from pathlib import Path

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Set up logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
        
    Environment Variables:
        MISSION_PLANNER_LOG_LEVEL: Override log level (DEBUG, INFO, WARNING, ERROR)
    """
    import os
    # Allow environment variable to override
    env_level = os.environ.get("MISSION_PLANNER_LOG_LEVEL")
    if env_level:
        level = env_level
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    logger.info(f"Logging configured at {level} level")


def parse_datetime(date_string: str) -> datetime:
    """
    Parse datetime string in various formats.
    
    Args:
        date_string: Date string to parse
        
    Returns:
        Parsed datetime object (UTC)
        
    Raises:
        ValueError: If date string cannot be parsed
    """
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_string, fmt)
            # Ensure UTC timezone
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            continue
    
    raise ValueError(f"Could not parse datetime string: {date_string}")


def download_tle_file(url: str, output_file: Union[str, Path]) -> bool:
    """
    Download TLE file from URL.
    
    Args:
        url: URL to download TLE data from
        output_file: Local file path to save TLE data
        
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Downloading TLE data from {url}")
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(response.text)
        
        logger.info(f"TLE data saved to {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error downloading TLE file: {e}")
        return False


def get_common_tle_sources() -> dict:
    """
    Get dictionary of common TLE data sources.
    
    Returns:
        Dictionary mapping source names to URLs
    """
    tle_sources = {
        "celestrak_active": "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle",
        "celestrak_stations": "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle",
        "celestrak_visual": "https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=tle",
        "celestrak_weather": "https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle",
        "celestrak_noaa": "https://celestrak.org/NORAD/elements/gp.php?GROUP=noaa&FORMAT=tle",
        "celestrak_goes": "https://celestrak.org/NORAD/elements/gp.php?GROUP=goes&FORMAT=tle",
        "celestrak_resource": "https://celestrak.org/NORAD/elements/gp.php?GROUP=resource&FORMAT=tle",
        "celestrak_cubesat": "https://celestrak.org/NORAD/elements/gp.php?GROUP=cubesat&FORMAT=tle",
        "celestrak_other": "https://celestrak.org/NORAD/elements/gp.php?GROUP=other-comm&FORMAT=tle",
    }
    return tle_sources


def validate_coordinates(latitude: float, longitude: float) -> bool:
    """
    Validate latitude and longitude coordinates.
    
    Args:
        latitude: Latitude in degrees
        longitude: Longitude in degrees
        
    Returns:
        True if coordinates are valid
    """
    return (-90 <= latitude <= 90) and (-180 <= longitude <= 180)


def degrees_to_dms(degrees: float) -> tuple:
    """
    Convert decimal degrees to degrees, minutes, seconds.
    
    Args:
        degrees: Decimal degrees
        
    Returns:
        Tuple of (degrees, minutes, seconds)
    """
    abs_degrees = abs(degrees)
    d = int(abs_degrees)
    m = int((abs_degrees - d) * 60)
    s = ((abs_degrees - d) * 60 - m) * 60
    
    return (d, m, s)


def format_coordinates(latitude: float, longitude: float, format: str = "decimal") -> str:
    """
    Format coordinates for display.
    
    Args:
        latitude: Latitude in degrees
        longitude: Longitude in degrees
        format: Format type ("decimal" or "dms")
        
    Returns:
        Formatted coordinate string
    """
    if format == "decimal":
        return f"{latitude:.6f}°, {longitude:.6f}°"
    elif format == "dms":
        lat_d, lat_m, lat_s = degrees_to_dms(latitude)
        lon_d, lon_m, lon_s = degrees_to_dms(longitude)
        
        lat_dir = "N" if latitude >= 0 else "S"
        lon_dir = "E" if longitude >= 0 else "W"
        
        return (f"{lat_d}°{lat_m}'{lat_s:.1f}\"{lat_dir}, "
                f"{lon_d}°{lon_m}'{lon_s:.1f}\"{lon_dir}")
    else:
        raise ValueError(f"Unknown format: {format}")


def calculate_ground_distance(
    lat1: float, lon1: float,
    lat2: float, lon2: float
) -> float:
    """
    Calculate great circle distance between two points on Earth.
    
    Args:
        lat1, lon1: First point coordinates (degrees)
        lat2, lon2: Second point coordinates (degrees)
        
    Returns:
        Distance in kilometers
    """
    import math
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = (math.sin(dlat/2)**2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2)
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth's radius in km
    earth_radius = 6371.0
    return earth_radius * c


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def create_sample_tle_file(output_file: Union[str, Path]) -> None:
    """
    Create a sample TLE file with common satellites.
    
    Args:
        output_file: Path to create sample TLE file
    """
    sample_tle_data = """ISS (ZARYA)
1 25544U 98067A   24001.00000000  .00002182  00000-0  40864-4 0  9990
2 25544  51.6461 339.7939 0001220  92.8340 267.3124 15.49309239426382
NOAA 18
1 28654U 05018A   24001.00000000  .00000012  00000-0  28110-4 0  9997
2 28654  99.0581 161.3857 0013414  73.9446 286.3932 14.12501637967188
TERRA
1 25994U 99068A   24001.00000000  .00000023  00000-0  42979-4 0  9991
2 25994  98.2022  10.3559 0001378  83.7123 276.4313 14.57107527260649
AQUA
1 27424U 02022A   24001.00000000  .00000024  00000-0  43856-4 0  9996
2 27424  98.2123  70.8559 0002378  93.7123 266.4313 14.57207527160649
LANDSAT 8
1 39084U 13008A   24001.00000000  .00000012  00000-0  28110-4 0  9993
2 39084  98.2062 348.0319 0001378  83.7123 276.4313 14.57107527560649"""
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(sample_tle_data)
    
    logger.info(f"Created sample TLE file: {output_path}")


def get_current_utc() -> datetime:
    """
    Get current UTC datetime.
    
    Returns:
        Current UTC datetime (timezone-naive)
    """
    return datetime.utcnow()


def ensure_directory_exists(directory: Union[str, Path]) -> Path:
    """
    Ensure directory exists, create if it doesn't.
    
    Args:
        directory: Directory path
        
    Returns:
        Path object for the directory
    """
    dir_path = Path(directory)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path
