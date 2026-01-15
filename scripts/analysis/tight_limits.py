#!/usr/bin/env python3
"""
TIGHT ROLL LIMITS SCENARIO - Test rejection with realistic opportunities
Uses real visibility analysis but sets VERY TIGHT roll limits to force rejections
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

# Widely spread targets to create varying roll angles
targets = [
    GroundTarget(name="Athens", latitude=37.9838, longitude=23.7275, priority=3),
    GroundTarget(name="Istanbul", latitude=41.0082, longitude=28.9784, priority=3),
    GroundTarget(name="Stockholm", latitude=59.3293, longitude=18.0686, priority=2),
    GroundTarget(name="Rome", latitude=41.9028, longitude=12.4964, priority=2),
]

print("=" * 100)
print("TIGHT ROLL LIMITS SCENARIO - REALISTIC OPPORTUNITIES + STRICT LIMITS")
print("=" * 100)
print(f"\n📍 4 Targets across Europe:")
for t in targets:
    print(f"  - {t.name:12s}: {t.latitude:>7.4f}°N, {t.longitude:>8.4f}°E (P={t.priority})")

# Load satellite
tle_data = """ICEYE-X44
1 59219U 24055K   24307.50000000  .00009876  00000-0  45678-3 0  9990
2 59219  97.5900 123.4567 0015000  90.1234 270.0000 15.19000000123456"""

with tempfile.NamedTemporaryFile(mode='w', suffix='.tle', delete=False) as f:
    f.write(tle_data)
    tle_file = f.name

satellite = SatelliteOrbit.from_tle_file(tle_file, "ICEYE-X44")
os.unlink(tle_file)

sat_lat, sat_lon, sat_alt = satellite.get_position(datetime(2025, 11, 3, 12, 0, 0))
print(f"\n🛰️  Satellite altitude: {sat_alt:.1f} km")

# Run visibility analysis
start_time = datetime(2025, 11, 3, 0, 0, 0)
end_time = start_time + timedelta(hours=24)
print(f"\n📅 Mission: 24 hours")

print(f"\n🔍 Finding visibility passes...")
calc = VisibilityCalculator(satellite)

all_passes = []
for target in targets:
    target.sensor_fov_half_angle_deg = 45.0
    target.elevation_mask_deg = 10.0
    target.imaging_type = 'optical'
    
    passes = calc.find_passes(target, start_time, end_time)
    print(f"  {target.name:12s}: {len(passes):2d} passes")
    all_passes.extend([(target.name, p) for p in passes])

print(f"\n✅ Total passes: {len(all_passes)}")

# Convert to opportunities
opportunities = []
target_positions = {t.name: (t.latitude, t.longitude) for t in targets}

for target_name, pass_details in all_passes:
    target = next(t for t in targets if t.name == target_name)
    midpoint = pass_details.start_time + (pass_details.end_time - pass_details.start_time) / 2
    
    opp = Opportunity(
        id=f"{target_name}_{pass_details.start_time.strftime('%H%M')}",
        satellite_id="ICEYE-X44",
        target_id=target_name,
        start_time=midpoint,
        end_time=midpoint + timedelta(seconds=1),
        max_elevation=pass_details.max_elevation,
        value=float(target.priority)
    )
    opportunities.append(opp)

opportunities.sort(key=lambda x: x.start_time)
print(f"\n📊 Created {len(opportunities)} opportunities")

# TEST 1: Normal limits (should schedule many)
print(f"\n{'=' * 100}")
print(f"TEST 1: NORMAL LIMITS (45° max roll)")
print(f"{'=' * 100}")

config1 = SchedulerConfig(
    imaging_time_s=1.0,
    max_roll_rate_dps=2.0,
    max_roll_accel_dps2=2.0,
    max_spacecraft_roll_deg=45.0,
    look_window_s=600.0
)

scheduler1 = MissionScheduler(config1, satellite=satellite)
schedule1, metrics1 = scheduler1.schedule(opportunities, target_positions, AlgorithmType.FIRST_FIT)

print(f"Scheduled: {len(schedule1)}/{len(opportunities)}")
if schedule1:
    rolls1 = [s.roll_angle for s in schedule1]
    print(f"Roll angles: min={min(rolls1):.2f}°, max={max(rolls1):.2f}°, avg={sum(rolls1)/len(rolls1):.2f}°")

# TEST 2: Tight limits (should reject some)
print(f"\n{'=' * 100}")
print(f"TEST 2: TIGHT LIMITS (5° max roll - VERY RESTRICTIVE)")
print(f"{'=' * 100}")

config2 = SchedulerConfig(
    imaging_time_s=1.0,
    max_roll_rate_dps=2.0,
    max_roll_accel_dps2=2.0,
    max_spacecraft_roll_deg=5.0,  # VERY TIGHT!
    look_window_s=600.0
)

scheduler2 = MissionScheduler(config2, satellite=satellite)
schedule2, metrics2 = scheduler2.schedule(opportunities, target_positions, AlgorithmType.FIRST_FIT)

print(f"Scheduled: {len(schedule2)}/{len(opportunities)}")
print(f"Rejected: {len(opportunities) - len(schedule2)}")

if schedule2:
    print(f"\n✅ SCHEDULED opportunities (all should have roll ≤5°):")
    print(f"{'#':<4} {'Target':<12} {'Time':<20} {'Roll°':<9} {'ΔRoll':<9} {'Status'}")
    print(f"{'-' * 80}")
    for i, sched in enumerate(schedule2, 1):
        status = "✅" if sched.roll_angle <= 5.0 else "❌ VIOLATED"
        print(
            f"{i:<4} "
            f"{sched.target_id:<12} "
            f"{sched.start_time.strftime('%m/%d %H:%M:%S'):<20} "
            f"{sched.roll_angle:>7.2f}°  "
            f"{sched.delta_roll:>7.2f}°  "
            f"{status}"
        )
    
    rolls2 = [s.roll_angle for s in schedule2]
    violations = [s for s in schedule2 if s.roll_angle > 5.0]
    
    print(f"\n  Roll statistics:")
    print(f"    Min: {min(rolls2):.2f}°, Max: {max(rolls2):.2f}°, Avg: {sum(rolls2)/len(rolls2):.2f}°")
    print(f"    Limit: 5.00°")
    if violations:
        print(f"    ❌ {len(violations)} violations found!")
    else:
        print(f"    ✅ All within limit")

# TEST 3: Very tight limits (might schedule very few)
print(f"\n{'=' * 100}")
print(f"TEST 3: EXTREME LIMITS (1° max roll - NADIR ONLY)")
print(f"{'=' * 100}")

config3 = SchedulerConfig(
    imaging_time_s=1.0,
    max_roll_rate_dps=2.0,
    max_roll_accel_dps2=2.0,
    max_spacecraft_roll_deg=1.0,  # EXTREME!
    look_window_s=600.0
)

scheduler3 = MissionScheduler(config3, satellite=satellite)
schedule3, metrics3 = scheduler3.schedule(opportunities, target_positions, AlgorithmType.FIRST_FIT)

print(f"Scheduled: {len(schedule3)}/{len(opportunities)}")
print(f"Rejected: {len(opportunities) - len(schedule3)}")

if schedule3:
    rolls3 = [s.roll_angle for s in schedule3]
    print(f"Roll angles: min={min(rolls3):.2f}°, max={max(rolls3):.2f}°")
    print(f"✅ With 1° limit, only near-nadir imaging possible")

# Summary
print(f"\n{'=' * 100}")
print(f"SUMMARY - ROLL LIMIT ENFORCEMENT")
print(f"{'=' * 100}")
print(f"\nLimit →  45°: {len(schedule1):2d} scheduled")
print(f"Limit →   5°: {len(schedule2):2d} scheduled (rejected {len(opportunities)-len(schedule2):2d})")
print(f"Limit →   1°: {len(schedule3):2d} scheduled (rejected {len(opportunities)-len(schedule3):2d})")

if len(schedule1) > len(schedule2) > len(schedule3):
    print(f"\n✅ SUCCESS: Tighter limits result in fewer scheduled opportunities")
    print(f"✅ Roll limit enforcement working correctly")
else:
    print(f"\n⚠️  Unexpected scheduling pattern")

print(f"\n{'=' * 100}")
print(f"TEST COMPLETE")
print(f"{'=' * 100}")
