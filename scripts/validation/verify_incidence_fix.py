#!/usr/bin/env python3
"""
Verify that imaging opportunities are scheduled at minimum incidence angle.

This script checks that the PassDetails created for imaging opportunities
uses the time with the best (minimum) incidence angle, not the pass start time.
"""

from datetime import datetime, timedelta
from src.mission_planner.orbit import SatelliteOrbit
from src.mission_planner.visibility import VisibilityCalculator
from src.mission_planner.targets import GroundTarget

def verify_incidence_fix():
    """Verify imaging opportunities use minimum incidence angle timing."""
    
    # Test TLE for ICEYE-X44
    tle_line1 = "1 62707U 24065AE  25203.00000000  .00000000  00000+0  00000+0 0  9999"
    tle_line2 = "2 62707  97.4500 332.0000 0001500  90.0000 270.0000 15.19000000000000"
    
    # Create satellite
    satellite = SatelliteOrbit(
        satellite_name="ICEYE-X44",
        tle_lines=(tle_line1, tle_line2)
    )
    
    # Create target (Athens, Greece)
    target = GroundTarget(
        name="Athens",
        latitude=37.9838,
        longitude=23.7275,
        elevation_mask=10.0,
        mission_type='imaging',
        pointing_angle=45.0
    )
    
    # Add separation parameter as attribute (used by filtering logic)
    target.min_imaging_separation_km = 500.0
    
    # Create visibility calculator
    calc = VisibilityCalculator(satellite, use_adaptive=False)
    
    # Find passes for 24 hours
    start_time = datetime(2025, 10, 23, 0, 0, 0)
    end_time = start_time + timedelta(hours=24)
    
    passes = calc.find_passes(target, start_time, end_time, time_step_seconds=10)
    
    print(f"\n{'='*80}")
    print(f"INCIDENCE ANGLE FIX VERIFICATION")
    print(f"{'='*80}")
    print(f"Target: {target.name}")
    print(f"Period: {start_time} to {end_time}")
    print(f"Found {len(passes)} imaging opportunities\n")
    
    if not passes:
        print("❌ No passes found - cannot verify fix")
        return False
    
    all_good = True
    for i, pass_detail in enumerate(passes, 1):
        # Check that the pass has imaging opportunities stored
        if not hasattr(pass_detail, '_imaging_opportunities'):
            print(f"❌ Pass {i}: Missing _imaging_opportunities attribute")
            all_good = False
            continue
        
        imaging_opps = pass_detail._imaging_opportunities
        if not imaging_opps:
            print(f"❌ Pass {i}: No imaging opportunities stored")
            all_good = False
            continue
        
        # Find the opportunity with minimum incidence angle
        best_opp = min(imaging_opps, key=lambda x: x['look_angle'])
        
        # Check if the PassDetails uses this optimal time
        if pass_detail.start_time == best_opp['time']:
            print(f"✅ Pass {i}: Scheduled at OPTIMAL time")
            print(f"   Time: {best_opp['time'].strftime('%H:%M:%S UTC')}")
            print(f"   Incidence angle: {best_opp['look_angle']:.2f}°")
            print(f"   Total opportunities in pass: {len(imaging_opps)}")
        else:
            print(f"❌ Pass {i}: NOT scheduled at optimal time!")
            print(f"   Scheduled time: {pass_detail.start_time.strftime('%H:%M:%S UTC')}")
            print(f"   Optimal time: {best_opp['time'].strftime('%H:%M:%S UTC')}")
            print(f"   Scheduled incidence: {pass_detail.incidence_angle_deg:.2f}°")
            print(f"   Optimal incidence: {best_opp['look_angle']:.2f}°")
            all_good = False
        print()
    
    print(f"{'='*80}")
    if all_good:
        print("✅ SUCCESS: All imaging opportunities scheduled at optimal time!")
    else:
        print("❌ FAILURE: Some opportunities NOT scheduled at optimal time")
    print(f"{'='*80}\n")
    
    return all_good


if __name__ == "__main__":
    success = verify_incidence_fix()
    exit(0 if success else 1)
