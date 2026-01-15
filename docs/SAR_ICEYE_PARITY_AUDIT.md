# SAR ICEYE-Parity Audit Document

This document provides a comprehensive description of the SAR (Synthetic Aperture Radar) mission analysis and planning implementation, specifically its alignment with ICEYE tasking API concepts.

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [ICEYE Tasking Concepts Mapping](#3-iceye-tasking-concepts-mapping)
4. [Implementation Details](#4-implementation-details)
5. [SAR Mode Specifications](#5-sar-mode-specifications)
6. [Technical Algorithms](#6-technical-algorithms)
7. [API Reference](#7-api-reference)
8. [Frontend Implementation](#8-frontend-implementation)
9. [CZML Visualization](#9-czml-visualization)
10. [Known Approximations](#10-known-approximations)
11. [Implementation Status](#11-implementation-status)
12. [Validation Plan](#12-validation-plan)
13. [Future Enhancements](#13-future-enhancements)
14. [References](#14-references)

---

## 1. Overview

### 1.1 Purpose

This PR adds SAR mission analysis and planning capabilities to the satellite mission planning tool, achieving "ICEYE-parity" - meaning the system supports SAR-specific inputs, left/right-looking swath visualization, and tasking concepts aligned with ICEYE's API.

### 1.2 Key Capabilities

- **SAR Mission Analysis**: Compute imaging opportunities with SAR-specific attributes
- **Look Side Detection**: Automatic LEFT/RIGHT determination based on geometry
- **Pass Direction Filtering**: ASCENDING/DESCENDING pass filtering
- **Incidence Angle Constraints**: Mode-specific incidence ranges with quality scoring
- **Swath Visualization**: Color-coded left/right swath polygons in Cesium
- **Day/Night Operation**: SAR works regardless of illumination (no optical constraints)

### 1.3 What "SAR Done" Means

After this PR:
- ✅ User can run SAR mission analysis and get SAR imaging opportunities
- ✅ User can run SAR mission planning on those opportunities
- ✅ Cesium shows left-looking and right-looking swaths (not just points)
- ✅ Inputs align with ICEYE Tasking API concepts
- ✅ No optical-only concepts (illumination/day-night) block SAR

---

## 2. Architecture

### 2.1 File Structure

```
mission-planning/
├── config/
│   └── sar_modes.yaml              # SAR mode specifications (ICEYE-aligned)
├── src/mission_planner/
│   ├── sar_config.py               # SAR configuration management
│   ├── sar_visibility.py           # SAR visibility analysis
│   └── visibility.py               # Base visibility (extended for SAR)
├── backend/
│   ├── main.py                     # API endpoints with SAR support
│   └── sar_czml.py                 # SAR CZML swath generation
├── frontend/src/
│   ├── types/index.ts              # SAR TypeScript types
│   └── components/
│       └── MissionParameters.tsx   # SAR inputs panel
└── docs/
    └── SAR_ICEYE_PARITY_AUDIT.md   # This document
```

### 2.2 Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend      │     │    Backend       │     │   Cesium        │
│   SAR Panel     │────▶│    /analyze      │────▶│   Swath         │
│                 │     │                  │     │   Polygons      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                       │                        │
        ▼                       ▼                        ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ SARInputParams  │     │ SARVisibility    │     │ SARCZMLGenerator│
│ - imaging_mode  │     │ Calculator       │     │ - swath packets │
│ - look_side     │     │ - look side calc │     │ - dynamic swath │
│ - pass_direction│     │ - incidence calc │     │ - color by side │
│ - incidence     │     │ - filtering      │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

### 2.3 Class Hierarchy

```python
# Configuration
SARConfigManager          # Singleton config loader
├── SARModeSpec           # Per-mode specifications
├── SARSpacecraftSpec     # Spacecraft constraints
└── SARConstraints        # SAR-specific constraints

# Data Types
SARInputParams            # User input parameters
SAROpportunityData        # Per-opportunity SAR data
SARPassDetails            # Extended PassDetails with SAR

# Analysis
SARVisibilityCalculator   # SAR opportunity computation
├── _compute_look_side()
├── _compute_pass_direction()
├── _compute_incidence_angle()
└── _compute_sar_quality()

# Visualization
SARCZMLGenerator          # CZML swath generation
├── generate_swath_packets()
└── generate_dynamic_swath_packet()
```

---

## 3. ICEYE Tasking Concepts Mapping

### 3.1 Complete Mapping Table

| ICEYE Concept | Our Field | Type | Location | Notes |
|---------------|-----------|------|----------|-------|
| **Imaging Mode** | `imaging_mode` | Enum | `SARInputParams` | spot, strip, scan, dwell |
| **Look Side** | `look_side` | Enum | `SARInputParams` | LEFT, RIGHT, ANY |
| **Pass Direction** | `pass_direction` | Enum | `SARInputParams` | ASCENDING, DESCENDING, ANY |
| **Incidence Min** | `incidence_min_deg` | float | `SARInputParams` | Minimum off-nadir angle |
| **Incidence Max** | `incidence_max_deg` | float | `SARInputParams` | Maximum off-nadir angle |
| **Incidence Center** | `incidence_center_deg` | float | `SAROpportunityData` | Computed center angle |
| **Incidence Near** | `incidence_near_deg` | float | `SAROpportunityData` | Near swath edge |
| **Incidence Far** | `incidence_far_deg` | float | `SAROpportunityData` | Far swath edge |
| **Swath Width** | `swath_width_km` | float | `SAROpportunityData` | Cross-track dimension |
| **Scene Length** | `scene_length_km` | float | `SAROpportunityData` | Along-track dimension |

### 3.2 Enum Definitions

```python
class SARMode(Enum):
    SPOT = "spot"       # High-resolution spotlight
    STRIP = "strip"     # Standard stripmap
    SCAN = "scan"       # Wide area ScanSAR
    DWELL = "dwell"     # Extended dwell mode

class LookSide(Enum):
    LEFT = "LEFT"       # Antenna points left of track
    RIGHT = "RIGHT"     # Antenna points right of track
    ANY = "ANY"         # System selects optimal

class PassDirection(Enum):
    ASCENDING = "ASCENDING"     # Northbound pass
    DESCENDING = "DESCENDING"   # Southbound pass
    ANY = "ANY"                 # Either direction
```

---

## 4. Implementation Details

### 4.1 SAR Configuration (`config/sar_modes.yaml`)

The configuration file defines ICEYE-aligned mode specifications:

```yaml
modes:
  spot:
    display_name: "Spot"
    description: "High-resolution spotlight mode"
    incidence_angle:
      recommended_min: 15.0
      recommended_max: 35.0
      absolute_min: 10.0
      absolute_max: 45.0
    scene:
      width_km: 5.0
      length_km: 5.0
    collection:
      duration_s: 10.0
      azimuth_resolution_m: 0.5
      range_resolution_m: 0.5
    quality:
      optimal_incidence_deg: 25.0
      quality_model: "band"

  strip:
    # ... similar structure for strip mode

  scan:
    # ... similar structure for scan mode

  dwell:
    # ... similar structure for dwell mode
```

### 4.2 SAR Config Manager (`src/mission_planner/sar_config.py`)

Key classes and functions:

```python
@dataclass
class SARInputParams:
    """User-provided SAR mission parameters (ICEYE-aligned)."""
    imaging_mode: SARMode = SARMode.STRIP
    incidence_min_deg: Optional[float] = None
    incidence_max_deg: Optional[float] = None
    look_side: LookSide = LookSide.ANY
    pass_direction: PassDirection = PassDirection.ANY
    priority: int = 3
    exclusivity: str = "STANDARD"

@dataclass
class SAROpportunityData:
    """SAR-specific data for an imaging opportunity."""
    look_side: LookSide
    pass_direction: PassDirection
    incidence_center_deg: float
    incidence_near_deg: Optional[float] = None
    incidence_far_deg: Optional[float] = None
    swath_width_km: float = 30.0
    scene_length_km: float = 50.0
    imaging_mode: SARMode = SARMode.STRIP
    quality_score: float = 0.0

class SARConfigManager:
    """Singleton manager for SAR mode configurations."""
    def get_mode_spec(self, mode: SARMode) -> SARModeSpec
    def get_default_incidence_range(self, mode: SARMode) -> Tuple[float, float]
    def get_swath_width(self, mode: SARMode) -> float
    def validate_sar_params(self, params: SARInputParams) -> Tuple[bool, List[str]]
```

### 4.3 SAR Visibility Calculator (`src/mission_planner/sar_visibility.py`)

Core analysis class:

```python
class SARVisibilityCalculator:
    """SAR-specific visibility and opportunity analysis."""

    def __init__(self, base_calculator: VisibilityCalculator, sar_params: SARInputParams):
        self.base_calc = base_calculator
        self.sar_params = sar_params
        self.mode_spec = get_sar_config().get_mode_spec(sar_params.imaging_mode)

    def compute_sar_passes(
        self,
        target_lat: float,
        target_lon: float,
        target_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[SARPassDetails]:
        """Compute SAR imaging opportunities for a target."""
        # 1. Get base visibility passes
        # 2. Filter by SAR constraints (incidence, look side, pass direction)
        # 3. Enrich with SAR-specific data
        # 4. Return filtered and enriched passes

    def _compute_look_side(self, sat_pos, sat_vel, target_pos) -> LookSide:
        """Determine look side from satellite-target geometry."""

    def _compute_pass_direction(self, velocity, position) -> PassDirection:
        """Determine pass direction from velocity vector."""

    def _compute_incidence_angle(self, sat_pos, target_pos) -> float:
        """Compute incidence angle (off-nadir) to target."""

    def _compute_sar_quality(self, incidence_deg: float) -> float:
        """Compute SAR imaging quality using band model."""
```

### 4.4 Backend API Integration (`backend/main.py`)

Pydantic model for SAR parameters:

```python
class SARInputParams(BaseModel):
    """SAR mission parameters aligned with ICEYE tasking concepts."""

    imaging_mode: str = Field(default="strip", description="SAR imaging mode")
    incidence_min_deg: Optional[float] = Field(default=None)
    incidence_max_deg: Optional[float] = Field(default=None)
    look_side: str = Field(default="ANY", description="LEFT, RIGHT, or ANY")
    pass_direction: str = Field(default="ANY", description="ASCENDING, DESCENDING, or ANY")
    priority: int = Field(default=3, description="Task priority (1-5)")
    exclusivity: str = Field(default="STANDARD")

    @field_validator("imaging_mode")
    @classmethod
    def validate_imaging_mode(cls, v: str) -> str:
        valid_modes = ["spot", "strip", "scan", "dwell"]
        if v.lower() not in valid_modes:
            raise ValueError(f"Invalid SAR mode: {v}")
        return v.lower()
```

MissionRequest extension:

```python
class MissionRequest(BaseModel):
    # ... existing fields ...

    # SAR-specific parameters (ICEYE-parity)
    sar: Optional[SARInputParams] = Field(
        default=None,
        description="SAR-specific parameters (only used when imaging_type='sar')"
    )
```

---

## 5. SAR Mode Specifications

### 5.1 Mode Comparison Table

| Mode | Incidence Range | Swath Width | Scene Length | Resolution | Use Case |
|------|-----------------|-------------|--------------|------------|----------|
| **Spot** | 15° - 35° | 5 km | 5 km | 0.5m | High-detail targets |
| **Strip** | 15° - 45° | 30 km | 50 km | 3m | General imaging |
| **Scan** | 20° - 50° | 100 km | 100 km | 15m | Wide area surveillance |
| **Dwell** | 20° - 40° | 5 km | 5 km | 1m | Change detection |

### 5.2 Mode Selection Guidelines

- **Spot**: Use for small, high-value targets requiring maximum detail
- **Strip**: Default mode for most imaging tasks, good balance
- **Scan**: Large area coverage, maritime surveillance, disaster response
- **Dwell**: Coherent change detection, moving target indication

### 5.3 Incidence Angle Considerations

| Range | Characteristics | Best For |
|-------|-----------------|----------|
| 15° - 25° | Steeper look, better penetration | Flat terrain, vegetation |
| 25° - 35° | **Optimal** for most applications | General purpose |
| 35° - 45° | Shallower look, more shadow | Urban areas, topography |
| > 45° | Extreme foreshortening | Specialized applications |

---

## 6. Technical Algorithms

### 6.1 Look Side Determination

The look side is determined by the geometric relationship between the satellite velocity vector and the satellite-to-target vector:

```python
def _compute_look_side(self, sat_pos, sat_vel, target_pos) -> LookSide:
    # Vector from satellite to target
    sat_to_target = target_pos - sat_pos

    # Cross product: velocity × sat_to_target
    cross = np.cross(sat_vel, sat_to_target)

    # Project onto radial (up) direction
    radial = sat_pos / np.linalg.norm(sat_pos)
    up_component = np.dot(cross, radial)

    # Positive: target is on RIGHT side of ground track
    # Negative: target is on LEFT side of ground track
    return LookSide.RIGHT if up_component > 0 else LookSide.LEFT
```

**Geometric Interpretation**:
- Satellite moves along velocity vector
- Target lies either left or right of ground track
- Cross product determines which side

### 6.2 Pass Direction Detection

Pass direction is determined from the satellite's velocity vector:

```python
def _compute_pass_direction(self, velocity, position) -> PassDirection:
    # Get local north direction
    radial = position / np.linalg.norm(position)
    earth_axis = np.array([0, 0, 1])
    east = np.cross(earth_axis, radial)
    east = east / np.linalg.norm(east)
    north = np.cross(radial, east)

    # Project velocity onto north direction
    north_velocity = np.dot(velocity, north)

    return PassDirection.ASCENDING if north_velocity > 0 else PassDirection.DESCENDING
```

**Definition**:
- **ASCENDING**: Satellite moving northward (positive latitude rate)
- **DESCENDING**: Satellite moving southward (negative latitude rate)

### 6.3 Incidence Angle Calculation

The incidence angle is the off-nadir angle from satellite to target:

```python
def _compute_incidence_angle(self, sat_pos, target_pos) -> float:
    # Nadir direction (toward Earth center)
    nadir = -sat_pos / np.linalg.norm(sat_pos)

    # Line of sight to target
    los = target_pos - sat_pos
    los_norm = los / np.linalg.norm(los)

    # Angle between nadir and LOS
    cos_angle = np.dot(nadir, los_norm)
    incidence_rad = math.acos(np.clip(cos_angle, -1.0, 1.0))

    return math.degrees(incidence_rad)
```

### 6.4 SAR Quality Scoring (Band Model)

SAR quality uses a Gaussian band model centered on the optimal incidence angle:

```python
def _compute_sar_quality(self, incidence_deg: float) -> float:
    optimal = self.mode_spec.quality.optimal_incidence_deg  # e.g., 30°
    sigma = 15.0  # Width of quality band

    quality = 100.0 * math.exp(-((incidence_deg - optimal) / sigma) ** 2)
    return max(0.0, min(100.0, quality))
```

**Quality Distribution**:
```
Quality Score
    100 |        *****
     80 |      **     **
     60 |    **         **
     40 |  **             **
     20 | *                 *
      0 |*                   *
        +-----------------------
          10  20  30  40  50  60  Incidence (°)
                   ↑
              Optimal (30°)
```

### 6.5 Swath Polygon Computation

Swath corners are computed using spherical geometry:

```python
def _compute_swath_corners(self, sat_lat, sat_lon, sat_alt_km, ...):
    # 1. Get satellite velocity → track direction
    track_azimuth = self._velocity_to_azimuth(velocity, sat_lat, sat_lon)

    # 2. Cross-track direction based on look side
    if look_side == "LEFT":
        cross_track_azimuth = (track_azimuth - 90) % 360
    else:
        cross_track_azimuth = (track_azimuth + 90) % 360

    # 3. Ground range to swath center
    ground_range_km = sat_alt_km * math.tan(math.radians(incidence_deg))

    # 4. Compute swath center point
    center_lat, center_lon = self._destination_point(
        sat_lat, sat_lon, ground_range_km, cross_track_azimuth
    )

    # 5. Compute four corners
    # ... corner computation using along-track and cross-track offsets
```

---

## 7. API Reference

### 7.1 SAR Mission Analysis Request

**Endpoint**: `POST /api/mission/analyze`

**Request Body**:
```json
{
  "tle": {
    "name": "ICEYE-X1",
    "line1": "1 43114U 18004A   25015.50000000  .00000000  00000-0  00000-0 0  9999",
    "line2": "2 43114  97.4500 100.0000 0001000  90.0000 270.0000 15.20000000000000"
  },
  "targets": [
    {
      "name": "Target-Alpha",
      "latitude": 24.4539,
      "longitude": 54.3773,
      "description": "Test target in UAE"
    }
  ],
  "start_time": "2025-01-15T00:00:00Z",
  "end_time": "2025-01-16T00:00:00Z",
  "mission_type": "imaging",
  "imaging_type": "sar",
  "sar": {
    "imaging_mode": "strip",
    "incidence_min_deg": 20.0,
    "incidence_max_deg": 40.0,
    "look_side": "ANY",
    "pass_direction": "ANY"
  }
}
```

### 7.2 SAR Mission Analysis Response

**Response Body** (per pass):
```json
{
  "target": "Target-Alpha",
  "target_name": "Target-Alpha",
  "satellite_name": "ICEYE-X1",
  "satellite_id": "sat_ICEYE-X1",
  "pass_index": 0,
  "start_time": "2025-01-15T06:30:00",
  "max_elevation_time": "2025-01-15T06:34:00",
  "end_time": "2025-01-15T06:38:00",
  "duration_s": 480.0,
  "max_elevation": 45.2,
  "pass_type": "ascending",
  "mode": "SAR",
  "look_side": "RIGHT",
  "pass_direction": "ASCENDING",
  "incidence_center_deg": 32.5,
  "swath_width_km": 30.0,
  "imaging_mode": "strip",
  "sar": {
    "look_side": "RIGHT",
    "pass_direction": "ASCENDING",
    "incidence_center_deg": 32.5,
    "incidence_near_deg": 30.0,
    "incidence_far_deg": 35.0,
    "swath_width_km": 30.0,
    "scene_length_km": 50.0,
    "imaging_mode": "strip",
    "quality_score": 85.2
  }
}
```

### 7.3 Mission Data Response (SAR-specific fields)

```json
{
  "mission_data": {
    "mission_type": "imaging",
    "imaging_type": "sar",
    "total_passes": 6,
    "sar": {
      "imaging_mode": "strip",
      "look_side": "ANY",
      "pass_direction": "ANY",
      "incidence_min_deg": 20.0,
      "incidence_max_deg": 40.0,
      "sar_passes_count": 6
    },
    "passes": [ /* array of SAR passes */ ]
  },
  "czml_data": [ /* CZML packets including SAR swaths */ ]
}
```

---

## 8. Frontend Implementation

### 8.1 TypeScript Types (`frontend/src/types/index.ts`)

```typescript
/** SAR imaging mode types */
export type SARImagingMode = "spot" | "strip" | "scan" | "dwell";

/** SAR look side options */
export type SARLookSide = "LEFT" | "RIGHT" | "ANY";

/** SAR pass direction options */
export type SARPassDirection = "ASCENDING" | "DESCENDING" | "ANY";

/** SAR mission input parameters */
export interface SARInputParams {
  imaging_mode: SARImagingMode;
  incidence_min_deg?: number;
  incidence_max_deg?: number;
  look_side: SARLookSide;
  pass_direction: SARPassDirection;
  priority?: number;
  exclusivity?: string;
}

/** SAR opportunity data for a pass */
export interface SAROpportunityData {
  look_side: SARLookSide;
  pass_direction: SARPassDirection;
  incidence_center_deg: number;
  incidence_near_deg?: number;
  incidence_far_deg?: number;
  swath_width_km: number;
  scene_length_km: number;
  imaging_mode: SARImagingMode;
  quality_score: number;
}

/** SAR mission response data */
export interface SARMissionData {
  imaging_mode: SARImagingMode;
  look_side: SARLookSide;
  pass_direction: SARPassDirection;
  incidence_min_deg?: number;
  incidence_max_deg?: number;
  sar_passes_count: number;
}
```

### 8.2 SAR Panel Component (`frontend/src/components/MissionParameters.tsx`)

Key features:
- **Mode Toggle**: Optical / SAR selection
- **SAR Mode Dropdown**: Spot, Strip, Scan, Dwell
- **Look Side Buttons**: LEFT, ANY, RIGHT (color-coded)
- **Pass Direction Buttons**: ASC, ANY, DESC
- **Advanced Options**: Incidence angle range sliders
- **Summary Panel**: Shows all selected SAR parameters

```tsx
// SAR mode defaults (ICEYE-aligned)
const SAR_MODE_DEFAULTS = {
  spot: { incMin: 15, incMax: 35, desc: 'High resolution (0.5m), 5x5km scene' },
  strip: { incMin: 15, incMax: 45, desc: 'Standard mode (3m), 30km swath' },
  scan: { incMin: 20, incMax: 50, desc: 'Wide area (15m), 100km swath' },
  dwell: { incMin: 20, incMax: 40, desc: 'Extended dwell, change detection' },
};
```

### 8.3 UI Styling

- **SAR Panel Background**: Purple-tinted (`bg-purple-900/20`)
- **SAR Active State**: Purple buttons (`bg-purple-600`)
- **Look Side Colors**:
  - LEFT: Red (`bg-red-600`)
  - RIGHT: Blue (`bg-blue-600`)
  - ANY: Purple (`bg-purple-600`)
- **ICEYE Badge**: "ICEYE-compatible" label

---

## 9. CZML Visualization

### 9.1 Swath Color Scheme

```python
SAR_COLORS = {
    "LEFT": {
        "fill": [255, 100, 100, 60],      # Red tint (semi-transparent)
        "outline": [255, 50, 50, 200],    # Red outline
    },
    "RIGHT": {
        "fill": [100, 100, 255, 60],      # Blue tint (semi-transparent)
        "outline": [50, 50, 255, 200],    # Blue outline
    },
    "ANY": {
        "fill": [150, 100, 255, 60],      # Purple
        "outline": [100, 50, 255, 200],
    },
}
```

### 9.2 Swath CZML Packet Structure

```json
{
  "id": "sar_swath_0",
  "name": "SAR Swath - Target-Alpha (RIGHT)",
  "description": "<html>...SAR details...</html>",
  "availability": "2025-01-15T06:30:00Z/2025-01-15T06:38:00Z",
  "polygon": {
    "positions": {
      "cartographicDegrees": [lon1, lat1, 0, lon2, lat2, 0, ...]
    },
    "height": 0,
    "material": {
      "solidColor": {
        "color": { "rgba": [100, 100, 255, 60] }
      }
    },
    "outline": true,
    "outlineColor": { "rgba": [50, 50, 255, 200] },
    "outlineWidth": 2
  }
}
```

### 9.3 Dynamic Swath (Time-Following)

For real-time visualization, a time-dynamic swath polygon follows the satellite:

```python
def generate_dynamic_swath_packet(self, look_side, swath_width_km, incidence_deg):
    """Generate time-dynamic swath that follows satellite motion."""
    # Generates polygon positions at 30-second intervals
    # Each time step: compute new swath corners based on satellite position/velocity
    # Result: animated swath coverage visualization
```

---

## 10. Known Approximations

### 10.1 Geometric Approximations

| Approximation | Impact | Accuracy | Mitigation |
|---------------|--------|----------|------------|
| Spherical Earth | ~0.3% error in ground range | ±20m at 30km range | Use WGS84 for production |
| Simplified swath | Rectangle vs actual footprint | ~5% area error | Adequate for planning |
| Constant altitude | Slight variation over pass | ~1km variation | Use per-step altitude |

### 10.2 Incidence Angle Model

**Simplified Model**:
- Center incidence: Nadir-to-LOS angle
- Near/Far: ±2.5° offset (configurable)

**Production Model** (not implemented):
- True swath edges from antenna beamwidth
- Range-dependent incidence variation
- Terrain-adjusted local incidence

### 10.3 Quality Scoring

**Current**: Gaussian band model
- Simple, effective
- Centered on optimal incidence per mode

**Production Enhancement**:
- NESZ (Noise Equivalent Sigma Zero) consideration
- Ambiguity levels
- Scene-specific factors

---

## 11. Implementation Status

### 11.1 Fully Implemented ✅

| Feature | Description | Files |
|---------|-------------|-------|
| SAR Mode Configuration | ICEYE-aligned mode specs | `config/sar_modes.yaml`, `sar_config.py` |
| SAR Mission Analysis | Compute opportunities with SAR attributes | `sar_visibility.py` |
| Look Side Determination | Geometric LEFT/RIGHT computation | `SARVisibilityCalculator` |
| Pass Direction Detection | ASC/DESC from velocity | `SARVisibilityCalculator` |
| Incidence Angle Model | Near/center/far computation | `SARVisibilityCalculator` |
| SAR Feasibility Filters | Constraint-based filtering | `SARVisibilityCalculator` |
| SAR Quality Scoring | Band model quality | `SARVisibilityCalculator` |
| CZML Swath Visualization | Color-coded swath polygons | `sar_czml.py` |
| Dynamic Swath Display | Time-following swath | `SARCZMLGenerator` |
| API SAR Parameters | Full SAR input block | `backend/main.py` |
| Frontend SAR Panel | Complete UI controls | `MissionParameters.tsx` |
| SAR TypeScript Types | Full type definitions | `types/index.ts` |

### 11.2 Out of Scope ❌

| Feature | Reason |
|---------|--------|
| Real antenna pattern / NESZ | Requires SAR payload modeling |
| Polarization constraints | Mode-specific, not in v1 |
| True local incidence (DEM) | Requires terrain data |
| Advanced beam modeling | Antenna-specific |
| Full ICAS/IMAS integration | External system |

---

## 12. Validation Plan

### 12.1 Unit Tests

| Test Suite | Coverage |
|------------|----------|
| `test_sar_config.py` | Config loading, mode specs, validation |
| `test_sar_visibility.py` | Look side, pass direction, incidence, filtering |
| `test_sar_czml.py` | Swath polygon generation, CZML structure |

### 12.2 Integration Tests

| Test | Validation |
|------|------------|
| SAR API E2E | Request → Response validation |
| CZML Rendering | Visual verification in Cesium |
| Frontend Interaction | UI state management |

### 12.3 SAR Validation Harness ✅ IMPLEMENTED

A complete validation harness has been implemented in `backend/validation/` for automated SAR correctness verification.

#### Components

| File | Purpose |
|------|---------|
| `models.py` | Data models (SARScenario, ValidationReport, AssertionResult) |
| `assertions.py` | Semantic assertion checkers |
| `scenario_runner.py` | Headless scenario execution |
| `storage.py` | Scenario/report persistence |

#### Semantic Assertions Implemented

| Assertion | Description | Status |
|-----------|-------------|--------|
| `look_side_correctness` | Validates LEFT/RIGHT constraint compliance | ✅ |
| `pass_direction_correctness` | Verifies ASC/DESC from velocity vector | ✅ |
| `incidence_filtering` | Checks min/max angle constraints | ✅ |
| `swath_side_correctness` | Validates swath geometry position | ✅ |
| `mode_defaults_applied` | Verifies SAR mode defaults | ✅ |
| `expect_left/right_opportunities` | Checks expected outcomes | ✅ |
| `min/max_opportunities` | Count validations | ✅ |

#### Built-in Test Scenarios

| Scenario | Description | Opportunities |
|----------|-------------|---------------|
| `sar_left_right_basic` | LEFT/RIGHT look side with Athens/Thessaloniki | 16 |
| `sar_asc_desc_filter` | ASCENDING-only filter with Istanbul | 6 |
| `sar_incidence_range_clip` | Narrow incidence range (25-35°) with Nicosia | 2 |
| `sar_any_lookside_choice` | look_side=ANY with Rhodes | 8 |
| `sar_multisat_stress` | 3 satellites, 8 Eastern Mediterranean targets | 87 |

#### Running Validation

```bash
# Run all scenarios
.venv/bin/python -c "
from backend.validation import ScenarioStorage, ScenarioRunner
storage = ScenarioStorage()
runner = ScenarioRunner()
for s in storage.get_builtin_scenarios():
    r = runner.run_scenario(s)
    print(f'{\"✅\" if r.passed else \"❌\"} {s.name}: {r.passed_assertions}/{r.total_assertions}')
"
```

#### Validation API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/validate/scenarios` | GET | List available scenarios |
| `/api/v1/validate/scenario/{id}/run` | POST | Run specific scenario |
| `/api/v1/validate/run-all` | POST | Run all scenarios (CI/CD) |
| `/api/v1/validate/reports` | GET | List validation reports |

### 12.4 ICEYE API Semantic Validation

**Checklist** (Automated via Validation Harness):
- [x] LEFT swaths appear on left of ground track
- [x] RIGHT swaths appear on right of ground track
- [x] ASC passes are northbound
- [x] DESC passes are southbound
- [x] Opportunities outside incidence range are excluded
- [x] Mode defaults match ICEYE specs

### 12.5 Manual Verification Steps

1. **Start Application**: `./run_dev.sh`
2. **Select SAR Mode**: Click SAR button in Imaging Type
3. **Configure Parameters**: Select mode, look side, pass direction
4. **Run Analysis**: Click Analyze Mission
5. **Verify Results**:
   - Check SAR passes in results table
   - Verify swath polygons in Cesium
   - Confirm swath colors match look side

---

## 13. Future Enhancements

### Phase 2 (Planned)

- [ ] Priority-based scheduling order in mission planning
- [ ] Exclusivity enforcement in conflict resolution
- [ ] Multi-satellite SAR constellation deconfliction
- [ ] SAR-specific metrics in planning summary (mean incidence, L/R counts)
- [ ] Swath overlap visualization

### Phase 3 (Future)

- [ ] Doppler centroid estimation
- [ ] PRF (Pulse Repetition Frequency) constraint validation
- [ ] Azimuth/Range ambiguity checking
- [ ] Resolution modeling per geometry
- [ ] Terrain-aware local incidence
- [ ] Weather integration for SAR (rain cell detection)

### Phase 4 (Advanced)

- [ ] Full NESZ modeling
- [ ] Polarimetric mode support
- [ ] Interferometric baseline planning
- [ ] GMTI (Ground Moving Target Indication) mode

---

## 14. References

### 14.1 ICEYE Documentation

- ICEYE Product Specifications (Public)
- ICEYE Tasking API Documentation
- ICEYE Image Product Guide

### 14.2 SAR Fundamentals

- Curlander, J.C. & McDonough, R.N. - "Synthetic Aperture Radar: Systems and Signal Processing"
- Moreira, A. et al. - "A Tutorial on Synthetic Aperture Radar" (IEEE)

### 14.3 Internal Documentation

- `docs/algorithms/OVERVIEW.md` - Mission planning algorithms
- `docs/api/API_REFERENCE.md` - Full API documentation
- `docs/architecture/OVERVIEW.md` - System architecture

---

## Document Information

| Field | Value |
|-------|-------|
| **Version** | 1.1 |
| **Last Updated** | 2025-01-15 |
| **Author** | Mission Planning Team |
| **PR** | `feat/sar-analysis-planning-iceye-parity` |
| **Branch** | `feat/sar-analysis-planning-iceye-parity` |
| **Status** | Implementation Complete |
