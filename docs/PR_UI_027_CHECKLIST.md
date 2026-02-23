# PR-UI-027: Master Schedule Timeline — Dynamic Zoom & Global Future View

## Summary

Adds a **Master** tab to the Schedule panel that renders a backend-driven global
timeline of all future scheduled acquisitions in the selected workspace's time
range. The timeline reuses the existing `ScheduleTimeline` component and adds
aggregation support for zoomed-out performance.

## Data Audit

| Field | Source | Storage | Status |
|---|---|---|---|
| `acquisition_id` | auto-generated | `acquisitions.id` | ✅ existing |
| `workspace_id` | commit request | `acquisitions.workspace_id` | ✅ existing |
| `scheduled_start_time` | plan item | `acquisitions.start_time` | ✅ existing |
| `satellite_id` | plan item | `acquisitions.satellite_id` | ✅ existing |
| `satellite_display_name` | workspace config | `acquisitions.satellite_display_name` | 🆕 v2.5 |
| `target_id` | plan item | `acquisitions.target_id` | ✅ existing |
| `target_lat` | workspace config | `acquisitions.target_lat` | 🆕 v2.5 |
| `target_lon` | workspace config | `acquisitions.target_lon` | 🆕 v2.5 |
| `off_nadir_deg` | abs(roll_angle_deg) | `acquisitions.off_nadir_deg` | 🆕 v2.5 |
| `mode` | commit request | `acquisitions.mode` | ✅ existing |

## DB Migration

- **v2.5**: `_migrate_to_v2_5` in `schedule_persistence.py`
  - Adds columns: `target_lat REAL`, `target_lon REAL`, `satellite_display_name TEXT`, `off_nadir_deg REAL`
  - Backfills `off_nadir_deg` from `ABS(roll_angle_deg)` for existing rows
  - Backfills `target_lat`/`target_lon` from workspace `scenario_config.targets[]` JSON
  - Adds composite index `idx_acq_workspace_time(workspace_id, start_time, end_time)`

## API Contract

### `GET /api/v1/schedule/master`

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `workspace_id` | string | ✅ | — | Workspace to query |
| `t_start` | ISO datetime | — | now | Visible range start |
| `t_end` | ISO datetime | — | +7 days | Visible range end |
| `zoom` | `detail` \| `aggregate` | — | `detail` | Zoom level |
| `limit` | int (1–5000) | — | 2000 | Max items in detail mode |
| `offset` | int | — | 0 | Pagination offset |

**Response** (`MasterScheduleResponse`):
```json
{
  "success": true,
  "zoom": "detail",
  "total": 42,
  "items": [ { "id": "acq_...", "satellite_id": "...", ... } ],
  "buckets": [],
  "t_start": "2026-02-05T00:00:00Z",
  "t_end": "2026-02-12T00:00:00Z",
  "fetch_ms": 12.3
}
```

In `aggregate` mode, `items` is empty and `buckets` contains grouped data:
```json
{
  "target_id": "T1",
  "satellite_id": "ICEYE-X44",
  "mode": "SAR",
  "bucket_start": "...",
  "bucket_end": "...",
  "count": 5,
  "target_lat": 40.7,
  "target_lon": -74.0,
  "avg_off_nadir_deg": 22.31
}
```

## Frontend Changes

| File | Change |
|---|---|
| `store/scheduleStore.ts` | 🆕 Zustand store for master schedule state |
| `api/scheduleApi.ts` | Added `getMasterSchedule()` + types |
| `api/config.ts` | Added `SCHEDULE_MASTER` endpoint |
| `constants/simpleMode.ts` | Added `MASTER` tab to `SCHEDULE_TABS` |
| `components/SchedulePanel.tsx` | Added `MasterTimelineTab` component + tab |
| `components/Map/GlobeViewport.tsx` | Map fly-to on focused acquisition |
| `store/index.ts` | Barrel export for `scheduleStore` |

## Performance

- **Aggregation**: `zoom=aggregate` groups by target×satellite, reducing payload
- **Pagination**: `limit`/`offset` on detail mode (default 2000 items)
- **DB index**: `idx_acq_workspace_time` for fast range queries
- **Perf counter**: `fetch_ms` returned in API response, displayed in UI

## Verification

- [ ] Backend starts without errors (migration v2.5 runs)
- [ ] `GET /api/v1/schedule/master?workspace_id=...` returns data
- [ ] Master tab appears in Schedule panel
- [ ] Timeline renders acquisitions from backend
- [ ] Clicking acquisition in Master tab flies map to target
- [ ] Aggregate mode works when zoom=aggregate
- [ ] No scheduler algorithm changes
- [ ] No conflict UI changes
- [ ] `pytest tests/unit/` passes
- [ ] Frontend `npm run build` succeeds
