#!/usr/bin/env python3
"""
Heavy benchmark script for 1-week mission durations.

Tests realistic operational scenarios matching user requirements:
- 1 satellite
- 2-3 targets
- 1 week (168 hours) analysis duration
"""

import sys
import os
from pathlib import Path
import time
from datetime import datetime, timedelta
import json

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from mission_planner.orbit import SatelliteOrbit
from mission_planner.targets import GroundTarget
from mission_planner.visibility import VisibilityCalculator
from mission_planner.parallel import ParallelVisibilityCalculator, get_optimal_workers
from mission_planner.utils import setup_logging

# Setup logging
setup_logging()
import logging
logger = logging.getLogger(__name__)


def create_test_targets(count: int) -> list:
    """Create test targets (UAE region for realism)."""
    # Real locations in UAE region
    locations = [
        ("Dubai", 25.2048, 55.2708),
        ("Abu Dhabi", 24.4539, 54.3773),
        ("Sharjah", 25.3573, 55.4033),
        ("Al Ain", 24.2075, 55.7447),
        ("Fujairah", 25.1288, 56.3265),
    ]
    
    targets = []
    for i in range(min(count, len(locations))):
        name, lat, lon = locations[i]
        target = GroundTarget(
            name=name,
            latitude=lat,
            longitude=lon,
            description=f"UAE target {i+1}",
            mission_type="communication",
            elevation_mask=10.0
        )
        targets.append(target)
    
    return targets


def benchmark_heavy(satellite, target_counts: list, duration_days: int = 7):
    """
    Heavy benchmark with 1-week mission duration.
    
    Args:
        satellite: SatelliteOrbit instance
        target_counts: List of target counts to test
        duration_days: Mission duration in days (default 7)
    """
    print("\n" + "="*80)
    print(f"HEAVY BENCHMARK - {duration_days}-DAY MISSION DURATION")
    print("="*80)
    print(f"Scenario: 1 satellite, multiple targets, {duration_days*24} hours analysis")
    print(f"Workers available: {get_optimal_workers()}")
    print("="*80)
    
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(days=duration_days)
    duration_hours = duration_days * 24
    
    results = []
    
    for count in target_counts:
        print(f"\n{'─'*80}")
        print(f"Testing with {count} target(s) - {duration_days} days...")
        print(f"{'─'*80}")
        
        # Create targets
        targets = create_test_targets(count)
        
        # Serial benchmark
        print(f"  Running serial computation...")
        serial_calc = VisibilityCalculator(satellite)
        
        serial_start = time.time()
        serial_results = serial_calc.get_visibility_windows(targets, start_time, end_time)
        serial_time = time.time() - serial_start
        
        serial_passes = sum(len(passes) for passes in serial_results.values())
        
        print(f"  ✓ Serial:   {serial_time:7.2f}s  ({serial_passes} passes)")
        
        # Parallel benchmark with different worker counts
        worker_configs = [
            get_optimal_workers(),  # Default (CPU-1)
            get_optimal_workers() + 1,  # All CPUs
        ]
        
        best_parallel_time = float('inf')
        best_workers = 0
        best_parallel_passes = 0
        
        for workers in worker_configs:
            print(f"  Running parallel ({workers} workers)...")
            parallel_calc = ParallelVisibilityCalculator(satellite, max_workers=workers)
            
            parallel_start = time.time()
            parallel_results = parallel_calc.get_visibility_windows(targets, start_time, end_time)
            parallel_time = time.time() - parallel_start
            
            parallel_passes = sum(len(passes) for passes in parallel_results.values())
            
            speedup = serial_time / parallel_time if parallel_time > 0 else 0
            print(f"    {workers} workers: {parallel_time:7.2f}s  (speedup: {speedup:.2f}x)")
            
            if parallel_time < best_parallel_time:
                best_parallel_time = parallel_time
                best_workers = workers
                best_parallel_passes = parallel_passes
        
        # Calculate metrics with best configuration
        speedup = serial_time / best_parallel_time if best_parallel_time > 0 else 0
        efficiency = (speedup / best_workers) * 100 if best_workers > 0 else 0
        time_saved = serial_time - best_parallel_time
        
        print(f"\n  BEST RESULT:")
        print(f"  ✓ Workers:  {best_workers}")
        print(f"  ✓ Parallel: {best_parallel_time:7.2f}s  ({best_parallel_passes} passes)")
        print(f"  ✓ Speedup:  {speedup:7.2f}x  (Efficiency: {efficiency:.1f}%)")
        print(f"  ✓ Time Saved: {time_saved:.2f}s ({(time_saved/serial_time)*100:.1f}% faster)")
        
        # Validate results match
        results_match = serial_passes == best_parallel_passes
        print(f"  ✓ Validation: {'PASS ✓' if results_match else 'FAIL ✗'} (passes match: {results_match})")
        
        results.append({
            'targets': count,
            'duration_days': duration_days,
            'serial_time': round(serial_time, 2),
            'parallel_time': round(best_parallel_time, 2),
            'speedup': round(speedup, 2),
            'efficiency_percent': round(efficiency, 1),
            'workers': best_workers,
            'time_saved_seconds': round(time_saved, 2),
            'percent_faster': round((time_saved/serial_time)*100, 1),
            'serial_passes': serial_passes,
            'parallel_passes': best_parallel_passes,
            'results_match': results_match
        })
    
    # Summary
    print("\n" + "="*80)
    print("HEAVY BENCHMARK SUMMARY")
    print("="*80)
    print(f"{'Targets':<10} {'Serial':<12} {'Parallel':<12} {'Speedup':<10} {'Saved':<12} {'Match':<8}")
    print("─"*80)
    
    for r in results:
        match_symbol = '✓' if r['results_match'] else '✗'
        print(f"{r['targets']:<10} {r['serial_time']:>7.2f}s     {r['parallel_time']:>7.2f}s     "
              f"{r['speedup']:>6.2f}x    {r['time_saved_seconds']:>7.2f}s     {match_symbol}")
    
    print("="*80)
    
    # Performance insights
    print("\nPERFORMANCE INSIGHTS:")
    avg_speedup = sum(r['speedup'] for r in results) / len(results)
    avg_saved = sum(r['time_saved_seconds'] for r in results) / len(results)
    
    print(f"  Average speedup: {avg_speedup:.2f}x")
    print(f"  Average time saved: {avg_saved:.2f}s per mission")
    print(f"  Mission duration: {duration_days} days ({duration_hours} hours)")
    
    # Find best case
    best = max(results, key=lambda x: x['speedup'])
    print(f"\n  BEST CASE ({best['targets']} targets):")
    print(f"    Before: {best['serial_time']:.2f}s")
    print(f"    After:  {best['parallel_time']:.2f}s")
    print(f"    Speedup: {best['speedup']:.2f}x ({best['percent_faster']:.1f}% faster)")
    print(f"    Time saved: {best['time_saved_seconds']:.2f}s")
    
    # Save results
    output_file = project_root / "benchmark_heavy_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.utcnow().isoformat(),
            'duration_days': duration_days,
            'duration_hours': duration_hours,
            'workers_available': get_optimal_workers(),
            'results': results
        }, f, indent=2)
    
    print(f"\n  Results saved to: {output_file}")
    
    return results


def main():
    """Run heavy benchmarks."""
    print("\n🚀 HEAVY Parallel Processing Benchmark")
    print(f"Project: {project_root}")
    print("Scenario: Realistic operational missions (1 week duration)")
    
    # Use sample TLE for ICEYE-X44
    tle_data = """ICEYE-X44
1 58931U 24032W   24288.50000000  .00008755  00000-0  45219-3 0  9999
2 58931  97.6932 349.4258 0010581  80.6517 279.5887 15.16344495 35186"""
    
    # Create TLE file
    tle_file = project_root / "temp_benchmark_heavy.tle"
    with open(tle_file, 'w') as f:
        f.write(tle_data)
    
    try:
        # Load satellite
        satellite = SatelliteOrbit.from_tle_file(str(tle_file), satellite_name="ICEYE-X44")
        print(f"✓ Loaded satellite: {satellite.satellite_name}")
        
        # Configuration
        target_counts = [1, 2, 3, 5]  # Test 1-5 targets (realistic scenarios)
        duration_days = 7  # 1 week
        
        print(f"\nConfiguration:")
        print(f"  - Mission duration: {duration_days} days (168 hours)")
        print(f"  - Target counts: {target_counts}")
        print(f"  - Satellite: {satellite.satellite_name}")
        print(f"  - CPU cores: {get_optimal_workers()} (optimal), {get_optimal_workers()+1} (all cores)")
        
        # Run heavy benchmarks
        results = benchmark_heavy(satellite, target_counts, duration_days)
        
        # Recommendations
        print("\n" + "="*80)
        print("RECOMMENDATIONS")
        print("="*80)
        
        if len(results) > 0:
            avg_speedup = sum(r['speedup'] for r in results) / len(results)
            
            if avg_speedup >= 2.0:
                print("\n✓ EXCELLENT parallel performance!")
                print(f"  Average speedup: {avg_speedup:.2f}x")
                print("  Parallel mode is ALWAYS beneficial.")
                print("  ✓ Auto-enable by default: RECOMMENDED")
            elif avg_speedup >= 1.5:
                print("\n✓ GOOD parallel performance.")
                print(f"  Average speedup: {avg_speedup:.2f}x")
                print("  Parallel mode provides measurable benefit.")
                print("  ✓ Auto-enable by default: RECOMMENDED")
            else:
                print("\n⚠ MODERATE parallel performance.")
                print(f"  Average speedup: {avg_speedup:.2f}x")
                print("  Parallel mode has some overhead for small missions.")
                print("  ⚠ Consider auto-enable only for 2+ targets")
        
        print("\n" + "="*80)
        print("✓ BENCHMARK COMPLETE")
        print("="*80)
        
    finally:
        # Cleanup
        if tle_file.exists():
            tle_file.unlink()


if __name__ == "__main__":
    main()
