"""
E2E Tests for Constellation Support.

Tests extreme scenarios and mission planning with the real backend API.
"""

import requests
import json
from datetime import datetime, timedelta
from collections import defaultdict

BASE_URL = "http://localhost:8000"

# Real TLE data from CelesTrak
SATELLITES = {
    "HAWK-7C": {
        "line1": "1 56200U 23054Y   25341.94396439  .00009755  00000+0  34153-3 0  9993",
        "line2": "2 56200  97.2931 227.8239 0006777  29.0973 331.0644 15.29678956147838"
    },
    "NUSAT-39": {
        "line1": "1 56201U 23054Z   25341.88587524  .00030131  00000+0  78403-3 0  9992",
        "line2": "2 56201  97.3244 245.9822 0007442  33.9273 326.2448 15.38828619148970"
    },
    "FLOCK-4": {
        "line1": "1 55060U 23001BK  25341.77729867  .00015830  00000+0  63445-3 0  9990",
        "line2": "2 55060  97.4690  55.9021 0010127  86.0519 274.1893 15.20932641109419"
    },
    "FLOCK-5": {
        "line1": "1 55061U 23001BL  25341.84063200  .00014579  00000+0  58584-3 0  9991",
        "line2": "2 55061  97.4700  56.4682 0009769  84.2018 275.9894 15.20872879109420"
    },
    "FLOCK-6": {
        "line1": "1 55062U 23001BM  25341.77729867  .00011234  00000+0  45123-3 0  9992",
        "line2": "2 55062  97.4710  57.0021 0009500  82.5519 277.8893 15.20812641109421"
    },
}

TARGETS = {
    "Dubai": {"latitude": 25.2048, "longitude": 55.2708},
    "Athens": {"latitude": 37.9838, "longitude": 23.7275},
    "London": {"latitude": 51.5074, "longitude": -0.1278},
    "Tokyo": {"latitude": 35.6762, "longitude": 139.6503},
    "New York": {"latitude": 40.7128, "longitude": -74.0060},
    "Sydney": {"latitude": -33.8688, "longitude": 151.2093},
    "Cairo": {"latitude": 30.0444, "longitude": 31.2357},
    "Moscow": {"latitude": 55.7558, "longitude": 37.6173},
}


def print_header(title: str):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def analyze_mission(satellites: list, targets: list, start: str, end: str, mission_type: str = "imaging"):
    """Call the mission analysis API."""
    payload = {
        "satellites": satellites,
        "targets": targets,
        "start_time": start,
        "end_time": end,
        "mission_type": mission_type
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/api/mission/analyze", json=payload, timeout=120)
        return resp.json()
    except Exception as e:
        return {"success": False, "message": str(e)}


def plan_mission(algorithm: str = "greedy"):
    """Call the mission planning API."""
    payload = {"algorithms": [algorithm]}
    
    try:
        resp = requests.post(f"{BASE_URL}/api/planning/schedule", json=payload, timeout=60)
        return resp.json()
    except Exception as e:
        return {"success": False, "message": str(e)}


def test_large_constellation():
    """Test 1: Large constellation (5 satellites)."""
    print_header("TEST 1: LARGE CONSTELLATION (5 SATELLITES)")
    
    sats = [{"name": name, **data} for name, data in SATELLITES.items()]
    tgts = [{"name": name, **data} for name, data in list(TARGETS.items())[:3]]
    
    result = analyze_mission(
        satellites=sats,
        targets=tgts,
        start="2025-12-08T00:00:00Z",
        end="2025-12-10T00:00:00Z"
    )
    
    print(f"Status: {'✅ SUCCESS' if result.get('success') else '❌ FAILED'}")
    
    if result.get('data'):
        md = result['data']['mission_data']
        print(f"Satellites: {len(md.get('satellites', []))}")
        for s in md.get('satellites', []):
            print(f"  🛰️  {s['name']}: {s['color']}")
        print(f"Total passes: {md['total_passes']}")
        
        by_sat = defaultdict(int)
        for p in md.get('passes', []):
            by_sat[p.get('satellite_name', 'Unknown')] += 1
        print("Passes per satellite:")
        for sat, cnt in sorted(by_sat.items()):
            print(f"  {sat}: {cnt}")
    else:
        print(f"Error: {result.get('message')}")
    
    return result.get('success', False)


def test_many_targets():
    """Test 2: Many targets (8 cities worldwide)."""
    print_header("TEST 2: MANY TARGETS (8 CITIES WORLDWIDE)")
    
    sats = [{"name": name, **data} for name, data in list(SATELLITES.items())[:2]]
    tgts = [{"name": name, **data} for name, data in TARGETS.items()]
    
    result = analyze_mission(
        satellites=sats,
        targets=tgts,
        start="2025-12-08T00:00:00Z",
        end="2025-12-09T00:00:00Z"
    )
    
    print(f"Status: {'✅ SUCCESS' if result.get('success') else '❌ FAILED'}")
    
    if result.get('data'):
        md = result['data']['mission_data']
        print(f"Satellites: {len(md.get('satellites', []))}")
        print(f"Targets: {len(md.get('targets', []))}")
        print(f"Total passes: {md['total_passes']}")
        
        by_target = defaultdict(int)
        for p in md.get('passes', []):
            by_target[p['target']] += 1
        print("Passes per target:")
        for tgt, cnt in sorted(by_target.items(), key=lambda x: -x[1]):
            print(f"  {tgt}: {cnt}")
    else:
        print(f"Error: {result.get('message')}")
    
    return result.get('success', False)


def test_long_duration():
    """Test 3: Long duration (2 weeks)."""
    print_header("TEST 3: LONG DURATION (2 WEEKS)")
    
    sats = [{"name": name, **data} for name, data in list(SATELLITES.items())[:2]]
    tgts = [{"name": "Dubai", **TARGETS["Dubai"]}]
    
    result = analyze_mission(
        satellites=sats,
        targets=tgts,
        start="2025-12-08T00:00:00Z",
        end="2025-12-22T00:00:00Z"
    )
    
    print(f"Status: {'✅ SUCCESS' if result.get('success') else '❌ FAILED'}")
    
    if result.get('data'):
        md = result['data']['mission_data']
        print(f"Duration: {md['duration_hours']:.0f} hours ({md['duration_hours']/24:.0f} days)")
        print(f"Total passes: {md['total_passes']}")
        
        # Show distribution by day
        by_day = defaultdict(int)
        for p in md.get('passes', []):
            day = p['start_time'][:10]
            by_day[day] += 1
        print("Passes per day:")
        for day, cnt in sorted(by_day.items()):
            print(f"  {day}: {cnt}")
    else:
        print(f"Error: {result.get('message')}")
    
    return result.get('success', False)


def test_single_satellite_backward_compat():
    """Test 4: Single satellite (backward compatibility)."""
    print_header("TEST 4: SINGLE SATELLITE (BACKWARD COMPAT)")
    
    # Use legacy 'tle' field instead of 'satellites'
    payload = {
        "tle": {
            "name": "HAWK-7C",
            **SATELLITES["HAWK-7C"]
        },
        "targets": [{"name": "Dubai", **TARGETS["Dubai"]}],
        "start_time": "2025-12-08T00:00:00Z",
        "end_time": "2025-12-09T00:00:00Z",
        "mission_type": "imaging"
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/api/mission/analyze", json=payload, timeout=60)
        result = resp.json()
    except Exception as e:
        result = {"success": False, "message": str(e)}
    
    print(f"Status: {'✅ SUCCESS' if result.get('success') else '❌ FAILED'}")
    
    if result.get('data'):
        md = result['data']['mission_data']
        print(f"Is Constellation: {md.get('is_constellation')}")
        print(f"Satellite Name: {md.get('satellite_name')}")
        print(f"Total passes: {md['total_passes']}")
    else:
        print(f"Error: {result.get('message')}")
    
    return result.get('success', False)


def test_mission_planning():
    """Test 5: Mission planning with scheduling."""
    print_header("TEST 5: MISSION PLANNING (GREEDY ALGORITHM)")
    
    # First, analyze a mission
    sats = [{"name": name, **data} for name, data in list(SATELLITES.items())[:2]]
    tgts = [
        {"name": "Dubai", **TARGETS["Dubai"], "priority": 5},
        {"name": "Athens", **TARGETS["Athens"], "priority": 3},
        {"name": "London", **TARGETS["London"], "priority": 1},
    ]
    
    analyze_result = analyze_mission(
        satellites=sats,
        targets=tgts,
        start="2025-12-08T00:00:00Z",
        end="2025-12-10T00:00:00Z"
    )
    
    if not analyze_result.get('success'):
        print(f"❌ Analysis failed: {analyze_result.get('message')}")
        return False
    
    print(f"Analysis: ✅ {analyze_result['data']['mission_data']['total_passes']} passes found")
    
    # Now run mission planning
    plan_result = plan_mission(algorithm="greedy")
    
    print(f"Planning: {'✅ SUCCESS' if plan_result.get('success') else '❌ FAILED'}")
    
    if plan_result.get('results'):
        for algo, result in plan_result['results'].items():
            print(f"\n{algo.upper()} Algorithm:")
            print(f"  Scheduled: {result.get('scheduled_count', 0)}")
            print(f"  Skipped: {result.get('skipped_count', 0)}")
            print(f"  Total score: {result.get('total_score', 0):.1f}")
            
            schedule = result.get('schedule', [])
            if schedule:
                print(f"  First 5 scheduled opportunities:")
                for i, opp in enumerate(schedule[:5]):
                    print(f"    {i+1}. {opp.get('target', 'N/A')} @ {opp.get('imaging_time', 'N/A')[:16]}")
    else:
        print(f"Error: {plan_result.get('message')}")
    
    return plan_result.get('success', False)


def test_czml_generation():
    """Test 6: CZML generation for constellation."""
    print_header("TEST 6: CZML GENERATION")
    
    sats = [{"name": name, **data} for name, data in list(SATELLITES.items())[:3]]
    tgts = [{"name": "Dubai", **TARGETS["Dubai"]}]
    
    result = analyze_mission(
        satellites=sats,
        targets=tgts,
        start="2025-12-08T00:00:00Z",
        end="2025-12-08T12:00:00Z"
    )
    
    print(f"Status: {'✅ SUCCESS' if result.get('success') else '❌ FAILED'}")
    
    if result.get('data'):
        czml = result['data'].get('czml_data', [])
        print(f"Total CZML packets: {len(czml)}")
        
        # Categorize packets
        doc_packets = [p for p in czml if p.get('id') == 'document']
        sat_packets = [p for p in czml if p.get('id', '').startswith('sat_') and 'ground_track' not in p.get('id', '')]
        track_packets = [p for p in czml if 'ground_track' in p.get('id', '')]
        target_packets = [p for p in czml if p.get('id', '').startswith('target_')]
        other_packets = [p for p in czml if p not in doc_packets + sat_packets + track_packets + target_packets]
        
        print(f"  Document: {len(doc_packets)}")
        print(f"  Satellites: {len(sat_packets)}")
        for sp in sat_packets:
            has_pos = 'position' in sp
            print(f"    - {sp.get('id')}: position={'Yes' if has_pos else 'No'}")
        print(f"  Ground tracks: {len(track_packets)}")
        print(f"  Targets: {len(target_packets)}")
        print(f"  Other: {len(other_packets)}")
    else:
        print(f"Error: {result.get('message')}")
    
    return result.get('success', False)


def test_edge_case_empty_results():
    """Test 7: Edge case - no visibility (polar target)."""
    print_header("TEST 7: EDGE CASE - POLAR TARGET (LIKELY NO PASSES)")
    
    sats = [{"name": "HAWK-7C", **SATELLITES["HAWK-7C"]}]
    tgts = [{"name": "South Pole", "latitude": -89.9, "longitude": 0.0}]
    
    result = analyze_mission(
        satellites=sats,
        targets=tgts,
        start="2025-12-08T00:00:00Z",
        end="2025-12-08T06:00:00Z"
    )
    
    print(f"Status: {'✅ SUCCESS' if result.get('success') else '❌ FAILED'}")
    
    if result.get('data'):
        md = result['data']['mission_data']
        print(f"Total passes: {md['total_passes']}")
        if md['total_passes'] == 0:
            print("  (Expected: polar regions may have limited coverage)")
    else:
        print(f"Error: {result.get('message')}")
    
    return result.get('success', False)


def run_all_tests():
    """Run all E2E tests."""
    print("\n" + "=" * 60)
    print("CONSTELLATION E2E TEST SUITE")
    print("=" * 60)
    print(f"Target: {BASE_URL}")
    print(f"Started: {datetime.now().isoformat()}")
    
    tests = [
        ("Large Constellation", test_large_constellation),
        ("Many Targets", test_many_targets),
        ("Long Duration", test_long_duration),
        ("Backward Compat", test_single_satellite_backward_compat),
        ("Mission Planning", test_mission_planning),
        ("CZML Generation", test_czml_generation),
        ("Edge Case", test_edge_case_empty_results),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed))
        except Exception as e:
            print(f"❌ Exception: {e}")
            results.append((name, False))
    
    print_header("TEST RESULTS SUMMARY")
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, p in results:
        status = "✅ PASS" if p else "❌ FAIL"
        print(f"  {status}  {name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    print(f"Finished: {datetime.now().isoformat()}")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
