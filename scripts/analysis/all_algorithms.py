#!/usr/bin/env python3
"""
Test ALL 4 algorithms and compare results.
Investigate for bugs in best_fit algorithms.
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

# Test targets
TARGETS = [
    {"name": "Dubai", "latitude": 25.2048, "longitude": 55.2708, "priority": 5},
    {"name": "Abu_Dhabi", "latitude": 24.4539, "longitude": 54.3773, "priority": 5},
    {"name": "Doha", "latitude": 25.2854, "longitude": 51.5310, "priority": 4},
    {"name": "Riyadh", "latitude": 24.7136, "longitude": 46.6753, "priority": 5},
    {"name": "Kuwait_City", "latitude": 29.3759, "longitude": 47.9774, "priority": 4},
    {"name": "Tehran", "latitude": 35.6892, "longitude": 51.3890, "priority": 5},
]


def run_all_algorithms():
    """Run all 4 algorithms and collect results."""
    
    start_time = datetime(2025, 11, 18, 0, 0, 0)
    window_hours = 24
    
    print("\n" + "=" * 120)
    print("🔬 ALGORITHM COMPARISON: Testing All 4 Algorithms")
    print("=" * 120)
    
    print(f"\nConfiguration:")
    print(f"  Satellite: ICEYE-X44")
    print(f"  Targets: {len(TARGETS)}")
    print(f"  Time Window: {window_hours} hours")
    print(f"  Max Roll: 45°, Max Pitch: 45°")
    
    algorithms_to_test = [
        "first_fit",
        "best_fit",
        "roll_pitch_first_fit",
        "roll_pitch_best_fit"
    ]
    
    results = {}
    
    for algo in algorithms_to_test:
        print(f"\n{'─' * 120}")
        print(f"Testing: {algo}")
        print(f"{'─' * 120}")
        
        payload = {
            "scenario_id": f"test_{algo}",
            "satellites": [SATELLITE_TLE],
            "targets": TARGETS,
            "time_window": {
                "start": start_time.isoformat() + "Z",
                "end": (start_time + timedelta(hours=window_hours)).isoformat() + "Z"
            },
            "planning_params": {
                "imaging_time_s": 5.0,
                "max_roll_rate_dps": 1.0,
                "max_roll_accel_dps2": 1000.0,
                "max_spacecraft_roll_deg": 45.0,
                "max_pitch_rate_dps": 1.0,
                "max_pitch_accel_dps2": 10000.0,
                "max_spacecraft_pitch_deg": 45.0,
                "quality_model": "uniform",
                "quality_weight": 0.5
            },
            "algorithms": [algo]
        }
        
        try:
            print(f"  Calling API... ", end="", flush=True)
            response = requests.post(DEBUG_ENDPOINT, json=payload, timeout=180)
            response.raise_for_status()
            result = response.json()
            
            if "algorithms" in result and algo in result["algorithms"]:
                algo_data = result["algorithms"][algo]
                
                # Check status
                status = algo_data.get("status", "unknown")
                print(f"✓ Status: {status}")
                
                if status == "ok":
                    metrics = algo_data["metrics"]
                    schedule = algo_data["schedule"]
                    
                    covered = {opp["target_id"] for opp in schedule}
                    
                    # Calculate incidence angle stats
                    incidences = [abs(opp.get("incidence_angle", 0)) for opp in schedule]
                    pitches = [abs(opp.get("pitch_angle", 0)) for opp in schedule]
                    
                    results[algo] = {
                        "status": status,
                        "coverage": len(covered),
                        "total_opps": metrics["total_opportunities"],
                        "accepted": metrics["accepted"],
                        "mean_incidence": metrics["mean_incidence_deg"],
                        "max_incidence": max(incidences) if incidences else 0,
                        "min_incidence": min(incidences) if incidences else 0,
                        "max_roll": metrics["max_roll_deg"],
                        "max_pitch": metrics["max_pitch_deg"],
                        "opps_using_pitch": metrics["opps_using_pitch"],
                        "total_maneuver": metrics["total_maneuver_time_s"],
                        "covered_targets": sorted(covered),
                        "schedule": schedule,
                        "error": None
                    }
                    
                    print(f"     Coverage: {len(covered)}/{len(TARGETS)}")
                    print(f"     Mean Incidence: {metrics['mean_incidence_deg']:.1f}°")
                    
                elif status == "error":
                    error_msg = algo_data.get("error", "Unknown error")
                    print(f"  ❌ Error: {error_msg}")
                    results[algo] = {
                        "status": "error",
                        "error": error_msg,
                        "coverage": 0
                    }
                
            else:
                print(f"  ❌ Unexpected response structure")
                results[algo] = {
                    "status": "error",
                    "error": "Unexpected response",
                    "coverage": 0
                }
                
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            results[algo] = {
                "status": "error",
                "error": str(e),
                "coverage": 0
            }
    
    return results


def print_comparison_table(results):
    """Print main comparison table."""
    print("\n" + "=" * 120)
    print("📊 ALGORITHM COMPARISON TABLE")
    print("=" * 120)
    
    table = []
    for algo in ["first_fit", "best_fit", "roll_pitch_first_fit", "roll_pitch_best_fit"]:
        r = results.get(algo, {})
        
        if r.get("status") == "ok":
            table.append([
                algo,
                r.get("status", "N/A"),
                f"{r['coverage']}/{len(TARGETS)}",
                f"{r['coverage']/len(TARGETS)*100:.0f}%",
                f"{r['total_opps']}",
                f"{r['accepted']}",
                f"{r['mean_incidence']:.1f}°",
                f"{r['min_incidence']:.1f}°",
                f"{r['max_incidence']:.1f}°",
                f"{r['max_pitch']:.1f}°",
                f"{r['total_maneuver']:.0f}s"
            ])
        else:
            table.append([
                algo,
                r.get("status", "N/A"),
                "ERROR",
                "N/A",
                "N/A",
                "N/A",
                "N/A",
                "N/A",
                "N/A",
                "N/A",
                "N/A"
            ])
    
    headers = ["Algorithm", "Status", "Coverage", "%", "Total Opps", "Accepted", 
               "Mean Inc", "Min Inc", "Max Inc", "Max Pitch", "Maneuver"]
    
    print("\n" + tabulate(table, headers=headers, tablefmt="grid"))


def print_target_coverage(results):
    """Show which targets each algorithm captured."""
    print("\n" + "=" * 120)
    print("🎯 TARGET-BY-TARGET COVERAGE")
    print("=" * 120)
    
    # Get all algorithms that succeeded
    success_algos = [algo for algo, r in results.items() if r.get("status") == "ok"]
    
    if not success_algos:
        print("\n⚠️  No algorithms succeeded")
        return
    
    table = []
    for target in TARGETS:
        row = [target["name"]]
        for algo in ["first_fit", "best_fit", "roll_pitch_first_fit", "roll_pitch_best_fit"]:
            r = results.get(algo, {})
            if r.get("status") == "ok":
                captured = "✓" if target["name"] in r["covered_targets"] else "✗"
                row.append(captured)
            else:
                row.append("ERR")
        table.append(row)
    
    headers = ["Target", "first_fit", "best_fit", "roll_pitch_first_fit", "roll_pitch_best_fit"]
    print("\n" + tabulate(table, headers=headers, tablefmt="grid"))


def print_quality_comparison(results):
    """Compare image quality metrics."""
    print("\n" + "=" * 120)
    print("📸 IMAGE QUALITY COMPARISON")
    print("=" * 120)
    
    success_algos = {algo: r for algo, r in results.items() if r.get("status") == "ok"}
    
    if len(success_algos) < 2:
        print("\n⚠️  Need at least 2 successful algorithms to compare")
        return
    
    table = []
    for algo in ["first_fit", "best_fit", "roll_pitch_first_fit", "roll_pitch_best_fit"]:
        if algo in success_algos:
            r = success_algos[algo]
            table.append([
                algo,
                f"{r['mean_incidence']:.1f}°",
                f"{r['min_incidence']:.1f}°",
                f"{r['max_incidence']:.1f}°",
                f"{r['max_incidence'] - r['min_incidence']:.1f}°"
            ])
    
    headers = ["Algorithm", "Mean Incidence", "Best (Min)", "Worst (Max)", "Range"]
    print("\n" + tabulate(table, headers=headers, tablefmt="grid"))
    
    # Find best quality
    if success_algos:
        best_mean = min((r['mean_incidence'], algo) for algo, r in success_algos.items())
        best_min = min((r['min_incidence'], algo) for algo, r in success_algos.items())
        
        print(f"\n🏆 Quality Winners:")
        print(f"  • Best Average Quality: {best_mean[1]} ({best_mean[0]:.1f}° mean incidence)")
        print(f"  • Best Single Image: {best_min[1]} ({best_min[0]:.1f}° incidence)")


def investigate_errors(results):
    """Investigate any errors or issues."""
    print("\n" + "=" * 120)
    print("🔍 ERROR INVESTIGATION")
    print("=" * 120)
    
    errors_found = False
    
    for algo, r in results.items():
        if r.get("status") != "ok":
            errors_found = True
            print(f"\n❌ {algo}:")
            print(f"   Status: {r.get('status')}")
            print(f"   Error: {r.get('error', 'Unknown')}")
    
    if not errors_found:
        print("\n✅ All algorithms executed successfully - no errors found!")


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
    
    results = run_all_algorithms()
    
    print_comparison_table(results)
    print_target_coverage(results)
    print_quality_comparison(results)
    investigate_errors(results)
    
    print("\n" + "=" * 120)
    print("✅ ALGORITHM COMPARISON COMPLETE")
    print("=" * 120)
    
    # Summary
    success_count = sum(1 for r in results.values() if r.get("status") == "ok")
    print(f"\nSummary:")
    print(f"  • Algorithms tested: {len(results)}")
    print(f"  • Successful: {success_count}")
    print(f"  • Failed: {len(results) - success_count}")
    
    if success_count == len(results):
        print(f"\n🎉 All algorithms working correctly!")
    
    print("\n" + "=" * 120 + "\n")
    
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
