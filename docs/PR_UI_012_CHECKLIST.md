# PR_UI_012 — Right Pane Cleanup: Units, Rounding & Score Standout

## Summary

Apply remaining "after feasibility / right pane" cleanup notes:
remove coordinates from the right pane, enforce 2dp rounding on lat/lon elsewhere,
ensure agility includes unit, and make perfect-coverage targets visually distinct.

**No backend changes. No workflow changes.**

---

## A) Right pane: coordinates removed

### What changed

| File | Change |
|---|---|
| `MissionResultsPanel.tsx` | Removed `targetMeta.latitude.toFixed(2)°, targetMeta.longitude.toFixed(2)°` spans from both multi-target and single-target Opportunity headers |

Note: `Inspector.tsx` `TargetInspector` **keeps** the Location section with `CoordinateField` (now at 2dp per item C).

### Manual verification

1. Open Feasibility Results → select a target → **Opportunity headers show no coordinates**.
2. Object Explorer → click a target node → Inspector still shows Location with 2dp coordinates.

---

## B) Agility unit

### Status: Already present — no code changes needed

| Location | Display | Unit |
|---|---|---|
| `Inspector.tsx` `SatelliteInspector` | Slew Rate | `°/s` (inline in template literal) |
| `Inspector.tsx` `SpacecraftConstraintInspector` | Slew Rate | `°/s` (inline in template literal) |
| `AdminPanel.tsx` satellite list | Agility | `°/s` |

Agility was already removed from the Overview section per PR_UI_008.
No right-pane or target-details component displays agility without a unit.

### Manual verification

1. Object Explorer → select a satellite → Capabilities section → confirm "Slew Rate: X °/s".

---

## C) Rounding: lat/lon → 2 decimal places

### What changed

| File | Line(s) | Before | After |
|---|---|---|---|
| `Inspector.tsx` `CoordinateField` | `formatCoord()` | `toFixed(4)` | `toFixed(2)` |
| `TargetInput.tsx` | Parse status msg | `toFixed(4)` | `toFixed(2)` |
| `TargetInput.tsx` | Map-click status msg | `toFixed(4)` | `toFixed(2)` |
| `TargetInput.tsx` | Target list display | `toFixed(4)` | `toFixed(2)` |
| `ObjectMapViewer.tsx` | Selected object lat | `toFixed(4)` | `toFixed(2)` |
| `ObjectMapViewer.tsx` | Selected object lon | `toFixed(4)` | `toFixed(2)` |
| `AdminPanel.tsx` | Ground station coords | `toFixed(4)` | `toFixed(2)` |

### Already at 2dp (no change needed)

- `MissionResultsPanel.tsx` — coordinates removed entirely (see A)
- `OrdersPanel.tsx` `OrderTargetRow` — already `toFixed(2)`
- `MissionSidebar.tsx` — already `toFixed(2)`
- `TLEInput.tsx` — already `toFixed(2)`

### Manual verification

1. Hover any map entity / click in ObjectMapViewer → confirm coords show 2dp.
2. Add a target via TargetInput → confirm coords in list and status message show 2dp.
3. Admin → Ground Stations → confirm coords show 2dp.

---

## D) Perfect coverage (10/10) standout

### What changed

| File | Change |
|---|---|
| `MissionResultsPanel.tsx` Overview section | Targets metric card: when `covered === total`, applies `ring-1 ring-green-500/60 bg-green-900/20` to card, `text-green-400` to value, and appends ` ✓` to label |

### Design notes

- Green ring + subtle green background on the metric card
- Value text turns green (from white)
- "Targets ✓" label suffix
- Does **not** conflict with priority colors (those are per-target, not on overview cards)
- Does **not** conflict with lock indicators (those are on acquisitions, not overview)

### Manual verification

1. Run a feasibility analysis where **all** targets have at least one opportunity.
2. Confirm the "Targets" metric card in Overview has a green ring, green text, and "✓".
3. Run a feasibility analysis where **some** targets have no opportunities.
4. Confirm the card shows normal white text, no ring, no "✓".

---

## Build verification

```
npx tsc --noEmit   # ✅ Exit code 0, no errors
```

---

## Files changed (complete list)

1. `frontend/src/components/MissionResultsPanel.tsx` — A) coords removed, D) standout styling
2. `frontend/src/components/ObjectExplorer/Inspector.tsx` — A) Location section removed, C) CoordinateField 2dp
3. `frontend/src/components/TargetInput.tsx` — C) 3× toFixed(4) → toFixed(2)
4. `frontend/src/components/ObjectMapViewer.tsx` — C) 2× toFixed(4) → toFixed(2)
5. `frontend/src/components/AdminPanel.tsx` — C) ground station coords 2dp
6. `docs/PR_UI_012_CHECKLIST.md` — this file

---

## Non-goals (confirmed not touched)

- No backend changes
- No target UID work
- No feasibility/planning logic changes
- No timeline/opportunities rendering changes
- `docs/PR_UI_011_CHECKLIST.md` not modified
