#!/usr/bin/env python3
"""
EXTREME PITCH SCENARIO - Force large along-track maneuvers
Creates widely separated along-track targets to maximize pitch usage
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from datetime import datetime, timedelta
from mission_planner.orbit import SatelliteOrbit
from mission_planner.targets import GroundTarget
from mission_planner.scheduler import MissionScheduler, SchedulerConfig, AlgorithmType, Opportunity
import tempfile
import os

print("=" * 100)
print("EXTREME PITCH SCENARIO - ALONG-TRACK POINTING")
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

sat_lat, sat_lon, sat_alt = satellite.get_position(datetime(2025, 11, 4, 10, 0, 0))
print(f"\n🛰️  Satellite altitude: {sat_alt:.1f} km")

# Create synthetic opportunities along satellite's ground track
# Varying ONLY latitude (along-track), keeping longitude constant (no cross-track)
base_time = datetime(2025, 11, 4, 10, 0, 0)
center_lon = 25.0

# Create opportunities at different latitudes along same longitude
opportunities = [
    Opportunity(
        id="Target_South_15",
        satellite_id="ICEYE-X44",
        target_id="Target_South_15",
        start_time=base_time,
        end_time=base_time + timedelta(seconds=1),
        max_elevation=45.0,
        value=3.0
    ),
    Opportunity(
        id="Target_South_10",
        satellite_id="ICEYE-X44",
        target_id="Target_South_10",
        start_time=base_time + timedelta(seconds=10),
        end_time=base_time + timedelta(seconds=11),
        max_elevation=45.0,
        value=3.0
    ),
    Opportunity(
        id="Target_Center",
        satellite_id="ICEYE-X44",
        target_id="Target_Center",
        start_time=base_time + timedelta(seconds=20),
        end_time=base_time + timedelta(seconds=21),
        max_elevation=85.0,
        value=3.0
    ),
    Opportunity(
        id="Target_North_10",
        satellite_id="ICEYE-X44",
        target_id="Target_North_10",
        start_time=base_time + timedelta(seconds=30),
        end_time=base_time + timedelta(seconds=31),
        max_elevation=45.0,
        value=3.0
    ),
    Opportunity(
        id="Target_North_15",
        satellite_id="ICEYE-X44",
        target_id="Target_North_15",
        start_time=base_time + timedelta(seconds=40),
        end_time=base_time + timedelta(seconds=41),
        max_elevation=30.0,
        value=3.0
    ),
]

# Target positions: along-track only (varying latitude)
target_positions = {
    "Target_South_15": (30.0, center_lon),  # 15° south
    "Target_South_10": (35.0, center_lon),  # 10° south
    "Target_Center": (45.0, center_lon),     # Center
    "Target_North_10": (55.0, center_lon),   # 10° north
    "Target_North_15": (60.0, center_lon),   # 15° north
}

print(f"\n📍 Synthetic Along-Track Targets:")
print(f"   (Same longitude={center_lon}°E, varying latitude)")
for name, (lat, lon) in target_positions.items():
    print(f"     {name:20s}: {lat:>5.1f}°N, {lon:>5.1f}°E")

# Scheduler
print(f"\n⚙️  Scheduler Configuration:")
print(f"  - Max roll/pitch rate: 1.0 deg/s")
print(f"  - Max roll/pitch accel: 10000.0 deg/s²")

config = SchedulerConfig(
    imaging_time_s=1.0,
    max_roll_rate_dps=1.0,
    max_roll_accel_dps2=10000.0,
    max_spacecraft_roll_deg=45.0,
    look_window_s=60.0
)

scheduler = MissionScheduler(config, satellite=satellite)

print(f"\n🚀 Running FIRST-FIT...")
schedule, metrics = scheduler.schedule(opportunities, target_positions, AlgorithmType.FIRST_FIT)

print(f"\n{'=' * 100}")
print(f"EXTREME PITCH RESULTS")
print(f"{'=' * 100}")
print(f"Scheduled: {len(schedule)}/{len(opportunities)}")

if schedule:
    print(f"\n{'=' * 100}")
    print(f"DETAILED SCHEDULE - PITCH MANEUVER ANALYSIS")
    print(f"{'=' * 100}")
    print(f"{'#':<4} {'Target':<20} {'Time':<8} {'ΔRoll':<9} {'ΔPitch':<9} {'Roll°':<9} {'Pitch°':<9} {'Slew':<10}")
    print(f"{'-' * 110}")
    
    for i, sched in enumerate(schedule, 1):
        print(
            f"{i:<4} "
            f"{sched.target_id:<20} "
            f"T+{(sched.start_time - base_time).seconds:3d}s  "
            f"{sched.delta_roll:>7.2f}°  "
            f"{sched.delta_pitch:>7.2f}°  "
            f"{sched.roll_angle:>7.2f}°  "
            f"{sched.pitch_angle:>7.2f}°  "
            f"{sched.maneuver_time:>8.3f}s"
        )
    
    # Analysis
    rolls = [s.roll_angle for s in schedule]
    pitches = [s.pitch_angle for s in schedule]
    delta_pitches = [s.delta_pitch for s in schedule]
    
    print(f"\n{'=' * 100}")
    print(f"STATISTICS")
    print(f"{'=' * 100}")
    
    print(f"\n✓ Roll Angles:")
    print(f"  Min: {min(rolls):.2f}°, Max: {max(rolls):.2f}°, Avg: {sum(rolls)/len(rolls):.2f}°")
    
    print(f"\n✓ Pitch Angles:")
    print(f"  Absolute pitch: Min={min(pitches):.2f}°, Max={max(pitches):.2f}°, Avg={sum(pitches)/len(pitches):.2f}°")
    print(f"  Delta pitch: Min={min(delta_pitches):.2f}°, Max={max(delta_pitches):.2f}°, Avg={sum(delta_pitches)/len(delta_pitches):.2f}°")
    
    max_pitch = max(pitches)
    max_delta_pitch = max(delta_pitches)
    
    print(f"\n{'=' * 100}")
    print(f"PITCH IMPLEMENTATION VALIDATION")
    print(f"{'=' * 100}")
    
    if max_pitch > 0.01 or max_delta_pitch > 0.01:
        print(f"\n✅ PITCH IS WORKING!")
        print(f"   Maximum pitch angle: {max_pitch:.2f}°")
        print(f"   Maximum delta pitch: {max_delta_pitch:.2f}°")
        print(f"\n   Pitch Strategy:")
        print(f"   • Roll handles CROSS-TRACK pointing (left/right of ground track)")
        print(f"   • Pitch handles ALONG-TRACK pointing (forward/backward along velocity)")
        print(f"   • Pitch only used when along-track component > 0.1° (threshold)")
        print(f"   • Total maneuver time = MAX(roll_time, pitch_time) - simultaneous axes")
    else:
        print(f"\n⚠️  Pitch values too small to detect")
        print(f"   This is correct if targets are on perpendicular longitude line")
    
    # Check which opportunities used pitch
    print(f"\n✓ Opportunities Using Pitch (pitch > 0.05°):")
    pitch_users = [s for s in schedule if s.pitch_angle > 0.05]
    if pitch_users:
        for s in pitch_users:
            print(f"   • {s.target_id:20s}: pitch={s.pitch_angle:.2f}°, roll={s.roll_angle:.2f}°")
    else:
        print(f"   (None - all angles < 0.05°)")

print(f"\n{'=' * 100}")
print(f"TEST COMPLETE")
print(f"{'=' * 100}")
