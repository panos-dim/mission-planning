#!/usr/bin/env python3
"""
Test Greece 24-hour mission with exact targets from UI
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

print("=" * 100)
print("GREECE 24-HOUR MISSION VALIDATION")
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

# Exact targets from UI
targets = [
    GroundTarget(name="Athens", latitude=37.9838, longitude=23.7275, priority=3),
    GroundTarget(name="Thessaloniki", latitude=40.6401, longitude=22.9444, priority=2),
    GroundTarget(name="Izmir", latitude=38.4237, longitude=27.1428, priority=2),
    GroundTarget(name="Heraklion", latitude=35.3387, longitude=25.1442, priority=1),
]

print(f"\n📍 Targets:")
for t in targets:
    print(f"  {t.name:15s}: {t.latitude:>7.4f}°N, {t.longitude:>7.4f}°E, Priority={t.priority}")

# Mission window (24 hours)
start_time = datetime(2025, 11, 4, 11, 0, 0)
end_time = start_time + timedelta(hours=24)

print(f"\n⏰ Mission Window: {start_time} to {end_time}")

# Find passes
print(f"\n🔍 Finding visibility passes...")
calc = VisibilityCalculator(satellite)

all_passes = []
for target in targets:
    target.sensor_fov_half_angle_deg = 45.0
    target.elevation_mask_deg = 10.0
    target.imaging_type = 'optical'
    
    passes = calc.find_passes(target, start_time, end_time)
    print(f"  {target.name:15s}: {len(passes):2d} passes")
    all_passes.extend([(target.name, p) for p in passes])

# Convert to opportunities
opportunities = []
target_positions = {t.name: (t.latitude, t.longitude) for t in targets}

for target_name, pass_details in all_passes:
    target = next(t for t in targets if t.name == target_name)
    midpoint = pass_details.start_time + (pass_details.end_time - pass_details.start_time) / 2
    
    opp = Opportunity(
        id=f"ICEYE-X44_{target_name}_{pass_details.start_time.strftime('%d%H%M')}",
        satellite_id="ICEYE-X44",
        target_id=target_name,
        start_time=midpoint,
        end_time=midpoint + timedelta(seconds=1),
        max_elevation=pass_details.max_elevation,
        value=float(target.priority),
        incidence_angle=pass_details.incidence_angle_deg
    )
    opportunities.append(opp)

opportunities.sort(key=lambda x: x.start_time)
print(f"\n📊 Total opportunities: {len(opportunities)}")

# Scheduler config
config = SchedulerConfig(
    imaging_time_s=1.0,
    max_roll_rate_dps=1.0,
    max_roll_accel_dps2=10000.0,
    max_spacecraft_roll_deg=45.0,
    look_window_s=600.0
)

scheduler = MissionScheduler(config, satellite=satellite)

print(f"\n{'=' * 100}")
print(f"ALGORITHM COMPARISON")
print(f"{'=' * 100}")

algorithms = [
    (AlgorithmType.FIRST_FIT, "First-Fit"),
    (AlgorithmType.BEST_FIT, "Best-Fit"),
    (AlgorithmType.VALUE_DENSITY, "Value-Density")
]

results = {}

for algo_type, algo_name in algorithms:
    schedule, metrics = scheduler.schedule(opportunities, target_positions, algo_type)
    results[algo_name] = (schedule, metrics)
    
    print(f"\n{algo_name}:")
    print(f"  Targets: {len(set(s.target_id for s in schedule))}/{len(targets)}")
    print(f"  Opportunities: {len(schedule)}/{len(opportunities)}")
    print(f"  Total Value: {sum(s.value for s in schedule):.2f}")

# Detailed schedule for each algorithm
for algo_name, (schedule, metrics) in results.items():
    print(f"\n{'=' * 100}")
    print(f"{algo_name} DETAILED SCHEDULE")
    print(f"{'=' * 100}")
    
    if not schedule:
        print("  No opportunities scheduled")
        continue
    
    print(f"{'#':<3} {'Target':<15} {'Time':<20} {'Inc°':<6} {'ΔRoll°':<8} {'Roll°':<7} {'Slew(s)':<8} {'Slack(s)':<9} {'Value':<6}")
    print("-" * 100)
    
    for i, s in enumerate(schedule, 1):
        print(
            f"{i:<3} "
            f"{s.target_id:<15} "
            f"{s.start_time.strftime('%m/%d %H:%M:%S'):<20} "
            f"{s.incidence_angle:>5.1f}  "
            f"{s.delta_roll:>6.2f}°  "
            f"{s.roll_angle:>5.2f}°  "
            f"{s.maneuver_time:>6.2f}s  "
            f"{s.slack_time:>7.2f}s  "
            f"{s.value:>5.2f}"
        )

# VALIDATION
print(f"\n{'=' * 100}")
print(f"VALIDATION CHECKS")
print(f"{'=' * 100}")

for algo_name, (schedule, metrics) in results.items():
    print(f"\n{algo_name}:")
    
    if len(schedule) < 2:
        print("  ⚠️  Less than 2 opportunities - skipping validation")
        continue
    
    # Check delta roll consistency
    errors = []
    for i in range(1, len(schedule)):
        prev = schedule[i-1]
        curr = schedule[i]
        
        expected_delta = abs(curr.roll_angle - prev.roll_angle)
        actual_delta = curr.delta_roll
        
        if abs(expected_delta - actual_delta) > 0.1:
            errors.append(f"  ❌ Opp #{i+1} ({curr.target_id}): ΔRoll={actual_delta:.2f}° but should be {expected_delta:.2f}° (from {prev.roll_angle:.2f}° to {curr.roll_angle:.2f}°)")
    
    if errors:
        print("  ❌ DELTA ROLL ERRORS:")
        for err in errors:
            print(err)
    else:
        print("  ✅ Delta roll calculations correct")
    
    # Check feasibility
    feasibility_errors = []
    for i in range(1, len(schedule)):
        prev = schedule[i-1]
        curr = schedule[i]
        
        time_gap = (curr.start_time - (prev.end_time + timedelta(seconds=1))).total_seconds()
        slew_needed = curr.maneuver_time
        
        if slew_needed > time_gap + 0.1:  # Allow 0.1s tolerance
            feasibility_errors.append(f"  ❌ Opp #{i+1} ({curr.target_id}): Needs {slew_needed:.2f}s slew but only {time_gap:.2f}s available")
    
    if feasibility_errors:
        print("  ❌ FEASIBILITY ERRORS:")
        for err in feasibility_errors:
            print(err)
    else:
        print("  ✅ All opportunities feasible")

print(f"\n{'=' * 100}")
print(f"VALIDATION COMPLETE")
print(f"{'=' * 100}")
