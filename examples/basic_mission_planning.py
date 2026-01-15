#!/usr/bin/env python3
"""
Basic Mission Planning Example

This example demonstrates the core functionality of the satellite mission
planning tool with a simple workflow: TLE → propagation → visibility → visualization.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mission_planner import SatelliteOrbit, MissionPlanner, GroundTarget, Visualizer
from mission_planner.utils import setup_logging, create_sample_tle_file


def main():
    """Run basic mission planning example."""
    
    # Set up logging
    setup_logging("INFO")
    
    print("=== Satellite Mission Planning Tool - Basic Example ===\n")
    
    # Step 1: Create sample TLE file
    print("Step 1: Creating sample TLE data...")
    tle_file = Path(__file__).parent.parent / "data" / "sample_satellites.tle"
    tle_file.parent.mkdir(exist_ok=True)
    create_sample_tle_file(tle_file)
    print(f"✓ Sample TLE file created: {tle_file}\n")
    
    # Step 2: Load satellite orbit
    print("Step 2: Loading satellite orbit...")
    satellite_name = "ISS (ZARYA)"
    satellite = SatelliteOrbit.from_tle_file(tle_file, satellite_name)
    print(f"✓ Loaded satellite: {satellite}\n")
    
    # Step 3: Define ground targets
    print("Step 3: Defining ground targets...")
    targets = [
        GroundTarget(
            name="Houston Mission Control",
            latitude=29.5586,
            longitude=-95.0964,
            elevation_mask=10.0,
            description="NASA Johnson Space Center"
        ),
        GroundTarget(
            name="Moscow Mission Control", 
            latitude=55.9286,
            longitude=38.1420,
            elevation_mask=10.0,
            description="Roscosmos Mission Control Center"
        ),
        GroundTarget(
            name="Tokyo",
            latitude=35.6762,
            longitude=139.6503,
            elevation_mask=15.0,
            description="Tokyo, Japan"
        )
    ]
    
    for target in targets:
        print(f"  • {target}")
    print()
    
    # Step 4: Create mission planner
    print("Step 4: Creating mission planner...")
    planner = MissionPlanner(satellite, targets)
    print("✓ Mission planner initialized\n")
    
    # Step 5: Compute visibility windows
    print("Step 5: Computing satellite passes...")
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=24)
    
    passes = planner.compute_passes(start_time, end_time)
    
    # Display results
    total_passes = sum(len(target_passes) for target_passes in passes.values())
    print(f"✓ Found {total_passes} passes over {len(targets)} targets\n")
    
    # Show pass details
    print("Pass Details:")
    print("-" * 80)
    for target_name, target_passes in passes.items():
        if target_passes:
            print(f"\n{target_name}:")
            for i, pass_detail in enumerate(target_passes, 1):
                print(f"  Pass {i}: {pass_detail.start_time.strftime('%m/%d %H:%M')} - "
                      f"{pass_detail.end_time.strftime('%H:%M')} UTC, "
                      f"Max Elev: {pass_detail.max_elevation:.1f}°, "
                      f"Duration: {pass_detail.duration.total_seconds()/60:.1f}min")
        else:
            print(f"\n{target_name}: No passes found")
    
    # Step 6: Generate mission summary
    print("\n" + "="*80)
    summary = planner.get_mission_summary(passes)
    print("Mission Summary:")
    print(f"  • Satellite: {summary['satellite_name']}")
    print(f"  • Analysis period: {start_time.strftime('%Y-%m-%d %H:%M')} - "
          f"{end_time.strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"  • Total passes: {summary['total_passes']}")
    print(f"  • Targets with passes: {summary['targets_with_passes']}/{summary['targets_analyzed']}")
    print(f"  • Highest elevation: {summary['highest_elevation']}°")
    print(f"  • Total contact time: {summary['total_contact_time_minutes']:.1f} minutes")
    
    if summary['total_passes'] > 0:
        best = summary['best_pass']
        print(f"  • Best pass: {best['target']} at {best['time']} ({best['elevation']}°)")
    
    # Step 7: Create visualization
    print("\nStep 7: Creating mission visualization...")
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Create comprehensive mission analysis
    results = planner.run_mission_analysis(
        start_time, 
        duration_hours=24,
        output_dir=output_dir
    )
    
    print(f"✓ Mission analysis complete!")
    print(f"✓ Results saved to: {output_dir}")
    print(f"  • Mission overview map: {output_dir}/mission_overview.png")
    print(f"  • Pass timeline: {output_dir}/mission_overview_timeline.png")
    print(f"  • Schedule (JSON): {output_dir}/mission_schedule.json")
    print(f"  • Summary: {output_dir}/mission_summary.json")
    
    print("\n=== Example Complete ===")
    print("Check the output directory for generated files!")


if __name__ == "__main__":
    main()
