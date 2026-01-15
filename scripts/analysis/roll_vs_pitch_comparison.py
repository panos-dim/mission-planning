#!/usr/bin/env python3
"""
Test script to compare Roll-Only vs Roll+Pitch algorithms using the debug API.

This script:
1. Starts the backend server (if not running)
2. Calls the debug API endpoint with different time ranges
3. Compares first_fit (roll-only) vs roll_pitch_first_fit (roll+pitch)
4. Creates comparison tables showing coverage improvements
5. Identifies specific targets captured by pitch that roll-only missed
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
import time
from tabulate import tabulate

# API endpoint
BASE_URL = "http://localhost:8000"
DEBUG_ENDPOINT = f"{BASE_URL}/api/v1/debug/planning/run_scenario"

# Test satellite (ICEYE-X44)
SATELLITE_TLE = {
    "id": "ICEYE-X44",
    "name": "ICEYE-X44",
    "tle_line1": "1 62707U 25009DC  25306.22031033  .00004207  00000+0  39848-3 0  9995",
    "tle_line2": "2 62707  97.7269  23.9854 0002193 135.9671 224.1724 14.94137357 66022"
}

# Test targets (10 targets around Mediterranean/Europe)
TEST_TARGETS = [
    {"name": "Athens", "latitude": 37.9838, "longitude": 23.7275, "priority": 5},
    {"name": "Istanbul", "latitude": 41.0082, "longitude": 28.9784, "priority": 4},
    {"name": "Rome", "latitude": 41.9028, "longitude": 12.4964, "priority": 5},
    {"name": "Barcelona", "latitude": 41.3851, "longitude": 2.1734, "priority": 4},
    {"name": "Paris", "latitude": 48.8566, "longitude": 2.3522, "priority": 5},
    {"name": "Berlin", "latitude": 52.5200, "longitude": 13.4050, "priority": 4},
    {"name": "Vienna", "latitude": 48.2082, "longitude": 16.3738, "priority": 3},
    {"name": "Prague", "latitude": 50.0755, "longitude": 14.4378, "priority": 3},
    {"name": "Warsaw", "latitude": 52.2297, "longitude": 21.0122, "priority": 3},
    {"name": "Budapest", "latitude": 47.4979, "longitude": 19.0402, "priority": 3},
]


def check_server_health():
    """Check if backend server is running."""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=2)
        return response.status_code == 200
    except:
        return False


def run_scenario(start_time: datetime, duration_hours: int, algorithms: List[str]) -> Dict[str, Any]:
    """
    Run a planning scenario via the debug API.
    
    Args:
        start_time: Mission start time
        duration_hours: Mission duration in hours
        algorithms: List of algorithm names to test
        
    Returns:
        API response with results for each algorithm
    """
    end_time = start_time + timedelta(hours=duration_hours)
    
    payload = {
        "scenario_id": f"test_{duration_hours}h",
        "satellites": [SATELLITE_TLE],
        "targets": TEST_TARGETS,
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
            "max_spacecraft_pitch_deg": 30.0,  # Enable pitch
            "quality_model": "uniform",
            "quality_weight": 0.5
        },
        "algorithms": algorithms
    }
    
    print(f"  📡 Calling API: {duration_hours}h window from {start_time.strftime('%Y-%m-%d %H:%M')}")
    
    response = requests.post(DEBUG_ENDPOINT, json=payload, timeout=120)
    
    # Debug: print response details if error
    if response.status_code != 200:
        print(f"  ❌ API Error {response.status_code}")
        print(f"     Response: {response.text[:500]}")
    
    response.raise_for_status()
    
    return response.json()


def extract_covered_targets(schedule: List[Dict]) -> set:
    """Extract unique target names from schedule."""
    return {opp["target_id"] for opp in schedule}


def analyze_results(results: Dict[str, Any], duration_hours: int) -> Dict[str, Any]:
    """
    Analyze results from API response.
    
    Returns:
        Dictionary with comparison metrics
    """
    # API returns algorithms in 'algorithms' key
    roll_only_data = results["algorithms"]["first_fit"]
    roll_pitch_data = results["algorithms"]["roll_pitch_first_fit"]
    
    # Extract metrics
    roll_only_metrics = roll_only_data["metrics"]
    roll_pitch_metrics = roll_pitch_data["metrics"]
    
    # Extract schedules
    roll_only_schedule = roll_only_data["schedule"]
    roll_pitch_schedule = roll_pitch_data["schedule"]
    
    # Get covered targets
    roll_only_targets = extract_covered_targets(roll_only_schedule)
    roll_pitch_targets = extract_covered_targets(roll_pitch_schedule)
    
    # Find targets only captured by pitch
    pitch_exclusive_targets = roll_pitch_targets - roll_only_targets
    
    # Calculate improvement
    coverage_improvement = len(roll_pitch_targets) - len(roll_only_targets)
    
    return {
        "duration_hours": duration_hours,
        "roll_only": {
            "covered": len(roll_only_targets),
            "total_opps": roll_only_metrics["total_opportunities"],
            "accepted": roll_only_metrics["accepted"],
            "mean_incidence": roll_only_metrics["mean_incidence_deg"],
            "total_roll": roll_only_metrics["total_roll_used_deg"],
            "max_roll": roll_only_metrics["max_roll_deg"],
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
            "opps_using_pitch": roll_pitch_metrics["opps_using_pitch"],
            "targets": sorted(roll_pitch_targets)
        },
        "improvement": {
            "coverage_delta": coverage_improvement,
            "coverage_pct": (coverage_improvement / len(TEST_TARGETS)) * 100,
            "pitch_exclusive_targets": sorted(pitch_exclusive_targets),
            "pitch_enabled_coverage": len(pitch_exclusive_targets) > 0
        }
    }


def print_comparison_table(all_results: List[Dict[str, Any]]):
    """Print comprehensive comparison table."""
    print("\n" + "=" * 120)
    print("ROLL-ONLY vs ROLL+PITCH COMPARISON ACROSS TIME WINDOWS")
    print("=" * 120)
    
    # Main comparison table
    table_data = []
    for result in all_results:
        row = [
            f"{result['duration_hours']}h",
            f"{result['roll_only']['covered']}/{len(TEST_TARGETS)}",
            f"{result['roll_only']['total_opps']} → {result['roll_only']['accepted']}",
            f"{result['roll_only']['mean_incidence']:.1f}°",
            f"{result['roll_only']['max_roll']:.1f}°",
            "0.0°",
            f"{result['roll_pitch']['covered']}/{len(TEST_TARGETS)}",
            f"{result['roll_pitch']['total_opps']} → {result['roll_pitch']['accepted']}",
            f"{result['roll_pitch']['mean_incidence']:.1f}°",
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
        "Roll-Only\nMean Inc",
        "Roll-Only\nMax Roll",
        "Roll-Only\nMax Pitch",
        "Roll+Pitch\nCoverage",
        "Roll+Pitch\nOpps",
        "Roll+Pitch\nMean Inc",
        "Roll+Pitch\nMax Roll",
        "Roll+Pitch\nMax Pitch",
        "Coverage\nΔ",
        "Coverage\n%",
        "Pitch\nHelped?"
    ]
    
    print("\n" + tabulate(table_data, headers=headers, tablefmt="grid"))


def print_pitch_exclusive_targets(all_results: List[Dict[str, Any]]):
    """Print targets that were ONLY captured by pitch."""
    print("\n" + "=" * 120)
    print("🎯 TARGETS CAPTURED BY ROLL+PITCH BUT MISSED BY ROLL-ONLY")
    print("=" * 120)
    
    found_exclusive = False
    for result in all_results:
        exclusive = result['improvement']['pitch_exclusive_targets']
        if exclusive:
            found_exclusive = True
            print(f"\n{result['duration_hours']}h Window:")
            print(f"  ✅ Pitch enabled capture of {len(exclusive)} additional target(s):")
            for target in exclusive:
                print(f"     • {target}")
            
            # Show what was captured by both
            roll_only_targets = set(result['roll_only']['targets'])
            common_targets = roll_only_targets & set(result['roll_pitch']['targets'])
            print(f"  ℹ️  Both algorithms captured: {', '.join(sorted(common_targets))}")
    
    if not found_exclusive:
        print("\n  ℹ️  No exclusive pitch captures found in these time windows.")
        print("     (Both algorithms achieved same coverage)")


def print_detailed_schedule_comparison(all_results: List[Dict[str, Any]]):
    """Print detailed schedule comparison for each time window."""
    print("\n" + "=" * 120)
    print("📋 DETAILED TARGET COVERAGE BY TIME WINDOW")
    print("=" * 120)
    
    for result in all_results:
        print(f"\n{'─' * 120}")
        print(f"{result['duration_hours']}h WINDOW")
        print(f"{'─' * 120}")
        
        # Create target-by-target comparison
        all_targets = sorted(set(result['roll_only']['targets']) | set(result['roll_pitch']['targets']))
        
        table_data = []
        for target in all_targets:
            roll_only_captured = target in result['roll_only']['targets']
            roll_pitch_captured = target in result['roll_pitch']['targets']
            
            row = [
                target,
                "✓" if roll_only_captured else "✗",
                "✓" if roll_pitch_captured else "✗",
            ]
            
            # Add insight
            if roll_pitch_captured and not roll_only_captured:
                row.append("🎯 PITCH ENABLED CAPTURE")
            elif roll_only_captured and roll_pitch_captured:
                row.append("Both captured")
            elif not roll_only_captured and not roll_pitch_captured:
                row.append("Both missed")
            else:
                row.append("Unexpected")
            
            table_data.append(row)
        
        headers = ["Target", "Roll-Only", "Roll+Pitch", "Insight"]
        print("\n" + tabulate(table_data, headers=headers, tablefmt="grid"))
        
        # Summary stats
        print(f"\nSummary:")
        print(f"  • Roll-Only Coverage: {result['roll_only']['covered']}/{len(TEST_TARGETS)} ({result['roll_only']['covered']/len(TEST_TARGETS)*100:.0f}%)")
        print(f"  • Roll+Pitch Coverage: {result['roll_pitch']['covered']}/{len(TEST_TARGETS)} ({result['roll_pitch']['covered']/len(TEST_TARGETS)*100:.0f}%)")
        print(f"  • Improvement: +{result['improvement']['coverage_delta']} targets (+{result['improvement']['coverage_pct']:.0f}%)")


def main():
    """Main test execution."""
    print("\n" + "=" * 120)
    print("🚀 ROLL-ONLY vs ROLL+PITCH VALIDATION TEST")
    print("=" * 120)
    print(f"\nSatellite: {SATELLITE_TLE['name']}")
    print(f"Targets: {len(TEST_TARGETS)} ({', '.join(t['name'] for t in TEST_TARGETS[:5])}...)")
    print(f"Pitch Capability: 30° (enabled for roll+pitch, disabled for roll-only)")
    
    # Check server
    print("\n📡 Checking backend server...")
    if not check_server_health():
        print("❌ Backend server not running!")
        print("   Please start it with: ./run_dev.sh")
        return 1
    print("✅ Backend server is running")
    
    # Test different time windows
    test_scenarios = [
        {"hours": 12, "desc": "12-hour window (tight timing)"},
        {"hours": 24, "desc": "24-hour window (1 day)"},
        {"hours": 48, "desc": "48-hour window (2 days)"},
    ]
    
    all_results = []
    
    start_time = datetime(2025, 11, 18, 0, 0, 0)  # Nov 18, 2025 00:00 UTC
    
    for scenario in test_scenarios:
        print(f"\n{'=' * 120}")
        print(f"Testing: {scenario['desc']}")
        print(f"{'=' * 120}")
        
        try:
            # Run both algorithms
            result = run_scenario(
                start_time=start_time,
                duration_hours=scenario["hours"],
                algorithms=["first_fit", "roll_pitch_first_fit"]
            )
            
            # Check if we have the expected data structure
            if "algorithms" in result and "first_fit" in result["algorithms"] and "roll_pitch_first_fit" in result["algorithms"]:
                print("  ✅ API call successful")
                
                # Analyze results
                analysis = analyze_results(result, scenario["hours"])
                all_results.append(analysis)
                
                # Quick summary
                print(f"\n  Quick Summary:")
                print(f"    Roll-Only: {analysis['roll_only']['covered']}/{len(TEST_TARGETS)} targets")
                print(f"    Roll+Pitch: {analysis['roll_pitch']['covered']}/{len(TEST_TARGETS)} targets")
                print(f"    Improvement: +{analysis['improvement']['coverage_delta']} targets")
                print(f"    Pitch used: {analysis['roll_pitch']['opps_using_pitch']} times (max: {analysis['roll_pitch']['max_pitch']:.1f}°)")
                
            else:
                print(f"  ❌ Unexpected API response structure")
                print(f"     Result keys: {list(result.keys())}")
                if "algorithms" in result:
                    print(f"     Available algorithms: {list(result['algorithms'].keys())}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        # Brief pause between scenarios
        time.sleep(1)
    
    # Print comprehensive comparison
    if all_results:
        print_comparison_table(all_results)
        print_pitch_exclusive_targets(all_results)
        print_detailed_schedule_comparison(all_results)
        
        # Final verdict
        print("\n" + "=" * 120)
        print("🏆 FINAL VERDICT")
        print("=" * 120)
        
        total_improvement = sum(r['improvement']['coverage_delta'] for r in all_results)
        any_pitch_helped = any(r['improvement']['pitch_enabled_coverage'] for r in all_results)
        
        if total_improvement > 0:
            print(f"\n✅ PITCH CAPABILITY IMPROVED COVERAGE!")
            print(f"   Total additional targets captured across all windows: {total_improvement}")
            print(f"   Pitch enabled coverage that roll-only couldn't achieve: {'YES' if any_pitch_helped else 'NO'}")
        elif total_improvement == 0:
            print(f"\n⚖️  EQUAL PERFORMANCE")
            print(f"   Both algorithms achieved identical coverage across all time windows.")
            print(f"   Note: Pitch may still be valuable for:")
            print(f"   - Different target geometries")
            print(f"   - Tighter timing constraints")
            print(f"   - Multi-satellite coordination")
        else:
            print(f"\n⚠️  UNEXPECTED: Roll+Pitch performed worse")
            print(f"   This suggests an implementation issue that needs investigation.")
        
        print("\n" + "=" * 120)
        
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
