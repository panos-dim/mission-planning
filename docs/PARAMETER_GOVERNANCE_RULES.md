# Parameter Governance Rules

> Single source of truth for which parameters are controlled where.

## Governance Tiers

### Tier 1 — Mission Analysis Inputs (UI, per-run)

User intent for each analysis run. Always visible in the Mission Analysis form.

| Parameter | Description | Default |
|-----------|-------------|---------|
| `targets` | List of ground targets (lat/lon/name/priority) | — (required) |
| `startTime` | Analysis window start (UTC) | Now |
| `endTime` | Analysis window end (UTC) | Now + 24h |
| `imagingType` | `optical` or `sar` | `optical` |
| `pointingAngle` | Max off-nadir for optical (clamped to bus limit) | 45° |
| `sar.imaging_mode` | SAR mode: spot / strip / scan / dwell | `strip` |
| `sar.look_side` | LEFT / RIGHT / ANY | `ANY` |
| `sar.pass_direction` | ASCENDING / DESCENDING / ANY | `ANY` |
| `sar.incidence_min_deg` | Override within mode bounds (Advanced) | Mode recommended min |
| `sar.incidence_max_deg` | Override within mode bounds (Advanced) | Mode recommended max |

### Tier 2 — Mission Planning Inputs (UI, per-run)

Objective tuning for the scheduling optimizer. Basic section always visible; advanced collapsed.

**Basic (always visible):**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `weight_preset` | Scoring preset: balanced / priority / quality / urgent / archival | `balanced` |
| `repairObjective` | Repair goal: maximize_score / maximize_priority / minimize_changes | `maximize_score` |
| `maxChanges` | Max schedule changes in repair mode | 100 |
| `lockPolicy` | Lock enforcement: respect_hard_only / respect_all | `respect_hard_only` |

**Advanced (collapsed by default):**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `imaging_time_s` | Dwell time per acquisition | 1.0 s |
| `look_window_s` | Lookahead window for scheduling | 600 s |
| `value_source` | target_priority / uniform / custom | `target_priority` |
| `quality_model` | off / monotonic / band | `monotonic` |
| `ideal_incidence_deg` | SAR band model center | 35° |
| `band_width_deg` | SAR band model width | 7.5° |
| `weight_priority` | Raw priority weight | 40 |
| `weight_geometry` | Raw geometry weight | 40 |
| `weight_timing` | Raw timing weight | 20 |

### Tier 3 — Admin / YAML Config (not editable per-run)

Platform truth managed exclusively through Admin Panel or YAML files.
The backend **rejects** these if sent via mission input requests (unless `allow_bus_override` flag is set for developer mode).

| Parameter | Source File | Description |
|-----------|------------|-------------|
| `max_spacecraft_roll_deg` | `satellites.yaml` | Bus roll limit |
| `max_roll_rate_dps` | `satellites.yaml` | Slew rate (roll) |
| `max_roll_accel_dps2` | `satellites.yaml` | Slew acceleration (roll) |
| `max_spacecraft_pitch_deg` | `satellites.yaml` | Bus pitch limit |
| `max_pitch_rate_dps` | `satellites.yaml` | Slew rate (pitch) |
| `max_pitch_accel_dps2` | `satellites.yaml` | Slew acceleration (pitch) |
| `settling_time_s` | `satellites.yaml` | Post-maneuver settling |
| `satellite_agility` | `satellites.yaml` | Agility rating (°/s) |
| `sensor_fov_half_angle_deg` | `satellites.yaml` | Sensor FOV half-angle |
| `min_sun_elevation_deg` | `satellites.yaml` | Min sun elevation (optical) |
| `max_cloud_cover_percent` | `satellites.yaml` | Max cloud cover (optical) |
| SAR mode incidence bounds | `sar_modes.yaml` | Per-mode absolute/recommended ranges |
| SAR scene dimensions | `sar_modes.yaml` | Swath width/length per mode |
| SAR quality model params | `sar_modes.yaml` | Optimal incidence, quality model |
| Spacecraft SAR defaults | `sar_modes.yaml` | Max roll, slew rates for SAR bus |

## Enforcement

1. **Backend `ConfigResolver`** validates every mission run request:
   - Admin-only params in request body → **reject with error**
   - Out-of-range values (e.g., incidence outside absolute bounds) → **clamp with warning**
   - Missing satellite config → **reject with clear message**
   - Invalid SAR mode / look side / pass direction → **reject with valid options**

2. **Frontend** does not send admin-only parameters in planning requests.
   Instead, it fetches resolved config from backend (`/api/v1/config/satellite-config-summary`)
   and displays bus/sensor specs as read-only in the Config Summary block.

3. **Config Summary** (read-only, collapsed in Advanced):
   Shows platform roll limit, pitch limit, sensor FOV, SAR defaults for trust/verification.

## Dead Fields (removed from frontend requests)

These legacy fields must NOT be sent in planning or analysis requests:

- `max_roll_rate_dps` / `max_roll_accel_dps2` — admin-only
- `max_pitch_rate_dps` / `max_pitch_accel_dps2` — admin-only
- `elevationMask` — replaced by `mission_settings.yaml` defaults
- `sarMode` (legacy string) — replaced by `sar.imaging_mode`
