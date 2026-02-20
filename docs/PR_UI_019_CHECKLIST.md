# PR-UI-019 — UI Quick Fixes: Mission Params, Feasibility Panel, Formatting & Exports

## Overview

Batch of quick, low-risk UI fixes: simplify Mission Parameters layout, streamline
Feasibility Results panel (remove Overview section, remove JSON export, add targets
summary bar), enforce ≤2dp numeric formatting, and clean up export icons/buttons.
No backend changes.

## Changes

### A) Mission Parameters

| Change | File |
|--------|------|
| Removed "Summary" glass-panel box | `MissionParameters.tsx` |
| Start + End time inputs on same row (`flex-wrap`, `min-w-[180px]`) | `MissionParameters.tsx` |
| Removed dead code (`calculateDuration`, `durationHours`) | `MissionParameters.tsx` |

### B) Feasibility Results Panel

| Change | File |
|--------|------|
| **Removed Overview section entirely** (collapsible header + body) | `MissionResultsPanel.tsx` |
| **Removed JSON export button** and `downloadJSON` function | `MissionResultsPanel.tsx` |
| **Added targets summary bar** at top: `10/10 targets · ICEYE-X44` (left-aligned, green when all covered) | `MissionResultsPanel.tsx` |
| Removed unused imports (`Activity`, `Download`) | `MissionResultsPanel.tsx` |

### C) Planning Panel (Left Side)

| Change | File |
|--------|------|
| Removed "X targets · Y opportunities" status bar (only shows prompt when no data) | `MissionPlanning.tsx` |
| Removed unused `uniqueTargets` variable | `MissionPlanning.tsx` |

### D) Number Formatting

Created `frontend/src/utils/format.ts` with `fmt2(n)` helper:

- Up to 2 decimal places, trailing zeros stripped: `45` → `"45"`, `45.1` → `"45.1"`, `45.126` → `"45.13"`
- Returns `"–"` for null/undefined/NaN

| Numeric field | Component |
|---------------|-----------|
| Incidence center/near/far (°) | `MissionResultsPanel` opportunity cards |
| Swath width (km) | `MissionResultsPanel` opportunity cards |
| Off-nadir angle (°) | `MissionResultsPanel` opportunity cards |
| Elevation mask (°) | `MissionSidebar` overview |
| Target lat/lon (°) | `MissionSidebar` targets |
| Max elevation (°) | `MissionSidebar` schedule + summary |

Integer counts/IDs intentionally not converted.

### E) Export UI Cleanup

| Change | File |
|--------|------|
| Removed CSV export button + `downloadCSV` function | `MissionResultsPanel.tsx` |
| Removed CSV export button + `downloadCSV` function | `MissionSidebar.tsx` |
| Replaced `List` icon → `Download` for JSON export | `MissionSidebar.tsx` |
| `MissionPlanning.tsx` / `PlanningResults.tsx` exports already use `Download` icon | No change needed |

## Files Changed

- **`frontend/src/utils/format.ts`** — NEW (`fmt2` helper)
- **`frontend/src/components/MissionParameters.tsx`** — Summary removed, start/end same row
- **`frontend/src/components/MissionResultsPanel.tsx`** — Overview removed, JSON export removed, targets bar added, `fmt2` applied
- **`frontend/src/components/MissionPlanning.tsx`** — Status bar simplified
- **`frontend/src/components/MissionSidebar.tsx`** — CSV export removed, icon swap, `fmt2` applied

## Non-Goals

- No map color rule changes
- No opportunity hover content changes
- No visualization/path/roll changes
- No Apply button styling work
- No backend changes

## Verification

| Step | Result |
|------|--------|
| Mission Parameters: summary box removed, start/end on same row | ✅ |
| Feasibility Results: Overview section gone, only Opportunities + Timeline remain | ✅ |
| Feasibility Results: targets summary bar shows `X/X targets · satellite` at top | ✅ |
| Feasibility Results: no JSON export button | ✅ |
| Planning panel: no "X targets · Y opportunities" text | ✅ |
| Numeric fields: ≤2dp, no trailing zeros (e.g. `45°` not `45.00°`) | ✅ |
| No CSV export buttons in Feasibility Results or MissionSidebar | ✅ |
| All remaining export icons are `Download` arrows | ✅ |
| `tsc --noEmit` passes | ✅ |
| `vite build` passes | ✅ |
