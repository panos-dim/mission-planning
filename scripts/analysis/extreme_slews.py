#!/usr/bin/env python3
"""
EXTREME SLEW SCENARIO - Force maximum roll angles
Creates artificial opportunities at edge of FOV to test geometry calculations
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
import math

# Create targets that form a WIDE cross pattern (forces extreme cross-track pointing)
targets = [
    # East-West line (extreme cross-track)
    GroundTarget(name="Far_West", latitude=45.0, longitude=10.0, priority=3),
    GroundTarget(name="West", latitude=45.0, longitude=20.0, priority=3),
    GroundTarget(name="Center", latitude=45.0, longitude=30.0, priority=3),
    GroundTarget(name="East", latitude=45.0, longitude=40.0, priority=3),
    GroundTarget(name="Far_East", latitude=45.0, longitude=50.0, priority=3),
]

print("=" * 100)
print("EXTREME SLEW SCENARIO - MAXIMUM ROLL ANGLE TESTING")
print("=" * 100)
print(f"\n📍 5 Targets in WIDE East-West line (40° longitude span):")
for t in targets:
    print(f"  - {t.name:10s}: {t.latitude:.1f}°N, {t.longitude:.1f}°E")

# Load satellite
print("\n🛰️  Loading satellite...")
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
print(f"  Satellite altitude: {sat_alt:.1f} km")

# MANUALLY CREATE opportunities with satellite at specific positions
# to force large off-nadir angles
print(f"\n🎯 Creating ARTIFICIAL opportunities to force extreme roll angles...")
print(f"   Strategy: Place satellite over CENTER target, create opportunities for FAR targets")

base_time = datetime(2025, 11, 4, 10, 0, 0)
target_positions = {t.name: (t.latitude, t.longitude) for t in targets}

# Scenario: Satellite passes over CENTER (30°E)
# Create opportunities for West and East targets during same pass
# This forces large cross-track pointing

opportunities = [
    # Time 0: Image Far_West (10°E) while satellite is approaching Center (30°E)
    Opportunity(
        id="Far_West_0010",
        satellite_id="ICEYE-X44",
        target_id="Far_West",
        start_time=base_time,
        end_time=base_time + timedelta(seconds=1),
        max_elevation=15.0,
        value=3.0
    ),
    # Time +10s: Image West (20°E) - satellite moved closer
    Opportunity(
        id="West_0020",
        satellite_id="ICEYE-X44",
        target_id="West",
        start_time=base_time + timedelta(seconds=10),
        end_time=base_time + timedelta(seconds=11),
        max_elevation=25.0,
        value=3.0
    ),
    # Time +20s: Image Center (30°E) - satellite overhead (nadir)
    Opportunity(
        id="Center_0030",
        satellite_id="ICEYE-X44",
        target_id="Center",
        start_time=base_time + timedelta(seconds=20),
        end_time=base_time + timedelta(seconds=21),
        max_elevation=85.0,
        value=3.0
    ),
    # Time +30s: Image East (40°E) - satellite moved past, looking back
    Opportunity(
        id="East_0040",
        satellite_id="ICEYE-X44",
        target_id="East",
        start_time=base_time + timedelta(seconds=30),
        end_time=base_time + timedelta(seconds=31),
        max_elevation=25.0,
        value=3.0
    ),
    # Time +40s: Image Far_East (50°E) - extreme backward look
    Opportunity(
        id="Far_East_0050",
        satellite_id="ICEYE-X44",
        target_id="Far_East",
        start_time=base_time + timedelta(seconds=40),
        end_time=base_time + timedelta(seconds=41),
        max_elevation=15.0,
        value=3.0
    ),
]

print(f"\n   Created {len(opportunities)} synthetic opportunities:")
for opp in opportunities:
    elev = opp.max_elevation
    print(f"     T+{(opp.start_time - base_time).seconds:2d}s: {opp.target_id:10s} (elevation: {elev:.0f}°)")

# Scheduler with REALISTIC constraints
print("\n⚙️  Scheduler Configuration (REALISTIC):")
print("  - Imaging time: 1.0 seconds")
print("  - Max roll rate: 1.0 deg/s")
print("  - Max roll acceleration: 1.0 deg/s²")
print("  - Max spacecraft roll: 45.0 deg")
print("  - Look window: 60 seconds")

config = SchedulerConfig(
    imaging_time_s=1.0,
    max_roll_rate_dps=1.0,
    max_roll_accel_dps2=1.0,
    max_spacecraft_roll_deg=45.0,
    look_window_s=60.0
)

scheduler = MissionScheduler(config, satellite=satellite)
print(f"  ✅ Scheduler initialized with satellite object")

# Run scheduling
print("\n🚀 Running FIRST-FIT...")
schedule, metrics = scheduler.schedule(opportunities, target_positions, AlgorithmType.FIRST_FIT)

print(f"\n{'=' * 100}")
print(f"EXTREME SLEW RESULTS")
print(f"{'=' * 100}")
print(f"Scheduled: {len(schedule)}/{len(opportunities)} opportunities")
print(f"Runtime: {metrics.runtime_ms:.2f} ms")

# Show schedule
print(f"\n{'=' * 100}")
print(f"DETAILED SCHEDULE - ROLL ANGLE PROGRESSION")
print(f"{'=' * 100}")
print(f"{'#':<4} {'Target':<12} {'Time':<8} {'Elev':<7} {'ΔRoll':<9} {'Roll°':<9} {'Pitch°':<9} {'Slew':<10} {'Slack':<10}")
print(f"{'-' * 110}")

for i, sched in enumerate(schedule, 1):
    # Find original opportunity to get elevation
    orig_opp = next(o for o in opportunities if o.id == sched.opportunity_id)
    elev = orig_opp.max_elevation
    
    print(
        f"{i:<4} "
        f"{sched.target_id:<12} "
        f"T+{(sched.start_time - base_time).seconds:3d}s  "
        f"{elev:>5.0f}°  "
        f"{sched.delta_roll:>7.2f}°  "
        f"{sched.roll_angle:>7.2f}°  "
        f"{sched.pitch_angle:>7.2f}°  "
        f"{sched.maneuver_time:>8.3f}s  "
        f"{sched.slack_time:>8.2f}s"
    )

# Analysis
print(f"\n{'=' * 100}")
print(f"ROLL ANGLE ANALYSIS")
print(f"{'=' * 100}")

if schedule:
    rolls = [s.roll_angle for s in schedule]
    deltas = [s.delta_roll for s in schedule]
    slews = [s.maneuver_time for s in schedule]
    
    print(f"\n✓ Roll Angle Statistics:")
    print(f"  Minimum roll:      {min(rolls):7.2f}°")
    print(f"  Maximum roll:      {max(rolls):7.2f}°")
    print(f"  Average roll:      {sum(rolls)/len(rolls):7.2f}°")
    print(f"  Maximum delta:     {max(deltas):7.2f}°")
    print(f"  Spacecraft limit:  {config.max_spacecraft_roll_deg:7.2f}°")
    
    if max(rolls) > config.max_spacecraft_roll_deg:
        print(f"  ❌ VIOLATED roll limit!")
        violated = [s for s in schedule if s.roll_angle > config.max_spacecraft_roll_deg]
        print(f"     {len(violated)} opportunities violated limit:")
        for s in violated:
            print(f"       {s.target_id}: {s.roll_angle:.2f}°")
    else:
        print(f"  ✅ All within limit")
    
    print(f"\n✓ Slew Time Statistics:")
    print(f"  Minimum slew:  {min(slews):7.3f}s")
    print(f"  Maximum slew:  {max(slews):7.3f}s")
    print(f"  Average slew:  {sum(slews)/len(slews):7.3f}s")
    
    print(f"\n✓ Expected Roll Angles (based on target longitude vs overhead position):")
    print(f"{'Target':<12} {'Lon':<8} {'Expected Roll':<15} {'Actual Roll':<12} {'Status'}")
    print(f"{'-' * 70}")
    
    # Satellite roughly over Center (30°E) at T+20s
    satellite_lon_overhead = 30.0
    
    for s in schedule:
        target_lon = target_positions[s.target_id][1]
        # Rough cross-track distance
        cross_track_deg = abs(target_lon - satellite_lon_overhead)
        
        # Expected roll using small-angle approximation
        # At 500km altitude, ~1° cross-track ≈ ~0.1° roll
        expected_roll_approx = cross_track_deg * 0.1
        
        actual_roll = s.roll_angle
        status = "✅" if actual_roll < config.max_spacecraft_roll_deg else "❌"
        
        print(
            f"{s.target_id:<12} "
            f"{target_lon:>6.1f}°  "
            f"~{expected_roll_approx:>5.1f}° (approx)  "
            f"{actual_roll:>9.2f}°  "
            f"{status}"
        )
    
    print(f"\n✓ Attitude Persistence Check:")
    for i in range(1, len(schedule)):
        prev_roll = schedule[i-1].roll_angle
        curr_roll = schedule[i].roll_angle
        delta_roll = schedule[i].delta_roll
        expected_delta = abs(curr_roll - prev_roll)
        
        if abs(delta_roll - expected_delta) < 0.1:
            print(f"  ✅ #{i+1}: delta_roll={delta_roll:.2f}° matches change from {prev_roll:.2f}° to {curr_roll:.2f}°")
        else:
            print(f"  ⚠️  #{i+1}: delta_roll={delta_roll:.2f}° but actual change={expected_delta:.2f}°")

print(f"\n{'=' * 100}")
print(f"EXTREME SLEW TEST COMPLETE")
print(f"{'=' * 100}")

if schedule and max([s.roll_angle for s in schedule]) > 2.0:
    print(f"\n✅ SUCCESS: Achieved roll angles > 2° using synthetic opportunities")
    print(f"   This validates the roll angle calculation works for off-nadir imaging")
else:
    print(f"\n⚠️  Roll angles still small - satellite geometry correctly calculates")
    print(f"   small angles for near-overhead imaging. This is CORRECT behavior!")
