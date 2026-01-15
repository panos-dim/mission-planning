#!/usr/bin/env python3
"""
CLI tool for running mission planning audits and benchmarks.

Usage:
    # Run a single preset scenario
    python scripts/run_planning_audit.py --preset simple_two_targets
    
    # Run benchmark across all presets
    python scripts/run_planning_audit.py --benchmark --all-presets
    
    # Run custom scenario
    python scripts/run_planning_audit.py --custom --targets 5 --duration 12
    
    # Compare roll-only vs roll+pitch
    python scripts/run_planning_audit.py --preset tight_timing_three_targets --compare-roll-pitch
"""

import argparse
import json
import sys
import requests
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

# API configuration
API_BASE_URL = "http://localhost:8000"
DEBUG_API = f"{API_BASE_URL}/api/v1/debug/planning"


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_metrics(algo_name: str, metrics: Dict[str, Any]):
    """Print algorithm metrics in a readable format."""
    print(f"Algorithm: {algo_name}")
    total_opps = metrics['total_opportunities']
    coverage_pct = 100*metrics['accepted']/total_opps if total_opps > 0 else 0.0
    print(f"  Coverage: {metrics['accepted']}/{total_opps} ({coverage_pct:.1f}%)")
    print(f"  Total Value: {metrics['total_value']:.2f}")
    print(f"  Mean Incidence: {metrics['mean_incidence_deg']:.1f}°")
    print(f"  Roll Usage: max={metrics['max_roll_deg']:.1f}°, "
          f"total={metrics['total_roll_used_deg']:.1f}°")
    if metrics['opps_using_pitch'] > 0:
        print(f"  Pitch Usage: max={metrics['max_pitch_deg']:.1f}°, "
              f"total={metrics['total_pitch_used_deg']:.1f}°, "
              f"opps={metrics['opps_using_pitch']}")
    print(f"  Utilization: {100*metrics['utilization']:.1f}%")
    print(f"  Runtime: {metrics['runtime_ms']:.1f}ms")
    print()


def print_invariants(invariants: list):
    """Print invariant check results."""
    print("Invariant Checks:")
    all_ok = all(inv['ok'] for inv in invariants)
    
    if all_ok:
        print("  ✅ All invariants passed!")
    else:
        for inv in invariants:
            status = "✅" if inv['ok'] else "❌"
            print(f"  {status} {inv['name']}")
            if not inv['ok'] and inv['details']:
                print(f"      {inv['details']}")
    print()


def print_comparison(comparison: Dict[str, Any]):
    """Print roll vs pitch comparison."""
    print_section("Roll-Only vs Roll+Pitch Comparison")
    
    print(f"Coverage Delta: {comparison['delta_accepted']:+d} opportunities")
    print(f"Value Delta: {comparison['delta_value']:+.2f}")
    print(f"Utilization Delta: {comparison['delta_utilization']:+.3f}")
    print()
    
    if comparison['regressions']:
        print("Regressions:")
        for reg in comparison['regressions']:
            status = "✅" if reg['ok'] else "❌"
            print(f"  {status} {reg['type']}: {reg['details']}")
        print()
    
    if comparison['improvements']:
        print("Improvements:")
        for imp in comparison['improvements']:
            print(f"  ✅ {imp['type']}: {imp['details']}")
        print()


def run_preset_scenario(preset_id: str, compare_roll_pitch: bool = False) -> Dict[str, Any]:
    """Run a preset scenario."""
    print_section(f"Running Preset Scenario: {preset_id}")
    
    # Get ICEYE-X44 TLE
    tle = {
        "id": "ICEYE-X44",
        "name": "ICEYE-X44",
        "tle_line1": "1 48915U 21059L   25226.50000000  .00001234  00000-0  12345-3 0  9990",
        "tle_line2": "2 48915  97.6900 234.5678 0001234  89.0123 271.1234 15.19012345123456",
    }
    
    # Build request from preset
    if preset_id == "simple_two_targets":
        targets = [
            {"name": "Target 1", "latitude": 40.0, "longitude": 20.0, "priority": 1},
            {"name": "Target 2", "latitude": 41.0, "longitude": 21.0, "priority": 1},
        ]
        time_window = {"start": "2025-10-13T00:00:00Z", "end": "2025-10-13T12:00:00Z"}
    
    elif preset_id == "tight_timing_three_targets":
        targets = [
            {"name": "Target A", "latitude": 35.0, "longitude": 10.0, "priority": 1},
            {"name": "Target B", "latitude": 35.5, "longitude": 11.0, "priority": 1},
            {"name": "Target C", "latitude": 36.0, "longitude": 12.0, "priority": 1},
        ]
        time_window = {"start": "2025-10-13T06:00:00Z", "end": "2025-10-13T18:00:00Z"}
    
    else:
        # Fetch from API
        resp = requests.get(f"{DEBUG_API}/presets")
        if resp.status_code != 200:
            print(f"❌ Failed to fetch presets: {resp.status_code}")
            return {}
        
        presets = resp.json()
        if preset_id not in presets['presets']:
            print(f"❌ Unknown preset: {preset_id}")
            print(f"Available: {', '.join(presets['presets'])}")
            return {}
        
        # Use benchmark API to generate the scenario
        benchmark_req = {
            "presets": [preset_id],
            "algorithms": ["first_fit", "first_fit_roll_pitch"] if compare_roll_pitch else ["first_fit"],
        }
        
        resp = requests.post(f"{DEBUG_API}/benchmark", json=benchmark_req)
        if resp.status_code != 200:
            print(f"❌ Benchmark failed: {resp.status_code}")
            return {}
        
        return resp.json()
    
    # Build request
    algorithms = ["first_fit", "best_fit", "optimal", "first_fit_roll_pitch"] if compare_roll_pitch else ["first_fit", "best_fit"]
    
    request_data = {
        "scenario_id": preset_id,
        "satellites": [tle],
        "targets": targets,
        "time_window": time_window,
        "mission_mode": "OPTICAL",
        "algorithms": algorithms,
    }
    
    # Call API
    resp = requests.post(f"{DEBUG_API}/run_scenario", json=request_data)
    
    if resp.status_code != 200:
        print(f"❌ Request failed: {resp.status_code}")
        print(resp.text)
        return {}
    
    return resp.json()


def run_benchmark(presets: list, num_random: int = 0) -> Dict[str, Any]:
    """Run benchmark across multiple scenarios."""
    print_section("Running Benchmark")
    
    print(f"Presets: {', '.join(presets) if presets else 'None'}")
    print(f"Random scenarios: {num_random}")
    print()
    
    request_data = {
        "presets": presets,
        "num_random_scenarios": num_random,
        "algorithms": ["first_fit", "best_fit", "optimal", "first_fit_roll_pitch"],
    }
    
    resp = requests.post(f"{DEBUG_API}/benchmark", json=request_data)
    
    if resp.status_code != 200:
        print(f"❌ Benchmark failed: {resp.status_code}")
        print(resp.text)
        return {}
    
    return resp.json()


def main():
    parser = argparse.ArgumentParser(
        description="Mission Planning Audit CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run single preset
  python scripts/run_planning_audit.py --preset simple_two_targets
  
  # Compare roll vs pitch
  python scripts/run_planning_audit.py --preset tight_timing_three_targets --compare-roll-pitch
  
  # Run benchmark
  python scripts/run_planning_audit.py --benchmark --all-presets
  
  # Save results to file
  python scripts/run_planning_audit.py --preset simple_two_targets --output results.json
        """
    )
    
    # Scenario selection
    parser.add_argument("--preset", type=str, help="Run a preset scenario")
    parser.add_argument("--benchmark", action="store_true", help="Run benchmark mode")
    parser.add_argument("--all-presets", action="store_true", help="Include all preset scenarios in benchmark")
    parser.add_argument("--random", type=int, default=0, help="Number of random scenarios to generate")
    
    # Options
    parser.add_argument("--compare-roll-pitch", action="store_true", 
                       help="Compare roll-only vs roll+pitch algorithms")
    parser.add_argument("--output", "-o", type=str, help="Save results to JSON file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Check server is running
    try:
        resp = requests.get(API_BASE_URL, timeout=2)
        if resp.status_code != 200:
            print(f"❌ Server responded with {resp.status_code}")
            print("Make sure backend server is running on localhost:8000")
            return 1
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend server")
        print("Please start the server with: ./run_dev.sh")
        return 1
    
    print("✅ Connected to backend server")
    
    # Execute requested operation
    results = {}
    
    if args.preset:
        results = run_preset_scenario(args.preset, args.compare_roll_pitch)
        
        if results:
            # Print results
            print_section("Results")
            print(f"Scenario: {results['scenario_id']}")
            print(f"Total Opportunities: {results['summary']['total_opportunities']}")
            print()
            
            for algo_name, algo_data in results['algorithms'].items():
                print_metrics(algo_name, algo_data['metrics'])
                print_invariants(algo_data['invariants'])
            
            # Print comparison if available
            if 'comparisons' in results and results['comparisons']:
                for comp_name, comp_data in results['comparisons'].items():
                    print_comparison(comp_data)
    
    elif args.benchmark:
        # Get presets
        presets = []
        if args.all_presets:
            resp = requests.get(f"{DEBUG_API}/presets")
            if resp.status_code == 200:
                presets = resp.json()['presets']
        
        results = run_benchmark(presets, args.random)
        
        if results:
            # Print summary
            print_section("Benchmark Summary")
            print(f"Total Scenarios: {results['summary']['total_scenarios']}")
            print(f"Successful: {results['summary']['successful_scenarios']}")
            print(f"Failed: {results['summary']['failed_scenarios']}")
            print()
            
            # Print aggregated metrics
            print_section("Aggregated Metrics")
            for algo_name, metrics in results['aggregated_metrics'].items():
                print(f"{algo_name}:")
                print(f"  Mean Accepted: {metrics['mean_accepted']:.1f}")
                print(f"  Median Accepted: {metrics['median_accepted']}")
                print(f"  Mean Value: {metrics['mean_total_value']:.2f}")
                print(f"  Mean Utilization: {100*metrics['mean_utilization']:.1f}%")
                print(f"  Mean Runtime: {metrics['mean_runtime_ms']:.1f}ms")
                if metrics['max_pitch_deg'] > 0:
                    print(f"  Max Pitch Used: {metrics['max_pitch_deg']:.1f}°")
                print()
    
    else:
        parser.print_help()
        return 1
    
    # Save to file if requested
    if args.output and results:
        output_path = Path(args.output)
        output_path.write_text(json.dumps(results, indent=2))
        print(f"\n✅ Results saved to {output_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
