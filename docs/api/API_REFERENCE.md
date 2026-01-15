# API Reference

> Complete REST API documentation for COSMOS42

## Base URL

```text
Development: http://localhost:8000
Production: https://your-domain.com
```

## Authentication

Currently no authentication required (internal tool).

---

## Endpoints Overview

### TLE Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/tle/validate` | Validate TLE and get satellite info |
| GET | `/api/tle/sources` | List TLE data sources |
| GET | `/api/tle/search` | Search satellites by name |

### Mission Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/mission/analyze` | Run full mission analysis |
| GET | `/api/mission/status` | Get analysis status |

### Mission Planning

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/planning/opportunities` | Get available opportunities |
| POST | `/api/planning/schedule` | Run scheduling algorithms |
| POST | `/api/planning/clear` | Clear planning state |

### Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config/full` | Get full configuration |
| GET | `/api/ground-stations` | List ground stations |
| POST | `/api/ground-stations` | Add ground station |
| PUT | `/api/ground-stations/{name}` | Update ground station |
| DELETE | `/api/ground-stations/{name}` | Delete ground station |
| GET | `/api/satellites` | List managed satellites |
| POST | `/api/satellites` | Add satellite |
| PUT | `/api/satellites/{id}` | Update satellite |
| DELETE | `/api/satellites/{id}` | Delete satellite |
| GET | `/api/mission-settings` | Get mission settings |

### Targets

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/targets/parse` | Parse coordinate string |
| POST | `/api/targets/upload` | Upload targets from file |

---

## Detailed Endpoint Documentation

### POST /api/mission/analyze

Analyze mission visibility and generate opportunities.

#### Request Body

```json
{
  "tle": {
    "name": "ICEYE-X44",
    "line1": "1 56195U 23054G   25...",
    "line2": "2 56195  97.5541..."
  },
  "targets": [
    {
      "name": "Athens",
      "latitude": 37.9838,
      "longitude": 23.7275,
      "description": "Capital of Greece",
      "priority": 1,
      "color": "#EF4444"
    }
  ],
  "start_time": "2025-12-04T00:00:00Z",
  "end_time": "2025-12-06T00:00:00Z",
  "mission_type": "imaging",
  "imaging_type": "optical",
  "elevation_mask": 10,
  "max_spacecraft_roll_deg": 45.0,
  "use_parallel": true,
  "use_adaptive": true
}
```

#### Parameters

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| tle | TLEData | Yes | - | Satellite TLE data |
| targets | TargetData[] | Yes | - | List of ground targets |
| start_time | string (ISO8601) | Yes | - | Analysis start time |
| end_time | string (ISO8601) | No | - | Analysis end time |
| duration_hours | number | No | - | Alternative to end_time |
| mission_type | string | Yes | - | "imaging" or "communication" |
| imaging_type | string | No | "optical" | "optical" or "sar" |
| elevation_mask | number | No | 10 | Minimum elevation (degrees) |
| max_spacecraft_roll_deg | number | No | 45 | Max roll angle |
| use_parallel | boolean | No | true | Enable parallel processing |
| use_adaptive | boolean | No | false | Enable adaptive time stepping |

#### Response

```json
{
  "success": true,
  "mission_type": "imaging",
  "satellite_name": "ICEYE-X44",
  "duration_hours": 48.0,
  "passes": [
    {
      "target_name": "Athens",
      "start_time": "2025-12-04T08:15:00Z",
      "end_time": "2025-12-04T08:22:00Z",
      "max_elevation": 45.2,
      "max_elevation_time": "2025-12-04T08:18:30Z",
      "incidence_angle_deg": 23.5,
      "imaging_time": "2025-12-04T08:18:30Z"
    }
  ],
  "czml": [...],
  "opportunities": [...],
  "analysis_metrics": {
    "analysis_time_seconds": 2.3,
    "total_passes": 15,
    "targets_processed": 5
  }
}
```

---

### POST /api/planning/schedule

Run scheduling algorithms on opportunities.

#### Request Body

```json
{
  "imaging_time_s": 1.0,
  "max_roll_rate_dps": 1.0,
  "max_roll_accel_dps2": 10000.0,
  "max_pitch_rate_dps": 1.0,
  "max_pitch_accel_dps2": 10000.0,
  "algorithms": ["first_fit", "best_fit", "roll_pitch_first_fit"],
  "value_source": "target_priority",
  "look_window_s": 600.0,
  "quality_model": "monotonic",
  "ideal_incidence_deg": 35.0,
  "band_width_deg": 7.5,
  "weight_priority": 40,
  "weight_geometry": 40,
  "weight_timing": 20
}
```

#### Algorithms

| Algorithm | Description |
|-----------|-------------|
| `first_fit` | Greedy chronological selection |
| `best_fit` | Global best geometry per target |
| `roll_pitch_first_fit` | First-fit with 2D slew |
| `roll_pitch_best_fit` | Best-fit with 2D slew |

#### Response

```json
{
  "success": true,
  "message": "Completed 3 algorithms",
  "results": {
    "first_fit": {
      "schedule": [
        {
          "opportunity_id": "ICEYE-X44_Athens_0",
          "satellite_id": "ICEYE-X44",
          "target_id": "Athens",
          "start_time": "2025-12-04T08:18:30Z",
          "value": 0.85,
          "incidence_angle": 23.5,
          "roll_angle": 23.5,
          "pitch_angle": 0.0,
          "delta_roll": 23.5,
          "delta_pitch": 0.0,
          "maneuver_time": 23.5,
          "slack_time": 120.0
        }
      ],
      "metrics": {
        "opportunities_evaluated": 15,
        "opportunities_accepted": 10,
        "total_value": 8.5,
        "runtime_ms": 1.2,
        "mean_incidence_deg": 25.3,
        "total_maneuver_time_s": 180.0,
        "utilization": 0.67
      },
      "target_statistics": {
        "total_targets": 5,
        "targets_acquired": 4,
        "targets_missing": 1,
        "coverage_percentage": 80.0,
        "missing_target_ids": ["Thessaloniki"]
      }
    }
  }
}
```

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "success": false,
  "error": "Error message",
  "detail": "Additional details if available"
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid parameters |
| 404 | Not Found - Resource doesn't exist |
| 422 | Validation Error - Invalid request body |
| 500 | Server Error - Internal error |

---

## Rate Limiting

No rate limiting currently implemented.

---

## WebSocket Endpoints

Currently no WebSocket endpoints. Future: real-time mission updates.
