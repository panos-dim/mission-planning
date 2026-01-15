#!/usr/bin/env python3
"""
Quick script to compare best-fit schedule from verification script
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from coordinate_parser import FileParser

from mission_planner.orbit import SatelliteOrbit
from mission_planner.planner import MissionPlanner
from mission_planner.scheduler import AlgorithmType, MissionScheduler, SchedulerConfig
from mission_planner.targets import GroundTarget

# Configuration (matching your frontend)
kml_file = Path(__file__).parent.parent / "examples/verification/coordinates.kml"
tle_file = Path(__file__).parent.parent / "data/active_satellites.tle"
satellite_name = "ICEYE-X44"
pointing_angle = 45.0

# Parse your frontend start time (EXACT match from frontend console log)
frontend_start = "2025-10-21T12:38:00Z"  # 12:38 PM UTC
start_time = datetime.fromisoformat(frontend_start.replace("Z", "+00:00"))
end_time = start_time + timedelta(days=3)

print("Loading targets and satellite...")
with open(kml_file, "rb") as f:
    kml_content = f.read()
parsed_targets = FileParser.parse_file(kml_file.name, kml_content)

# Create GroundTarget objects with priorities
targets = []
for i, pt in enumerate(parsed_targets):
    # Assign priorities cyclically 1-5 for variety
    priority = 1 + (i % 5)
    target = GroundTarget(
        name=pt["name"],
        latitude=pt["latitude"],
        longitude=pt["longitude"],
        mission_type="imaging",
        elevation_mask=10.0,
        pointing_angle=pointing_angle,
    )
    target.priority = priority  # Set as attribute after creation
    targets.append(target)

print(f"Loaded {len(targets)} targets:")
print(f"Target names: {', '.join(sorted([t.name for t in targets]))}")

satellite = SatelliteOrbit.from_tle_file(str(tle_file), satellite_name=satellite_name)

print(f"Running mission analysis from {start_time} to {end_time}...")
planner = MissionPlanner(satellite, targets)
passes_dict = planner.compute_passes(
    start_time, end_time, use_parallel=True, use_adaptive=True
)

# Get opportunities
all_passes = []
for target_name, target_passes in passes_dict.items():
    all_passes.extend(target_passes)

# Get target positions
target_positions = {t.name: (t.latitude, t.longitude) for t in targets}

# Create opportunities manually like verification script does
from mission_planner.quality_scoring import (
    QualityModel,
    compute_opportunity_value,
    compute_quality_score,
)
from mission_planner.scheduler import Opportunity

opportunities = []
for idx, pass_detail in enumerate(all_passes):
    target = next((t for t in targets if t.name == pass_detail.target_name), None)
    base_priority = target.priority if target else 1

    # Extract incidence angle from pass_detail
    incidence_angle_deg = getattr(pass_detail, "incidence_angle_deg", None)

    # Compute quality score
    quality_score = compute_quality_score(
        incidence_angle_deg=incidence_angle_deg,
        mode="IMAGING",
        quality_model=QualityModel.MONOTONIC,
        ideal_incidence_deg=35.0,
        band_width_deg=7.5,
    )

    # Blend priority and quality
    value = compute_opportunity_value(
        base_priority=base_priority, quality_score=quality_score, quality_weight=0.6
    )

    opp = Opportunity(
        id=f"opp_{idx}",
        satellite_id=satellite_name,
        target_id=pass_detail.target_name,
        start_time=pass_detail.start_time,
        end_time=pass_detail.end_time,
        max_elevation=pass_detail.max_elevation,
        priority=base_priority,
        value=value,
        incidence_angle=incidence_angle_deg,
    )
    opportunities.append(opp)

print(f"Found {len(opportunities)} opportunities")

# Debug: Export all opportunities to file for comparison
sorted_opps = sorted(opportunities, key=lambda x: x.start_time)
with open("backend_opportunities.txt", "w") as f:
    for i, opp in enumerate(sorted_opps):
        f.write(
            f"Opportunity {i+1}:{opp.start_time.strftime('%m-%d at %H:%M')} UTC→ {opp.end_time.strftime('%H:%M')} UTC ({opp.target_id})\n"
        )
print(f"Exported {len(sorted_opps)} opportunities to backend_opportunities.txt")

# Show first 10
print("\n=== FIRST 10 OPPORTUNITIES ===")
for i, opp in enumerate(sorted_opps[:10]):
    print(f"{i+1}. {opp.target_id} at {opp.start_time.strftime('%m-%d %H:%M:%S')} UTC")

# Create configuration for scheduler
config = SchedulerConfig(
    imaging_time_s=1.0, max_spacecraft_roll_deg=pointing_angle, max_roll_rate_dps=1.0
)

# Run best-fit
scheduler = MissionScheduler(config)
schedule, metrics = scheduler.schedule(
    opportunities, target_positions, AlgorithmType.BEST_FIT
)

print(f"\n{'='*80}")
print(f"BEST-FIT SCHEDULE ({len(schedule)} opportunities)")
print(f"{'='*80}\n")

print(
    f"{'#':<4} {'Target':<8} {'Start Time':<25} {'End Time':<25} {'Δroll':<8} {'Slew':<8}"
)
print(f"{'-'*80}")

for i, sched in enumerate(schedule, 1):
    start_str = sched.start_time.strftime("%m/%d/%Y, %I:%M:%S %p")
    end_str = sched.end_time.strftime("%m/%d/%Y, %I:%M:%S %p")
    print(
        f"{i:<4} {sched.target_id:<8} {start_str:<25} {end_str:<25} {abs(sched.delta_roll):<8.2f} {sched.maneuver_time:<8.3f}"
    )

print(f"\n{'='*80}")
print(f"SUMMARY")
print(f"{'='*80}")
print(f"Total Opportunities: {len(schedule)}")
print(f"Total Value: {metrics.total_value:.2f}")
print(f"Mean Incidence: {metrics.mean_incidence_deg:.2f}°")
print(f"Total Maneuver Time: {metrics.total_maneuver_time:.1f}s")
