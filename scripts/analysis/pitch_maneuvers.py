#!/usr/bin/env python3
"""
PITCH MANEUVER SCENARIO - Test along-track (pitch) pointing
Creates targets along satellite ground track to force forward/backward looking
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

print("=" * 100)
print("PITCH MANEUVER SCENARIO - ALONG-TRACK POINTING TEST")
print("=" * 100)

# Load satellite
tle_data = """ICEYE-X44
1 59219U 24055K   24307.50000000  .00009876  00000-0  45678-3 0  9990
2 59219  97.5900 123.4567 0015000  90.1234 270.0000 15.19000000123456"""

with tempfile.NamedTemporaryFile(mode='w', suffix='.tle', delete=False) as f:
    f.write(tle_data)
    tle_file = f.name

satellite = SatelliteOrbit.from_tle_file(tle_file, "ICEYE-X44")
os.unlink(tle_file)

# Get satellite ground track direction
sample_time = datetime(2025, 11, 4, 10, 0, 0)
sat_lat1, sat_lon1, sat_alt = satellite.get_position(sample_time)
sat_lat2, sat_lon2, _ = satellite.get_position(sample_time + timedelta(seconds=60))

print(f"\n🛰️  Satellite Info:")
print(f"  Altitude: {sat_alt:.1f} km")
print(f"  Ground track at T+0:  {sat_lat1:.2f}°N, {sat_lon1:.2f}°E")
print(f"  Ground track at T+60s: {sat_lat2:.2f}°N, {sat_lon2:.2f}°E")
print(f"  Direction: {'South→North' if sat_lat2 > sat_lat1 else 'North→South'}")

# Create targets ALONG the ground track (north-south line)
# This forces pitch (along-track) maneuvers instead of roll (cross-track)
center_lat = 45.0
center_lon = 25.0

targets = [
    # Along-track targets (varying latitude, same longitude)
    GroundTarget(name="South", latitude=center_lat - 5.0, longitude=center_lon, priority=3),  # 5° south
    GroundTarget(name="Center", latitude=center_lat, longitude=center_lon, priority=3),        # Center
    GroundTarget(name="North", latitude=center_lat + 5.0, longitude=center_lon, priority=3),   # 5° north
    
    # Add one cross-track target for comparison
    GroundTarget(name="East_CrossTrack", latitude=center_lat, longitude=center_lon + 5.0, priority=2),
]

print(f"\n📍 Target Configuration (testing pitch maneuvers):")
print(f"  Along-track targets (same lon, varying lat):")
for t in targets[:3]:
    print(f"    - {t.name:15s}: {t.latitude:>6.1f}°N, {t.longitude:>6.1f}°E")
print(f"  Cross-track target (for comparison):")
print(f"    - {targets[3].name:15s}: {targets[3].latitude:>6.1f}°N, {targets[3].longitude:>6.1f}°E")

# Mission analysis
start_time = datetime(2025, 11, 3, 0, 0, 0)
end_time = start_time + timedelta(days=2)

print(f"\n🔍 Running visibility analysis (45° FOV)...")
calc = VisibilityCalculator(satellite)

all_passes = []
for target in targets:
    target.sensor_fov_half_angle_deg = 45.0
    target.elevation_mask_deg = 10.0
    target.imaging_type = 'optical'
    
    passes = calc.find_passes(target, start_time, end_time)
    print(f"  {target.name:15s}: {len(passes):2d} passes")
    all_passes.extend([(target.name, p) for p in passes])

print(f"\n✅ Total passes: {len(all_passes)}")

# Convert to opportunities
opportunities = []
target_positions = {t.name: (t.latitude, t.longitude) for t in targets}

for target_name, pass_details in all_passes:
    target = next(t for t in targets if t.name == target_name)
    midpoint = pass_details.start_time + (pass_details.end_time - pass_details.start_time) / 2
    
    opp = Opportunity(
        id=f"{target_name}_{pass_details.start_time.strftime('%d%H%M')}",
        satellite_id="ICEYE-X44",
        target_id=target_name,
        start_time=midpoint,
        end_time=midpoint + timedelta(seconds=1),
        max_elevation=pass_details.max_elevation,
        value=float(target.priority)
    )
    opportunities.append(opp)

opportunities.sort(key=lambda x: x.start_time)
print(f"📊 Created {len(opportunities)} opportunities")

# Scheduler with normal limits
print(f"\n⚙️  Scheduler Configuration:")
print(f"  - Imaging time: 1.0 seconds")
print(f"  - Max roll rate: 1.0 deg/s")
print(f"  - Max roll acceleration: 10000.0 deg/s²")
print(f"  - Max spacecraft roll: 45.0 deg")

config = SchedulerConfig(
    imaging_time_s=1.0,
    max_roll_rate_dps=1.0,
    max_roll_accel_dps2=10000.0,
    max_spacecraft_roll_deg=45.0,
    look_window_s=600.0
)

scheduler = MissionScheduler(config, satellite=satellite)

# Run FIRST_FIT
print(f"\n🚀 Running FIRST-FIT...")
schedule, metrics = scheduler.schedule(opportunities, target_positions, AlgorithmType.FIRST_FIT)

print(f"\n{'=' * 100}")
print(f"PITCH MANEUVER RESULTS")
print(f"{'=' * 100}")
print(f"Scheduled: {len(schedule)}/{len(opportunities)}")
print(f"Targets: {len(set(s.target_id for s in schedule))}/{len(targets)}")

# Analyze roll vs pitch
print(f"\n{'=' * 100}")
print(f"ROLL vs PITCH ANALYSIS")
print(f"{'=' * 100}")
print(f"{'#':<4} {'Target':<20} {'Time':<12} {'ΔRoll':<9} {'ΔPitch':<9} {'Roll°':<9} {'Pitch°':<9} {'Type':<15}")
print(f"{'-' * 110}")

for i, sched in enumerate(schedule, 1):
    # Determine if this is cross-track (roll) or along-track (pitch) based on target
    is_cross_track = "CrossTrack" in sched.target_id
    maneuver_type = "Cross-Track (Roll)" if is_cross_track else "Along-Track (Pitch?)"
    
    print(
        f"{i:<4} "
        f"{sched.target_id:<20} "
        f"{sched.start_time.strftime('%m/%d %H:%M'):<12} "
        f"{sched.delta_roll:>7.2f}°  "
        f"{sched.delta_pitch:>7.2f}°  "
        f"{sched.roll_angle:>7.2f}°  "
        f"{sched.pitch_angle:>7.2f}°  "
        f"{maneuver_type:<15}"
    )

# Statistics
if schedule:
    rolls = [s.roll_angle for s in schedule]
    pitches = [s.pitch_angle for s in schedule]
    delta_rolls = [s.delta_roll for s in schedule]
    delta_pitches = [s.delta_pitch for s in schedule]
    
    print(f"\n{'=' * 100}")
    print(f"STATISTICS")
    print(f"{'=' * 100}")
    
    print(f"\n✓ Roll Angles:")
    print(f"  Absolute roll: min={min(rolls):.2f}°, max={max(rolls):.2f}°, avg={sum(rolls)/len(rolls):.2f}°")
    print(f"  Delta roll: min={min(delta_rolls):.2f}°, max={max(delta_rolls):.2f}°, avg={sum(delta_rolls)/len(delta_rolls):.2f}°")
    
    print(f"\n✓ Pitch Angles:")
    print(f"  Absolute pitch: min={min(pitches):.2f}°, max={max(pitches):.2f}°, avg={sum(pitches)/len(pitches):.2f}°")
    print(f"  Delta pitch: min={min(delta_pitches):.2f}°, max={max(delta_pitches):.2f}°, avg={sum(delta_pitches)/len(delta_pitches):.2f}°")
    
    # Check if pitch is actually being used
    max_pitch = max(abs(p) for p in pitches)
    max_delta_pitch = max(delta_pitches)
    
    print(f"\n✓ Pitch Implementation Status:")
    if max_pitch > 0.1 or max_delta_pitch > 0.1:
        print(f"  ✅ PITCH IS IMPLEMENTED: Max pitch={max_pitch:.2f}°, Max delta={max_delta_pitch:.2f}°")
    else:
        print(f"  ⚠️  PITCH NOT IMPLEMENTED: All pitch values = 0.00°")
        print(f"  ℹ️  Current implementation uses ROLL only (nadir + cross-track)")
        print(f"  ℹ️  Along-track targets are being reached via orbital motion, not pitch")
    
    # Explain what's happening
    print(f"\n✓ How Along-Track Targets Are Imaged:")
    print(f"  Current: Satellite waits for orbital motion to bring it over target (no pitch needed)")
    print(f"  With Pitch: Satellite could point forward/backward along track to image earlier/later")
    print(f"  → Pitch would allow \"forward-looking\" or \"backward-looking\" imaging")

print(f"\n{'=' * 100}")
print(f"PITCH SCENARIO TEST COMPLETE")
print(f"{'=' * 100}")

print(f"\n📝 KEY FINDINGS:")
if schedule:
    if max(abs(s.pitch_angle) for s in schedule) < 0.1:
        print(f"  • Current implementation: ROLL-ONLY (nadir + cross-track pointing)")
        print(f"  • Pitch maneuvers: NOT YET IMPLEMENTED")
        print(f"  • Along-track imaging: Achieved via orbital motion (wait for satellite to move)")
        print(f"  • To test pitch: Would need to implement pitch calculation in compute_target_roll_pitch()")
    else:
        print(f"  • Pitch maneuvers: IMPLEMENTED AND WORKING!")
else:
    print(f"  • No opportunities scheduled - check visibility windows")
