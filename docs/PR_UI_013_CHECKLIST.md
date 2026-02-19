# PR-UI-013: Schedule Map Status Colors & Remove Satellite Filter

## Summary

Simplify schedule execution UX by removing satellite-per-satellite filtering from
schedule/opportunities surfaces and replacing manual/random target color coding on
the schedule map with status-based colors: **green = acquired**, **red = not acquired**.

---

## Changes Made

### A) Satellite Filter Removed (schedule/opportunities)

- **`ScheduleTimeline.tsx`** — Removed `satellite` from `TimelineFilters` interface, `DEFAULT_FILTERS`, `FilterChips` props, `ChipSelect` for satellite, and `filteredAcquisitions` satellite filter logic. Removed `Satellite` icon import and `uniqueSatellites` memo.
- **`ContextFilterBar.tsx`** — Removed satellite `FilterChip` rendering (the purple "Satellite: X" chip).
- **`MissionPlanning.tsx`** — Removed `contextFilter.satelliteId` filter from schedule table row filtering.

### B) Map Colors: Acquired vs Not-Acquired

- **`GlobeViewport.tsx`** — Added `useEffect` that recolors CZML target pin entities when committed schedule orders exist: green (`#22c55e`) for targets with ≥1 scheduled acquisition, red (`#ef4444`) for targets with 0 acquisitions. Uses `useOrdersStore` to read committed orders.
- **`ScheduleTimeline.tsx`** — Replaced random 8-color target palette (`laneColors`) with uniform green (`#22c55e`) for all lane borders — all lanes represent acquired targets by definition.
- **`MissionResultsPanel.tsx`** — Replaced satellite-based `getOpportunityColor()` with mode-based coloring: cyan for Optical, purple for SAR. Removed `getSatelliteColor()`, `getSatelliteColorByIndex` import, and unused `satellites` variable.

### C) Satellite Ground Track / Path Colors Neutralized

- **`GlobeViewport.tsx`** — Added `useEffect` that overrides per-satellite CZML ground track and path entity colors to uniform cyan (`Color.CYAN` alpha 0.7) after CZML load. Handles both constellation (`{sat_id}_ground_track`) and single-satellite (`satellite_ground_track`) entities.
- **`slewVisualization.ts`** — Replaced `getSatelliteArcColor()` with uniform cyan (`rgba(34, 211, 238, 0.6)`). Removed `getSatelliteColorByIndex` import and dead `hexToRgba` helper. Fixed pre-existing `any` type warning on `_viewer` parameter.

### D) Lock Mechanics Unchanged

- Lock/unlock via map Lock Mode and list toggles remain intact.
- Lock indicators (red circle + shield icon) still visible on timeline bars.
- `ScheduledAcquisitionsList.tsx` satellite grouping preserved (not a filter; used for lock management).
- Status colors do not visually hide lock state — lock icons render on top of bars.

---

## Acquired / Not-Acquired Computation Rule

A target is considered **acquired** if it appears as `target_id` in at least one
schedule item within any committed order in `useOrdersStore().orders`.

```text
acquiredTargetIds = Set of all target_id values from:
  committedOrders → order.schedule[] → item.target_id
```

A target is **not acquired** if it exists in `state.missionData.targets` but is
absent from the acquired set.

---

## Files Not Changed (by design)

- **No backend changes** — all changes are frontend-only.
- **No scoring/priority changes.**
- **No timeline realism work.**
- **No opportunity naming changes** (Athens 1/2/3 stays).
- **No schedule time formatting changes** (start-only stays).
- `selectionStore.ts` — `ContextFilter.satelliteId` field preserved in type for backward compatibility; just not rendered or consumed in schedule/planning views.
- `constants/colors.ts` — Satellite color palette preserved (used by other non-schedule surfaces like ground tracks).

---

## Verification / Sanity Steps

### Step 1: Schedule view has no satellite filter

- [ ] Open Schedule → Timeline tab → confirm satellite chip/dropdown is absent
- [ ] Open Planning → confirm ContextFilterBar does not show satellite chip
- [ ] Schedule table filters by target, look side, pass direction — not satellite

### Step 2: Schedule map — acquired targets green, not-acquired red

- [ ] Run a mission with multiple targets where some are scheduled and some are not
- [ ] Commit a schedule (promote to orders)
- [ ] Verify acquired targets show **green** pins on the globe
- [ ] Verify not-acquired targets show **red** pins on the globe
- [ ] Screenshot: schedule map with both green and red targets

### Step 3: Lock indicators still visible

- [ ] Toggle a lock on a scheduled acquisition via timeline (double-click) or Lock Mode
- [ ] Confirm lock indicator (red circle + shield) still visible on timeline bar
- [ ] Confirm map colors unchanged by lock toggle (status-only coloring)

### Step 4: Mode-based colors (SAR/Optical)

- [ ] Switch mission mode (SAR/Optical)
- [ ] Opportunity dots in MissionResultsPanel use cyan (Optical) or purple (SAR)
- [ ] Timeline bars use cyan (Optical) or purple (SAR) — not satellite colors
- [ ] Colors are consistent regardless of satellite

### Step 5: Build passes

- [ ] `npm run build` completes without errors
- [ ] `npm run lint` passes with zero errors and zero warnings

---

## Before / After

### Schedule Filters

- **Before:** Satellite chip + Target chip + Locked chip in ScheduleTimeline
- **After:** Target chip + Locked chip only (satellite chip removed)

### Schedule Map

- **Before:** Target pins colored by user-assigned target color from input form
- **After:** Target pins colored green (acquired) / red (not acquired) when schedule committed

### Opportunity Colors

- **Before:** Satellite-based color coding (Sky Blue, Orange, Rose, Teal, etc.)
- **After:** Mode-based color coding (Cyan = Optical, Purple = SAR)

---

## References

- UI-012 checklist (`docs/PR_UI_012_CHECKLIST.md`) confirms coordinate removal + 2dp rounding — **not modified** by this PR.
- Meeting notes: "we don't care schedule satellite by satellite" and "map should show red/green targets… remove manual colour coding."
