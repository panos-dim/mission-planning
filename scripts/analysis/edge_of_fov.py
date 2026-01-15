#!/usr/bin/env python3
"""
EDGE-OF-FOV SCENARIO - Force large roll angles using pass edges
Uses start/end of passes instead of midpoints to force off-nadir imaging
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

# Widely spread targets
targets = [
    GroundTarget(name="Athens", latitude=37.9838, longitude=23.7275, priority=3),
    GroundTarget(name="Stockholm", latitude=59.3293, longitude=18.0686, priority=3),
    GroundTarget(name="Rome", latitude=41.9028, longitude=12.4964, priority=2),
]

print("=" * 100)
print("EDGE-OF-FOV SCENARIO - LARGE ROLL ANGLES FROM PASS EDGES")
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

# Run visibility
start_time = datetime(2025, 11, 3, 0, 0, 0)
end_time = start_time + timedelta(days=2)
calc = VisibilityCalculator(satellite)

all_passes = []
for target in targets:
    target.sensor_fov_half_angle_deg = 45.0  # Wide FOV
    target.elevation_mask_deg = 10.0
    target.imaging_type = 'optical'
    
    passes = calc.find_passes(target, start_time, end_time)
    all_passes.extend([(target.name, p) for p in passes])

print(f"\n✅ Found {len(all_passes)} passes")

# Create opportunities at PASS EDGES (not midpoint) to force larger roll angles
opportunities = []
target_positions = {t.name: (t.latitude, t.longitude) for t in targets}

for target_name, pass_details in all_passes:
    target = next(t for t in targets if t.name == target_name)
    
    # Create opportunity at START of pass (satellite just entering FOV)
    # This forces off-nadir imaging
    early_time = pass_details.start_time + timedelta(seconds=15)
    
    opp = Opportunity(
        id=f"{target_name}_{pass_details.start_time.strftime('%d%H%M')}_edge",
        satellite_id="ICEYE-X44",
        target_id=target_name,
        start_time=early_time,
        end_time=early_time + timedelta(seconds=1),
        max_elevation=pass_details.max_elevation * 0.3,  # Lower elevation at edge
        value=float(target.priority)
    )
    opportunities.append(opp)

opportunities.sort(key=lambda x: x.start_time)
print(f"📊 Created {len(opportunities)} edge-of-FOV opportunities")

# Test with different limits
configs = [
    ("Normal (45°)", 45.0),
    ("Tight (20°)", 20.0),
    ("Very Tight (10°)", 10.0),
    ("Extreme (5°)", 5.0),
]

results = []

for config_name, roll_limit in configs:
    print(f"\n{'=' * 100}")
    print(f"TEST: {config_name} Roll Limit")
    print(f"{'=' * 100}")
    
    config = SchedulerConfig(
        imaging_time_s=0.5,
        max_roll_rate_dps=2.0,
        max_roll_accel_dps2=2.0,
        max_spacecraft_roll_deg=roll_limit,
        look_window_s=600.0
    )
    
    scheduler = MissionScheduler(config, satellite=satellite)
    schedule, metrics = scheduler.schedule(opportunities, target_positions, AlgorithmType.FIRST_FIT)
    
    scheduled_count = len(schedule)
    rejected_count = len(opportunities) - scheduled_count
    
    if schedule:
        rolls = [s.roll_angle for s in schedule]
        deltas = [s.delta_roll for s in schedule]
        slews = [s.maneuver_time for s in schedule]
        
        max_roll = max(rolls)
        violations = sum(1 for r in rolls if r > roll_limit)
        
        print(f"  Scheduled: {scheduled_count}/{len(opportunities)}")
        print(f"  Rejected: {rejected_count}")
        print(f"  Roll angles: min={min(rolls):.2f}°, max={max_roll:.2f}°, avg={sum(rolls)/len(rolls):.2f}°")
        print(f"  Max delta roll: {max(deltas):.2f}°")
        print(f"  Max slew time: {max(slews):.3f}s")
        
        if violations > 0:
            print(f"  ❌ VIOLATIONS: {violations} opportunities exceed {roll_limit}° limit!")
        else:
            print(f"  ✅ All within {roll_limit}° limit")
        
        results.append((config_name, scheduled_count, rejected_count, max_roll, violations))
        
        if max_roll > 5.0:  # Show details for interesting cases
            print(f"\n  Detailed schedule:")
            print(f"  {'#':<4} {'Target':<12} {'Time':<12} {'Roll°':<9} {'ΔRoll':<9} {'Slew':<9}")
            print(f"  {'-' * 70}")
            for i, sched in enumerate(schedule[:5], 1):  # Show first 5
                print(
                    f"  {i:<4} "
                    f"{sched.target_id:<12} "
                    f"{sched.start_time.strftime('%m/%d %H:%M'):<12} "
                    f"{sched.roll_angle:>7.2f}°  "
                    f"{sched.delta_roll:>7.2f}°  "
                    f"{sched.maneuver_time:>7.3f}s"
                )
    else:
        print(f"  ⚠️  No opportunities scheduled (all rejected)")
        results.append((config_name, 0, len(opportunities), 0.0, 0))

# Summary
print(f"\n{'=' * 100}")
print(f"SUMMARY - ROLL LIMIT SCALING")
print(f"{'=' * 100}")
print(f"\n{'Config':<20} {'Scheduled':<12} {'Rejected':<12} {'Max Roll':<12} {'Violations':<12}")
print(f"{'-' * 80}")
for config_name, sched, reject, max_roll, viols in results:
    viol_str = f"{viols} ❌" if viols > 0 else "✅"
    print(f"{config_name:<20} {sched:<12} {reject:<12} {max_roll:>10.2f}°  {viol_str:<12}")

# Check if tighter limits result in fewer scheduled
scheduled_counts = [r[1] for r in results]
if scheduled_counts == sorted(scheduled_counts, reverse=True):
    print(f"\n✅ SUCCESS: Tighter limits correctly reduce scheduled opportunities")
else:
    print(f"\n⚠️  Unexpected pattern")

if all(r[4] == 0 for r in results):  # No violations
    print(f"✅ SUCCESS: No roll limit violations detected")
    print(f"✅ Roll angle calculations and limit enforcement working correctly")
else:
    print(f"❌ BUG: Roll limit violations detected!")

print(f"\n{'=' * 100}")
