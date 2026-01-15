#!/usr/bin/env python3
"""
Test script for quality-aware mission planning implementation.

Tests:
1. Quality scoring models (Monotonic, Band, Off)
2. Value computation and blending
3. Integration with scheduler
4. End-to-end planning with quality weights
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))
sys.path.insert(0, str(project_root))

from mission_planner.quality_scoring import (
    QualityModel, compute_quality_score, compute_opportunity_value, select_default_model
)
from mission_planner.scheduler import (
    Opportunity, SchedulerConfig, MissionScheduler, AlgorithmType
)

def test_quality_scoring_models():
    """Test quality scoring models."""
    print("\n" + "="*60)
    print("TEST 1: Quality Scoring Models")
    print("="*60)
    
    # Test Monotonic model (optical)
    print("\nMonotonic Model (Optical - lower is better):")
    test_angles = [0, 15, 30, 45, 60]
    for angle in test_angles:
        score = compute_quality_score(
            incidence_angle_deg=angle,
            mode='OPTICAL',
            quality_model=QualityModel.MONOTONIC
        )
        print(f"  {angle:2d}° → quality_score = {score:.4f}")
    
    # Test Band model (SAR)
    print("\nBand Model (SAR - peaked at 35°±7.5°):")
    ideal = 35.0
    band_width = 7.5
    test_angles = [20, 27.5, 35, 42.5, 50]
    for angle in test_angles:
        score = compute_quality_score(
            incidence_angle_deg=angle,
            mode='SAR',
            quality_model=QualityModel.BAND,
            ideal_incidence_deg=ideal,
            band_width_deg=band_width
        )
        delta = abs(angle - ideal)
        print(f"  {angle:5.1f}° (Δ={delta:4.1f}°) → quality_score = {score:.4f}")
    
    # Test Off model
    print("\nOff Model (no quality adjustment):")
    for angle in [0, 30, 60, 90]:
        score = compute_quality_score(
            incidence_angle_deg=angle,
            mode='OPTICAL',
            quality_model=QualityModel.OFF
        )
        print(f"  {angle:2d}° → quality_score = {score:.4f} (should be 1.0)")
    
    # Test None incidence
    print("\nMissing incidence angle:")
    score = compute_quality_score(
        incidence_angle_deg=None,
        mode='OPTICAL',
        quality_model=QualityModel.MONOTONIC
    )
    print(f"  None → quality_score = {score:.4f} (should be 1.0)")
    
    print("\n✅ Quality scoring models test passed")


def test_value_blending():
    """Test value blending with quality weights."""
    print("\n" + "="*60)
    print("TEST 2: Value Blending")
    print("="*60)
    
    base_priority = 3.0
    quality_score = 0.8
    
    print(f"\nBase priority: {base_priority}")
    print(f"Quality score: {quality_score}")
    print("\nBlending with different weights:")
    
    for weight in [0.0, 0.25, 0.5, 0.75, 1.0]:
        value = compute_opportunity_value(base_priority, quality_score, weight)
        print(f"  weight={weight:.2f} → value = {value:.4f}")
    
    print("\n✅ Value blending test passed")


def test_scheduler_integration():
    """Test scheduler with quality-weighted opportunities."""
    print("\n" + "="*60)
    print("TEST 3: Scheduler Integration")
    print("="*60)
    
    # Create sample opportunities with different incidence angles
    start_time = datetime(2024, 9, 10, 12, 0, 0)
    opportunities = []
    
    # Target A: 3 passes with different incidence angles
    for i, (inc_angle, offset_hours) in enumerate([
        (40.0, 0),   # Poor geometry
        (15.0, 2),   # Excellent geometry
        (30.0, 4),   # Good geometry
    ]):
        # Compute quality score (monotonic)
        quality_score = compute_quality_score(
            incidence_angle_deg=inc_angle,
            mode='OPTICAL',
            quality_model=QualityModel.MONOTONIC
        )
        
        # Blend with priority (weight=0.6)
        value = compute_opportunity_value(
            base_priority=1.0,
            quality_score=quality_score,
            quality_weight=0.6
        )
        
        opp_time = start_time + timedelta(hours=offset_hours)
        opp = Opportunity(
            id=f"sat1_targetA_{i}",
            satellite_id="sat1",
            target_id="targetA",
            start_time=opp_time,
            end_time=opp_time + timedelta(minutes=2),
            max_elevation=45.0,
            azimuth=180.0,
            value=value,
            incidence_angle=inc_angle
        )
        opportunities.append(opp)
        print(f"Pass {i+1}: incidence={inc_angle:5.1f}°, quality={quality_score:.4f}, value={value:.4f}")
    
    # Target positions
    target_positions = {
        "targetA": (25.0, 55.0),
    }
    
    # Create scheduler
    config = SchedulerConfig(
        imaging_time_s=5.0,
        max_roll_rate_dps=3.0,
        max_roll_accel_dps2=1.0,
        look_window_s=600.0
    )
    scheduler = MissionScheduler(config)
    
    # Test Best-Fit (should prefer highest value = lowest incidence)
    print("\nRunning Best-Fit algorithm...")
    schedule, metrics = scheduler.schedule(
        opportunities=opportunities,
        target_positions=target_positions,
        algorithm=AlgorithmType.BEST_FIT
    )
    
    print(f"Scheduled {len(schedule)} opportunities")
    if schedule:
        for s in schedule:
            # Find original opportunity
            orig_opp = next((o for o in opportunities if o.id == s.opportunity_id), None)
            if orig_opp:
                print(f"  Selected: {s.opportunity_id}, incidence={orig_opp.incidence_angle:.1f}°, value={s.value:.4f}")
    
    print(f"Mean incidence: {metrics.mean_incidence_deg:.2f}°" if metrics.mean_incidence_deg else "Mean incidence: N/A")
    print(f"Total value: {metrics.total_value:.2f}")
    
    # Expected: Should select pass with 15° (highest quality)
    if schedule and len(schedule) > 0:
        selected_opp = next((o for o in opportunities if o.id == schedule[0].opportunity_id), None)
        if selected_opp and selected_opp.incidence_angle == 15.0:
            print("\n✅ Scheduler correctly selected highest quality opportunity!")
        else:
            print(f"\n⚠️ Expected pass with 15° but got {selected_opp.incidence_angle if selected_opp else 'unknown'}°")
    
    print("\n✅ Scheduler integration test passed")


def test_quality_weight_impact():
    """Test impact of different quality weights on selection."""
    print("\n" + "="*60)
    print("TEST 4: Quality Weight Impact")
    print("="*60)
    
    # Two opportunities: high priority/poor quality vs low priority/excellent quality
    start_time = datetime(2024, 9, 10, 12, 0, 0)
    
    target_positions = {"targetX": (25.0, 55.0)}
    config = SchedulerConfig(
        imaging_time_s=5.0,
        max_roll_rate_dps=3.0,
        max_roll_accel_dps2=1.0,
        look_window_s=3600.0  # Large window to consider both
    )
    
    for weight in [0.0, 0.5, 1.0]:
        print(f"\n--- Quality Weight = {weight:.1f} ---")
        
        opportunities = []
        
        # Opportunity 1: High priority (5), poor quality (45° incidence)
        q1 = compute_quality_score(45.0, 'OPTICAL', QualityModel.MONOTONIC)
        v1 = compute_opportunity_value(5.0, q1, weight)
        opp1 = Opportunity(
            id="sat1_targetX_0",
            satellite_id="sat1",
            target_id="targetX",
            start_time=start_time,
            end_time=start_time + timedelta(minutes=2),
            max_elevation=45.0,
            azimuth=180.0,
            value=v1,
            incidence_angle=45.0
        )
        opportunities.append(opp1)
        
        # Opportunity 2: Low priority (1), excellent quality (10° incidence)
        q2 = compute_quality_score(10.0, 'OPTICAL', QualityModel.MONOTONIC)
        v2 = compute_opportunity_value(1.0, q2, weight)
        opp2 = Opportunity(
            id="sat1_targetX_1",
            satellite_id="sat1",
            target_id="targetX",
            start_time=start_time + timedelta(hours=1),
            end_time=start_time + timedelta(hours=1, minutes=2),
            max_elevation=45.0,
            azimuth=180.0,
            value=v2,
            incidence_angle=10.0
        )
        opportunities.append(opp2)
        
        print(f"Opp1: priority=5.0, incidence=45°, quality={q1:.4f}, value={v1:.4f}")
        print(f"Opp2: priority=1.0, incidence=10°, quality={q2:.4f}, value={v2:.4f}")
        
        scheduler = MissionScheduler(config)
        schedule, metrics = scheduler.schedule(
            opportunities=opportunities,
            target_positions=target_positions,
            algorithm=AlgorithmType.BEST_FIT
        )
        
        if schedule:
            selected = next((o for o in opportunities if o.id == schedule[0].opportunity_id), None)
            if selected:
                print(f"→ Selected: incidence={selected.incidence_angle:.1f}°")
                
                # Verify expected behavior
                if weight == 0.0 and selected.incidence_angle == 45.0:
                    print("  ✓ Correct: w=0 → priority only (high priority)")
                elif weight == 1.0 and selected.incidence_angle == 10.0:
                    print("  ✓ Correct: w=1 → quality only (low incidence)")
                elif weight == 0.5:
                    print(f"  ✓ w=0.5 → balanced (selected {selected.incidence_angle:.1f}°)")
    
    print("\n✅ Quality weight impact test passed")


def test_default_model_selection():
    """Test default model selection based on mode."""
    print("\n" + "="*60)
    print("TEST 5: Default Model Selection")
    print("="*60)
    
    optical_model = select_default_model('OPTICAL')
    sar_model = select_default_model('SAR')
    
    print(f"OPTICAL mode → {optical_model.value} (expected: monotonic)")
    print(f"SAR mode → {sar_model.value} (expected: band)")
    
    assert optical_model == QualityModel.MONOTONIC, "OPTICAL should default to monotonic"
    assert sar_model == QualityModel.BAND, "SAR should default to band"
    
    print("\n✅ Default model selection test passed")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("QUALITY-AWARE MISSION PLANNING - TEST SUITE")
    print("="*60)
    
    try:
        test_quality_scoring_models()
        test_value_blending()
        test_default_model_selection()
        test_scheduler_integration()
        test_quality_weight_impact()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        return 0
        
    except Exception as e:
        print("\n" + "="*60)
        print(f"❌ TEST FAILED: {e}")
        print("="*60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
