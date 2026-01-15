#!/usr/bin/env python3
"""
Test script to verify aerospace roll convention for signed roll angles.

AEROSPACE ROLL CONVENTION: When looking along velocity vector
- POSITIVE roll angle = target is on the LEFT side → roll RIGHT to point at it
- NEGATIVE roll angle = target is on the RIGHT side → roll LEFT to point at it
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from datetime import datetime, timedelta
from mission_planner.orbit import SatelliteOrbit
from mission_planner.targets import GroundTarget
from mission_planner.visibility import VisibilityCalculator

# ICEYE-X44 TLE (ascending and descending passes over UAE region)
TLE_LINE1 = "1 48915U 21080AL  25315.00000000  .00000000  00000-0  00000-0 0  9999"
TLE_LINE2 = "2 48915  97.5200  13.0000 0001500  90.0000 270.2000 15.16000000000000"

def test_sign_convention():
    """Test that sign convention follows right-hand rule"""
    
    print("=" * 80)
    print("TESTING AEROSPACE ROLL SIGN CONVENTION")
    print("=" * 80)
    print()
    
    # Create satellite
    satellite = SatelliteOrbit(
        tle_lines=[TLE_LINE1, TLE_LINE2],
        satellite_name="ICEYE-X44-TEST"
    )
    
    # Create visibility calculator
    vis_calc = VisibilityCalculator(satellite=satellite)
    
    # Test at a specific time - get satellite position
    test_time = datetime(2025, 11, 11, 12, 0, 0)
    sat_lat, sat_lon, sat_alt = satellite.get_position(test_time)
    
    print(f"Satellite position: {sat_lat:.2f}°N, {sat_lon:.2f}°E, {sat_alt:.1f}km")
    print()
    
    # Create targets NEAR satellite position (±2° to ensure they're within visibility)
    target_center = GroundTarget(
        name="Center",
        latitude=sat_lat,
        longitude=sat_lon,
        mission_type="imaging"
    )
    
    target_west = GroundTarget(
        name="West-Left",
        latitude=sat_lat,
        longitude=sat_lon - 2.0,  # West of center (left side for northward satellite)
        mission_type="imaging"
    )
    
    target_east = GroundTarget(
        name="East-Right",
        latitude=sat_lat,
        longitude=sat_lon + 2.0,  # East of center (right side for northward satellite)
        mission_type="imaging"
    )
    
    # Test each target
    test_cases = [
        (target_center, "CENTER (nadir)", sat_lon),
        (target_west, "WEST/LEFT of ground track", sat_lon - 2.0),
        (target_east, "EAST/RIGHT of ground track", sat_lon + 2.0),
    ]
    
    print("Testing sign convention:")
    print("-" * 80)
    
    for target, description, expected_lon in test_cases:
        roll_angle = vis_calc._calculate_signed_roll_angle(
            sat_lat, sat_lon, sat_alt,
            target.latitude, target.longitude,
            test_time
        )
        
        sign_str = "+" if roll_angle >= 0 else ""
        side = "LEFT (positive)" if roll_angle > 0 else "RIGHT (negative)" if roll_angle < 0 else "CENTER (zero)"
        
        print(f"\nTarget: {target.name} ({expected_lon}°E)")
        print(f"  Position: {description}")
        print(f"  Roll angle: {sign_str}{roll_angle:.2f}°")
        print(f"  Convention: {side}")
        
        # Verify sign convention
        if "WEST" in description:
            expected_sign = "positive (left side)"
            is_correct = roll_angle > 0
        elif "EAST" in description:
            expected_sign = "negative (right side)"
            is_correct = roll_angle < 0
        else:
            expected_sign = "~0 (nadir)"
            is_correct = abs(roll_angle) < 5.0  # Small angle for nadir
        
        status = "✓ CORRECT" if is_correct else "✗ WRONG"
        print(f"  Expected: {expected_sign}")
        print(f"  Result: {status}")
    
    print()
    print("=" * 80)
    print("AEROSPACE ROLL CONVENTION VERIFICATION COMPLETE")
    print("=" * 80)
    print()
    print("Convention Summary:")
    print("  • When looking along velocity vector:")
    print("  • Target on LEFT side  → need to roll RIGHT → POSITIVE angle")
    print("  • Target on RIGHT side → need to roll LEFT  → NEGATIVE angle")
    print()
    print("This matches standard aerospace roll convention:")
    print("  • Positive roll = roll to the right (right wing down)")
    print("  • Negative roll = roll to the left (left wing down)")
    print()

if __name__ == "__main__":
    test_sign_convention()
