# PR-UI-033 · Schedule Groundtrack Temporal Slicing

**Branch**: `feat/schedule-groundtrack-temporal-slicing-by-visible-window`
**Depends on**: PR-UI-031 (schedule satellite layers)

---

## Goal

Render only the groundtrack arc that falls within the schedule visible window
`[tStart, tEnd]` instead of always showing the full CZML path arc.
This eliminates clutter when zooming the timeline and makes the
Cesium ↔ Schedule-timeline synchronisation visually correct.

No backend changes. No algorithm changes.

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/components/Map/utils/groundtrackSlicing.ts` | **New** — position sampling utility |
| `frontend/src/components/Map/hooks/useScheduleSatelliteLayers.ts` | Modified — temporal slicing effects |

### No changes required

- `frontend/src/components/Map/GlobeViewport.tsx` — hook reads `tStart`/`tEnd` from `scheduleStore` directly; no prop threading needed.

---

## Architecture

### `groundtrackSlicing.ts` (new utility)

```ts
sliceGroundtrackPositions(entity, tStartIso, tEndIso): Cartesian3[] | null
```

- Samples `entity.position` (a CZML `SampledPositionProperty`) at
  `GROUNDTRACK_SAMPLE_STEP_SECONDS = 120` s intervals (matches backend `time_step`).
- Returns a static `Cartesian3[]` covering exactly `[tStart, tEnd]`, or `null`
  when the entity has no position data or fewer than 2 valid samples.

### `useScheduleSatelliteLayers.ts` — two-effect design

| Effect | Trigger | What it does |
|--------|---------|--------------|
| **Effect 1** (immediate) | Any dep change | Show/hide entities; for groundtracks: sets `entity.path.show = false` (suppresses the clock-relative arc). Immediately removes the sliced polyline for any entity leaving the window. |
| **Effect 2** (300 ms debounce) | `tStart`, `tEnd`, window, datasource, focus | For each in-window groundtrack: calls `sliceGroundtrackPositions`, creates a `viewer.entities` polyline covering exactly `[tStart, tEnd]`. Removes stale sliced entities. |

**Sliced entity ID convention**: `{groundtrackId}_sliced`
e.g. `sat_ICEYE-X1_ground_track_sliced`

**Visual spec**:

- Normal in-window track: `getSatColorWithAlpha(ownerSatId, 0.5)`, width `1.5`
- Focused satellite track: `getSatColor(ownerSatId).withAlpha(1.0)`, width `3`

**Cleanup matrix**:

| Event | Action |
|-------|--------|
| Leave schedule tab | Effect 1 restores `entity.path.show = true`, removes all sliced entities |
| Datasource replaced | Effect 1 removes all sliced entities (stale position refs) |
| `showGroundtracks = false` | Effect 2 removes all sliced entities |
| Satellite exits window | Effect 1 removes its sliced entity immediately |
| Window `[tStart, tEnd]` changes | Effect 2 debounce fires; old sliced entities stay visible until replaced |

---

## Acceptance Criteria

- [ ] With CZML loaded, enter Schedule tab — groundtracks are rendered as
      windowed arcs, not full-mission arcs.
- [ ] Pan / zoom the schedule timeline — Cesium groundtracks update to match
      the new `[tStart, tEnd]` window (after ≤ 300 ms debounce).
- [ ] Narrowing the window removes satellites that no longer have acquisitions
      in range; their groundtrack arcs disappear immediately.
- [ ] Focused satellite groundtrack is thicker (`width = 3`) and fully opaque
      within the window.
- [ ] `schedLayerGroundtracks = false` hides all arcs (sliced and original).
- [ ] Switching away from the Schedule tab restores full path arcs; no
      residual sliced polylines remain in the viewer.
- [ ] Reloading CZML (new analysis run) removes stale sliced entities before
      rebuilding.
- [ ] No console errors.
- [ ] No visible flicker during window pan/zoom (old arc stays until replaced).
- [ ] `npm run build` passes with no type errors.
- [ ] ESLint passes with no new warnings.

---

## Performance Notes

- Geometry is only rebuilt on **window change** (debounced 300 ms) and on
  **datasource change** — not on every Cesium frame.
- Position sampling is O(N/120) per satellite where N = mission duration in
  seconds.  For a 24-hour mission with 1 satellite: ≤ 720 sample points.
- `slicedEntityIdsRef` uses a `Set<string>` so add/remove/has are O(1).
- The original CZML `entity.path` is hidden (not removed), so no CZML
  re-parsing is triggered.

---

## Non-Goals

- No TLE on-demand propagation.
- No new API endpoints.
- No changes to schedule timeline contents or ordering.
- No changes to dev-debug footer logic.
- No animation — polylines are static `ConstantProperty` geometry.
