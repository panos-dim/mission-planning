# Mission Types in Satellite Mission Planning

## Overview

The satellite mission planning tool now supports two distinct mission types, each with different visibility constraints:

## 🛰️ Mission Types

### 📡 **Communication Mission**

**Purpose**: Data downlink/uplink between satellite and ground station

**Constraints**:

- Satellite elevation ≥ elevation mask (default: 10°)
- Maximum distance: ~3,400km (at 10° elevation)
- No pointing cone constraint

**Use Cases**:

- Telemetry download
- Command uplink
- Data relay

**Example**:

```bash
pdm run python -m src.mission_planner.cli plan \
  --tle data/active_satellites.tle \
  --satellite "ICEYE-X44" \
  --target "Space42" 24.44 54.83 \
  --mission-type communication \
  --elevation-mask 10.0
```

### 📸 **Imaging Mission**

**Purpose**: Earth observation and target imaging

**Constraints**:

- Target within satellite's pointing cone
- Pointing angle: ±5° (default) from nadir
- Maximum imaging distance: ~52km (at 5°, 600km altitude)
- No elevation constraint (satellite looks down)

**Key Differences from Communication**:

- **Much more restrictive**: Imaging coverage ~158km radius vs ~2856km for communication
- **Geometric constraint**: Based on satellite's downward-looking cone, not ground station elevation
- **Fewer opportunities**: Typically 1-3 imaging opportunities vs 9+ communication opportunities over same period
- **Shorter duration**: Often seconds/minutes vs longer communication windows

**Coverage Analysis** (ICEYE-X44 example over 60.6 hours):

- **Communication (10° elevation)**: 9 opportunities, ~52 minutes total contact time
- **Imaging (15° pointing)**: 1 opportunity, instantaneous contact at closest approach
- **Imaging (5° pointing)**: ~52km max distance from nadir
- **Imaging (15° pointing)**: ~158km max distance from nadir

**Use Cases**:

- Earth observation
- Target reconnaissance
- Agricultural monitoring

**Example**:

```bash
pdm run python -m src.mission_planner.cli plan \
  --tle data/active_satellites.tle \
  --satellite "ICEYE-X44" \
  --target "Space42" 24.44 54.83 \
  --mission-type imaging \
  --pointing-angle 5.0


## 📊 Comparison Results (ICEYE-X44 over Space42, UAE)

| Mission Type  | Opportunities Found | Best Elevation | Total Contact Time | Max Distance |
|---------------|---------------------|----------------|-------------------|--------------||
| Communication | 3                   | 50.3°          | 17.5 minutes      | ~3,400km     |
| Imaging       | 0                   | N/A            | 0 minutes         | ~52km        |

## 🔍 Analysis

### Why No Imaging Opportunities for ICEYE-X44?

{{ ... }}

- It primarily passes over polar regions (Arctic/Antarctic)
- UAE is at 24°N latitude (relatively low latitude)
- The satellite's ground track rarely comes within 52km of UAE targets
- Communication is possible from much greater distances (up to 3,400km)

### Pointing Angle Impact

| Pointing Angle | Max Imaging Distance | Imaging Opportunities |
|----------------|---------------------|----------------------|
| 5° (typical)   | 52.5km             | Very limited         |
| 10°            | 105.8km            | Limited              |
| 15°            | 160.8km            | Moderate             |
| 30°            | 346.4km            | Good                 |

## 🎯 Recommendations

### For UAE Targets (Low Latitude)

1. **Use `communication` mission type** for data downlink operations
2. **Consider higher-inclination satellites** for imaging missions
3. **Use larger pointing angles** (10-20°) if imaging is required
4. **Plan multiple days** to increase imaging opportunities

### For Polar Targets (High Latitude)

1. **All mission types work well** with polar-orbiting satellites
2. **Imaging opportunities are frequent** due to orbital geometry

### General Guidelines

- **Communication missions**: Always use for telemetry and data operations
- **Imaging missions**: Best for dedicated Earth observation satellites
- **Pointing angles**: Start with 5°, increase if no opportunities found

## 📊 **Mission Type Comparison**

### Real-World Example: ICEYE-X44 over Space42 (UAE)

**Test Period**: 60.6 hours (Aug 4-6, 2025)
**Satellite**: ICEYE-X44 (591km altitude, polar orbit)
**Target**: Space42 (24.44°N, 54.83°E)

| Mission Type | Constraint | Coverage Radius | Opportunities Found | Total Contact Time | Opportunity Duration |
|--------------|------------|-----------------|---------------------|--------------------|-----------------------|
| **Communication** | 10° elevation | ~2856 km | **9 opportunities** | 52.0 minutes | 2-8 minutes each |
| **Imaging** | 15° pointing | ~158 km | **1 opportunity** | 0.0 minutes | Instantaneous |
| **Imaging** | 5° pointing | ~52 km | ~0-1 opportunities | <1 minute | Seconds |

### Key Insights

- **Imaging is 9x more restrictive** than communication for the same target
- **Pointing angle matters**: 15° gives ~3x larger coverage than 5°
- **Opportunity duration**: Communication opportunities last minutes, imaging opportunities are often instantaneous
- **Mission planning**: Use communication for regular operations, imaging for specific target acquisition

## 🔠️ Technical Details

### Communication Constraint

```python
elevation >= target.elevation_mask
```

### Imaging Constraint

```python
ground_distance <= satellite_altitude * tan(pointing_angle)
```

## 📈 Future Enhancements

1. **Constellation support**: Multiple satellites for better coverage
2. **Orbital optimization**: Suggest optimal satellite orbits for targets
3. **Mission scheduling**: Optimize timing across multiple mission types
4. **Coverage analysis**: Visualize imaging footprints and communication zones
