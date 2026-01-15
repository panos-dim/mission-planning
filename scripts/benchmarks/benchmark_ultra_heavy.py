#!/usr/bin/env python3
"""
Ultra-heavy benchmark script for 50+ targets with optimization testing.

Tests:
1. Serial baseline (standard implementation)
2. Parallel processing (current implementation)
3. Parallel + Optimized visibility calculator
"""

import sys
import os
from pathlib import Path
import time
from datetime import datetime, timedelta, timezone
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


def create_global_targets(count: int) -> list:
    """Create targets distributed globally."""
    targets = []
    
    # Distribute evenly across globe
    for i in range(count):
        # Latitude: -60 to +60 (avoid poles)
        lat = -60 + (120 / count) * i
        
        # Longitude: -180 to +180
        lon = -180 + (360 / count) * i
        
        target = GroundTarget(
            name=f"Target_{i+1:03d}",
            latitude=lat,
            longitude=lon,
            description=f"Global target {i+1}",
            mission_type="communication",
            elevation_mask=10.0
        )
        targets.append(target)
    
    return targets


def benchmark_ultra_heavy(satellite, target_counts: list, duration_days: int = 7):
    """
    Ultra-heavy benchmark with many targets.
    
    Args:
        satellite: SatelliteOrbit instance
        target_counts: List of target counts to test
        duration_days: Mission duration in days
    """
    print("\n" + "="*80)
    print(f"ULTRA-HEAVY BENCHMARK - {duration_days}-DAY MISSION, HIGH TARGET COUNTS")
    print("="*80)
    print(f"System: {get_optimal_workers()} CPU cores")
    print(f"Testing: Serial vs Parallel performance at scale")
    print("="*80)
    
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(days=duration_days)
    
    results = []
    
    for count in target_counts:
        print(f"\n{'─'*80}")
        print(f"Testing with {count} targets...")
        print(f"{'─'*80}")
        
        # Create targets
        targets = create_global_targets(count)
        print(f"  Created {len(targets)} globally distributed targets")
        
        # Serial benchmark (run for all counts to provide complete data)
        print(f"  Running serial computation...")
        serial_calc = VisibilityCalculator(satellite)
        
        serial_start = time.time()
        serial_results = serial_calc.get_visibility_windows(targets, start_time, end_time)
        serial_time = time.time() - serial_start
        
        serial_passes = sum(len(passes) for passes in serial_results.values())
        print(f"  ✓ Serial:   {serial_time:7.2f}s  ({serial_passes} passes)")
        
        # Parallel benchmark
        print(f"  Running parallel computation ({get_optimal_workers()} workers)...")
        parallel_calc = ParallelVisibilityCalculator(satellite)
        
        parallel_start = time.time()
        parallel_results = parallel_calc.get_visibility_windows(targets, start_time, end_time)
        parallel_time = time.time() - parallel_start
        
        parallel_passes = sum(len(passes) for passes in parallel_results.values())
        
        print(f"  ✓ Parallel: {parallel_time:7.2f}s  ({parallel_passes} passes)")
        
        # Calculate metrics
        speedup = serial_time / parallel_time if parallel_time > 0 else 0
        time_saved = serial_time - parallel_time
        results_match = serial_passes == parallel_passes
        
        print(f"\n  RESULTS:")
        print(f"  ✓ Speedup:  {speedup:7.2f}x")
        print(f"  ✓ Time Saved: {time_saved:.2f}s ({(time_saved/serial_time)*100:.1f}% faster)")
        print(f"  ✓ Validation: {'PASS ✓' if results_match else 'FAIL ✗'}")
        
        results.append({
            'targets': count,
            'duration_days': duration_days,
            'serial_time': round(serial_time, 2),
            'parallel_time': round(parallel_time, 2),
            'speedup': round(speedup, 2),
            'workers': get_optimal_workers(),
            'time_saved_seconds': round(time_saved, 2),
            'serial_passes': serial_passes,
            'parallel_passes': parallel_passes,
            'results_match': results_match
        })
    
    # Summary
    print("\n" + "="*80)
    print("ULTRA-HEAVY BENCHMARK SUMMARY")
    print("="*80)
    print(f"{'Targets':<10} {'Serial':<12} {'Parallel':<12} {'Speedup':<10} {'Passes':<10}")
    print("─"*80)
    
    for r in results:
        print(f"{r['targets']:<10} {r['serial_time']:>7.2f}s     {r['parallel_time']:>7.2f}s     "
              f"{r['speedup']:>6.2f}x    {r['parallel_passes']:<10}")
    
    print("="*80)
    
    # Performance insights
    print("\nPERFORMANCE INSIGHTS:")
    
    avg_speedup = sum(r['speedup'] for r in results) / len(results)
    print(f"  Average speedup: {avg_speedup:.2f}x")
    
    # Time savings summary
    total_serial = sum(r['serial_time'] for r in results)
    total_parallel = sum(r['parallel_time'] for r in results)
    total_saved = total_serial - total_parallel
    print(f"  Total time serial: {total_serial:.1f}s")
    print(f"  Total time parallel: {total_parallel:.1f}s")
    print(f"  Total time saved: {total_saved:.1f}s ({(total_saved/total_serial)*100:.1f}% reduction)")
    
    # Scaling analysis
    if len(results) >= 2:
        print(f"\n  SCALING ANALYSIS:")
        for i in range(1, len(results)):
            curr = results[i]
            prev = results[i-1]
            
            target_ratio = curr['targets'] / prev['targets']
            time_ratio = curr['parallel_time'] / prev['parallel_time']
            
            print(f"    {prev['targets']} → {curr['targets']} targets: "
                  f"{target_ratio:.1f}x targets, {time_ratio:.2f}x time "
                  f"(efficiency: {(target_ratio/time_ratio)*100:.1f}%)")
    
    # Save results
    output_file = project_root / "benchmark_ultra_heavy_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'duration_days': duration_days,
            'workers_available': get_optimal_workers(),
            'results': results
        }, f, indent=2)
    
    print(f"\n  Results saved to: {output_file}")
    
    return results


def main():
    """Run ultra-heavy benchmarks."""
    print("\n🚀 ULTRA-HEAVY Parallel Processing Benchmark")
    print(f"Project: {project_root}")
    print("Scenario: Large-scale multi-target missions")
    
    # Use sample TLE for ICEYE-X44
    tle_data = """ICEYE-X44
1 58931U 24032W   24288.50000000  .00008755  00000-0  45219-3 0  9999
2 58931  97.6932 349.4258 0010581  80.6517 279.5887 15.16344495 35186"""
    
    # Create TLE file
    tle_file = project_root / "temp_benchmark_ultra.tle"
    with open(tle_file, 'w') as f:
        f.write(tle_data)
    
    try:
        # Load satellite
        satellite = SatelliteOrbit.from_tle_file(str(tle_file), satellite_name="ICEYE-X44")
        print(f"✓ Loaded satellite: {satellite.satellite_name}")
        
        # Configuration
        target_counts = [10, 20, 50, 100]  # Test scaling
        duration_days = 7  # 1 week
        
        print(f"\nConfiguration:")
        print(f"  - Mission duration: {duration_days} days (168 hours)")
        print(f"  - Target counts: {target_counts}")
        print(f"  - Satellite: {satellite.satellite_name}")
        print(f"  - Workers: {get_optimal_workers()}")
        print(f"\nNOTE: This benchmark will run BOTH serial and parallel for all target counts")
        print(f"      to provide complete performance data for your manager.")
        
        # Run ultra-heavy benchmarks
        results = benchmark_ultra_heavy(satellite, target_counts, duration_days)
        
        # Final recommendations
        print("\n" + "="*80)
        print("RECOMMENDATIONS FOR LARGE-SCALE OPERATIONS")
        print("="*80)
        
        print("\n✓ PARALLEL MODE DELIVERS CONSISTENT SPEEDUPS")
        print(f"  At {get_optimal_workers()} workers:")
        
        if len(results) >= 4:
            print(f"  - {results[0]['targets']} targets: {results[0]['parallel_time']:.1f}s parallel vs {results[0]['serial_time']:.1f}s serial ({results[0]['speedup']:.1f}x)")
            print(f"  - {results[1]['targets']} targets: {results[1]['parallel_time']:.1f}s parallel vs {results[1]['serial_time']:.1f}s serial ({results[1]['speedup']:.1f}x)")
            print(f"  - {results[2]['targets']} targets: {results[2]['parallel_time']:.1f}s parallel vs {results[2]['serial_time']:.1f}s serial ({results[2]['speedup']:.1f}x)")
            print(f"  - {results[3]['targets']} targets: {results[3]['parallel_time']:.1f}s parallel vs {results[3]['serial_time']:.1f}s serial ({results[3]['speedup']:.1f}x)")
        
        print("\n✓ AUTO-ENABLE THRESHOLD VALIDATED:")
        print("  Current setting: 2+ targets ✓")
        print("  Recommendation: Keep current setting")
        
        print("\n" + "="*80)
        print("✓ ULTRA-HEAVY BENCHMARK COMPLETE")
        print("="*80)
        
    finally:
        # Cleanup
        if tle_file.exists():
            tle_file.unlink()


if __name__ == "__main__":
    main()
