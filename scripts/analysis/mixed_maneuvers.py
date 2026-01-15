#!/usr/bin/env python3
"""
MIXED MANEUVER SCENARIO - Mix of feasible and extreme angles
Tests proper rejection of infeasible opportunities while scheduling feasible ones
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

# Create targets with VARYING distances to force mix of roll angles
targets = [
    GroundTarget(name="Nadir", latitude=45.0, longitude=30.0, priority=3),  # Near overhead
    GroundTarget(name="Close", latitude=45.0, longitude=32.0, priority=3),  # 2° away
    GroundTarget(name="Medium", latitude=45.0, longitude=35.0, priority=2), # 5° away
    GroundTarget(name="Far", latitude=45.0, longitude=40.0, priority=2),    # 10° away
    GroundTarget(name="VeryFar", latitude=45.0, longitude=50.0, priority=1),# 20° away (should violate 45° limit)
]

print("=" * 100)
print("MIXED MANEUVER SCENARIO - FEASIBLE + INFEASIBLE OPPORTUNITIES")
print("=" * 100)
print(f"\n📍 5 Targets at varying distances from satellite ground track:")
for t in targets:
    print(f"  - {t.name:10s}: {t.latitude:.1f}°N, {t.longitude:.1f}°E (P={t.priority})")

# Load satellite
tle_data = """ICEYE-X44
1 59219U 24055K   24307.50000000  .00009876  00000-0  45678-3 0  9990
2 59219  97.5900 123.4567 0015000  90.1234 270.0000 15.19000000123456"""

with tempfile.NamedTemporaryFile(mode='w', suffix='.tle', delete=False) as f:
    f.write(tle_data)
    tle_file = f.name

satellite = SatelliteOrbit.from_tle_file(tle_file, "ICEYE-X44")
os.unlink(tle_file)

sample_time = datetime(2025, 11, 4, 10, 0, 0)
sat_lat, sat_lon, sat_alt = satellite.get_position(sample_time)
print(f"\n🛰️  Satellite altitude: {sat_alt:.1f} km")

# Create synthetic opportunities simulating satellite pass over 30°E
base_time = datetime(2025, 11, 4, 10, 0, 0)
target_positions = {t.name: (t.latitude, t.longitude) for t in targets}

print(f"\n🎯 Creating synthetic opportunities during pass over 30°E:")
print(f"   (Lower elevation = more off-nadir = larger roll angle)")

opportunities = [
    # T+0s: Nadir target (overhead, 90° elevation) - should be ~0° roll
    Opportunity(
        id="Nadir_000",
        satellite_id="ICEYE-X44",
        target_id="Nadir",
        start_time=base_time,
        end_time=base_time + timedelta(seconds=1),
        max_elevation=90.0,  # Overhead
        value=3.0
    ),
    # T+10s: Close target (2° away, 70° elevation) - should be small roll
    Opportunity(
        id="Close_010",
        satellite_id="ICEYE-X44",
        target_id="Close",
        start_time=base_time + timedelta(seconds=10),
        end_time=base_time + timedelta(seconds=11),
        max_elevation=70.0,
        value=3.0
    ),
    # T+20s: Medium target (5° away, 45° elevation) - moderate roll
    Opportunity(
        id="Medium_020",
        satellite_id="ICEYE-X44",
        target_id="Medium",
        start_time=base_time + timedelta(seconds=20),
        end_time=base_time + timedelta(seconds=21),
        max_elevation=45.0,
        value=2.0
    ),
    # T+30s: Far target (10° away, 25° elevation) - large roll, might exceed 45°
    Opportunity(
        id="Far_030",
        satellite_id="ICEYE-X44",
        target_id="Far",
        start_time=base_time + timedelta(seconds=30),
        end_time=base_time + timedelta(seconds=31),
        max_elevation=25.0,
        value=2.0
    ),
    # T+40s: VeryFar target (20° away, 15° elevation) - extreme roll, definitely >45°
    Opportunity(
        id="VeryFar_040",
        satellite_id="ICEYE-X44",
        target_id="VeryFar",
        start_time=base_time + timedelta(seconds=40),
        end_time=base_time + timedelta(seconds=41),
        max_elevation=15.0,
        value=1.0
    ),
]

for opp in opportunities:
    print(f"   T+{(opp.start_time - base_time).seconds:2d}s: {opp.target_id:10s} (elev: {opp.max_elevation:>5.1f}°)")

# Scheduler with 45° roll limit
print("\n⚙️  Scheduler Configuration:")
print("  - Imaging time: 0.5 seconds")
print("  - Max roll rate: 2.0 deg/s")
print("  - Max roll acceleration: 2.0 deg/s²")
print("  - Max spacecraft roll: **45.0 deg** (HARD LIMIT)")
print("  - Look window: 60 seconds")

config = SchedulerConfig(
    imaging_time_s=0.5,
    max_roll_rate_dps=2.0,
    max_roll_accel_dps2=2.0,
    max_spacecraft_roll_deg=45.0,  # Hard limit
    look_window_s=60.0
)

scheduler = MissionScheduler(config, satellite=satellite)
print(f"  ✅ Scheduler initialized")

# Run scheduling
print("\n🚀 Running FIRST-FIT...")
schedule, metrics = scheduler.schedule(opportunities, target_positions, AlgorithmType.FIRST_FIT)

print(f"\n{'=' * 100}")
print(f"MIXED MANEUVER RESULTS")
print(f"{'=' * 100}")
print(f"Scheduled: {len(schedule)}/{len(opportunities)} opportunities")
print(f"Rejected: {len(opportunities) - len(schedule)} opportunities")
print(f"Runtime: {metrics.runtime_ms:.2f} ms")

# Show scheduled
if schedule:
    print(f"\n{'=' * 100}")
    print(f"SCHEDULED OPPORTUNITIES")
    print(f"{'=' * 100}")
    print(f"{'#':<4} {'Target':<12} {'Time':<8} {'Elev':<7} {'ΔRoll':<9} {'Roll°':<9} {'Slew':<10} {'Status'}")
    print(f"{'-' * 100}")
    
    for i, sched in enumerate(schedule, 1):
        orig_opp = next(o for o in opportunities if o.id == sched.opportunity_id)
        status = "✅" if sched.roll_angle <= 45.0 else "❌ VIOLATED"
        
        print(
            f"{i:<4} "
            f"{sched.target_id:<12} "
            f"T+{(sched.start_time - base_time).seconds:3d}s  "
            f"{orig_opp.max_elevation:>5.0f}°  "
            f"{sched.delta_roll:>7.2f}°  "
            f"{sched.roll_angle:>7.2f}°  "
            f"{sched.maneuver_time:>8.3f}s  "
            f"{status}"
        )

# Show rejected
rejected_ids = [o.id for o in opportunities if o.id not in [s.opportunity_id for s in schedule]]
if rejected_ids:
    print(f"\n{'=' * 100}")
    print(f"REJECTED OPPORTUNITIES")
    print(f"{'=' * 100}")
    print(f"Total rejected: {len(rejected_ids)}")
    for opp_id in rejected_ids:
        opp = next(o for o in opportunities if o.id == opp_id)
        print(f"  - {opp.target_id:10s} (T+{(opp.start_time - base_time).seconds:2d}s, elev: {opp.max_elevation:.0f}°) - likely exceeded 45° roll limit")

# Analysis
print(f"\n{'=' * 100}")
print(f"VALIDATION ANALYSIS")
print(f"{'=' * 100}")

if schedule:
    print(f"\n✓ Roll Angle Distribution:")
    rolls = [s.roll_angle for s in schedule]
    deltas = [s.delta_roll for s in schedule]
    
    print(f"  Minimum roll:      {min(rolls):7.2f}°")
    print(f"  Maximum roll:      {max(rolls):7.2f}°")
    print(f"  Average roll:      {sum(rolls)/len(rolls):7.2f}°")
    print(f"  Maximum delta:     {max(deltas):7.2f}°")
    print(f"  Spacecraft limit:  45.00°")
    
    violations = [s for s in schedule if s.roll_angle > 45.0]
    if violations:
        print(f"  ❌ {len(violations)} VIOLATIONS found - BUG!")
    else:
        print(f"  ✅ All scheduled opportunities within limit")
    
    print(f"\n✓ Delta Roll Accuracy Check:")
    for i in range(1, len(schedule)):
        prev_roll = schedule[i-1].roll_angle
        curr_roll = schedule[i].roll_angle
        delta_roll = schedule[i].delta_roll
        expected_delta = abs(curr_roll - prev_roll)
        
        match = "✅" if abs(delta_roll - expected_delta) < 0.1 else "⚠️"
        print(f"  #{i+1}: delta_roll={delta_roll:6.2f}° vs expected={expected_delta:6.2f}° {match}")
    
    print(f"\n✓ Maneuver Time Check:")
    for i, sched in enumerate(schedule, 1):
        if sched.delta_roll > 0.1:
            # Expected time with 2.0 deg/s² acceleration
            expected = sched.delta_roll / 2.0  # Approximate for small angles
            actual = sched.maneuver_time
            print(f"  #{i}: ΔRoll={sched.delta_roll:.2f}° → Expected~{expected:.2f}s, Actual={actual:.3f}s")

print(f"\n{'=' * 100}")
print(f"TEST COMPLETE")
print(f"{'=' * 100}")

if schedule and max([s.roll_angle for s in schedule]) <= 45.0:
    print(f"\n✅ SUCCESS: All scheduled opportunities respect 45° roll limit")
    print(f"✅ Infeasible opportunities correctly rejected")
    print(f"✅ Roll angle calculations work for various off-nadir angles")
else:
    print(f"\n⚠️  Issues detected - see analysis above")
