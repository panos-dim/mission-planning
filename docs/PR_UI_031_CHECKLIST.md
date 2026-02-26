# PR-UI-031 — Schedule Master View: Satellite Layers

**Feature:** Satellite objects + groundtracks in the Cesium globe, synchronized with the Schedule
timeline visible window. Visual-only toggles. Highlight selected satellite on pass click.

---

## What was built

### 1. `scheduleStore` additions (no breaking changes)

| Field | Type | Default | Purpose |
|---|---|---|---|
| `focusedSatelliteId` | `string \| null` | `null` | Satellite ID extracted from focused acquisition |
| `schedLayerSatellites` | `boolean` | `true` | Toggle: show satellite objects in globe |
| `schedLayerGroundtracks` | `boolean` | `true` | Toggle: show groundtrack paths |
| `schedLayerHighlight` | `boolean` | `true` | Toggle: highlight focused satellite |

New action: `setSchedLayer(key, visible)` — viewer-only, does **not** filter the schedule
timeline.

`focusAcquisition` now also sets `focusedSatelliteId` from the matched `MasterScheduleItem`.

### 2. `useScheduleSatelliteLayers` hook

`frontend/src/components/Map/hooks/useScheduleSatelliteLayers.ts`

- Called inside `GlobeViewport` (primary + secondary), receives `viewerRef` + `loadedDataSource`.
- **In Schedule view** (`activeLeftPanel === 'schedule'`):
  - Computes satellites with acquisitions overlapping `[tStart, tEnd]` from `scheduleStore.items`.
  - Shows only matching `sat_<id>` CZML entities (when `schedLayerSatellites` is on).
  - Shows only matching `<id>_ground_track` CZML entities (when `schedLayerGroundtracks` is on).
  - Highlights focused satellite: larger point (14px), full opacity, thicker groundtrack (3px).
  - Tracks touched entity IDs for clean restoration.
- **Outside Schedule view**: restores all touched entities to their defaults and clears the
  touched-ID set, so other views are unaffected.
- **Graceful fallback**: no-op when CZML is not loaded (groundtracks require a prior mission run).

### 3. `ScheduleSatelliteLayers` overlay component

`frontend/src/components/Map/ScheduleSatelliteLayers.tsx`

- Rendered only when `activeLeftPanel === 'schedule'` (primary viewport).
- Collapsible panel positioned bottom-right of the Cesium viewport.
- Three switch toggles wired to `scheduleStore.setSchedLayer`.
- Per-satellite list: colored dot + display name, "selected" badge on focused satellite.
- "In window (N)" count shows only satellites with acquisitions in the visible timeline range.
- Empty state when no acquisitions are in the visible window.

---

## Files changed

| File | Change |
|---|---|
| `frontend/src/store/scheduleStore.ts` | +`focusedSatelliteId`, +`schedLayerSatellites/Groundtracks/Highlight`, +`setSchedLayer`, update `focusAcquisition` |
| `frontend/src/components/Map/hooks/useScheduleSatelliteLayers.ts` | **New** |
| `frontend/src/components/Map/hooks/index.ts` | Export new hook |
| `frontend/src/components/Map/ScheduleSatelliteLayers.tsx` | **New** |
| `frontend/src/components/Map/GlobeViewport.tsx` | Import + call hook, render overlay component |

---

## Acceptance criteria

### A — Satellites + groundtracks render

- [ ] Open Schedule view with ≥2 satellites having acquisitions → colored satellite objects
      and groundtracks appear in Cesium globe.
- [ ] Satellites not in the visible timeline window are hidden.
- [ ] Colors match the satellite color legend (same `getSatColor` registry).

### B — Toggles

- [ ] "Show satellites" OFF → satellite billboard/points disappear; timeline unchanged.
- [ ] "Show groundtracks" OFF → groundtrack paths disappear; timeline unchanged.
- [ ] "Highlight selected" OFF → all satellites shown at equal weight.
- [ ] Toggling back ON restores visibility immediately.

### C — Click highlight

- [ ] Click a pass in the schedule timeline → focused satellite point grows (14px) and its
      groundtrack renders thicker (3px) at full opacity.
- [ ] Clicking a different pass switches the highlight to the new satellite.
- [ ] Deselecting (or clearing focus) returns all satellites to default weight.

### D — Dynamic timeline sync

- [ ] Pan/zoom the schedule timeline → satellite + groundtrack set updates to match new
      `[tStart, tEnd]` window.
- [ ] Satellites that scroll out of the window disappear; new ones that scroll in appear.

### E — Non-schedule views unaffected

- [ ] Switch to Mission Planning view → all CZML entities restored to their default visibility
      (governed by existing `activeLayers` toggles).
- [ ] No console errors on view switch.

### F — No backend changes

- [ ] Backend diff: zero lines changed.
- [ ] Schedule timeline content unchanged — all acquisitions shown regardless of toggles.

---

## Regression notes

- `useLayerVisibility` hook still runs for `orbitLine`, `targets`, `labels`, etc. — no conflicts
  because `useScheduleSatelliteLayers` runs after it (declared later in GlobeViewport render).
- CZML `onLoad` callback (`setLoadedDataSource`) feeds the hook reactively — no polling needed.
- No `satelliteSelectionStore` or `visStore.activeLayers` changes made; existing layer toggles
  remain the authority outside the schedule view.

---

## Known limitations / follow-up

- Groundtracks require a prior mission analysis run (CZML must be loaded). Without CZML the
  overlay shows "No acquisitions in visible window" even if items exist in the schedule. A
  future PR could add TLE-based on-demand propagation via `satellite.js`.
- The groundtrack time-clipping (showing only the arc within `[tStart, tEnd]`) relies on Cesium's
  path entity availability interval — the full orbit arc is always rendered, not a sliced segment.
  True temporal slicing would require CZML re-generation or a custom primitive.
