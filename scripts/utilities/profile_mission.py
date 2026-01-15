#!/usr/bin/env python3
"""
Profiling script for mission planning performance analysis.

This script uses cProfile to identify bottlenecks in the mission planning code.
"""

import sys
import os
from pathlib import Path
import cProfile
import pstats
from datetime import datetime, timedelta
from io import StringIO

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from mission_planner.orbit import SatelliteOrbit
from mission_planner.targets import GroundTarget
from mission_planner.planner import MissionPlanner
from mission_planner.utils import setup_logging

# Setup logging
setup_logging()
import logging
logger = logging.getLogger(__name__)


def create_test_scenario(num_targets: int = 10):
    """Create a test scenario with satellite and targets."""
    
    # Sample TLE for ICEYE-X44
    tle_data = """ICEYE-X44
1 58931U 24032W   24288.50000000  .00008755  00000-0  45219-3 0  9999
2 58931  97.6932 349.4258 0010581  80.6517 279.5887 15.16344495 35186"""
    
    # Create TLE file
    tle_file = project_root / "temp_profile.tle"
    with open(tle_file, 'w') as f:
        f.write(tle_data)
    
    # Load satellite
    satellite = SatelliteOrbit.from_tle_file(str(tle_file), satellite_name="ICEYE-X44")
    
    # Create targets
    targets = []
    for i in range(num_targets):
        lat = -60 + (120 / num_targets) * i
        lon = -180 + (360 / num_targets) * i
        
        target = GroundTarget(
            name=f"Target_{i+1:03d}",
            latitude=lat,
            longitude=lon,
            description=f"Profile target {i+1}",
            mission_type="communication",
            elevation_mask=10.0
        )
        targets.append(target)
    
    # Cleanup
    if tle_file.exists():
        tle_file.unlink()
    
    return satellite, targets


def profile_mission_analysis(num_targets: int = 10, duration_hours: float = 24):
    """Profile mission analysis with cProfile."""
    
    print("\n" + "="*80)
    print(f"PROFILING MISSION ANALYSIS - {num_targets} targets, {duration_hours}h duration")
    print("="*80)
    
    # Create test scenario
    satellite, targets = create_test_scenario(num_targets)
    
    # Create mission planner
    planner = MissionPlanner(satellite=satellite, targets=targets)
    
    # Time window
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=duration_hours)
    
    print(f"\nConfiguration:")
    print(f"  - Satellite: {satellite.satellite_name}")
    print(f"  - Targets: {len(targets)}")
    print(f"  - Duration: {duration_hours} hours")
    print(f"  - Time window: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}")
    
    # Profile the computation
    print("\nProfiling... (this may take a while)")
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Run mission analysis
    passes_dict = planner.compute_passes(start_time, end_time)
    
    profiler.disable()
    
    # Get statistics
    s = StringIO()
    stats = pstats.Stats(profiler, stream=s)
    
    # Sort by cumulative time
    stats.strip_dirs()
    stats.sort_stats('cumulative')
    
    print("\n" + "="*80)
    print("TOP 20 FUNCTIONS BY CUMULATIVE TIME")
    print("="*80)
    stats.print_stats(20)
    print(s.getvalue())
    
    # Sort by time spent in function itself
    s = StringIO()
    stats = pstats.Stats(profiler, stream=s)
    stats.strip_dirs()
    stats.sort_stats('time')
    
    print("\n" + "="*80)
    print("TOP 20 FUNCTIONS BY TIME (excluding calls)")
    print("="*80)
    stats.print_stats(20)
    print(s.getvalue())
    
    # Summary
    total_passes = sum(len(passes) for passes in passes_dict.values())
    print("\n" + "="*80)
    print("MISSION SUMMARY")
    print("="*80)
    print(f"Total passes found: {total_passes}")
    print(f"Targets analyzed: {len(targets)}")
    print(f"Average passes per target: {total_passes / len(targets):.1f}")
    
    # Save detailed profile
    profile_file = project_root / f"profile_t{num_targets}_d{int(duration_hours)}.prof"
    profiler.dump_stats(str(profile_file))
    print(f"\nDetailed profile saved to: {profile_file}")
    print(f"To analyze: python -m pstats {profile_file}")
    
    return passes_dict


def analyze_bottlenecks(num_targets: int = 10):
    """Analyze specific bottleneck functions."""
    
    print("\n" + "="*80)
    print("BOTTLENECK ANALYSIS")
    print("="*80)
    
    import time
    
    satellite, targets = create_test_scenario(num_targets)
    
    from mission_planner.visibility import VisibilityCalculator
    
    calc = VisibilityCalculator(satellite)
    
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=24)
    
    target = targets[0]
    
    # Test elevation calculation speed
    print("\nTesting elevation calculation speed...")
    test_time = start_time
    iterations = 1000
    
    start = time.time()
    for _ in range(iterations):
        calc.calculate_elevation_azimuth(target, test_time)
    elapsed = time.time() - start
    
    print(f"  {iterations} elevation calculations: {elapsed:.3f}s")
    print(f"  Average: {(elapsed/iterations)*1000:.3f}ms per calculation")
    print(f"  Rate: {iterations/elapsed:.0f} calculations/second")
    
    # Estimate total calculations for full mission
    duration_seconds = (end_time - start_time).total_seconds()
    total_calcs = num_targets * duration_seconds  # 1-second time step
    estimated_time = (total_calcs / iterations) * elapsed
    
    print(f"\nEstimated for full mission ({num_targets} targets, 24h):")
    print(f"  Total calculations: {total_calcs:,.0f}")
    print(f"  Estimated serial time: {estimated_time:.1f}s ({estimated_time/60:.1f} minutes)")
    
    # Test visibility checking
    print("\nTesting visibility checking speed...")
    start = time.time()
    for _ in range(iterations):
        calc.is_visible(target, test_time)
    elapsed = time.time() - start
    
    print(f"  {iterations} visibility checks: {elapsed:.3f}s")
    print(f"  Average: {(elapsed/iterations)*1000:.3f}ms per check")
    print(f"  Rate: {iterations/elapsed:.0f} checks/second")


def main():
    """Run profiling analysis."""
    
    print("\n🔍 Mission Planning Performance Profiler")
    print(f"Project: {project_root}")
    
    # Quick bottleneck analysis
    analyze_bottlenecks(num_targets=10)
    
    # Full profile with 10 targets
    print("\n" + "="*80)
    print("Running full profile...")
    print("="*80)
    profile_mission_analysis(num_targets=10, duration_hours=24)
    
    print("\n" + "="*80)
    print("PROFILING COMPLETE")
    print("="*80)
    print("\nKey bottlenecks to optimize:")
    print("  1. find_passes() - Serial loop through time steps")
    print("  2. calculate_elevation_azimuth() - Called for every time step")
    print("  3. get_visibility_windows() - Serial loop through targets")
    print("\nOptimization strategy:")
    print("  ✓ Parallelize target analysis (implemented)")
    print("  - Consider NumPy vectorization for math operations")
    print("  - Consider Numba JIT compilation for hot loops")


if __name__ == "__main__":
    main()
