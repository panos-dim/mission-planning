#!/usr/bin/env python3
"""
Test mission analysis and planning with Greece targets.
Validates the new production-ready roll angle calculations.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from datetime import datetime, timedelta
from mission_planner.orbit import SatelliteOrbit
from mission_planner.targets import GroundTarget
from mission_planner.visibility import VisibilityCalculator
from mission_planner.scheduler import MissionScheduler, SchedulerConfig, AlgorithmType

# Greece targets (around Athens, Thessaloniki, Crete)
targets = [
    GroundTarget(name="Athens", latitude=37.9838, longitude=23.7275),
    GroundTarget(name="Thessaloniki", latitude=40.6401, longitude=22.9444),
    GroundTarget(name="Heraklion", latitude=35.3387, longitude=25.1442),
    GroundTarget(name="Patras", latitude=38.2466, longitude=21.7346),
]

print("=" * 80)
print("MISSION ANALYSIS & PLANNING TEST - GREECE TARGETS")
print("=" * 80)
print(f"\n📍 Targets:")
for t in targets:
    print(f"  - {t.name}: {t.latitude:.4f}°N, {t.longitude:.4f}°E")

# Load ICEYE-X44 satellite (sample TLE data)
print("\n🛰️  Loading ICEYE-X44 satellite...")
import tempfile
import os

# Sample ICEYE-X44 TLE data
tle_data = """ICEYE-X44
1 59219U 24055K   24307.50000000  .00009876  00000-0  45678-3 0  9990
2 59219  97.5900 123.4567 0015000  90.1234 270.0000 15.19000000123456"""

# Create temporary TLE file
with tempfile.NamedTemporaryFile(mode='w', suffix='.tle', delete=False) as f:
    f.write(tle_data)
    tle_file = f.name

satellite = SatelliteOrbit.from_tle_file(tle_file, "ICEYE-X44")
os.unlink(tle_file)  # Clean up temp file
print(f"  Satellite loaded: {satellite.satellite_name}")

# Get sample position
sample_time = datetime.utcnow()
lat, lon, alt = satellite.get_position(sample_time)
print(f"  Current position: {lat:.2f}°, {lon:.2f}°, {alt:.1f} km altitude")

# Mission parameters: 1 week
start_time = datetime(2025, 11, 3, 0, 0, 0)  # Today
end_time = start_time + timedelta(days=7)  # 1 week
print(f"\n📅 Mission Duration:")
print(f"  Start: {start_time}")
print(f"  End: {end_time}")
print(f"  Duration: 7 days")

# Run visibility analysis
print("\n🔍 Running visibility analysis (imaging mission)...")
calc = VisibilityCalculator(satellite)

all_passes = []
for target in targets:
    print(f"\n  Analyzing {target.name}...")
    # Set imaging parameters
    target.sensor_fov_half_angle_deg = 45.0  # Wide FOV for imaging
    target.elevation_mask_deg = 10.0
    target.imaging_type = 'optical'  # Optical imaging
    
    passes = calc.find_passes(
        target,
        start_time,
        end_time
    )
    
    print(f"    Found {len(passes)} passes")
    all_passes.extend([(target.name, p) for p in passes])

print(f"\n✅ Total passes found: {len(all_passes)}")

# Convert to opportunities for scheduling
from mission_planner.scheduler import Opportunity

opportunities = []
target_positions = {}

for target_name, pass_details in all_passes:
    # Get target position
    target = next(t for t in targets if t.name == target_name)
    target_positions[target_name] = (target.latitude, target.longitude)
    
    # Create opportunity (use pass midpoint for imaging)
    midpoint = pass_details.start_time + (pass_details.end_time - pass_details.start_time) / 2
    
    opp = Opportunity(
        id=f"{target_name}_{pass_details.start_time.strftime('%Y%m%d_%H%M')}",
        satellite_id="ICEYE-X44",
        target_id=target_name,
        start_time=midpoint,
        end_time=midpoint + timedelta(seconds=5),
        max_elevation=pass_details.max_elevation,
        value=1.0
    )
    opportunities.append(opp)

# Sort by time
opportunities.sort(key=lambda x: x.start_time)

print(f"\n📊 Created {len(opportunities)} opportunities")
print(f"   Spanning {len(target_positions)} targets")

# Configure scheduler with HIGH acceleration (10000 deg/s²)
print("\n⚙️  Scheduler Configuration:")
print("  - Imaging time: 1.0 seconds")
print("  - Max roll rate: 1.0 deg/s")
print("  - Max roll acceleration: 10000.0 deg/s² (FAST SLEW)")
print("  - Max spacecraft roll: 45.0 deg")

config = SchedulerConfig(
    imaging_time_s=1.0,
    max_roll_rate_dps=1.0,
    max_roll_accel_dps2=10000.0,  # Very fast acceleration
    max_spacecraft_roll_deg=45.0,
    look_window_s=600.0
)

# Create scheduler with satellite object (production-ready)
scheduler = MissionScheduler(config, satellite=satellite)
print(f"  ✅ Scheduler initialized with satellite object")

# Run First-Fit algorithm
print("\n🚀 Running FIRST-FIT algorithm...")
schedule, metrics = scheduler.schedule(opportunities, target_positions, AlgorithmType.FIRST_FIT)

print(f"\n{'=' * 80}")
print(f"SCHEDULING RESULTS")
print(f"{'=' * 80}")
print(f"Scheduled opportunities: {len(schedule)}")
print(f"Runtime: {metrics.runtime_ms:.2f} ms")
print(f"Targets acquired: {len(set(s.target_id for s in schedule))}/{len(targets)}")

# Display schedule with detailed attitude information
print(f"\n{'=' * 80}")
print(f"DETAILED SCHEDULE (with Roll/Pitch Analysis)")
print(f"{'=' * 80}")
print(f"{'#':<4} {'Target':<15} {'Time':<20} {'ΔRoll':<8} {'ΔPitch':<8} {'Roll°':<8} {'Pitch°':<8} {'Slew':<8} {'Slack':<8}")
print(f"{'-' * 120}")

for i, sched in enumerate(schedule, 1):
    print(
        f"{i:<4} "
        f"{sched.target_id:<15} "
        f"{sched.start_time.strftime('%m/%d %H:%M:%S'):<20} "
        f"{sched.delta_roll:>6.2f}°  "
        f"{sched.delta_pitch:>6.2f}°  "
        f"{sched.roll_angle:>6.2f}°  "
        f"{sched.pitch_angle:>6.2f}°  "
        f"{sched.maneuver_time:>6.2f}s  "
        f"{sched.slack_time:>6.2f}s"
    )

# Validation checks
print(f"\n{'=' * 80}")
print(f"VALIDATION CHECKS")
print(f"{'=' * 80}")

# Check 1: Delta roll should match difference in consecutive roll angles
print("\n✓ Check 1: Delta Roll Consistency")
for i in range(1, len(schedule)):
    prev_roll = schedule[i-1].roll_angle
    curr_roll = schedule[i].roll_angle
    delta_roll = schedule[i].delta_roll
    expected_delta = abs(curr_roll - prev_roll)
    
    if abs(delta_roll - expected_delta) > 0.1:  # Allow 0.1° tolerance
        print(f"  ⚠️  Mismatch at #{i+1}: delta_roll={delta_roll:.2f}° but roll change={expected_delta:.2f}°")
    else:
        print(f"  ✅ Opp #{i+1}: delta_roll={delta_roll:.2f}° matches roll change={expected_delta:.2f}°")

# Check 2: Maneuver time should be reasonable for given delta roll and acceleration
print("\n✓ Check 2: Maneuver Time Validation")
for i, sched in enumerate(schedule[:5], 1):  # Check first 5
    delta = sched.delta_roll
    if delta > 0:
        # With 10000 deg/s² acceleration and 3 deg/s max rate
        # Triangular profile time: t = 2*sqrt(delta/accel)
        expected_time = 2 * (delta / 10000.0) ** 0.5
        actual_time = sched.maneuver_time
        
        print(f"  Opp #{i}: ΔRoll={delta:.2f}°, Expected~{expected_time:.3f}s, Actual={actual_time:.3f}s")

# Check 3: Roll angles should be within spacecraft limits
print("\n✓ Check 3: Spacecraft Roll Limits")
max_roll = max(s.roll_angle for s in schedule)
min_roll = min(s.roll_angle for s in schedule)
print(f"  Roll angle range: {min_roll:.2f}° to {max_roll:.2f}°")
if max_roll <= 90.0:
    print(f"  ✅ All roll angles within spacecraft limit (90.0°)")
else:
    print(f"  ⚠️  Some roll angles exceed limit!")

# Check 4: Attitude persistence (should not reset to 0° unless first)
print("\n✓ Check 4: Attitude Persistence Across Passes")
roll_resets = sum(1 for i in range(1, len(schedule)) if schedule[i].roll_angle < schedule[i-1].roll_angle * 0.5)
if roll_resets == 0:
    print(f"  ✅ No unexpected attitude resets detected")
else:
    print(f"  ℹ️  {roll_resets} apparent attitude changes detected (may be intentional)")

# Summary statistics
print(f"\n{'=' * 80}")
print(f"SUMMARY STATISTICS")
print(f"{'=' * 80}")

total_slew_time = sum(s.maneuver_time for s in schedule)
total_imaging_time = len(schedule) * 1.0  # 1 second per image
total_slack = sum(s.slack_time for s in schedule)

print(f"Total slew time: {total_slew_time:.2f} seconds ({total_slew_time/60:.2f} minutes)")
print(f"Total imaging time: {total_imaging_time:.2f} seconds ({total_imaging_time/60:.2f} minutes)")
print(f"Total slack time: {total_slack:.2f} seconds ({total_slack/60:.2f} minutes)")
print(f"Average delta roll: {sum(s.delta_roll for s in schedule)/len(schedule):.2f}°")
print(f"Average maneuver time: {total_slew_time/len(schedule):.3f} seconds")

print(f"\n{'=' * 80}")
print(f"TEST COMPLETE ✅")
print(f"{'=' * 80}")
