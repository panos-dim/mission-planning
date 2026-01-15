#!/usr/bin/env .venv/bin/python
"""
Demonstrate incidence angle optimization problem and solution.
"""

import sys

sys.path.insert(0, "src")

import math
from datetime import datetime, timedelta

from mission_planner.scheduler import (
    AlgorithmType,
    MissionScheduler,
    Opportunity,
    SchedulerConfig,
)

print("=" * 80)
print("INCIDENCE ANGLE OPTIMIZATION PROBLEM")
print("=" * 80)

# Simulate: Target T1 has 3 opportunities with different quality
print("\n📊 SCENARIO: Target T1 has 3 imaging opportunities")
print("-" * 80)

opportunities = [
    # Pass 1: Early morning, high incidence angle (poor quality)
    Opportunity(
        id="T1_Pass1",
        satellite_id="Sat1",
        target_id="T1",
        start_time=datetime(2025, 10, 20, 6, 0, 0),
        end_time=datetime(2025, 10, 20, 6, 2, 0),
        max_elevation=35.0,
        incidence_angle=42.0,  # Poor quality (high angle)
        value=1.0,  # Currently: All opportunities have same value!
    ),
    # Pass 2: Midday, excellent incidence angle (best quality)
    Opportunity(
        id="T1_Pass2",
        satellite_id="Sat1",
        target_id="T1",
        start_time=datetime(2025, 10, 20, 12, 0, 0),
        end_time=datetime(2025, 10, 20, 12, 2, 0),
        max_elevation=65.0,
        incidence_angle=12.0,  # Excellent quality (low angle)
        value=1.0,  # Should be HIGHER value!
    ),
    # Pass 3: Evening, moderate incidence angle (ok quality)
    Opportunity(
        id="T1_Pass3",
        satellite_id="Sat1",
        target_id="T1",
        start_time=datetime(2025, 10, 20, 18, 0, 0),
        end_time=datetime(2025, 10, 20, 18, 2, 0),
        max_elevation=45.0,
        incidence_angle=28.0,  # Moderate quality
        value=1.0,
    ),
]

# Display opportunities
for i, opp in enumerate(opportunities, 1):
    quality = (
        "★★★ EXCELLENT"
        if opp.incidence_angle < 20
        else "★★ GOOD" if opp.incidence_angle < 35 else "★ POOR"
    )
    print(f"\n  Pass {i}: {opp.start_time.strftime('%H:%M')}")
    print(f"    Incidence Angle: {opp.incidence_angle:.1f}°")
    print(f"    Max Elevation:   {opp.max_elevation:.1f}°")
    print(f"    Image Quality:   {quality}")
    print(f"    Current Value:   {opp.value:.2f} ❌ (No quality consideration!)")

# Target position (for agility calculations)
target_positions = {"T1": (25.0, 55.0)}

# Configure scheduler
config = SchedulerConfig(
    imaging_time_s=1.0,
    max_roll_rate_dps=3.0,
    max_roll_accel_dps2=1.0,
    max_spacecraft_roll_deg=45.0,
    look_window_s=600.0,
)

scheduler = MissionScheduler(config)

print("\n" + "=" * 80)
print("CURRENT SYSTEM BEHAVIOR (Quality-Blind)")
print("=" * 80)

schedule, metrics = scheduler.schedule(
    opportunities, target_positions, AlgorithmType.FIRST_FIT
)

print("\n📅 Scheduled:")
if schedule:
    selected = schedule[0]
    quality = (
        "★★★"
        if selected.opportunity_id == "T1_Pass2"
        else "★★" if selected.opportunity_id == "T1_Pass3" else "★"
    )

    # Find original opportunity to get incidence angle
    orig_opp = next(o for o in opportunities if o.id == selected.opportunity_id)

    print(f"  ✅ Selected: {selected.opportunity_id}")
    print(f"     Time: {selected.start_time.strftime('%H:%M:%S')}")
    print(f"     Incidence Angle: {orig_opp.incidence_angle:.1f}°")
    print(f"     Image Quality: {quality}")

    if selected.opportunity_id != "T1_Pass2":
        print(
            f"\n  ❌ PROBLEM: Selected Pass {selected.opportunity_id[-1]}, not the best quality!"
        )
        print(
            f"     ⚠️  Pass 2 has {orig_opp.incidence_angle - 12.0:.1f}° better incidence angle!"
        )
        print(f"     ⚠️  Missed opportunity for superior image!")

print("\n" + "=" * 80)
print("PROPOSED SOLUTION: Quality-Aware Value Function")
print("=" * 80)


# Define quality-aware value function
def calculate_quality_value(incidence_angle: float, priority: float = 1.0) -> float:
    """
    Value based on image quality (incidence angle).

    Exponential decay: Lower incidence = higher value
    - 0° (nadir):     quality_factor = 1.00 (100%)
    - 15° (excellent): quality_factor = 0.63 (63%)
    - 30° (good):     quality_factor = 0.41 (41%)
    - 45° (poor):     quality_factor = 0.26 (26%)
    """
    quality_factor = math.exp(-0.03 * incidence_angle)
    return priority * quality_factor


# Apply quality-aware values
print("\n📊 Recalculated Values (Quality-Aware):")
quality_opportunities = []
for opp in opportunities:
    new_opp = Opportunity(
        id=opp.id,
        satellite_id=opp.satellite_id,
        target_id=opp.target_id,
        start_time=opp.start_time,
        end_time=opp.end_time,
        max_elevation=opp.max_elevation,
        incidence_angle=opp.incidence_angle,
        value=calculate_quality_value(opp.incidence_angle),  # Quality-aware!
    )
    quality_opportunities.append(new_opp)

    quality = (
        "★★★ EXCELLENT"
        if opp.incidence_angle < 20
        else "★★ GOOD" if opp.incidence_angle < 35 else "★ POOR"
    )

    print(f"\n  {opp.id}:")
    print(f"    Incidence Angle: {opp.incidence_angle:.1f}°")
    print(f"    Quality Factor:  {math.exp(-0.03 * opp.incidence_angle):.2f}")
    print(f"    New Value:       {new_opp.value:.2f} ✅")
    print(f"    Image Quality:   {quality}")

# Schedule with quality-aware values using Best-Fit (picks highest value)
print("\n📅 Scheduling with Quality-Aware Values (Best-Fit):")
schedule_quality, metrics_quality = scheduler.schedule(
    quality_opportunities,
    target_positions,
    AlgorithmType.BEST_FIT,  # Picks highest value = best quality!
)

if schedule_quality:
    selected = schedule_quality[0]
    orig_opp = next(o for o in quality_opportunities if o.id == selected.opportunity_id)
    quality = (
        "★★★"
        if selected.opportunity_id == "T1_Pass2"
        else "★★" if selected.opportunity_id == "T1_Pass3" else "★"
    )

    print(f"  ✅ Selected: {selected.opportunity_id}")
    print(f"     Time: {selected.start_time.strftime('%H:%M:%S')}")
    print(f"     Incidence Angle: {orig_opp.incidence_angle:.1f}°")
    print(f"     Value: {orig_opp.value:.2f}")
    print(f"     Image Quality: {quality}")

    if selected.opportunity_id == "T1_Pass2":
        print(f"\n  ✅ SUCCESS: Selected Pass 2 with best incidence angle!")
        print(f"     🎯 12° incidence = Highest quality image possible")
        print(f"     🎯 Algorithm automatically prioritized quality")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(
    """
❌ CURRENT PROBLEM:
   - All opportunities have same value (1.0)
   - First-Fit picks first feasible (arbitrary quality)
   - Ignores superior opportunities with better geometry

✅ SOLUTION (Phase 1-2):
   1. Compute quality_factor from incidence angle
   2. Set opportunity.value = priority × quality_factor
   3. Existing algorithms automatically optimize!

   Result:
   - Best-Fit → Picks best quality
   - Value-Density → Balances quality vs slew time
   - First-Fit → Still works (just faster)

🚀 IMPLEMENTATION:
   - Mission Analysis: Already computes incidence angle
   - Just need to: Pass to scheduler + Apply value function
   - NO algorithm changes required!
   - 2-3 hours of work for major improvement

💡 ADDITIONAL BENEFITS:
   - Within-window optimization (find best moment)
   - Multi-target scenarios (prioritize quality across targets)
   - User control (quality_weight parameter)
"""
)

print("\n" + "=" * 80)
print("Would you like me to implement Phase 1-2?")
print("=" * 80)
print(
    """
This will:
1. ✅ Add incidence_angle to backend opportunity data
2. ✅ Implement quality_factor value function
3. ✅ Update existing algorithms to use quality-aware values
4. ✅ Add configuration parameter for quality_weight

Estimated time: 2-3 hours
Impact: Immediate quality improvement with existing algorithms
"""
)
