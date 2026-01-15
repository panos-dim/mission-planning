#!/usr/bin/env python3
"""
Comprehensive analysis with 45° pitch capability.
Shows full pass duration sampling with maximum agility.
"""

import requests
import json
from datetime import datetime, timedelta
from tabulate import tabulate

BASE_URL = "http://localhost:8000"
DEBUG_ENDPOINT = f"{BASE_URL}/api/v1/debug/planning/run_scenario"

SATELLITE_TLE = {
    "id": "ICEYE-X44",
    "name": "ICEYE-X44",
    "tle_line1": "1 62707U 25009DC  25306.22031033  .00004207  00000+0  39848-3 0  9995",
    "tle_line2": "2 62707  97.7269  23.9854 0002193 135.9671 224.1724 14.94137357 66022"
}

# Middle East targets for tight scenario
TARGETS = [
    {"name": "Dubai", "latitude": 25.2048, "longitude": 55.2708, "priority": 5},
    {"name": "Abu_Dhabi", "latitude": 24.4539, "longitude": 54.3773, "priority": 5},
    {"name": "Doha", "latitude": 25.2854, "longitude": 51.5310, "priority": 4},
    {"name": "Riyadh", "latitude": 24.7136, "longitude": 46.6753, "priority": 5},
    {"name": "Kuwait_City", "latitude": 29.3759, "longitude": 47.9774, "priority": 4},
    {"name": "Manama", "latitude": 26.2285, "longitude": 50.5860, "priority": 3},
    {"name": "Tehran", "latitude": 35.6892, "longitude": 51.3890, "priority": 5},
    {"name": "Baghdad", "latitude": 33.3152, "longitude": 44.3661, "priority": 5},
]


def run_comparison():
    """Run roll-only vs roll+pitch with 45° capability."""
    
    start_time = datetime(2025, 11, 18, 0, 0, 0)
    
    print("\n" + "=" * 120)
    print("🚀 45° PITCH CAPABILITY ANALYSIS - FULL PASS DURATION SAMPLING")
    print("=" * 120)
    
    results = {}
    
    for max_pitch, label in [(0, "Roll-Only (0°)"), (45, "Roll+Pitch (45°)")]:
        print(f"\n{'─' * 120}")
        print(f"Testing: {label}")
        print(f"{'─' * 120}")
        
        for window_hours in [12, 24]:
            payload = {
                "scenario_id": f"test_{max_pitch}deg_{window_hours}h",
                "satellites": [SATELLITE_TLE],
                "targets": TARGETS,
                "time_window": {
                    "start": start_time.isoformat() + "Z",
                    "end": (start_time + timedelta(hours=window_hours)).isoformat() + "Z"
                },
                "planning_params": {
                    "imaging_time_s": 5.0,
                    "max_roll_rate_dps": 1.0,
                    "max_roll_accel_dps2": 1000.0,
                    "max_spacecraft_roll_deg": 45.0,
                    "max_pitch_rate_dps": 1.0,
                    "max_pitch_accel_dps2": 10000.0,
                    "max_spacecraft_pitch_deg": float(max_pitch),
                    "quality_model": "uniform",
                    "quality_weight": 0.5
                },
                "algorithms": ["first_fit"] if max_pitch == 0 else ["roll_pitch_first_fit"]
            }
            
            print(f"  Running {window_hours}h window... ", end="", flush=True)
            response = requests.post(DEBUG_ENDPOINT, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            
            algo_key = "first_fit" if max_pitch == 0 else "roll_pitch_first_fit"
            metrics = result["algorithms"][algo_key]["metrics"]
            schedule = result["algorithms"][algo_key]["schedule"]
            
            covered_targets = {opp["target_id"] for opp in schedule}
            
            key = f"{max_pitch}deg_{window_hours}h"
            results[key] = {
                "label": label,
                "window": window_hours,
                "max_pitch": max_pitch,
                "coverage": len(covered_targets),
                "total_targets": len(TARGETS),
                "total_opps": metrics["total_opportunities"],
                "accepted": metrics["accepted"],
                "mean_incidence": metrics["mean_incidence_deg"],
                "max_roll": metrics["max_roll_deg"],
                "max_pitch": metrics["max_pitch_deg"],
                "opps_using_pitch": metrics["opps_using_pitch"],
                "total_roll": metrics["total_roll_used_deg"],
                "total_pitch": metrics["total_pitch_used_deg"],
                "maneuver_time": metrics["total_maneuver_time_s"],
                "covered_targets": sorted(covered_targets),
                "schedule": schedule
            }
            
            print(f"✓ {len(covered_targets)}/{len(TARGETS)} targets")
    
    return results


def print_summary_table(results):
    """Print main comparison table."""
    print("\n" + "=" * 120)
    print("📊 SUMMARY: Roll-Only vs Roll+Pitch (45°)")
    print("=" * 120)
    
    table = []
    for key in ["0deg_12h", "45deg_12h", "0deg_24h", "45deg_24h"]:
        r = results[key]
        table.append([
            f"{r['window']}h",
            f"{r['max_pitch']}°",
            f"{r['coverage']}/{r['total_targets']}",
            f"{r['coverage']/r['total_targets']*100:.0f}%",
            f"{r['total_opps']}",
            f"{r['accepted']}",
            f"{r['mean_incidence']:.1f}°",
            f"{r['max_roll']:.1f}°",
            f"{r['max_pitch']:.1f}°",
            f"{r['opps_using_pitch']}",
            f"{r['maneuver_time']:.0f}s",
        ])
    
    headers = ["Window", "Max Pitch", "Coverage", "%", "Total Opps", "Accepted", 
               "Mean Inc", "Max Roll", "Max Pitch", "Pitch Uses", "Maneuver Time"]
    print("\n" + tabulate(table, headers=headers, tablefmt="grid"))


def print_coverage_comparison(results):
    """Print target-by-target coverage."""
    print("\n" + "=" * 120)
    print("🎯 TARGET COVERAGE COMPARISON")
    print("=" * 120)
    
    all_targets = set()
    for r in results.values():
        all_targets.update(r['covered_targets'])
    
    for window in [12, 24]:
        print(f"\n{'─' * 120}")
        print(f"{window}h WINDOW")
        print(f"{'─' * 120}")
        
        r0 = results[f"0deg_{window}h"]
        r45 = results[f"45deg_{window}h"]
        
        table = []
        for target in sorted(all_targets):
            in_roll_only = target in r0['covered_targets']
            in_roll_pitch = target in r45['covered_targets']
            
            if in_roll_pitch and not in_roll_only:
                result = "🎯 PITCH ENABLED"
            elif in_roll_only and in_roll_pitch:
                result = "Both"
            elif not in_roll_only and not in_roll_pitch:
                result = "Neither"
            else:
                result = "Roll-only"
            
            table.append([
                target,
                "✓" if in_roll_only else "✗",
                "✓" if in_roll_pitch else "✗",
                result
            ])
        
        print("\n" + tabulate(table, headers=["Target", "Roll-Only (0°)", "Roll+Pitch (45°)", "Result"], tablefmt="grid"))
        
        improvement = r45['coverage'] - r0['coverage']
        print(f"\nSummary:")
        print(f"  Roll-Only: {r0['coverage']}/{r0['total_targets']} ({r0['coverage']/r0['total_targets']*100:.0f}%)")
        print(f"  Roll+Pitch: {r45['coverage']}/{r45['total_targets']} ({r45['coverage']/r45['total_targets']*100:.0f}%)")
        print(f"  Improvement: {'+' if improvement >= 0 else ''}{improvement} targets ({improvement/r0['total_targets']*100:+.0f}%)")


def print_pitch_analysis(results):
    """Analyze pitch usage in detail."""
    print("\n" + "=" * 120)
    print("📈 PITCH USAGE ANALYSIS (45° Capability)")
    print("=" * 120)
    
    for window in [12, 24]:
        r = results[f"45deg_{window}h"]
        schedule = r['schedule']
        
        if not schedule:
            continue
        
        print(f"\n{'─' * 120}")
        print(f"{window}h WINDOW - Pitch Distribution")
        print(f"{'─' * 120}")
        
        pitches = [opp.get("pitch_angle", 0) for opp in schedule]
        rolls = [opp.get("roll_angle", 0) for opp in schedule]
        
        # Pitch ranges
        ranges = [
            ("0-10°", lambda p: 0 <= abs(p) <= 10),
            ("10-20°", lambda p: 10 < abs(p) <= 20),
            ("20-30°", lambda p: 20 < abs(p) <= 30),
            ("30-40°", lambda p: 30 < abs(p) <= 40),
            ("40-45°", lambda p: 40 < abs(p) <= 45),
        ]
        
        table = []
        for range_name, check in ranges:
            count = sum(1 for p in pitches if check(p))
            pct = count / len(pitches) * 100 if pitches else 0
            table.append([range_name, count, f"{pct:.0f}%"])
        
        print("\n" + tabulate(table, headers=["Pitch Range", "Count", "%"], tablefmt="grid"))
        
        print(f"\nStatistics:")
        print(f"  Opportunities: {len(pitches)}")
        print(f"  Pitch min: {min(pitches):.1f}°")
        print(f"  Pitch max: {max(pitches):.1f}°")
        print(f"  Pitch span: {max(pitches) - min(pitches):.1f}°")
        print(f"  Pitch mean: {sum(pitches)/len(pitches):.1f}°")
        print(f"  Roll min: {min(rolls):.1f}°")
        print(f"  Roll max: {max(rolls):.1f}°")
        print(f"  Using >30° pitch: {sum(1 for p in pitches if abs(p) > 30)} opps")
        print(f"  Using >40° pitch: {sum(1 for p in pitches if abs(p) > 40)} opps")


def print_opportunity_explosion(results):
    """Show how opportunities increase with pitch."""
    print("\n" + "=" * 120)
    print("💥 OPPORTUNITY EXPLOSION - Full Pass Sampling Effect")
    print("=" * 120)
    
    table = []
    for window in [12, 24]:
        r0 = results[f"0deg_{window}h"]
        r45 = results[f"45deg_{window}h"]
        
        opp_increase = r45['total_opps'] - r0['total_opps']
        factor = r45['total_opps'] / r0['total_opps'] if r0['total_opps'] > 0 else 0
        
        table.append([
            f"{window}h",
            r0['total_opps'],
            r45['total_opps'],
            f"+{opp_increase}",
            f"{factor:.1f}×"
        ])
    
    print("\n" + tabulate(table, headers=["Window", "Roll-Only Opps", "Roll+Pitch Opps", "Increase", "Factor"], tablefmt="grid"))
    
    print("\nExplanation:")
    print("  • Roll-only: 1 opportunity per pass (at max elevation)")
    print("  • Roll+pitch: 3-11 opportunities per pass (sampled across full duration)")
    print("  • Factor depends on average pass duration and sampling strategy")


def main():
    # Check server
    try:
        response = requests.get(f"{BASE_URL}/", timeout=2)
        if response.status_code != 200:
            print("❌ Backend server not running! Start with: ./run_dev.sh")
            return 1
    except:
        print("❌ Backend server not running! Start with: ./run_dev.sh")
        return 1
    
    results = run_comparison()
    
    print_summary_table(results)
    print_coverage_comparison(results)
    print_pitch_analysis(results)
    print_opportunity_explosion(results)
    
    print("\n" + "=" * 120)
    print("✅ ANALYSIS COMPLETE")
    print("=" * 120)
    print("\nKey Findings:")
    
    r12_0 = results["0deg_12h"]
    r12_45 = results["45deg_12h"]
    r24_0 = results["0deg_24h"]
    r24_45 = results["45deg_24h"]
    
    improvement_12 = r12_45['coverage'] - r12_0['coverage']
    improvement_24 = r24_45['coverage'] - r24_0['coverage']
    
    print(f"  • 12h window: {r12_0['coverage']} → {r12_45['coverage']} targets ({improvement_12:+d}, {improvement_12/r12_0['total_targets']*100:+.0f}%)")
    print(f"  • 24h window: {r24_0['coverage']} → {r24_45['coverage']} targets ({improvement_24:+d}, {improvement_24/r24_0['total_targets']*100:+.0f}%)")
    print(f"  • Opportunity increase: {r12_45['total_opps']/r12_0['total_opps']:.1f}× average")
    print(f"  • Max pitch used: {r12_45['max_pitch']:.1f}° (out of 45° available)")
    print(f"  • Full pass duration sampling: ACTIVE ✓")
    print(f"\n" + "=" * 120 + "\n")
    
    return 0


if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted")
        exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
