# PR-UI-003: Map Lock Mode Toggle & Click-to-Lock

## Lock Mode Placement

- **Location**: Bottom-right of the primary map viewport (`GlobeViewport`), positioned at `bottom-24 right-4` to sit above the Cesium timeline controls.
- **Component**: `LockModeButton` (`frontend/src/components/Map/LockModeButton.tsx`)
- **Visual states**:
  - **OFF**: Gray button with Lock icon, label "Lock Mode"
  - **ON**: Red button with X icon, label "Exit Lock Mode", plus a helper tooltip and a subtle red border overlay on the viewport

## What Entity Types Are Lockable

| Entity Type | Lockable? | ID Resolution |
|---|---|---|
| SAR swath acquisitions | Yes | Entity ID starts with `sar_swath_`; `entity_type: "sar_swath"` |
| Optical pass acquisitions | Yes | Entity ID starts with `optical_pass_`; `entity_type: "optical_pass"` |
| Target markers (CZML) | No | No acquisition/opportunity ID; clicking logs "Entity not lockable" |
| Satellites | No | Orbital objects, not lockable |
| Coverage areas / cones | No | Visualization helpers, not interactive |

**ID resolution path**: `Entity.properties.opportunity_id` → `lockStore.toggleLock(opportunityId)` → optimistic update → `PUT /api/v1/schedule/acquisitions/{id}/lock`

Both SAR swaths and optical passes use the same `extractLockableOpportunityId()` helper in `GlobeViewport.tsx` which reads `entity.properties.opportunity_id` for any entity with `entity_type` of `"sar_swath"` or `"optical_pass"`.

## Files Changed

| File | Change |
|---|---|
| `backend/czml_generator.py` | **Modified** — Added `_optical_pass_description()` + `_create_optical_pass_packets()` to generate per-pass CZML entities for optical missions |
| `frontend/src/store/lockModeStore.ts` | **New** — Zustand store: `isLockMode`, `enableLockMode`, `disableLockMode`, `toggleLockMode` |
| `frontend/src/components/Map/LockModeButton.tsx` | **New** — Map overlay toggle button with tooltip, aria-label, Esc hint, mutual exclusion with add mode |
| `frontend/src/components/Map/GlobeViewport.tsx` | **Modified** — Lock mode click handler supports SAR + optical; added `isOpticalPassEntity`, `isLockableEntity`, `extractLockableOpportunityId` helpers; optical pass normal selection |
| `frontend/src/components/SchedulePanel.tsx` | **Modified** — Imports `useMission` context; pipes `imaging_type` into timeline acquisitions as `mode: 'Optical' \| 'SAR'` |
| `frontend/src/components/ScheduleTimeline.tsx` | **Modified** — Color-coded mode badge (cyan=Optical, purple=SAR) + colored left border on timeline cards |
| `frontend/src/App.tsx` | **Modified** — Wire `disableLockMode()` to Esc key handler |
| `frontend/src/store/index.ts` | **Modified** — Export `useLockModeStore` from barrel |

## State Wiring

- Lock mode toggle: `lockModeStore.isLockMode` (client-only, no persistence needed)
- Lock level state: `lockStore.levels` (existing, optimistic + API + rollback)
- Lock toggle action: `lockStore.toggleLock(acquisitionId)` (existing, reused as-is)
- Toast notifications: `lockStore.toasts` → `LockToastContainer` (existing, no changes)
- Mutual exclusion: entering lock mode auto-exits target add mode; Esc exits both

## Code-Verified Results

### 1. Baseline: Lock Mode OFF → click map entities → normal selection behavior

- [x] Click SAR swath → swath selected in swath store, cross-panel sync works — `isLockMode` is `false` by default (`lockModeStore` line 26), so the `if (isLockMode)` block at GlobeViewport line 711 is skipped and the existing normal swath-picking path (line 736+) executes unchanged.
- [x] Click target marker → scene object created/selected — normal entity selection at line 730+ runs; no lock mode interference.
- [x] Click empty space → deselect — `selectObject(null)` at line 817 fires as before.

### 2. Lock Mode ON → click an acquisition on map → toggles to Locked

- [x] Click Lock Mode button → button turns red, "Exit Lock Mode" label, helper tooltip visible — `LockModeButton` renders red bg (`bg-red-600`) + X icon + tooltip div when `isLockMode === true` (lines 32-49).
- [x] Click SAR swath entity → lock toggled (toast: "Acquisition locked") — `isLockMode` block at line 711 picks the entity, checks `isSarSwathEntity`, extracts `opportunityId`, calls `toggleLock(opportunityId)` which calls `lockStore.setLockLevel(id, "hard")` → optimistic update + API call + success toast "Acquisition locked" (lockStore lines 93-133).
- [x] Lock state visible in acquisitions list / inspector panel — `lockStore.levels` is a shared Zustand map; `SchedulePanel` reads it at line 39 (`useLockStore(s => s.levels)`), `Inspector` reads it at line 1276 (`useLockStore(s => s.levels)`). Same store instance = always in sync.

### 3. Click same entity again → toggles back to Unlocked

- [x] Click same swath → lock toggled back (toast: "Acquisition unlocked") — `toggleLock` reads current level via `getLockLevel(id)` which returns `"hard"`, then calls `setLockLevel(id, "none")` → optimistic update + API call + toast "Acquisition unlocked" (lockStore lines 93-97, 128-131).

### 4. Cross-check: lock state matches across map clicks and list/panel toggles

- [x] Lock via map → ScheduleTimeline/Inspector shows "Hard Lock" — single `lockStore.levels` Map is the source of truth. `SchedulePanel.timelineAcquisitions` merges `lockLevels.get(acqId) ?? 'none'` (line 66). Inspector reads the same map at line 1276.
- [x] Unlock via list toggle → map click still reflects correct state — list toggle calls `lockStore.toggleLock(id)` → updates `lockStore.levels` → next map lock-mode click reads current level from the same store.

### 5. Refresh/re-render map → lock state persists

- [x] Pan/zoom map → lock icons/state unchanged — lock state lives in `lockStore.levels` (Zustand, in-memory), not in Cesium entities. Pan/zoom does not re-render React components or reset the store.
- [x] Lock mode button state resets on page refresh — `lockModeStore.isLockMode` defaults to `false` (line 26), no persist middleware. Intentional.

### 6. Esc exits lock mode

- [x] Esc key calls `disableLockMode()` — App.tsx line 56 in the keydown handler, with `disableLockMode` in the dependency array (line 68).

### 7. Accessibility

- [x] Button has `title` attribute — `"Exit Lock Mode (Esc)"` / `"Lock Mode — click map items to lock/unlock"` (LockModeButton line 37).
- [x] Button has `aria-label` — `"Exit Lock Mode"` / `"Enter Lock Mode"` (LockModeButton line 38).

### 8. No TS/ESLint/build regressions

- [x] `tsc --noEmit` → 0 errors
- [x] `eslint` on all changed files → 0 errors, 0 warnings

### 9. Mutual exclusion between modes

- [x] Entering lock mode auto-exits target add mode — `LockModeButton.handleToggle` calls `disableAddMode()` if `isAddMode` is true before toggling (line 22-24).
- [x] Click handler priority: `isAddMode` checked first (line 690), `isLockMode` second (line 711) — if both somehow active, add mode wins (safe fallback).

## Known Limitations

1. **Only SAR swath entities are lockable** — these are the only map entities that carry `opportunity_id` linking to acquisitions in the lock store.
2. **Non-lockable clicks are silently ignored** — clicking a target or satellite in lock mode does nothing (logged at verbose level). No toast shown to avoid noise.
3. **Lock mode is ephemeral** — not persisted across page refreshes. This is intentional; it's a transient interaction mode.
4. **CZML reload** — if CZML data reloads (new mission analysis), entity references reset but lock state in the store is preserved.
5. **No cursor change** — Cesium does not support CSS cursor changes on the canvas. A subtle red border overlay indicates lock mode instead.
