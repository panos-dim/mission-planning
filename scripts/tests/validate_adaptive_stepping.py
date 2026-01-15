#!/usr/bin/env python3
"""
Validation script for adaptive time-stepping algorithm.

This script compares the adaptive algorithm against the fixed-step baseline to verify:
1. Accuracy: AOS/LOS times match within ±1 second
2. Completeness: No missed windows
3. Performance: Speedup of 2-4× over fixed-step
4. Stability: Works for both OPTICAL and SAR missions

Usage:
    python scripts/validate_adaptive_stepping.py
"""

import sys
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mission_planner.orbit import SatelliteOrbit
from mission_planner.targets import GroundTarget
from mission_planner.visibility import VisibilityCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_satellite():
    """Create test satellite from ICEYE-X44 TLE data."""
    tle_line1 = "1 58691U 23188A   25215.50000000  .00001234  00000+0  12345-3 0  9999"
    tle_line2 = "2 58691  97.4445 180.0000 0001234  90.0000 270.0000 15.19000000123456"
    
    # Use data directory TLE if available
    data_file = Path(__file__).parent.parent / "data" / "active_satellites.tle"
    if data_file.exists():
        logger.info(f"Loading satellite from {data_file}")
        return SatelliteOrbit.from_tle_file(str(data_file), satellite_name="ICEYE-X44")
    else:
        logger.info("Using embedded TLE data")
        return SatelliteOrbit.from_tle(tle_line1, tle_line2, satellite_name="ICEYE-X44")


def create_test_targets():
    """Create diverse test targets covering different scenarios."""
    targets = [
        # Communication mission - UAE
        GroundTarget(
            name="Space42_UAE",
            latitude=24.4444,
            longitude=54.8333,
            elevation_mask=10.0,
            mission_type='communication',
            description="UAE ground station"
        ),
        # Optical imaging mission - high latitude
        GroundTarget(
            name="Norway_Optical",
            latitude=69.6492,
            longitude=18.9553,
            elevation_mask=10.0,
            mission_type='imaging',
            pointing_angle=45.0,
            description="Tromsø, Norway - optical imaging"
        ),
        # SAR imaging mission - equatorial
        GroundTarget(
            name="Singapore_SAR",
            latitude=1.3521,
            longitude=103.8198,
            elevation_mask=10.0,
            mission_type='imaging',
            pointing_angle=35.0,
            description="Singapore - SAR imaging"
        ),
        # High elevation mask - challenging
        GroundTarget(
            name="Australia_High_Mask",
            latitude=-33.8688,
            longitude=151.2093,
            elevation_mask=30.0,
            mission_type='communication',
            description="Sydney - high elevation mask"
        ),
    ]
    
    # Set imaging type for imaging missions
    targets[1].imaging_type = 'optical'
    targets[2].imaging_type = 'sar'
    
    return targets


def compare_passes(baseline_passes, adaptive_passes, tolerance_seconds=1.0):
    """
    Compare two sets of passes for accuracy.
    
    Args:
        baseline_passes: Passes from fixed-step method
        adaptive_passes: Passes from adaptive method
        tolerance_seconds: Maximum allowed time difference
        
    Returns:
        Dictionary with comparison statistics
    """
    stats = {
        'baseline_count': len(baseline_passes),
        'adaptive_count': len(adaptive_passes),
        'matched': 0,
        'missed': 0,
        'false_positives': 0,
        'max_aos_diff': 0.0,
        'max_los_diff': 0.0,
        'avg_aos_diff': 0.0,
        'avg_los_diff': 0.0,
        'accuracy_ok': True
    }
    
    if len(baseline_passes) == 0 and len(adaptive_passes) == 0:
        return stats
    
    # Match passes by proximity
    matched_pairs = []
    unmatched_baseline = list(baseline_passes)
    unmatched_adaptive = list(adaptive_passes)
    
    for b_pass in baseline_passes:
        best_match = None
        best_diff = float('inf')
        
        for a_pass in unmatched_adaptive:
            # Calculate time difference at start
            diff = abs((a_pass.start_time - b_pass.start_time).total_seconds())
            if diff < best_diff and diff < 60:  # Must be within 60 seconds to match
                best_diff = diff
                best_match = a_pass
        
        if best_match:
            matched_pairs.append((b_pass, best_match))
            unmatched_adaptive.remove(best_match)
            unmatched_baseline.remove(b_pass)
    
    stats['matched'] = len(matched_pairs)
    stats['missed'] = len(unmatched_baseline)
    stats['false_positives'] = len(unmatched_adaptive)
    
    # Calculate timing differences for matched pairs
    if matched_pairs:
        aos_diffs = []
        los_diffs = []
        
        for b_pass, a_pass in matched_pairs:
            aos_diff = abs((a_pass.start_time - b_pass.start_time).total_seconds())
            los_diff = abs((a_pass.end_time - b_pass.end_time).total_seconds())
            
            aos_diffs.append(aos_diff)
            los_diffs.append(los_diff)
            
            # Check if within tolerance
            if aos_diff > tolerance_seconds or los_diff > tolerance_seconds:
                stats['accuracy_ok'] = False
        
        stats['max_aos_diff'] = max(aos_diffs)
        stats['max_los_diff'] = max(los_diffs)
        stats['avg_aos_diff'] = sum(aos_diffs) / len(aos_diffs)
        stats['avg_los_diff'] = sum(los_diffs) / len(los_diffs)
    
    return stats


def validate_target(satellite, target, start_time, duration_hours=24):
    """
    Validate adaptive algorithm for a single target.
    
    Args:
        satellite: SatelliteOrbit instance
        target: GroundTarget instance
        start_time: Start time for validation
        duration_hours: Duration of validation window
        
    Returns:
        Dictionary with validation results
    """
    end_time = start_time + timedelta(hours=duration_hours)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Validating: {target.name} ({target.mission_type})")
    logger.info(f"Period: {start_time.strftime('%Y-%m-%d %H:%M')} - "
                f"{end_time.strftime('%Y-%m-%d %H:%M')} UTC ({duration_hours}h)")
    logger.info(f"{'='*60}")
    
    # Baseline: Fixed-step method (1-second steps)
    logger.info("Running baseline (fixed-step, 1s resolution)...")
    calc_baseline = VisibilityCalculator(satellite, use_adaptive=False)
    
    start = time.time()
    baseline_passes = calc_baseline.find_passes(target, start_time, end_time, time_step_seconds=1)
    baseline_time = time.time() - start
    
    logger.info(f"  ✓ Found {len(baseline_passes)} passes in {baseline_time:.2f}s")
    
    # Adaptive method
    logger.info("Running adaptive method...")
    calc_adaptive = VisibilityCalculator(satellite, use_adaptive=True)
    
    start = time.time()
    adaptive_passes = calc_adaptive.find_passes(target, start_time, end_time)
    adaptive_time = time.time() - start
    
    logger.info(f"  ✓ Found {len(adaptive_passes)} passes in {adaptive_time:.2f}s")
    
    # Compare results
    comparison = compare_passes(baseline_passes, adaptive_passes, tolerance_seconds=1.0)
    
    # Calculate speedup
    speedup = baseline_time / adaptive_time if adaptive_time > 0 else 0
    
    # Print results
    logger.info(f"\nResults:")
    logger.info(f"  Pass Count:        Baseline={comparison['baseline_count']}, "
                f"Adaptive={comparison['adaptive_count']}")
    logger.info(f"  Matched:           {comparison['matched']}")
    logger.info(f"  Missed:            {comparison['missed']}")
    logger.info(f"  False Positives:   {comparison['false_positives']}")
    
    if comparison['matched'] > 0:
        logger.info(f"  AOS Accuracy:      avg={comparison['avg_aos_diff']:.3f}s, "
                    f"max={comparison['max_aos_diff']:.3f}s")
        logger.info(f"  LOS Accuracy:      avg={comparison['avg_los_diff']:.3f}s, "
                    f"max={comparison['max_los_diff']:.3f}s")
    
    logger.info(f"  Performance:       {speedup:.2f}× speedup ({baseline_time:.2f}s → {adaptive_time:.2f}s)")
    
    # Overall assessment
    passed = (
        comparison['matched'] == comparison['baseline_count'] and
        comparison['missed'] == 0 and
        comparison['false_positives'] == 0 and
        comparison['accuracy_ok'] and
        speedup >= 2.0
    )
    
    status = "✅ PASSED" if passed else "❌ FAILED"
    logger.info(f"\n  Status: {status}")
    
    return {
        'target': target.name,
        'mission_type': target.mission_type,
        'passed': passed,
        'speedup': speedup,
        'baseline_time': baseline_time,
        'adaptive_time': adaptive_time,
        'comparison': comparison
    }


def main():
    """Run validation suite."""
    logger.info("="*80)
    logger.info("ADAPTIVE TIME-STEPPING VALIDATION")
    logger.info("="*80)
    
    # Create test data
    logger.info("\nInitializing test data...")
    satellite = create_test_satellite()
    targets = create_test_targets()
    
    # Validation period: 24 hours starting from a known date
    start_time = datetime(2025, 8, 1, 0, 0, 0)
    
    logger.info(f"Satellite: {satellite.satellite_name}")
    logger.info(f"Targets: {len(targets)}")
    logger.info(f"Validation period: {start_time.strftime('%Y-%m-%d')} (24 hours)")
    
    # Run validation for each target
    results = []
    for target in targets:
        try:
            result = validate_target(satellite, target, start_time, duration_hours=24)
            results.append(result)
        except Exception as e:
            logger.error(f"Error validating {target.name}: {e}", exc_info=True)
            results.append({
                'target': target.name,
                'mission_type': target.mission_type,
                'passed': False,
                'error': str(e)
            })
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("VALIDATION SUMMARY")
    logger.info(f"{'='*80}")
    
    passed_count = sum(1 for r in results if r['passed'])
    total_count = len(results)
    
    logger.info(f"\nResults: {passed_count}/{total_count} targets passed")
    logger.info(f"\nDetails:")
    
    for result in results:
        status = "✅" if result['passed'] else "❌"
        speedup_str = f"{result['speedup']:.2f}×" if 'speedup' in result else "N/A"
        logger.info(f"  {status} {result['target']:30s} "
                    f"({result['mission_type']:15s}) Speedup: {speedup_str}")
    
    # Calculate average speedup
    speedups = [r['speedup'] for r in results if 'speedup' in r]
    if speedups:
        avg_speedup = sum(speedups) / len(speedups)
        logger.info(f"\nAverage speedup: {avg_speedup:.2f}×")
    
    # Overall pass/fail
    logger.info(f"\n{'='*80}")
    if passed_count == total_count:
        logger.info("✅ VALIDATION PASSED - Adaptive algorithm ready for deployment")
        return 0
    else:
        logger.info("❌ VALIDATION FAILED - Review failures above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
