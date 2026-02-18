# PR-UI-006: Timeline Realism v1 — Time Axis & Rich Hover

## Summary

Replaced the card-stack timeline with a real time-axis timeline featuring:
- Horizontal time axis with proportional placement of acquisition bars
- Per-target swim lanes for multi-target readability
- Rich hover tooltips showing date/time + full opportunity details
- Removed duplicated opportunity card list from the timeline area

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/components/ScheduleTimeline.tsx` | Full rewrite: card-stack → time-axis timeline with lanes, tooltips, legend |
| `frontend/src/components/SchedulePanel.tsx` | Pass `missionStartTime`/`missionEndTime` props to `ScheduleTimeline` |

## Lane Strategy

- **Grouping**: Per-target lanes (one horizontal lane per unique `target_id`)
- **Sorting**: Lanes sorted alphabetically by target ID
- **Color**: Each lane gets a left-border accent from an 8-color palette
- **Bars**: Acquisition bars positioned proportionally by `start_time`/`end_time` within the time axis range
- **Min width**: Bars have a minimum width of 4px to remain clickable even for very short passes

## Tooltip Content Checklist

| Field | Shown | Source |
|-------|-------|--------|
| Start datetime (UTC) | ✅ | `acquisition.start_time` |
| End datetime (UTC) | ✅ | `acquisition.end_time` |
| Duration (minutes) | ✅ | Computed from start/end |
| Target name/ID | ✅ | `acquisition.target_id` |
| Satellite name/ID | ✅ | `acquisition.satellite_id` |
| Mode (SAR/Optical) | ✅ | `acquisition.mode` |
| SAR Look Side | ✅ (if SAR) | `acquisition.sar_look_side` |
| Priority | ✅ (if > 0) | `acquisition.priority` |
| Lock status | ✅ (if locked) | `acquisition.lock_level` |
| Repair reason | ✅ (if present) | `acquisition.repair_reason` |

## Visual Differentiation

- **Optical**: Cyan bars (`bg-cyan-500/70`)
- **SAR**: Purple bars (`bg-purple-500/70`)
- **Locked**: Red border + red dot with shield icon
- **Selected**: Blue ring highlight

## Time Axis

- Axis uses mission time window (`MissionData.start_time`/`end_time`) when available, otherwise derives from acquisition data
- Nice tick steps: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 24h (auto-selected based on range)
- Date labels shown on first tick and when day changes
- Faint vertical grid lines aligned with ticks

## Manual Test Results

### 1. Single-target timeline
- [ ] Run feasibility with 1 target
- [ ] Confirm bars appear with correct start/end placement
- [ ] Confirm single lane renders with target label
- [ ] Screenshot: _(attach here)_

### 2. Multi-target timeline (lanes)
- [ ] Run feasibility with 2+ targets
- [ ] Confirm multiple lanes render, each labeled
- [ ] Confirm lanes are visually separated and readable
- [ ] Screenshot: _(attach here)_

### 3. SAR segment hover
- [ ] Hover a SAR acquisition bar
- [ ] Tooltip shows: start/end times, target, satellite, "SAR" mode, look side
- [ ] Screenshot: _(attach here)_

### 4. Optical segment hover
- [ ] Hover an Optical acquisition bar
- [ ] Tooltip shows: start/end times, target, satellite, "Optical" mode
- [ ] Screenshot: _(attach here)_

### 5. No duplication with right sidebar
- [ ] Confirm right sidebar Opportunities list still exists independently
- [ ] Confirm timeline area shows only the time-axis view (no card list)

### 6. Filters
- [ ] Satellite filter works (multi-satellite missions)
- [ ] Target filter works
- [ ] Locked-only filter works
- [ ] Clear filters restores full view

### 7. Lock toggle
- [ ] Double-click a bar to toggle lock
- [ ] Red dot + border appears on locked bars
- [ ] Tooltip shows "Hard Locked" for locked acquisitions

### 8. Build verification
- [x] `npx tsc --noEmit` passes (zero errors)
- [x] `npx vite build` succeeds
