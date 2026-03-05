# PR-UI-035: Schedule Master View Polish — Checklist

**Branch:** `chore/schedule-master-view-polish-selection-locks-and-clean-ui`
**Scope:** Selection polish, sticky time axis, lock indicator parity, visual noise reduction.
No backend changes. No algorithm changes. PR-UI-034 slicing/caching logic untouched.

---

## Changes implemented

### A) Schedule timeline → Cesium selection polish

**Files:** `ScheduleTimeline.tsx`, `scheduleStore.ts`, `SchedulePanel.tsx`, `ScheduledAcquisitionsList.tsx`

| # | Change | Where |
|---|--------|--------|
| A1 | **Scroll-into-view** when selection changes: `trackRef.current.querySelector([data-acquisition-id=…]).scrollIntoView({ behavior: 'smooth', block: 'nearest' })` with 60 ms debounce | `ScheduleTimeline.tsx` |
| A2 | **Selection persistence across polling**: `useEffect` checks if `selectedAcquisitionId` is still in `acquisitions`; calls `selectAcquisition(null)` if not | `ScheduleTimeline.tsx` |
| A3 | **scheduleStore persistence**: `fetchMaster/success` checks `focusedAcquisitionId` against new items; spreads `staleFields` (null-outs all 4 focus fields) if acquisition was removed | `scheduleStore.ts` |
| A4 | **SchedulePanel bridge**: `useEffect` after `masterAcquisitions` memo clears both `focusAcquisition(null)` and `clearAcquisitionSelection(null)` when polled item is gone | `SchedulePanel.tsx` |
| A5 | **Stronger selected ring**: `ring-2 ring-white ring-offset-1 ring-offset-blue-600 z-10` — white ring is unambiguous at high density regardless of bar colour; `z-10` lifts bar above neighbours | `ScheduleTimeline.tsx` (TargetLane) |
| A6 | **Cross-view focus sync in list**: `ScheduledAcquisitionsList` subscribes to `selectedAcquisitionId` from `selectionStore`; auto-expands satellite group and scrolls `focusedItemRef` into view | `ScheduledAcquisitionsList.tsx` |
| A7 | **Click → selectAcquisition**: row click now calls `selectAcquisitionInStore(id, 'table')` before the prop callback | `ScheduledAcquisitionsList.tsx` |

### B) Freeze schedule list header / no layout jitter

**Files:** `ScheduleTimeline.tsx`

| # | Change | Where |
|---|--------|--------|
| B1 | **Sticky time axis**: `TimeAxis` wrapped in `<div className="sticky top-0 z-20 bg-gray-900 pb-px">` so it stays visible while lanes scroll | `ScheduleTimeline.tsx` |
| B2 | **Preserve user zoom across polls**: `userHasAdjustedViewRef` flag; `setViewRange` in the `useEffect([minTs, maxTs])` is skipped once user has zoomed/panned. `resetZoom` clears the flag. Pan (`handleMouseDown`) and zoom (`zoomAt`) both set it | `ScheduleTimeline.tsx` |

### C) Lock/unlock indicator parity

**Files:** `ScheduleTimeline.tsx`, `ScheduleSatelliteLayers.tsx`

| # | Change | Where |
|---|--------|--------|
| C1 | **Lock indicator on timeline bar**: changed from `rounded-full -top-1 -right-1` (clips on narrow bars) to `rounded-sm top-0.5 right-0.5 size-3.5 z-10` — always visible inside the bar bounds | `ScheduleTimeline.tsx` (TargetLane) |
| C2 | **Legend updated** to match new `rounded-sm` indicator shape | `ScheduleTimeline.tsx` |
| C3 | **Lock badge on map overlay**: `ScheduleSatelliteLayers` imports `useLockStore`; `SatRow` accepts `isLocked` prop; focused satellite row shows `<Shield>` in red when focused acquisition is hard-locked | `ScheduleSatelliteLayers.tsx` |
| C4 | **Lock row styling in list**: focused acquisition row uses `bg-blue-900/40 border-blue-400 ring-1 ring-blue-400/40` (distinct from conflict highlight in orange and bulk-select in `bg-blue-900/20`) | `ScheduledAcquisitionsList.tsx` |

### D) Reduce visual noise

| # | Finding | Action |
|---|---------|--------|
| D1 | `SchedulePanel.tsx` — no unguarded dev output | No change needed |
| D2 | `ScheduleTimeline.tsx` — summary footer shows operational counts only | No change needed |
| D3 | `ScheduleSatelliteLayers.tsx` — dev sample-step selector + debug stats already guarded by `import.meta.env.DEV` | Confirmed, no change |
| D4 | Numeric formatting: `AcquisitionTooltip` uses `fmt1(off_nadir_deg)` (1 dp) ✓; no unformatted floats in production UI | Verified correct |

---

## Acceptance criteria verification

| Step | Criterion | Status |
|------|-----------|--------|
| 1 | Click a pass → selection highlights (white ring + z-10), Cesium focuses, item scrolls into view | ✅ A1, A5 |
| 2 | Let polling refresh occur → selection persists if item exists; cleared gracefully if removed | ✅ A2, A3, A4 |
| 3 | Scroll a long schedule → time axis stays fixed at top; zoom/pan not reset by polling | ✅ B1, B2 |
| 4 | Lock icons clearly visible on bars (inside bounds, no clipping); lock state shown on map overlay for focused acquisition | ✅ C1, C3 |
| 5 | Build passes, no TypeScript errors | ✅ `npm run build` exit 0 |

---

## Files changed

```
frontend/src/store/scheduleStore.ts                    — A3
frontend/src/components/SchedulePanel.tsx              — A4 (import selectionStore)
frontend/src/components/ScheduleTimeline.tsx           — A1 A2 A5 B1 B2 C1 C2
frontend/src/components/ScheduledAcquisitionsList.tsx  — A6 A7 C4
frontend/src/components/Map/ScheduleSatelliteLayers.tsx — C3
```

## Non-goals (not touched)

- No backend changes
- No slicing/caching logic from PR-UI-034 (`groundtrackSlicing.ts`, `useScheduleSatelliteLayers`)
- No new schedule filtering
- No new timeline zoom engine
