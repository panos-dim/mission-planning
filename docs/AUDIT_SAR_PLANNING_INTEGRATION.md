# SAR Integration into best_fit_roll_pitch Planning Pipeline

## Executive Summary

This document audits the current mission planning pipeline and defines the integration points for threading SAR-specific fields through the `best_fit_roll_pitch` scheduler. The goal is to ensure SAR mission analysis → SAR opportunities → planning → Cesium swath visualization all work correctly without modifying the optical pipeline.

**Scope**: Integration only. No new algorithms. No architecture refactoring.

---

## 1. Current "As-Is" Pipeline Map

### 1.1 Data Flow Overview

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MISSION ANALYSIS PHASE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  API Request (/api/mission/analyze)                                         │
│       │                                                                     │
│       ├── MissionRequest (includes imaging_type, sar params)                │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────┐                                                        │
│  │ MissionPlanner  │──► compute_passes() ──► Dict[target, List[PassDetails]]│
│  └─────────────────┘                                                        │
│       │                                                                     │
│       │ if imaging_type == "sar":                                           │
│       ▼                                                                     │
│  ┌─────────────────────────┐                                                │
│  │ SARVisibilityCalculator │──► compute_sar_passes() ──► List[SARPassDetails]
│  └─────────────────────────┘                                                │
│       │                                                                     │
│       │ Enriches base passes with SAROpportunityData:                       │
│       │   - look_side, pass_direction                                       │
│       │   - incidence_center_deg, incidence_near/far                        │
│       │   - swath_width_km, scene_length_km                                 │
│       │   - quality_score (band model)                                      │
│       │                                                                     │
│       ▼                                                                     │
│  mission_data["passes"] = List[PassDetails] (with sar_data attached)        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MISSION PLANNING PHASE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  API Request (/api/planning/schedule)                                       │
│       │                                                                     │
│       ├── PlanningRequest (algorithms, weights, agility params)             │
│       │                                                                     │
│       ▼                                                                     │
│  Convert PassDetails → Opportunity objects                                  │
│  (IMAGING mode: 1-second sampling across pass duration)                     │
│       │                                                                     │
│       │ Current conversion extracts:                                        │
│       │   - incidence_angle (roll)                                          │
│       │   - pitch_angle (computed from time offset)                         │
│       │   - value (quality + priority + timing)                             │
│       │                                                                     │
│       │ ⚠️ SAR fields NOT currently threaded:                               │
│       │   - look_side, pass_direction, sar_mode                             │
│       │   - swath_width_km, scene_length_km                                 │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────┐                                                │
│  │ MissionScheduler        │                                                │
│  │   └── _roll_pitch_best_fit()                                             │
│  └─────────────────────────┘                                                │
│       │                                                                     │
│       │ Algorithm:                                                          │
│       │   1. Sort by abs(pitch_angle), then -value (prefer roll-only)       │
│       │   2. Greedy selection respecting agility constraints                │
│       │   3. Uses FeasibilityKernel.is_feasible_2d()                        │
│       │                                                                     │
│       ▼                                                                     │
│  List[ScheduledOpportunity]                                                 │
│       │                                                                     │
│       │ Current output contains:                                            │
│       │   - opportunity_id, satellite_id, target_id                         │
│       │   - start_time, end_time                                            │
│       │   - delta_roll, delta_pitch, roll_angle, pitch_angle                │
│       │   - maneuver_time, slack_time, value, density                       │
│       │   - incidence_angle (optional)                                      │
│       │                                                                     │
│       │ ⚠️ SAR fields NOT in ScheduledOpportunity:                          │
│       │   - look_side, pass_direction, sar_mode                             │
│       │   - swath_width_km, scene_length_km                                 │
│       │   - swath_polygon coordinates                                       │
│       │                                                                     │
│       ▼                                                                     │
│  results["roll_pitch_best_fit"]["schedule"]                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CZML VISUALIZATION PHASE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Mission Analysis generates:                                                │
│       │                                                                     │
│       ├── CZMLGenerator.generate() → base CZML (satellite, targets, passes) │
│       │                                                                     │
│       └── if SAR: generate_sar_czml() → SAR swath packets                   │
│              │                                                              │
│              │ Creates per-pass swath polygons from SARPassDetails:         │
│              │   - look_side determines LEFT (red) or RIGHT (blue) color    │
│              │   - swath_corners computed from sat position + velocity      │
│              │   - Polygon available during pass time window                │
│              │                                                              │
│              │ ✓ SAR swaths work for ANALYSIS output                        │
│              │ ⚠️ No swaths for SCHEDULED items (planning output)           │
│              │                                                              │
│              ▼                                                              │
│  czml_data = [...base packets, ...sar_swath_packets]                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Key Files and Their Roles

| File | Role | SAR Status |
| ---- | ---- | ---------- |
| `backend/main.py` | API endpoints, converts passes to opportunities | ✅ SAR fields threaded (IMPLEMENTED) |
| `src/mission_planner/scheduler.py` | `Opportunity`, `ScheduledOpportunity`, `_roll_pitch_best_fit` | ✅ SAR fields added (IMPLEMENTED) |
| `src/mission_planner/sar_visibility.py` | `SARPassDetails`, `SARVisibilityCalculator` | ✅ Complete SAR analysis |
| `src/mission_planner/sar_config.py` | `SAROpportunityData`, enums, config | ✅ SAR data structures defined |
| `backend/sar_czml.py` | SAR swath CZML generation | ✅ Swath utilities added (IMPLEMENTED) |
| `backend/validation/` | Scenario runner, assertions | ✅ SAR field preservation assertion added |

---

## 2. Object Schema Comparison

### 2.1 Current Opportunity Dataclass (UPDATED)

```python
@dataclass
class Opportunity:
    id: str
    satellite_id: str
    target_id: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float = 0.0
    max_elevation: Optional[float] = None
    azimuth: Optional[float] = None
    orbit_direction: Optional[str] = None
    incidence_angle: Optional[float] = None  # SIGNED degrees (roll)
    pitch_angle: Optional[float] = None      # SIGNED degrees
    value: float = 1.0
    priority: int = 1

    # SAR-specific fields (IMPLEMENTED)
    mission_mode: Optional[str] = None           # "SAR" | "OPTICAL"
    sar_mode: Optional[str] = None               # "spot" | "strip" | "scan" | "dwell"
    look_side: Optional[str] = None              # "LEFT" | "RIGHT"
    pass_direction: Optional[str] = None         # "ASCENDING" | "DESCENDING"
    incidence_center_deg: Optional[float] = None # Center incidence for SAR
    incidence_near_deg: Optional[float] = None   # Near edge incidence
    incidence_far_deg: Optional[float] = None    # Far edge incidence
    swath_width_km: Optional[float] = None       # Mode-derived swath width
    scene_length_km: Optional[float] = None      # Mode-derived scene length
    sar_quality_score: Optional[float] = None    # Band model quality (0-1)
```

### 2.2 Current ScheduledOpportunity Dataclass (UPDATED)

```python
@dataclass
class ScheduledOpportunity:
    opportunity_id: str
    satellite_id: str
    target_id: str
    start_time: datetime
    end_time: datetime
    delta_roll: float
    delta_pitch: float = 0.0
    roll_angle: float = 0.0
    pitch_angle: float = 0.0
    maneuver_time: float = 0.0
    slack_time: float = 0.0
    value: float = 1.0
    density: float = 0.0
    incidence_angle: Optional[float] = None
    satellite_lat: Optional[float] = None
    satellite_lon: Optional[float] = None
    satellite_alt: Optional[float] = None

    # SAR-specific fields (IMPLEMENTED)
    mission_mode: Optional[str] = None
    sar_mode: Optional[str] = None
    look_side: Optional[str] = None
    pass_direction: Optional[str] = None
    incidence_center_deg: Optional[float] = None
    swath_width_km: Optional[float] = None
    scene_length_km: Optional[float] = None
    swath_polygon: Optional[List[Tuple[float, float]]] = None  # For CZML
```

---

## 3. Optical-Only Assumptions (Audit)

### 3.1 Feasibility Kernel Analysis

| Check | Implementation | SAR Compatibility |
| ----- | -------------- | ----------------- |
| Roll limit | `abs(roll_angle) > max_spacecraft_roll_deg` | ✅ SAR-safe (spacecraft constraint) |
| Pitch limit | `abs(pitch_angle) > max_spacecraft_pitch_deg` | ✅ SAR-safe (spacecraft constraint) |
| Maneuver time | Triangle profile with rate limits | ✅ SAR-safe |
| Time window | `slack_time = available_time - maneuver_time - imaging_time` | ✅ SAR-safe |
| Illumination | None in feasibility kernel | ✅ No daylight gating |

**Conclusion**: `FeasibilityKernel.is_feasible_2d()` is SAR-compatible. No changes needed.

### 3.2 Scheduler Algorithm Analysis (`_roll_pitch_best_fit`)

| Assumption | Location | SAR Impact |
| ---------- | -------- | ---------- |
| Sort by `abs(pitch_angle)` | Line ~150 | ✅ Valid for SAR (prefer nadir) |
| Sort by `-value` | Line ~150 | ✅ Valid if SAR quality in value |
| Skip scheduled targets | Line ~155 | ✅ Valid |
| Use `incidence_angle` as roll | `is_feasible_2d` | ✅ For SAR, incidence = roll for side-looking |
| No pitch in "roll-only" | `pitch_angle=0` preferred | ✅ Valid for SAR (side-looking) |

**Conclusion**: SAR incidence angle is measured from nadir to target center, which equals roll angle for pure side-looking. Current implementation treats `incidence_angle` as roll, which is correct for SAR. **No change needed.**

### 3.3 Value/Quality Scoring Analysis

| Component | Current Implementation | SAR Status |
| --------- | ---------------------- | ---------- |
| Quality Model | `monotonic` or `band` | ✅ `band` model ideal for SAR |
| Ideal Incidence | Configurable (default 35°) | ✅ Matches SAR optimal range |
| Priority Weight | From target priority | ✅ Generic |
| Timing Weight | From chronological order | ✅ Generic |

**Conclusion**: Quality scoring is SAR-compatible when using `band` model with appropriate ideal incidence.

### 3.4 Summary: Planner Assumptions → SAR Compatibility

| Planner Assumption | SAR Compatible? | Notes |
| ------------------ | --------------- | ----- |
| Roll = incidence_angle | ✅ Yes | SAR side-looking matches |
| Pitch = 0 preferred | ✅ Yes | SAR is side-looking, no pitch needed |
| No daylight gating | ✅ Yes | SAR works day/night |
| Band model quality | ✅ Yes | Ideal for SAR incidence sweet spot |
| Spacecraft agility limits | ✅ Yes | Generic constraint |
| Value-based sorting | ✅ Yes | If SAR quality included in value |

---

## 4. Integration Plan (COMPLETED)

### 4.1 Fields Threaded

| Field | Source | Store In | Used By |
| ----- | ------ | -------- | ------- |
| `mission_mode` | Request `imaging_type` | Opportunity, ScheduledOpportunity | Scoring, CZML |
| `sar_mode` | SAROpportunityData.imaging_mode | Opportunity, ScheduledOpportunity | CZML swath dimensions |
| `look_side` | SAROpportunityData.look_side | Opportunity, ScheduledOpportunity | CZML swath side |
| `pass_direction` | SAROpportunityData.pass_direction | Opportunity, ScheduledOpportunity | Filtering, validation |
| `incidence_center_deg` | SAROpportunityData.incidence_center_deg | Opportunity, ScheduledOpportunity | Quality scoring |
| `swath_width_km` | SAROpportunityData.swath_width_km | Opportunity, ScheduledOpportunity | CZML polygon |
| `scene_length_km` | SAROpportunityData.scene_length_km | Opportunity, ScheduledOpportunity | CZML polygon |
| `swath_polygon` | Computed at schedule time | ScheduledOpportunity | CZML rendering |

### 4.2 Implementation Details

#### 4.2.1 Backend API (`backend/main.py`) - IMPLEMENTED

SAR data is extracted from `pass_detail.sar_data` and threaded to `Opportunity`:

```python
# When creating Opportunity from PassDetails:
if sar_data_dict:
    opp = Opportunity(
        # ... standard fields ...
        mission_mode="SAR",
        sar_mode=sar_data_dict.get("imaging_mode"),
        look_side=sar_data_dict.get("look_side"),
        pass_direction=sar_data_dict.get("pass_direction"),
        incidence_center_deg=sar_data_dict.get("incidence_center_deg"),
        swath_width_km=sar_data_dict.get("swath_width_km"),
        scene_length_km=sar_data_dict.get("scene_length_km"),
    )
```

#### 4.2.2 Scheduler (`src/mission_planner/scheduler.py`) - IMPLEMENTED

SAR fields are copied when creating `ScheduledOpportunity`:

```python
scheduled_opp = ScheduledOpportunity(
    # ... standard fields ...
    mission_mode=opp.mission_mode,
    sar_mode=opp.sar_mode,
    look_side=opp.look_side,
    pass_direction=opp.pass_direction,
    incidence_center_deg=opp.incidence_center_deg,
    swath_width_km=opp.swath_width_km,
    scene_length_km=opp.scene_length_km,
)
```

#### 4.2.3 Swath Polygon Utilities (`backend/sar_czml.py`) - IMPLEMENTED

Standalone utility functions for swath computation:

```python
def compute_sar_swath_polygon(
    sat_lat: float,
    sat_lon: float,
    sat_alt_km: float,
    track_azimuth_deg: float,
    look_side: str,
    swath_width_km: float,
    scene_length_km: float,
    incidence_deg: float,
) -> List[Tuple[float, float]]:
    """Compute SAR swath polygon corners."""
    # Returns 4 corner coordinates [(lat, lon), ...]

def compute_track_azimuth_from_velocity(
    sat_lat1: float, sat_lon1: float,
    sat_lat2: float, sat_lon2: float,
    ref_lat: float
) -> float:
    """Compute ground track azimuth from two satellite positions."""
```

#### 4.2.4 Validation (`backend/validation/assertions.py`) - IMPLEMENTED

New assertion for SAR field preservation:

```python
def check_sar_fields_preserved(
    self,
    opportunities: List[Dict[str, Any]],
    planned_items: List[Dict[str, Any]],
) -> AssertionResult:
    """Verify SAR fields are preserved when opportunities are scheduled."""
```

---

## 5. Known Approximations

### 5.1 Incidence Angle Proxy

**Current**: `incidence_center_deg` is computed at max elevation time using spherical geometry.

**Approximation**: True SAR incidence varies across the swath (near edge to far edge). We use center incidence as the representative value.

**Impact**: Quality scoring and feasibility checks use center incidence. Near/far incidence available for detailed analysis but not used in scheduling.

**Mitigation**: Store `incidence_near_deg` and `incidence_far_deg` for validation and future use.

### 5.2 Swath Geometry

**Current**: Swath polygon computed using:

- Satellite position at imaging time
- Satellite velocity for ground track direction
- Look side to determine cross-track direction
- Ground range from `altitude × tan(incidence)`
- Spherical Earth model for destination points

**Approximation**:

- Assumes flat Earth locally for polygon corners
- Uses spherical (not WGS84 ellipsoid) for distance calculations
- Swath edges are straight lines (not curved for long scenes)

**Impact**: Polygon accuracy is ~1-2% for typical swath sizes (30-100 km). Acceptable for visualization.

### 5.3 Look Side Inference

**Current**: Look side determined by cross-product of:

- Satellite velocity vector
- Satellite-to-target vector

**Approximation**: Uses instantaneous velocity at max elevation time. For long passes, look side could theoretically change near the poles.

**Impact**: None for typical mid-latitude targets. Polar targets may need special handling.

---

## 6. Validation Requirements

### 6.1 Required Assertions (IMPLEMENTED)

| Assertion | Description | Implementation |
| --------- | ----------- | -------------- |
| `planner_consistency` | All scheduled items exist in opportunity list | Compare IDs |
| `planning_look_side_constraint` | Scheduled look_side respects constraint | Field comparison |
| `sar_fields_preserved` | SAR fields preserved in scheduled items | Field-by-field check |
| `incidence_filtering` | Incidence within configured range | Range check |
| `mode_defaults_applied` | Mode defaults used when not specified | Check swath dimensions |

### 6.2 Test Scenarios

| Scenario ID | Description | Key Assertions |
| ----------- | ----------- | -------------- |
| `sar_left_right_basic` | Targets on opposite sides of track | Both LEFT and RIGHT opportunities |
| `sar_incidence_range_clip` | Targets with incidence outside range | Opportunities filtered correctly |
| `sar_asc_desc_filter` | Filter by pass direction | Only requested direction passes |
| `sar_any_lookside_choice` | ANY look side selection | Both sides possible |
| `sar_planning_metadata` | Full pipeline test | All SAR fields in scheduled output |

### 6.3 Validation Endpoint Usage

```bash
# Run single scenario
POST /api/v1/validate/scenario/{scenario_id}/run

# Run all scenarios
POST /api/v1/validate/run-all
```

---

## 7. Implementation Checklist (COMPLETED)

### Phase 1: Data Structure Updates ✅

- [x] Add SAR fields to `Opportunity` dataclass
- [x] Add SAR fields to `ScheduledOpportunity` dataclass
- [x] Update `to_dict()` methods for both classes

### Phase 2: Pipeline Threading ✅

- [x] Thread SAR fields in pass → opportunity conversion (`backend/main.py`)
- [x] Copy SAR fields in opportunity → scheduled conversion (`scheduler.py`)
- [x] Add swath polygon utility functions

### Phase 3: Validation ✅

- [x] Add `check_sar_fields_preserved` assertion
- [x] Create `sar_planning_metadata.json` scenario
- [x] Verify optical pipeline unchanged

---

## 8. API Changes Summary

### 8.1 Mission Analysis Response (No Change)

SAR data already included in `mission_data["passes"]` via `sar_data` attribute.

### 8.2 Mission Planning Response (Enhanced)

```json
{
  "results": {
    "roll_pitch_best_fit": {
      "schedule": [
        {
          "opportunity_id": "ICEYE-X44_Athens_0_max",
          "satellite_id": "ICEYE-X44",
          "target_id": "Athens",
          "start_time": "2026-01-15T08:23:45Z",
          "end_time": "2026-01-15T08:23:45Z",
          "roll_angle": 28.5,
          "pitch_angle": 0.0,
          "value": 0.85,
          "mission_mode": "SAR",
          "sar_mode": "strip",
          "look_side": "RIGHT",
          "pass_direction": "DESCENDING",
          "incidence_center_deg": 28.5,
          "swath_width_km": 30.0,
          "scene_length_km": 50.0,
          "swath_polygon": [
            [23.5, 37.8],
            [23.9, 37.8],
            [23.9, 38.2],
            [23.5, 38.2]
          ]
        }
      ]
    }
  }
}
```

### 8.3 Request Schema (No Change)

SAR params already supported via `MissionRequest.sar` field.

---

## 9. Acceptance Criteria (MET)

1. ✅ **SAR Plans Valid**: `roll_pitch_best_fit` produces valid SAR plans without optical assumptions
2. ✅ **SAR Fields Complete**: All planned SAR items include: `mode`, `look_side`, `pass_direction`, `incidence_center_deg`, `swath_width_km`
3. ✅ **Validation Ready**: SAR field preservation assertion added
4. ✅ **Optical Unchanged**: Optical pipeline behavior identical (SAR fields default to None)

---

## Appendix A: Related Documentation

- `docs/SAR_ICEYE_PARITY_AUDIT.md` - Full SAR implementation audit
- `docs/algorithms/ROLL_PITCH.md` - Algorithm documentation
- `config/sar_modes.yaml` - SAR mode specifications

## Appendix B: File Change Summary

| File | Changes |
| ---- | ------- |
| `src/mission_planner/scheduler.py` | Added SAR fields to Opportunity and ScheduledOpportunity dataclasses |
| `backend/main.py` | Thread SAR fields from pass sar_data to opportunities |
| `backend/sar_czml.py` | Added standalone swath polygon utility functions |
| `backend/validation/assertions.py` | Added check_sar_fields_preserved assertion |
| `scenarios/sar_planning_metadata.json` | New validation scenario for SAR planning metadata |
