#!/usr/bin/env python3
"""
Benchmark script to test NumPy vectorization performance.

Compares:
1. Loop-based (current implementation)
2. NumPy vectorized (new implementation)
"""

import sys
import os
from pathlib import Path
import time
from datetime import datetime, timedelta, timezone

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from mission_planner.orbit import SatelliteOrbit
from mission_planner.targets import GroundTarget
from mission_planner.visibility import VisibilityCalculator
from mission_planner.utils import setup_logging

# Setup logging (minimal for benchmarking)
import logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def create_test_target(name: str, lat: float, lon: float) -> GroundTarget:
    """Create a single test target."""
    return GroundTarget(
        name=name,
        latitude=lat,
        longitude=lon,
        description=f"Test target {name}",
        mission_type="communication",
        elevation_mask=10.0
    )


def benchmark_single_target(satellite, duration_days: int = 7):
    """
    Benchmark loop vs vectorized for a single target.
    
    Args:
        satellite: SatelliteOrbit instance
        duration_days: Mission duration in days
    """
    print("\n" + "="*80)
    print(f"VECTORIZATION BENCHMARK - {duration_days}-DAY MISSION, SINGLE TARGET")
    print("="*80)
    
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(days=duration_days)
    
    # Create target (Dubai)
    target = create_test_target("Dubai", 25.2048, 55.2708)
    
    print(f"\nTarget: {target.name} ({target.latitude:.2f}°, {target.longitude:.2f}°)")
    print(f"Time window: {duration_days} days ({duration_days * 24} hours)")
    print(f"Time steps: {duration_days * 24 * 3600:,} (1-second intervals)")
    
    # Test 1: Loop-based (current implementation)
    print(f"\n[1/2] Loop-based implementation...")
    calc = VisibilityCalculator(satellite)
    
    loop_start = time.time()
    loop_passes = calc.find_passes(target, start_time, end_time, time_step_seconds=1)
    loop_time = time.time() - loop_start
    
    print(f"      Time: {loop_time:7.2f}s  ({len(loop_passes)} passes)")
    
    # Test 2: Vectorized implementation
    print(f"[2/2] NumPy vectorized implementation...")
    
    vectorized_start = time.time()
    vectorized_passes = calc.find_passes_vectorized(target, start_time, end_time, time_step_seconds=1)
    vectorized_time = time.time() - vectorized_start
    
    speedup = loop_time / vectorized_time if vectorized_time > 0 else 0
    print(f"      Time: {vectorized_time:7.2f}s  ({len(vectorized_passes)} passes)")
    print(f"      Speedup: {speedup:.2f}x faster")
    
    # Validation
    print(f"\n{'─'*80}")
    print("VALIDATION")
    print(f"{'─'*80}")
    
    passes_match = len(loop_passes) == len(vectorized_passes)
    print(f"Pass count: Loop={len(loop_passes)}, Vectorized={len(vectorized_passes)} - {'✓ MATCH' if passes_match else '✗ MISMATCH'}")
    
    # Compare pass details
    if passes_match and len(loop_passes) > 0:
        print(f"\nComparing first pass details:")
        lp = loop_passes[0]
        vp = vectorized_passes[0]
        
        time_diff = abs((lp.start_time - vp.start_time).total_seconds())
        elev_diff = abs(lp.max_elevation - vp.max_elevation)
        az_diff = abs(lp.start_azimuth - vp.start_azimuth)
        
        print(f"  Start time diff: {time_diff:.1f}s")
        print(f"  Max elevation diff: {elev_diff:.3f}°")
        print(f"  Azimuth diff: {az_diff:.3f}°")
        
        accuracy_ok = time_diff < 2 and elev_diff < 0.1 and az_diff < 1.0
        print(f"  Accuracy: {'✓ PASS' if accuracy_ok else '✗ FAIL'}")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Loop-based:       {loop_time:7.2f}s  (baseline)")
    print(f"NumPy vectorized: {vectorized_time:7.2f}s  ({speedup:.2f}x faster)")
    print(f"Time saved:       {loop_time - vectorized_time:7.2f}s  ({((loop_time - vectorized_time) / loop_time * 100):.1f}%)")
    print(f"{'='*80}")
    
    return {
        'loop_time': loop_time,
        'vectorized_time': vectorized_time,
        'speedup': speedup,
        'loop_passes': len(loop_passes),
        'vectorized_passes': len(vectorized_passes),
        'validation': passes_match
    }


def benchmark_multi_target(satellite, num_targets: int = 10, duration_days: int = 7):
    """
    Benchmark loop vs vectorized for multiple targets.
    
    Args:
        satellite: SatelliteOrbit instance
        num_targets: Number of targets to test
        duration_days: Mission duration in days
    """
    print("\n" + "="*80)
    print(f"VECTORIZATION BENCHMARK - {duration_days}-DAY MISSION, {num_targets} TARGETS")
    print("="*80)
    
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(days=duration_days)
    
    # Create targets distributed globally
    targets = []
    for i in range(num_targets):
        lat = -60 + (120 / num_targets) * i
        lon = -180 + (360 / num_targets) * i
        targets.append(create_test_target(f"Target_{i+1:02d}", lat, lon))
    
    print(f"\nTargets: {len(targets)} globally distributed")
    print(f"Time window: {duration_days} days")
    
    # Test 1: Loop-based
    print(f"\n[1/2] Loop-based implementation...")
    calc = VisibilityCalculator(satellite)
    
    loop_start = time.time()
    loop_results = {}
    for target in targets:
        loop_results[target.name] = calc.find_passes(target, start_time, end_time, time_step_seconds=1)
    loop_time = time.time() - loop_start
    
    loop_total_passes = sum(len(passes) for passes in loop_results.values())
    print(f"      Time: {loop_time:7.2f}s  ({loop_total_passes} total passes)")
    
    # Test 2: Vectorized
    print(f"[2/2] NumPy vectorized implementation...")
    
    vectorized_start = time.time()
    vectorized_results = {}
    for target in targets:
        vectorized_results[target.name] = calc.find_passes_vectorized(target, start_time, end_time, time_step_seconds=1)
    vectorized_time = time.time() - vectorized_start
    
    vectorized_total_passes = sum(len(passes) for passes in vectorized_results.values())
    speedup = loop_time / vectorized_time if vectorized_time > 0 else 0
    
    print(f"      Time: {vectorized_time:7.2f}s  ({vectorized_total_passes} total passes)")
    print(f"      Speedup: {speedup:.2f}x faster")
    
    # Validation
    print(f"\n{'─'*80}")
    print("VALIDATION")
    print(f"{'─'*80}")
    
    passes_match = loop_total_passes == vectorized_total_passes
    print(f"Total passes: Loop={loop_total_passes}, Vectorized={vectorized_total_passes} - {'✓ MATCH' if passes_match else '✗ MISMATCH'}")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Loop-based:       {loop_time:7.2f}s  (baseline)")
    print(f"NumPy vectorized: {vectorized_time:7.2f}s  ({speedup:.2f}x faster)")
    print(f"Time saved:       {loop_time - vectorized_time:7.2f}s  ({((loop_time - vectorized_time) / loop_time * 100):.1f}%)")
    print(f"Avg per target:   Loop={loop_time/num_targets:.2f}s, Vectorized={vectorized_time/num_targets:.2f}s")
    print(f"{'='*80}")
    
    return {
        'loop_time': loop_time,
        'vectorized_time': vectorized_time,
        'speedup': speedup,
        'loop_passes': loop_total_passes,
        'vectorized_passes': vectorized_total_passes,
        'validation': passes_match
    }


def main():
    """Run vectorization benchmarks."""
    print("\n🚀 NumPy Vectorization Benchmark")
    print(f"Project: {project_root}")
    print("Testing: Loop-based vs NumPy vectorized implementation")
    
    # Use sample TLE for ICEYE-X44
    tle_data = """ICEYE-X44
1 58931U 24032W   24288.50000000  .00008755  00000-0  45219-3 0  9999
2 58931  97.6932 349.4258 0010581  80.6517 279.5887 15.16344495 35186"""
    
    # Create TLE file
    tle_file = project_root / "temp_benchmark_vectorized.tle"
    with open(tle_file, 'w') as f:
        f.write(tle_data)
    
    try:
        # Load satellite
        satellite = SatelliteOrbit.from_tle_file(str(tle_file), satellite_name="ICEYE-X44")
        print(f"✓ Loaded satellite: {satellite.satellite_name}")
        
        # Test 1: Single target (7 days)
        print("\n" + "█"*80)
        print("TEST 1: Single Target")
        print("█"*80)
        result1 = benchmark_single_target(satellite, duration_days=7)
        
        # Test 2: Multiple targets (7 days)
        print("\n" + "█"*80)
        print("TEST 2: Multiple Targets")
        print("█"*80)
        result2 = benchmark_multi_target(satellite, num_targets=10, duration_days=7)
        
        # Final summary
        print("\n" + "="*80)
        print("FINAL RESULTS")
        print("="*80)
        print(f"\nSingle Target (7 days):")
        print(f"  Loop:       {result1['loop_time']:.2f}s")
        print(f"  Vectorized: {result1['vectorized_time']:.2f}s")
        print(f"  Speedup:    {result1['speedup']:.2f}x")
        
        print(f"\n10 Targets (7 days):")
        print(f"  Loop:       {result2['loop_time']:.2f}s")
        print(f"  Vectorized: {result2['vectorized_time']:.2f}s")
        print(f"  Speedup:    {result2['speedup']:.2f}x")
        
        print(f"\nRECOMMENDATION:")
        avg_speedup = (result1['speedup'] + result2['speedup']) / 2
        if avg_speedup > 3.0:
            print(f"  ✅ EXCELLENT! {avg_speedup:.1f}x speedup - Deploy vectorized version")
        elif avg_speedup > 1.5:
            print(f"  ✓ GOOD! {avg_speedup:.1f}x speedup - Consider deploying")
        else:
            print(f"  ⚠ LIMITED! {avg_speedup:.1f}x speedup - Needs investigation")
        
        print("="*80)
        
    finally:
        # Cleanup
        if tle_file.exists():
            tle_file.unlink()


if __name__ == "__main__":
    main()
