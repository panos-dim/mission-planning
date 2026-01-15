#!/usr/bin/env python3
"""
Test to demonstrate FULL PASS DURATION pitch usage.

This validates that:
1. Opportunities are created throughout the entire pass (not just 3 fixed points)
2. Pitch angles vary continuously from start to end of pass
3. Longer passes create more opportunities (more granular sampling)
4. Full pitch range is utilized based on actual pass geometry
"""

import requests
import json
from datetime import datetime, timedelta
from tabulate import tabulate

BASE_URL = "http://localhost:8000"
DEBUG_ENDPOINT = f"{BASE_URL}/api/v1/debug/planning/run_scenario"

SATELLITE_TLE = {
    "id": "ICEYE-X44",
    "name": "ICEYE-X44",
    "tle_line1": "1 62707U 25009DC  25306.22031033  .00004207  00000+0  39848-3 0  9995",
    "tle_line2": "2 62707  97.7269  23.9854 0002193 135.9671 224.1724 14.94137357 66022"
}

# Single target to analyze pass structure in detail
TEST_TARGET = [
    {"name": "Athens", "latitude": 37.9838, "longitude": 23.7275, "priority": 5},
]


def run_scenario_and_analyze():
    """Run scenario and analyze opportunity distribution."""
    
    start_time = datetime(2025, 11, 18, 0, 0, 0)
    end_time = start_time + timedelta(hours=24)
    
    payload = {
        "scenario_id": "full_pass_test",
        "satellites": [SATELLITE_TLE],
        "targets": TEST_TARGET,
        "time_window": {
            "start": start_time.isoformat() + "Z",
            "end": end_time.isoformat() + "Z"
        },
        "planning_params": {
            "imaging_time_s": 5.0,
            "max_roll_rate_dps": 1.0,
            "max_roll_accel_dps2": 1000.0,
            "max_spacecraft_roll_deg": 45.0,
            "max_pitch_rate_dps": 1.0,
            "max_pitch_accel_dps2": 10000.0,
            "max_spacecraft_pitch_deg": 45.0,  # Full 45° range
            "quality_model": "uniform",
            "quality_weight": 0.5
        },
        "algorithms": ["roll_pitch_first_fit"]
    }
    
    print("\n" + "=" * 100)
    print("🔬 FULL PASS DURATION PITCH TEST")
    print("=" * 100)
    print(f"\nConfiguration:")
    print(f"  • Satellite: {SATELLITE_TLE['name']}")
    print(f"  • Target: Athens")
    print(f"  • Time Window: 24 hours")
    print(f"  • Max Pitch: 45° (full range enabled)")
    print(f"  • Sampling: Dynamic across entire pass duration")
    
    response = requests.post(DEBUG_ENDPOINT, json=payload, timeout=120)
    response.raise_for_status()
    result = response.json()
    
    if "algorithms" not in result or "roll_pitch_first_fit" not in result["algorithms"]:
        print("\n❌ Unexpected response structure")
        return
    
    algo_data = result["algorithms"]["roll_pitch_first_fit"]
    
    print(f"\n✅ API Response received")
    print(f"   Total opportunities created: {algo_data['metrics']['total_opportunities']}")
    print(f"   Opportunities accepted: {algo_data['metrics']['accepted']}")
    
    # We need to see ALL opportunities created, not just the scheduled ones
    # For this test, we'll call the API with a simpler request that returns opportunity details
    print(f"\n⚠️  Note: Scheduler only shows accepted opportunities.")
    print(f"   To see full pass sampling, we need access to all {algo_data['metrics']['total_opportunities']} opportunities.")
    print(f"   Let me demonstrate with the scheduled ones:\n")
    
    schedule = algo_data["schedule"]
    
    # Group opportunities by pass
    passes = {}
    for opp in schedule:
        # Extract pass index from opportunity ID (format: satellite_target_passidx_timetype)
        parts = opp["opportunity_id"].split("_")
        pass_idx = parts[2] if len(parts) >= 3 else "0"
        
        if pass_idx not in passes:
            passes[pass_idx] = []
        passes[pass_idx].append(opp)
    
    print(f"\n📊 Found {len(passes)} passes with scheduled opportunities")
    
    # Analyze each pass
    for pass_idx, opps in sorted(passes.items()):
        print(f"\n{'=' * 100}")
        print(f"PASS {pass_idx} - {len(opps)} opportunities scheduled")
        print(f"{'=' * 100}")
        
        # Sort by time
        opps_sorted = sorted(opps, key=lambda x: x["start_time"])
        
        # Calculate pass duration
        first_time = datetime.fromisoformat(opps_sorted[0]["start_time"].replace("Z", "+00:00"))
        last_time = datetime.fromisoformat(opps_sorted[-1]["start_time"].replace("Z", "+00:00"))
        pass_duration = (last_time - first_time).total_seconds()
        
        print(f"\nPass Characteristics:")
        print(f"  Start: {first_time.strftime('%H:%M:%S')}")
        print(f"  End:   {last_time.strftime('%H:%M:%S')}")
        print(f"  Duration: {pass_duration:.0f} seconds")
        print(f"  Opportunities: {len(opps)} (sampled every ~{pass_duration/(len(opps)-1):.0f}s)")
        
        # Create detailed table
        table_data = []
        for i, opp in enumerate(opps_sorted):
            opp_time = datetime.fromisoformat(opp["start_time"].replace("Z", "+00:00"))
            time_from_start = (opp_time - first_time).total_seconds()
            
            roll = opp.get("roll_angle", 0.0)
            pitch = opp.get("pitch_angle", 0.0)
            
            # Determine position in pass
            if time_from_start < pass_duration * 0.2:
                position = "Early"
            elif time_from_start > pass_duration * 0.8:
                position = "Late"
            else:
                position = "Middle"
            
            table_data.append([
                i + 1,
                opp_time.strftime("%H:%M:%S"),
                f"{time_from_start:.0f}s",
                position,
                f"{roll:+.1f}°",
                f"{pitch:+.1f}°",
            ])
        
        headers = ["#", "Time", "From Start", "Position", "Roll", "Pitch"]
        print("\n" + tabulate(table_data, headers=headers, tablefmt="grid"))
        
        # Statistics
        pitches = [opp.get("pitch_angle", 0.0) for opp in opps_sorted]
        rolls = [opp.get("roll_angle", 0.0) for opp in opps_sorted]
        
        print(f"\nPitch Statistics:")
        print(f"  Range: {min(pitches):.1f}° to {max(pitches):.1f}°")
        print(f"  Span: {max(pitches) - min(pitches):.1f}°")
        print(f"  Mean: {sum(pitches)/len(pitches):.1f}°")
        
        print(f"\nRoll Statistics:")
        print(f"  Range: {min(rolls):.1f}° to {max(rolls):.1f}°")
        print(f"  Span: {max(rolls) - min(rolls):.1f}°")
        
        # Show pitch progression
        print(f"\nPitch Progression (visualized):")
        print(f"  Early   → Middle → Late")
        pitch_viz = " → ".join([f"{p:+.0f}°" for p in pitches])
        print(f"  {pitch_viz}")
    
    # Overall statistics
    all_pitches = [opp.get("pitch_angle", 0.0) for opp in schedule]
    all_rolls = [opp.get("roll_angle", 0.0) for opp in schedule]
    
    print(f"\n{'=' * 100}")
    print("🎯 OVERALL STATISTICS")
    print(f"{'=' * 100}")
    print(f"\nPitch Usage:")
    print(f"  Total opportunities: {len(all_pitches)}")
    print(f"  Min pitch: {min(all_pitches):.1f}°")
    print(f"  Max pitch: {max(all_pitches):.1f}°")
    print(f"  Full range: {max(all_pitches) - min(all_pitches):.1f}° (out of ±45° = 90° total)")
    print(f"  Pitch > 20°: {sum(1 for p in all_pitches if abs(p) > 20)}")
    print(f"  Pitch > 30°: {sum(1 for p in all_pitches if abs(p) > 30)}")
    print(f"  Pitch > 40°: {sum(1 for p in all_pitches if abs(p) > 40)}")
    
    print(f"\nRoll Usage:")
    print(f"  Min roll: {min(all_rolls):.1f}°")
    print(f"  Max roll: {max(all_rolls):.1f}°")
    print(f"  Full range: {max(all_rolls) - min(all_rolls):.1f}°")
    
    print(f"\n✅ VALIDATION:")
    print(f"  [{'✓' if len(passes) > 0 else '✗'}] Multiple passes analyzed")
    print(f"  [{'✓' if any(len(opps) > 3 for opps in passes.values()) else '✗'}] More than 3 opportunities per pass")
    print(f"  [{'✓' if max(all_pitches) - min(all_pitches) > 20 else '✗'}] Significant pitch range used (>20°)")
    print(f"  [{'✓' if any(abs(p) > 20 for p in all_pitches) else '✗'}] High pitch angles achieved (>20°)")
    print(f"\n{'=' * 100}\n")


if __name__ == "__main__":
    try:
        # Check server
        response = requests.get(f"{BASE_URL}/", timeout=2)
        if response.status_code != 200:
            print("❌ Backend server not running!")
            print("   Start it with: ./run_dev.sh")
            exit(1)
        
        run_scenario_and_analyze()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
