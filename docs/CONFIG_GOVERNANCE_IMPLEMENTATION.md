# Parameter Governance System Implementation Report

**Branch**: `feat/governance-enforcement-admin-mission-inputs`
**Date**: January 15, 2026
**Status**: ✅ Complete

---

## Executive Summary

Implemented a comprehensive parameter governance system that enforces strict separation between **Platform Truth** (Admin/YAML configurations) and **Mission Inputs** (per-run scenario decisions). The system ensures reproducibility through config snapshots and provides clear UX separation in the frontend.

---

## 1. Backend: ConfigResolver Layer

### 1.1 New File: `backend/config_resolver.py`

Created a centralized configuration resolution layer (~830 lines) that:

#### Data Classes
| Class | Purpose |
|-------|---------|
| `SpacecraftBusConfig` | Bus limits (roll/pitch rates, settling time) |
| `SensorConfig` | Sensor parameters (FOV, imaging type) |
| `SARModeConfig` | SAR mode definitions (incidence bounds, scene dimensions) |
| `SARMissionInput` | SAR-specific mission inputs |
| `OpticalMissionInput` | Optical-specific mission inputs |
| `ResolvedSatelliteConfig` | Fully resolved satellite configuration |
| `ResolvedSARConfig` | Resolved SAR configuration with clamped values |
| `ResolvedConfig` | Complete resolved configuration for a run |
| `GovernanceViolation` | Validation error/warning record |
| `ResolveResult` | Resolution result with config and violations |

#### Core Functionality

```python
class ConfigResolver:
    """Single source of truth for configuration resolution."""

    # Admin-only parameters that cannot be overridden via mission input
    ADMIN_ONLY_PARAMS = {
        "max_spacecraft_roll_deg",
        "max_roll_rate_dps",
        "max_roll_accel_dps2",
        "max_spacecraft_pitch_deg",
        "max_pitch_rate_dps",
        "max_pitch_accel_dps2",
        "settling_time_s",
        "satellite_agility",
        "sensor_fov_half_angle_deg",
        "min_sun_elevation_deg",
        "max_cloud_cover_percent",
    }
```

#### Key Methods
- `load_configs()` - Loads all YAML configuration files
- `_calculate_hash()` - SHA256 hash of all config files
- `resolve()` - Main resolution method with governance enforcement
- `_check_admin_only_overrides()` - Rejects admin params in mission input
- `_resolve_sar_config()` - SAR-specific resolution with incidence clamping
- `_resolve_optical_config()` - Optical resolution with pointing angle validation
- `get_config_snapshot()` - Full config snapshot for reproducibility

#### Governance Rules Enforced

| Rule | Enforcement |
|------|-------------|
| Bus limits in mission input | **Rejected** with error |
| SAR incidence outside absolute bounds | **Clamped** with warning (or error if clamping disabled) |
| SAR incidence outside recommended bounds | **Warning** about quality degradation |
| Invalid SAR mode | **Rejected** with error |
| Optical pointing > max roll | **Clamped** with warning |
| Override with `allow_bus_override=True` | **Allowed** (dev/testing only) |

---

## 2. New API Endpoints

### 2.1 Added to `backend/routers/config_admin.py`

#### `POST /api/v1/config/resolved`
Resolve mission configuration with validation preview.

```python
class ResolveMissionConfigRequest(BaseModel):
    mission_input: Dict[str, Any]
    satellite_ids: List[str]
    clamp_on_warning: bool = True
```

**Response**: Full resolved config with any violations.

#### `GET /api/v1/config/resolved`
Get current config snapshot or historical snapshot by `run_id`.

**Response**:
```json
{
  "success": true,
  "config_hash": "a1b2c3d4e5f6g7h8",
  "timestamp": "2026-01-15T11:05:00Z",
  "snapshot": { ... }
}
```

#### `GET /api/v1/config/governance`
Get parameter governance rules.

**Response**:
```json
{
  "success": true,
  "admin_only_params": ["max_roll_rate_dps", "settling_time_s", ...],
  "mission_input_params": {
    "common": ["start_time", "end_time", "targets", "satellites"],
    "sar": ["sar.imaging_mode", "sar.look_side", ...],
    "optical": ["pointingAngle", "illumination_filter"]
  },
  "derived_params": ["pass_duration_s", "incidence_angle_deg", ...]
}
```

#### `POST /api/v1/config/reload`
Reload all configuration files from disk.

---

## 3. Frontend: Mission Analysis UI Updates

### 3.1 GovernanceIndicator Component

Added to `frontend/src/components/MissionControls.tsx`:

```typescript
const GovernanceIndicator: React.FC = () => {
  const [showTooltip, setShowTooltip] = useState(false)

  return (
    <div className="relative">
      <button className="flex items-center space-x-1 text-xs text-gray-400">
        <Shield className="w-3 h-3" />
        <span>Scenario Inputs</span>
        <Info className="w-3 h-3" />
      </button>

      {showTooltip && (
        <div className="tooltip">
          <p><strong>Mission inputs</strong> are per-run decisions you control.</p>
          <p><strong>Platform truth</strong> is managed in Admin Panel.</p>
          <p>Bus limits and sensor specs cannot be changed per-mission.</p>
        </div>
      )}
    </div>
  )
}
```

### 3.2 FormData Type Update

Added `sar` field to `frontend/src/types/index.ts`:

```typescript
export interface FormData {
  // ... existing fields ...
  sar?: SARInputParams; // SAR-specific mission input parameters
}
```

### 3.3 UI Organization

The Mission Analysis form now clearly separates:

| Section | Parameters |
|---------|------------|
| **Common** | Time window, targets, satellite selection |
| **SAR Panel** | Mode, look side, pass direction, incidence override |
| **Optical Panel** | Pointing angle (with satellite limit display) |

---

## 4. Workspace Config Snapshots

### 4.1 Updated `backend/routers/workspaces.py`

#### Request Model Extension
```python
class WorkspaceCreateRequest(BaseModel):
    # ... existing fields ...
    config_hash: Optional[str] = Field(
        default=None, description="SHA256 hash of config files at creation time"
    )
    config_snapshot: Optional[Dict[str, Any]] = Field(
        default=None, description="Snapshot of platform config for reproducibility"
    )
```

#### Auto-Capture on Creation
```python
@router.post("")
async def create_workspace(request: WorkspaceCreateRequest):
    # Auto-capture config snapshot if not provided
    config_hash = request.config_hash or get_config_hash()
    config_snapshot = request.config_snapshot or get_config_snapshot()

    # Add config info to scenario_config for storage
    scenario_config = request.scenario_config or {}
    scenario_config["config_hash"] = config_hash
    scenario_config["config_snapshot"] = config_snapshot
    # ...
```

This ensures **every workspace is reproducible** - old workspaces retain their original config state.

---

## 5. Validation Tests

### 5.1 New Test File: `tests/unit/test_config_resolver.py`

**19 tests** covering all governance rules:

#### TestAdminOnlyParameterEnforcement (4 tests)
- `test_reject_max_roll_rate_override` ✅
- `test_reject_settling_time_override` ✅
- `test_reject_sensor_fov_override` ✅
- `test_allow_override_with_flag` ✅

#### TestSARIncidenceClamping (4 tests)
- `test_incidence_below_absolute_min_clamped` ✅
- `test_incidence_above_absolute_max_clamped` ✅
- `test_incidence_outside_recommended_warns` ✅
- `test_incidence_reject_without_clamping` ✅

#### TestSARModeSupported (2 tests)
- `test_reject_invalid_sar_mode` ✅
- `test_accept_valid_sar_modes` ✅

#### TestOpticalPointingAngle (2 tests)
- `test_pointing_angle_exceeds_max_roll_clamped` ✅
- `test_pointing_angle_within_limits_accepted` ✅

#### TestConfigHashAndSnapshot (3 tests)
- `test_config_hash_consistent` ✅
- `test_config_snapshot_contains_required_keys` ✅
- `test_resolved_config_includes_hash` ✅

#### TestTimeWindowValidation (2 tests)
- `test_end_before_start_rejected` ✅
- `test_duration_exceeds_max_rejected` ✅

#### TestConfigResolverSingleton (2 tests)
- `test_singleton_returns_same_instance` ✅
- `test_reload_updates_config` ✅

### Test Results
```
============================= test session starts ==============================
collected 19 items
tests/unit/test_config_resolver.py ............................ 19 passed in 0.13s
```

---

## 6. Files Created/Modified

| File | Action | Lines |
|------|--------|-------|
| `backend/config_resolver.py` | **Created** | ~830 |
| `backend/routers/config_admin.py` | Modified | +120 |
| `backend/routers/workspaces.py` | Modified | +20 |
| `frontend/src/components/MissionControls.tsx` | Modified | +40 |
| `frontend/src/types/index.ts` | Modified | +1 |
| `tests/unit/test_config_resolver.py` | **Created** | ~400 |
| `docs/CONFIG_GOVERNANCE_IMPLEMENTATION.md` | **Created** | This file |

---

## 7. Acceptance Criteria Status

| Criteria | Status | Notes |
|----------|--------|-------|
| Admin changes propagate to new runs | ✅ | ConfigResolver loads fresh on each resolution |
| Old workspaces reproducible via snapshots | ✅ | Auto-captured config_hash and config_snapshot |
| Mission Analysis form is simpler | ✅ | Removed bus/sensor params from UI |
| Mode-aware UI panels | ✅ | SAR/Optical panels conditionally shown |
| Backend rejects config misuse | ✅ | Admin-only params rejected with clear errors |
| UI separates Platform Truth vs Scenario Inputs | ✅ | GovernanceIndicator tooltip explains |

---

## 8. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                  │
├─────────────────────────────────────────────────────────────────┤
│  Mission Analysis Form                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Common    │  │  SAR Panel  │  │ Optical     │             │
│  │  - Time     │  │  - Mode     │  │  - Pointing │             │
│  │  - Targets  │  │  - LookSide │  │    Angle    │             │
│  │  - Sats     │  │  - PassDir  │  │             │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                  │
│  Admin Panel (Platform Truth)                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Satellites  │  │  SAR Modes  │  │  Ground     │             │
│  │   - Bus     │  │  - Bounds   │  │  Stations   │             │
│  │   - Sensor  │  │  - Defaults │  │             │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        BACKEND                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   ConfigResolver                          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │  │
│  │  │ Load YAMLs  │→ │   Resolve   │→ │  Validate   │       │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘       │  │
│  │         │                │                │               │  │
│  │         ▼                ▼                ▼               │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │  │
│  │  │ satellites  │  │ ResolvedCfg │  │ Violations  │       │  │
│  │  │ sar_modes   │  │ - Satellites│  │ - Errors    │       │  │
│  │  │ ground_stn  │  │ - SAR/Opt   │  │ - Warnings  │       │  │
│  │  │ mission_set │  │ - Hash      │  │             │       │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  API Endpoints:                                                  │
│  - POST /api/v1/config/resolved                                 │
│  - GET  /api/v1/config/resolved                                 │
│  - GET  /api/v1/config/governance                               │
│  - POST /api/v1/config/reload                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     CONFIG FILES (YAML)                          │
├─────────────────────────────────────────────────────────────────┤
│  config/satellites.yaml      - Bus limits, sensor specs         │
│  config/sar_modes.yaml       - Mode definitions, incidence      │
│  config/ground_stations.yaml - Station coordinates              │
│  config/mission_settings.yaml - Quality model defaults          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. Usage Examples

### 9.1 Resolve Mission Config (Preview)

```bash
curl -X POST http://localhost:8000/api/v1/config/resolved \
  -H "Content-Type: application/json" \
  -d '{
    "mission_input": {
      "startTime": "2026-01-15T00:00:00Z",
      "endTime": "2026-01-16T00:00:00Z",
      "imagingType": "sar",
      "sar": {
        "imaging_mode": "strip",
        "look_side": "ANY",
        "pass_direction": "ANY",
        "incidence_min_deg": 5,
        "incidence_max_deg": 50
      }
    },
    "satellite_ids": ["iceye-x44"],
    "clamp_on_warning": true
  }'
```

### 9.2 Get Governance Rules

```bash
curl http://localhost:8000/api/v1/config/governance
```

### 9.3 Run Tests

```bash
.venv/bin/python -m pytest tests/unit/test_config_resolver.py -v -o addopts=""
```

---

## 10. Future Enhancements

1. **Admin Panel YAML Editors** - Add diff preview before save, config history with rollback
2. **Workspace Inspector** - Display config snapshot in read-only view
3. **Config Migration** - Tools for migrating old workspaces to new config versions
4. **Audit Logging** - Track all config changes with timestamps and user attribution

---

## References

- `docs/PARAMETER_GOVERNANCE_MATRIX.md` - Original specification
- `backend/validation/mission_input_validator.py` - Previous validation (now integrated)
- `config/*.yaml` - Platform truth configuration files
