#!/usr/bin/env python3
"""Test multi-criteria weight system for best_fit algorithms."""

import requests

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

def test_weight_presets(mission_data):
    """Test all weight presets."""
    print("\n" + "=" * 70)
    print("TESTING WEIGHT PRESETS")
    print("=" * 70)
    
    presets = ['balanced', 'priority_first', 'quality_first', 'urgent', 'archival']
    
    for preset in presets:
        request = {
            "mission_data": mission_data,
            "algorithms": ["best_fit"],
            "value_source": "target_priority",
            "weight_preset": preset
        }
        resp = requests.post(f"{BASE_URL}/api/planning/schedule", json=request)
        if resp.status_code != 200:
            print(f"Error with preset {preset}: {resp.text}")
            continue
        
        result = resp.json().get("results", {}).get("best_fit", {})
        metrics = result.get("metrics", {})
        schedule = result.get("schedule", [])
        
        print(f"\n{preset.upper()}:")
        print(f"  Total Value: {metrics.get('total_value', 0):.2f}")
        print(f"  Avg Incidence: {metrics.get('mean_incidence_deg', 0):.1f}°")
        print(f"  Schedule: ", end="")
        for opp in schedule[:3]:
            print(f"{opp['target_id']}({opp['value']:.2f}), ", end="")
        print()

def test_custom_weights(mission_data):
    """Test custom weight combinations."""
    print("\n" + "=" * 70)
    print("TESTING CUSTOM WEIGHTS")
    print("=" * 70)
    
    test_cases = [
        {"priority": 100, "geometry": 0, "timing": 0, "name": "PRIORITY ONLY"},
        {"priority": 0, "geometry": 100, "timing": 0, "name": "GEOMETRY ONLY"},
        {"priority": 0, "geometry": 0, "timing": 100, "name": "TIMING ONLY"},
        {"priority": 50, "geometry": 50, "timing": 0, "name": "50/50 PRIORITY-GEOMETRY"},
    ]
    
    for case in test_cases:
        request = {
            "mission_data": mission_data,
            "algorithms": ["best_fit"],
            "value_source": "target_priority",
            "use_multi_criteria": True,
            "weight_priority": case["priority"],
            "weight_geometry": case["geometry"],
            "weight_timing": case["timing"]
        }
        resp = requests.post(f"{BASE_URL}/api/planning/schedule", json=request)
        if resp.status_code != 200:
            print(f"Error: {resp.text}")
            continue
        
        result = resp.json().get("results", {}).get("best_fit", {})
        metrics = result.get("metrics", {})
        schedule = result.get("schedule", [])
        
        print(f"\n{case['name']} (P:{case['priority']}, G:{case['geometry']}, T:{case['timing']}):")
        print(f"  Total Value: {metrics.get('total_value', 0):.2f}")
        print(f"  Avg Incidence: {metrics.get('mean_incidence_deg', 0):.1f}°")
        print(f"  First scheduled: {schedule[0]['target_id'] if schedule else 'None'} (value={schedule[0]['value']:.3f})" if schedule else "")

def test_preset_endpoint():
    """Test the weight presets endpoint."""
    print("\n" + "=" * 70)
    print("TESTING PRESETS ENDPOINT")
    print("=" * 70)
    
    resp = requests.get(f"{BASE_URL}/api/planning/weight-presets")
    if resp.status_code != 200:
        print(f"Error: {resp.text}")
        return
    
    presets = resp.json().get("presets", {})
    print(f"Found {len(presets)} presets:")
    for name, data in presets.items():
        normalized = data.get("normalized", {})
        desc = data.get("description", "")
        print(f"  {name}: P={normalized.get('priority', 0)*100:.0f}%, G={normalized.get('geometry', 0)*100:.0f}%, T={normalized.get('timing', 0)*100:.0f}%")
        print(f"         {desc}")

def main():
    print("=" * 70)
    print("MULTI-CRITERIA WEIGHT SYSTEM TEST")
    print("=" * 70)
    
    # Test presets endpoint first
    test_preset_endpoint()
    
    # Run mission analysis
    mission_data = run_mission_analysis()
    if not mission_data:
        print("Failed to run mission analysis")
        return
    
    # Test weight presets
    test_weight_presets(mission_data)
    
    # Test custom weights
    test_custom_weights(mission_data)
    
    print("\n" + "=" * 70)
    print("✅ ALL TESTS COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
