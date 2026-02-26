# PR-UI-032 — Schedule Satellite Layers: CZML Fallback & True-Window Empty States

**Branch:** `fix/schedule-satellite-layers-czml-fallback-and-true-window-empty-states`

**Goal:** Harden the Schedule satellite layers overlay so users get correct, actionable messages
whether CZML is absent or the visible window genuinely has no acquisitions. Fixes entity
restoration on view-switch and adds a dev-only debug summary.

---

## What changed

### 1. `useScheduleSatelliteLayers` — restoration robustness

`frontend/src/components/Map/hooks/useScheduleSatelliteLayers.ts`

| Fix | Detail |
|---|---|
| **Datasource identity change detection** | `prevDataSourceRef` compares the incoming `loadedDataSource` against the last-seen value. On mismatch the `touchedEntityIdsRef` is cleared immediately so stale IDs from a previous CZML load are never used to restore entities on the new datasource. |
| **Early-exit guard on non-schedule path** | If `touchedEntityIdsRef.current.size === 0` when leaving schedule view, the full entity iteration is skipped. Avoids redundant work on the very common "CZML first loads, user is already on a non-schedule tab" path. |
| **Ref clear when datasource goes null** | When `loadedDataSource` becomes `null` (CZML unloaded), the identity-change block fires and clears the touched set. Entities are gone from Cesium anyway; no restoration attempt is made. |

### 2. `ScheduleSatelliteLayers` — correct empty states + CZML warning

`frontend/src/components/Map/ScheduleSatelliteLayers.tsx`

| Change | Detail |
|---|---|
| **`loadedDataSource` prop** | Optional `DataSource \| null` (default `null`) passed from `GlobeViewport`. Used to derive `czmlLoaded`. |
| **CZML not-loaded warning (satList > 0)** | When items **do** exist in the visible window (`satList.length > 0`) but CZML is not loaded, an amber notice appears below the satellite list: *"CZML not loaded — run mission analysis to see globe entities."* |
| **Correct empty-state message (satList = 0)** | `showCzmlWarning = !czmlLoaded && items.length > 0`. When true, empty-state text is *"CZML not loaded — run mission analysis first."* (amber). Otherwise the original *"No acquisitions in visible window."* (gray) is shown. |
| **Dev-only debug summary** | Rendered only when `import.meta.env.DEV`. Shows `iw:<n> czml:<0\|1> sats:<n> gt:<n>` in a monospace 9px footer. Entity counts (`sats`, `gt`) are computed from `loadedDataSource.entities.values` and are zero when CZML is absent. |

### 3. `GlobeViewport` — wire prop

`frontend/src/components/Map/GlobeViewport.tsx`

```tsx
{viewportId === 'primary' && <ScheduleSatelliteLayers loadedDataSource={loadedDataSource} />}
```

---

## Files changed

| File | Change |
|---|---|
| `frontend/src/components/Map/hooks/useScheduleSatelliteLayers.ts` | `prevDataSourceRef`, early-exit guard, datasource-null clear |
| `frontend/src/components/Map/ScheduleSatelliteLayers.tsx` | `loadedDataSource` prop, CZML warning, correct empty states, dev debug |
| `frontend/src/components/Map/GlobeViewport.tsx` | Pass `loadedDataSource` prop |
| `docs/PR_UI_032_CHECKLIST.md` | This file |

---

## Acceptance criteria

### A — CZML not loaded, schedule items exist in window

- [ ] Open Schedule view **before** running mission analysis (no CZML, but master schedule
      fetched). Visible window contains acquisitions.
      Overlay satellite list shows entries **and** amber notice:
      *"CZML not loaded — run mission analysis to see globe entities."*

### B — CZML not loaded, no items in window

- [ ] Items exist in schedule store but the current `[tStart, tEnd]` window has none
      (`satList.length === 0`), and CZML is absent.
      Overlay shows amber empty state:
      *"CZML not loaded — run mission analysis first."*

### C — Truly no acquisitions in window (CZML loaded)

- [ ] CZML is loaded, schedule items exist but none fall within the visible window.
      Overlay shows gray empty state:
      *"No acquisitions in visible window."*
      (No amber / CZML warning shown.)

### D — Normal state (CZML loaded, items in window)

- [ ] CZML loaded, items in window → satellite list renders normally, no amber notice.

### E — Restoration: switching away from schedule view

- [ ] Enter schedule view (entities get hidden/modified), then switch to Mission Planning.
      All CZML `sat_*` and `*_ground_track` entities are restored to `show = true` and
      default path widths/alphas.
      No console errors.

### F — Restoration: CZML reload while in schedule view

- [ ] Trigger a CZML reload (re-run mission analysis) while on the Schedule tab.
      `touchedEntityIdsRef` is cleared (new datasource detected).
      Entities from the new datasource receive correct visibility immediately.
      Switching away restores them cleanly — no stale-ID artifacts.

### G — Dev debug summary

- [ ] In dev mode (`import.meta.env.DEV === true`) the overlay footer shows a monospace
      line, e.g. `iw:3 czml:1 sats:6 gt:6`.
- [ ] In production build (`DEV === false`) the debug footer is absent.

### H — No behavior change to toggles

- [ ] "Show satellites / groundtracks / highlight" switches behave identically to PR-UI-031.
- [ ] Schedule timeline contents are unaffected by all toggles.

### I — No backend changes

- [ ] Backend diff: zero lines changed.

---

## Regression notes

- `prevDataSourceRef` is a plain React ref — no re-renders triggered, no new deps added.
- The `touchedEntityIdsRef.clear()` on datasource change happens **before** the early return,
  so it fires even if `loadedDataSource` went `null`.
- `ScheduleSatelliteLayers` props are backward-compatible: `loadedDataSource` defaults to
  `null`, so any callers that don't pass it get the CZML-missing behavior (amber state when
  items exist, gray otherwise).
- Dev entity-count loop runs only inside `import.meta.env.DEV` guard; tree-shaken in prod.

---

## Known limitations (unchanged from PR-UI-031)

- Groundtrack temporal slicing (showing only the arc within `[tStart, tEnd]`) is not
  implemented; the full orbit arc is always rendered.
- TLE-based on-demand propagation (satellite.js) is out of scope for this PR.
