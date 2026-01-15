#!/usr/bin/env python3
"""Debug test for pointing cone calculation."""

from datetime import datetime
from mission_planner.orbit import SatelliteOrbit
from mission_planner.targets import GroundTarget
from mission_planner.visibility import VisibilityCalculator
import tempfile
import math

# Create TLE file
tle_content = """ICEYE-X44
1 62707U 25009DC  25288.94104150  .00005233  00000+0  49676-3 0  9994
2 62707  97.7279   6.9881 0001205 170.4542 189.6701 14.93939975 63446
"""

with tempfile.NamedTemporaryFile(mode='w', suffix='.tle', delete=False) as f:
    f.write(tle_content)
    tle_file = f.name

# Create satellite
satellite = SatelliteOrbit.from_tle_file(tle_file, satellite_name="ICEYE-X44")

# Create Dubai target with imaging mission
target = GroundTarget(
    name="Dubai",
    latitude=25.2048,
    longitude=55.2708,
    mission_type='imaging',
    elevation_mask=10.0,
    sensor_fov_half_angle_deg=65.0,
    priority=5
)

# Create visibility calculator
vis_calc = VisibilityCalculator(satellite)

# Test the specific time when elevation was positive
test_time = datetime(2025, 10, 16, 18, 0, 0)

print(f"Testing at: {test_time}")
print(f"Target: {target.name} ({target.latitude:.4f}°N, {target.longitude:.4f}°E)")
print(f"Sensor FOV half-angle: {target.sensor_fov_half_angle_deg}°")
print()

# Get satellite position
sat_lat, sat_lon, sat_alt = satellite.get_position(test_time)
print(f"Satellite position: {sat_lat:.4f}°N, {sat_lon:.4f}°E, {sat_alt:.1f}km")
print()

# Calculate elevation and azimuth
elevation, azimuth = vis_calc.calculate_elevation_azimuth(target, test_time)
print(f"Elevation: {elevation:.2f}° (mask: {target.elevation_mask}°)")
print(f"Azimuth: {azimuth:.2f}°")
print()

# Check if above horizon manually
above_mask = elevation >= target.elevation_mask
print(f"Above elevation mask: {above_mask}")
print()

# Check pointing cone manually
print("=== Pointing Cone Check ===")

# Calculate look angle
earth_radius = 6371.0
sat_lat_rad = math.radians(sat_lat)
sat_lon_rad = math.radians(sat_lon)
target_lat_rad = math.radians(target.latitude)
target_lon_rad = math.radians(target.longitude)

# Satellite position (Cartesian)
sat_r = earth_radius + sat_alt
sat_x = sat_r * math.cos(sat_lat_rad) * math.cos(sat_lon_rad)
sat_y = sat_r * math.cos(sat_lat_rad) * math.sin(sat_lon_rad)
sat_z = sat_r * math.sin(sat_lat_rad)

# Target position (Cartesian)
target_x = earth_radius * math.cos(target_lat_rad) * math.cos(target_lon_rad)
target_y = earth_radius * math.cos(target_lat_rad) * math.sin(target_lon_rad)
target_z = earth_radius * math.sin(target_lat_rad)

# Vector from satellite to target
dx = target_x - sat_x
dy = target_y - sat_y
dz = target_z - sat_z
dist = math.sqrt(dx*dx + dy*dy + dz*dz)

# Nadir vector (from satellite toward Earth center)
nadir_x, nadir_y, nadir_z = -sat_x, -sat_y, -sat_z
nadir_len = math.sqrt(nadir_x*nadir_x + nadir_y*nadir_y + nadir_z*nadir_z)

# Dot product
dot = (dx*nadir_x + dy*nadir_y + dz*nadir_z) / (dist * nadir_len)
look_angle = math.degrees(math.acos(max(-1, min(1, dot))))

print(f"Look angle (off-nadir): {look_angle:.2f}°")
print(f"Sensor FOV limit: {target.sensor_fov_half_angle_deg}° (+ 0.1° tolerance)")
print(f"Within cone: {look_angle <= (target.sensor_fov_half_angle_deg + 0.1)}")
print()

# Now test the actual visibility check
is_visible = vis_calc._is_target_visible(target, test_time, elevation)
print(f"=== Final Result ===")
print(f"is_visible: {is_visible}")
