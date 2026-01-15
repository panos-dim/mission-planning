#!/usr/bin/env python3
"""
Basic smoke test for adaptive time-stepping.
Quick sanity check before running full validation.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mission_planner.orbit import SatelliteOrbit
from mission_planner.targets import GroundTarget
from mission_planner.visibility import VisibilityCalculator

print("Adaptive Time-Stepping Smoke Test")
print("=" * 50)

# Create simple test data
print("\n1. Creating test satellite and target...")
data_file = Path(__file__).parent.parent / "data" / "active_satellites.tle"
if data_file.exists():
    satellite = SatelliteOrbit.from_tle_file(str(data_file), satellite_name="ICEYE-X44")
    print(f"   ✓ Loaded satellite from {data_file}")
else:
    print(f"   ✗ TLE file not found: {data_file}")
    print("   Please ensure data/active_satellites.tle exists")
    sys.exit(1)

target = GroundTarget(
    name="Test Target",
    latitude=24.4444,
    longitude=54.8333,
    elevation_mask=10.0,
    mission_type='communication'
)
print("   ✓ Created satellite and target")

# Test adaptive algorithm
print("\n2. Testing adaptive algorithm...")
calc_adaptive = VisibilityCalculator(satellite, use_adaptive=True)
print("   ✓ VisibilityCalculator initialized with use_adaptive=True")

# Find passes
start_time = datetime(2025, 8, 1, 0, 0, 0)
end_time = start_time + timedelta(hours=6)

print(f"\n3. Finding passes for 6-hour window...")
print(f"   Start: {start_time.strftime('%Y-%m-%d %H:%M')} UTC")
print(f"   End:   {end_time.strftime('%Y-%m-%d %H:%M')} UTC")

try:
    passes = calc_adaptive.find_passes(target, start_time, end_time)
    print(f"   ✓ Found {len(passes)} passes")
    
    if passes:
        print(f"\n4. Sample pass details:")
        p = passes[0]
        print(f"   Start:        {p.start_time.strftime('%H:%M:%S')} UTC")
        print(f"   Max Elev:     {p.max_elevation:.1f}° at {p.max_elevation_time.strftime('%H:%M:%S')}")
        print(f"   End:          {p.end_time.strftime('%H:%M:%S')} UTC")
        print(f"   Duration:     {(p.end_time - p.start_time).total_seconds():.0f}s")
    
    print("\n" + "=" * 50)
    print("✅ SMOKE TEST PASSED")
    print("\nAdaptive algorithm is working correctly.")
    print("Run full validation: python scripts/validate_adaptive_stepping.py")
    sys.exit(0)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    print("\n" + "=" * 50)
    print("❌ SMOKE TEST FAILED")
    sys.exit(1)
