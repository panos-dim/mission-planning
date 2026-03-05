# PR-UI-039: Inspector Acquisitions & Schedule Click-to-Target

## Summary

Added an **Acquisitions** section to the Inspector right panel for selected targets, and wired schedule timeline clicks to drive target selection so the Inspector updates instantly.

## Changes

### A) Inspector — Acquisitions Section (`Inspector.tsx`)

- New `TargetAcquisitionsSection` component renders a chronological list of acquisitions for the selected target.
- Each row shows: **start time** (DD-MM-YYYY HH:mm:ss UTC), **satellite name** (display name or ID fallback), **off-nadir angle** (1 dp with `°`).
- Empty state: "No scheduled acquisitions in current window".
- Data source: unified `acquisitionRows` — prefers `scheduleStore.items`, falls back to orders-derived rows.
- Available in both unified-selection path and tree-based `TargetInspector`.

### B) Schedule Click → Target Selection (`ScheduleTimeline.tsx`)

- `handleSelectAcquisition` now calls `selectTarget(target_id, 'timeline')` instead of `selectAcquisition(id, 'timeline')`.
- Inspector opens with the target view (including acquisitions list) rather than the acquisition view.
- Bar highlight uses `activeBarId` derived from `selectedAcquisitionId`, with `focusedAcquisitionId` fallback only when `lastSelectionSource === 'timeline'` (prevents stale highlights).
- Polling cleanup effect added for `focusedAcquisitionId` to clear stale target selection.

## Data Sources

| Field           | Primary source                            | Orders fallback                       |
| --------------- | ----------------------------------------- | ------------------------------------- |
| `target_id`     | `MasterScheduleItem.target_id`            | `order.schedule[].target_id`          |
| `start_time`    | `MasterScheduleItem.start_time`           | `order.schedule[].start_time`         |
| Satellite name  | `satellite_display_name` ‖ `satellite_id` | `satelliteNameMap` ‖ `satellite_id`   |
| Off-nadir angle | `off_nadir_deg`                           | `abs(droll_deg)` with `isFinite` guard |
| Coordinates     | `missionData.targets` ‖ `schedItem`       | `order.target_positions`              |

## Bug Fixes (post-audit)

1. **Location NaN**: Unified target view always rendered `CoordinateField` even when coordinates were undefined → NaN. Fixed with `!= null` guard.
2. **Acquisitions showed 0**: `scheduleStore.items` was empty when timeline used orders fallback. Fixed by computing `acquisitionRows` from both sources.
3. **Raw satellite ID**: Orders fallback showed `satellite_id` instead of display name. Fixed by building `satelliteNameMap` from `missionData.satellites`.
4. **off_nadir NaN**: `Math.abs(undefined)` → NaN passed `!= null` check. Fixed with `Number.isFinite()` guard.
5. **Tree TargetInspector missing acquisitions**: Threaded `acquisitionRows` through `renderInspectorContent` → `TargetInspector`.
6. **Stale bar highlight**: `focusedAcquisitionId` persisted when switching from timeline to map/tree selection. Fixed by gating on `lastSelectionSource === 'timeline'`.

## Verification Steps

- [ ] Apply schedule with multiple targets → select target → acquisitions list appears ordered by time
- [ ] Select target with no acquisitions → empty state message shown
- [ ] Click pass in schedule timeline → Inspector switches to target and shows acquisitions list
- [ ] Select target from explorer tree → acquisitions list also appears
- [ ] Bar highlight follows timeline click, clears on map/tree selection
- [ ] Bar highlight follows cross-view click from `ScheduledAcquisitionsList` (via `selectedAcquisitionId`)
- [ ] Satellite names resolve to display names (not raw IDs)
- [ ] Location section hidden when coordinates unavailable (no NaN)
- [ ] `npx tsc --noEmit` passes
- [ ] `npx eslint` passes on changed files

## Files Changed

- `frontend/src/components/ObjectExplorer/Inspector.tsx` — `TargetAcquisitionsSection`, unified `acquisitionRows` with orders fallback, `satelliteNameMap`, Location NaN guard, tree-based `TargetInspector` threading
- `frontend/src/components/ScheduleTimeline.tsx` — `selectTarget` wiring, `activeBarId` with `lastSelectionSource` gate, polling cleanup
