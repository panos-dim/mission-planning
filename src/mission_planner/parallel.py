"""
Parallel processing utilities for mission planning computations.

This module provides parallel processing capabilities for CPU-intensive
mission planning tasks, enabling significant speedups on multi-core systems.
"""

from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict, Any, Callable, Optional, Tuple
from datetime import datetime
import logging
import os
import multiprocessing as mp
from functools import partial

logger = logging.getLogger(__name__)

# Global process pool for reuse (avoids repeated spawn overhead)
_process_pool: Optional[ProcessPoolExecutor] = None
_pool_max_workers: Optional[int] = None


def get_optimal_workers(max_workers: Optional[int] = None, num_targets: int = 0) -> int:
    """
    Determine optimal number of worker processes.
    
    Args:
        max_workers: Maximum number of workers (None = auto-detect)
        num_targets: Number of targets to process (used for optimization)
        
    Returns:
        Optimal number of workers for parallel processing
    """
    cpu_count = os.cpu_count() or 4
    
    if max_workers is not None:
        return min(max_workers, cpu_count)
    
    # Optimize worker count based on workload
    # For small workloads, fewer workers reduce overhead
    if num_targets > 0:
        # Don't spawn more workers than targets
        optimal = min(num_targets, cpu_count)
        # For small workloads (<20 targets), use 75% of cores
        if num_targets < 20:
            optimal = max(1, int(cpu_count * 0.75))
        return optimal
    
    # Default: use all available cores
    return cpu_count


def get_or_create_process_pool(max_workers: int) -> ProcessPoolExecutor:
    """
    Get or create a reusable process pool to avoid repeated spawn overhead.
    
    Args:
        max_workers: Number of worker processes
        
    Returns:
        ProcessPoolExecutor instance
    """
    global _process_pool, _pool_max_workers
    
    # Reuse existing pool if same size
    if _process_pool is not None and _pool_max_workers == max_workers:
        return _process_pool
    
    # Shutdown old pool if different size
    if _process_pool is not None:
        _process_pool.shutdown(wait=False)
    
    # Create new pool with mp_context='fork' on Unix systems for faster startup
    # Note: 'fork' is faster but may have issues with certain libraries
    # Fall back to 'spawn' if 'fork' unavailable
    mp_context = None
    if hasattr(mp, 'get_context'):
        try:
            mp_context = mp.get_context('fork')
            logger.debug("Using 'fork' context for faster worker startup")
        except ValueError:
            # 'fork' not available (Windows), use default
            logger.debug("'fork' context not available, using default 'spawn'")
            pass
    
    _process_pool = ProcessPoolExecutor(
        max_workers=max_workers,
        mp_context=mp_context
    )
    _pool_max_workers = max_workers
    
    return _process_pool


def cleanup_process_pool():
    """
    Clean up the global process pool on shutdown.
    
    Call this when the application is shutting down to gracefully
    terminate worker processes.
    """
    global _process_pool, _pool_max_workers
    
    if _process_pool is not None:
        logger.info("Shutting down process pool...")
        _process_pool.shutdown(wait=True)
        _process_pool = None
        _pool_max_workers = None


def _compute_target_passes_worker(
    target_data: Dict[str, Any],
    satellite_tle_data: Dict[str, Any],
    start_time: datetime,
    end_time: datetime,
    time_step_seconds: int = 1,
    use_adaptive: bool = False
) -> Tuple[str, List[Any]]:
    """
    Worker function to compute passes for a single target.
    
    This function is designed to be pickled and run in a separate process.
    
    Args:
        target_data: Dictionary with target information
        satellite_tle_data: Dictionary with satellite TLE data
        start_time: Start of analysis window
        end_time: End of analysis window
        time_step_seconds: Time step for calculations (fixed-step mode only)
        use_adaptive: Enable adaptive time-stepping algorithm
        
    Returns:
        Tuple of (target_name, list_of_passes)
    """
    try:
        # Import here to avoid pickling issues
        from mission_planner.orbit import SatelliteOrbit
        from mission_planner.targets import GroundTarget
        from mission_planner.visibility import VisibilityCalculator
        import tempfile
        import os
        
        # Recreate satellite orbit from TLE data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tle', delete=False) as f:
            f.write(f"{satellite_tle_data['name']}\n")
            f.write(f"{satellite_tle_data['line1']}\n")
            f.write(f"{satellite_tle_data['line2']}\n")
            tle_file = f.name
        
        try:
            satellite = SatelliteOrbit.from_tle_file(
                tle_file, 
                satellite_name=satellite_tle_data['name']
            )
            
            # Recreate target from data
            target = GroundTarget(
                name=target_data['name'],
                latitude=target_data['latitude'],
                longitude=target_data['longitude'],
                description=target_data.get('description', ''),
                mission_type=target_data.get('mission_type', 'communication'),
                elevation_mask=target_data.get('elevation_mask', 10.0),
                sensor_fov_half_angle_deg=target_data.get('sensor_fov_half_angle_deg'),
                max_spacecraft_roll=target_data.get('max_spacecraft_roll')
            )
            
            # Set imaging_type if applicable
            if 'imaging_type' in target_data:
                target.imaging_type = target_data['imaging_type']
            
            # Create visibility calculator
            from mission_planner.visibility import VisibilityCalculator
            calc = VisibilityCalculator(satellite, use_adaptive=use_adaptive)
            
            # Find passes (adaptive or fixed-step based on flag)
            passes = calc.find_passes(target, start_time, end_time, time_step_seconds)
            
            # Convert PassDetails to dictionaries for serialization
            passes_dict = [p.to_dict() for p in passes]
            
            return (target_data['name'], passes_dict)
            
        finally:
            # Clean up temp file
            if os.path.exists(tle_file):
                os.unlink(tle_file)
        
    except Exception as e:
        logger.error(f"Error computing passes for target {target_data['name']}: {e}")
        return (target_data['name'], [])


class ParallelVisibilityCalculator:
    """
    Parallel implementation of visibility calculations.
    
    Distributes target analysis across multiple CPU cores for significant
    speedup on systems with multiple cores.
    """
    
    def __init__(self, satellite, max_workers: Optional[int] = None, use_adaptive: bool = False):
        """
        Initialize parallel visibility calculator.
        
        Args:
            satellite: SatelliteOrbit instance
            max_workers: Maximum worker processes (None = auto-detect)
            use_adaptive: Enable adaptive time-stepping algorithm
        """
        self.satellite = satellite
        self.max_workers = max_workers  # Will be optimized based on target count
        self.use_adaptive = use_adaptive
        
        # Extract TLE data for serialization
        # tle_lines format: [name, line1, line2] or [line1, line2]
        if len(satellite.tle_lines) == 3:
            # Format: [name, line1, line2]
            self.satellite_tle_data = {
                'name': satellite.satellite_name,
                'line1': satellite.tle_lines[1],
                'line2': satellite.tle_lines[2]
            }
        else:
            # Format: [line1, line2]
            self.satellite_tle_data = {
                'name': satellite.satellite_name,
                'line1': satellite.tle_lines[0],
                'line2': satellite.tle_lines[1]
            }
        
        method = "adaptive" if use_adaptive else "fixed-step"
        # Worker count will be optimized based on target count at runtime
        cpu_count = os.cpu_count() or 4
        max_display = self.max_workers if self.max_workers else cpu_count
        logger.info(f"Initialized ParallelVisibilityCalculator (max {max_display} workers, method: {method})")
    
    def get_visibility_windows(
        self,
        targets: List[Any],
        start_time: datetime,
        end_time: datetime,
        time_step_seconds: int = 1,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, List[Any]]:
        """
        Compute visibility windows for multiple targets in parallel.
        
        Args:
            targets: List of GroundTarget objects
            start_time: Start of analysis window
            end_time: End of analysis window
            time_step_seconds: Time step for calculations (fixed-step mode only)
            progress_callback: Optional callback(completed, total) for progress
            
        Returns:
            Dictionary mapping target names to lists of PassDetails dicts
        """
        if not targets:
            return {}
        
        # Optimize worker count based on target count
        optimal_workers = get_optimal_workers(self.max_workers, len(targets))
        
        # Serialize target data
        target_data_list = []
        for target in targets:
            target_dict = {
                'name': target.name,
                'latitude': target.latitude,
                'longitude': target.longitude,
                'description': target.description,
                'mission_type': target.mission_type,
                'elevation_mask': target.elevation_mask,
                'sensor_fov_half_angle_deg': target.sensor_fov_half_angle_deg,
                'max_spacecraft_roll': target.max_spacecraft_roll
            }
            
            # Include imaging_type if available
            if hasattr(target, 'imaging_type'):
                target_dict['imaging_type'] = target.imaging_type
            
            target_data_list.append(target_dict)
        
        # Create partial function with fixed parameters
        worker_func = partial(
            _compute_target_passes_worker,
            satellite_tle_data=self.satellite_tle_data,
            start_time=start_time,
            end_time=end_time,
            time_step_seconds=time_step_seconds,
            use_adaptive=self.use_adaptive
        )
        
        # Execute in parallel
        results = {}
        completed = 0
        
        logger.info(f"Computing passes for {len(targets)} targets using {optimal_workers} workers")
        
        # Use persistent pool to avoid spawn overhead on repeated calls
        executor = get_or_create_process_pool(optimal_workers)
        
        # Submit all tasks
        future_to_target = {
            executor.submit(worker_func, target_data): target_data['name']
            for target_data in target_data_list
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_target):
            target_name = future_to_target[future]
            
            try:
                target_name, passes = future.result()
                results[target_name] = passes
                completed += 1
                
                logger.debug(f"Completed {completed}/{len(targets)}: {target_name} ({len(passes)} passes)")
                
                # Call progress callback if provided
                if progress_callback:
                    progress_callback(completed, len(targets))
                    
            except Exception as e:
                logger.error(f"Error processing target {target_name}: {e}")
                results[target_name] = []
                completed += 1
        
        total_passes = sum(len(passes) for passes in results.values())
        logger.info(f"Parallel computation complete: {total_passes} total passes across {len(targets)} targets")
        
        return results


def benchmark_parallel_speedup(
    satellite,
    targets: List[Any],
    start_time: datetime,
    end_time: datetime,
    time_step_seconds: int = 1
) -> Dict[str, Any]:
    """
    Benchmark serial vs parallel performance.
    
    Args:
        satellite: SatelliteOrbit instance
        targets: List of GroundTarget objects
        start_time: Start of analysis window
        end_time: End of analysis window
        time_step_seconds: Time step for calculations
        
    Returns:
        Dictionary with benchmark results
    """
    import time
    from mission_planner.visibility import VisibilityCalculator
    
    logger.info(f"Benchmarking with {len(targets)} targets...")
    
    # Serial execution
    serial_calc = VisibilityCalculator(satellite)
    
    start = time.time()
    serial_results = serial_calc.get_visibility_windows(targets, start_time, end_time)
    serial_time = time.time() - start
    
    serial_passes = sum(len(passes) for passes in serial_results.values())
    
    logger.info(f"Serial execution: {serial_time:.2f}s ({serial_passes} passes)")
    
    # Parallel execution
    parallel_calc = ParallelVisibilityCalculator(satellite)
    
    start = time.time()
    parallel_results = parallel_calc.get_visibility_windows(targets, start_time, end_time, time_step_seconds)
    parallel_time = time.time() - start
    
    parallel_passes = sum(len(passes) for passes in parallel_results.values())
    
    logger.info(f"Parallel execution: {parallel_time:.2f}s ({parallel_passes} passes)")
    
    # Calculate speedup
    speedup = serial_time / parallel_time if parallel_time > 0 else 0
    
    benchmark_results = {
        'targets': len(targets),
        'serial_time_seconds': round(serial_time, 2),
        'parallel_time_seconds': round(parallel_time, 2),
        'speedup_factor': round(speedup, 2),
        'workers': parallel_calc.max_workers,
        'serial_passes': serial_passes,
        'parallel_passes': parallel_passes,
        'results_match': serial_passes == parallel_passes
    }
    
    logger.info(f"Speedup: {speedup:.2f}x with {parallel_calc.max_workers} workers")
    
    return benchmark_results
