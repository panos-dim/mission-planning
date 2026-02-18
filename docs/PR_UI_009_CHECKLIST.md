# PR UI 009 — Feasibility Results Cleanup: Date Format & Overview Trim

## Summary

UI-only cleanup to reduce visual noise in Feasibility Results:
- Removed relative/elapsed time indicators (`+Xh`, `-Xm`)
- Standardized all dates to DD-MM-YYYY format
- Trimmed Overview panel (removed opportunities count, mission type, satellite agility, sensor FOV)
- Renamed "Duration" → "Time window"

---

## Before / After Screenshots

> **Instructions**: Capture screenshots of the Feasibility Results right pane and Overview section before and after merging this branch.

| Area | Before | After |
|------|--------|-------|
| Overview metrics row | 3-col grid (Opportunities, Duration, Targets) | 2-col grid (Time window, Targets) |
| Overview config section | Mission Type, Imaging Type, Sensor FOV, Satellite Agility, Max Off-Nadir | Imaging Type, SAR config (if SAR), Max Off-Nadir only |
| Timeline controls bar | Start time + `+Xh` elapsed ... `-Xm` remaining + End time | Start time ... End time (no elapsed/remaining) |
| Opportunity card dates | `DD-MM-YYYY [HH:MM:SS - HH:MM:SS] UTC` | Same DD-MM-YYYY format (already was, now consistent everywhere) |
| Timeline section dates | `YYYY-MM-DD HH:MM` | `DD-MM-YYYY HH:MM UTC` |
| MissionSidebar overview | Mission Type, Duration, Elevation Mask, Total Opportunities | Time window, Elevation Mask (comm only) |
| MissionSidebar schedule | `MM-DD HH:MM UTC` | `DD-MM-YYYY HH:MM UTC` |
| MissionSidebar timeline | `YYYY-MM-DDTHH:MM UTC` | `DD-MM-YYYY HH:MM UTC` |

---

## Date Formatting Confirmation

DD-MM-YYYY format is now applied in the following locations:

| File | Location | Format |
|------|----------|--------|
| `MissionResultsPanel.tsx` | Opportunity card time row | `DD-MM-YYYY [HH:MM:SS - HH:MM:SS] UTC` |
| `MissionResultsPanel.tsx` | Timeline Mission Start/End | `DD-MM-YYYY HH:MM UTC` |
| `MissionResultsPanel.tsx` | Timeline axis labels | `DD-MM HH:MM` |
| `MissionResultsPanel.tsx` | Timeline marker tooltips | `DD-MM HH:MM:SS UTC` |
| `MissionSidebar.tsx` | Overview → Time window | Value only (e.g., `24.0h`) |
| `MissionSidebar.tsx` | Schedule tab → Start/End | `DD-MM-YYYY HH:MM UTC` |
| `MissionSidebar.tsx` | Timeline tab → Start/End Time | `DD-MM-YYYY HH:MM UTC` |
| `MissionSidebar.tsx` | Timeline tab → Pass entries | `DD-MM HH:MM → HH:MM UTC` |
| `utils/date.ts` | Shared helpers | `formatDateDDMMYYYY`, `formatDateTimeDDMMYYYY`, `formatDateTimeShort` |

---

## Manual Verification Steps

1. **Run feasibility analysis** (imaging + SAR modes) and confirm:
   - Overview shows only Time window + Targets in the metrics row (no opportunities count)
   - Overview config shows no "Mission Type", "Sensor FOV", or "Satellite Agility" rows
   - All dates display in DD-MM-YYYY format

2. **Open Timeline section** in MissionResultsPanel and verify:
   - Mission Start/End use `DD-MM-YYYY HH:MM UTC` format
   - Timeline axis labels use `DD-MM HH:MM` format
   - Marker tooltips show `DD-MM HH:MM:SS UTC`

3. **Check Cesium timeline controls** at bottom of map:
   - No `+Xh` elapsed or `-Xm` remaining indicators
   - Start time and end time labels remain visible

4. **Open MissionSidebar** Overview, Schedule, and Timeline tabs:
   - Overview: "Time window" label (not "Duration"), no "Total Opportunities"
   - Schedule: Pass dates use `DD-MM-YYYY HH:MM UTC`
   - Timeline: Start/End times use `DD-MM-YYYY HH:MM UTC`, pass entries show `DD-MM`

5. **Build verification**: Run `npx tsc --noEmit && npx eslint src/ && npx vite build` — all pass without errors.

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/utils/date.ts` | **NEW** — Shared DD-MM-YYYY formatting helpers |
| `frontend/src/components/MissionResultsPanel.tsx` | Overview trimming, date standardization |
| `frontend/src/components/MissionSidebar.tsx` | Overview trimming, date standardization |
| `frontend/src/components/Map/TimelineControls.tsx` | Removed elapsed/remaining indicators |
| `docs/PR_UI_009_CHECKLIST.md` | **NEW** — This checklist |
