#!/usr/bin/env python3
"""
Tight scenario test: Create challenging conditions where pitch is more likely to help.

Strategy:
1. More targets (15 instead of 10)
2. Tighter geographic clustering (Middle East region)
3. Shorter time windows (6h, 12h, 18h)
4. Mix of high and low priority targets
5. Tighter agility constraints to stress the scheduler
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
import time
from tabulate import tabulate

BASE_URL = "http://localhost:8000"
DEBUG_ENDPOINT = f"{BASE_URL}/api/v1/debug/planning/run_scenario"

# Test satellite (ICEYE-X44)
SATELLITE_TLE = {
    "id": "ICEYE-X44",
    "name": "ICEYE-X44",
    "tle_line1": "1 62707U 25009DC  25306.22031033  .00004207  00000+0  39848-3 0  9995",
    "tle_line2": "2 62707  97.7269  23.9854 0002193 135.9671 224.1724 14.94137357 66022"
}

# TIGHT SCENARIO: 15 targets in Middle East/Gulf region
# These are geographically close, creating tight timing windows between passes
TIGHT_TARGETS = [
    {"name": "Dubai", "latitude": 25.2048, "longitude": 55.2708, "priority": 5},
    {"name": "Abu_Dhabi", "latitude": 24.4539, "longitude": 54.3773, "priority": 5},
    {"name": "Doha", "latitude": 25.2854, "longitude": 51.5310, "priority": 4},
    {"name": "Riyadh", "latitude": 24.7136, "longitude": 46.6753, "priority": 5},
    {"name": "Kuwait_City", "latitude": 29.3759, "longitude": 47.9774, "priority": 4},
    {"name": "Manama", "latitude": 26.2285, "longitude": 50.5860, "priority": 3},
    {"name": "Muscat", "latitude": 23.5880, "longitude": 58.3829, "priority": 4},
    {"name": "Tehran", "latitude": 35.6892, "longitude": 51.3890, "priority": 5},
    {"name": "Baghdad", "latitude": 33.3152, "longitude": 44.3661, "priority": 5},
    {"name": "Damascus", "latitude": 33.5138, "longitude": 36.2765, "priority": 4},
    {"name": "Amman", "latitude": 31.9454, "longitude": 35.9284, "priority": 3},
    {"name": "Beirut", "latitude": 33.8938, "longitude": 35.5018, "priority": 4},
    {"name": "Jerusalem", "latitude": 31.7683, "longitude": 35.2137, "priority": 5},
    {"name": "Cairo", "latitude": 30.0444, "longitude": 31.2357, "priority": 5},
    {"name": "Ankara", "latitude": 39.9334, "longitude": 32.8597, "priority": 4},
]


def check_server_health():
    """Check if backend server is running."""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=2)
        return response.status_code == 200
    except:
        return False


def run_scenario(start_time: datetime, duration_hours: int, algorithms: List[str], 
                 tighter_constraints: bool = False) -> Dict[str, Any]:
    """
    Run a planning scenario via the debug API.
    
    Args:
        start_time: Mission start time
        duration_hours: Mission duration in hours
        algorithms: List of algorithm names to test
        tighter_constraints: If True, use more restrictive agility constraints
    """
    end_time = start_time + timedelta(hours=duration_hours)
    
    # Tighter constraints to stress the scheduler
    if tighter_constraints:
        max_roll_rate = 0.8  # Slower roll rate
        max_roll_accel = 800.0  # Slower acceleration
        max_pitch_rate = 0.8  # Slower pitch rate
        imaging_time = 8.0  # Longer imaging time
    else:
        max_roll_rate = 1.0
        max_roll_accel = 1000.0
        max_pitch_rate = 1.0
        imaging_time = 5.0
    
    payload = {
        "scenario_id": f"tight_{duration_hours}h",
        "satellites": [SATELLITE_TLE],
        "targets": TIGHT_TARGETS,
        "time_window": {
            "start": start_time.isoformat() + "Z",
            "end": end_time.isoformat() + "Z"
        },
        "planning_params": {
            "imaging_time_s": imaging_time,
            "max_roll_rate_dps": max_roll_rate,
            "max_roll_accel_dps2": max_roll_accel,
            "max_spacecraft_roll_deg": 45.0,
            "max_pitch_rate_dps": max_pitch_rate,
            "max_pitch_accel_dps2": 10000.0,
            "max_spacecraft_pitch_deg": 30.0,  # Enable pitch
            "quality_model": "uniform",
            "quality_weight": 0.5
        },
        "algorithms": algorithms
    }
    
    print(f"  📡 Calling API: {duration_hours}h window from {start_time.strftime('%Y-%m-%d %H:%M')}")
    if tighter_constraints:
        print(f"      ⚠️  Using tighter agility constraints (roll_rate={max_roll_rate}°/s)")
    
    response = requests.post(DEBUG_ENDPOINT, json=payload, timeout=180)
    
    if response.status_code != 200:
        print(f"  ❌ API Error {response.status_code}")
        print(f"     Response: {response.text[:500]}")
    
    response.raise_for_status()
    return response.json()


def extract_covered_targets(schedule: List[Dict]) -> set:
    """Extract unique target names from schedule."""
    return {opp["target_id"] for opp in schedule}


def analyze_results(results: Dict[str, Any], duration_hours: int) -> Dict[str, Any]:
    """Analyze results from API response."""
    roll_only_data = results["algorithms"]["first_fit"]
    roll_pitch_data = results["algorithms"]["roll_pitch_first_fit"]
    
    roll_only_metrics = roll_only_data["metrics"]
    roll_pitch_metrics = roll_pitch_data["metrics"]
    
    roll_only_schedule = roll_only_data["schedule"]
    roll_pitch_schedule = roll_pitch_data["schedule"]
    
    roll_only_targets = extract_covered_targets(roll_only_schedule)
    roll_pitch_targets = extract_covered_targets(roll_pitch_schedule)
    
    pitch_exclusive_targets = roll_pitch_targets - roll_only_targets
    
    return {
        "duration_hours": duration_hours,
        "roll_only": {
            "covered": len(roll_only_targets),
            "total_opps": roll_only_metrics["total_opportunities"],
            "accepted": roll_only_metrics["accepted"],
            "mean_incidence": roll_only_metrics["mean_incidence_deg"],
            "total_roll": roll_only_metrics["total_roll_used_deg"],
            "max_roll": roll_only_metrics["max_roll_deg"],
            "total_maneuver_time": roll_only_metrics["total_maneuver_time_s"],
            "opps_using_pitch": roll_only_metrics["opps_using_pitch"],
            "targets": sorted(roll_only_targets)
        },
        "roll_pitch": {
            "covered": len(roll_pitch_targets),
            "total_opps": roll_pitch_metrics["total_opportunities"],
            "accepted": roll_pitch_metrics["accepted"],
            "mean_incidence": roll_pitch_metrics["mean_incidence_deg"],
            "total_roll": roll_pitch_metrics["total_roll_used_deg"],
            "max_roll": roll_pitch_metrics["max_roll_deg"],
            "total_pitch": roll_pitch_metrics["total_pitch_used_deg"],
            "max_pitch": roll_pitch_metrics["max_pitch_deg"],
            "total_maneuver_time": roll_pitch_metrics["total_maneuver_time_s"],
            "opps_using_pitch": roll_pitch_metrics["opps_using_pitch"],
            "targets": sorted(roll_pitch_targets)
        },
        "improvement": {
            "coverage_delta": len(roll_pitch_targets) - len(roll_only_targets),
            "coverage_pct": ((len(roll_pitch_targets) - len(roll_only_targets)) / len(TIGHT_TARGETS)) * 100,
            "pitch_exclusive_targets": sorted(pitch_exclusive_targets),
            "pitch_enabled_coverage": len(pitch_exclusive_targets) > 0
        }
    }


def print_comparison_table(all_results: List[Dict[str, Any]]):
    """Print comprehensive comparison table."""
    print("\n" + "=" * 140)
    print("🎯 TIGHT SCENARIO: ROLL-ONLY vs ROLL+PITCH COMPARISON")
    print("=" * 140)
    
    table_data = []
    for result in all_results:
        row = [
            f"{result['duration_hours']}h",
            f"{result['roll_only']['covered']}/{len(TIGHT_TARGETS)}",
            f"{result['roll_only']['total_opps']} → {result['roll_only']['accepted']}",
            f"{result['roll_only']['total_maneuver_time']:.0f}s",
            f"{result['roll_only']['max_roll']:.1f}°",
            "0.0°",
            f"{result['roll_pitch']['covered']}/{len(TIGHT_TARGETS)}",
            f"{result['roll_pitch']['total_opps']} → {result['roll_pitch']['accepted']}",
            f"{result['roll_pitch']['total_maneuver_time']:.0f}s",
            f"{result['roll_pitch']['max_roll']:.1f}°",
            f"{result['roll_pitch']['max_pitch']:.1f}°",
            f"+{result['improvement']['coverage_delta']}",
            f"+{result['improvement']['coverage_pct']:.0f}%",
            "✓" if result['improvement']['pitch_enabled_coverage'] else "✗"
        ]
        table_data.append(row)
    
    headers = [
        "Window",
        "Roll-Only\nCoverage",
        "Roll-Only\nOpps",
        "Roll-Only\nManeuver",
        "Roll-Only\nMax Roll",
        "Roll-Only\nMax Pitch",
        "Roll+Pitch\nCoverage",
        "Roll+Pitch\nOpps",
        "Roll+Pitch\nManeuver",
        "Roll+Pitch\nMax Roll",
        "Roll+Pitch\nMax Pitch",
        "Coverage\nΔ",
        "Coverage\n%",
        "Pitch\nHelped?"
    ]
    
    print("\n" + tabulate(table_data, headers=headers, tablefmt="grid"))


def print_pitch_exclusive_targets(all_results: List[Dict[str, Any]]):
    """Print targets that were ONLY captured by pitch."""
    print("\n" + "=" * 140)
    print("🎯 TARGETS CAPTURED BY ROLL+PITCH BUT MISSED BY ROLL-ONLY")
    print("=" * 140)
    
    found_exclusive = False
    for result in all_results:
        exclusive = result['improvement']['pitch_exclusive_targets']
        if exclusive:
            found_exclusive = True
            print(f"\n{result['duration_hours']}h Window:")
            print(f"  ✅ Pitch enabled capture of {len(exclusive)} additional target(s):")
            for target in exclusive:
                print(f"     • {target}")
            
            roll_only_targets = set(result['roll_only']['targets'])
            common_targets = roll_only_targets & set(result['roll_pitch']['targets'])
            print(f"  ℹ️  Both algorithms captured: {', '.join(sorted(common_targets))}")
    
    if not found_exclusive:
        print("\n  ℹ️  No exclusive pitch captures found.")
        print("     Trying even tighter constraints or different target geometries may show improvement.")


def print_detailed_comparison(all_results: List[Dict[str, Any]]):
    """Print detailed target-by-target comparison."""
    print("\n" + "=" * 140)
    print("📋 DETAILED TARGET COVERAGE COMPARISON")
    print("=" * 140)
    
    for result in all_results:
        print(f"\n{'─' * 140}")
        print(f"{result['duration_hours']}h WINDOW - {len(TIGHT_TARGETS)} Targets in Middle East/Gulf Region")
        print(f"{'─' * 140}")
        
        all_targets = sorted(set(result['roll_only']['targets']) | set(result['roll_pitch']['targets']))
        
        table_data = []
        for target in all_targets:
            roll_only_captured = target in result['roll_only']['targets']
            roll_pitch_captured = target in result['roll_pitch']['targets']
            
            row = [target, "✓" if roll_only_captured else "✗", "✓" if roll_pitch_captured else "✗"]
            
            if roll_pitch_captured and not roll_only_captured:
                row.append("🎯 PITCH ENABLED CAPTURE")
            elif roll_only_captured and roll_pitch_captured:
                row.append("Both captured")
            elif not roll_only_captured and not roll_pitch_captured:
                row.append("Both missed")
            else:
                row.append("Unexpected")
            
            table_data.append(row)
        
        print("\n" + tabulate(table_data, headers=["Target", "Roll-Only", "Roll+Pitch", "Result"], tablefmt="grid"))
        
        print(f"\nSummary:")
        print(f"  • Roll-Only: {result['roll_only']['covered']}/{len(TIGHT_TARGETS)} ({result['roll_only']['covered']/len(TIGHT_TARGETS)*100:.0f}%)")
        print(f"  • Roll+Pitch: {result['roll_pitch']['covered']}/{len(TIGHT_TARGETS)} ({result['roll_pitch']['covered']/len(TIGHT_TARGETS)*100:.0f}%)")
        print(f"  • Improvement: +{result['improvement']['coverage_delta']} targets (+{result['improvement']['coverage_pct']:.0f}%)")
        print(f"  • Pitch Usage: {result['roll_pitch']['opps_using_pitch']} opportunities (max: {result['roll_pitch']['max_pitch']:.1f}°)")


def main():
    """Main test execution."""
    print("\n" + "=" * 140)
    print("🚀 TIGHT SCENARIO: TESTING PITCH CAPABILITY UNDER PRESSURE")
    print("=" * 140)
    print(f"\nSatellite: {SATELLITE_TLE['name']}")
    print(f"Targets: {len(TIGHT_TARGETS)} in Middle East/Gulf region")
    print(f"  • Geographic span: ~2000 km (tight clustering)")
    print(f"  • Mix of priorities: 5 high, 6 medium, 4 low")
    print(f"  • Expected: Tight timing conflicts between passes")
    print(f"Pitch Capability: 30° (enabled for roll+pitch, disabled for roll-only)")
    
    print("\n📡 Checking backend server...")
    if not check_server_health():
        print("❌ Backend server not running!")
        print("   Please start it with: ./run_dev.sh")
        return 1
    print("✅ Backend server is running")
    
    # Test scenarios with progressively shorter windows
    test_scenarios = [
        {"hours": 6, "desc": "6-hour window (very tight - expected conflicts)", "tight": True},
        {"hours": 12, "desc": "12-hour window (tight timing)", "tight": True},
        {"hours": 18, "desc": "18-hour window (moderate pressure)", "tight": False},
    ]
    
    all_results = []
    start_time = datetime(2025, 11, 18, 0, 0, 0)
    
    for scenario in test_scenarios:
        print(f"\n{'=' * 140}")
        print(f"Testing: {scenario['desc']}")
        print(f"{'=' * 140}")
        
        try:
            result = run_scenario(
                start_time=start_time,
                duration_hours=scenario["hours"],
                algorithms=["first_fit", "roll_pitch_first_fit"],
                tighter_constraints=scenario.get("tight", False)
            )
            
            if "algorithms" in result and "first_fit" in result["algorithms"] and "roll_pitch_first_fit" in result["algorithms"]:
                print("  ✅ API call successful")
                
                analysis = analyze_results(result, scenario["hours"])
                all_results.append(analysis)
                
                print(f"\n  Quick Summary:")
                print(f"    Roll-Only: {analysis['roll_only']['covered']}/{len(TIGHT_TARGETS)} targets")
                print(f"    Roll+Pitch: {analysis['roll_pitch']['covered']}/{len(TIGHT_TARGETS)} targets")
                print(f"    Improvement: +{analysis['improvement']['coverage_delta']} targets")
                print(f"    Pitch used: {analysis['roll_pitch']['opps_using_pitch']} times (max: {analysis['roll_pitch']['max_pitch']:.1f}°)")
                
                if analysis['improvement']['pitch_enabled_coverage']:
                    print(f"    🎯 PITCH UNLOCKED: {', '.join(analysis['improvement']['pitch_exclusive_targets'])}")
            else:
                print(f"  ❌ Unexpected API response structure")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        time.sleep(1)
    
    if all_results:
        print_comparison_table(all_results)
        print_pitch_exclusive_targets(all_results)
        print_detailed_comparison(all_results)
        
        print("\n" + "=" * 140)
        print("🏆 FINAL VERDICT")
        print("=" * 140)
        
        total_improvement = sum(r['improvement']['coverage_delta'] for r in all_results)
        any_pitch_helped = any(r['improvement']['pitch_enabled_coverage'] for r in all_results)
        max_improvement = max((r['improvement']['coverage_delta'] for r in all_results), default=0)
        
        if total_improvement > 0:
            print(f"\n✅ PITCH CAPABILITY DEMONSTRATED VALUE!")
            print(f"   • Total additional targets captured: {total_improvement}")
            print(f"   • Maximum single-window improvement: +{max_improvement} targets")
            print(f"   • Pitch enabled exclusive coverage: {'YES' if any_pitch_helped else 'NO'}")
            print(f"\n💡 Key Insight:")
            print(f"   Pitch provides value in tight-timing scenarios where roll-only")
            print(f"   scheduling creates conflicts. The 2D slew capability (roll+pitch)")
            print(f"   offers more flexibility to capture time-critical targets.")
        else:
            print(f"\n⚖️  EQUAL PERFORMANCE IN THIS SCENARIO")
            print(f"   Both algorithms achieved identical coverage.")
            print(f"\n💡 Possible reasons:")
            print(f"   • Targets well-distributed for roll-only scheduling")
            print(f"   • Time windows sufficient for sequential captures")
            print(f"   • Pass geometries favorable without pitch")
            print(f"\n🔍 To demonstrate pitch value, try:")
            print(f"   • Even shorter time windows (3-4 hours)")
            print(f"   • More targets (20+) for more conflicts")
            print(f"   • Targets with overlapping pass times")
        
        print("\n" + "=" * 140)
    else:
        print("\n❌ No results to compare")
        return 1
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
