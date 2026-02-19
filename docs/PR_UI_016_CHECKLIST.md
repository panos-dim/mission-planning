# PR-UI-016 Checklist — Remove "All" Filter Option & Reverse Default Viewing

**Branch:** `chore/opportunities-filters-remove-all-and-reverse-default-view`
**Baseline:** PR-UI-015 (per-target opportunity naming & post-filter indexing)

---

## 1. Before / After — Filter Controls

### SAR filters (right sidebar, Opportunities section)

| | Control type | Options | Default state |
|---|---|---|---|
| **Before** | Two `<select>` dropdowns | "All Sides" / "Left Only" / "Right Only"; "All Directions" / "Ascending ↑" / "Descending ↓" | `ALL` (global "show everything") |
| **After** | Toggle pill buttons | `Left` `Right`; `Asc ↑` `Desc ↓` | All pills active (white) — nothing hidden |

> Screenshot placeholder — SAR filter pills:
> ![sar-filter-pills-after](screenshots/sar-filter-pills-after.png)

### Timeline target filter (right sidebar, Timeline section)

| | Control type | Options |
|---|---|---|
| **Before** | Pill buttons with leading **All** pill | `All` + per-target pills (`Athens (3)`, `Riyadh (2)`, …) |
| **After** | Per-target pills only | `Athens (3)`, `Riyadh (2)`, … — no `All` pill |

> Screenshot placeholder — timeline target pills:
> ![timeline-target-pills-after](screenshots/timeline-target-pills-after.png)

---

## 2. "Reverse Viewing" — Definition of Implemented Behavior

Two rules define the new filter model:

1. **Exclude-first toggles**: Each filter category (Left/Right, Asc/Desc, per-target) is represented by an individual toggle pill. The pill is active (visible, white text) by default. Clicking it strikes through and dims the pill, hiding all opportunities matching that value. Clicking again restores visibility.

2. **No global "All" equivalent**: There is no button, dropdown option, or shortcut that sets all filters to "show everything" at once. Every visible category is an explicit, individually-controlled inclusion. To see all opportunities, all pills must be individually active.

### State representation

| Filter | State type | Default | Hidden semantics |
|---|---|---|---|
| Look side | `Set<string>` (`hiddenLookSides`) | `new Set()` (empty = nothing hidden) | `hiddenLookSides.has('LEFT')` → Left-side passes excluded |
| Pass direction | `Set<string>` (`hiddenPassDirections`) | `new Set()` (empty = nothing hidden) | `hiddenPassDirections.has('ASCENDING')` → Ascending passes excluded |
| Timeline targets | `Set<string>` (`hiddenTimelineTargets`) | `new Set()` (empty = nothing hidden) | `hiddenTimelineTargets.has('Athens')` → Athens hidden from timeline |

---

## 3. Per-Target Numbering — Confirmation of Post-Filter Rule

Per PR-UI-015, opportunity indices are computed **after** filters are applied, producing contiguous 1, 2, 3… sequences matching exactly what is on screen.

### How it works (unchanged from PR-UI-015)

| Component | Filter application point | Index source |
|---|---|---|
| Opportunity cards | `hiddenLookSides` + `hiddenPassDirections` applied in `passesGroupedByTarget` `useMemo` | `localIndex` from `targetPasses.map()` callback |
| Timeline dots | Same SAR filters + `hiddenTimelineTargets` | `perTargetIndex` assigned after time-sort of filtered `targetPasses` |
| Schedule timeline tooltip | `filters.target` + `filters.lockedOnly` in `ScheduleTimeline.tsx` | `opportunityNames` `useMemo` iterates post-filter `targetLanes` |
| Accepted orders table | None (committed schedule, no runtime filters) | Per-target counter over time-sorted `schedule` array |

> Screenshot placeholder — post-filter numbering with filter active:
> ![post-filter-numbering](screenshots/post-filter-numbering.png)

---

## 4. Files Changed

| File | Changes |
|---|---|
| `frontend/src/components/MissionResultsPanel.tsx` | Replaced `lookSideFilter`/`passDirectionFilter` (`'ALL'\|'LEFT'\|'RIGHT'` single-select) with `hiddenLookSides`/`hiddenPassDirections` (`Set<string>` exclude-first); added `toggleLookSide`/`togglePassDirection` callbacks; replaced `<select>` dropdowns with toggle pill buttons; removed "All" pill from timeline target filter; updated `passesGroupedByTarget` filter logic and dependency array |
| `docs/PR_UI_016_CHECKLIST.md` | This file |

---

## 5. Build / Lint

```
$ npx tsc --noEmit          → exit 0 (zero errors)
$ npx eslint src/components/MissionResultsPanel.tsx → exit 0 (zero warnings)
```

---

## 6. Constraints / Non-goals (hard)

- [x] No backend changes
- [x] No change to opportunity naming / per-target numbering rules (PR-UI-015)
- [x] No timeline popout window
- [x] No additional filters (same categories, just different control style)
- [x] No new "All" equivalent introduced
- [x] Locked indicators and SAR/Optical mode colors unaffected
- [x] CSV export format unchanged

---

## 7. Manual Verification Results

| # | Step | Result |
|---|---|---|
| 1 | Open Opportunities section → SAR filter pills show `Left` `Right` `Asc ↑` `Desc ↓` — no "All" option | ⬜ pending |
| 2 | Open Timeline section → target pills show per-target names only — no "All" pill | ⬜ pending |
| 3 | Toggle `Left` pill off → only Right-side opportunities remain; count updates | ⬜ pending |
| 4 | Toggle `Asc ↑` pill off → only Descending opportunities remain; count updates | ⬜ pending |
| 5 | With filters active → labels show `Athens 1`, `Athens 2`… contiguous, no gaps (post-filter rule) | ⬜ pending |
| 6 | Toggle `Left` pill back on → Left-side opportunities reappear; indices renumber | ⬜ pending |
| 7 | Timeline target pills: toggle a target off → target disappears from timeline; toggle back → reappears | ⬜ pending |
| 8 | Confirm locked indicators (red shield badge) still display on locked items | ⬜ pending |
| 9 | Confirm Optical (cyan `#06b6d4`) / SAR (purple `#a855f7`) mode colors unchanged | ⬜ pending |
| 10 | Timeline dot titles show `{TargetName} {n} — DD-MM HH:MM:SS UTC` format (PR-UI-015) | ⬜ pending |

---

## 8. Screenshots

> Attach before/after screenshots after manual verification:
>
> - [ ] **Before**: SAR filter dropdowns with "All Sides" / "All Directions" options
> - [ ] **After**: SAR filter toggle pills (Left, Right, Asc ↑, Desc ↓)
> - [ ] **Before**: Timeline target pills with leading "All" pill
> - [ ] **After**: Timeline target pills without "All" pill
> - [ ] **Filter test**: Left pill toggled off → only Right opportunities, contiguous numbering
> - [ ] **Filter test**: Asc ↑ pill toggled off → only Descending opportunities, contiguous numbering
> - [ ] **Color check**: Mode colors (cyan/purple) and lock indicators unchanged
