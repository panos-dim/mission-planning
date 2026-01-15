"""
Enhanced STK Validation with Detailed Timing Analysis
Compare start/end times and durations between backend and STK
"""

import csv
import sys
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.mission_planner.orbit import SatelliteOrbit
from src.mission_planner.targets import GroundTarget
from src.mission_planner.visibility import VisibilityCalculator


def parse_kml(kml_file: Path) -> Dict[str, Tuple[float, float]]:
    """Parse KML coordinates."""
    tree = ET.parse(kml_file)
    root = tree.getroot()
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    
    targets = {}
    for placemark in root.findall('.//kml:Placemark', ns):
        name = placemark.find('kml:name', ns).text.strip()
        coords = placemark.find('.//kml:coordinates', ns).text.strip().split(',')
        targets[name] = (float(coords[0]), float(coords[1]))
    return targets


def parse_stk_chain_csv(csv_file: Path) -> List[Dict]:
    """Parse STK Chain access CSV."""
    opportunities = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row['Access']:  # Skip empty rows
                continue
            opportunities.append({
                'access_num': int(row['Access']),
                'start_time': datetime.strptime(row['Start Time (UTCG)'], '%d %b %Y %H:%M:%S.%f'),
                'stop_time': datetime.strptime(row['Stop Time (UTCG)'], '%d %b %Y %H:%M:%S.%f'),
                'duration_sec': float(row['Duration (sec)'])
            })
    return opportunities


def fetch_tle() -> Tuple[str, str]:
    """Fetch fresh ICEYE-X44 TLE."""
    url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    
    lines = response.text.strip().split('\n')
    for i in range(0, len(lines) - 2, 3):
        if "ICEYE-X44" in lines[i].upper():
            return (lines[i+1].strip(), lines[i+2].strip())
    raise ValueError("ICEYE-X44 not found in Celestrak data")


def find_best_match(backend_opp: Dict, stk_opps: List[Dict]) -> Tuple[Dict, Dict]:
    """
    Find best matching STK opportunity for backend opportunity.
    Returns match statistics including start/end time differences.
    """
    best_match = None
    best_stats = None
    min_combined_diff = float('inf')
    
    for stk_opp in stk_opps:
        # Calculate time differences
        start_diff = abs((backend_opp['start_time'] - stk_opp['start_time']).total_seconds())
        end_diff = abs((backend_opp['end_time'] - stk_opp['stop_time']).total_seconds())
        duration_diff = abs(backend_opp['duration_sec'] - stk_opp['duration_sec'])
        
        # Combined metric: average of start and end differences
        combined_diff = (start_diff + end_diff) / 2
        
        # Consider it a match if within reasonable bounds
        if start_diff <= 120 and end_diff <= 120 and combined_diff < min_combined_diff:
            min_combined_diff = combined_diff
            best_match = stk_opp
            best_stats = {
                'start_diff_sec': start_diff,
                'end_diff_sec': end_diff,
                'duration_diff_sec': duration_diff,
                'combined_diff_sec': combined_diff
            }
    
    return best_match, best_stats


def main():
    """Main validation execution."""
    
    script_dir = Path(__file__).parent
    verification_dir = script_dir.parent / "verification"
    
    print("="*80)
    print("DETAILED STK VALIDATION: START/END TIME & DURATION ANALYSIS")
    print("="*80)
    
    # Load STK data
    print("\n📖 Loading STK Chain Access data...")
    stk_csv = script_dir / "Chain1_Time_Ordered_Access.csv"
    stk_opportunities = parse_stk_chain_csv(stk_csv)
    
    print(f"  STK Opportunities: {len(stk_opportunities)}")
    if stk_opportunities:
        print(f"  Period: {stk_opportunities[0]['start_time']} to {stk_opportunities[-1]['stop_time']}")
        start_time = stk_opportunities[0]['start_time']
        end_time = stk_opportunities[-1]['stop_time']
    
    # Load targets
    print(f"\n📍 Loading targets...")
    kml_file = verification_dir / "coordinates.kml"
    targets = parse_kml(kml_file)
    print(f"  Targets loaded: {len(targets)}")
    
    # Fetch TLE
    print(f"\n🌐 Fetching ICEYE-X44 TLE...")
    tle1, tle2 = fetch_tle()
    epoch_day = float(tle1[20:32])
    print(f"  TLE Epoch: Day {epoch_day:.2f}")
    
    satellite = SatelliteOrbit(tle_lines=[tle1, tle2], satellite_name="ICEYE-X44")
    
    # Run backend
    print(f"\n⚙️  Running backend optical imaging mission...")
    print(f"  Mission type: Optical (SAR)")
    print(f"  Pointing angle: 45.0°")
    print(f"  Elevation mask: 0.0°")
    
    all_backend_opportunities = []
    
    for idx, (target_name, (lon, lat)) in enumerate(sorted(targets.items()), 1):
        target = GroundTarget(
            name=target_name,
            latitude=lat,
            longitude=lon,
            mission_type='imaging',
            pointing_angle=45.0,
            elevation_mask=0.0
        )
        target.imaging_type = 'SAR'
        target.min_imaging_separation_km = 0.0
        
        vis_calc = VisibilityCalculator(satellite, use_adaptive=True)
        passes = vis_calc.find_passes(target, start_time, end_time, time_step_seconds=30)
        
        for p in passes:
            all_backend_opportunities.append({
                'target': target_name,
                'start_time': p.start_time,
                'max_time': p.max_elevation_time,
                'end_time': p.end_time,
                'max_elevation': p.max_elevation,
                'duration_sec': (p.end_time - p.start_time).total_seconds()
            })
        
        if idx % 10 == 0:
            print(f"  Progress: {idx}/{len(targets)} targets, {len(all_backend_opportunities)} opportunities")
    
    print(f"\n✅ Backend found: {len(all_backend_opportunities)} opportunities")
    
    # Sort by time
    all_backend_opportunities.sort(key=lambda x: x['start_time'])
    
    # Detailed comparison
    print(f"\n{'='*80}")
    print("DETAILED TIMING COMPARISON")
    print(f"{'='*80}")
    
    matched_opportunities = []
    unmatched_backend = []
    
    start_diffs = []
    end_diffs = []
    duration_diffs = []
    
    for backend_opp in all_backend_opportunities:
        stk_match, stats = find_best_match(backend_opp, stk_opportunities)
        
        if stk_match and stats:
            matched_opportunities.append({
                'backend': backend_opp,
                'stk': stk_match,
                'stats': stats
            })
            start_diffs.append(stats['start_diff_sec'])
            end_diffs.append(stats['end_diff_sec'])
            duration_diffs.append(stats['duration_diff_sec'])
        else:
            unmatched_backend.append(backend_opp)
    
    # Calculate statistics
    if matched_opportunities:
        print(f"\n✅ Matched: {len(matched_opportunities)}/{len(all_backend_opportunities)}")
        print(f"   Match rate: {100*len(matched_opportunities)/len(all_backend_opportunities):.1f}%")
        
        print(f"\n📊 START TIME ANALYSIS:")
        print(f"   Average difference: {sum(start_diffs)/len(start_diffs):.2f} seconds")
        print(f"   Median difference:  {sorted(start_diffs)[len(start_diffs)//2]:.2f} seconds")
        print(f"   Maximum difference: {max(start_diffs):.2f} seconds")
        print(f"   Minimum difference: {min(start_diffs):.2f} seconds")
        
        print(f"\n📊 END TIME ANALYSIS:")
        print(f"   Average difference: {sum(end_diffs)/len(end_diffs):.2f} seconds")
        print(f"   Median difference:  {sorted(end_diffs)[len(end_diffs)//2]:.2f} seconds")
        print(f"   Maximum difference: {max(end_diffs):.2f} seconds")
        print(f"   Minimum difference: {min(end_diffs):.2f} seconds")
        
        print(f"\n📊 DURATION ANALYSIS:")
        print(f"   Average difference: {sum(duration_diffs)/len(duration_diffs):.2f} seconds")
        print(f"   Median difference:  {sorted(duration_diffs)[len(duration_diffs)//2]:.2f} seconds")
        print(f"   Maximum difference: {max(duration_diffs):.2f} seconds")
        
        # Accuracy breakdown
        print(f"\n🎯 ACCURACY BREAKDOWN:")
        within_10s_start = sum(1 for d in start_diffs if d <= 10)
        within_30s_start = sum(1 for d in start_diffs if d <= 30)
        within_60s_start = sum(1 for d in start_diffs if d <= 60)
        
        within_10s_end = sum(1 for d in end_diffs if d <= 10)
        within_30s_end = sum(1 for d in end_diffs if d <= 30)
        within_60s_end = sum(1 for d in end_diffs if d <= 60)
        
        total = len(matched_opportunities)
        print(f"   Start times within ±10s: {within_10s_start}/{total} ({100*within_10s_start/total:.1f}%)")
        print(f"   Start times within ±30s: {within_30s_start}/{total} ({100*within_30s_start/total:.1f}%)")
        print(f"   Start times within ±60s: {within_60s_start}/{total} ({100*within_60s_start/total:.1f}%)")
        print(f"   End times within ±10s:   {within_10s_end}/{total} ({100*within_10s_end/total:.1f}%)")
        print(f"   End times within ±30s:   {within_30s_end}/{total} ({100*within_30s_end/total:.1f}%)")
        print(f"   End times within ±60s:   {within_60s_end}/{total} ({100*within_60s_end/total:.1f}%)")
    
    # Show worst mismatches
    if matched_opportunities:
        print(f"\n⚠️  LARGEST START TIME MISMATCHES (Top 5):")
        worst_start = sorted(matched_opportunities, key=lambda x: x['stats']['start_diff_sec'], reverse=True)[:5]
        for i, match in enumerate(worst_start, 1):
            backend = match['backend']
            stk = match['stk']
            diff = match['stats']['start_diff_sec']
            print(f"   {i}. {backend['target']}: {diff:.1f}s difference")
            print(f"      Backend: {backend['start_time'].strftime('%m/%d %H:%M:%S')}")
            print(f"      STK:     {stk['start_time'].strftime('%m/%d %H:%M:%S')}")
        
        print(f"\n⚠️  LARGEST END TIME MISMATCHES (Top 5):")
        worst_end = sorted(matched_opportunities, key=lambda x: x['stats']['end_diff_sec'], reverse=True)[:5]
        for i, match in enumerate(worst_end, 1):
            backend = match['backend']
            stk = match['stk']
            diff = match['stats']['end_diff_sec']
            print(f"   {i}. {backend['target']}: {diff:.1f}s difference")
            print(f"      Backend: {backend['end_time'].strftime('%m/%d %H:%M:%S')}")
            print(f"      STK:     {stk['stop_time'].strftime('%m/%d %H:%M:%S')}")
    
    # Save detailed CSV
    output_file = script_dir / "detailed_timing_comparison.csv"
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'Target', 'Backend_Start', 'STK_Start', 'Start_Diff_Sec',
            'Backend_End', 'STK_End', 'End_Diff_Sec',
            'Backend_Duration', 'STK_Duration', 'Duration_Diff_Sec',
            'Backend_Max_Elev', 'Match_Status'
        ])
        writer.writeheader()
        
        for match in matched_opportunities:
            backend = match['backend']
            stk = match['stk']
            stats = match['stats']
            
            writer.writerow({
                'Target': backend['target'],
                'Backend_Start': backend['start_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'STK_Start': stk['start_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'Start_Diff_Sec': f"{stats['start_diff_sec']:.2f}",
                'Backend_End': backend['end_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'STK_End': stk['stop_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'End_Diff_Sec': f"{stats['end_diff_sec']:.2f}",
                'Backend_Duration': f"{backend['duration_sec']:.1f}",
                'STK_Duration': f"{stk['duration_sec']:.1f}",
                'Duration_Diff_Sec': f"{stats['duration_diff_sec']:.2f}",
                'Backend_Max_Elev': f"{backend['max_elevation']:.2f}",
                'Match_Status': 'MATCHED'
            })
        
        # Add unmatched
        for backend in unmatched_backend:
            writer.writerow({
                'Target': backend['target'],
                'Backend_Start': backend['start_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'STK_Start': '',
                'Start_Diff_Sec': '',
                'Backend_End': backend['end_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'STK_End': '',
                'End_Diff_Sec': '',
                'Backend_Duration': f"{backend['duration_sec']:.1f}",
                'STK_Duration': '',
                'Duration_Diff_Sec': '',
                'Backend_Max_Elev': f"{backend['max_elevation']:.2f}",
                'Match_Status': 'UNMATCHED'
            })
    
    print(f"\n💾 Detailed timing comparison saved to: {output_file.name}")
    print(f"\nℹ️  NOTE: STK Chain data does not include elevation information.")
    print(f"   Elevation validation requires detailed STK report with max elevation data.")
    print(f"\n{'='*80}")


if __name__ == "__main__":
    main()
