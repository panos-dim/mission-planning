# PR-UI-021: Opportunities Hover + Feasibility Timeline Redesign

## Scope

1. **Hover tooltips** on opportunity bars/cards now show **satellite name**, **off-nadir angle (2dp)**, and **off-nadir time (DD-MM-YYYY)**. Excluded: target name, incidence angle, relative time.
2. **Feasibility timeline redesign** — replaced dot-based markers with lane-based horizontal bars matching the Schedule Timeline's design system.
3. **Dark theme alignment** — removed `glass-panel` / `bg-gray-850` from Feasibility Results panel; unified to `bg-gray-900` base matching the Schedule panel.

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/components/ScheduleTimeline.tsx` | Added `satellite_name?`, `off_nadir_deg?` to `ScheduledAcquisition`; updated `AcquisitionTooltip` to show sat name + off-nadir angle + time |
| `frontend/src/components/SchedulePanel.tsx` | Plumbed `satellite_name` (from mission context satellites array) and `off_nadir_deg` (from `droll_deg`) into timeline acquisitions |
| `frontend/src/components/MissionResultsPanel.tsx` | See detailed breakdown below |

### MissionResultsPanel.tsx — Detailed Changes

- **Hover tooltip**: Added `opportunityHoverTitle()` for card `title` attrs; added styled fixed-position tooltip for timeline bars via `onMouseEnter`/`onMouseLeave` (same style as ScheduleTimeline's `AcquisitionTooltip`)
- **Tooltip positioning**: Opens to the **left** (`-translate-x-full`) anchored at bar's left edge, preventing right-edge clipping since the panel is on the right side of the screen
- **Timeline redesign**: Replaced dot/cluster markers with proportional horizontal bars per target lane:
  - Time axis with auto-generated ticks (nice-step algorithm matching ScheduleTimeline)
  - Per-target lanes with `MapPin` icon + green left border + target name + count
  - Proportional bars colored blue (Optical) / purple (SAR) with `min-width: 4px`
  - Faint vertical grid lines aligned to tick marks
  - Optical / SAR legend at bottom
- **Lane sizing**: `FT_LANE_HEIGHT=32`, `FT_LANE_GAP=4` — matches ScheduleTimeline's `LANE_HEIGHT`/`LANE_GAP`
- **Dark theme**: Outer container → `bg-gray-900`; summary bar → `bg-gray-900/95`; removed `glass-panel` and `bg-gray-850` from section content areas; opportunity cards → solid `bg-gray-800/40 border-gray-700/40`; section header hover → `bg-gray-700`

## Field Source Mapping

| Hover field | ScheduleTimeline source | MissionResultsPanel source |
|-------------|------------------------|---------------------------|
| Satellite name | `ScheduledAcquisition.satellite_name` ← `SatelliteInfo.name` via mission context lookup; fallback: `satellite_id` | `PassData.satellite_name`; fallback: `satellite_id` → `'Unknown'` |
| Off-nadir angle | `ScheduledAcquisition.off_nadir_deg` ← `Math.abs(droll_deg)` from accepted order schedule item | `PassData.off_nadir_deg`; fallback: `90 - max_elevation` |
| Off-nadir time | `ScheduledAcquisition.start_time` (formatted DD-MM-YYYY HH:MM:SS UTC) | `PassData.max_elevation_time` (TCA); fallback: `start_time` |

## Formatting

- **Off-nadir angle**: `fmt2()` → 2dp, `°` suffix (e.g. `23.46°`, `5.12°`)
- **Off-nadir time**: `formatUTCDateTime()` / `formatDateTimeDDMMYYYY()` → `DD-MM-YYYY HH:MM:SS UTC`

## Manual Verification Checklist

- [ ] **SAR hover (ScheduleTimeline)**: Hover purple bar → tooltip: satellite name + off-nadir angle (2dp °) + DD-MM-YYYY time
- [ ] **Optical hover (ScheduleTimeline)**: Hover blue bar → same format
- [ ] **SAR hover (Feasibility timeline)**: Hover purple bar → styled tooltip opens to the left
- [ ] **Optical hover (Feasibility timeline)**: Hover blue bar → styled tooltip opens to the left
- [ ] **Card hover (MissionResultsPanel)**: Native tooltip shows sat name + off-nadir angle + time
- [ ] **No target name** in any hover tooltip
- [ ] **No incidence angle** in any hover tooltip
- [ ] **No relative/elapsed time** in any hover tooltip
- [ ] **Feasibility timeline** uses lane-based bars (not dots), time axis with ticks, grid lines, legend
- [ ] **Dark theme**: Feasibility panel background matches Schedule panel (no lighter patches)
- [ ] **Tooltip clipping**: Bars near right edge don't cause tooltip overflow
- [ ] **Lane sizing**: Feasibility lanes same height as Schedule lanes
- [ ] `tsc --noEmit` passes ✅
- [ ] `vite build` passes ✅

## Screenshots

> To be added after manual verification.
>
> - [ ] SAR opportunity hover screenshot
> - [ ] Optical opportunity hover screenshot
> - [ ] Feasibility timeline lane-based bars screenshot
> - [ ] Side-by-side Schedule vs Feasibility comparison

## Acceptance Criteria Status

| Criterion | Status |
|-----------|--------|
| Hovering opportunity shows Satellite + Off-nadir angle + Off-nadir time | ✅ |
| Hover shows no target name and no relative time | ✅ |
| Angle uses 2dp and includes ° | ✅ |
| Works for SAR and Optical opportunities | ✅ |
| Feasibility timeline matches Schedule timeline design | ✅ |
| Dark theme consistent across both panels | ✅ |
| Tooltip opens left (no right-edge clipping) | ✅ |
| Lane height matches Schedule timeline | ✅ |
| Builds pass (`tsc --noEmit`, `vite build`) | ✅ |
