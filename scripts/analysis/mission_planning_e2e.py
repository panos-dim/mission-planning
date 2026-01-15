"""
Test Mission Planning with roll_pitch_best_fit algorithm.
"""

import requests
import json

BASE_URL = "http://localhost:8000"

# Step 1: Analyze mission with constellation
print("=" * 60)
print("STEP 1: ANALYZE CONSTELLATION MISSION")
print("=" * 60)

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
        }
    ],
    "targets": [
        {"name": "Dubai", "latitude": 25.2048, "longitude": 55.2708, "priority": 5},
        {"name": "Athens", "latitude": 37.9838, "longitude": 23.7275, "priority": 3},
        {"name": "London", "latitude": 51.5074, "longitude": -0.1278, "priority": 1}
    ],
    "start_time": "2025-12-08T00:00:00Z",
    "end_time": "2025-12-10T00:00:00Z",
    "mission_type": "imaging"
}

resp = requests.post(f"{BASE_URL}/api/mission/analyze", json=analyze_payload, timeout=120)
data = resp.json()

print(f"SUCCESS: {data.get('success')}")
if data.get('data'):
    md = data['data']['mission_data']
    print(f"Constellation: {md.get('is_constellation')}")
    print(f"Satellites: {len(md.get('satellites', []))}")
    for s in md.get('satellites', []):
        print(f"  🛰️  {s['name']}: {s['color']}")
    print(f"Total passes: {md['total_passes']}")
    print()
    print("Passes found:")
    for i, p in enumerate(md.get('passes', [])):
        sat = p.get('satellite_name', p.get('satellite_id', '?'))
        print(f"  {i+1}. [{sat}] {p['target']} @ {p['start_time'][11:16]}-{p['end_time'][11:16]} elev={p['max_elevation']:.1f}°")
else:
    print(f"Error: {data.get('message')}")
    exit(1)

# Step 2: Run mission planning with roll_pitch_best_fit
print()
print("=" * 60)
print("STEP 2: MISSION PLANNING (roll_pitch_best_fit)")
print("=" * 60)

plan_payload = {"algorithms": ["roll_pitch_best_fit"]}
resp = requests.post(f"{BASE_URL}/api/planning/schedule", json=plan_payload, timeout=60)
data = resp.json()

print(f"SUCCESS: {data.get('success')}")
print(f"MESSAGE: {data.get('message', '')}")

if data.get('results'):
    for algo, result in data['results'].items():
        print()
        print(f"=== {algo.upper()} ===")
        metrics = result.get('metrics', {})
        target_stats = result.get('target_statistics', {})
        angle_stats = result.get('angle_statistics', {})
        
        print(f"Opportunities Scheduled: {metrics.get('opportunities_accepted', len(result.get('schedule', [])))}")
        print(f"Targets Acquired: {target_stats.get('targets_acquired', 0)}/{target_stats.get('total_targets', 0)} ({target_stats.get('coverage_percentage', 0):.1f}%)")
        print(f"Avg Off-Nadir: {angle_stats.get('avg_off_nadir_deg', 0):.1f}°")
        print(f"Avg Cross-Track (Roll): {angle_stats.get('avg_cross_track_deg', 0):.1f}°")
        print(f"Avg Along-Track (Pitch): {angle_stats.get('avg_along_track_deg', 0):.1f}°")
        
        schedule = result.get('schedule', [])
        if schedule:
            print()
            print("Scheduled Opportunities:")
            print(f"{'#':>2} {'Satellite':>10} {'Target':<10} {'Start Time':<20} {'Roll':>7} {'Pitch':>7} {'Value':>8}")
            print("-" * 75)
            for i, opp in enumerate(schedule):
                target = opp.get('target_id', 'N/A')
                start_time = opp.get('start_time', '')[:19] if opp.get('start_time') else 'N/A'
                roll = opp.get('roll_angle', 0) or 0
                pitch = opp.get('pitch_angle', 0) or 0
                value = opp.get('value', 0) or 0
                sat_id = opp.get('satellite_id', '')
                sat_name = sat_id.replace('sat_', '') if sat_id else 'N/A'
                print(f"{i+1:>2} {sat_name:>10} {target:<10} {start_time:<20} {roll:>6.1f}° {pitch:>6.1f}° {value:>7.2f}")
        
        # Show skipped opportunities
        skipped = result.get('skipped', [])
        if skipped:
            print()
            print(f"Skipped Opportunities ({len(skipped)}):")
            for i, sk in enumerate(skipped[:5]):
                reason = sk.get('reason', 'Unknown')
                target = sk.get('target', 'N/A')
                print(f"  - {target}: {reason}")
            if len(skipped) > 5:
                print(f"  ... and {len(skipped) - 5} more")
else:
    print(f"No results returned")

print()
print("=" * 60)
print("TEST COMPLETE")
print("=" * 60)
