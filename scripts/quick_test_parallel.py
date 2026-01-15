#!/usr/bin/env python3
"""Quick test to validate parallel processing implementation."""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))


def main():
    """Run parallel processing tests."""
    print("Testing parallel processing implementation...\n")

    try:
        # Test imports
        print("1. Testing imports...")
        from mission_planner.orbit import SatelliteOrbit
        from mission_planner.targets import GroundTarget
        from mission_planner.visibility import VisibilityCalculator
        from mission_planner.parallel import ParallelVisibilityCalculator, get_optimal_workers
        print("   ✓ All modules imported successfully")
        
        # Test optimal workers detection
        print("\n2. Testing optimal workers detection...")
        optimal = get_optimal_workers()
        print(f"   ✓ Detected {optimal} optimal workers")
        
        # Create test satellite
        print("\n3. Creating test satellite...")
        tle_data = """ICEYE-X44
1 58931U 24032W   24288.50000000  .00008755  00000-0  45219-3 0  9999
2 58931  97.6932 349.4258 0010581  80.6517 279.5887 15.16344495 35186"""
        
        tle_file = project_root / "temp_quick_test.tle"
        with open(tle_file, 'w') as f:
            f.write(tle_data)
        
        satellite = SatelliteOrbit.from_tle_file(str(tle_file), satellite_name="ICEYE-X44")
        print(f"   ✓ Satellite loaded: {satellite.satellite_name}")
        
        # Create test targets
        print("\n4. Creating test targets...")
        targets = [
            GroundTarget(name="Dubai", latitude=25.2, longitude=55.3, 
                        mission_type="communication", elevation_mask=10.0),
            GroundTarget(name="Singapore", latitude=1.4, longitude=103.8,
                        mission_type="communication", elevation_mask=10.0),
            GroundTarget(name="London", latitude=51.5, longitude=-0.1,
                        mission_type="communication", elevation_mask=10.0),
        ]
        print(f"   ✓ Created {len(targets)} targets")
        
        # Test serial computation
        print("\n5. Testing serial computation...")
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=12)
        
        serial_calc = VisibilityCalculator(satellite)
        serial_results = serial_calc.get_visibility_windows(targets, start_time, end_time)
        serial_passes = sum(len(passes) for passes in serial_results.values())
        print(f"   ✓ Serial: Found {serial_passes} passes")
        
        # Test parallel computation
        print("\n6. Testing parallel computation...")
        parallel_calc = ParallelVisibilityCalculator(satellite, max_workers=2)
        parallel_results = parallel_calc.get_visibility_windows(targets, start_time, end_time)
        parallel_passes = sum(len(passes) for passes in parallel_results.values())
        print(f"   ✓ Parallel: Found {parallel_passes} passes")
        
        # Validate results match
        print("\n7. Validating results...")
        if serial_passes == parallel_passes:
            print(f"   ✓ PASS: Results match ({serial_passes} passes)")
        else:
            print(f"   ✗ FAIL: Results don't match (serial={serial_passes}, parallel={parallel_passes})")
            sys.exit(1)
        
        # Cleanup
        if tle_file.exists():
            tle_file.unlink()
        
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED")
        print("="*70)
        print("\nParallel processing is working correctly!")
        print("\nNext steps:")
        print("  1. Run full benchmark: python scripts/benchmark_parallel.py")
        print("  2. Run validation tests: pytest tests/test_parallel_validation.py")
        print("  3. Profile performance: python scripts/profile_mission.py")
        print("\nTo use in API, add to mission request:")
        print('  "use_parallel": true')
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
