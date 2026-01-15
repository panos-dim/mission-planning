#!/usr/bin/env python3
"""
Benchmark script for parallel processing performance.

This script compares serial vs parallel execution times for mission planning
computations with varying numbers of targets.
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
from mission_planner.parallel import ParallelVisibilityCalculator, benchmark_parallel_speedup
from mission_planner.utils import setup_logging

# Setup logging
setup_logging()
import logging
logger = logging.getLogger(__name__)


def create_test_targets(count: int) -> list:
    """Create test targets spread across the globe."""
    targets = []
    
    # Create targets at different latitudes and longitudes
    for i in range(count):
        lat = -60 + (120 / count) * i  # Spread from -60 to +60
        lon = -180 + (360 / count) * i  # Spread across all longitudes
        
        target = GroundTarget(
            name=f"Target_{i+1:03d}",
            latitude=lat,
            longitude=lon,
            description=f"Benchmark target {i+1}",
            mission_type="communication",
            elevation_mask=10.0
        )
        targets.append(target)
    
    return targets


def benchmark_scaling(satellite, target_counts: list, duration_hours: float = 24):
    """
    Benchmark scaling performance with different numbers of targets.
    
    Args:
        satellite: SatelliteOrbit instance
        target_counts: List of target counts to test
        duration_hours: Mission duration in hours
    """
    print("\n" + "="*80)
    print("PARALLEL PROCESSING BENCHMARK - SCALING TEST")
    print("="*80)
    
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=duration_hours)
    
    results = []
    
    for count in target_counts:
        print(f"\n{'─'*80}")
        print(f"Testing with {count} targets...")
        print(f"{'─'*80}")
        
        # Create targets
        targets = create_test_targets(count)
        
        # Serial benchmark
        serial_calc = VisibilityCalculator(satellite)
        
        serial_start = time.time()
        serial_results = serial_calc.get_visibility_windows(targets, start_time, end_time)
        serial_time = time.time() - serial_start
        
        serial_passes = sum(len(passes) for passes in serial_results.values())
        
        print(f"  Serial:   {serial_time:7.2f}s  ({serial_passes} passes)")
        
        # Parallel benchmark
        parallel_calc = ParallelVisibilityCalculator(satellite)
        
        parallel_start = time.time()
        parallel_results = parallel_calc.get_visibility_windows(targets, start_time, end_time)
        parallel_time = time.time() - parallel_start
        
        # Convert dict results back to count
        parallel_passes = sum(len(passes) for passes in parallel_results.values())
        
        print(f"  Parallel: {parallel_time:7.2f}s  ({parallel_passes} passes, {parallel_calc.max_workers} workers)")
        
        # Calculate metrics
        speedup = serial_time / parallel_time if parallel_time > 0 else 0
        efficiency = (speedup / parallel_calc.max_workers) * 100 if parallel_calc.max_workers > 0 else 0
        
        print(f"  Speedup:  {speedup:7.2f}x  (Efficiency: {efficiency:.1f}%)")
        
        # Validate results match
        results_match = serial_passes == parallel_passes
        print(f"  Validation: {'✓ PASS' if results_match else '✗ FAIL'} (passes match: {results_match})")
        
        results.append({
            'targets': count,
            'serial_time': round(serial_time, 2),
            'parallel_time': round(parallel_time, 2),
            'speedup': round(speedup, 2),
            'efficiency_percent': round(efficiency, 1),
            'workers': parallel_calc.max_workers,
            'serial_passes': serial_passes,
            'parallel_passes': parallel_passes,
            'results_match': results_match
        })
    
    # Summary
    print("\n" + "="*80)
    print("BENCHMARK SUMMARY")
    print("="*80)
    print(f"{'Targets':<10} {'Serial':<12} {'Parallel':<12} {'Speedup':<10} {'Efficiency':<12} {'Match':<8}")
    print("─"*80)
    
    for r in results:
        match_symbol = '✓' if r['results_match'] else '✗'
        print(f"{r['targets']:<10} {r['serial_time']:>7.2f}s     {r['parallel_time']:>7.2f}s     "
              f"{r['speedup']:>6.2f}x    {r['efficiency_percent']:>6.1f}%      {match_symbol}")
    
    print("="*80)
    
    # Save results
    output_file = project_root / "benchmark_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.utcnow().isoformat(),
            'duration_hours': duration_hours,
            'results': results
        }, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    return results


def main():
    """Run benchmarks."""
    print("\n🚀 Parallel Processing Benchmark for Satellite Mission Planning")
    print(f"Project: {project_root}")
    
    # Use sample TLE for ICEYE-X44
    tle_data = """ICEYE-X44
1 58931U 24032W   24288.50000000  .00008755  00000-0  45219-3 0  9999
2 58931  97.6932 349.4258 0010581  80.6517 279.5887 15.16344495 35186"""
    
    # Create TLE file
    tle_file = project_root / "temp_benchmark.tle"
    with open(tle_file, 'w') as f:
        f.write(tle_data)
    
    try:
        # Load satellite
        satellite = SatelliteOrbit.from_tle_file(str(tle_file), satellite_name="ICEYE-X44")
        print(f"✓ Loaded satellite: {satellite.satellite_name}")
        
        # Run scaling benchmarks
        target_counts = [5, 10, 20, 50]  # Test with different numbers of targets
        duration_hours = 24
        
        print(f"\nConfiguration:")
        print(f"  - Mission duration: {duration_hours} hours")
        print(f"  - Target counts: {target_counts}")
        print(f"  - Satellite: {satellite.satellite_name}")
        
        results = benchmark_scaling(satellite, target_counts, duration_hours)
        
        # Recommendations
        print("\n" + "="*80)
        print("RECOMMENDATIONS")
        print("="*80)
        
        avg_speedup = sum(r['speedup'] for r in results) / len(results)
        avg_efficiency = sum(r['efficiency_percent'] for r in results) / len(results)
        
        print(f"Average speedup: {avg_speedup:.2f}x")
        print(f"Average efficiency: {avg_efficiency:.1f}%")
        
        if avg_speedup >= 3.0:
            print("\n✓ Excellent parallel performance!")
            print("  Recommend enabling HPC mode for 10+ targets.")
        elif avg_speedup >= 2.0:
            print("\n✓ Good parallel performance.")
            print("  Recommend enabling HPC mode for 20+ targets.")
        else:
            print("\n⚠ Moderate parallel performance.")
            print("  Consider enabling HPC mode only for 50+ targets.")
        
        print("\nTo enable HPC mode in API:")
        print('  POST /api/mission/analyze with "use_parallel": true')
        
    finally:
        # Cleanup
        if tle_file.exists():
            tle_file.unlink()


if __name__ == "__main__":
    main()
