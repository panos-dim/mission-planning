# Satellite Mission Planning Tool

A modular, offline-capable satellite mission planning tool built in Python. This tool loads TLE (Two-Line Element) data, propagates satellite orbits, computes visibility windows over ground targets, and creates beautiful visualizations using Cartopy.

## Features

- **Orbit Propagation**: Uses the `orbit-predictor` library for accurate satellite orbit calculations
- **Visibility Analysis**: Computes satellite visibility windows over ground targets with configurable elevation masks
- **Beautiful Visualizations**: Creates clean 2D world map visualizations using Cartopy showing:
  - Satellite ground tracks over time
  - Target points and coverage areas
  - Optional day/night terminator shading
- **Structured Output**: Generates JSON/CSV mission schedules and static map images
- **Modular Design**: Clean separation between data handling, orbit logic, and visualization

## Installation

This project uses PDM for dependency management. Install PDM first:

```bash
pip install pdm
```

Then install the project dependencies:

```bash
pdm install
```

For development dependencies:

```bash
pdm install -d
```

## Quick Start

```python
from mission_planner import SatelliteOrbit, MissionPlanner, Visualizer
from mission_planner.targets import GroundTarget
from datetime import datetime, timedelta

# Load satellite from TLE
satellite = SatelliteOrbit.from_tle_file("iss.tle", "ISS (ZARYA)")

# Define ground target
target = GroundTarget(
    name="Mission Control",
    latitude=29.5586,  # Houston
    longitude=-95.0964,
    elevation_mask=10.0  # degrees
)

# Create mission planner
planner = MissionPlanner(satellite, [target])

# Compute visibility windows
start_time = datetime.utcnow()
end_time = start_time + timedelta(days=1)
imaging_opportunities = planner.compute_passes(start_time, end_time)

# Generate visualization
visualizer = Visualizer()
visualizer.plot_ground_track(satellite, start_time, end_time)
visualizer.plot_targets([target])
visualizer.save_map("mission_map.png")

# Export schedule
planner.export_schedule(imaging_opportunities, "mission_schedule.json")
```

## Project Structure

```text
src/mission_planner/
├── __init__.py
├── cli.py              # Command-line interface
├── orbit.py            # Satellite orbit propagation
├── targets.py          # Ground target definitions
├── visibility.py       # Visibility calculations
├── visualization.py    # Cartopy-based plotting
├── planner.py         # Main mission planning logic
└── utils.py           # Utility functions
```

## CLI Usage

The tool provides 7 comprehensive commands for satellite mission planning:

### 1. Download TLE Data

```bash
# Get latest TLE data from CelesTrak
pdm run mission-planner download-tle \
--source celestrak_active \
--output data/active_satellites.tle

# List available TLE sources
pdm run mission-planner list-sources

# Download from custom URL
pdm run mission-planner download-tle \
--url "https://example.com/satellites.tle" \
--output data/custom_satellites.tle
```

### 2. Find Next Satellite Imaging Opportunity

```bash
# Find next ICEYE-X44 imaging opportunity over Space42 (UAE)
pdm run mission-planner next-pass \
--tle data/active_satellites.tle \
--satellite "ICEYE-X44" \
--target "Space42" 24.440534486449263 54.82664910413539 \
--elevation-mask 5 --hours 48
```

### 3. Plan Complete Mission

```bash
# Plan 24-hour mission over Space42
pdm run mission-planner plan \
--tle data/active_satellites.tle \
--satellite "ICEYE-X44" \
--target "Space42" 24.440534486449263 54.82664910413539 \
--mission-type communication
--duration 24 --output output/mission_results/ \
--format json --elevation-mask 10

# Multi-target mission planning
pdm run mission-planner plan \
--tle data/active_satellites.tle \
--satellite "ICEYE-X44" \
--target "Space42" 24.440534486449263 54.82664910413539 \
--target "Dubai" 25.2048 55.2708 \
--duration 12 --output output/multi_target_mission/
```

### 4. Generate Visualizations

```bash
# Create ground track visualization
pdm run mission-planner visualize \
--tle data/active_satellites.tle \
--satellite "ICEYE-X44" \
--duration 6 --output output/ground_track.png

# Visualization with targets
pdm run mission-planner visualize \
--tle data/active_satellites.tle \
--satellite "ICEYE-X44" \
--targets data/targets.json \
--duration 3 --output output/mission_overview.png
```

### 5. Create Sample Data

```bash
# Create sample TLE file with common satellites
pdm run mission-planner create-sample-tle \
--output data/sample_satellites.tle

# Create sample targets file
pdm run mission-planner create-sample-targets \
--output data/sample_targets.json
```

### 6. Available TLE Sources

- `celestrak_active` - All active satellites (recommended)
- `celestrak_visual` - Bright satellites visible to naked eye  
- `celestrak_weather` - Weather satellites
- `celestrak_stations` - Space stations (ISS, etc.)
- `celestrak_cubesat` - CubeSats
- `celestrak_noaa` - NOAA satellites
- `celestrak_goes` - GOES weather satellites
- `celestrak_resource` - Earth resource satellites
- `celestrak_other` - Other communication satellites

## Requirements

- Python 3.11+
- orbit-predictor >= 1.15.0
- cartopy >= 0.22.0
- matplotlib >= 3.7.0
- numpy >= 1.24.0
- pandas >= 2.0.0

## License

MIT License - see LICENSE file for details.




cone of 5deg for targeting on top of the target