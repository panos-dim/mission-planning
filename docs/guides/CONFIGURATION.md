# Configuration Guide

This guide covers all configuration files and options for the Mission Planning Tool.

## Configuration Files

```text
config/
├── satellites.yaml      # Satellite definitions
├── ground_stations.yaml # Ground station locations
└── mission_settings.yaml # Mission planning parameters
```

---

## Satellites Configuration

**File**: `config/satellites.yaml`

```yaml
satellites:
  - name: "ICEYE-X44"
    norad_id: 62707
    tle_source: "celestrak"  # or "file"
    tle_file: "data/active_satellites.tle"  # if source is "file"

  - name: "Custom-SAT"
    tle_line1: "1 99999U ..."
    tle_line2: "2 99999 ..."
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name |
| `norad_id` | integer | NORAD catalog number |
| `tle_source` | string | "celestrak" or "file" |
| `tle_file` | string | Path to TLE file |
| `tle_line1/2` | string | Direct TLE input |

---

## Ground Stations Configuration

**File**: `config/ground_stations.yaml`

```yaml
ground_stations:
  - name: "Space42 UAE"
    latitude: 24.4444
    longitude: 54.8333
    elevation_mask_deg: 10.0
    antenna_type: "S-band"

  - name: "Svalbard"
    latitude: 78.2297
    longitude: 15.3893
    elevation_mask_deg: 5.0
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | required | Station name |
| `latitude` | float | required | Degrees (-90 to 90) |
| `longitude` | float | required | Degrees (-180 to 180) |
| `elevation_mask_deg` | float | 10.0 | Minimum elevation angle |
| `antenna_type` | string | optional | Equipment description |

---

## Mission Settings

**File**: `config/mission_settings.yaml`

```yaml
mission_settings:
  # Default mission parameters
  default_duration_hours: 24
  default_elevation_mask_deg: 10.0

  # Imaging defaults
  imaging:
    default_pointing_angle_deg: 45.0
    default_fov_half_angle_deg: 1.0  # Optical
    sar_fov_half_angle_deg: 30.0     # SAR

  # Spacecraft agility
  spacecraft:
    max_roll_deg: 45.0
    max_pitch_deg: 30.0
    roll_rate_dps: 1.0
    pitch_rate_dps: 1.0
    settle_time_sec: 5.0

  # Scheduling
  scheduling:
    min_imaging_separation_km: 500
    default_algorithm: "first_fit"

  # Output
  output:
    directory: "output"
    formats: ["json", "csv"]
```

### Imaging Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `default_pointing_angle_deg` | 45.0 | Max off-nadir angle |
| `default_fov_half_angle_deg` | 1.0 | Optical sensor FOV |
| `sar_fov_half_angle_deg` | 30.0 | SAR wide swath |

### Spacecraft Agility

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_roll_deg` | 45.0 | Maximum roll angle |
| `max_pitch_deg` | 30.0 | Maximum pitch angle |
| `roll_rate_dps` | 1.0 | Roll slew rate (°/s) |
| `pitch_rate_dps` | 1.0 | Pitch slew rate (°/s) |
| `settle_time_sec` | 5.0 | Attitude settle time |

### Scheduling Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_imaging_separation_km` | 500 | Min distance between images |
| `default_algorithm` | "first_fit" | Default scheduler |

---

## Environment Variables

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8000` | Backend API URL |
| `VITE_CESIUM_ION_TOKEN` | - | Cesium Ion access token |

**File**: `frontend/.env`

```bash
VITE_API_URL=http://localhost:8000
VITE_CESIUM_ION_TOKEN=your_token_here
```

### Backend

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |

---

## Algorithm Configuration

Algorithms can be configured via API or config file:

```yaml
algorithms:
  first_fit:
    enabled: true

  best_fit:
    enabled: true
    geometry_priority: true

  roll_pitch_first_fit:
    enabled: true
    use_pitch: true

  optimal:
    enabled: false  # Computationally expensive
```

---

## Adaptive Time-Stepping

Performance tuning for visibility calculations:

```yaml
adaptive_stepping:
  enabled: true
  initial_step_sec: 10.0
  min_step_sec: 0.25
  max_step_sec: 30.0
  refinement_tolerance_sec: 0.5
```

See [Adaptive Time-Stepping](../algorithms/ADAPTIVE_TIME_STEPPING.md) for details.

---

## Validation

Validate configuration on startup:

```bash
python -m mission_planner.cli validate-config
```

This checks:
- YAML syntax
- Required fields
- Value ranges
- File paths exist
