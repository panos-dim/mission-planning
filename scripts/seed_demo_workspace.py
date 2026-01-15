#!/usr/bin/env python3
"""
Seed script to create a demo workspace for testing.

Run with: python scripts/seed_demo_workspace.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.workspace_persistence import get_workspace_db


def seed_demo_workspace() -> str:
    """Create a demo workspace with sample mission data."""
    db = get_workspace_db()

    # Sample scenario configuration
    scenario_config = {
        "satellites": [
            {
                "id": "sat_ICEYE-X44",
                "name": "ICEYE-X44",
                "norad_id": 62707,
                "tle": {
                    "line1": "1 62707U 25009DC  25306.22031033  .00004207  00000+0  39848-3 0  9995",
                    "line2": "2 62707  97.7269  23.9854 0002193 135.9671 224.1724 14.94137357 66022",
                },
                "color": "#FFD700",
            }
        ],
        "targets": [
            {
                "name": "Athens",
                "latitude": 37.9838,
                "longitude": 23.7275,
                "priority": 5,
            },
            {
                "name": "Istanbul",
                "latitude": 41.0082,
                "longitude": 28.9784,
                "priority": 3,
            },
            {
                "name": "Dubai",
                "latitude": 25.2048,
                "longitude": 55.2708,
                "priority": 4,
            },
        ],
        "constraints": {
            "elevation_mask_deg": 10.0,
            "max_spacecraft_roll_deg": 45.0,
            "min_sun_elevation_deg": -6.0,
        },
        "time_window": {
            "start": "2026-01-06T00:00:00Z",
            "end": "2026-01-07T00:00:00Z",
        },
    }

    # Sample analysis state (simulated results)
    analysis_state = {
        "run_timestamp": "2026-01-06T10:30:00Z",
        "computation_time_seconds": 2.5,
        "passes": [
            {
                "target_name": "Athens",
                "satellite_name": "ICEYE-X44",
                "start_time": "2026-01-06T08:15:00Z",
                "end_time": "2026-01-06T08:22:00Z",
                "max_elevation": 45.2,
                "duration_seconds": 420,
            },
            {
                "target_name": "Istanbul",
                "satellite_name": "ICEYE-X44",
                "start_time": "2026-01-06T08:18:00Z",
                "end_time": "2026-01-06T08:25:00Z",
                "max_elevation": 38.7,
                "duration_seconds": 420,
            },
            {
                "target_name": "Dubai",
                "satellite_name": "ICEYE-X44",
                "start_time": "2026-01-06T10:45:00Z",
                "end_time": "2026-01-06T10:52:00Z",
                "max_elevation": 62.1,
                "duration_seconds": 420,
            },
        ],
        "statistics": {
            "total_passes": 3,
            "total_targets": 3,
            "coverage_percentage": 100.0,
        },
    }

    # Create workspace
    workspace_id = db.create_workspace(
        name="Demo Mission - Mediterranean",
        mission_mode="OPTICAL",
        scenario_config=scenario_config,
        analysis_state=analysis_state,
        time_window_start="2026-01-06T00:00:00Z",
        time_window_end="2026-01-07T00:00:00Z",
        app_version="1.0.0",
    )

    return workspace_id


def main() -> None:
    """Main entry point."""
    print("Seeding demo workspace...")

    db = get_workspace_db()

    # Check if demo already exists
    existing = db.list_workspaces()
    for ws in existing:
        if ws.name == "Demo Mission - Mediterranean":
            print(f"Demo workspace already exists: {ws.id}")
            print(f"  Created: {ws.created_at}")
            print(f"  Mission Mode: {ws.mission_mode}")
            print(f"  Satellites: {ws.satellites_count}")
            print(f"  Targets: {ws.targets_count}")
            return

    workspace_id = seed_demo_workspace()

    print(f"✅ Demo workspace created: {workspace_id}")
    print()

    # Verify
    workspace = db.get_workspace(workspace_id)
    if workspace:
        print("Workspace Details:")
        print(f"  Name: {workspace.name}")
        print(f"  Mission Mode: {workspace.mission_mode}")
        print(f"  Satellites: {workspace.satellites_count}")
        print(f"  Targets: {workspace.targets_count}")
        print(f"  Status: {workspace.last_run_status}")
        print()
        print("You can now load this workspace from the UI!")


if __name__ == "__main__":
    main()
