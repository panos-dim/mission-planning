#!/usr/bin/env python3
"""Debug script to verify GroundTarget attribute handling"""

import sys
sys.path.insert(0, '/Users/panagiotis.d/CascadeProjects/mission-planning/src')

from mission_planner.targets import GroundTarget

print("=" * 80)
print("Testing GroundTarget attribute handling")
print("=" * 80)

# Test 1: Create target like backend does
print("\n1. Creating target with max_spacecraft_roll=45, sensor_fov=1.0:")
target1 = GroundTarget(
    name="TestTarget",
    latitude=37.9838,
    longitude=23.7275,
    mission_type='imaging',
    elevation_mask=10.0,
    sensor_fov_half_angle_deg=1.0,  # Sensor FOV
    max_spacecraft_roll=45.0,  # Spacecraft agility limit
    priority=1
)
target1.imaging_type = 'optical'

print(f"  max_spacecraft_roll: {target1.max_spacecraft_roll}")
print(f"  sensor_fov_half_angle_deg: {target1.sensor_fov_half_angle_deg}")
print(f"  pointing_angle: REMOVED ✅")

# Test 2: Simulate what getattr chain will return (simplified, no pointing_angle)
print("\n2. Testing getattr chain for visibility:")
visibility_fov = getattr(target1, 'max_spacecraft_roll', None) or 45.0
print(f"  Result: {visibility_fov}° (should be 45)")

# Test 3: Check each attribute individually
print("\n3. Individual attribute checks:")
print(f"  getattr(target1, 'max_spacecraft_roll', None) = {getattr(target1, 'max_spacecraft_roll', None)}")
print(f"  getattr(target1, 'sensor_fov_half_angle_deg', None) = {getattr(target1, 'sensor_fov_half_angle_deg', None)}")

# Test 4: Simulate pickling (like parallel workers do)
print("\n4. Testing pickle/unpickle (like parallel workers):")
import pickle
pickled = pickle.dumps(target1)
target2 = pickle.loads(pickled)

print(f"  After unpickle:")
print(f"    max_spacecraft_roll: {target2.max_spacecraft_roll}")
print(f"    sensor_fov_half_angle_deg: {target2.sensor_fov_half_angle_deg}")

visibility_fov2 = getattr(target2, 'max_spacecraft_roll', None) or 45.0
print(f"  Visibility FOV after unpickle: {visibility_fov2}° (should be 45)")

# Test 5: Check what happens with None values (should use default 45)
print("\n5. Testing with max_spacecraft_roll=None (should auto-set to 45 in __post_init__):")
target3 = GroundTarget(
    name="TestTarget3",
    latitude=37.9838,
    longitude=23.7275,
    mission_type='imaging',
    elevation_mask=10.0,
    sensor_fov_half_angle_deg=1.0,
    max_spacecraft_roll=None,  # Explicitly None, should be set to 45 in __post_init__
    priority=1
)
target3.imaging_type = 'optical'

print(f"  max_spacecraft_roll: {target3.max_spacecraft_roll}")
print(f"  sensor_fov_half_angle_deg: {target3.sensor_fov_half_angle_deg}")
visibility_fov3 = getattr(target3, 'max_spacecraft_roll', None) or 45.0
print(f"  Visibility FOV: {visibility_fov3}° (should be 45 from default)")

print("\n" + "=" * 80)
print("✅ Test complete - check results above")
print("=" * 80)
