#!/usr/bin/env python3
"""
CLI Demo Script

This script demonstrates the command-line interface capabilities
of the satellite mission planning tool.
"""

import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a command and display the output."""
    print(f"\n{'='*60}")
    print(f"DEMO: {description}")
    print(f"Command: {cmd}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running command: {e}")
        return False

def main():
    """Run CLI demonstration."""
    
    print("=== Satellite Mission Planning Tool - CLI Demo ===")
    print("This demo shows the command-line interface capabilities.")
    
    # Demo 1: Show help
    run_command("pdm run mission-planner --help", "Show main help")
    
    # Demo 2: Create sample TLE file
    run_command("pdm run mission-planner create-sample-tle --output data/demo_satellites.tle", 
                "Create sample TLE file")
    
    # Demo 3: Show next pass
    run_command('pdm run mission-planner next-pass --tle data/demo_satellites.tle --satellite "ISS (ZARYA)" --target "New York" 40.7128 -74.0060', 
                "Find next ISS pass over New York")
    
    # Demo 4: Plan a mission
    run_command('pdm run mission-planner plan --tle data/demo_satellites.tle --satellite "ISS (ZARYA)" --target "New York" 40.7128 -74.0060 --target "London" 51.5074 -0.1278 --duration 12 --output output/cli_demo --format json', 
                "Plan 12-hour mission with two targets")
    
    # Demo 5: Create visualization
    run_command('pdm run mission-planner visualize --tle data/demo_satellites.tle --satellite "ISS (ZARYA)" --duration 3 --output output/cli_demo_viz.png', 
                "Create 3-hour ground track visualization")
    
    # Demo 6: List TLE sources
    run_command("pdm run mission-planner list-sources", 
                "List available TLE data sources")
    
    print(f"\n{'='*60}")
    print("CLI DEMO COMPLETE")
    print("Check the output/ directory for generated files!")
    print('='*60)

if __name__ == "__main__":
    main()
