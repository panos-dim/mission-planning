#!/usr/bin/env python3
"""
AGGRESSIVE MANEUVER SCENARIO - Force large roll/pitch angles
Tests extreme attitude changes with tight time constraints
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from datetime import datetime, timedelta
from mission_planner.orbit import SatelliteOrbit
from mission_planner.targets import GroundTarget
from mission_planner.visibility import VisibilityCalculator
from mission_planner.scheduler import MissionScheduler, SchedulerConfig, AlgorithmType, Opportunity
import tempfile
import os
import math

# AGGRESSIVE SCENARIO: Targets in a GRID pattern
# This forces satellite to slew between distant targets in short time
targets = [
    # Cross-track spread (East-West) - forces ROLL
    GroundTarget(name="Target_West", latitude=40.0, longitude=15.0, priority=3),  # Italy
    GroundTarget(name="Target_Center", latitude=40.0, longitude=25.0, priority=3),  # Greece  
    GroundTarget(name="Target_East", latitude=40.0, longitude=35.0, priority=3),  # Turkey
    
    # Along-track spread (North-South) - forces PITCH (if implemented)
    GroundTarget(name="Target_North", latitude=50.0, longitude=25.0, priority=2),  # Poland
    GroundTarget(name="Target_South", latitude=30.0, longitude=25.0, priority=2),  # Egypt
    
    # Diagonal targets - forces combined ROLL+PITCH
    GroundTarget(name="Target_NE", latitude=50.0, longitude=35.0, priority=1),  # Ukraine
    GroundTarget(name="Target_SW", latitude=30.0, longitude=15.0, priority=1),  # Libya
]

print("=" * 100)
print("AGGRESSIVE MANEUVER SCENARIO - LARGE ROLL/PITCH TESTING")
print("=" * 100)
print(f"\n📍 {len(targets)} Targets in GRID pattern (10° × 20° coverage):")

# Calculate grid dimensions
lats = [t.latitude for t in targets]
lons = [t.longitude for t in targets]
print(f"   Latitude range: {min(lats):.1f}° to {max(lats):.1f}° ({max(lats)-min(lats):.1f}° span)")
print(f"   Longitude range: {min(lons):.1f}° to {max(lons):.1f}° ({max(lons)-min(lons):.1f}° span)")

for t in targets:
    print(f"  - {t.name:15s}: {t.latitude:>6.1f}°N, {t.longitude:>6.1f}°E  (P={t.priority})")

# Load satellite
print("\n🛰️  Loading ICEYE-X44 satellite...")
tle_data = """ICEYE-X44
1 59219U 24055K   24307.50000000  .00009876  00000-0  45678-3 0  9990
2 59219  97.5900 123.4567 0015000  90.1234 270.0000 15.19000000123456"""

with tempfile.NamedTemporaryFile(mode='w', suffix='.tle', delete=False) as f:
    f.write(tle_data)
    tle_file = f.name

satellite = SatelliteOrbit.from_tle_file(tle_file, "ICEYE-X44")
os.unlink(tle_file)

sample_time = datetime(2025, 11, 3, 12, 0, 0)
lat, lon, alt = satellite.get_position(sample_time)
print(f"  Satellite: {satellite.satellite_name}, Altitude: {alt:.1f} km")

# Mission window - 24 HOURS but TIGHT scheduling to force rapid transitions
start_time = datetime(2025, 11, 3, 0, 0, 0)
end_time = start_time + timedelta(hours=24)
print(f"\n📅 Mission Duration: 24 HOURS ({start_time} to {end_time})")
print(f"   ⚠️  WIDE FOV + TIGHT SCHEDULING → Forces rapid slews between distant targets")

# Visibility analysis with WIDE FOV to get many opportunities
print("\n🔍 Running visibility analysis with WIDE FOV (45° half-angle)...")
calc = VisibilityCalculator(satellite)

all_passes = []
for target in targets:
    target.sensor_fov_half_angle_deg = 45.0  # WIDE FOV - more opportunities
    target.elevation_mask_deg = 10.0
    target.imaging_type = 'optical'
    
    passes = calc.find_passes(target, start_time, end_time)
    print(f"  {target.name:15s}: {len(passes):2d} passes")
    all_passes.extend([(target.name, p) for p in passes])

print(f"\n✅ Total passes: {len(all_passes)}")

# Convert to opportunities - use START of pass (not optimal midpoint)
# This forces satellite to image when NOT overhead → larger roll angles
opportunities = []
target_positions = {}

for target_name, pass_details in all_passes:
    target = next(t for t in targets if t.name == target_name)
    target_positions[target_name] = (target.latitude, target.longitude)
    
    # Use EARLY in pass (not midpoint) to force off-nadir imaging
    early_time = pass_details.start_time + timedelta(seconds=10)
    
    opp = Opportunity(
        id=f"{target_name}_{pass_details.start_time.strftime('%H%M')}",
        satellite_id="ICEYE-X44",
        target_id=target_name,
        start_time=early_time,
        end_time=early_time + timedelta(seconds=1),
        max_elevation=pass_details.max_elevation,
        value=float(target.priority)
    )
    opportunities.append(opp)

opportunities.sort(key=lambda x: x.start_time)

print(f"\n📊 Created {len(opportunities)} opportunities")

# AGGRESSIVE scheduler config
print("\n⚙️  AGGRESSIVE Scheduler Configuration:")
print("  - Imaging time: 0.5 seconds (FAST)")
print("  - Max roll rate: 2.0 deg/s (MODERATE)")
print("  - Max roll acceleration: 1.0 deg/s² (REALISTIC - NOT INSTANT)")
print("  - Max spacecraft roll: 30.0 deg (TIGHT LIMIT)")
print("  - Look window: 120 seconds (VERY SHORT)")

config = SchedulerConfig(
    imaging_time_s=0.5,  # Fast imaging
    max_roll_rate_dps=2.0,  # Moderate rate
    max_roll_accel_dps2=1.0,  # REALISTIC acceleration (not 10000!)
    max_spacecraft_roll_deg=30.0,  # Tighter limit
    look_window_s=120.0  # Very short window
)

scheduler = MissionScheduler(config, satellite=satellite)
print(f"  ✅ Scheduler initialized")

# Run FIRST_FIT for chronological order (worst case for maneuvers)
print("\n🚀 Running FIRST-FIT (chronological - worst case for maneuvers)...")
schedule, metrics = scheduler.schedule(opportunities, target_positions, AlgorithmType.FIRST_FIT)

print(f"\n{'=' * 100}")
print(f"AGGRESSIVE SCHEDULING RESULTS")
print(f"{'=' * 100}")
print(f"Scheduled: {len(schedule)} opportunities")
print(f"Runtime: {metrics.runtime_ms:.2f} ms")
print(f"Targets acquired: {len(set(s.target_id for s in schedule))}/{len(targets)}")

# Detailed schedule
print(f"\n{'=' * 100}")
print(f"DETAILED SCHEDULE - LARGE MANEUVER ANALYSIS")
print(f"{'=' * 100}")
print(f"{'#':<4} {'Target':<15} {'Time':<12} {'ΔRoll':<9} {'Roll°':<9} {'ΔPitch':<9} {'Pitch°':<9} {'Slew':<10} {'Slack':<10}")
print(f"{'-' * 110}")

for i, sched in enumerate(schedule, 1):
    print(
        f"{i:<4} "
        f"{sched.target_id:<15} "
        f"{sched.start_time.strftime('%H:%M:%S'):<12} "
        f"{sched.delta_roll:>7.2f}°  "
        f"{sched.roll_angle:>7.2f}°  "
        f"{sched.delta_pitch:>7.2f}°  "
        f"{sched.pitch_angle:>7.2f}°  "
        f"{sched.maneuver_time:>8.3f}s  "
        f"{sched.slack_time:>8.2f}s"
    )

# VALIDATION
print(f"\n{'=' * 100}")
print(f"MANEUVER ANALYSIS")
print(f"{'=' * 100}")

# Find large maneuvers
print("\n✓ Large Roll Maneuvers (>5°):")
large_rolls = [(i, s) for i, s in enumerate(schedule, 1) if s.delta_roll > 5.0]
if large_rolls:
    print(f"  Found {len(large_rolls)} large roll maneuvers:")
    for idx, s in large_rolls:
        print(f"    #{idx}: {s.target_id:15s} - ΔRoll={s.delta_roll:6.2f}°, Slew={s.maneuver_time:.3f}s")
else:
    print(f"  ℹ️  No large rolls >5° detected")

# Check maneuver time calculations
print(f"\n✓ Maneuver Time Validation (with REALISTIC acceleration = 1.0 deg/s²):")
print(f"{'#':<4} {'ΔRoll':<10} {'Expected Time':<20} {'Actual Time':<15} {'Status'}")
print(f"{'-' * 70}")

for i, sched in enumerate(schedule[:5], 1):  # Check first 5
    delta = sched.delta_roll
    max_rate = 2.0  # deg/s
    max_accel = 1.0  # deg/s²
    
    if delta > 0:
        # Time to reach max rate
        t_accel = max_rate / max_accel  # seconds
        # Distance during acceleration
        d_accel = 0.5 * max_accel * t_accel * t_accel
        d_total_accel = 2 * d_accel
        
        if delta <= d_total_accel:
            # Triangular profile
            expected = 2 * math.sqrt(delta / max_accel)
        else:
            # Trapezoidal profile
            d_cruise = delta - d_total_accel
            t_cruise = d_cruise / max_rate
            expected = 2 * t_accel + t_cruise
    else:
        expected = 0.0
    
    actual = sched.maneuver_time
    diff = abs(actual - expected)
    status = "✅" if diff < 0.1 else "⚠️"
    
    print(f"{i:<4} {delta:>7.2f}°  {expected:>16.3f}s  {actual:>13.3f}s  {status}")

# Roll angle distribution
print(f"\n✓ Roll Angle Distribution:")
rolls = [s.roll_angle for s in schedule]
if rolls:
    print(f"  Minimum: {min(rolls):6.2f}°")
    print(f"  Maximum: {max(rolls):6.2f}°")
    print(f"  Average: {sum(rolls)/len(rolls):6.2f}°")
    print(f"  Limit:   {config.max_spacecraft_roll_deg:6.2f}°")
    
    if max(rolls) > config.max_spacecraft_roll_deg:
        print(f"  ❌ VIOLATED spacecraft roll limit!")
    else:
        print(f"  ✅ Within spacecraft roll limit")

# Slack time analysis
print(f"\n✓ Slack Time Analysis:")
slacks = [s.slack_time for s in schedule if s.slack_time >= 0]
if slacks:
    tight_maneuvers = [s for s in schedule if 0 <= s.slack_time < 5.0]
    print(f"  Tight maneuvers (<5s slack): {len(tight_maneuvers)}/{len(schedule)}")
    if tight_maneuvers:
        print(f"  Tightest:")
        for s in sorted(tight_maneuvers, key=lambda x: x.slack_time)[:3]:
            print(f"    {s.target_id:15s}: ΔRoll={s.delta_roll:6.2f}°, Slack={s.slack_time:6.2f}s")

print(f"\n{'=' * 100}")
print(f"AGGRESSIVE SCENARIO COMPLETE")
print(f"{'=' * 100}")

if schedule:
    max_roll = max(s.roll_angle for s in schedule)
    max_delta = max(s.delta_roll for s in schedule)
    avg_slew = sum(s.maneuver_time for s in schedule) / len(schedule)
    
    print(f"\nKey Metrics:")
    print(f"  • Maximum roll angle: {max_roll:.2f}°")
    print(f"  • Maximum delta roll: {max_delta:.2f}°")
    print(f"  • Average slew time: {avg_slew:.3f}s")
    print(f"  • Realistic acceleration model: 1.0 deg/s² (not instant)")
    print(f"  • Roll/pitch angles from actual satellite position at imaging time")
else:
    print(f"\n⚠️  No opportunities scheduled - constraints too tight!")
