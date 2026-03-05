# PR-UI-034 · Schedule Groundtrack Slicing — Fast-path Cache & Sample-step Control

**Branch**: `perf/schedule-groundtrack-slicing-fast-path-cache-and-sample-step-control`
**Depends on**: PR-UI-033 (schedule groundtrack temporal slicing)

---

## Goal

Harden and optimise the groundtrack temporal slicing introduced in PR-UI-033:
reduce rebuild cost on rapid zoom/pan, eliminate unnecessary Cesium entity churn,
add a controllable sample-step to balance fidelity vs performance, and guard
against runaway point counts on very large windows.

No backend changes. No schedule-timeline changes. No animation.

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/components/Map/utils/groundtrackSlicing.ts` | Extended — cache, cap, `SliceResult` type, dev stats |
| `frontend/src/components/Map/hooks/useScheduleSatelliteLayers.ts` | Extended — in-place updates, cache invalidation, sampleStep wiring, dev stats flush |
| `frontend/src/components/Map/ScheduleSatelliteLayers.tsx` | Extended — dev sample-step selector + enhanced debug footer |
| `frontend/src/store/scheduleStore.ts` | Extended — `groundtrackSampleStep` state + `setGroundtrackSampleStep` action |

---

## Architecture

### A) Position-slice cache (`groundtrackSlicing.ts`)

**Cache key**: `${entityId}|${tStartIso}|${tEndIso}|${sampleStep}`

| Key component | Why |
|---------------|-----|
| `entityId` | Different entities produce different positions |
| `tStartIso` | Window bounds determine the sampled range |
| `tEndIso` | Window bounds determine the sampled range |
| `sampleStep` | Different steps produce different point arrays |

**Cache invalidation rules**:

| Trigger | Action |
|---------|--------|
| CZML datasource replaced | `invalidateGroundtrackCache()` called in Effect 1 on identity change |
| Cache reaches 500 entries | Full clear before inserting the 501st entry (overflow guard) |
| `sampleStep` changes | New key → automatic cache miss; old entries unused but harmless |

**Cache storage**: module-level `Map<string, { positions: Cartesian3[], effectiveStep: number }>`.

---

### B) In-place polyline update (`useScheduleSatelliteLayers.ts`)

The previous implementation always did `entities.remove(existing)` then `entities.add(...)`.
PR-UI-034 replaces this with:

```
if (existing?.polyline) {
  if (!cacheHit) existing.polyline.positions = new ConstantProperty(positions)
  existing.polyline.width    = ...  // always — focus may have changed
  existing.polyline.material = ...  // always — focus may have changed
} else {
  // add new entity (first render or edge-case entity without polyline)
}
```

- **Cache hit + entity exists**: positions unchanged, only visual style refreshed.
- **Cache miss + entity exists**: positions replaced in-place via `ConstantProperty` reassignment (triggers Cesium `definitionChanged`, no entity ID churn).
- **No entity yet**: full `entities.add(...)` as before.

---

### C) Sample-step control

**Options**: `60 s` / `120 s` (default) / `300 s`

**Store location**: `scheduleStore.groundtrackSampleStep: 60 | 120 | 300`
**Action**: `scheduleStore.setGroundtrackSampleStep(step)`

**Behaviour**:
- Changing the step updates the store → Effect 2 dep array includes `sampleStep` → debounced rebuild fires automatically.
- New `sampleStep` produces a different cache key → always a cache miss on first rebuild after change.

**UI**: Dev-only row of three toggle-buttons (`GT sample step: 60s | 120s | 300s`)
visible in the Schedule Satellite Layers overlay when groundtracks are enabled.

---

### D) Max-points-per-satellite cap

**Constant**: `GROUNDTRACK_MAX_POINTS_PER_SAT = 2000`

**Logic** (inside `sliceGroundtrackPositions`):

```
estimatedPoints = ceil(totalSeconds / sampleStep) + 1
if estimatedPoints > 2000:
  effectiveStep = ceil(totalSeconds / 1999)   // auto-increase step
  capTriggered  = true
```

**Result** carried through `SliceResult.capTriggered` and `SliceResult.effectiveStep`.

**Dev footer** turns amber and shows the cap note when triggered:
```
step:432s ⚡cap
step auto-increased to 432s to maintain cap
```

---

## `SliceResult` type

```ts
interface SliceResult {
  positions:      Cartesian3[]
  effectiveStep:  number   // actual step used (may > requested when cap fires)
  capTriggered:   boolean
  cacheHit:       boolean
}
```

The function signature changed from `→ Cartesian3[] | null` to `→ SliceResult | null`.
The only caller (`useScheduleSatelliteLayers`) is updated accordingly.

---

## Dev diagnostics (`_devGroundtrackStats`)

Module-level mutable object in `groundtrackSlicing.ts`, written by the hook
and read by `ScheduleSatelliteLayers` on each render (no Zustand churn):

| Field | Meaning |
|-------|---------|
| `totalHits` / `totalMisses` | Session running totals |
| `lastHits` / `lastMisses` | Per-rebuild counts (reset each Effect-2 callback) |
| `effectiveStep` | Step used in the last rebuild (auto-increased value if cap hit) |
| `capTriggered` | Whether the cap fired in the last rebuild |
| `capNote` | Human-readable string when cap is active, `null` otherwise |

**Debug footer example** (DEV only, bottom of overlay):

```
iw:3 czml:1 sats:5 gt:5
hits:3 miss:0 tot:12/4
step:120s
```

Cap-triggered example:
```
iw:2 czml:1 sats:5 gt:5
hits:0 miss:2 tot:6/8
step:432s ⚡cap
step auto-increased to 432s to maintain cap
```

---

## Acceptance Criteria

- [ ] Rapid zoom/pan causes cache hits (visible as `hits > 0` in debug footer)
      after the first build — fewer rebuilds, less entity churn.
- [ ] Sliced polylines update smoothly with no flicker and no console errors.
- [ ] **Sample-step selector** (DEV): 60 → 120 → 300 s changes fidelity
      deterministically; rebuild fires after 300 ms debounce.
- [ ] Effective-step shown in debug footer matches selected step when cap is not hit.
- [ ] **Cap**: open a large window spanning > 2000 × 120 s ≈ 69 hrs → footer shows
      `⚡cap` and the auto-increased step value.
- [ ] CZML reload (new analysis run) clears the cache and rebuilds correctly.
- [ ] Toggle groundtracks off/on → sliced entities removed/restored correctly.
- [ ] Switching away from the Schedule tab removes all sliced entities.
- [ ] `npm run build` passes with no type errors.
- [ ] ESLint passes with no new warnings.

---

## Verification steps

1. **Zoom/pan stress test** — Pan the timeline repeatedly → `hits` counter in
   debug footer increases; no lag spikes; no console errors.
2. **Toggle groundtracks** — `schedLayerGroundtracks = false` removes sliced
   entities; re-enabling restores them.
3. **Sample-step change** — Switch 60 → 120 → 300 → observe expected
   fidelity change (fewer/more points) and rebuild note in footer.
4. **Large window** — Expand visible window to > 70 hours → cap fires,
   footer shows `⚡cap` and `step auto-increased to Xs`.
5. **CZML reload** — Re-run analysis → cache invalidated; tracks rebuilt from
   fresh positions.
6. **Build** — `npm run build` in `frontend/` must pass with no errors.

---

## Non-Goals

- No backend changes.
- No schedule timeline contents change.
- No animation (polylines remain static `ConstantProperty` geometry).
- No TLE on-demand propagation.
- No changes to the two-effect design or 300 ms debounce — only improved.
