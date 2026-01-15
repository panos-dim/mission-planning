#!/usr/bin/env python3
"""
Benchmark script to test Location and Position caching optimizations.

Compares:
1. Serial with all caching (ground + location + position)
2. Parallel with all caching
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


def create_test_targets(count: int) -> list:
    """Create targets distributed globally."""
    targets = []
    
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


def benchmark_caching(satellite, target_counts: list, duration_days: int = 7):
    """
    Benchmark with all caching optimizations.
    
    Args:
        satellite: SatelliteOrbit instance
        target_counts: List of target counts to test
        duration_days: Mission duration in days
    """
    print("\n" + "="*80)
    print(f"CACHING OPTIMIZATION BENCHMARK - {duration_days}-DAY MISSIONS")
    print("="*80)
    print(f"Testing: Ground + Location + Position Caching")
    print(f"System: {get_optimal_workers()} CPU cores")
    print("="*80)
    
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(days=duration_days)
    
    all_results = []
    
    for count in target_counts:
        print(f"\n{'─'*80}")
        print(f"Testing with {count} targets...")
        print(f"{'─'*80}")
        
        # Create targets
        targets = create_test_targets(count)
        print(f"  Created {len(targets)} globally distributed targets")
        
        result = {
            'targets': count,
            'duration_days': duration_days
        }
        
        # Test 1: Serial with all caching
        print(f"\n  [1/2] Serial (Ground + Location + Position caching)...")
        serial_calc = VisibilityCalculator(satellite)
        
        serial_start = time.time()
        serial_results = serial_calc.get_visibility_windows(targets, start_time, end_time)
        serial_time = time.time() - serial_start
        
        serial_passes = sum(len(passes) for passes in serial_results.values())
        
        # Report cache stats
        location_cache_size = len(serial_calc._location_cache)
        position_cache_size = len(serial_calc._sat_position_cache)
        ground_cache_size = len(serial_calc._ground_ecef_cache)
        
        print(f"        Time: {serial_time:7.2f}s  ({serial_passes} passes)")
        print(f"        Cache sizes: Location={location_cache_size}, Position={position_cache_size}, Ground={ground_cache_size}")
        
        result['serial_time'] = round(serial_time, 2)
        result['serial_passes'] = serial_passes
        result['location_cache_size'] = location_cache_size
        result['position_cache_size'] = position_cache_size
        result['ground_cache_size'] = ground_cache_size
        
        # Test 2: Parallel with all caching
        print(f"  [2/2] Parallel (Ground + Location + Position caching, {get_optimal_workers()} workers)...")
        parallel_calc = ParallelVisibilityCalculator(satellite)
        
        parallel_start = time.time()
        parallel_results = parallel_calc.get_visibility_windows(targets, start_time, end_time)
        parallel_time = time.time() - parallel_start
        
        parallel_passes = sum(len(passes) for passes in parallel_results.values())
        parallel_speedup = serial_time / parallel_time if parallel_time > 0 else 0
        
        print(f"        Time: {parallel_time:7.2f}s  ({parallel_passes} passes, {parallel_speedup:.2f}x speedup)")
        
        result['parallel_time'] = round(parallel_time, 2)
        result['parallel_passes'] = parallel_passes
        result['parallel_speedup'] = round(parallel_speedup, 2)
        
        # Validation
        results_match = (serial_passes == parallel_passes)
        result['validation'] = results_match
        
        print(f"\n  VALIDATION: {'✓ PASS' if results_match else '✗ FAIL'}")
        print(f"    Serial: {serial_passes}, Parallel: {parallel_passes}")
        
        # Summary
        time_saved = serial_time - parallel_time
        print(f"\n  SUMMARY:")
        print(f"    Serial:   {serial_time:7.2f}s  (baseline)")
        print(f"    Parallel: {parallel_time:7.2f}s  ({parallel_speedup:.2f}x faster)")
        print(f"    Time saved: {time_saved:.2f}s ({(time_saved/serial_time)*100:.1f}%)")
        
        all_results.append(result)
    
    # Final Summary
    print("\n" + "="*80)
    print("CACHING BENCHMARK SUMMARY")
    print("="*80)
    print(f"{'Targets':<10} {'Serial':<12} {'Parallel':<12} {'Speedup':<12} {'Passes':<10}")
    print("─"*80)
    
    for r in all_results:
        print(f"{r['targets']:<10} {r['serial_time']:>7.2f}s     "
              f"{r['parallel_time']:>7.2f}s     {r['parallel_speedup']:>6.2f}x    "
              f"{r['parallel_passes']:<10}")
    
    print("="*80)
    
    # Performance Analysis
    print("\nPERFORMANCE ANALYSIS:")
    
    avg_parallel_speedup = sum(r['parallel_speedup'] for r in all_results) / len(all_results)
    
    print(f"\n  Optimizations Active:")
    print(f"    ✓ Ground coordinate caching")
    print(f"    ✓ Location object caching")
    print(f"    ✓ Satellite position caching")
    
    print(f"\n  Parallel Processing:")
    print(f"    Average speedup: {avg_parallel_speedup:.2f}x")
    print(f"    Workers: {get_optimal_workers()}")
    
    # Cache efficiency
    print(f"\n  Cache Efficiency:")
    for r in all_results:
        if 'position_cache_size' in r:
            total_calcs = r['serial_time'] * 1000  # Rough estimate
            cache_hit_rate = (1 - r['position_cache_size'] / total_calcs) * 100 if total_calcs > 0 else 0
            print(f"    {r['targets']} targets: Position cache={r['position_cache_size']} entries")
    
    # Save results
    output_file = project_root / "benchmark_caching_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'duration_days': duration_days,
            'workers': get_optimal_workers(),
            'optimizations': [
                'Ground coordinate caching',
                'Location object caching',
                'Satellite position caching',
                'Parallel processing'
            ],
            'results': all_results
        }, f, indent=2)
    
    print(f"\n  Results saved to: {output_file}")
    
    return all_results


def main():
    """Run caching benchmarks."""
    print("\n🚀 Caching Optimization Benchmark")
    print(f"Project: {project_root}")
    print("Testing: Location + Position caching improvements")
    
    # Use sample TLE for ICEYE-X44
    tle_data = """ICEYE-X44
1 58931U 24032W   24288.50000000  .00008755  00000-0  45219-3 0  9999
2 58931  97.6932 349.4258 0010581  80.6517 279.5887 15.16344495 35186"""
    
    # Create TLE file
    tle_file = project_root / "temp_benchmark_cache.tle"
    with open(tle_file, 'w') as f:
        f.write(tle_data)
    
    try:
        # Load satellite
        satellite = SatelliteOrbit.from_tle_file(str(tle_file), satellite_name="ICEYE-X44")
        print(f"✓ Loaded satellite: {satellite.satellite_name}")
        
        # Configuration
        target_counts = [10, 20, 50]  # Test scaling
        duration_days = 7  # 1 week
        
        print(f"\nConfiguration:")
        print(f"  - Mission duration: {duration_days} days (168 hours)")
        print(f"  - Target counts: {target_counts}")
        print(f"  - Satellite: {satellite.satellite_name}")
        print(f"  - Workers: {get_optimal_workers()}")
        
        # Run benchmarks
        results = benchmark_caching(satellite, target_counts, duration_days)
        
        # Comparison to previous benchmarks (if available)
        print("\n" + "="*80)
        print("COMPARISON TO PREVIOUS RESULTS")
        print("="*80)
        
        # Try to load previous results
        prev_file = project_root / "benchmark_ultra_heavy_results.json"
        if prev_file.exists():
            with open(prev_file, 'r') as f:
                prev_data = json.load(f)
                prev_results = {r['targets']: r for r in prev_data.get('results', [])}
                
                print("\nImprovement over previous version:")
                for r in results:
                    if r['targets'] in prev_results:
                        prev = prev_results[r['targets']]
                        prev_serial = prev.get('serial_time', 0)
                        curr_serial = r['serial_time']
                        
                        if prev_serial > 0:
                            improvement = ((prev_serial - curr_serial) / prev_serial) * 100
                            print(f"  {r['targets']} targets: {prev_serial:.2f}s → {curr_serial:.2f}s "
                                  f"({improvement:+.1f}% {'faster' if improvement > 0 else 'slower'})")
        
        print("\n" + "="*80)
        print("✓ CACHING BENCHMARK COMPLETE")
        print("="*80)
        
    finally:
        # Cleanup
        if tle_file.exists():
            tle_file.unlink()


if __name__ == "__main__":
    main()
