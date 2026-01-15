# Workspace Object Tree Audit

> **Version**: 1.0
> **Date**: January 2026
> **Purpose**: Deep scan of current mission analysis + mission planning object model with STK-style workspace proposal

---

## Table of Contents

1. [Current Object Tree (As-Is)](#1-current-object-tree-as-is)
2. [Proposed STK-Style Object Tree (To-Be)](#2-proposed-stk-style-object-tree-to-be)
3. [Object Inventory Table](#3-object-inventory-table)
4. [Relationship Table](#4-relationship-table)
5. [Metadata Inventory](#5-metadata-inventory)
6. [Computed vs Persisted Fields](#6-computed-vs-persisted-fields)
7. [Parameter Mapping](#7-parameter-mapping)
8. [Gap Analysis](#8-gap-analysis)
9. [Workspace Schema Design](#9-workspace-schema-design)

---

## 1. Current Object Tree (As-Is)

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CURRENT OBJECT MODEL                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐   │
│  │ TLE Data    │────>│ Satellite   │────>│ Mission Analysis    │   │
│  │ (Input)     │     │ Orbit       │     │ (Passes)            │   │
│  └─────────────┘     └─────────────┘     └─────────────────────┘   │
│                                                   │                  │
│  ┌─────────────┐     ┌─────────────┐             │                  │
│  │ Target Data │────>│ Ground      │─────────────┤                  │
│  │ (Input)     │     │ Target      │             │                  │
│  └─────────────┘     └─────────────┘             ▼                  │
│                                          ┌─────────────────────┐    │
│  ┌─────────────┐                        │ Opportunities       │    │
│  │ Config      │───────────────────────>│ (Planning Input)    │    │
│  │ (Settings)  │                        └─────────────────────┘    │
│  └─────────────┘                                 │                  │
│                                                  ▼                  │
│                                          ┌─────────────────────┐    │
│                                          │ Scheduled           │    │
│                                          │ Opportunities       │    │
│                                          │ (Planning Output)   │    │
│                                          └─────────────────────┘    │
│                                                  │                  │
│                                                  ▼                  │
│                                          ┌─────────────────────┐    │
│                                          │ CZML Data           │    │
│                                          │ (Visualization)     │    │
│                                          └─────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow

1. **Input Phase**: TLE data + Target coordinates + Mission parameters
2. **Analysis Phase**: Visibility calculations → Pass detection → Opportunity creation
3. **Planning Phase**: Opportunity filtering → Algorithm scheduling → Schedule generation
4. **Output Phase**: CZML generation → Visualization + JSON export

### 1.3 Current State Storage

| Storage Type | Location | Contents |
|--------------|----------|----------|
| **In-Memory** | `current_mission_data` (backend/main.py) | Mission data, CZML, passes, satellite objects |
| **Config Files** | `config/` directory | ground_stations.yaml, satellites.yaml, mission_settings.yaml |
| **Frontend State** | Zustand store + Context | Form data, mission results, UI state |
| **No Persistence** | - | No database, workspaces are lost on refresh |

---

## 2. Proposed STK-Style Object Tree (To-Be)

### 2.1 STK-Inspired Hierarchy

```
┌─────────────────────────────────────────────────────────────────────┐
│                     STK-STYLE WORKSPACE MODEL                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  WORKSPACE (Root)                                                    │
│  ├── id: uuid                                                        │
│  ├── name: string                                                    │
│  ├── created_at: datetime                                            │
│  ├── updated_at: datetime                                            │
│  ├── schema_version: string                                          │
│  ├── app_version: string                                             │
│  │                                                                   │
│  ├── SCENARIO                                                        │
│  │   ├── mission_mode: OPTICAL | SAR | COMMUNICATION                │
│  │   ├── time_window: { start, end }                                │
│  │   │                                                               │
│  │   ├── ASSETS                                                      │
│  │   │   └── SATELLITES[]                                           │
│  │   │       ├── id, name                                           │
│  │   │       ├── tle_data: { line1, line2, epoch }                  │
│  │   │       ├── sensor_config                                      │
│  │   │       └── spacecraft_config                                  │
│  │   │                                                               │
│  │   ├── TARGETS[]                                                  │
│  │   │   ├── id, name                                               │
│  │   │   ├── position: { lat, lon, alt }                           │
│  │   │   ├── priority: 1-5                                         │
│  │   │   └── constraints                                            │
│  │   │                                                               │
│  │   └── CONSTRAINTS                                                │
│  │       ├── elevation_mask_deg                                     │
│  │       ├── max_spacecraft_roll_deg                                │
│  │       ├── max_spacecraft_pitch_deg                               │
│  │       ├── sensor_fov_half_angle_deg                              │
│  │       └── quality_model_config                                   │
│  │                                                                   │
│  ├── ANALYSIS_RESULTS                                               │
│  │   ├── run_timestamp: datetime                                    │
│  │   ├── passes[]: PassDetails                                      │
│  │   ├── opportunities[]: Opportunity                               │
│  │   ├── czml_reference: blob | path                                │
│  │   └── statistics: { total_passes, by_satellite, by_target }     │
│  │                                                                   │
│  ├── PLANNING_RESULTS                                               │
│  │   ├── algorithm_runs[]                                           │
│  │   │   ├── algorithm_name                                         │
│  │   │   ├── run_timestamp                                          │
│  │   │   ├── config_snapshot                                        │
│  │   │   ├── schedule[]: ScheduledOpportunity                       │
│  │   │   ├── metrics: ScheduleMetrics                               │
│  │   │   └── target_statistics                                      │
│  │   └── selected_algorithm: string                                 │
│  │                                                                   │
│  ├── ORDERS[]                                                       │
│  │   ├── order_id                                                   │
│  │   ├── created_at                                                 │
│  │   ├── algorithm_source                                           │
│  │   ├── status: DRAFT | ACCEPTED | EXECUTED                       │
│  │   └── schedule_snapshot                                          │
│  │                                                                   │
│  └── UI_STATE (optional)                                            │
│      ├── active_tab                                                 │
│      ├── selected_target                                            │
│      ├── timeline_cursor                                            │
│      ├── layer_visibility                                           │
│      └── sidebar_widths                                             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Entity Diagram

```
                    ┌───────────────┐
                    │   WORKSPACE   │
                    │───────────────│
                    │ id (PK)       │
                    │ name          │
                    │ created_at    │
                    │ updated_at    │
                    │ schema_version│
                    └───────┬───────┘
                            │
           ┌────────────────┼────────────────┐
           │                │                │
           ▼                ▼                ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │  SCENARIO   │  │  ANALYSIS   │  │  PLANNING   │
    │─────────────│  │─────────────│  │─────────────│
    │ workspace_id│  │ workspace_id│  │ workspace_id│
    │ mission_mode│  │ run_time    │  │ algorithm   │
    │ time_start  │  │ passes_json │  │ schedule_json│
    │ time_end    │  │ opps_json   │  │ metrics_json│
    │ config_json │  │ czml_blob   │  │ run_time    │
    └──────┬──────┘  └─────────────┘  └─────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌─────────┐  ┌─────────┐
│SATELLITE│  │ TARGET  │
│─────────│  │─────────│
│ id      │  │ id      │
│ name    │  │ name    │
│ tle_json│  │ lat/lon │
│ config  │  │ priority│
└─────────┘  └─────────┘
```

---

## 3. Object Inventory Table

### 3.1 Backend Objects

| Object Name | File | Purpose | Key Fields | Creator | Persist? |
|-------------|------|---------|------------|---------|----------|
| **SatelliteOrbit** | `src/mission_planner/orbit.py` | Orbit propagation | satellite_name, tle_lines, predictor | TLE input | Config only |
| **GroundTarget** | `src/mission_planner/targets.py` | Target location | name, lat, lon, elevation_mask, priority, sensor_fov | User input | ✅ Yes |
| **PassDetails** | `src/mission_planner/visibility.py` | Visibility pass | target_name, sat_name, start/end_time, max_elevation, incidence_angle | Analysis | ✅ Yes |
| **Opportunity** | `src/mission_planner/scheduler.py` | Planning input | id, sat_id, target_id, start/end_time, value, incidence_angle, pitch_angle | Analysis→Planning | ✅ Yes |
| **ScheduledOpportunity** | `src/mission_planner/scheduler.py` | Planning output | opp_id, delta_roll/pitch, roll/pitch_angle, maneuver_time, slack_time, value, density | Planning | ✅ Yes |
| **ScheduleMetrics** | `src/mission_planner/scheduler.py` | Schedule stats | algorithm, runtime, accepted/rejected, total_value, utilization, mean_incidence | Planning | ✅ Yes |
| **SchedulerConfig** | `src/mission_planner/scheduler.py` | Planning params | imaging_time_s, max_roll/pitch_deg, rates, look_window_s | User input | ✅ Yes |
| **SensorConfig** | `src/mission_planner/mission_config.py` | Sensor params | sensor_fov_half_angle_deg, mode, incidence_range | Config | ✅ Yes |
| **SpacecraftConfig** | `src/mission_planner/mission_config.py` | Bus params | max_roll/pitch_deg, rates, settling_time | Config | ✅ Yes |
| **MultiCriteriaWeights** | `src/mission_planner/quality_scoring.py` | Value weights | priority, geometry, timing (normalized) | User input | ✅ Yes |
| **CZMLGenerator** | `backend/czml_generator.py` | Visualization | satellite, targets, passes, time_range | Analysis | Derived |

### 3.2 API Models (Pydantic)

| Model | File | Purpose | Key Fields |
|-------|------|---------|------------|
| **TLEData** | `backend/main.py` | TLE input | name, line1, line2 |
| **TargetData** | `backend/main.py` | Target input | name, lat, lon, description, priority, color |
| **MissionRequest** | `backend/main.py` | Analysis request | tle/satellites, targets, start/end_time, mission_type, constraints |
| **MissionResponse** | `backend/main.py` | Analysis response | success, message, data (mission_data + czml_data) |
| **PlanningRequest** | `backend/main.py` | Planning params | imaging_time_s, rates, algorithms, weights, quality_model |
| **PlanningResponse** | `backend/main.py` | Planning result | success, message, results (per-algorithm) |

### 3.3 Frontend Types

| Type | File | Purpose | Key Fields |
|------|------|---------|------------|
| **MissionData** | `frontend/src/types/index.ts` | Analysis result | satellites, mission_type, time_range, passes, targets |
| **PassData** | `frontend/src/types/index.ts` | Pass info | target, satellite, times, max_elevation |
| **Opportunity** | `frontend/src/types/index.ts` | Planning input | id, sat/target_id, times, value, incidence |
| **ScheduledOpportunity** | `frontend/src/types/index.ts` | Planning output | opp_id, roll/pitch angles, maneuver_time, value |
| **ScheduleMetrics** | `frontend/src/types/index.ts` | Schedule stats | algorithm, runtime, accepted, total_value |
| **AcceptedOrder** | `frontend/src/types/index.ts` | Order definition | order_id, algorithm, metrics, schedule |
| **Workspace** | `frontend/src/types/index.ts` | Save state | id, name, sceneObjects, missionData, czmlData |
| **MissionState** | `frontend/src/types/index.ts` | UI state | isLoading, missionData, czmlData, error, workspaces |

---

## 4. Relationship Table

| Parent | Child | Cardinality | FK/ID | Notes |
|--------|-------|-------------|-------|-------|
| Workspace | Scenario | 1:1 | workspace_id | Core mission definition |
| Workspace | AnalysisResult | 1:N | workspace_id | Multiple analysis runs possible |
| Workspace | PlanningResult | 1:N | workspace_id | Multiple algorithm runs |
| Workspace | Order | 1:N | workspace_id | Accepted schedules |
| Scenario | Satellite | 1:N | scenario_id | Constellation support |
| Scenario | Target | 1:N | scenario_id | Multiple targets |
| Scenario | Constraint | 1:1 | scenario_id | Shared constraints |
| AnalysisResult | PassDetails | 1:N | analysis_id | Passes from visibility |
| AnalysisResult | Opportunity | 1:N | analysis_id | Derived from passes |
| PlanningResult | ScheduledOpportunity | 1:N | planning_id | Algorithm output |
| PlanningResult | ScheduleMetrics | 1:1 | planning_id | Performance stats |
| Opportunity | ScheduledOpportunity | 1:0..1 | opportunity_id | Accepted or not |
| Order | ScheduledOpportunity | 1:N | order_id | Snapshot of schedule |

---

## 5. Metadata Inventory

### 5.1 Fields by Object Type

#### Workspace Metadata (Right Sidebar)
| Field | Source | Show? | Store? |
|-------|--------|-------|--------|
| workspace_id | Generated | ❌ | ✅ |
| name | User input | ✅ | ✅ |
| created_at | System | ✅ | ✅ |
| updated_at | System | ✅ | ✅ |
| mission_mode | Scenario | ✅ | ✅ |
| time_window | Scenario | ✅ | ✅ |
| satellites_count | Scenario | ✅ | Derived |
| targets_count | Scenario | ✅ | Derived |
| total_passes | Analysis | ✅ | ✅ |
| total_opportunities | Analysis | ✅ | Derived |
| last_run_status | System | ✅ | ✅ |
| schema_version | System | ❌ | ✅ |
| app_version | System | ❌ | ✅ |

#### Satellite Metadata
| Field | Source | Show? | Store? |
|-------|--------|-------|--------|
| name | TLE | ✅ | ✅ |
| norad_id | TLE Line 1 | ✅ | Derived |
| tle_epoch | TLE Line 1 | ✅ | Derived |
| orbital_period_min | Computed | ✅ | Derived |
| altitude_km | Computed | ✅ | Derived |
| inclination_deg | TLE Line 2 | ✅ | Derived |
| sensor_fov_deg | Config | ✅ | ✅ |
| max_roll_deg | Config | ✅ | ✅ |
| color | Assigned | ✅ | ✅ |

#### Target Metadata
| Field | Source | Show? | Store? |
|-------|--------|-------|--------|
| name | User input | ✅ | ✅ |
| latitude | User input | ✅ | ✅ |
| longitude | User input | ✅ | ✅ |
| altitude_m | User input | ✅ | ✅ |
| priority | User input | ✅ | ✅ |
| elevation_mask_deg | Config | ✅ | ✅ |
| color | User input | ✅ | ✅ |
| passes_count | Analysis | ✅ | Derived |
| best_incidence_deg | Analysis | ✅ | Derived |

#### Pass/Opportunity Metadata
| Field | Source | Show? | Store? |
|-------|--------|-------|--------|
| start_time | Visibility | ✅ | ✅ |
| end_time | Visibility | ✅ | ✅ |
| duration_s | Computed | ✅ | Derived |
| max_elevation_deg | Visibility | ✅ | ✅ |
| max_elevation_time | Visibility | ✅ | ✅ |
| incidence_angle_deg | Visibility | ✅ | ✅ |
| azimuth_deg | Visibility | ✅ | ✅ |
| orbit_direction | Visibility | ✅ | ✅ |
| pitch_angle_deg | Planning | ✅ | ✅ |
| value | Planning | ✅ | ✅ |

#### Schedule Metadata
| Field | Source | Show? | Store? |
|-------|--------|-------|--------|
| algorithm | User selection | ✅ | ✅ |
| runtime_ms | Planning | ✅ | ✅ |
| opportunities_accepted | Planning | ✅ | ✅ |
| opportunities_rejected | Planning | ✅ | ✅ |
| total_value | Planning | ✅ | ✅ |
| mean_incidence_deg | Planning | ✅ | ✅ |
| total_maneuver_time_s | Planning | ✅ | ✅ |
| utilization | Planning | ✅ | ✅ |
| coverage_percentage | Planning | ✅ | ✅ |

---

## 6. Computed vs Persisted Fields

### 6.1 Always Derived (Never Persist)
| Field | Source | Computation |
|-------|--------|-------------|
| orbital_period | TLE | `predictor.period` |
| altitude_km | TLE + time | `satellite.get_position(t)[2]` |
| ground_track | TLE + time range | Propagation loop |
| czml_positions | TLE + time range | `CZMLGenerator._generate_positions()` |
| footprint_radius | Altitude + FOV | `alt * tan(fov)` |
| timing_score | Opportunity index | `1 - (idx / total)` |
| quality_score | Incidence angle | `exp(-0.02 * abs(angle))` |
| composite_value | Priority + quality + timing | Weighted sum |
| maneuver_time | Delta roll/pitch + rates | Trapezoidal profile |

### 6.2 Always Persist
| Field | Reason |
|-------|--------|
| TLE lines | Reproducibility - ephemeris source |
| Target coordinates | User input |
| Time window | Analysis scope |
| Config snapshot | Reproducibility |
| Pass times | Analysis results |
| Schedule | Planning output |
| Metrics | Performance tracking |
| Order status | Workflow state |

### 6.3 Persist for Performance (Cache)
| Field | Reason |
|-------|--------|
| CZML blob | Expensive to regenerate |
| Opportunities JSON | Derived but reused |
| Statistics | Aggregation results |

---

## 7. Parameter Mapping

### 7.1 User Input → Storage → Display

| User Inputs | API Field | Stored As | Displayed As |
|-------------|-----------|-----------|--------------|
| TLE text | `tle.name/line1/line2` | `satellites_json` | Satellite list |
| Target coords | `targets[].lat/lon` | `targets_json` | Target markers |
| Start/End time | `start_time/end_time` | `time_window_start/end` | Time range |
| Mission type | `mission_type` | `mission_mode` | Mode badge |
| Elevation mask | `elevation_mask` | `constraints_json` | Config panel |
| Max roll | `max_spacecraft_roll_deg` | `constraints_json` | Config panel |
| Algorithm | `algorithms[]` | `planning_state_json` | Results tabs |
| Weights | `weight_priority/geometry/timing` | `config_snapshot_json` | Sliders |

### 7.2 Analysis Output → Storage → Display

| Analysis Output | API Response Field | Stored As | Displayed As |
|-----------------|-------------------|-----------|--------------|
| Passes | `mission_data.passes[]` | `analysis_state_json` | Timeline bars |
| Total passes | `mission_data.total_passes` | Derived | Summary card |
| CZML | `czml_data[]` | `czml_blob` | 3D visualization |
| Pass details | `passes[].max_elevation` | `analysis_state_json` | Pass table |

### 7.3 Planning Output → Storage → Display

| Planning Output | API Response Field | Stored As | Displayed As |
|-----------------|-------------------|-----------|--------------|
| Schedule | `results[algo].schedule[]` | `planning_state_json` | Schedule table |
| Metrics | `results[algo].metrics` | `planning_state_json` | Metrics cards |
| Coverage | `results[algo].target_statistics` | `planning_state_json` | Coverage bar |
| Angles | `results[algo].angle_statistics` | `planning_state_json` | Angle stats |

---

## 8. Gap Analysis

### 8.1 Missing Entities

| Gap | Current State | Required For | Priority |
|-----|---------------|--------------|----------|
| **Workspace entity** | None | Session persistence | 🔴 Critical |
| **Scenario snapshot** | In-memory only | Reproducibility | 🔴 Critical |
| **Order entity** | Frontend only | Workflow | 🟡 High |
| **Constraint config** | Scattered | Unified view | 🟡 High |
| **Ephemeris reference** | TLE lines only | Long-term tracking | 🟢 Medium |
| **Ground station entity** | Config file only | Full model | 🟢 Medium |
| **Access constraints** | Hardcoded | Flexibility | 🟢 Medium |

### 8.2 Normalization Needs

| Issue | Current | Should Be |
|-------|---------|-----------|
| Satellite config | Mixed in targets | Separate SensorConfig + SpacecraftConfig |
| Constraints | Per-target | Scenario-level with target overrides |
| Quality model | Per-request | Scenario-level config |
| Weights | Per-request | Scenario-level config |

### 8.3 Missing Metadata

| Object | Missing Fields |
|--------|----------------|
| PassDetails | orbit_number, sun_illumination, slant_range_km |
| Opportunity | uncertainty_s, cloud_probability |
| Schedule | execution_status, feedback |
| Workspace | tags, description, shared_with |

### 8.4 State Synchronization Issues

| Issue | Current Behavior | Required |
|-------|-----------------|----------|
| Refresh loses state | Everything in memory | Persist to DB |
| Multiple tabs | Conflicting state | Single source of truth |
| Backend restart | Clears `current_mission_data` | Persist analysis |

---

## 9. Workspace Schema Design

### 9.1 Database Schema (SQLite v1)

```sql
-- Core workspace table
CREATE TABLE workspaces (
    id TEXT PRIMARY KEY,           -- UUID
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    schema_version TEXT DEFAULT '1.0',
    app_version TEXT,

    -- Scenario summary (denormalized for listing)
    mission_mode TEXT,             -- 'OPTICAL' | 'SAR' | 'COMMUNICATION'
    time_window_start TIMESTAMP,
    time_window_end TIMESTAMP,
    satellites_count INTEGER DEFAULT 0,
    targets_count INTEGER DEFAULT 0,

    -- Status
    last_run_status TEXT,          -- 'success' | 'error' | 'pending'
    last_run_timestamp TIMESTAMP
);

-- Workspace state blobs (JSON storage for v1 simplicity)
CREATE TABLE workspace_blobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

    -- State snapshots (JSON blobs)
    scenario_config_json TEXT,     -- Satellites, targets, constraints
    analysis_state_json TEXT,      -- Passes, opportunities, statistics
    planning_state_json TEXT,      -- Algorithm results, metrics
    orders_state_json TEXT,        -- Accepted schedules
    ui_state_json TEXT,            -- Optional: tabs, selections, filters

    -- Large binary data
    czml_blob BLOB,                -- Cached CZML for fast reload

    -- Metadata
    config_hash TEXT,              -- Hash of config for change detection
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups
CREATE INDEX idx_workspace_blobs_workspace_id ON workspace_blobs(workspace_id);
CREATE INDEX idx_workspaces_updated_at ON workspaces(updated_at DESC);
```

### 9.2 JSON Blob Schemas

#### scenario_config_json
```json
{
  "satellites": [
    {
      "id": "sat_ICEYE-X44",
      "name": "ICEYE-X44",
      "tle": { "line1": "...", "line2": "..." },
      "sensor_config": {
        "sensor_fov_half_angle_deg": 1.0,
        "mode": "OPTICAL"
      },
      "spacecraft_config": {
        "max_spacecraft_roll_deg": 45.0,
        "max_roll_rate_dps": 1.0
      },
      "color": "#FFD700"
    }
  ],
  "targets": [
    {
      "id": "target_Athens",
      "name": "Athens",
      "latitude": 37.9838,
      "longitude": 23.7275,
      "priority": 5,
      "color": "#EF4444"
    }
  ],
  "constraints": {
    "elevation_mask_deg": 10.0,
    "max_spacecraft_roll_deg": 45.0,
    "max_spacecraft_pitch_deg": 30.0,
    "sensor_fov_half_angle_deg": 1.0
  },
  "quality_config": {
    "model": "monotonic",
    "weights": { "priority": 40, "geometry": 40, "timing": 20 }
  }
}
```

#### analysis_state_json
```json
{
  "run_timestamp": "2026-01-06T10:30:00Z",
  "passes": [
    {
      "target_name": "Athens",
      "satellite_name": "ICEYE-X44",
      "satellite_id": "sat_ICEYE-X44",
      "start_time": "2026-01-06T12:15:00Z",
      "end_time": "2026-01-06T12:22:00Z",
      "max_elevation": 45.2,
      "max_elevation_time": "2026-01-06T12:18:30Z",
      "incidence_angle_deg": 23.5
    }
  ],
  "statistics": {
    "total_passes": 14,
    "by_satellite": { "sat_ICEYE-X44": 14 },
    "by_target": { "Athens": 3, "Istanbul": 4 }
  }
}
```

#### planning_state_json
```json
{
  "algorithm_runs": {
    "roll_pitch_best_fit": {
      "run_timestamp": "2026-01-06T10:35:00Z",
      "config_snapshot": { "imaging_time_s": 5.0, "max_roll_rate_dps": 1.0 },
      "schedule": [
        {
          "opportunity_id": "ICEYE-X44_Athens_0_max",
          "satellite_id": "ICEYE-X44",
          "target_id": "Athens",
          "start_time": "2026-01-06T12:18:30Z",
          "roll_angle": 15.2,
          "pitch_angle": 0.0,
          "maneuver_time": 15.2,
          "value": 0.85
        }
      ],
      "metrics": {
        "algorithm": "roll_pitch_best_fit",
        "runtime_ms": 125.5,
        "opportunities_accepted": 8,
        "opportunities_rejected": 6,
        "total_value": 6.8,
        "mean_incidence_deg": 22.5,
        "utilization": 0.78
      },
      "target_statistics": {
        "total_targets": 10,
        "targets_acquired": 8,
        "coverage_percentage": 80.0
      }
    }
  },
  "selected_algorithm": "roll_pitch_best_fit"
}
```

#### orders_state_json
```json
{
  "orders": [
    {
      "order_id": "ord_20260106_001",
      "name": "Athens Campaign v1",
      "created_at": "2026-01-06T11:00:00Z",
      "algorithm": "roll_pitch_best_fit",
      "status": "ACCEPTED",
      "schedule_snapshot": [ /* ... */ ],
      "metrics_snapshot": { /* ... */ }
    }
  ]
}
```

### 9.3 Version Migration Strategy

```python
SCHEMA_VERSION = "1.0"

def migrate_workspace(workspace_data: dict, from_version: str) -> dict:
    """Migrate workspace data between schema versions."""
    if from_version == "1.0" and SCHEMA_VERSION == "1.1":
        # Example migration: add new field with default
        workspace_data.setdefault("new_field", "default_value")
    return workspace_data
```

---

## Appendix A: File References

### Backend Files
- `src/mission_planner/orbit.py` - SatelliteOrbit class
- `src/mission_planner/targets.py` - GroundTarget, TargetManager
- `src/mission_planner/visibility.py` - PassDetails, VisibilityCalculator
- `src/mission_planner/scheduler.py` - Opportunity, ScheduledOpportunity, ScheduleMetrics, SchedulerConfig
- `src/mission_planner/mission_config.py` - SensorConfig, SpacecraftConfig, MissionConfig
- `src/mission_planner/quality_scoring.py` - QualityModel, MultiCriteriaWeights
- `backend/main.py` - API models (TLEData, TargetData, MissionRequest, etc.)
- `backend/czml_generator.py` - CZMLGenerator

### Frontend Files
- `frontend/src/types/index.ts` - TypeScript type definitions
- `frontend/src/context/MissionContext.tsx` - Mission state management
- `frontend/src/store/visStore.ts` - Zustand visualization store

### Config Files
- `config/ground_stations.yaml`
- `config/satellites.yaml`
- `config/mission_settings.yaml`

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **Workspace** | Top-level container for a complete mission session |
| **Scenario** | Mission configuration (satellites, targets, constraints, time window) |
| **Pass** | Visibility window when satellite can see target |
| **Opportunity** | Actionable pass with scheduling metadata |
| **Schedule** | Set of accepted opportunities with maneuver details |
| **Order** | Finalized schedule ready for execution |
| **CZML** | Cesium Markup Language for 3D visualization |
| **Incidence Angle** | Off-nadir angle for imaging quality |
| **Roll/Pitch** | Spacecraft attitude maneuvers |

---

*Document generated as part of PR: Object Tree Audit + Workspace Save/Load Foundation*
