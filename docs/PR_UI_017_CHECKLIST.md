# PR-UI-017: Timeline Hover — Off-Nadir Exact Time (DD-MM-YYYY), No Name

## Tooltip Rule Checklist

| Rule | Status |
|------|--------|
| Hover shows **only** the off-nadir timestamp | ✅ |
| Format: `DD-MM-YYYY HH:mm:ss UTC` | ✅ |
| No target name in hover | ✅ |
| No incidence angle in hover | ✅ |
| No start/end window range in hover | ✅ |
| No duration in hover | ✅ |
| No relative/elapsed time (e.g. "+6h") in hover | ✅ |

## Field Source

| Component | Off-Nadir Time Field | Fallback |
|-----------|---------------------|----------|
| **MissionResultsPanel** (Opportunities timeline dots) | `PassData.max_elevation_time` (TCA — Time of Closest Approach) | `PassData.start_time` |
| **ScheduleTimeline** (Committed schedule bars) | N/A — `ScheduledAcquisition` lacks `max_elevation_time` | `ScheduledAcquisition.start_time` |

### Why `max_elevation_time` = off-nadir time

`max_elevation_time` is the TCA (Time of Closest Approach), the moment during a pass when
the satellite reaches maximum elevation above the target — which corresponds to the minimum
off-nadir angle. This is the single "off-nadir time" reference for each opportunity.

### Fallback Rule

- **Opportunities timeline** (`MissionResultsPanel.tsx`): Uses `pass.max_elevation_time`.
  Falls back to `pass.start_time` only if `max_elevation_time` is falsy (undefined/empty).
- **Schedule timeline** (`ScheduleTimeline.tsx`): Always uses `acquisition.start_time` because
  the `ScheduledAcquisition` type does not carry `max_elevation_time`. This is documented and
  acceptable — the committed schedule tooltip is not the primary Opportunities timeline.

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/components/MissionResultsPanel.tsx` | Timeline dot `title` → `formatDateTimeDDMMYYYY(pass.max_elevation_time \|\| pass.start_time)`. Removed target name + per-target index from tooltip. Removed unused `perTargetIndex` field from marker data. |
| `frontend/src/components/ScheduleTimeline.tsx` | `AcquisitionTooltip` → shows only `start_time` in `DD-MM-YYYY HH:mm:ss UTC` format. Removed target, satellite, mode, look side, priority, lock, repair from tooltip. Updated `formatUTCDateTime` to include seconds. |
| `frontend/src/utils/date.ts` | No changes needed — `formatDateTimeDDMMYYYY` already outputs `DD-MM-YYYY HH:mm:ss UTC`. |
| `frontend/src/types/index.ts` | No changes — `PassData.max_elevation_time` already exists. |

## Non-Regressions

| Prior PR | Scope | Verified |
|----------|-------|----------|
| PR-UI-016 | Filters model | ✅ Not touched — SAR filter chips in MissionResultsPanel unchanged |
| PR-UI-015 | Per-target naming/indexing | ✅ Not touched — opportunity card naming (`{target} {n}`) unchanged |
| PR-UI-014 | Schedule start-only display | ✅ Not touched — only tooltip content changed, not card layout |

## Manual Verification Steps

1. **Hover SAR opportunity dot** → tooltip shows off-nadir timestamp only in `DD-MM-YYYY HH:mm:ss UTC` format
2. **Hover Optical opportunity dot** → same behavior (uses `max_elevation_time`, fallback `start_time`)
3. **Confirm no target name** in any hover tooltip
4. **Confirm no other metadata** (no incidence angle, no duration, no relative time)
5. **SAR filters** (PR-UI-016) still work — Left/Right/Asc/Desc toggle chips unchanged
6. **Opportunity card naming** (PR-UI-015) still shows `{TargetName} {n}` in card headers
7. **Schedule timeline tooltip** shows only timestamp (fallback: start_time)

## Screenshots

> _To be captured during manual QA_
>
> - [ ] SAR opportunity hover
> - [ ] Optical opportunity hover
> - [ ] Schedule timeline bar hover
