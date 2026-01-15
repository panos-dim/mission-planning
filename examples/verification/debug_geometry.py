"""
Debug geometry calculation to understand the 5° difference.
"""

import sys
import math
import numpy as np
import requests
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.mission_planner.orbit import SatelliteOrbit

def fetch_tle():
    url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    lines = response.text.strip().split('\n')
    for i in range(0, len(lines) - 2, 3):
        if "ICEYE-X44" in lines[i].upper():
            return (lines[i+1].strip(), lines[i+2].strip())
    raise ValueError("Not found")

# Test case: T1 first pass
# STK: 08:32:20.774, elevation 49.233°
test_time = datetime(2025, 10, 15, 8, 32, 20, 774000)
target_lat = 84.699032
target_lon = 66.784494

print("="*80)
print("GEOMETRY DEBUG")
print("="*80)

# Get satellite position
tle1, tle2 = fetch_tle()
satellite = SatelliteOrbit(tle_lines=[tle1, tle2], satellite_name="ICEYE-X44")
sat_lat, sat_lon, sat_alt = satellite.get_position(test_time)

print(f"\n📍 Test Case (T1, First Pass):")
print(f"  Time: {test_time}")
print(f"  STK Reported: 49.233°")
print(f"\n🛰️  Satellite:")
print(f"  Lat: {sat_lat:.6f}°")
print(f"  Lon: {sat_lon:.6f}°")
print(f"  Alt: {sat_alt:.3f} km")
print(f"\n🎯 Target:")
print(f"  Lat: {target_lat:.6f}°")
print(f"  Lon: {target_lon:.6f}°")

# Calculate different angle definitions
earth_radius = 6371.0

# Method 1: Our current method (ECEF vectors)
sat_lat_rad = math.radians(sat_lat)
sat_lon_rad = math.radians(sat_lon)
target_lat_rad = math.radians(target_lat)
target_lon_rad = math.radians(target_lon)

sat_r = earth_radius + sat_alt
sat_x = sat_r * math.cos(sat_lat_rad) * math.cos(sat_lon_rad)
sat_y = sat_r * math.cos(sat_lat_rad) * math.sin(sat_lon_rad)
sat_z = sat_r * math.sin(sat_lat_rad)

target_x = earth_radius * math.cos(target_lat_rad) * math.cos(target_lon_rad)
target_y = earth_radius * math.cos(target_lat_rad) * math.sin(target_lon_rad)
target_z = earth_radius * math.sin(target_lat_rad)

nadir_vec = np.array([-sat_x, -sat_y, -sat_z])
nadir_vec = nadir_vec / np.linalg.norm(nadir_vec)

target_vec = np.array([target_x - sat_x, target_y - sat_y, target_z - sat_z])
target_vec = target_vec / np.linalg.norm(target_vec)

cos_angle = np.dot(nadir_vec, target_vec)
cos_angle = max(-1.0, min(1.0, cos_angle))
method1_angle = math.degrees(math.acos(cos_angle))

print(f"\n📐 Method 1 (ECEF Nadir Vector):")
print(f"  Angle: {method1_angle:.3f}°")
print(f"  Error: {method1_angle - 49.233:.3f}°")

# Method 2: Spherical law of cosines
cos_central = (math.sin(sat_lat_rad) * math.sin(target_lat_rad) +
               math.cos(sat_lat_rad) * math.cos(target_lat_rad) * 
               math.cos(target_lon_rad - sat_lon_rad))
cos_central = max(-1.0, min(1.0, cos_central))
central_angle_rad = math.acos(cos_central)

# Using law of cosines in satellite-center-target triangle
range_to_target = math.sqrt(sat_r**2 + earth_radius**2 - 
                            2 * sat_r * earth_radius * cos_central)

cos_look = (sat_r**2 + range_to_target**2 - earth_radius**2) / (2 * sat_r * range_to_target)
cos_look = max(-1.0, min(1.0, cos_look))
method2_angle = math.degrees(math.acos(cos_look))

print(f"\n📐 Method 2 (Spherical Law of Cosines):")
print(f"  Central angle: {math.degrees(central_angle_rad):.3f}°")
print(f"  Range: {range_to_target:.3f} km")
print(f"  Look angle: {method2_angle:.3f}°")
print(f"  Error: {method2_angle - 49.233:.3f}°")

# Method 3: Using elevation angle relationship
# Ground elevation angle
ground_lat_rad = math.radians(target_lat)
ground_lon_rad = math.radians(target_lon)

ground_x = earth_radius * math.cos(ground_lat_rad) * math.cos(ground_lon_rad)
ground_y = earth_radius * math.cos(ground_lat_rad) * math.sin(ground_lon_rad)
ground_z = earth_radius * math.sin(ground_lat_rad)

# Local up vector at target
up_x = ground_x / earth_radius
up_y = ground_y / earth_radius
up_z = ground_z / earth_radius

# Vector from ground to satellite
dx = sat_x - ground_x
dy = sat_y - ground_y
dz = sat_z - ground_z
range_km = math.sqrt(dx*dx + dy*dy + dz*dz)

dot_product = (dx * up_x + dy * up_y + dz * up_z)
elevation_rad = math.asin(dot_product / range_km)
elevation_deg = math.degrees(elevation_rad)

# Off-nadir should be complement in some sense
method3_angle = 90 - elevation_deg  # Simple complement

print(f"\n📐 Method 3 (From Ground Elevation):")
print(f"  Ground elevation: {elevation_deg:.3f}°")
print(f"  Complement (90-elev): {method3_angle:.3f}°")
print(f"  Error: {method3_angle - 49.233:.3f}°")

# Method 4: Earth oblateness correction
# WGS84: a=6378.137 km, b=6356.752 km
a = 6378.137  # Equatorial radius
b = 6356.752  # Polar radius

# Use ellipsoidal Earth
def ellipsoid_radius(lat_rad):
    """Radius at given latitude on WGS84 ellipsoid."""
    cos_lat = math.cos(lat_rad)
    sin_lat = math.sin(lat_rad)
    num = (a**2 * cos_lat)**2 + (b**2 * sin_lat)**2
    den = (a * cos_lat)**2 + (b * sin_lat)**2
    return math.sqrt(num / den)

r_target = ellipsoid_radius(target_lat_rad)
r_sat = ellipsoid_radius(sat_lat_rad) + sat_alt

# Recalculate with ellipsoid
target_x_ell = r_target * math.cos(target_lat_rad) * math.cos(target_lon_rad)
target_y_ell = r_target * math.cos(target_lat_rad) * math.sin(target_lon_rad)
target_z_ell = r_target * math.sin(target_lat_rad)

sat_x_ell = r_sat * math.cos(sat_lat_rad) * math.cos(sat_lon_rad)
sat_y_ell = r_sat * math.cos(sat_lat_rad) * math.sin(sat_lon_rad)
sat_z_ell = r_sat * math.sin(sat_lat_rad)

nadir_vec_ell = np.array([-sat_x_ell, -sat_y_ell, -sat_z_ell])
nadir_vec_ell = nadir_vec_ell / np.linalg.norm(nadir_vec_ell)

target_vec_ell = np.array([target_x_ell - sat_x_ell, target_y_ell - sat_y_ell, target_z_ell - sat_z_ell])
target_vec_ell = target_vec_ell / np.linalg.norm(target_vec_ell)

cos_angle_ell = np.dot(nadir_vec_ell, target_vec_ell)
cos_angle_ell = max(-1.0, min(1.0, cos_angle_ell))
method4_angle = math.degrees(math.acos(cos_angle_ell))

print(f"\n📐 Method 4 (WGS84 Ellipsoid):")
print(f"  Target radius: {r_target:.3f} km (vs {earth_radius:.3f} km spherical)")
print(f"  Look angle: {method4_angle:.3f}°")
print(f"  Error: {method4_angle - 49.233:.3f}°")

print("\n" + "="*80)
print("SUMMARY:")
print(f"  STK Value:     49.233°")
print(f"  Method 1 (Current): {method1_angle:.3f}° ({method1_angle - 49.233:+.3f}°)")
print(f"  Method 2 (Spherical): {method2_angle:.3f}° ({method2_angle - 49.233:+.3f}°)")
print(f"  Method 3 (Complement): {method3_angle:.3f}° ({method3_angle - 49.233:+.3f}°)")
print(f"  Method 4 (Ellipsoid): {method4_angle:.3f}° ({method4_angle - 49.233:+.3f}°)")
print("="*80)
