# PR-UI-028: UI Terminology & Formatting Checklist

## Summary

Standardize off-nadir angle to 1dp, rename Run Scheduler → Generate Mission Plan,
rename Geometry → Quality in Scoring Strategy, and document Apply → Next status.

---

## 1. Off-nadir angle formatting (2dp → 1dp)

### Grep verification

```bash
# Should return NO matches (all 2dp off-nadir usages eliminated):
rg -i 'off.?nadir.*toFixed\(2\)|offNadir.*toFixed\(2\)' frontend/src/

# Should return NO matches for fmt2 used with off-nadir:
rg 'fmt2.*off_nadir|off_nadir.*fmt2' frontend/src/
```

### Files changed

| File | Change |
|------|--------|
| `frontend/src/utils/format.ts` | Added `fmt1()` helper (1dp) |
| `frontend/src/components/OpportunityMetricsCard.tsx` | `offNadir.toFixed(2)` → `.toFixed(1)` |
| `frontend/src/components/Map/SlewCanvasOverlay.tsx` | `offNadir.toFixed(2)` → `.toFixed(1)` |
| `frontend/src/components/features/mission-planning/ScheduleTable.tsx` | `offNadirAngle.toFixed(2)` → `.toFixed(1)` |
| `frontend/src/components/features/mission-planning/PlanningResults.tsx` | `mean_incidence_deg.toFixed(2)` → `.toFixed(1)` |
| `frontend/src/components/ScheduleTimeline.tsx` | `fmt2()` → `fmt1()` for off-nadir tooltip |
| `frontend/src/components/MissionResultsPanel.tsx` | `fmt2()` → `fmt1()` for off-nadir tooltip |

### Surfaces already at 1dp (no change needed)

- `MissionPlanning.tsx` — angle_statistics display (line ~983), schedule table (line ~1216)
- `ObjectExplorer/Inspector.tsx` — Overview field + inline badge
- `usePlanningState.ts` — console summary
- `utils/debug.ts` — debug table

---

## 2. "Run Scheduler" → "Generate Mission Plan"

### Grep verification

```bash
# Should return NO matches:
rg -F 'Run Scheduler' frontend/src/
```

### Files changed

| File | Change |
|------|--------|
| `frontend/src/components/MissionPlanning.tsx` | `'▶ Run Scheduler'` → `'▶ Generate Mission Plan'` |
| `frontend/src/components/DemoScenarioRunner.tsx` | Step label updated |

---

## 3. "Geometry" → "Quality" (Scoring Strategy labels)

### Grep verification

```bash
# Should return NO matches in scoring strategy display labels:
# (Note: code-level keys like weight_geometry, geometry property remain unchanged — intentional)
rg -F '"Geometry"' frontend/src/components/features/mission-planning/WeightConfiguration.tsx
rg '>Geometry<' frontend/src/components/features/mission-planning/WeightConfiguration.tsx
rg 'Geometry ' frontend/src/components/MissionPlanning.tsx
```

### Files changed

| File | Change |
|------|--------|
| `frontend/src/components/features/mission-planning/WeightConfiguration.tsx` | Label, tooltip title, bar legend: Geometry → Quality |
| `frontend/src/components/MissionPlanning.tsx` | Inline weight bar legend: Geometry → Quality |
| `frontend/src/components/features/mission-planning/usePlanningState.ts` | Preset descriptions: "geometry" → "quality" |

### Intentionally unchanged

- `weight_geometry` (config key) — backend API contract
- `getNormalizedWeights().geometry` (code property) — internal data
- Algorithm descriptions ("Best geometry per target") — describes algorithm behavior, not scoring strategy

---

## 4. Apply → Next (Scoring Strategy CTA)

### Files changed

| File | Change |
|------|--------|
| `frontend/src/components/MissionPlanning.tsx` | Bottom CTA after results: `{LABELS.APPLY}` → `Next`; removed unused `LABELS` import |

The scoring strategy bottom CTA (shown after Generate Mission Plan produces results)
now reads **"Next"** instead of "Apply". Clicking it proceeds to the
`ApplyConfirmationPanel`, which retains its own "Apply Plan" / "Apply Anyway" buttons
unchanged.

### Grep verification

```bash
# Should return NO matches for LABELS in MissionPlanning.tsx:
rg 'LABELS' frontend/src/components/MissionPlanning.tsx
```

---

## 5. Manual verification steps

1. **Generate Mission Plan CTA** — Open Mission Planning panel with loaded opportunities.
   Verify bottom button reads "▶ Generate Mission Plan" (not "Run Scheduler").

2. **Scoring Strategy labels** — Before running the planner, check the Scoring Strategy
   section. Weight bar legend and slider labels should show "Priority / Quality / Timing"
   (not "Geometry"). Hover on the green bar segment should show "Quality: XX%".

3. **Off-nadir 1dp** — Run the planner and inspect:
   - Schedule table: Off-Nadir column shows `X.X` (not `X.XX`)
   - Map canvas overlay labels: `X.X°` format
   - Opportunity hover card: "Off-nadir angle: X.X°"
   - Schedule timeline tooltip: "Off-nadir angle: X.X°"
   - Feasibility timeline tooltip: "Off-nadir angle: X.X°"

4. **Next CTA + Apply Plan unchanged** — After generating a plan, verify the bottom CTA
   reads "Next" (not "Apply"). Click it and confirm the ApplyConfirmationPanel appears
   with "Apply Plan" / "Apply Anyway" buttons unchanged.

5. **Build** — `npx tsc --noEmit` passes with exit code 0.

---

## 6. Build status

- **TypeScript**: ✅ Clean (`npx tsc --noEmit` exit 0)
- **Pre-existing lint warnings** (not introduced by this PR):
  - `WeightConfiguration.tsx:133` — `Unexpected any` (pre-existing)
  - `usePlanningState.ts:144` — missing useEffect dep (pre-existing)
  - `usePlanningState.ts:292` — unnecessary useCallback dep (pre-existing)
