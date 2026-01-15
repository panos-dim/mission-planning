# Parameter Governance Matrix

**Version**: 1.0
**Last Updated**: January 2026
**Purpose**: Define strict boundaries between Admin/YAML configuration (platform truth) and Mission Analysis inputs (per-run decisions).

---

## Overview

This document establishes the "single source of truth" for all configurable parameters in the Mission Planning system. It follows an STK-style governance model where:

- **Admin/YAML** = What is true about the satellite/payload and system defaults (rarely changes)
- **Mission Input** = What is chosen per scenario/run (changes frequently)
- **Derived** = Computed from other parameters (not directly editable)

---

## Parameter Ownership Matrix

### 1. Spacecraft Bus Parameters

| Parameter | Applies To | Owner | Default Source | Override? | UI Location | Validation |
| --------- | ---------- | ----- | -------------- | --------- | ----------- | ---------- |
| `max_spacecraft_roll_deg` | Both | Admin YAML | `satellites.yaml` | No | Admin → Satellites | 0-90° |
| `max_roll_rate_dps` | Both | Admin YAML | `satellites.yaml` | No | Admin → Satellites | 0.1-10°/s |
| `max_roll_accel_dps2` | Both | Admin YAML | `satellites.yaml` | No | Admin → Satellites | 0.1-10°/s² |
| `max_spacecraft_pitch_deg` | Optical | Admin YAML | `satellites.yaml` | No | Admin → Satellites | 0-45° |
| `max_pitch_rate_dps` | Optical | Admin YAML | `mission_settings.yaml` | No | Admin → Settings | 0-5°/s |
| `max_pitch_accel_dps2` | Optical | Admin YAML | `mission_settings.yaml` | No | Admin → Settings | 0.1-100°/s² |
| `settling_time_s` | Both | Admin YAML | `satellites.yaml` | No | Admin → Satellites | 0-30s |
| `satellite_agility` | Both | Admin YAML | `satellites.yaml` | No | Admin → Satellites | 0.1-5.0°/s |

### 2. Sensor/Payload Parameters

| Parameter | Applies To | Owner | Default Source | Override? | UI Location | Validation |
| --------- | ---------- | ----- | -------------- | --------- | ----------- | ---------- |
| `sensor_fov_half_angle_deg` | Both | Admin YAML | `satellites.yaml` | No | Admin → Satellites | Optical: 0.1-5°, SAR: 5-60° |
| `imaging_type` | Both | Admin YAML | `satellites.yaml` | No | Admin → Satellites | "optical" or "sar" |
| `min_sun_elevation_deg` | Optical | Admin YAML | `satellites.yaml` | No | Admin → Settings | 0-90° |
| `max_cloud_cover_percent` | Optical | Admin YAML | `satellites.yaml` | No | Admin → Settings | 0-100% |

### 3. SAR-Specific Payload Parameters

| Parameter | Applies To | Owner | Default Source | Override? | UI Location | Validation |
| --------- | ---------- | ----- | -------------- | --------- | ----------- | ---------- |
| `sar_modes` | SAR | Admin YAML | `sar_modes.yaml` | No | Admin → SAR Modes | Valid mode names |
| `incidence_angle.recommended_min` | SAR | Admin YAML | `sar_modes.yaml` | No | Admin → SAR Modes | 10-45° |
| `incidence_angle.recommended_max` | SAR | Admin YAML | `sar_modes.yaml` | No | Admin → SAR Modes | 15-55° |
| `incidence_angle.absolute_min` | SAR | Admin YAML | `sar_modes.yaml` | No | Admin → SAR Modes | 5-30° |
| `incidence_angle.absolute_max` | SAR | Admin YAML | `sar_modes.yaml` | No | Admin → SAR Modes | 30-60° |
| `scene.width_km` | SAR | Admin YAML | `sar_modes.yaml` | No | Admin → SAR Modes | 1-200km |
| `scene.length_km` | SAR | Admin YAML | `sar_modes.yaml` | No | Admin → SAR Modes | 1-1000km |
| `collection.duration_s` | SAR | Admin YAML | `sar_modes.yaml` | No | Admin → SAR Modes | 1-60s |
| `quality.optimal_incidence_deg` | SAR | Admin YAML | `sar_modes.yaml` | No | Admin → SAR Modes | 15-45° |
| `polarizations` | SAR | Admin YAML | `satellites.yaml` | No | Admin → SAR Config | VV, VH, HH, HV |

### 4. Ground Station Parameters

| Parameter | Applies To | Owner | Default Source | Override? | UI Location | Validation |
| --------- | ---------- | ----- | -------------- | --------- | ----------- | ---------- |
| `name` | Both | Admin YAML | `ground_stations.yaml` | No | Admin → Ground Stations | Non-empty string |
| `latitude` | Both | Admin YAML | `ground_stations.yaml` | No | Admin → Ground Stations | -90 to 90° |
| `longitude` | Both | Admin YAML | `ground_stations.yaml` | No | Admin → Ground Stations | -180 to 180° |
| `altitude_km` | Both | Admin YAML | `ground_stations.yaml` | No | Admin → Ground Stations | 0-10km |
| `elevation_mask` | Both | Admin YAML | `ground_stations.yaml` | No | Admin → Ground Stations | 0-90° |
| `capabilities` | Both | Admin YAML | `ground_stations.yaml` | No | Admin → Ground Stations | Array of strings |

### 5. Mission Analysis Input Parameters (Per-Run)

| Parameter | Applies To | Owner | Default Source | Override? | UI Location | Validation |
| --------- | ---------- | ----- | -------------- | --------- | ----------- | ---------- |
| `start_time` | Both | Mission Input | Current time | **Yes** | Mission Analysis | ISO8601 UTC |
| `end_time` | Both | Mission Input | +24h from start | **Yes** | Mission Analysis | > start_time |
| `targets` | Both | Mission Input | User selection | **Yes** | Mission Analysis | Array of coordinates |
| `satellites` | Both | Mission Input | Admin selection | **Yes** | Mission Analysis | Array of satellite IDs |

### 6. SAR Mission Input Parameters (Per-Run)

| Parameter | Applies To | Owner | Default Source | Override? | UI Location | Validation |
| --------- | ---------- | ----- | -------------- | --------- | ----------- | ---------- |
| `sar.imaging_mode` | SAR | Mission Input | `sar_modes.yaml` | **Yes** | Mission Analysis → SAR | spot, strip, scan, dwell |
| `sar.look_side` | SAR | Mission Input | `sar_modes.yaml` | **Yes** | Mission Analysis → SAR | LEFT, RIGHT, ANY |
| `sar.pass_direction` | SAR | Mission Input | `sar_modes.yaml` | **Yes** | Mission Analysis → SAR | ASC, DESC, ANY |
| `sar.incidence_min_deg` | SAR | Mission Input | Admin mode default | **Yes** | Mission Analysis → Advanced | Within mode bounds |
| `sar.incidence_max_deg` | SAR | Mission Input | Admin mode default | **Yes** | Mission Analysis → Advanced | Within mode bounds |

### 7. Optical Mission Input Parameters (Per-Run)

| Parameter | Applies To | Owner | Default Source | Override? | UI Location | Validation |
| --------- | ---------- | ----- | -------------- | --------- | ----------- | ---------- |
| `pointing_angle` | Optical | Mission Input | Admin satellite default | **Yes** | Mission Analysis | 0° to max_roll |
| `illumination_filter` | Optical | Mission Input | Default: enabled | **Yes** | Mission Analysis → Advanced | boolean |

### 8. Planning Algorithm Parameters

| Parameter | Applies To | Owner | Default Source | Override? | UI Location | Validation |
| --------- | ---------- | ----- | -------------- | --------- | ----------- | ---------- |
| `algorithm` | Both | Mission Input | User selection | **Yes** | Mission Planning | first_fit, best_fit, etc. |
| `quality_model` | Both | Admin YAML | `mission_settings.yaml` | No | Admin → Settings | monotonic, band |
| `value_source` | Both | Admin YAML | `mission_settings.yaml` | No | Admin → Settings | uniform, priority |
| `default_imaging_time_s` | Both | Admin YAML | `mission_settings.yaml` | No | Admin → Settings | 1-30s |

### 9. Derived/Computed Parameters

| Parameter | Applies To | Owner | Derived From | Override? | UI Location | Notes |
| --------- | ---------- | ----- | ------------ | --------- | ----------- | ----- |
| `pass_duration_s` | Both | Derived | Visibility calculation | No | Hidden | Orbital mechanics |
| `incidence_angle_deg` | Both | Derived | Geometry calculation | No | Results only | Per-opportunity |
| `elevation_deg` | Both | Derived | Geometry calculation | No | Results only | Per-pass |
| `maneuver_time_s` | Both | Derived | Agility params + angles | No | Results only | Per-opportunity |
| `slew_angle_deg` | Both | Derived | Current + target attitude | No | Results only | Per-opportunity |

---

## Configuration File Ownership

| File | Purpose | Editable Via |
| ---- | ------- | ------------ |
| `config/satellites.yaml` | Satellite definitions, TLE, bus/sensor specs | Admin Panel → Satellites |
| `config/sar_modes.yaml` | SAR mode specifications and defaults | Admin Panel → SAR Modes |
| `config/ground_stations.yaml` | Ground station locations and capabilities | Admin Panel → Ground Stations |
| `config/mission_settings.yaml` | System defaults, planning constraints | Admin Panel → Mission Settings |

---

## Validation Rules Summary

### Admin-Level Validation (Enforced on Save)

1. **Bus Limits**: `max_roll_deg` ≤ 90°, rates > 0
2. **SAR Mode Bounds**: `absolute_min` ≤ `recommended_min` ≤ `recommended_max` ≤ `absolute_max`
3. **Ground Station**: Valid lat/lon ranges, elevation_mask 0-90°
4. **Sensor FOV**: Optical 0.1-5°, SAR 5-60°

### Mission Input Validation (Enforced on Submit)

1. **Time Window**: `end_time` > `start_time`, duration ≤ 30 days
2. **SAR Incidence Override**: Must be within satellite/mode absolute bounds
3. **Pointing Angle Override**: Must be ≤ satellite's `max_spacecraft_roll_deg`
4. **At least one target and one satellite selected**

### Cross-Validation Rules

| Rule | Check | Action on Failure |
| ---- | ----- | ----------------- |
| SAR mode supported | `sar.imaging_mode` in satellite's supported modes | Reject with error |
| Incidence within bounds | `incidence_min/max` within mode's absolute bounds | Clamp to bounds + warning |
| Roll within bus limits | `pointing_angle` ≤ `max_spacecraft_roll_deg` | Reject with error |
| Sensor type match | `imaging_type` matches mission type selection | Auto-filter satellites |

---

## UI Organization

### Admin Panel (Platform Truth)

```text
Admin Panel
├── Ground Stations
│   ├── List with CRUD operations
│   └── Elevation mask, coordinates, capabilities
├── Satellites
│   ├── Constellation management
│   ├── TLE data (with refresh)
│   └── Bus specs (roll/pitch limits, rates)
├── SAR Modes (NEW)
│   ├── Mode definitions (spot/strip/scan/dwell)
│   ├── Incidence angle bounds per mode
│   └── Scene/swath defaults
└── Mission Settings
    ├── Pass duration constraints
    ├── Elevation constraints
    ├── Planning algorithm defaults
    └── Output format settings
```

### Mission Analysis Form (Per-Run Decisions)

```text
Mission Analysis
├── Step 1: Define Targets
│   ├── Add/import targets
│   └── Priority assignment
├── Step 2: Mission Parameters
│   ├── Time window (start/end)
│   ├── Imaging Type toggle (Optical/SAR)
│   │
│   ├── [IF OPTICAL]
│   │   └── Max Agility slider (constrained by satellite)
│   │
│   └── [IF SAR]
│       ├── Imaging Mode dropdown (spot/strip/scan)
│       ├── Look Side (L/R/ANY)
│       ├── Pass Direction (ASC/DESC/ANY)
│       └── [Advanced] Incidence range override
│
└── [Satellites shown as read-only, selected in Admin]
```

---

## Migration Notes

### Parameters Removed from Mission Analysis Form

- `max_roll_rate_dps` → Admin only (satellite capability)
- `max_roll_accel_dps2` → Admin only (satellite capability)
- `settling_time_s` → Admin only (satellite capability)
- `sensor_fov_half_angle_deg` → Admin only (payload specification)

### Parameters Added to Admin Panel

- SAR mode configuration (full mode specs)
- Satellite bus constraints (roll/pitch limits)
- Quality model selection

---

## Config Snapshot & Versioning

Workspaces should include:

1. **Config Hash**: SHA256 of all YAML files at analysis time
2. **Config Snapshot**: Copy of relevant config sections
3. **Timestamp**: When config was captured

This enables:

- Reproducible analysis runs
- Audit trail for configuration changes
- Rollback capability

---

## Changelog

| Date | Version | Changes |
| ---- | ------- | ------- |
| Jan 2026 | 1.0 | Initial parameter governance matrix |
