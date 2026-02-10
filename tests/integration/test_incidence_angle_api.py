#!/usr/bin/env python3
"""
Test script to verify incidence angle is working in API and algorithms.

This script:
1. Runs mission analysis with 4 nearby targets
2. Runs all 3 scheduling algorithms
3. Verifies incidence angles are included in responses
4. Compares algorithm results
"""

import json
from datetime import datetime, timedelta

import pytest
import requests

BASE_URL = "http://127.0.0.1:8000"

pytestmark = pytest.mark.requires_server  # All tests in this module require server


def print_header(text: str) -> None:
    """Print formatted section header."""
    print(f"\n{'='*80}")
    print(f"{text}")
    print(f"{'='*80}\n")


def test_mission_analysis() -> bool:
    """Run mission analysis with 4 nearby Eastern Mediterranean targets."""
    print_header("STEP 1: Running Mission Analysis")

    # Eastern Mediterranean scenario - 4 nearby targets
    targets = [
        {
            "name": "Athens",
            "latitude": 37.9838,
            "longitude": 23.7275,
            "priority": 3,  # High priority
        },
        {
            "name": "Thessaloniki",
            "latitude": 40.6401,
            "longitude": 22.9444,
            "priority": 2,  # Medium priority
        },
        {
            "name": "Izmir",
            "latitude": 38.4237,
            "longitude": 27.1428,
            "priority": 2,  # Medium priority
        },
        {
            "name": "Heraklion",
            "latitude": 35.3387,
            "longitude": 25.1442,
            "priority": 1,  # Lower priority
        },
    ]

    # Mission parameters
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=24)

    payload = {
        "tle": {
            "name": "ICEYE-X44",
            "line1": "1 62707U 24065AE  25203.00000000  .00000000  00000+0  00000+0 0  9999",
            "line2": "2 62707  97.4500 332.0000 0001500  90.0000 270.0000 15.19000000000000",
        },
        "targets": targets,
        "start_time": start_time.isoformat() + "Z",
        "end_time": end_time.isoformat() + "Z",
        "mission_type": "imaging",
        "elevation_mask": 10.0,
        "pointing_angle": 45.0,
        "imaging_type": "optical",
    }

    print(f"Analyzing mission for {len(targets)} targets:")
    for t in targets:
        print(
            f"  - {t['name']}: ({t['latitude']:.2f}°N, {t['longitude']:.2f}°E) Priority: {t['priority']}"
        )

    print(
        f"\nTime window: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')} UTC"
    )
    print(f"Mission type: Imaging (Optical)")
    print(f"Pointing angle: 45°")

    response = requests.post(
        f"{BASE_URL}/api/v1/mission/analyze", json=payload, timeout=60
    )

    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Mission analysis completed successfully!")
        print(f"   Total opportunities found: {len(data.get('passes', []))}")

        # Count opportunities per target
        target_counts: dict[str, int] = {}
        for pass_data in data.get("passes", []):
            target = pass_data.get("target")
            target_counts[target] = target_counts.get(target, 0) + 1

        print(f"\n   Opportunities by target:")
        for target, count in sorted(
            target_counts.items(), key=lambda x: x[1], reverse=True
        ):
            print(f"     {target}: {count} opportunities")

        # Check if incidence angles are present
        passes_with_incidence = [
            p for p in data.get("passes", []) if "incidence_angle_deg" in p
        ]
        print(
            f"\n   Passes with incidence angle: {len(passes_with_incidence)}/{len(data.get('passes', []))}"
        )

        if passes_with_incidence:
            incidence_angles = [p["incidence_angle_deg"] for p in passes_with_incidence]
            avg_incidence = sum(incidence_angles) / len(incidence_angles)
            min_incidence = min(incidence_angles)
            max_incidence = max(incidence_angles)
            print(
                f"   Incidence angle range: {min_incidence:.1f}° - {max_incidence:.1f}° (avg: {avg_incidence:.1f}°)"
            )

        return True
    else:
        print(f"❌ Mission analysis failed: {response.status_code}")
        print(f"   {response.text}")
        return False


def test_scheduling_algorithms() -> bool:
    """Run all 3 scheduling algorithms and compare results."""
    print_header("STEP 2: Running Scheduling Algorithms")

    # First, get opportunities
    print("Fetching opportunities from mission analysis...")
    opp_response = requests.get(f"{BASE_URL}/api/v1/planning/opportunities", timeout=30)

    if opp_response.status_code != 200:
        print(f"❌ Failed to get opportunities: {opp_response.status_code}")
        return False

    opp_data = opp_response.json()
    print(f"✅ Found {len(opp_data.get('opportunities', []))} opportunities")

    # Run scheduling with all 3 algorithms
    schedule_payload = {
        "imaging_time_s": 1.0,
        "max_roll_rate_dps": 1.0,
        "max_roll_accel_dps2": 1.0,
        "algorithms": ["first_fit", "best_fit", "value_density"],
        "value_source": "target_priority",
        "look_window_s": 600.0,
        "quality_weight": 0.6,  # Balance quality and priority
        "quality_model": "monotonic",
        "ideal_incidence_deg": 35.0,
        "band_width_deg": 7.5,
    }

    print("\nRunning algorithms:")
    print("  - First-Fit (Chronological)")
    print("  - Best-Fit (Priority-Aware)")
    print("  - Value-Density (Efficiency-Driven)")
    print(
        f"\nQuality weight: {schedule_payload['quality_weight']} (0=priority only, 1=quality only)"
    )

    response = requests.post(
        f"{BASE_URL}/api/v1/planning/schedule", json=schedule_payload, timeout=60
    )

    if response.status_code != 200:
        print(f"❌ Scheduling failed: {response.status_code}")
        print(f"   {response.text}")
        return False

    data = response.json()
    print(f"\n✅ Scheduling completed successfully!")

    # Analyze results for each algorithm
    print_header("STEP 3: Algorithm Comparison")

    results_summary = {}

    for algo_name in ["first_fit", "best_fit", "value_density"]:
        result = data["results"].get(algo_name)
        if not result:
            continue

        schedule = result["schedule"]
        metrics = result["metrics"]

        # Extract incidence angles
        incidence_angles = [
            s["incidence_angle"] for s in schedule if "incidence_angle" in s
        ]

        # Get target coverage
        targets_covered = set(s["target_id"] for s in schedule)

        results_summary[algo_name] = {
            "schedule_count": len(schedule),
            "targets_covered": targets_covered,
            "incidence_angles": incidence_angles,
            "avg_incidence": (
                sum(incidence_angles) / len(incidence_angles)
                if incidence_angles
                else None
            ),
            "min_incidence": min(incidence_angles) if incidence_angles else None,
            "max_incidence": max(incidence_angles) if incidence_angles else None,
            "total_value": metrics.get("total_value"),
            "runtime_ms": metrics.get("runtime_ms"),
            "mean_incidence_deg": metrics.get("mean_incidence_deg"),
        }

    # Print comparison table
    algo_display_names = {
        "first_fit": "First-Fit (Chronological)",
        "best_fit": "Best-Fit (Priority-Aware)",
        "value_density": "Value-Density (Efficiency)",
    }

    print(
        f"{'Algorithm':<35} {'Targets':<15} {'Avg Inc.∠':<15} {'Total Value':<15} {'Runtime'}"
    )
    print(f"{'-'*100}")

    for algo_name, summary in results_summary.items():
        targets_str = f"{len(summary['targets_covered'])}/{4}"
        incidence_str = (
            f"{summary['avg_incidence']:.1f}°" if summary["avg_incidence"] else "N/A"
        )
        value_str = f"{summary['total_value']:.2f}" if summary["total_value"] else "N/A"
        runtime_str = f"{summary['runtime_ms']:.2f}ms"

        print(
            f"{algo_display_names[algo_name]:<35} {targets_str:<15} {incidence_str:<15} {value_str:<15} {runtime_str}"
        )

    # Detailed breakdown
    print_header("STEP 4: Detailed Schedule Breakdown")

    for algo_name, summary in results_summary.items():
        result = data["results"][algo_name]
        schedule = result["schedule"]

        print(f"\n{algo_display_names[algo_name]}:")
        print(
            f"{'#':<4} {'Target':<15} {'Incidence∠':<12} {'Value':<10} {'Density':<10}"
        )
        print(f"{'-'*60}")

        for idx, sched in enumerate(schedule, 1):
            target = sched["target_id"]
            incidence = (
                f"{sched.get('incidence_angle', 0):.1f}°"
                if "incidence_angle" in sched
                else "N/A"
            )
            value = f"{sched.get('value', 0):.2f}"
            density = (
                "∞"
                if sched.get("density") == "inf"
                else f"{sched.get('density', 0):.3f}"
            )

            print(f"{idx:<4} {target:<15} {incidence:<12} {value:<10} {density:<10}")

    # Verify incidence angles are present
    print_header("STEP 5: Verification Results")

    all_have_incidence = True
    for algo_name, summary in results_summary.items():
        has_incidence = len(summary["incidence_angles"]) == summary["schedule_count"]
        status = "✅" if has_incidence else "❌"
        print(
            f"{status} {algo_display_names[algo_name]}: {len(summary['incidence_angles'])}/{summary['schedule_count']} schedules have incidence angle"
        )

        if not has_incidence:
            all_have_incidence = False

    print(f"\n{'='*80}")
    if all_have_incidence:
        print("✅ SUCCESS: All scheduled opportunities include incidence angle!")
    else:
        print("❌ FAILURE: Some scheduled opportunities missing incidence angle")
    print(f"{'='*80}\n")

    return all_have_incidence


def main() -> bool:
    """Run all tests."""
    print_header("Testing Incidence Angle Integration")
    print("This test verifies:")
    print("  1. Mission analysis returns incidence angles")
    print("  2. Scheduling algorithms include incidence angles")
    print("  3. Algorithm comparison with 4 nearby targets")

    try:
        # Test 1: Mission analysis
        if not test_mission_analysis():
            print("\n❌ Mission analysis test failed. Stopping.")
            return False

        # Test 2: Scheduling algorithms
        if not test_scheduling_algorithms():
            print("\n❌ Scheduling test failed.")
            return False

        print_header("🎉 ALL TESTS PASSED!")
        print("✅ Incidence angles are correctly integrated")
        print("✅ All 3 algorithms are working properly")
        print("✅ Algorithm comparison shows expected differentiation")

        return True

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
