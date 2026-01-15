"""
Final STK Verification Script

Runs optimized backend and generates comprehensive comparison report.
"""

import csv
import sys
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.mission_planner.orbit import SatelliteOrbit
from src.mission_planner.targets import GroundTarget
from src.mission_planner.visibility import VisibilityCalculator


def parse_kml(kml_file: Path) -> Dict[str, Tuple[float, float]]:
    """Parse KML coordinates."""
    import xml.etree.ElementTree as ET
    tree = ET.parse(kml_file)
    root = tree.getroot()
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    
    targets = {}
    for placemark in root.findall('.//kml:Placemark', ns):
        name = placemark.find('kml:name', ns).text.strip()
        coords = placemark.find('.//kml:coordinates', ns).text.strip().split(',')
        targets[name] = (float(coords[0]), float(coords[1]))
    return targets


def fetch_tle() -> Tuple[str, str]:
    """Fetch fresh TLE."""
    url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    
    lines = response.text.strip().split('\n')
    for i in range(0, len(lines) - 2, 3):
        if "ICEYE-X44" in lines[i].upper():
            return (lines[i+1].strip(), lines[i+2].strip())
    raise ValueError("ICEYE-X44 not found")


def main():
    """Main execution."""
    
    script_dir = Path(__file__).parent
    
    print("="*80)
    print("FINAL STK VERIFICATION")
    print("="*80)
    
    # Load data
    print("\n📖 Loading STK data...")
    kml_file = script_dir / "coordinates.kml"
    stk_csv = script_dir / "stk_imaging_opportunities.csv"
    
    targets = parse_kml(kml_file)
    print(f"  Targets: {len(targets)}")
    
    with open(stk_csv, 'r') as f:
        rows = list(csv.DictReader(f))
        times = [datetime.strptime(r['Start_Time'], '%Y-%m-%d %H:%M:%S.%f') for r in rows]
        times.extend([datetime.strptime(r['End_Time'], '%Y-%m-%d %H:%M:%S.%f') for r in rows])
        start_time = min(times)
        end_time = max(times)
    
    print(f"  Period: {start_time.date()} to {end_time.date()}")
    print(f"  STK Opportunities: {len(rows)}")
    
    # Fetch TLE
    print(f"\n🌐 Fetching fresh TLE...")
    tle1, tle2 = fetch_tle()
    epoch_day = float(tle1[20:32])
    print(f"  TLE Epoch: Day {epoch_day:.2f}")
    
    satellite = SatelliteOrbit(tle_lines=[tle1, tle2], satellite_name="ICEYE-X44")
    
    # Run backend
    print(f"\n⚙️  Running optimized backend...")
    print(f"  Time-stepping: Adaptive (10-30s)")
    print(f"  Pointing angle: 45.0°")
    
    results = {}
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
        
        results[target_name] = [{
            'target': target_name,
            'start_time': p.start_time,
            'max_time': p.max_elevation_time,
            'end_time': p.end_time,
            'max_elevation': p.max_elevation,
            'duration_sec': (p.end_time - p.start_time).total_seconds()
        } for p in passes]
        
        if idx % 10 == 0:
            total = sum(len(r) for r in results.values())
            print(f"  Progress: {idx}/{len(targets)} targets, {total} opportunities")
    
    # Export
    output_file = script_dir / "backend_final_results.csv"
    rows = []
    for target_name in sorted(results.keys()):
        for p in results[target_name]:
            rows.append({
                'Target': target_name,
                'Start_Time': p['start_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'Max_Time': p['max_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'End_Time': p['end_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'Max_Elevation_Deg': f"{p['max_elevation']:.3f}",
                'Duration_Sec': p['duration_sec']
            })
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\n✅ Backend: {len(rows)} opportunities")
    print(f"💾 Saved: {output_file.name}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
