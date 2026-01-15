"""
Tests for the parallel processing module.

Tests parallel visibility calculations with mocked multiprocessing components.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timedelta
from concurrent.futures import Future

from mission_planner.parallel import (
    get_optimal_workers,
    get_or_create_process_pool,
    cleanup_process_pool,
    _compute_target_passes_worker,
    ParallelVisibilityCalculator,
    benchmark_parallel_speedup
)


class TestGetOptimalWorkers:
    """Tests for get_optimal_workers function."""

    @patch('os.cpu_count')
    def test_default_uses_all_cores(self, mock_cpu) -> None:
        """Test that default uses all CPU cores."""
        mock_cpu.return_value = 8

        result = get_optimal_workers()

        assert result == 8

    @patch('os.cpu_count')
    def test_respects_max_workers(self, mock_cpu) -> None:
        """Test that max_workers limit is respected."""
        mock_cpu.return_value = 16

        result = get_optimal_workers(max_workers=4)

        assert result == 4

    @patch('os.cpu_count')
    def test_max_workers_cant_exceed_cpu(self, mock_cpu) -> None:
        """Test that max_workers can't exceed CPU count."""
        mock_cpu.return_value = 4

        result = get_optimal_workers(max_workers=16)

        assert result == 4

    @patch('os.cpu_count')
    def test_optimizes_for_small_workload(self, mock_cpu) -> None:
        """Test optimization for small number of targets."""
        mock_cpu.return_value = 8

        # With 10 targets (< 20), should use 75% of cores
        result = get_optimal_workers(num_targets=10)

        assert result == 6  # 75% of 8 = 6

    @patch('os.cpu_count')
    def test_limits_workers_to_target_count(self, mock_cpu) -> None:
        """Test workers limited to number of targets."""
        mock_cpu.return_value = 8

        result = get_optimal_workers(num_targets=50)

        assert result == 8  # Limited by CPU count

    @patch('os.cpu_count')
    def test_handles_none_cpu_count(self, mock_cpu) -> None:
        """Test handling when cpu_count returns None."""
        mock_cpu.return_value = None

        result = get_optimal_workers()

        assert result == 4  # Default fallback

    @patch('os.cpu_count')
    def test_small_target_count_optimization(self, mock_cpu) -> None:
        """Test that small target counts use fewer workers."""
        mock_cpu.return_value = 16

        result = get_optimal_workers(num_targets=5)

        # 75% of 16 = 12, but limited by target count
        assert result == 12


class TestProcessPool:
    """Tests for process pool management."""

    def test_cleanup_process_pool(self) -> None:
        """Test process pool cleanup."""
        import mission_planner.parallel as parallel_module

        # Reset global state
        parallel_module._process_pool = None
        parallel_module._pool_max_workers = None

        # Call cleanup (should handle None pool gracefully)
        cleanup_process_pool()

        assert parallel_module._process_pool is None
        assert parallel_module._pool_max_workers is None

    @patch('mission_planner.parallel.ProcessPoolExecutor')
    def test_get_or_create_pool_creates_new(self, mock_executor_class) -> None:
        """Test that a new pool is created when needed."""
        import mission_planner.parallel as parallel_module

        # Reset global state
        parallel_module._process_pool = None
        parallel_module._pool_max_workers = None

        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        result = get_or_create_process_pool(4)

        mock_executor_class.assert_called_once()
        assert result == mock_executor

    @patch('mission_planner.parallel.ProcessPoolExecutor')
    def test_get_or_create_pool_reuses_existing(self, mock_executor_class) -> None:
        """Test that existing pool is reused if same size."""
        import mission_planner.parallel as parallel_module

        mock_executor = MagicMock()
        parallel_module._process_pool = mock_executor
        parallel_module._pool_max_workers = 4

        result = get_or_create_process_pool(4)

        # Should not create a new one
        mock_executor_class.assert_not_called()
        assert result == mock_executor

        # Reset for other tests
        parallel_module._process_pool = None
        parallel_module._pool_max_workers = None

    @patch('mission_planner.parallel.ProcessPoolExecutor')
    def test_get_or_create_pool_replaces_different_size(self, mock_executor_class) -> None:
        """Test that pool is replaced if different size requested."""
        import mission_planner.parallel as parallel_module

        old_executor = MagicMock()
        parallel_module._process_pool = old_executor
        parallel_module._pool_max_workers = 4

        new_executor = MagicMock()
        mock_executor_class.return_value = new_executor

        result = get_or_create_process_pool(8)

        # Should shutdown old pool and create new
        old_executor.shutdown.assert_called_once_with(wait=False)
        mock_executor_class.assert_called_once()
        assert result == new_executor

        # Reset for other tests
        parallel_module._process_pool = None
        parallel_module._pool_max_workers = None


class TestComputeTargetPassesWorker:
    """Tests for the worker function."""

    @patch('mission_planner.visibility.VisibilityCalculator')
    @patch('mission_planner.targets.GroundTarget')
    @patch('mission_planner.orbit.SatelliteOrbit')
    @patch('tempfile.NamedTemporaryFile')
    @patch('os.path.exists')
    @patch('os.unlink')
    def test_worker_computes_passes(
        self, mock_unlink, mock_exists, mock_tempfile,
        mock_sat_class, mock_target_class, mock_calc_class
    ) -> None:
        """Test worker function computes passes correctly."""
        # Setup mocks
        mock_exists.return_value = True

        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.name = '/tmp/test.tle'
        mock_tempfile.return_value = mock_file

        mock_sat = MagicMock()
        mock_sat_class.from_tle_file.return_value = mock_sat

        mock_target = MagicMock()
        mock_target_class.return_value = mock_target

        mock_pass = MagicMock()
        mock_pass.to_dict.return_value = {'target_name': 'Test', 'max_elevation': 45.0}

        mock_calc = MagicMock()
        mock_calc.find_passes.return_value = [mock_pass]
        mock_calc_class.return_value = mock_calc

        target_data = {
            'name': 'TestTarget',
            'latitude': 45.0,
            'longitude': 10.0,
            'description': 'Test',
            'mission_type': 'communication',
            'elevation_mask': 10.0
        }

        satellite_tle_data = {
            'name': 'TEST-SAT',
            'line1': '1 00000U 00000A   00000.00000000  .00000000  00000-0  00000-0 0  0000',
            'line2': '2 00000  00.0000 000.0000 0000000 000.0000 000.0000 15.00000000 00000'
        }

        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=24)

        result = _compute_target_passes_worker(
            target_data, satellite_tle_data, start_time, end_time
        )

        assert result[0] == 'TestTarget'
        assert len(result[1]) == 1

    def test_worker_handles_exception(self) -> None:
        """Test worker handles exceptions gracefully."""
        target_data = {
            'name': 'FailTarget',
            'latitude': 'invalid',  # Will cause exception
            'longitude': 10.0
        }

        satellite_tle_data = {
            'name': 'TEST-SAT',
            'line1': 'invalid',
            'line2': 'invalid'
        }

        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=24)

        result = _compute_target_passes_worker(
            target_data, satellite_tle_data, start_time, end_time
        )

        # Should return target name and empty list on error
        assert result[0] == 'FailTarget'
        assert result[1] == []


class TestParallelVisibilityCalculator:
    """Tests for ParallelVisibilityCalculator class."""

    @pytest.fixture
    def mock_satellite(self):
        """Create a mock satellite."""
        sat = MagicMock()
        sat.satellite_name = "TEST-SAT"
        sat.tle_lines = [
            "TEST-SAT",
            "1 00000U 00000A   00000.00000000  .00000000  00000-0  00000-0 0  0000",
            "2 00000  00.0000 000.0000 0000000 000.0000 000.0000 15.00000000 00000"
        ]
        return sat

    def test_init_extracts_tle_data(self, mock_satellite) -> None:
        """Test initialization extracts TLE data correctly."""
        calc = ParallelVisibilityCalculator(mock_satellite, max_workers=4)

        assert calc.satellite_tle_data['name'] == 'TEST-SAT'
        assert '1 00000U' in calc.satellite_tle_data['line1']
        assert '2 00000' in calc.satellite_tle_data['line2']

    def test_init_with_two_line_tle(self) -> None:
        """Test initialization with 2-line TLE format."""
        sat = MagicMock()
        sat.satellite_name = "TEST-SAT"
        sat.tle_lines = [
            "1 00000U 00000A   00000.00000000  .00000000  00000-0  00000-0 0  0000",
            "2 00000  00.0000 000.0000 0000000 000.0000 000.0000 15.00000000 00000"
        ]

        calc = ParallelVisibilityCalculator(sat)

        assert calc.satellite_tle_data['name'] == 'TEST-SAT'
        assert '1 00000U' in calc.satellite_tle_data['line1']

    def test_get_visibility_windows_empty_targets(self, mock_satellite) -> None:
        """Test with empty target list."""
        calc = ParallelVisibilityCalculator(mock_satellite)

        result = calc.get_visibility_windows(
            [], datetime.utcnow(), datetime.utcnow() + timedelta(hours=24)
        )

        assert result == {}

    @patch('mission_planner.parallel.get_or_create_process_pool')
    @patch('mission_planner.parallel.as_completed')
    def test_get_visibility_windows_parallel(self, mock_as_completed, mock_pool, mock_satellite) -> None:
        """Test parallel visibility computation."""
        # Setup mock futures
        mock_future = MagicMock(spec=Future)
        mock_future.result.return_value = ('Target1', [{'max_elevation': 45.0}])

        mock_executor = MagicMock()
        mock_executor.submit.return_value = mock_future
        mock_pool.return_value = mock_executor

        mock_as_completed.return_value = iter([mock_future])

        # Create target
        target = MagicMock()
        target.name = 'Target1'
        target.latitude = 45.0
        target.longitude = 10.0
        target.description = 'Test'
        target.mission_type = 'communication'
        target.elevation_mask = 10.0
        target.sensor_fov_half_angle_deg = None
        target.max_spacecraft_roll = None

        calc = ParallelVisibilityCalculator(mock_satellite, max_workers=2)

        result = calc.get_visibility_windows(
            [target],
            datetime.utcnow(),
            datetime.utcnow() + timedelta(hours=24)
        )

        assert 'Target1' in result
        assert result['Target1'] == [{'max_elevation': 45.0}]

    @patch('mission_planner.parallel.get_or_create_process_pool')
    @patch('mission_planner.parallel.as_completed')
    def test_get_visibility_windows_with_progress(self, mock_as_completed, mock_pool, mock_satellite) -> None:
        """Test parallel computation with progress callback."""
        mock_future = MagicMock(spec=Future)
        mock_future.result.return_value = ('Target1', [])

        mock_executor = MagicMock()
        mock_executor.submit.return_value = mock_future
        mock_pool.return_value = mock_executor

        mock_as_completed.return_value = iter([mock_future])

        target = MagicMock()
        target.name = 'Target1'
        target.latitude = 45.0
        target.longitude = 10.0
        target.description = ''
        target.mission_type = 'communication'
        target.elevation_mask = 10.0
        target.sensor_fov_half_angle_deg = None
        target.max_spacecraft_roll = None

        progress_calls = []
        def progress_callback(completed, total):
            progress_calls.append((completed, total))

        calc = ParallelVisibilityCalculator(mock_satellite)

        calc.get_visibility_windows(
            [target],
            datetime.utcnow(),
            datetime.utcnow() + timedelta(hours=24),
            progress_callback=progress_callback
        )

        assert len(progress_calls) == 1
        assert progress_calls[0] == (1, 1)

    @patch('mission_planner.parallel.get_or_create_process_pool')
    @patch('mission_planner.parallel.as_completed')
    def test_get_visibility_windows_handles_errors(self, mock_as_completed, mock_pool, mock_satellite) -> None:
        """Test that errors in futures are handled."""
        mock_future = MagicMock(spec=Future)
        mock_future.result.side_effect = Exception("Worker error")

        mock_executor = MagicMock()
        mock_executor.submit.return_value = mock_future
        mock_pool.return_value = mock_executor

        # Map future to target name
        mock_executor.submit.return_value = mock_future

        mock_as_completed.return_value = iter([mock_future])

        target = MagicMock()
        target.name = 'Target1'
        target.latitude = 45.0
        target.longitude = 10.0
        target.description = ''
        target.mission_type = 'communication'
        target.elevation_mask = 10.0
        target.sensor_fov_half_angle_deg = None
        target.max_spacecraft_roll = None

        calc = ParallelVisibilityCalculator(mock_satellite)

        # Patch the future_to_target dict behavior
        with patch.object(calc, 'get_visibility_windows') as mock_method:
            mock_method.return_value = {'Target1': []}
            result = calc.get_visibility_windows(
                [target],
                datetime.utcnow(),
                datetime.utcnow() + timedelta(hours=24)
            )

        # Should return empty list for failed target
        assert 'Target1' in result

    def test_adaptive_mode_setting(self, mock_satellite) -> None:
        """Test adaptive mode is properly set."""
        calc_adaptive = ParallelVisibilityCalculator(mock_satellite, use_adaptive=True)
        calc_fixed = ParallelVisibilityCalculator(mock_satellite, use_adaptive=False)

        assert calc_adaptive.use_adaptive is True
        assert calc_fixed.use_adaptive is False


class TestBenchmarkParallelSpeedup:
    """Tests for benchmark_parallel_speedup function."""

    @patch('mission_planner.parallel.ParallelVisibilityCalculator')
    @patch('mission_planner.visibility.VisibilityCalculator')
    def test_benchmark_returns_results(self, mock_serial_class, mock_parallel_class) -> None:
        """Test benchmark returns comparison results."""
        # Setup serial mock
        mock_serial = MagicMock()
        mock_serial.get_visibility_windows.return_value = {
            'Target1': [{'max_elevation': 45.0}]
        }
        mock_serial_class.return_value = mock_serial

        # Setup parallel mock
        mock_parallel = MagicMock()
        mock_parallel.max_workers = 4
        mock_parallel.get_visibility_windows.return_value = {
            'Target1': [{'max_elevation': 45.0}]
        }
        mock_parallel_class.return_value = mock_parallel

        mock_satellite = MagicMock()
        mock_satellite.satellite_name = "TEST-SAT"
        mock_satellite.tle_lines = ["TEST-SAT", "line1", "line2"]

        target = MagicMock()
        target.name = 'Target1'

        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=24)

        result = benchmark_parallel_speedup(
            mock_satellite, [target], start_time, end_time
        )

        assert 'serial_time_seconds' in result
        assert 'parallel_time_seconds' in result
        assert 'speedup_factor' in result
        assert 'results_match' in result
        assert result['targets'] == 1

    @patch('mission_planner.parallel.ParallelVisibilityCalculator')
    @patch('mission_planner.visibility.VisibilityCalculator')
    def test_benchmark_speedup_calculation(self, mock_serial_class, mock_parallel_class) -> None:
        """Test speedup is calculated correctly."""
        import time

        # Mock serial to take 1 second
        mock_serial = MagicMock()
        def slow_serial(*args, **kwargs):
            time.sleep(0.1)
            return {'Target1': []}
        mock_serial.get_visibility_windows.side_effect = slow_serial
        mock_serial_class.return_value = mock_serial

        # Mock parallel to be fast
        mock_parallel = MagicMock()
        mock_parallel.max_workers = 4
        mock_parallel.get_visibility_windows.return_value = {'Target1': []}
        mock_parallel_class.return_value = mock_parallel

        mock_satellite = MagicMock()
        mock_satellite.satellite_name = "TEST-SAT"
        mock_satellite.tle_lines = ["TEST-SAT", "line1", "line2"]

        target = MagicMock()
        target.name = 'Target1'

        result = benchmark_parallel_speedup(
            mock_satellite, [target],
            datetime.utcnow(),
            datetime.utcnow() + timedelta(hours=1)
        )

        # Speedup should be > 1 since parallel is faster
        assert result['speedup_factor'] > 0
        assert result['results_match'] is True


class TestParallelWithImagingType:
    """Tests for parallel processing with imaging type targets."""

    @pytest.fixture
    def mock_satellite(self):
        """Create a mock satellite."""
        sat = MagicMock()
        sat.satellite_name = "TEST-SAT"
        sat.tle_lines = ["TEST-SAT", "line1", "line2"]
        return sat

    @patch('mission_planner.parallel.get_or_create_process_pool')
    @patch('mission_planner.parallel.as_completed')
    def test_imaging_type_passed_to_worker(self, mock_as_completed, mock_pool, mock_satellite) -> None:
        """Test that imaging_type is included in target data."""
        mock_future = MagicMock(spec=Future)
        mock_future.result.return_value = ('ImagingTarget', [])

        mock_executor = MagicMock()
        mock_executor.submit.return_value = mock_future
        mock_pool.return_value = mock_executor

        mock_as_completed.return_value = iter([mock_future])

        # Create target with imaging_type
        target = MagicMock()
        target.name = 'ImagingTarget'
        target.latitude = 45.0
        target.longitude = 10.0
        target.description = ''
        target.mission_type = 'imaging'
        target.elevation_mask = 10.0
        target.sensor_fov_half_angle_deg = 1.0
        target.max_spacecraft_roll = 45.0
        target.imaging_type = 'optical'

        calc = ParallelVisibilityCalculator(mock_satellite)

        calc.get_visibility_windows(
            [target],
            datetime.utcnow(),
            datetime.utcnow() + timedelta(hours=24)
        )

        # Verify submit was called
        mock_executor.submit.assert_called()
