# PR-TIMELINE-UX-01 — Schedule Timeline "Mission Planner Grade" Checklist

## 1. Satellite Grouping

- [x] Toggle at top of Timeline: "Group by satellite" ON by default
- [x] When ON: collapsible sections per satellite showing `SAT-ID (N acquisitions)`
- [x] Each satellite section displays activities grouped by day (same timeline style)
- [x] Only one satellite expanded by default (closest to current time)
- [x] When OFF: unified chronological list grouped by day (previous behavior)

## 2. Quick Filter Chips

- [x] Chip row above timeline (no big sidebar)
- [x] **Satellite chip**: dropdown select, only visible when group-by is OFF
- [x] **Target chip**: dropdown select for filtering by target
- [x] **Locked chip**: toggle, filters to locked-only acquisitions
- [x] **Conflict chip**: toggle, filters to conflict-only acquisitions
- [x] **Time window presets**: `All` | `±6h` | `Today`
- [x] All chips have ✕ Clear action; active chips visually distinguished
- [x] Global "Clear" button appears when any filter is active
- [x] Default view: All + group-by ON (no filters trapped)

## 3. Card Redesign

- [x] Time range in one line: `DD-MM-YYYY [HH:MM:SS–HH:MM:SS] UTC`
- [x] Satellite name + target name on second row with icons
- [x] **LOCKED** badge (red) when `lock_level === "hard"`
- [x] **CONFLICT** badge (yellow) when `has_conflict === true`
- [x] **SAR L/R** badge (purple) when `sar_look_side` present
- [x] Priority dot/badge (red ≥4, yellow ≥2, gray otherwise) when priority > 0
- [x] Mode badge (gray, uppercase) when mode present
- [x] Optional 1-line repair reason (italic, truncated) from repair context
- [x] Duration in minutes shown on right side of time row
- [x] No heavy animations; only `transition-colors` for hover/select states

## 4. Click Behavior Polish

- [x] Clicking card calls `selectAcquisition(id, "timeline")` → opens inspector
- [x] `onFocusAcquisition` callback for Cesium focus integration
- [x] Auto-scroll to selected card (`scrollIntoView({ block: "center" })`)
- [x] `data-acquisition-id` attribute on each card for scroll targeting
- [x] **Jump to Now** button (top right): scrolls to nearest-to-now activity
- [x] Jump to Now auto-expands the satellite group containing the target card
- [ ] Shift+click multi-select (skipped — non-trivial, deferred)

## 5. Performance

- [x] All sub-components wrapped in `React.memo` (TimelineCard, DaySection, SatelliteSection, FilterChips)
- [x] All grouping/filtering data structures memoized with `useMemo`
- [x] All callbacks stabilized with `useCallback`
- [x] CSS `content-visibility: auto` on DaySection for native browser-level virtualization
- [x] Collapsed satellite groups render zero cards (inherent perf gate)
- [x] No re-sorting/re-grouping on every render; derived data cached
- [x] Estimated capacity: 500–2000 activities smooth (memo'd cards + collapsed groups + content-visibility)

## 6. Empty / Edge States

- [x] No acquisitions at all: "No committed schedule yet" with Clock icon + guidance text
- [x] Filters hide all: "No activities match filters" + **Clear Filters** button
- [x] Summary footer shows `filtered / total acquisitions` + locked/conflict counts

## 7. Constraints Verified

- [x] No new routes or panels created
- [x] No new backend endpoints required
- [x] Simple Mode surface unchanged (Timeline is inside Schedule → Timeline tab only)
- [x] Scheduling logic untouched
- [x] `ScheduledAcquisition` interface extended with optional fields only (backward-compatible)

## Files Changed

| File                                            | Change                                                         |
|-------------------------------------------------|----------------------------------------------------------------|
| `frontend/src/components/ScheduleTimeline.tsx`  | Complete rewrite: grouping, filters, cards, click polish, perf |
| `docs/PR_TIMELINE_UX_01_CHECKLIST.md`           | This checklist                                                 |

## Notes

- `SchedulePanel.tsx` unchanged — new optional fields (`priority`, `sar_look_side`, `repair_reason`) degrade gracefully when absent
- SAR look_side / priority badges will display once upstream data sources (schedule horizon API, repair reports) populate those fields
- TypeScript compiles cleanly (`tsc --noEmit` passes)
