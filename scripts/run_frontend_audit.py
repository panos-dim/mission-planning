#!/usr/bin/env python3
"""
Run algorithm audit using the same input format as the frontend.

This validates algorithms with real mission data:
- 10 targets around Athens/Eastern Mediterranean
- ICEYE-X44 satellite
- 1 day, 2 days, and 7 days mission windows
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any


API_BASE_URL = "http://localhost:8000"
DEBUG_API = f"{API_BASE_URL}/api/v1/debug/planning"


def print_section(title: str):
    """Print section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_metrics(algo_name: str, metrics: Dict[str, Any]):
    """Print algorithm metrics."""
    print(f"Algorithm: {algo_name}")
    total_opps = metrics['total_opportunities']
    coverage_pct = 100*metrics['accepted']/total_opps if total_opps > 0 else 0.0
    print(f"  Coverage: {metrics['accepted']}/{total_opps} ({coverage_pct:.1f}%)")
    print(f"  Total Value: {metrics['total_value']:.2f}")
    print(f"  Mean Incidence: {metrics['mean_incidence_deg']:.1f}°")
    print(f"  Roll Usage: max={metrics['max_roll_deg']:.1f}°, total={metrics['total_roll_used_deg']:.1f}°")
    
    if metrics['opps_using_pitch'] > 0:
        print(f"  Pitch Usage: max={metrics['max_pitch_deg']:.1f}°, "
              f"total={metrics['total_pitch_used_deg']:.1f}°, opps={metrics['opps_using_pitch']}")
    
    print(f"  Utilization: {100*metrics['utilization']:.1f}%")
    print(f"  Runtime: {metrics['runtime_ms']:.1f}ms")
    print()


def print_invariants(invariants: list):
    """Print invariant checks."""
    all_ok = all(inv['ok'] for inv in invariants)
    
    if all_ok:
        print("  ✅ All invariants passed!")
    else:
        for inv in invariants:
            status = "✅" if inv['ok'] else "❌"
            print(f"  {status} {inv['name']}")
            if not inv['ok'] and inv['details']:
                for detail in inv['details'][:3]:
                    print(f"      {detail}")
    print()


def run_audit(days: int, compare_roll_pitch: bool = False):
    """Run audit for specified mission duration."""
    print_section(f"Mission Audit - {days} Day{'s' if days > 1 else ''}")
    
    # Frontend data format
    start_time = "2025-11-18T10:37:00Z"
    end_time_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00')) + timedelta(days=days)
    end_time = end_time_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # TLE data
    tle = {
        "id": "ICEYE-X44",
        "name": "ICEYE-X44",
        "tle_line1": "1 62707U 25009DC  25314.79215024  .00005593  00000+0  52657-3 0  9992",
        "tle_line2": "2 62707  97.7263  32.4188 0002390 115.7483 244.3984 14.94240684 67309",
    }
    
    # 10 targets around Athens
    targets = [
        {"name": "Athens", "latitude": 37.9838, "longitude": 23.7275, "priority": 5},
        {"name": "Istanbul", "latitude": 41.0082, "longitude": 28.9784, "priority": 4},
        {"name": "Thessaloniki", "latitude": 40.6401, "longitude": 22.9444, "priority": 3},
        {"name": "Izmir", "latitude": 38.4237, "longitude": 27.1428, "priority": 3},
        {"name": "Nicosia", "latitude": 35.1856, "longitude": 33.3823, "priority": 3},
        {"name": "Sofia", "latitude": 42.6977, "longitude": 23.3219, "priority": 2},
        {"name": "Rhodes", "latitude": 36.4341, "longitude": 28.2176, "priority": 2},
        {"name": "Antalya", "latitude": 36.8969, "longitude": 30.7133, "priority": 2},
        {"name": "Heraklion", "latitude": 35.3387, "longitude": 25.1442, "priority": 1},
        {"name": "Patras", "latitude": 38.2466, "longitude": 21.7346, "priority": 1},
    ]
    
    # Algorithm selection
    algorithms = ["first_fit", "best_fit", "optimal"]
    if compare_roll_pitch:
        algorithms.append("first_fit_roll_pitch")
    
    # Build request
    request_data = {
        "scenario_id": f"frontend_test_{days}d",
        "satellites": [tle],
        "targets": targets,
        "time_window": {
            "start": start_time,
            "end": end_time,
        },
        "mission_mode": "OPTICAL",
        "algorithms": algorithms,
        "planning_params": {
            "imaging_time_s": 5.0,
            "max_spacecraft_roll_deg": 45.0,
            "max_roll_rate_dps": 3.0,
            "max_roll_accel_dps2": 1.0,
            "max_spacecraft_pitch_deg": 30.0,
            "max_pitch_rate_dps": 1.0,
            "max_pitch_accel_dps2": 1.0,
            "quality_model": "off",
            "quality_weight": 0.5,
        }
    }
    
    print(f"Mission Window: {start_time} to {end_time} ({days} days)")
    print(f"Targets: {len(targets)}")
    print(f"Algorithms: {', '.join(algorithms)}")
    print()
    
    # Call API
    print("📡 Sending request to backend...")
    resp = requests.post(f"{DEBUG_API}/run_scenario", json=request_data)
    
    if resp.status_code != 200:
        print(f"❌ Request failed: {resp.status_code}")
        print(resp.text)
        return None
    
    results = resp.json()
    
    # Print results
    print_section("Results")
    print(f"Total Opportunities: {results['summary']['total_opportunities']}")
    print()
    
    for algo_name, algo_data in results['algorithms'].items():
        print_metrics(algo_name, algo_data['metrics'])
        print_invariants(algo_data['invariants'])
    
    # Print comparison if available
    if 'comparisons' in results and results['comparisons']:
        print_section("Roll vs Pitch Comparison")
        for comp_name, comp_data in results['comparisons'].items():
            print(f"Coverage Delta: {comp_data['delta_accepted']:+d} opportunities")
            print(f"Value Delta: {comp_data['delta_value']:+.2f}")
            print(f"Utilization Delta: {comp_data['delta_utilization']:+.3f}")
            print()
    
    return results


def main():
    # Check server
    try:
        resp = requests.get(API_BASE_URL, timeout=2)
        if resp.status_code != 200:
            print(f"❌ Server responded with {resp.status_code}")
            return 1
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend server")
        print("Please start: .venv/bin/python -m uvicorn backend.main:app --port 8000 --reload")
        return 1
    
    print("✅ Connected to backend server")
    
    # Run audits for different durations
    results = {}
    
    # 1 day
    results['1day'] = run_audit(days=1, compare_roll_pitch=False)
    
    # 2 days
    results['2days'] = run_audit(days=2, compare_roll_pitch=False)
    
    # 7 days (1 week) with roll+pitch comparison
    results['7days'] = run_audit(days=7, compare_roll_pitch=True)
    
    # Summary
    print_section("Overall Summary")
    
    for duration, result in results.items():
        if result:
            summary = result['summary']
            print(f"{duration}:")
            print(f"  Opportunities: {summary['total_opportunities']}")
            
            # Best algorithm
            best_algo = None
            best_accepted = 0
            for algo_name, algo_data in result['algorithms'].items():
                accepted = algo_data['metrics']['accepted']
                if accepted > best_accepted:
                    best_accepted = accepted
                    best_algo = algo_name
            
            print(f"  Best Algorithm: {best_algo} ({best_accepted} targets)")
            print()
    
    # Save results
    output_file = "frontend_audit_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"✅ Results saved to {output_file}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
