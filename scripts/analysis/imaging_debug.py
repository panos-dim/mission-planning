#!/usr/bin/env python3
"""Debug test for imaging visibility."""

from datetime import datetime, timedelta
from mission_planner.orbit import SatelliteOrbit
from mission_planner.targets import GroundTarget
from mission_planner.visibility import VisibilityCalculator
import tempfile

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
    sensor_fov_half_angle_deg=30.0,
    priority=5
)

print(f"Target: {target.name}")
print(f"Mission type: {target.mission_type}")
print(f"Sensor FOV: {target.sensor_fov_half_angle_deg}°")
print(f"Elevation mask: {target.elevation_mask}°")
print()

# Create visibility calculator
vis_calc = VisibilityCalculator(satellite)

# Test a few time points around TLE epoch
test_start = datetime(2025, 10, 15, 0, 0, 0)

print("Testing visibility at different times:")
for hours in range(0, 48, 6):
    test_time = test_start + timedelta(hours=hours)
    
    # Calculate elevation
    try:
        elevation, azimuth = vis_calc.calculate_elevation_azimuth(target, test_time)
        
        # Check visibility
        is_visible = vis_calc._is_target_visible(target, test_time, elevation)
        
        print(f"{test_time.strftime('%m/%d %H:%M')}: Elev={elevation:6.2f}° Az={azimuth:6.2f}° Visible={is_visible}")
        
        if is_visible:
            # Get satellite position
            sat_lat, sat_lon, sat_alt = satellite.get_position(test_time)
            print(f"   → Sat pos: {sat_lat:.2f}°N, {sat_lon:.2f}°E, {sat_alt:.1f}km")
            
    except Exception as e:
        print(f"{test_time.strftime('%m/%d %H:%M')}: Error: {e}")

print()
print("Computing passes for full period...")

# Now try to compute passes
start_time = datetime(2025, 10, 15, 0, 0, 0)
end_time = start_time + timedelta(days=2)

passes = vis_calc.compute_passes(target, start_time, end_time)

print(f"\nFound {len(passes)} passes")
for i, p in enumerate(passes[:5], 1):
    print(f"  Pass {i}: {p.start_time.strftime('%m/%d %H:%M')} - {p.end_time.strftime('%H:%M')} "
          f"(Max elev: {p.max_elevation:.1f}°)")
