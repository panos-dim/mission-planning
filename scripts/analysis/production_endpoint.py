#!/usr/bin/env python3
"""
Test the PRODUCTION endpoint /api/planning/schedule
Validates that all 4 algorithms work correctly with 1-second dynamic pitch sampling.
"""

import requests
import json
from datetime import datetime, timedelta
from tabulate import tabulate

BASE_URL = "http://localhost:8000"

# Test data - Match frontend payload structure!
TLE = {
    "name": "ICEYE-X44",
    "line1": "1 62707U 25009DC  25314.79215024  .00005593  00000+0  52657-3 0  9992",
    "line2": "2 62707  97.7263  32.4188 0002390 115.7483 244.3984 14.94240684 67309"
}

TARGETS = [
    {"name": "Athens", "latitude": 37.9838, "longitude": 23.7275, "description": "Greek Capital - High Priority", "priority": 5},
    {"name": "Istanbul", "latitude": 41.0082, "longitude": 28.9784, "description": "Turkey - Major City (~500km from Athens)", "priority": 4},
    {"name": "Thessaloniki", "latitude": 40.6401, "longitude": 22.9444, "description": "Northern Greece (~310km from Athens)", "priority": 3},
    {"name": "Izmir", "latitude": 38.4237, "longitude": 27.1428, "description": "Western Turkey (~280km from Athens)", "priority": 3},
    {"name": "Nicosia", "latitude": 35.1856, "longitude": 33.3823, "description": "Cyprus - Capital (~800km from Athens)", "priority": 3},
    {"name": "Sofia", "latitude": 42.6977, "longitude": 23.3219, "description": "Bulgaria - Capital (~550km from Athens)", "priority": 2},
    {"name": "Rhodes", "latitude": 36.4341, "longitude": 28.2176, "description": "Greek Island (~430km from Athens)", "priority": 2},
    {"name": "Antalya", "latitude": 36.8969, "longitude": 30.7133, "description": "Southern Turkey (~480km from Athens)", "priority": 2},
    {"name": "Heraklion", "latitude": 35.3387, "longitude": 25.1442, "description": "Crete, Greece (~380km from Athens)", "priority": 1},
    {"name": "Patras", "latitude": 38.2466, "longitude": 21.7346, "description": "Western Greece (~210km from Athens)", "priority": 1},
]


def run_mission_analysis():
    """Step 1: Run mission analysis to populate current_mission_data"""
    print("\n" + "=" * 100)
    print("STEP 1: Running Mission Analysis")
    print("=" * 100)
    
    # Use exact time window from frontend
    start_time = datetime(2025, 11, 18, 12, 26, 0)
    
    payload = {
        "tle": TLE,  # Not "satellite"!
        "targets": TARGETS,
        "start_time": start_time.isoformat() + "Z",
        "end_time": (start_time + timedelta(hours=24)).isoformat() + "Z",
        "mission_type": "imaging",  # lowercase!
        "imaging_type": "optical",
        "max_spacecraft_roll_deg": 45.0,
        "max_spacecraft_pitch_deg": 45.0  # Enable pitch!
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/mission/analyze", json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if result.get("success"):
            print(f"✅ Mission analysis complete")
            print(f"   Found {len(result.get('passes', []))} passes")
            return True
        else:
            print(f"❌ Mission analysis failed: {result.get('message')}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def run_planning():
    """Step 2: Run planning algorithms"""
    print("\n" + "=" * 100)
    print("STEP 2: Running Planning Algorithms")
    print("=" * 100)
    
    payload = {
        "algorithms": ["first_fit", "best_fit", "roll_pitch_first_fit", "roll_pitch_best_fit"],
        "imaging_time_s": 5.0,
        "max_roll_rate_dps": 1.0,
        "max_roll_accel_dps2": 1000.0,
        "max_pitch_deg": 45.0,  # This won't be used (we use mission_data value)
        "max_pitch_rate_dps": 1.0,
        "max_pitch_accel_dps2": 10000.0,
        "quality_weight": 0.6,
        "quality_model": "monotonic"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/planning/schedule", json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if result.get("success"):
            return result.get("results", {})
        else:
            print(f"❌ Planning failed: {result.get('message')}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def print_summary_table(results):
    """Print algorithm comparison table"""
    print("\n" + "=" * 100)
    print("📊 ALGORITHM COMPARISON TABLE")
    print("=" * 100)
    
    table = []
    for algo in ["first_fit", "best_fit", "roll_pitch_first_fit", "roll_pitch_best_fit"]:
        if algo not in results:
            continue
            
        r = results[algo]
        metrics = r.get("metrics", {})
        
        table.append([
            algo,
            f"{metrics.get('coverage_count', 0)}/{metrics.get('total_targets', 0)}",
            f"{metrics.get('coverage_percent', 0):.0f}%",
            metrics.get("total_opportunities", 0),
            metrics.get("accepted", 0),
            f"{metrics.get('mean_incidence_deg', 0):.1f}°",
            f"{metrics.get('mean_off_nadir_deg', 0):.1f}°",
            f"{metrics.get('mean_pitch_deg', 0):.1f}°",
            f"{metrics.get('max_pitch_deg', 0):.1f}°",
            f"{metrics.get('runtime_ms', 0):.2f}ms"
        ])
    
    headers = ["Algorithm", "Coverage", "%", "Total Opps", "Accepted", 
               "Mean Inc", "Mean Off-Nadir", "Mean Pitch", "Max Pitch", "Runtime"]
    
    print("\n" + tabulate(table, headers=headers, tablefmt="grid"))


def print_target_coverage(results):
    """Print target-by-target coverage"""
    print("\n" + "=" * 100)
    print("🎯 TARGET COVERAGE COMPARISON")
    print("=" * 100)
    
    # Get all targets
    all_targets = set()
    for algo, r in results.items():
        for opp in r.get("schedule", []):
            all_targets.add(opp["target_id"])
    
    # Build coverage table (sort by priority desc, then name)
    table = []
    sorted_targets = sorted(TARGETS, key=lambda t: (-t["priority"], t["name"]))
    for target_obj in sorted_targets:
        target = target_obj["name"]
        row = [f"{target} (P{target_obj['priority']})"]
        
        for algo in ["first_fit", "best_fit", "roll_pitch_first_fit", "roll_pitch_best_fit"]:
            if algo not in results:
                row.append("N/A")
                continue
                
            covered = any(opp["target_id"] == target for opp in results[algo].get("schedule", []))
            row.append("✓" if covered else "✗")
        
        table.append(row)
    
    headers = ["Target", "first_fit", "best_fit", "roll_pitch_first_fit", "roll_pitch_best_fit"]
    print("\n" + tabulate(table, headers=headers, tablefmt="grid"))


def print_pitch_analysis(results):
    """Print pitch usage analysis"""
    print("\n" + "=" * 100)
    print("🎯 PITCH USAGE ANALYSIS")
    print("=" * 100)
    
    table = []
    for algo in ["first_fit", "best_fit", "roll_pitch_first_fit", "roll_pitch_best_fit"]:
        if algo not in results:
            continue
            
        metrics = results[algo].get("metrics", {})
        schedule = results[algo].get("schedule", [])
        
        # Count pitch usage
        opps_using_pitch = sum(1 for opp in schedule if abs(opp.get("pitch_angle", 0)) > 1.0)
        
        table.append([
            algo,
            metrics.get("total_opportunities", 0),
            metrics.get("accepted", 0),
            f"{metrics.get('mean_pitch_deg', 0):.1f}°",
            f"{metrics.get('max_pitch_deg', 0):.1f}°",
            opps_using_pitch,
            f"{metrics.get('total_pitch_used_deg', 0):.1f}°"
        ])
    
    headers = ["Algorithm", "Total Opps", "Accepted", "Mean Pitch", "Max Pitch", "Using Pitch", "Total Pitch"]
    print("\n" + tabulate(table, headers=headers, tablefmt="grid"))


def validate_results(results):
    """Validate that results make sense"""
    print("\n" + "=" * 100)
    print("✅ VALIDATION CHECKS")
    print("=" * 100)
    
    checks = []
    
    # Check 1: roll+pitch >= roll-only coverage
    ff_coverage = len(results["first_fit"].get("schedule", []))
    rpff_coverage = len(results["roll_pitch_first_fit"].get("schedule", []))
    checks.append((
        "roll_pitch_first_fit >= first_fit",
        rpff_coverage >= ff_coverage,
        f"{rpff_coverage} >= {ff_coverage}"
    ))
    
    bf_coverage = len(results["best_fit"].get("schedule", []))
    rpbf_coverage = len(results["roll_pitch_best_fit"].get("schedule", []))
    checks.append((
        "roll_pitch_best_fit >= best_fit",
        rpbf_coverage >= bf_coverage,
        f"{rpbf_coverage} >= {bf_coverage}"
    ))
    
    # Check 2: roll-only has no pitch
    ff_max_pitch = results["first_fit"]["metrics"].get("max_pitch_deg", 0)
    bf_max_pitch = results["best_fit"]["metrics"].get("max_pitch_deg", 0)
    checks.append((
        "first_fit has near-zero pitch",
        ff_max_pitch <= 1.0,
        f"max_pitch={ff_max_pitch:.1f}°"
    ))
    checks.append((
        "best_fit has near-zero pitch",
        bf_max_pitch <= 1.0,
        f"max_pitch={bf_max_pitch:.1f}°"
    ))
    
    # Check 3: roll+pitch uses pitch
    rpff_max_pitch = results["roll_pitch_first_fit"]["metrics"].get("max_pitch_deg", 0)
    rpbf_max_pitch = results["roll_pitch_best_fit"]["metrics"].get("max_pitch_deg", 0)
    checks.append((
        "roll_pitch_first_fit uses pitch",
        rpff_max_pitch > 5.0,
        f"max_pitch={rpff_max_pitch:.1f}°"
    ))
    checks.append((
        "roll_pitch_best_fit uses pitch",
        rpbf_max_pitch > 5.0,
        f"max_pitch={rpbf_max_pitch:.1f}°"
    ))
    
    # Check 4: Opportunity counts
    ff_opps = results["first_fit"]["metrics"].get("total_opportunities", 0)
    rpff_opps = results["roll_pitch_first_fit"]["metrics"].get("total_opportunities", 0)
    if ff_opps > 0 and rpff_opps > ff_opps:
        checks.append((
            "roll_pitch has MORE opportunities",
            rpff_opps > ff_opps * 5,  # At least 5x more
            f"{rpff_opps} > {ff_opps} (factor: {rpff_opps/ff_opps:.1f}x)"
        ))
    else:
        checks.append((
            "roll_pitch has MORE opportunities",
            False,
            f"{rpff_opps} vs {ff_opps} (need data)"
        ))
    
    # Print results
    for check_name, passed, details in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}: {details}")
    
    all_passed = all(p for _, p, _ in checks)
    return all_passed


def main():
    print("\n" + "=" * 100)
    print("🧪 TESTING PRODUCTION ENDPOINT: /api/planning/schedule")
    print("=" * 100)
    
    # Check server
    try:
        response = requests.get(f"{BASE_URL}/", timeout=2)
        if response.status_code != 200:
            print("❌ Backend server not running!")
            return 1
    except:
        print("❌ Backend server not running!")
        return 1
    
    # Step 1: Mission analysis
    if not run_mission_analysis():
        return 1
    
    # Step 2: Planning
    results = run_planning()
    if not results:
        return 1
    
    print(f"\n✅ Planning complete! Got results for {len(results)} algorithms")
    
    # Print analysis
    print_summary_table(results)
    print_target_coverage(results)
    print_pitch_analysis(results)
    
    # Validate
    all_valid = validate_results(results)
    
    print("\n" + "=" * 100)
    if all_valid:
        print("🎉 ALL VALIDATION CHECKS PASSED!")
    else:
        print("⚠️  SOME VALIDATION CHECKS FAILED")
    print("=" * 100)
    
    return 0 if all_valid else 1


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
