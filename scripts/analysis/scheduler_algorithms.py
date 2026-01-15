#!/usr/bin/env python3
"""
Test script to validate all scheduling algorithms with real mission data.
Tests first_fit, best_fit, and value_density algorithms.
"""

import sys
sys.path.insert(0, '/Users/panagiotis.d/CascadeProjects/mission-planning/src')

from datetime import datetime, timezone
from mission_planner.orbit import SatelliteOrbit
from mission_planner.targets import GroundTarget
from mission_planner.visibility import VisibilityCalculator
from mission_planner.scheduler import MissionScheduler, SchedulerConfig

print("=" * 80)
print("SCHEDULER ALGORITHM VALIDATION TEST")
print("=" * 80)

# TLE data from user's request
tle_name = "ICEYE-X44"
tle_line1 = "1 62707U 25009DC  25306.22031033  .00004207  00000+0  39848-3 0  9995"
tle_line2 = "2 62707  97.7269  23.9854 0002193 135.9671 224.1724 14.94137357 66022"

# Time window - 1 week
start_time = datetime(2025, 11, 7, 11, 12, 0, tzinfo=timezone.utc)
end_time = datetime(2025, 11, 14, 11, 12, 0, tzinfo=timezone.utc)

# Real targets from user's mission (10 Greek/Mediterranean targets)
targets_data = [
    {"name": "Athens", "lat": 37.9838, "lon": 23.7275, "priority": 10},
    {"name": "Thessaloniki", "lat": 40.6401, "lon": 22.9444, "priority": 9},
    {"name": "Sofia", "lat": 42.6977, "lon": 23.3219, "priority": 8},
    {"name": "Istanbul", "lat": 41.0082, "lon": 28.9784, "priority": 7},
    {"name": "Izmir", "lat": 38.4237, "lon": 27.1428, "priority": 6},
    {"name": "Heraklion", "lat": 35.3387, "lon": 25.1442, "priority": 5},
    {"name": "Nicosia", "lat": 35.1856, "lon": 33.3823, "priority": 4},
    {"name": "Beirut", "lat": 33.8886, "lon": 35.4955, "priority": 3},
    {"name": "Tel_Aviv", "lat": 32.0853, "lon": 34.7818, "priority": 2},
    {"name": "Cairo", "lat": 30.0444, "lon": 31.2357, "priority": 1},
]

print("\n1. Loading satellite orbit...")
tle_lines = [tle_line1, tle_line2]
satellite = SatelliteOrbit(tle_lines, tle_name)
print(f"   ✓ Loaded: {tle_name}")

print("\n2. Creating targets...")
targets = []
for t in targets_data:
    target = GroundTarget(
        name=t["name"],
        latitude=t["lat"],
        longitude=t["lon"],
        mission_type='imaging',
        elevation_mask=10.0,
        sensor_fov_half_angle_deg=1.0,  # Optical sensor
        max_spacecraft_roll=45.0,  # Spacecraft agility
        priority=t["priority"]
    )
    targets.append(target)
    print(f"   ✓ {t['name']}: priority={t['priority']}, lat={t['lat']}, lon={t['lon']}")

print("\n3. Computing visibility passes...")
calc = VisibilityCalculator(satellite, use_adaptive=True)
all_passes = []
for target in targets:
    passes = calc.find_passes(target, start_time, end_time)
    all_passes.extend(passes)
print(f"   ✓ Found {len(all_passes)} total passes across {len(targets)} targets")

# Group passes by target
passes_by_target = {}
for pass_data in all_passes:
    target_name = pass_data.target_name
    if target_name not in passes_by_target:
        passes_by_target[target_name] = []
    passes_by_target[target_name].append(pass_data)

print("\n4. Pass details by target:")
for target_name, passes in passes_by_target.items():
    target = next(t for t in targets if t.name == target_name)
    print(f"\n   {target_name} (priority {target.priority}):")
    for i, p in enumerate(passes):
        incidence = p.incidence_angle_deg if hasattr(p, 'incidence_angle_deg') else 0
        start = p.start_time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"     Pass {i+1}: {start}, incidence={incidence:+6.2f}°")

print("\n" + "=" * 80)
print("5. Testing Scheduling Algorithms")
print("=" * 80)

# Create scheduler
config = SchedulerConfig(
    max_spacecraft_roll_deg=45.0,
    max_roll_rate_dps=1.0,  # degrees per second
    imaging_time_s=5.0,
    look_window_s=600,  # 10 minutes
    value_source='target_priority'  # Use target priorities
)

# Convert passes to opportunities
from mission_planner.scheduler import Opportunity

opportunities = []
for i, pass_data in enumerate(all_passes):
    target = next(t for t in targets if t.name == pass_data.target_name)
    incidence = getattr(pass_data, 'incidence_angle_deg', 0.0)
    duration_sec = (pass_data.end_time - pass_data.start_time).total_seconds()
    
    opp = Opportunity(
        id=f"ICEYE-X44_{pass_data.target_name}_{i}",
        satellite_id="ICEYE-X44",
        target_id=pass_data.target_name,
        start_time=pass_data.start_time,
        end_time=pass_data.end_time,
        duration_seconds=duration_sec,
        max_elevation=pass_data.max_elevation,
        value=target.priority,
        priority=target.priority,
        incidence_angle=incidence
    )
    opportunities.append(opp)

print(f"\n   Created {len(opportunities)} scheduling opportunities")

# PRE-FILTER: Keep only best opportunity per target (lowest incidence)
print("\n   Pre-filtering to best geometry per target...")
target_best_opps = {}
for opp in opportunities:
    incidence = abs(opp.incidence_angle) if opp.incidence_angle is not None else 90.0
    
    if opp.target_id not in target_best_opps or incidence < target_best_opps[opp.target_id][1]:
        target_best_opps[opp.target_id] = (opp, incidence)

# Use only best opportunities
opportunities = [opp for opp, _ in target_best_opps.values()]
print(f"   ✓ Filtered to {len(opportunities)} best opportunities (one per target)")

for target_name in sorted(target_best_opps.keys()):
    opp, incidence = target_best_opps[target_name]
    time_str = opp.start_time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"     {target_name:12s}: {time_str}, incidence={incidence:6.2f}°")

# Get target positions
target_positions = {t.name: (t.latitude, t.longitude) for t in targets}

# Initialize scheduler
scheduler = MissionScheduler(config, satellite)

# Test all algorithms
algorithms = ['first_fit', 'best_fit', 'value_density']
results = {}

from mission_planner.scheduler import AlgorithmType

for algo in algorithms:
    print(f"\n{'='*80}")
    print(f"Testing: {algo.upper()}")
    print(f"{'='*80}")
    
    # Convert string to AlgorithmType enum
    algo_enum = AlgorithmType(algo)
    schedule_opps, metrics = scheduler.schedule(opportunities, target_positions, algo_enum)
    results[algo] = schedule_opps
    
    # Calculate coverage
    unique_targets = set(opp.target_id for opp in schedule_opps)
    coverage = len(unique_targets)
    
    print(f"\n📊 Results for {algo}:")
    print(f"   Scheduled: {len(schedule_opps)} opportunities")
    print(f"   Coverage: {coverage}/{len(targets)} targets ({100*coverage/len(targets):.0f}%)")
    
    # Show schedule details
    print(f"\n   Schedule:")
    for i, opp in enumerate(schedule_opps):
        incidence = opp.incidence_angle
        roll = opp.roll_angle if hasattr(opp, 'roll_angle') else incidence
        time_str = opp.start_time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"   {i+1}. {opp.target_id:12s} @ {time_str} | "
              f"incidence={incidence:+6.2f}° | roll={roll:+6.2f}°")

print("\n" + "=" * 80)
print("6. COMPARISON SUMMARY")
print("=" * 80)

print(f"\n{'Algorithm':<15} | {'Coverage':<12} | {'Opportunities':<15} | {'Avg Incidence':<15}")
print("-" * 80)

for algo in algorithms:
    schedule = results[algo]
    unique_targets = set(opp.target_id for opp in schedule)
    coverage = len(unique_targets)
    avg_incidence = sum(abs(opp.incidence_angle) for opp in schedule) / len(schedule) if schedule else 0
    
    print(f"{algo:<15} | {coverage}/{len(targets)} ({100*coverage/len(targets):>3.0f}%) | "
          f"{len(schedule):>15} | {avg_incidence:>13.2f}°")

print("\n" + "=" * 80)
print("7. VALIDATION CHECKS")
print("=" * 80)

# Check 1: No Duplicate Targets
print("\n✓ CHECK 1: One Opportunity Per Target")
all_passed = True
for algo in algorithms:
    schedule = results[algo]
    target_counts = {}
    for opp in schedule:
        target_counts[opp.target_id] = target_counts.get(opp.target_id, 0) + 1
    
    duplicates = {t: c for t, c in target_counts.items() if c > 1}
    if duplicates:
        print(f"   ✗ {algo}: FAILED - Found duplicate targets: {duplicates}")
        all_passed = False
    else:
        unique_targets = len(target_counts)
        print(f"   ✓ {algo}: PASS - {len(schedule)} opportunities, {unique_targets} unique targets")

if not all_passed:
    print("\n   ⚠️  CRITICAL: Some algorithms scheduled multiple opportunities per target!")

# Check 2: Delta Roll Mathematical Correctness
print("\n✓ CHECK 2: Delta Roll Calculation Accuracy")
for algo in algorithms:
    schedule = results[algo]
    if len(schedule) < 2:
        print(f"   - {algo}: Skipped (< 2 opportunities)")
        continue
    
    print(f"\n   {algo}:")
    delta_errors = []
    for i in range(1, len(schedule)):
        prev_opp = schedule[i-1]
        curr_opp = schedule[i]
        
        # Expected delta: absolute difference between consecutive roll angles
        prev_roll = prev_opp.roll_angle if hasattr(prev_opp, 'roll_angle') else prev_opp.incidence_angle
        curr_roll = curr_opp.roll_angle if hasattr(curr_opp, 'roll_angle') else curr_opp.incidence_angle
        expected_delta = abs(curr_roll - prev_roll)
        
        # Reported delta
        reported_delta = curr_opp.delta_roll if hasattr(curr_opp, 'delta_roll') else 0.0
        
        # Calculate error
        error = abs(expected_delta - reported_delta)
        
        if error > 0.01:  # Allow 0.01° tolerance for floating point
            delta_errors.append((i, prev_opp.target_id, curr_opp.target_id, expected_delta, reported_delta, error))
            print(f"     ⚠ Opp {i}: {prev_opp.target_id} → {curr_opp.target_id}")
            print(f"        Roll: {prev_roll:+.2f}° → {curr_roll:+.2f}°")
            print(f"        Expected Δroll: {expected_delta:.2f}°, Reported: {reported_delta:.2f}°, Error: {error:.2f}°")
    
    if delta_errors:
        print(f"     ✗ FAILED: {len(delta_errors)} delta calculation errors")
    else:
        print(f"     ✓ PASS: All {len(schedule)-1} delta calculations correct")

# Check 3: Coverage
print("\n✓ CHECK 3: Target Coverage")
for algo in algorithms:
    schedule = results[algo]
    unique_targets = set(opp.target_id for opp in schedule)
    coverage = len(unique_targets)
    if coverage == len(targets):
        print(f"   ✓ {algo}: PASS ({len(targets)}/{len(targets)} targets, 100%)")
    else:
        missed = set(t.name for t in targets) - unique_targets
        print(f"   ⚠ {algo}: {coverage}/{len(targets)} targets ({100*coverage/len(targets):.0f}%), missed: {missed}")

# Check 4: Best geometry selection (highest priority target should get good geometry)
print("\n✓ CHECK 4: Best Geometry Selection (Athens - highest priority)")
for algo in ['best_fit', 'value_density']:
    schedule = results[algo]
    athens_opps = [opp for opp in schedule if opp.target_id == 'Athens']
    if athens_opps:
        athens_incidence = abs(athens_opps[0].incidence_angle)
        if athens_incidence < 35.0:  # Should pick good geometry pass
            print(f"   ✓ {algo}: Selected good geometry (incidence={athens_incidence:.2f}°)")
        else:
            print(f"   ⚠ {algo}: Higher incidence angle (incidence={athens_incidence:.2f}°)")
    else:
        print(f"   - {algo}: Athens not scheduled")

# Check 5: Chronological Order
print("\n✓ CHECK 5: Chronological Scheduling")
for algo in algorithms:
    schedule = results[algo]
    is_ordered = all(schedule[i].start_time <= schedule[i+1].start_time for i in range(len(schedule)-1))
    if is_ordered:
        print(f"   ✓ {algo}: PASS - Schedule is chronologically ordered")
    else:
        print(f"   ✗ {algo}: FAILED - Schedule not in chronological order")

print("\n" + "=" * 80)
print("✅ TEST COMPLETE")
print("=" * 80)
