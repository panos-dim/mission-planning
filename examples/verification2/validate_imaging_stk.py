"""
STK Validation for Optical Imaging Mission (45° pointing)
Compare backend results with STK Chain Access data for Oct 14-15, 2025
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


def find_time_match(backend_time: datetime, stk_opps: List[Dict], 
                   tolerance_sec: int = 60) -> Tuple[bool, Dict, float]:
    """Find if backend opportunity matches any STK opportunity within tolerance."""
    for stk_opp in stk_opps:
        # Check if backend time falls within STK access window (with tolerance)
        start_with_margin = stk_opp['start_time'] - timedelta(seconds=tolerance_sec)
        stop_with_margin = stk_opp['stop_time'] + timedelta(seconds=tolerance_sec)
        
        if start_with_margin <= backend_time <= stop_with_margin:
            # Calculate time difference
            diff_start = abs((backend_time - stk_opp['start_time']).total_seconds())
            diff_stop = abs((backend_time - stk_opp['stop_time']).total_seconds())
            min_diff = min(diff_start, diff_stop)
            return True, stk_opp, min_diff
    
    return False, None, 0.0


def main():
    """Main validation execution."""
    
    script_dir = Path(__file__).parent
    verification_dir = script_dir.parent / "verification"
    
    print("="*80)
    print("STK VALIDATION: OPTICAL IMAGING MISSION (45° POINTING)")
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
    
    # Load targets from verification folder
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
    
    # Run backend for all targets
    print(f"\n⚙️  Running backend optical imaging mission...")
    print(f"  Mission type: Optical (SAR)")
    print(f"  Pointing angle: 45.0°")
    print(f"  Elevation mask: 0.0°")
    print(f"  Min separation: 0.0 km (no filtering)")
    print(f"  Time period: {start_time} to {end_time}")
    
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
    
    # Sort backend opportunities by time
    all_backend_opportunities.sort(key=lambda x: x['start_time'])
    
    # Compare with STK
    print(f"\n📊 Comparing with STK...")
    print(f"  STK opportunities: {len(stk_opportunities)}")
    print(f"  Backend opportunities: {len(all_backend_opportunities)}")
    
    matched = 0
    unmatched_backend = []
    time_differences = []
    
    for backend_opp in all_backend_opportunities:
        is_match, stk_match, time_diff = find_time_match(
            backend_opp['start_time'], 
            stk_opportunities, 
            tolerance_sec=60
        )
        
        if is_match:
            matched += 1
            time_differences.append(time_diff)
        else:
            unmatched_backend.append(backend_opp)
    
    # Find STK opportunities not matched by backend
    matched_stk_indices = set()
    for backend_opp in all_backend_opportunities:
        for idx, stk_opp in enumerate(stk_opportunities):
            start_with_margin = stk_opp['start_time'] - timedelta(seconds=60)
            stop_with_margin = stk_opp['stop_time'] + timedelta(seconds=60)
            if start_with_margin <= backend_opp['start_time'] <= stop_with_margin:
                matched_stk_indices.add(idx)
                break
    
    unmatched_stk = [stk_opportunities[i] for i in range(len(stk_opportunities)) 
                     if i not in matched_stk_indices]
    
    # Print results
    print(f"\n{'='*80}")
    print("VALIDATION RESULTS")
    print(f"{'='*80}")
    print(f"\n✅ Matched opportunities: {matched}/{len(all_backend_opportunities)}")
    print(f"   Match rate: {100*matched/len(all_backend_opportunities):.1f}%")
    
    if time_differences:
        avg_diff = sum(time_differences) / len(time_differences)
        max_diff = max(time_differences)
        print(f"\n⏱️  Timing accuracy:")
        print(f"   Average difference: {avg_diff:.1f} seconds")
        print(f"   Maximum difference: {max_diff:.1f} seconds")
    
    print(f"\n❌ Unmatched by backend: {len(unmatched_backend)}")
    if unmatched_backend and len(unmatched_backend) <= 10:
        print("   First unmatched backend opportunities:")
        for opp in unmatched_backend[:10]:
            print(f"   - {opp['target']} at {opp['start_time'].strftime('%m/%d %H:%M:%S')}")
    
    print(f"\n❌ Unmatched by STK: {len(unmatched_stk)}")
    if unmatched_stk and len(unmatched_stk) <= 10:
        print("   First unmatched STK opportunities:")
        for opp in unmatched_stk[:10]:
            print(f"   - Access #{opp['access_num']} at {opp['start_time'].strftime('%m/%d %H:%M:%S')}")
    
    # Save detailed comparison
    output_file = script_dir / "validation_comparison.csv"
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'Backend_Target', 'Backend_Start', 'Backend_End', 'Backend_Duration',
            'STK_Access', 'STK_Start', 'STK_End', 'STK_Duration', 
            'Time_Diff_Sec', 'Match_Status'
        ])
        writer.writeheader()
        
        for backend_opp in all_backend_opportunities:
            is_match, stk_match, time_diff = find_time_match(
                backend_opp['start_time'], 
                stk_opportunities, 
                tolerance_sec=60
            )
            
            row = {
                'Backend_Target': backend_opp['target'],
                'Backend_Start': backend_opp['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
                'Backend_End': backend_opp['end_time'].strftime('%Y-%m-%d %H:%M:%S'),
                'Backend_Duration': f"{backend_opp['duration_sec']:.1f}",
                'Match_Status': 'MATCHED' if is_match else 'UNMATCHED'
            }
            
            if is_match and stk_match:
                row['STK_Access'] = stk_match['access_num']
                row['STK_Start'] = stk_match['start_time'].strftime('%Y-%m-%d %H:%M:%S')
                row['STK_End'] = stk_match['stop_time'].strftime('%Y-%m-%d %H:%M:%S')
                row['STK_Duration'] = f"{stk_match['duration_sec']:.1f}"
                row['Time_Diff_Sec'] = f"{time_diff:.1f}"
            else:
                row['STK_Access'] = ''
                row['STK_Start'] = ''
                row['STK_End'] = ''
                row['STK_Duration'] = ''
                row['Time_Diff_Sec'] = ''
            
            writer.writerow(row)
    
    print(f"\n💾 Detailed comparison saved to: {output_file.name}")
    print(f"\n{'='*80}")


if __name__ == "__main__":
    main()
