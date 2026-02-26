# PR-UI-030 — STK-Level Schedule View: Checklist

**Branch:** `feat/schedule-stk-level-live-master-view-satellites-sync-and-dynamic-cesium-timeline`

---

## A. Data Contract Audit

| Field | Backend (`Acquisition`) | API (`MasterScheduleItem`) | Frontend (`ScheduledAcquisition`) | Status |
|---|---|---|---|---|
| `id` / `opportunity_id` | `opportunity_id` | `id` | `id` | ✅ |
| `satellite_id` | `satellite_id` | `satellite_id` | `satellite_id` | ✅ |
| `satellite_name` | `satellite_display_name` | `satellite_display_name` | `satellite_name` | ✅ |
| `target_id` | `target_id` | `target_id` | `target_id` | ✅ |
| `target_lat` | `target_lat` | `target_lat` | `target_lat` *(new)* | ✅ |
| `target_lon` | `target_lon` | `target_lon` | `target_lon` *(new)* | ✅ |
| `start_time` | `start_time` | `start_time` | `start_time` | ✅ |
| `end_time` | `end_time` | `end_time` | `end_time` | ✅ |
| `off_nadir_deg` | `off_nadir_deg` | `off_nadir_deg` | `off_nadir_deg` | ✅ |
| `lock_level` | `lock_level` | `lock_level` | `lock_level` | ✅ |
| `mode` | `mode` | `mode` | `mode` | ✅ |

No backend schema changes were required — all fields were already persisted.

---

## B. Features Implemented

### B1 — Satellite Name/ID in Timeline Entries
- **Where:** `ScheduleTimeline.tsx`
- Each acquisition bar now renders the satellite name (or `satellite_id` as fallback) as an inline badge when the bar is wide enough (`widthPct > 3`).
- Tooltip already showed satellite name (unchanged).
- A **Satellite filter chip** was added to the filter bar (alongside the existing Target chip) allowing per-satellite filtering.

### B2 — Click a Pass → Focus Satellite + Sync Timelines
- **Where:** `ScheduleTimeline.tsx` → `SchedulePanel.tsx` → `scheduleStore.ts` → `GlobeViewport.tsx`
- Clicking a bar calls `onSelectAcquisition(acq: ScheduledAcquisition)` with the full item.
- `SchedulePanel.handleSelectAcquisition` calls `scheduleStore.focusAcquisition(id, { startTime, lat, lon })`.
- `GlobeViewport` subscribes to `focusedAcquisitionId` / `focusedTargetCoords` / `focusedStartTime`:
  - Calls `viewer.camera.flyTo({ destination: Cartesian3.fromDegrees(lon, lat, 1_200_000), duration: 1.5 })`.
  - Calls `setClockTime(JulianDate.fromIso8601(startTime))` → Cesium clock jumps to pass start.

### B3 — Dynamic Cesium Timeline Range Sync
- **Where:** `ScheduleTimeline.tsx` → `SchedulePanel.tsx` → `visStore.ts` → `GlobeViewport.tsx`
- `ScheduleTimeline` emits `onViewRangeChange(minMs, maxMs)` (debounced 300 ms) when the user zooms or pans.
- `SchedulePanel.handleViewRangeChange` converts timestamps to ISO and calls `visStore.setTimeRangeFromIso(start, stop)`.
- `visStore.setTimeRangeFromIso` updates `timeWindow` (JulianDates) + `clockTime`.
- The existing `useEffect` in `GlobeViewport` that watches `clockTime` propagates the change to `viewer.clock.currentTime`.

### B4 — Live Polling
- **Where:** `scheduleStore.ts` + `SchedulePanel.tsx`
- `scheduleStore.startPolling(workspaceId, intervalMs = 15_000)` starts a `setInterval`.
- A `visibilitychange` listener pauses ticks while the browser tab is hidden; resumes on show.
- `SchedulePanel` starts polling via `useEffect` when the Timeline tab is active and a `workspaceId` is available; stops it on cleanup (tab switch, unmount).
- Interval: **15 seconds** (configurable via `POLL_INTERVAL_MS` constant in `SchedulePanel.tsx`).

### B5 — Master Schedule as Timeline Data Source
- **Where:** `SchedulePanel.tsx`
- The Timeline tab now uses `masterAcquisitions` (derived from `scheduleStore.items`) as its primary data source.
- Falls back to `timelineAcquisitions` (orders-derived) when `scheduleStore.items` is empty (no workspace / first load).

---

## C. Files Changed

| File | Change |
|---|---|
| `frontend/src/store/scheduleStore.ts` | Added `focusedStartTime`, `pollingWorkspaceId`, `pollingIntervalMs`; extended `focusAcquisition` with coord overrides; added `startPolling` / `stopPolling` |
| `frontend/src/store/visStore.ts` | Added `setTimeRangeFromIso`; typed `cameraPosition` as `CameraState` (fix pre-existing `any` warnings) |
| `frontend/src/components/ScheduleTimeline.tsx` | Added `target_lat/lon` to `ScheduledAcquisition`; `satellite` filter; satellite badge on bars; `onViewRangeChange` + `onSelectAcquisition` props |
| `frontend/src/components/SchedulePanel.tsx` | Connected master schedule polling, Cesium timeline sync callbacks, `masterAcquisitions` data source |
| `frontend/src/components/Map/GlobeViewport.tsx` | Added fly-to + clock sync effect reacting to `focusedAcquisitionId` / `focusedTargetCoords` / `focusedStartTime` |

---

## D. Manual Verification Steps

- [ ] **D1** — Open Schedule → Timeline tab: confirm entries show satellite name badge inside each bar.
- [ ] **D2** — Satellite filter chip appears when multiple satellites exist; filtering works.
- [ ] **D3** — Click a pass → Cesium globe flies to target location (~1 200 km altitude); clock cursor jumps to pass start time.
- [ ] **D4** — Zoom in / out on schedule timeline → Cesium clock and `timeWindow` update within ~300 ms.
- [ ] **D5** — Switch to a non-Timeline tab (e.g. Schedule) → polling stops (verify in DevTools Network: no more `/master` requests).
- [ ] **D6** — Switch back to Timeline tab → polling resumes; switch browser tab to background → requests pause; foreground → resumes.
- [ ] **D7** — Apply a new schedule plan → Timeline auto-refreshes within 15 s without page reload.
- [ ] **D8** — No console errors in normal usage.

---

## E. Not in Scope (this PR)

- Full STK playback controls (speed scrubber, event editor).
- Satellite groundtrack visibility toggle per-satellite from schedule.
- Scheduler / algorithm changes.
- Conflict UI or force-commit behaviour changes.
- Target coloring policy changes.
