"""
Sunlight and illumination calculations for optical imaging missions.

This module provides functionality to determine if a ground target
is illuminated by the sun for optical satellite imaging.
"""

import math
from datetime import datetime
from typing import Tuple

import numpy as np

# Constants
EARTH_RADIUS_KM = 6371.0
AU_KM = 149597870.7  # Astronomical Unit in kilometers


def calculate_sun_position(timestamp: datetime) -> Tuple[float, float, float]:
    """
    Calculate the sun's position in Earth-Centered Inertial (ECI) coordinates.

    Uses simplified astronomical calculations for the sun's position.

    Args:
        timestamp: UTC datetime

    Returns:
        Tuple of (x, y, z) coordinates in kilometers
    """
    # Make timestamp timezone-naive for calculation
    if timestamp.tzinfo is not None:
        timestamp = timestamp.replace(tzinfo=None)

    # Days since J2000.0 epoch
    j2000 = datetime(2000, 1, 1, 12, 0, 0)
    delta = timestamp - j2000
    days = delta.total_seconds() / 86400.0

    # Mean anomaly
    M = math.radians(357.52911 + 0.98560028 * days) % (2 * math.pi)

    # Equation of center
    C = math.radians(1.914602 * math.sin(M) + 0.019993 * math.sin(2 * M))

    # True anomaly
    v = M + C

    # Ecliptic longitude
    lambda_sun = math.radians(280.46646 + 0.98564736 * days) + C

    # Obliquity of ecliptic
    epsilon = math.radians(23.439291)

    # Convert to equatorial coordinates
    x = AU_KM * math.cos(lambda_sun)
    y = AU_KM * math.sin(lambda_sun) * math.cos(epsilon)
    z = AU_KM * math.sin(lambda_sun) * math.sin(epsilon)

    return x, y, z


def is_target_illuminated(
    target_lat: float,
    target_lon: float,
    timestamp: datetime,
    min_sun_elevation: float = 0.0,
) -> bool:
    """
    Check if a ground target is illuminated by the sun.

    Args:
        target_lat: Target latitude in degrees
        target_lon: Target longitude in degrees
        timestamp: UTC datetime
        min_sun_elevation: Minimum sun elevation angle in degrees (default 0)

    Returns:
        True if target is illuminated, False otherwise
    """
    # Get sun position in ECI
    sun_x, sun_y, sun_z = calculate_sun_position(timestamp)

    # Convert target to ECI coordinates
    # Account for Earth's rotation
    gmst = calculate_gmst(timestamp)
    lon_rad = math.radians(target_lon + gmst)
    lat_rad = math.radians(target_lat)

    # Target position on Earth surface
    target_x = EARTH_RADIUS_KM * math.cos(lat_rad) * math.cos(lon_rad)
    target_y = EARTH_RADIUS_KM * math.cos(lat_rad) * math.sin(lon_rad)
    target_z = EARTH_RADIUS_KM * math.sin(lat_rad)

    # Vector from target to sun
    sun_vec = np.array([sun_x - target_x, sun_y - target_y, sun_z - target_z])
    sun_distance = np.linalg.norm(sun_vec)
    sun_unit = sun_vec / sun_distance

    # Local up vector at target
    up_vec = np.array([target_x, target_y, target_z]) / EARTH_RADIUS_KM

    # Sun elevation angle (angle between sun vector and local horizon)
    cos_elevation = np.dot(sun_unit, up_vec)
    sun_elevation_rad = math.asin(cos_elevation)
    sun_elevation_deg = math.degrees(sun_elevation_rad)

    return sun_elevation_deg >= min_sun_elevation


def get_sun_elevation(
    target_lat: float, target_lon: float, timestamp: datetime
) -> float:
    """
    Get the sun elevation angle at a target location.

    Args:
        target_lat: Target latitude in degrees
        target_lon: Target longitude in degrees
        timestamp: UTC datetime

    Returns:
        Sun elevation angle in degrees (positive = above horizon, negative = below)
    """
    # Get sun position in ECI
    sun_x, sun_y, sun_z = calculate_sun_position(timestamp)

    # Convert target to ECI coordinates
    gmst = calculate_gmst(timestamp)
    lon_rad = math.radians(target_lon + gmst)
    lat_rad = math.radians(target_lat)

    # Target position on Earth surface
    target_x = EARTH_RADIUS_KM * math.cos(lat_rad) * math.cos(lon_rad)
    target_y = EARTH_RADIUS_KM * math.cos(lat_rad) * math.sin(lon_rad)
    target_z = EARTH_RADIUS_KM * math.sin(lat_rad)

    # Vector from target to sun
    sun_vec = np.array([sun_x - target_x, sun_y - target_y, sun_z - target_z])
    sun_distance = np.linalg.norm(sun_vec)
    sun_unit = sun_vec / sun_distance

    # Local up vector at target
    up_vec = np.array([target_x, target_y, target_z]) / EARTH_RADIUS_KM

    # Sun elevation angle (angle between sun vector and local horizon)
    cos_elevation = np.dot(sun_unit, up_vec)
    sun_elevation_rad = math.asin(max(-1.0, min(1.0, cos_elevation)))

    return math.degrees(sun_elevation_rad)


def calculate_gmst(timestamp: datetime) -> float:
    """
    Calculate Greenwich Mean Sidereal Time (GMST) in degrees.

    Args:
        timestamp: UTC datetime

    Returns:
        GMST in degrees
    """
    # Make timestamp timezone-naive for calculation
    if timestamp.tzinfo is not None:
        timestamp = timestamp.replace(tzinfo=None)

    # Days since J2000.0
    j2000 = datetime(2000, 1, 1, 12, 0, 0)
    delta = timestamp - j2000
    days = delta.total_seconds() / 86400.0

    # GMST calculation
    T = days / 36525.0  # Julian centuries
    gmst = 280.46061837 + 360.98564736629 * days + 0.000387933 * T * T

    return gmst % 360.0


def calculate_solar_zenith_angle(
    target_lat: float, target_lon: float, timestamp: datetime
) -> float:
    """
    Calculate the solar zenith angle at a target location.

    The solar zenith angle is the angle between the sun and the vertical (zenith).
    0° means sun is directly overhead, 90° means sun is at horizon.

    Args:
        target_lat: Target latitude in degrees
        target_lon: Target longitude in degrees
        timestamp: UTC datetime

    Returns:
        Solar zenith angle in degrees
    """
    # Get sun elevation
    if is_target_illuminated(target_lat, target_lon, timestamp, -90):
        # Get sun position in ECI
        sun_x, sun_y, sun_z = calculate_sun_position(timestamp)

        # Convert target to ECI coordinates
        gmst = calculate_gmst(timestamp)
        lon_rad = math.radians(target_lon + gmst)
        lat_rad = math.radians(target_lat)

        # Target position on Earth surface
        target_x = EARTH_RADIUS_KM * math.cos(lat_rad) * math.cos(lon_rad)
        target_y = EARTH_RADIUS_KM * math.cos(lat_rad) * math.sin(lon_rad)
        target_z = EARTH_RADIUS_KM * math.sin(lat_rad)

        # Vector from target to sun
        sun_vec = np.array([sun_x - target_x, sun_y - target_y, sun_z - target_z])
        sun_distance = np.linalg.norm(sun_vec)
        sun_unit = sun_vec / sun_distance

        # Local up vector at target
        up_vec = np.array([target_x, target_y, target_z]) / EARTH_RADIUS_KM

        # Sun elevation angle
        cos_elevation = np.dot(sun_unit, up_vec)
        sun_elevation_rad = math.asin(cos_elevation)

        # Zenith angle is 90 - elevation
        zenith_angle_deg = 90.0 - math.degrees(sun_elevation_rad)

        return zenith_angle_deg
    else:
        # Sun is below horizon
        return 180.0  # Maximum possible value
