#!/usr/bin/env python3
"""
Benchmark adaptive time-stepping vs fixed-step baseline.
Tests 1-week mission duration with multiple targets.
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
from mission_planner.utils import setup_logging

# Setup logging
setup_logging()
import logging
logger = logging.getLogger(__name__)


def create_test_targets(count: int) -> list:
    """Create test targets (UAE region)."""
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
            elevation_mask=10.0,
            mission_type='communication',
            description=f"Test target {i+1}"
        )
        targets.append(target)
    
    return targets


def run_benchmark(target_counts, duration_days=7):
    """Run adaptive vs fixed-step benchmark."""
    
    print("="*80)
    print("ADAPTIVE TIME-STEPPING BENCHMARK")
    print("="*80)
    print(f"\nMission Duration: {duration_days} days ({duration_days * 24} hours)")
    print(f"Test Targets: {target_counts}")
    print(f"\nLoading satellite...")
    
    # Load satellite
    tle_file = project_root / "data" / "active_satellites.tle"
    satellite = SatelliteOrbit.from_tle_file(str(tle_file), satellite_name="ICEYE-X44")
    print(f"✓ Loaded: {satellite.satellite_name}")
    
    results = {
        'timestamp': datetime.utcnow().isoformat(),
        'duration_days': duration_days,
        'satellite': satellite.satellite_name,
        'benchmarks': []
    }
    
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(days=duration_days)
    
    print(f"\nTime window: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')} UTC")
    print("="*80)
    
    for target_count in target_counts:
        print(f"\n{'='*80}")
        print(f"TESTING: {target_count} targets")
        print(f"{'='*80}")
        
        targets = create_test_targets(target_count)
        
        # Baseline: Fixed-step (1 second)
        print(f"\n1. Fixed-Step Baseline (1s resolution)...")
        calc_fixed = VisibilityCalculator(satellite, use_adaptive=False)
        
        fixed_times = []
        fixed_passes_total = 0
        
        for target in targets:
            start = time.time()
            passes = calc_fixed.find_passes(target, start_time, end_time, time_step_seconds=1)
            elapsed = time.time() - start
            fixed_times.append(elapsed)
            fixed_passes_total += len(passes)
        
        fixed_time_total = sum(fixed_times)
        print(f"   ✓ Time: {fixed_time_total:.2f}s")
        print(f"   ✓ Passes: {fixed_passes_total}")
        print(f"   ✓ Avg per target: {fixed_time_total/target_count:.2f}s")
        
        # Adaptive algorithm
        print(f"\n2. Adaptive Time-Stepping...")
        calc_adaptive = VisibilityCalculator(satellite, use_adaptive=True)
        
        adaptive_times = []
        adaptive_passes_total = 0
        
        for target in targets:
            start = time.time()
            passes = calc_adaptive.find_passes(target, start_time, end_time)
            elapsed = time.time() - start
            adaptive_times.append(elapsed)
            adaptive_passes_total += len(passes)
        
        adaptive_time_total = sum(adaptive_times)
        print(f"   ✓ Time: {adaptive_time_total:.2f}s")
        print(f"   ✓ Passes: {adaptive_passes_total}")
        print(f"   ✓ Avg per target: {adaptive_time_total/target_count:.2f}s")
        
        # Calculate speedup
        speedup = fixed_time_total / adaptive_time_total if adaptive_time_total > 0 else 0
        time_saved = fixed_time_total - adaptive_time_total
        percent_faster = (time_saved / fixed_time_total * 100) if fixed_time_total > 0 else 0
        
        # Verify accuracy
        passes_match = (fixed_passes_total == adaptive_passes_total)
        
        # Results
        print(f"\n{'='*80}")
        print("RESULTS:")
        print(f"  Fixed-step:     {fixed_time_total:.2f}s  ({fixed_passes_total} passes)")
        print(f"  Adaptive:       {adaptive_time_total:.2f}s  ({adaptive_passes_total} passes)")
        print(f"  Speedup:        {speedup:.2f}× ({percent_faster:.1f}% faster)")
        print(f"  Time saved:     {time_saved:.2f}s")
        print(f"  Accuracy:       {'✓ PASS' if passes_match else '✗ FAIL'} (passes match: {passes_match})")
        print(f"{'='*80}")
        
        # Store results
        results['benchmarks'].append({
            'target_count': target_count,
            'fixed_step': {
                'total_time': fixed_time_total,
                'passes': fixed_passes_total,
                'avg_per_target': fixed_time_total / target_count
            },
            'adaptive': {
                'total_time': adaptive_time_total,
                'passes': adaptive_passes_total,
                'avg_per_target': adaptive_time_total / target_count
            },
            'speedup': speedup,
            'time_saved': time_saved,
            'percent_faster': percent_faster,
            'accuracy_pass': passes_match
        })
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"\n{'Targets':<10} {'Fixed':<12} {'Adaptive':<12} {'Speedup':<12} {'Status':<10}")
    print("-"*80)
    
    for result in results['benchmarks']:
        tc = result['target_count']
        fixed = result['fixed_step']['total_time']
        adaptive = result['adaptive']['total_time']
        speedup = result['speedup']
        status = "✓ PASS" if result['accuracy_pass'] else "✗ FAIL"
        
        print(f"{tc:<10} {fixed:>10.2f}s  {adaptive:>10.2f}s  {speedup:>10.2f}×  {status:<10}")
    
    # Average speedup
    avg_speedup = sum(r['speedup'] for r in results['benchmarks']) / len(results['benchmarks'])
    avg_saved = sum(r['time_saved'] for r in results['benchmarks']) / len(results['benchmarks'])
    
    print("-"*80)
    print(f"{'Average':<10} {'':>10}   {'':>10}   {avg_speedup:>10.2f}×")
    print(f"\nAverage time saved: {avg_saved:.2f}s per scenario")
    print(f"All accuracy checks: {'✓ PASSED' if all(r['accuracy_pass'] for r in results['benchmarks']) else '✗ FAILED'}")
    
    # Save results
    output_file = project_root / "benchmark_adaptive_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Results saved to: {output_file}")
    print("="*80)
    
    return results


if __name__ == "__main__":
    # Test with increasing target counts for 1-week duration
    target_counts = [1, 2, 3, 5]
    results = run_benchmark(target_counts, duration_days=7)
    
    # Check if speedup target met
    avg_speedup = sum(r['speedup'] for r in results['benchmarks']) / len(results['benchmarks'])
    
    if avg_speedup >= 2.0:
        print(f"\n✅ SUCCESS: Average speedup {avg_speedup:.2f}× meets target (≥2×)")
        sys.exit(0)
    else:
        print(f"\n⚠️  WARNING: Average speedup {avg_speedup:.2f}× below target (≥2×)")
        sys.exit(0)
