"""
Large Constellation Mission Planning Test.
Tests scheduling across multiple satellites.
"""

import requests
from collections import defaultdict

BASE_URL = "http://localhost:8000"

# Step 1: Analyze large constellation mission
print("=" * 70)
print("LARGE CONSTELLATION MISSION PLANNING TEST")
print("=" * 70)
print()

analyze_payload = {
    "satellites": [
        {
            "name": "HAWK-7C",
            "line1": "1 56200U 23054Y   25341.94396439  .00009755  00000+0  34153-3 0  9993",
            "line2": "2 56200  97.2931 227.8239 0006777  29.0973 331.0644 15.29678956147838"
        },
        {
            "name": "NUSAT-39",
            "line1": "1 56201U 23054Z   25341.88587524  .00030131  00000+0  78403-3 0  9992",
            "line2": "2 56201  97.3244 245.9822 0007442  33.9273 326.2448 15.38828619148970"
        },
        {
            "name": "FLOCK-4",
            "line1": "1 55060U 23001BK  25341.77729867  .00015830  00000+0  63445-3 0  9990",
            "line2": "2 55060  97.4690  55.9021 0010127  86.0519 274.1893 15.20932641109419"
        },
        {
            "name": "FLOCK-5",
            "line1": "1 55061U 23001BL  25341.84063200  .00014579  00000+0  58584-3 0  9991",
            "line2": "2 55061  97.4700  56.4682 0009769  84.2018 275.9894 15.20872879109420"
        }
    ],
    "targets": [
        {"name": "Dubai", "latitude": 25.2048, "longitude": 55.2708, "priority": 5},
        {"name": "Athens", "latitude": 37.9838, "longitude": 23.7275, "priority": 4},
        {"name": "London", "latitude": 51.5074, "longitude": -0.1278, "priority": 3},
        {"name": "Tokyo", "latitude": 35.6762, "longitude": 139.6503, "priority": 2},
        {"name": "Sydney", "latitude": -33.8688, "longitude": 151.2093, "priority": 1},
        {"name": "Moscow", "latitude": 55.7558, "longitude": 37.6173, "priority": 3}
    ],
    "start_time": "2025-12-08T00:00:00Z",
    "end_time": "2025-12-15T00:00:00Z",  # 1 week
    "mission_type": "imaging"
}

print("Configuration:")
print(f"  Satellites: {len(analyze_payload['satellites'])}")
print(f"  Targets: {len(analyze_payload['targets'])}")
print(f"  Duration: 7 days")
print()

resp = requests.post(f"{BASE_URL}/api/mission/analyze", json=analyze_payload, timeout=180)
data = resp.json()

print("=" * 70)
print("STEP 1: VISIBILITY ANALYSIS")
print("=" * 70)

if not data.get('success'):
    print(f"ERROR: {data.get('message')}")
    exit(1)

md = data['data']['mission_data']
print(f"✅ SUCCESS: {md['total_passes']} passes found")
print()

# Group passes by satellite
by_sat = defaultdict(list)
for p in md.get('passes', []):
    sat = p.get('satellite_name', p.get('satellite_id', 'Unknown'))
    by_sat[sat].append(p)

print("Passes by satellite:")
for sat, passes in sorted(by_sat.items(), key=lambda x: -len(x[1])):
    print(f"  {sat}: {len(passes)} passes")

# Group by target
by_target = defaultdict(list)
for p in md.get('passes', []):
    by_target[p['target']].append(p)

print()
print("Passes by target:")
for target, passes in sorted(by_target.items(), key=lambda x: -len(x[1])):
    sats = set(p.get('satellite_name', '?') for p in passes)
    print(f"  {target}: {len(passes)} passes (via {', '.join(sats)})")

# Step 2: Run mission planning
print()
print("=" * 70)
print("STEP 2: MISSION PLANNING (roll_pitch_best_fit)")
print("=" * 70)

plan_payload = {"algorithms": ["roll_pitch_best_fit"]}
resp = requests.post(f"{BASE_URL}/api/planning/schedule", json=plan_payload, timeout=60)
data = resp.json()

if not data.get('success'):
    print(f"ERROR: {data.get('message')}")
    exit(1)

print(f"✅ SUCCESS")
print()

for algo, result in data['results'].items():
    metrics = result.get('metrics', {})
    target_stats = result.get('target_statistics', {})
    angle_stats = result.get('angle_statistics', {})
    schedule = result.get('schedule', [])
    
    print(f"Algorithm: {algo}")
    print(f"  Opportunities Scheduled: {len(schedule)}")
    print(f"  Targets Acquired: {target_stats.get('targets_acquired', 0)}/{target_stats.get('total_targets', 0)} ({target_stats.get('coverage_percentage', 0):.1f}%)")
    print(f"  Missing Targets: {target_stats.get('missing_target_ids', [])}")
    print(f"  Avg Off-Nadir: {angle_stats.get('avg_off_nadir_deg', 0):.1f}°")
    print()
    
    # Group scheduled opportunities by satellite
    sched_by_sat = defaultdict(list)
    for opp in schedule:
        sat_id = opp.get('satellite_id', '')
        sat_name = sat_id.replace('sat_', '') if sat_id else 'Unknown'
        sched_by_sat[sat_name].append(opp)
    
    print("Scheduled by satellite:")
    for sat, opps in sorted(sched_by_sat.items(), key=lambda x: -len(x[1])):
        targets = [o.get('target_id', '?') for o in opps]
        print(f"  🛰️  {sat}: {len(opps)} opportunities → {', '.join(targets)}")
    
    print()
    print("Detailed Schedule:")
    print(f"{'#':>2} {'Day':>6} {'Time':>8} {'Satellite':>10} {'Target':<10} {'Roll':>7} {'Pitch':>7} {'Value':>7}")
    print("-" * 70)
    
    for i, opp in enumerate(schedule):
        target = opp.get('target_id', 'N/A')
        start = opp.get('start_time', '')
        day = start[8:10] if start else '??'
        time = start[11:16] if start else '??:??'
        roll = opp.get('roll_angle', 0) or 0
        pitch = opp.get('pitch_angle', 0) or 0
        value = opp.get('value', 0) or 0
        sat_id = opp.get('satellite_id', '')
        sat_name = sat_id.replace('sat_', '') if sat_id else 'N/A'
        print(f"{i+1:>2} Dec-{day} {time:>8} {sat_name:>10} {target:<10} {roll:>6.1f}° {pitch:>6.1f}° {value:>6.2f}")

print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)
