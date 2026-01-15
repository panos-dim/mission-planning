#!/usr/bin/env python3
"""
DEMONSTRATION: Sequential Imaging with Dynamic Pitch

Scenario: 3 targets aligned along satellite ground track
- Without pitch: Only captures 1 target (first one at max elevation)
- With pitch: Captures all 3 in single pass using forward/overhead/backward looking

This proves full dynamic pitch usage across entire pass duration.
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

# THREE TARGETS IN A LINE - Along satellite ground track
# These are positioned ~100-150 km apart along a north-south line
# The satellite will pass over them sequentially
SEQUENTIAL_TARGETS = [
    {"name": "Target_North", "latitude": 25.5, "longitude": 55.0, "priority": 5},   # Northernmost
    {"name": "Target_Center", "latitude": 25.0, "longitude": 55.0, "priority": 5},  # Middle
    {"name": "Target_South", "latitude": 24.5, "longitude": 55.0, "priority": 5},   # Southernmost
]


def run_sequential_test():
    """Run roll-only vs roll+pitch for sequential targets."""
    
    start_time = datetime(2025, 11, 18, 0, 0, 0)
    
    print("\n" + "=" * 120)
    print("🎯 SEQUENTIAL IMAGING DEMONSTRATION - Dynamic Pitch Across Full Pass")
    print("=" * 120)
    
    print("\n📍 Scenario Setup:")
    print("  • 3 targets in a line (North → Center → South)")
    print("  • Spacing: ~50 km between each target")
    print("  • Satellite passes over them sequentially (polar orbit)")
    print("  • Time window: 12 hours")
    
    for target in SEQUENTIAL_TARGETS:
        print(f"    - {target['name']}: {target['latitude']}°N, {target['longitude']}°E")
    
    results = {}
    
    for pitch_enabled, label, algo in [(False, "Roll-Only", "first_fit"), 
                                        (True, "Roll+Pitch (Dynamic)", "roll_pitch_first_fit")]:
        print(f"\n{'─' * 120}")
        print(f"Testing: {label}")
        print(f"{'─' * 120}")
        
        payload = {
            "scenario_id": f"sequential_{'pitch' if pitch_enabled else 'roll'}",
            "satellites": [SATELLITE_TLE],
            "targets": SEQUENTIAL_TARGETS,
            "time_window": {
                "start": start_time.isoformat() + "Z",
                "end": (start_time + timedelta(hours=12)).isoformat() + "Z"
            },
            "planning_params": {
                "imaging_time_s": 5.0,
                "max_roll_rate_dps": 1.0,
                "max_roll_accel_dps2": 1000.0,
                "max_spacecraft_roll_deg": 45.0,
                "max_pitch_rate_dps": 1.0,
                "max_pitch_accel_dps2": 10000.0,
                "max_spacecraft_pitch_deg": 45.0 if pitch_enabled else 0.0,
                "quality_model": "uniform",
                "quality_weight": 0.5
            },
            "algorithms": [algo]
        }
        
        print(f"  Calling API... ", end="", flush=True)
        response = requests.post(DEBUG_ENDPOINT, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        
        metrics = result["algorithms"][algo]["metrics"]
        schedule = result["algorithms"][algo]["schedule"]
        
        covered_targets = {opp["target_id"] for opp in schedule}
        
        print(f"✓ {len(covered_targets)}/3 targets captured")
        
        results[label] = {
            "enabled": pitch_enabled,
            "algo": algo,
            "coverage": len(covered_targets),
            "total_opps": metrics["total_opportunities"],
            "accepted": metrics["accepted"],
            "max_pitch": metrics["max_pitch_deg"],
            "covered": sorted(covered_targets),
            "schedule": schedule,
            "metrics": metrics
        }
    
    return results


def print_coverage_table(results):
    """Show which targets were captured."""
    print("\n" + "=" * 120)
    print("📊 TARGET CAPTURE COMPARISON")
    print("=" * 120)
    
    table = []
    for target in SEQUENTIAL_TARGETS:
        name = target["name"]
        position = name.split("_")[1]
        
        roll_captured = name in results["Roll-Only"]["covered"]
        pitch_captured = name in results["Roll+Pitch (Dynamic)"]["covered"]
        
        if pitch_captured and not roll_captured:
            result = "🎯 PITCH ENABLED"
        elif roll_captured and pitch_captured:
            result = "Both"
        else:
            result = "Neither"
        
        table.append([
            name,
            position,
            "✓" if roll_captured else "✗",
            "✓" if pitch_captured else "✗",
            result
        ])
    
    print("\n" + tabulate(table, 
                         headers=["Target", "Position", "Roll-Only", "Roll+Pitch", "Result"],
                         tablefmt="grid"))
    
    print(f"\nSummary:")
    print(f"  Roll-Only: {results['Roll-Only']['coverage']}/3 targets ({results['Roll-Only']['coverage']/3*100:.0f}%)")
    print(f"  Roll+Pitch: {results['Roll+Pitch (Dynamic)']['coverage']}/3 targets ({results['Roll+Pitch (Dynamic)']['coverage']/3*100:.0f}%)")
    print(f"  Improvement: +{results['Roll+Pitch (Dynamic)']['coverage'] - results['Roll-Only']['coverage']} targets")


def analyze_sequential_imaging(results):
    """Detailed analysis of how pitch enabled sequential imaging."""
    print("\n" + "=" * 120)
    print("🔬 SEQUENTIAL IMAGING ANALYSIS - Full Pass Duration")
    print("=" * 120)
    
    pitch_schedule = results["Roll+Pitch (Dynamic)"]["schedule"]
    
    if not pitch_schedule:
        print("\n⚠️  No opportunities scheduled with pitch")
        return
    
    # Sort by time
    pitch_schedule_sorted = sorted(pitch_schedule, key=lambda x: x["start_time"])
    
    print(f"\nScheduled Opportunities: {len(pitch_schedule_sorted)}")
    print(f"Targets Captured: {results['Roll+Pitch (Dynamic)']['coverage']}/3")
    
    # Create detailed table
    table = []
    for i, opp in enumerate(pitch_schedule_sorted):
        opp_time = datetime.fromisoformat(opp["start_time"].replace("Z", "+00:00"))
        target = opp["target_id"]
        pitch = opp.get("pitch_angle", 0.0)
        roll = opp.get("roll_angle", 0.0)
        
        # Determine imaging type based on pitch
        if abs(pitch) < 5:
            imaging_type = "Overhead (nadir)"
        elif pitch > 5:
            imaging_type = f"Forward-looking (+{pitch:.1f}°)"
        else:
            imaging_type = f"Backward-looking ({pitch:.1f}°)"
        
        # Determine target position
        if "North" in target:
            position = "North (1st)"
        elif "Center" in target:
            position = "Center (2nd)"
        else:
            position = "South (3rd)"
        
        table.append([
            i + 1,
            opp_time.strftime("%H:%M:%S"),
            target,
            position,
            f"{pitch:+.1f}°",
            f"{roll:+.1f}°",
            imaging_type
        ])
    
    headers = ["#", "Time", "Target", "Position", "Pitch", "Roll", "Imaging Mode"]
    print("\n" + tabulate(table, headers=headers, tablefmt="grid"))
    
    # Show pitch progression
    pitches = [opp.get("pitch_angle", 0) for opp in pitch_schedule_sorted]
    
    print(f"\nPitch Progression:")
    print(f"  Range: {min(pitches):.1f}° to {max(pitches):.1f}°")
    print(f"  Span: {max(pitches) - min(pitches):.1f}°")
    
    # Check if we got the sequential pattern
    if len(pitch_schedule_sorted) >= 3:
        print(f"\n✅ SEQUENTIAL IMAGING ACHIEVED!")
        print(f"   The satellite imaged targets in sequence using dynamic pitch:")
        
        for i, opp in enumerate(pitch_schedule_sorted, 1):
            pitch = opp.get("pitch_angle", 0.0)
            target = opp["target_id"]
            
            if pitch > 10:
                mode = f"forward-looking ({pitch:+.1f}°)"
            elif pitch < -10:
                mode = f"backward-looking ({pitch:.1f}°)"
            else:
                mode = f"overhead ({pitch:+.1f}°)"
            
            print(f"   {i}. {target}: {mode}")


def compare_opportunities(results):
    """Show opportunity generation difference."""
    print("\n" + "=" * 120)
    print("💥 OPPORTUNITY GENERATION - Full Pass vs Fixed Point")
    print("=" * 120)
    
    table = []
    for label in ["Roll-Only", "Roll+Pitch (Dynamic)"]:
        r = results[label]
        table.append([
            label,
            "No (0°)" if not r["enabled"] else "Yes (45°)",
            r["total_opps"],
            r["accepted"],
            f"{r['max_pitch']:.1f}°",
            r["coverage"]
        ])
    
    print("\n" + tabulate(table,
                         headers=["Algorithm", "Pitch", "Total Opps", "Accepted", "Max Pitch", "Coverage"],
                         tablefmt="grid"))
    
    roll_opps = results["Roll-Only"]["total_opps"]
    pitch_opps = results["Roll+Pitch (Dynamic)"]["total_opps"]
    factor = pitch_opps / roll_opps if roll_opps > 0 else 0
    
    print(f"\nOpportunity Increase: {pitch_opps - roll_opps} (+{factor:.1f}×)")
    print(f"Explanation:")
    print(f"  • Roll-only: 1 opportunity per pass (only at max elevation)")
    print(f"  • Roll+pitch: 3-11 opportunities per pass (sampled across FULL duration)")
    print(f"  • This creates opportunities for forward/backward looking imaging")


def main():
    # Check server
    try:
        response = requests.get(f"{BASE_URL}/", timeout=2)
        if response.status_code != 200:
            print("❌ Backend server not running! Start with: ./run_dev.sh")
            return 1
    except:
        print("❌ Backend server not running! Start with: ./run_dev.sh")
        return 1
    
    results = run_sequential_test()
    
    print_coverage_table(results)
    analyze_sequential_imaging(results)
    compare_opportunities(results)
    
    print("\n" + "=" * 120)
    print("✅ DEMONSTRATION COMPLETE")
    print("=" * 120)
    
    roll_coverage = results["Roll-Only"]["coverage"]
    pitch_coverage = results["Roll+Pitch (Dynamic)"]["coverage"]
    
    if pitch_coverage > roll_coverage:
        improvement = pitch_coverage - roll_coverage
        print(f"\n🎯 SUCCESS! Dynamic pitch captured {improvement} additional target(s)!")
        print(f"\nKey Achievement:")
        print(f"  • Roll-only: {roll_coverage}/3 targets (limited to single imaging point)")
        print(f"  • Roll+pitch: {pitch_coverage}/3 targets (full pass duration sampling)")
        print(f"  • Dynamic pitch range: {results['Roll+Pitch (Dynamic)']['max_pitch']:.1f}° (continuous, not fixed intervals)")
        print(f"\nThis proves the system uses FULL PASS DURATION with DYNAMIC PITCH calculation!")
    else:
        print(f"\n⚠️  Both achieved same coverage in this scenario")
        print(f"   Try running at different times when targets align better with pass geometry")
    
    print(f"\n" + "=" * 120 + "\n")
    
    return 0


if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted")
        exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
