# Backend Router Organization

> Modular API structure for the mission planning backend

## Overview

The backend API is organized into domain-specific routers located in `backend/routers/`:

```text
backend/routers/
├── __init__.py         # Router exports
├── tle.py              # TLE validation and satellite data
├── mission.py          # Mission analysis (stub, main logic in main.py)
├── planning.py         # Scheduling algorithms
├── config.py           # Configuration management
└── debug.py            # Debug and benchmarking
```

## Router Summary

| Router | Prefix | Description |
|--------|--------|-------------|
| TLE | `/api/tle` | TLE validation, satellite search |
| Mission | `/api/mission` | Mission analysis status |
| Planning | `/api/planning` | Opportunities, scheduling |
| Config | `/api` | Ground stations, satellites, settings |
| Debug | `/api/debug` | Presets, scenarios, benchmarks |

---

## TLE Router (`tle.py`)

Handles Two-Line Element operations for satellite orbital data.

### Endpoints

#### `POST /api/tle/validate`

Validate TLE data and get satellite information.

**Request:**

```json
{
  "name": "ICEYE-X44",
  "line1": "1 56195U 23054G   25...",
  "line2": "2 56195  97.5541..."
}
```

**Response:**

```json
{
  "valid": true,
  "satellite_name": "ICEYE-X44",
  "current_position": {
    "latitude": 45.2,
    "longitude": -120.5,
    "altitude_km": 591.2,
    "timestamp": "2025-12-03T12:00:00Z"
  },
  "orbital_period_minutes": 96.5
}
```

#### `GET /api/tle/sources`

Get available TLE data sources.

#### `GET /api/tle/search?query=ICEYE`

Search for satellites by name.

---

## Planning Router (`planning.py`)

Handles mission planning and scheduling algorithms.

### Endpoints

#### `GET /api/planning/opportunities`

Get current opportunities available for scheduling.

**Response:**

```json
{
  "success": true,
  "opportunities": [
    {
      "id": "ICEYE-X44_Athens_0",
      "satellite_id": "ICEYE-X44",
      "target_id": "Athens",
      "start_time": "2025-12-04T08:15:00Z",
      "end_time": "2025-12-04T08:22:00Z",
      "value": 1.0,
      "incidence_angle": 23.5
    }
  ],
  "count": 15
}
```

#### `POST /api/planning/schedule`

Run scheduling algorithms on opportunities.

**Request:**

```json
{
  "imaging_time_s": 1.0,
  "max_roll_rate_dps": 1.0,
  "max_roll_accel_dps2": 10000.0,
  "max_pitch_rate_dps": 1.0,
  "max_pitch_accel_dps2": 10000.0,
  "algorithms": ["first_fit", "best_fit"],
  "quality_model": "monotonic",
  "weight_priority": 40,
  "weight_geometry": 40,
  "weight_timing": 20
}
```

**Response:**

```json
{
  "success": true,
  "results": {
    "first_fit": {
      "schedule": [...],
      "metrics": {
        "opportunities_accepted": 12,
        "total_value": 10.5,
        "runtime_ms": 2.3
      },
      "target_statistics": {
        "total_targets": 10,
        "targets_acquired": 8,
        "coverage_percentage": 80.0
      }
    }
  }
}
```

---

## Config Router (`config.py`)

Manages application configuration.

### Ground Station Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ground-stations` | List all ground stations |
| POST | `/api/ground-stations` | Add new ground station |
| PUT | `/api/ground-stations/{name}` | Update ground station |
| DELETE | `/api/ground-stations/{name}` | Delete ground station |

### Satellite Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/satellites` | List all satellites |
| POST | `/api/satellites` | Add new satellite |
| PUT | `/api/satellites/{id}` | Update satellite |
| DELETE | `/api/satellites/{id}` | Delete satellite |
| POST | `/api/satellites/{id}/refresh-tle` | Refresh TLE data |

### Mission Settings Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/mission-settings` | Get all settings |
| PUT | `/api/mission-settings/{section}/{key}` | Update setting |
| POST | `/api/mission-settings/reload` | Reload from file |

---

## Debug Router (`debug.py`)

Development and testing utilities.

### Endpoints

#### `GET /api/debug/presets`

Get available test scenario presets.

#### `POST /api/debug/run-scenario`

Run a debug scenario with custom configuration.

#### `POST /api/debug/benchmark`

Run benchmark across multiple scenarios.

#### `GET /api/debug/health`

Health check endpoint.

---

## Router Registration

In `main.py`, routers are registered:

```python
from backend.routers import (
    tle_router,
    mission_router,
    planning_router,
    config_router,
    debug_router
)

app.include_router(tle_router)
app.include_router(mission_router)
app.include_router(planning_router)
app.include_router(config_router)
app.include_router(debug_router)
```

---

## Adding New Routers

1. Create new file in `backend/routers/`
2. Define router with prefix and tags:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/newroute", tags=["NewFeature"])

@router.get("/endpoint")
async def my_endpoint():
    return {"success": True}
```

3. Export in `__init__.py`:

```python
from .newroute import router as newroute_router
```

4. Register in `main.py`:

```python
app.include_router(newroute_router)
```
