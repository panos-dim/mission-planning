# PR-UI-015 Checklist — Opportunity Naming "{TargetName} 1/2/3" & Satellite Color Removal

**Branch:** `feat/opportunities-naming-athens-1-2-3-and-remove-satellite-colors`
**Baseline:** PR-UI-014 (schedule start-time only & DD-MM-YYYY format)

---

## 1. Before / After — Opportunity Naming

### Right sidebar opportunity cards (`MissionResultsPanel.tsx`)

| | Label format | Code |
|---|---|---|
| **Before** | `SAR Opportunity 7` / `Imaging Opportunity 12` (global sequential) | `{pass.sar_data ? 'SAR' : 'Imaging'} Opportunity {globalIndex + 1}` |
| **After** | `Athens 1`, `Athens 2`, `Riyadh 1` (per-target chronological) | `{targetName} {localIndex + 1}` |

> Screenshot placeholder — opportunities list showing "Athens 1 / 2 / 3":
> ![sidebar-after](screenshots/sidebar-after.png)

### Timeline dot titles (`MissionResultsPanel.tsx`)

| | Title format | Code |
|---|---|---|
| **Before** | `#7 Athens — 05-02 14:23:05 UTC` | `` `#${globalIndex + 1} ${pass.target} — …` `` |
| **After** | `Athens 1 — 05-02 14:23:05 UTC` | `` `${pass.target} ${perTargetIndex} — …` `` |

### Schedule timeline tooltip (`ScheduleTimeline.tsx`)

| | Tooltip content |
|---|---|
| **Before** | Start time, target, satellite, mode, lock — no name header |
| **After** | Bold **Athens 3** header above existing fields |

New fields added: `opportunityName: string` in `TooltipData`; bold `<div>` header in `AcquisitionTooltip`.

> Screenshot placeholder — timeline tooltip with opportunity name:
> ![timeline-tooltip-after](screenshots/timeline-tooltip-after.png)

### Accepted orders table (`AcceptedOrders.tsx`)

| | First column |
|---|---|
| **Before** | `#` (1, 2, 3 — global sequential) + separate `Target` column |
| **After** | `Opportunity` column: `Athens 1`, `Athens 2`, `Riyadh 1` (per-target chronological) |

> Screenshot placeholder — accepted orders table:
> ![orders-table-after](screenshots/orders-table-after.png)

---

## 2. Numbering Rule — Post-filter + Rationale

**Chosen rule: indices are computed _after_ filters are applied.**

### Why post-filter

- **User mental model**: When a filter hides half the opportunities, seeing "Athens 1, 3, 7" with gaps is confusing. Post-filter numbering always shows a contiguous 1, 2, 3… sequence matching exactly what is on screen.
- **Simplest implementation**: Each component already iterates only the filtered set. The `localIndex` / `perTargetIndex` is the natural loop index — no extra lookup table or pre-filter pass required.
- **No persistence dependency**: Indices are ephemeral display labels, not IDs. Changing filters re-numbers immediately, which is the expected behavior for a view-layer label.

### How it works per component

| Component | Filter mechanism | Index source |
|---|---|---|
| `MissionResultsPanel.tsx` — cards | `lookSideFilter` + `passDirectionFilter` applied before grouping in `passesGroupedByTarget` | `localIndex` from `targetPasses.map()` callback |
| `MissionResultsPanel.tsx` — timeline dots | `hiddenTimelineTargets` + same SAR filters | `perTargetIndex` assigned after time-sort of filtered `targetPasses` |
| `ScheduleTimeline.tsx` — tooltip | `filters.target` + `filters.lockedOnly` applied to build `targetLanes` | `opportunityNames` `useMemo` iterates post-filter `targetLanes` |
| `AcceptedOrders.tsx` — table | None (committed schedule, no runtime filters) | Per-target counter over time-sorted `schedule` array |

---

## 3. Satellite Color Mapping — Confirmation of Removal

Satellite-specific color coding was removed from opportunity/timeline rendering in **PR-UI-013**. This PR confirms no satellite colors are used in the changed surfaces.

### Files where satellite color is NOT used for opportunities

| File | Lines | What's there instead |
|---|---|---|
| `MissionResultsPanel.tsx` | L51–54 `getOpportunityColor()` | Returns `#a855f7` (purple) for SAR, `#06b6d4` (cyan) for Optical — mode-only |
| `ScheduleTimeline.tsx` | L473–475 `barColor` | `bg-purple-500/70` for SAR, `bg-cyan-500/70` for Optical — mode-only |
| `ScheduleTimeline.tsx` | L598–605 `laneColors` | All lanes `#22c55e` (green-500, acquired status) — no satellite mapping |
| `ScheduleTimeline.tsx` | L748–767 legend | Optical / SAR / Locked entries only — no satellite color legend |

### Files where satellite palette still exists (not in scope)

| File | Reason retained |
|---|---|
| `frontend/src/constants/colors.ts` | `SATELLITE_COLOR_PALETTE` and `getSatelliteColorByIndex()` are used by `Inspector.tsx` and `GlobeViewport` for non-opportunity satellite visualization (orbit lines, etc.). Removing them is a separate scope. |

---

## 4. Files Changed

| File | Changes |
|---|---|
| `frontend/src/components/MissionResultsPanel.tsx` | Card title → `{targetName} {localIndex+1}`; timeline dot title → `{target} {perTargetIndex}`; replaced `globalIndex` with `perTargetIndex` in `markerData` |
| `frontend/src/components/ScheduleTimeline.tsx` | Added `opportunityName` field to `TooltipData`; bold name header in `AcquisitionTooltip`; `opportunityNames` prop on `TargetLaneProps`; `opportunityNames` `useMemo`; wired prop through to `TargetLane` |
| `frontend/src/components/AcceptedOrders.tsx` | Replaced `#`+`Target` columns with single `Opportunity` column; per-target naming via time-sorted counter IIFE |
| `docs/PR_UI_015_CHECKLIST.md` | This file |

---

## 5. Build / Lint

```
$ npx tsc --noEmit          → exit 0 (zero errors)
$ npx eslint <changed files> → exit 0 (zero warnings)
```

---

## 6. Constraints / Non-goals

- [x] No backend changes
- [x] No changes to feasibility computations or API payloads
- [x] No changes to lock mechanics
- [x] No changes to schedule start-only display / date formatting (PR-UI-014)
- [x] No timeline popout window
- [x] CSV export retains original `#` + `Target` columns (data export format, not UI)

---

## 7. Manual Verification Results

| # | Step | Result |
|---|---|---|
| 1 | Run feasibility with multiple Athens opportunities → labels show "Athens 1", "Athens 2", "Athens 3" | ⬜ pending |
| 2 | Apply SAR look-side filter → numbering renumbers from 1 with no gaps (post-filter rule) | ⬜ pending |
| 3 | Apply pass direction filter → same contiguous renumbering | ⬜ pending |
| 4 | Confirm no satellite color legend or per-satellite colored bars remain | ⬜ pending |
| 5 | Confirm locked items show lock cues (red shield badge) | ⬜ pending |
| 6 | Confirm Optical (cyan) / SAR (purple) mode colors remain on bars and cards | ⬜ pending |
| 7 | Hover timeline dot → title shows `{TargetName} {n} — DD-MM HH:MM:SS UTC` | ⬜ pending |
| 8 | Hover schedule bar → tooltip shows bold opportunity name header | ⬜ pending |
| 9 | Open committed orders → table shows `Opportunity` column with per-target naming | ⬜ pending |

---

## 8. Screenshots

> Attach before/after screenshots after manual verification:
>
> - [ ] **Before**: Opportunity card with old `SAR Opportunity {n}` label
> - [ ] **After**: Opportunity card with `{TargetName} {n}` label
> - [ ] **Before**: Timeline without opportunity name in tooltip
> - [ ] **After**: Timeline tooltip with bold opportunity name header
> - [ ] **Filter test**: SAR look-side filter active → contiguous renumbered indices
> - [ ] **Color check**: Timeline bars showing only mode colors (cyan/purple), no satellite palette
