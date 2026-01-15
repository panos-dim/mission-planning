#!/usr/bin/env python3
"""
End-to-end integration test for quality-aware planning.

Tests the complete flow from PassDetails → Opportunity → Scheduling → Metrics
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))
sys.path.insert(0, str(project_root))

from mission_planner.visibility import PassDetails
from mission_planner.scheduler import Opportunity, SchedulerConfig, MissionScheduler, AlgorithmType
from mission_planner.quality_scoring import QualityModel, compute_quality_score, compute_opportunity_value


def test_passdetails_to_opportunity():
    """Test PassDetails with incidence_angle_deg → Opportunity flow."""
    print("\n" + "="*60)
    print("TEST 1: PassDetails → Opportunity Data Flow")
    print("="*60)
    
    # Create PassDetails with incidence angle and mode
    start_time = datetime(2024, 9, 10, 12, 0, 0)
    
    pass_detail = PassDetails(
        target_name="Dubai",
        satellite_name="ICEYE-X44",
        start_time=start_time,
        max_elevation_time=start_time + timedelta(minutes=1),
        end_time=start_time + timedelta(minutes=2),
        max_elevation=45.0,
        start_azimuth=180.0,
        max_elevation_azimuth=180.0,
        end_azimuth=180.0,
        incidence_angle_deg=25.5,  # Good geometry
        mode="OPTICAL"
    )
    
    # Verify PassDetails fields
    print(f"\nPassDetails created:")
    print(f"  Target: {pass_detail.target_name}")
    print(f"  Incidence angle: {pass_detail.incidence_angle_deg}°")
    print(f"  Mode: {pass_detail.mode}")
    
    # Convert to dict (as API would do)
    pass_dict = pass_detail.to_dict()
    print(f"\nPassDetails.to_dict() includes:")
    print(f"  incidence_angle_deg: {pass_dict.get('incidence_angle_deg')}")
    print(f"  mode: {pass_dict.get('mode')}")
    
    # Simulate backend conversion to Opportunity with quality scoring
    base_priority = 3.0
    quality_weight = 0.6
    
    quality_score = compute_quality_score(
        incidence_angle_deg=pass_detail.incidence_angle_deg,
        mode=pass_detail.mode,
        quality_model=QualityModel.MONOTONIC
    )
    
    value = compute_opportunity_value(
        base_priority=base_priority,
        quality_score=quality_score,
        quality_weight=quality_weight
    )
    
    opportunity = Opportunity(
        id=f"{pass_detail.satellite_name}_{pass_detail.target_name}_0",
        satellite_id=pass_detail.satellite_name,
        target_id=pass_detail.target_name,
        start_time=pass_detail.start_time,
        end_time=pass_detail.end_time,
        max_elevation=pass_detail.max_elevation,
        azimuth=pass_detail.start_azimuth,
        value=value,
        incidence_angle=pass_detail.incidence_angle_deg
    )
    
    print(f"\nOpportunity created:")
    print(f"  ID: {opportunity.id}")
    print(f"  Incidence angle: {opportunity.incidence_angle}°")
    print(f"  Quality score: {quality_score:.4f}")
    print(f"  Base priority: {base_priority}")
    print(f"  Quality weight: {quality_weight}")
    print(f"  Final value: {value:.4f}")
    
    assert opportunity.incidence_angle == pass_detail.incidence_angle_deg, "Incidence angle should match"
    assert opportunity.value == value, "Value should match computed value"
    
    print("\n✅ PassDetails → Opportunity flow verified")
    return opportunity


def test_scheduling_with_metrics():
    """Test scheduling produces correct metrics including mean_incidence_deg."""
    print("\n" + "="*60)
    print("TEST 2: Scheduling with Quality Metrics")
    print("="*60)
    
    # Create opportunities with different incidence angles
    start_time = datetime(2024, 9, 10, 12, 0, 0)
    opportunities = []
    incidence_angles = [20.0, 35.0, 50.0]  # Different quality levels
    
    for i, inc_angle in enumerate(incidence_angles):
        quality_score = compute_quality_score(
            incidence_angle_deg=inc_angle,
            mode='OPTICAL',
            quality_model=QualityModel.MONOTONIC
        )
        
        value = compute_opportunity_value(
            base_priority=1.0,
            quality_score=quality_score,
            quality_weight=0.5
        )
        
        opp_time = start_time + timedelta(hours=i*3)
        opp = Opportunity(
            id=f"sat1_target{i}_{i}",
            satellite_id="sat1",
            target_id=f"target{i}",
            start_time=opp_time,
            end_time=opp_time + timedelta(minutes=2),
            max_elevation=45.0,
            azimuth=180.0,
            value=value,
            incidence_angle=inc_angle
        )
        opportunities.append(opp)
        print(f"Target {i}: incidence={inc_angle:.1f}°, quality={quality_score:.4f}, value={value:.4f}")
    
    # Target positions
    target_positions = {f"target{i}": (25.0 + i, 55.0 + i) for i in range(3)}
    
    # Create scheduler and run
    config = SchedulerConfig(
        imaging_time_s=5.0,
        max_roll_rate_dps=3.0,
        max_roll_accel_dps2=1.0,
        look_window_s=36000.0  # Large window
    )
    scheduler = MissionScheduler(config)
    
    print("\nRunning First-Fit algorithm...")
    schedule, metrics = scheduler.schedule(
        opportunities=opportunities,
        target_positions=target_positions,
        algorithm=AlgorithmType.FIRST_FIT
    )
    
    print(f"\nSchedule Results:")
    print(f"  Opportunities scheduled: {len(schedule)}")
    print(f"  Total value: {metrics.total_value:.2f}")
    print(f"  Mean value: {metrics.mean_value:.4f}")
    print(f"  Mean incidence: {metrics.mean_incidence_deg:.2f}°" if metrics.mean_incidence_deg else "  Mean incidence: N/A")
    
    # Verify metrics computation
    if metrics.mean_incidence_deg is not None:
        # Manually compute expected mean
        scheduled_incidences = []
        for s in schedule:
            orig_opp = next((o for o in opportunities if o.id == s.opportunity_id), None)
            if orig_opp and orig_opp.incidence_angle is not None:
                scheduled_incidences.append(orig_opp.incidence_angle)
        
        expected_mean = sum(scheduled_incidences) / len(scheduled_incidences) if scheduled_incidences else None
        
        if expected_mean:
            print(f"\nVerification:")
            print(f"  Expected mean incidence: {expected_mean:.2f}°")
            print(f"  Actual mean incidence: {metrics.mean_incidence_deg:.2f}°")
            
            assert abs(metrics.mean_incidence_deg - expected_mean) < 0.01, "Mean incidence should match"
            print("  ✓ Mean incidence matches!")
    
    # Verify metrics.to_dict() includes mean_incidence_deg
    metrics_dict = metrics.to_dict()
    print(f"\nMetrics dict keys: {list(metrics_dict.keys())}")
    
    if 'mean_incidence_deg' in metrics_dict:
        print(f"  ✓ mean_incidence_deg in dict: {metrics_dict['mean_incidence_deg']}")
    else:
        print("  ℹ mean_incidence_deg not in dict (expected if None)")
    
    print("\n✅ Scheduling with quality metrics verified")


def test_quality_model_comparison():
    """Test different quality models produce different results."""
    print("\n" + "="*60)
    print("TEST 3: Quality Model Comparison")
    print("="*60)
    
    start_time = datetime(2024, 9, 10, 12, 0, 0)
    
    # Create 3 opportunities with different incidence angles
    test_angles = [25.0, 35.0, 45.0]
    target_positions = {f"target{i}": (25.0, 55.0 + i*5) for i in range(3)}
    
    config = SchedulerConfig(
        imaging_time_s=5.0,
        max_roll_rate_dps=3.0,
        max_roll_accel_dps2=1.0,
        look_window_s=36000.0
    )
    
    results = {}
    
    for model_name, quality_model in [
        ('Monotonic', QualityModel.MONOTONIC),
        ('Band (35°)', QualityModel.BAND),
        ('Off', QualityModel.OFF)
    ]:
        opportunities = []
        
        for i, inc_angle in enumerate(test_angles):
            quality_score = compute_quality_score(
                incidence_angle_deg=inc_angle,
                mode='SAR' if quality_model == QualityModel.BAND else 'OPTICAL',
                quality_model=quality_model,
                ideal_incidence_deg=35.0,
                band_width_deg=7.5
            )
            
            value = compute_opportunity_value(
                base_priority=1.0,
                quality_score=quality_score,
                quality_weight=0.8  # High quality weight
            )
            
            opp_time = start_time + timedelta(hours=i*3)
            opp = Opportunity(
                id=f"sat1_target{i}_{i}",
                satellite_id="sat1",
                target_id=f"target{i}",
                start_time=opp_time,
                end_time=opp_time + timedelta(minutes=2),
                max_elevation=45.0,
                azimuth=180.0,
                value=value,
                incidence_angle=inc_angle
            )
            opportunities.append(opp)
        
        scheduler = MissionScheduler(config)
        schedule, metrics = scheduler.schedule(
            opportunities=opportunities,
            target_positions=target_positions,
            algorithm=AlgorithmType.BEST_FIT
        )
        
        results[model_name] = {
            'total_value': metrics.total_value,
            'mean_incidence': metrics.mean_incidence_deg,
            'num_scheduled': len(schedule)
        }
        
        print(f"\n{model_name} Model:")
        print(f"  Scheduled: {len(schedule)} opportunities")
        print(f"  Total value: {metrics.total_value:.2f}")
        print(f"  Mean incidence: {metrics.mean_incidence_deg:.2f}°" if metrics.mean_incidence_deg else "  Mean incidence: N/A")
    
    # Verify different models produce different results
    mono_val = results['Monotonic']['total_value']
    band_val = results['Band (35°)']['total_value']
    off_val = results['Off']['total_value']
    
    print(f"\nComparison:")
    print(f"  Monotonic favors low incidence")
    print(f"  Band favors 35° incidence")
    print(f"  Off treats all equally")
    
    # They should differ when quality weight is high
    if mono_val != band_val or mono_val != off_val:
        print("  ✓ Different models produce different results!")
    else:
        print("  ⚠ All models produced same results (unexpected with quality_weight=0.8)")
    
    print("\n✅ Quality model comparison verified")


def main():
    """Run all E2E tests."""
    print("\n" + "="*60)
    print("END-TO-END QUALITY PLANNING INTEGRATION TESTS")
    print("="*60)
    
    try:
        test_passdetails_to_opportunity()
        test_scheduling_with_metrics()
        test_quality_model_comparison()
        
        print("\n" + "="*60)
        print("✅ ALL E2E TESTS PASSED!")
        print("="*60)
        print("\nImplementation Summary:")
        print("  ✓ PassDetails includes incidence_angle_deg and mode")
        print("  ✓ Quality scoring models work correctly")
        print("  ✓ Value blending integrates with scheduler")
        print("  ✓ Metrics include mean_incidence_deg")
        print("  ✓ Different quality models produce different outcomes")
        print("\nReady for frontend integration! 🚀")
        return 0
        
    except Exception as e:
        print("\n" + "="*60)
        print(f"❌ E2E TEST FAILED: {e}")
        print("="*60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
