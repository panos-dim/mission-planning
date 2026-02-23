# PR-UI-024: Planning Visualization — Path Only, Start at Target, Remove Roll

## Summary

Presentation-layer-only changes to planning visualization:
- Show **path only** (no roll arcs, no footprints, no coverage)
- Path **starts at the target** (not satellite origin)
- **Labels** show off-nadir angle only (`XX.XX°`)
- Overlay controls (Footprints, Arcs, Labels, Color-by) **removed** from UI

No backend or scheduling algorithm changes.

---

## Changes Made

### A) Visualization: path only (remove roll)

| File | Change |
|------|--------|
| `store/slewVisStore.ts` | Defaults: `showFootprints: false`, `showSlewArcs: true`, `showSlewLabels: true` |
| `components/Map/SlewVisualizationLayer.tsx` | Removed all Entity-based footprint, slew arc, and sensor overlays. Only `OpportunityMetricsCard` remains. Removed unused imports (`Entity`, `Cartesian2/3`, `Color`, `JulianDate`, `useMission`, etc.) |
| `components/Map/SlewCanvasOverlay.tsx` | Removed footprint circle rendering, roll/pitch labels (`[+R°, +P°]`), "IMAGING NOW" cyan overlay. Removed `scheduleToFootprints` import, `useState`, `JulianDate`, `currentOpportunityId` state. |

### B) Path starts at target

| File | Change |
|------|--------|
| `utils/slewVisualization.ts` → `scheduleToSlewArcs()` | Removed initial satellite→first-target arc (the `nadir` → `firstOpp` arc block). Removed "new pass start" satellite→target arcs for time gaps > 10 min. Path now starts at first target and only draws target-to-target arcs within the same pass. |

### C) Remove planning overlays (presentation only)

| File | Change |
|------|--------|
| `components/MissionPlanning.tsx` | Removed Footprints / Arcs / Labels toggle buttons and Color-by `<select>` dropdown from Globe Visualization Controls section. Removed unused store destructured properties (`showFootprints`, `setShowFootprints`, `showSlewArcs`, `setShowSlewArcs`, `showSlewLabels`, `setShowSlewLabels`, `colorBy`, `setColorBy`). Removed `ColorByMode` type import. |

### D) Labels: off-nadir angle only

| File | Change |
|------|--------|
| `components/Map/SlewCanvasOverlay.tsx` | Arc labels changed from `#N: Δroll° / slew_time_s` to `Off-nadir angle: XX.XX°` (computed as `sqrt(roll² + pitch²)` for the "to" opportunity). |
| `components/OpportunityMetricsCard.tsx` | Hover card stripped to show only satellite→target header + `Off-nadir angle: XX.XX°`. Removed start/end times, Δroll, t_slew, value, density, slack fields. |

---

## Overlays removed/disabled

- **Target coverage overlay** — footprint circles no longer rendered in `SlewCanvasOverlay`
- **Footprint overlay/polygons** — Entity ellipses removed from `SlewVisualizationLayer`
- **Footprint outlines** — stroke rendering removed with footprint circles
- **"IMAGING NOW" indicator** — cyan circle + label removed from `SlewCanvasOverlay`
- **Roll/pitch labels** — `[+R°, +P°]` footprint labels removed
- **Sensor FOV entity** — "active-sensor-fov" Entity removed from `SlewVisualizationLayer`

## What is kept

- **Acquisition path** (target-to-target slew arcs with animated direction dots)
- **Target markers** (pins on globe — coloring rules unchanged)
- **Visualization toggle button** (on/off)
- **OpportunityMetricsCard** (hover card, now off-nadir only)
- **Schedule table** (unchanged — still shows all columns for dev reference)

---

## Manual Verification Steps

1. **Path visible, no roll** — Open Planning view with ≥1 scheduled acquisition → path polylines visible, no footprint circles, no roll arcs, no `[roll, pitch]` labels.
2. **Path starts at target** — Confirm the first arc segment starts at the first target position (no line drawn from satellite sub-point to first target).
3. **Overlays cannot be enabled** — Footprints / Arcs / Labels / Color-by toggle buttons are gone from the UI. Only the Visualization on/off button remains.
4. **Labels show off-nadir only** — Hover over arc midpoints → labels show `Off-nadir angle: XX.XX°`. Hover over schedule table row → metrics card shows only satellite→target + off-nadir angle.
5. **Build passes** — `npm run build` completes with no errors.

---

## Screenshots

> _To be captured during verification:_
>
> - [ ] Before/after of Planning visualization (roll removed)
> - [ ] Path starting at target (not satellite)
> - [ ] Overlay controls removed from toolbar
> - [ ] Label showing `Off-nadir angle: XX.XX°`
