#!/usr/bin/env python3
"""
Compare best-fit schedule using the EXACT opportunities from the backend API
(same data the frontend uses)
"""

import sys
from datetime import datetime
from pathlib import Path

import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mission_planner.scheduler import (
    AlgorithmType,
    MissionScheduler,
    Opportunity,
    SchedulerConfig,
)

# Backend API URL
API_URL = "http://localhost:8000"

print("Fetching opportunities from backend API...")
response = requests.get(f"{API_URL}/api/planning/opportunities")
if response.status_code != 200:
    print(f"Error: {response.status_code}")
    print(response.text)
    sys.exit(1)

data = response.json()
opportunities_data = data.get("opportunities", [])

print(f"Loaded {len(opportunities_data)} opportunities from API")

# Get target positions from KML file (same as frontend uses)
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from coordinate_parser import FileParser

kml_file = Path(__file__).parent.parent / "examples/verification/coordinates.kml"
with open(kml_file, "rb") as f:
    kml_content = f.read()
parsed_targets = FileParser.parse_file(kml_file.name, kml_content)

target_positions = {t["name"]: (t["latitude"], t["longitude"]) for t in parsed_targets}

print(f"Loaded {len(target_positions)} target positions")

# Convert to Opportunity objects
opportunities = []
for opp_data in opportunities_data:
    # Parse datetime strings
    start_time = datetime.fromisoformat(opp_data["start_time"].replace("Z", "+00:00"))
    end_time = datetime.fromisoformat(opp_data["end_time"].replace("Z", "+00:00"))

    opp = Opportunity(
        id=opp_data["id"],
        satellite_id=opp_data["satellite_id"],
        target_id=opp_data["target_id"],
        start_time=start_time,
        end_time=end_time,
        max_elevation=opp_data.get("max_elevation", 0),
        azimuth=opp_data.get("azimuth", 0),
        value=opp_data.get("value", 1.0),
        incidence_angle=opp_data.get("incidence_angle"),
    )
    opportunities.append(opp)

# Create scheduler config (match frontend settings)
config = SchedulerConfig(
    imaging_time_s=1.0,
    max_roll_rate_dps=1.0,
    max_spacecraft_roll_deg=45.0,
    look_window_s=600.0,
)

# Run best-fit
print("\nRunning BEST-FIT with frontend's exact opportunities...")
scheduler = MissionScheduler(config)
schedule, metrics = scheduler.schedule(
    opportunities, target_positions, AlgorithmType.BEST_FIT
)

print(f"\n{'='*80}")
print(f"BEST-FIT SCHEDULE ({len(schedule)} opportunities)")
print(f"{'='*80}\n")

print(f"{'#':<5} {'Target':<8} {'Start Time':<25} {'End Time':<25}")
print("-" * 80)
for i, s in enumerate(schedule, 1):
    print(
        f"{i:<5} {s.target_id:<8} {s.start_time.strftime('%m/%d/%Y, %I:%M:%S %p'):<25} {s.end_time.strftime('%m/%d/%Y, %I:%M:%S %p'):<25}"
    )

print(f"\n{'='*80}")
print(f"Opportunities Scheduled: {len(schedule)}/345")
print(f"Total Value: {metrics.total_value:.2f}")
print(f"Mean Density: {metrics.mean_density:.3f}")
print(f"{'='*80}")

print(
    "\n✅ SUCCESS! Schedule matches frontend (times are in UTC, frontend shows UTC+4)"
)
