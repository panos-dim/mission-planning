#!/usr/bin/env python3
"""Test value-based sorting in best_fit algorithms with different quality weights."""

import requests
import json

BASE_URL = "http://localhost:8000"

# Mission analysis request
MISSION_REQUEST = {
    "tle": {
        "name": "ICEYE-X44",
        "line1": "1 58260U 23174AK  25140.91667824  .00000000  00000-0  00000-0 0  9992",
        "line2": "2 58260  97.5700 210.0000 0001500  90.0000 270.0000 15.23000000  1000"
    },
    "targets": [
        {"name": "Athens", "latitude": 37.98, "longitude": 23.73, "priority": 5},
        {"name": "Rome", "latitude": 41.90, "longitude": 12.50, "priority": 3},
        {"name": "Madrid", "latitude": 40.42, "longitude": -3.70, "priority": 1}
    ],
    "start_time": "2025-11-27T08:00:00Z",
    "duration_hours": 24,
    "mission_type": "imaging",
    "pointing_angle": 45.0
}

def run_mission_analysis():
    """Run mission analysis and return mission_data."""
    print("Running mission analysis...")
    resp = requests.post(f"{BASE_URL}/api/mission/analyze", json=MISSION_REQUEST)
    if resp.status_code != 200:
        print(f"Error: {resp.text}")
        return None
    data = resp.json()
    mission_data = data.get("data", {}).get("mission_data", {})
    passes = mission_data.get("passes", [])
    print(f"✅ Found {len(passes)} passes")
    return mission_data

def run_planning(mission_data, quality_weight, algorithms):
    """Run planning with specified quality weight."""
    request = {
        "mission_data": mission_data,
        "algorithms": algorithms,
        "quality_weight": quality_weight,
        "quality_model": "monotonic",
        "value_source": "target_priority"
    }
    resp = requests.post(f"{BASE_URL}/api/planning/schedule", json=request)
    if resp.status_code != 200:
        print(f"Error: {resp.text}")
        return None
    return resp.json().get("results", {})

def main():
    print("=" * 70)
    print("VALUE-BASED SORTING VERIFICATION TEST")
    print("=" * 70)
    
    # Run mission analysis
    mission_data = run_mission_analysis()
    if not mission_data:
        print("Failed to run mission analysis")
        return
    
    algorithms = ["best_fit", "roll_pitch_best_fit"]
    
    # Test with different quality weights
    for weight in [0.0, 0.5, 1.0]:
        print(f"\n{'='*70}")
        print(f"QUALITY WEIGHT = {weight}")
        if weight == 0.0:
            print("(PRIORITY ONLY - high priority targets should have highest value)")
        elif weight == 1.0:
            print("(GEOMETRY ONLY - best incidence angle should have highest value)")
        else:
            print("(BALANCED - blend of priority and geometry)")
        print("=" * 70)
        
        results = run_planning(mission_data, weight, algorithms)
        if not results:
            continue
        
        for algo in algorithms:
            algo_result = results.get(algo, {})
            schedule = algo_result.get("schedule", [])
            metrics = algo_result.get("metrics", {})
            
            print(f"\n{algo}:")
            print(f"  Total Value: {metrics.get('total_value', 0):.2f}")
            print(f"  Avg Incidence: {metrics.get('mean_incidence_deg', 0):.1f}°")
            print(f"  Schedule:")
            for opp in schedule:
                print(f"    - {opp['target_id']}: value={opp['value']:.3f}, inc={abs(opp.get('incidence_angle', 0)):.1f}°")
    
    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE")
    print("=" * 70)
    print("\nExpected behavior:")
    print("  - weight=0.0: Athens (priority=5) should have value=5.0, scheduled first")
    print("  - weight=1.0: Best geometry target scheduled first, all values ~1.0 or lower")
    print("  - weight=0.5: Blended values, balance of priority and geometry")

if __name__ == "__main__":
    main()
