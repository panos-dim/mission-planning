"""
Test parallel processing for correctness and numerical accuracy.

Validates that parallel computations produce identical results to serial
computations within acceptable numerical tolerances.

NOTE: These tests use ProcessPoolExecutor which can be slow.
Run with: pytest -m "not slow" to skip these tests.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pytest

# Mark all tests in this module as slow (they use multiprocessing)
pytestmark = [pytest.mark.slow, pytest.mark.integration]

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from mission_planner.orbit import SatelliteOrbit
from mission_planner.targets import GroundTarget
from mission_planner.visibility import VisibilityCalculator
from mission_planner.parallel import ParallelVisibilityCalculator


@pytest.fixture
def satellite():
    """Create test satellite."""
    tle_data = """ICEYE-X44
1 58931U 24032W   24288.50000000  .00008755  00000-0  45219-3 0  9999
2 58931  97.6932 349.4258 0010581  80.6517 279.5887 15.16344495 35186"""

    tle_file = project_root / "temp_test.tle"
    with open(tle_file, 'w') as f:
        f.write(tle_data)

    satellite = SatelliteOrbit.from_tle_file(str(tle_file), satellite_name="ICEYE-X44")

    yield satellite

    # Cleanup
    if tle_file.exists():
        tle_file.unlink()


@pytest.fixture
def targets():
    """Create test targets."""
    return [
        GroundTarget(
            name="Dubai", latitude=25.2048, longitude=55.2708,
            mission_type="communication", elevation_mask=10.0
        ),
        GroundTarget(
            name="Singapore", latitude=1.3521, longitude=103.8198,
            mission_type="communication", elevation_mask=10.0
        ),
        GroundTarget(
            name="London", latitude=51.5074, longitude=-0.1278,
            mission_type="communication", elevation_mask=10.0
        ),
        GroundTarget(
            name="New York", latitude=40.7128, longitude=-74.0060,
            mission_type="communication", elevation_mask=10.0
        ),
        GroundTarget(
            name="Tokyo", latitude=35.6762, longitude=139.6503,
            mission_type="communication", elevation_mask=10.0
        ),
    ]


def test_parallel_pass_count_matches_serial(satellite, targets):
    """Test that parallel and serial computations find same number of passes."""

    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=24)

    # Serial computation
    serial_calc = VisibilityCalculator(satellite)
    serial_results = serial_calc.get_visibility_windows(targets, start_time, end_time)

    # Parallel computation
    parallel_calc = ParallelVisibilityCalculator(satellite)
    parallel_results_dict = parallel_calc.get_visibility_windows(targets, start_time, end_time)

    # Compare pass counts per target
    for target in targets:
        serial_passes = len(serial_results[target.name])
        parallel_passes = len(parallel_results_dict[target.name])

        assert serial_passes == parallel_passes, (
            f"Pass count mismatch for {target.name}: "
            f"serial={serial_passes}, parallel={parallel_passes}"
        )


def test_parallel_pass_times_match_serial(satellite, targets):
    """Test that parallel and serial pass times match within tolerance."""

    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=24)

    # Serial computation
    serial_calc = VisibilityCalculator(satellite)
    serial_results = serial_calc.get_visibility_windows(targets, start_time, end_time)

    # Parallel computation
    parallel_calc = ParallelVisibilityCalculator(satellite)
    parallel_results_dict = parallel_calc.get_visibility_windows(targets, start_time, end_time)

    # Convert parallel results back to PassDetails
    from mission_planner.visibility import PassDetails

    time_tolerance_seconds = 1.0  # Allow 1 second difference

    for target in targets:
        serial_passes = serial_results[target.name]
        parallel_passes_dict = parallel_results_dict[target.name]

        # Convert dict to PassDetails for comparison
        parallel_passes = []
        for p_dict in parallel_passes_dict:
            pass_detail = PassDetails(
                target_name=p_dict['target_name'],
                satellite_name=p_dict['satellite_name'],
                start_time=datetime.fromisoformat(p_dict['start_time']),
                max_elevation_time=datetime.fromisoformat(p_dict['max_elevation_time']),
                end_time=datetime.fromisoformat(p_dict['end_time']),
                max_elevation=p_dict['max_elevation'],
                start_azimuth=p_dict['start_azimuth'],
                max_elevation_azimuth=p_dict['max_elevation_azimuth'],
                end_azimuth=p_dict['end_azimuth']
            )
            parallel_passes.append(pass_detail)

        assert len(serial_passes) == len(parallel_passes)

        # Compare each pass
        for i, (serial_pass, parallel_pass) in enumerate(zip(serial_passes, parallel_passes)):
            # Check times match within tolerance
            start_diff = abs((serial_pass.start_time - parallel_pass.start_time).total_seconds())
            max_diff = abs((serial_pass.max_elevation_time - parallel_pass.max_elevation_time).total_seconds())
            end_diff = abs((serial_pass.end_time - parallel_pass.end_time).total_seconds())

            assert start_diff <= time_tolerance_seconds, (
                f"Pass {i+1} for {target.name}: start time differs by {start_diff}s"
            )
            assert max_diff <= time_tolerance_seconds, (
                f"Pass {i+1} for {target.name}: max elevation time differs by {max_diff}s"
            )
            assert end_diff <= time_tolerance_seconds, (
                f"Pass {i+1} for {target.name}: end time differs by {end_diff}s"
            )


def test_parallel_elevations_match_serial(satellite, targets):
    """Test that parallel and serial elevation values match within tolerance."""

    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=24)

    # Serial computation
    serial_calc = VisibilityCalculator(satellite)
    serial_results = serial_calc.get_visibility_windows(targets, start_time, end_time)

    # Parallel computation
    parallel_calc = ParallelVisibilityCalculator(satellite)
    parallel_results_dict = parallel_calc.get_visibility_windows(targets, start_time, end_time)

    elevation_tolerance = 0.1  # Allow 0.1 degree difference

    for target in targets:
        serial_passes = serial_results[target.name]
        parallel_passes_dict = parallel_results_dict[target.name]

        assert len(serial_passes) == len(parallel_passes_dict)

        for i, (serial_pass, parallel_pass_dict) in enumerate(zip(serial_passes, parallel_passes_dict)):
            elevation_diff = abs(serial_pass.max_elevation - parallel_pass_dict['max_elevation'])

            assert elevation_diff <= elevation_tolerance, (
                f"Pass {i+1} for {target.name}: elevation differs by {elevation_diff}° "
                f"(serial={serial_pass.max_elevation:.2f}°, parallel={parallel_pass_dict['max_elevation']:.2f}°)"
            )


def test_parallel_no_memory_leak():
    """Test that parallel processing doesn't leak memory."""

    import gc
    import tracemalloc

    # Start tracking memory
    tracemalloc.start()
    gc.collect()

    # Create satellite
    tle_data = """ICEYE-X44
1 58931U 24032W   24288.50000000  .00008755  00000-0  45219-3 0  9999
2 58931  97.6932 349.4258 0010581  80.6517 279.5887 15.16344495 35186"""

    tle_file = project_root / "temp_test_memory.tle"
    with open(tle_file, 'w') as f:
        f.write(tle_data)

    satellite = SatelliteOrbit.from_tle_file(str(tle_file), satellite_name="ICEYE-X44")

    targets = [
        GroundTarget(
            name=f"Target_{i}", latitude=i*10, longitude=i*10,
            mission_type="communication", elevation_mask=10.0
        )
        for i in range(10)
    ]

    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=24)

    # Get initial memory
    gc.collect()
    snapshot1 = tracemalloc.take_snapshot()

    # Run parallel computation multiple times
    parallel_calc = ParallelVisibilityCalculator(satellite, max_workers=4)

    for run in range(3):
        results = parallel_calc.get_visibility_windows(targets, start_time, end_time)
        gc.collect()

    # Get final memory
    snapshot2 = tracemalloc.take_snapshot()

    # Compare memory usage
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')

    # Total memory growth should be minimal (< 10MB)
    total_growth = sum(stat.size_diff for stat in top_stats) / (1024 * 1024)  # Convert to MB

    # Cleanup
    if tle_file.exists():
        tle_file.unlink()

    tracemalloc.stop()

    assert abs(total_growth) < 10, f"Memory grew by {total_growth:.2f}MB after 3 runs"


def test_parallel_deterministic():
    """Test that parallel computation is deterministic (same results every time)."""

    # Create satellite
    tle_data = """ICEYE-X44
1 58931U 24032W   24288.50000000  .00008755  00000-0  45219-3 0  9999
2 58931  97.6932 349.4258 0010581  80.6517 279.5887 15.16344495 35186"""

    tle_file = project_root / "temp_test_deterministic.tle"
    with open(tle_file, 'w') as f:
        f.write(tle_data)

    satellite = SatelliteOrbit.from_tle_file(str(tle_file), satellite_name="ICEYE-X44")

    targets = [
        GroundTarget(
            name=f"Target_{i}", latitude=i*10, longitude=i*10,
            mission_type="communication", elevation_mask=10.0
        )
        for i in range(5)
    ]

    start_time = datetime(2025, 1, 1, 0, 0, 0)
    end_time = start_time + timedelta(hours=12)

    # Run multiple times
    parallel_calc = ParallelVisibilityCalculator(satellite, max_workers=4)

    results_list = []
    for run in range(3):
        results = parallel_calc.get_visibility_windows(targets, start_time, end_time)

        # Extract pass counts and elevations
        run_data = {}
        for target_name, passes in results.items():
            run_data[target_name] = [
                (p['start_time'], p['max_elevation']) for p in passes
            ]
        results_list.append(run_data)

    # Cleanup
    if tle_file.exists():
        tle_file.unlink()

    # All runs should produce identical results
    for run_idx in range(1, len(results_list)):
        assert results_list[run_idx] == results_list[0], (
            f"Run {run_idx+1} produced different results than run 1"
        )


if __name__ == "__main__":
    # Run tests manually
    pytest.main([__file__, "-v", "-s"])
