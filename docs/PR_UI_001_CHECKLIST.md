# PR_UI_001 — UI Terminology + Conflicts Surface Removal Checklist

## A) Terminology renames (UI-only)

### A1: Mission Analysis → Feasibility Analysis

- [x] Left sidebar panel title via `LABELS.FEASIBILITY_ANALYSIS` (`LeftSidebar.tsx`)
- [x] Guidance text in `MissionPlanning.tsx` ("Run Feasibility Analysis first")
- [x] Warning copy in `MissionPlanning.tsx` ("requires opportunities from Feasibility Analysis")
- [x] Step instructions in `MissionPlanning.tsx` ("Go to **Feasibility Analysis** panel")
- [x] Error suggestion in `errorMapper.ts` ("in the Feasibility Analysis panel")
- [x] Error suggestion in `errorMapper.ts` ("Run Feasibility Analysis first to generate…")

### A2: Mission Results → Feasibility Results

- [x] Right sidebar panel title via `LABELS.FEASIBILITY_RESULTS` (`RightSidebar.tsx`)
- [x] Empty-state heading in `MissionResultsPanel.tsx` ("No Feasibility Results Yet")
- [x] Legacy sidebar heading in `MissionSidebar.tsx`

### A3: Commit to Schedule → Apply

- [x] CTA button label in `PlanningResults.tsx`
- [x] Guidance copy in `AcceptedOrders.tsx` ("click **Apply** to add acquisitions")

### A4: Opportunities framing (right sidebar results)

- [x] Section header renamed from "Schedule" → "Opportunities" in `MissionResultsPanel.tsx`
- [x] Data unchanged — only the collapsible section label was updated

### A5: Max Off-nadir angle

- [x] Slider label via `LABELS.MAX_OFF_NADIR_ANGLE` in `MissionParameters.tsx`
- [x] Summary row via `LABELS.MAX_OFF_NADIR_ANGLE_SHORT` in `MissionParameters.tsx` (was "Max Agility")
- [x] Overview row via `LABELS.MAX_OFF_NADIR_ANGLE_SHORT` in `MissionResultsPanel.tsx`
- [x] Comment updated ("Max Agility" → "Max Off-nadir angle")
- [x] All labels centralized in `constants/labels.ts`

## B) Conflicts UI surface removal

### B1: Schedule panel

- [x] `CONFLICTS` key removed from `SCHEDULE_TABS` in `simpleMode.ts`
- [x] `SIMPLE_MODE_SCHEDULE_TABS` already excluded conflicts — no change needed
- [x] `SchedulePanel.tsx` tabs array has no Conflicts entry

### B2: Conflict store wiring

- [x] `useConflictStore` import removed from `SchedulePanel.tsx`
- [x] `getConflictsForAcquisition` call removed; `has_conflict` hardcoded to `false`
- [x] `conflictStore.ts` retained (may be used by non-planner surfaces)

### B3: ScheduleTimeline conflicts UI

- [x] Conflicts filter chip removed from `FilterChips` component
- [x] `conflictsOnly` removed from `TimelineFilters` interface and `DEFAULT_FILTERS`
- [x] `hasConflict` variable and "Conflict" badge removed from `TimelineCard`
- [x] Conflicts count removed from summary footer
- [x] `conflictsOnly` filter logic removed from `filteredAcquisitions` memo
- [x] Unused `AlertTriangle` import removed

## Constraints / Non-goals validation

- [x] **No API changes** — no endpoint renames, no request/response changes
- [x] **No behavior changes** — planning, scheduling, scoring, locking unchanged
- [x] **Schedule/Acquisitions stay in left pane** — not moved
- [x] **No timeline realism or map lock mode** implemented
- [x] **Conflict stores retained** — only UI surfacing removed

## Build / sanity

- [x] `npx tsc --noEmit` passes with zero errors
- [x] No dead imports or orphaned components from Conflicts removal
- [x] No API/contract diffs

## Verification steps

1. Open planner → left sidebar says **Feasibility Analysis**
2. Run typical flow → right sidebar shows **Feasibility Results** and **Opportunities** section label
3. CTA reads **Apply** everywhere "Commit to Schedule" was shown
4. **Max Off-nadir angle** visible where "Max Satellite agility / pointing angle" was
5. Schedule panel has **no Conflicts tab**; no Conflicts route in simple mode
6. Build passes cleanly

## Files changed

| File | Change |
| ---- | ------ |
| `constants/labels.ts` | Centralized labels (pre-existing) |
| `constants/simpleMode.ts` | Removed `CONFLICTS` from `SCHEDULE_TABS`; cleaned comment |
| `components/LeftSidebar.tsx` | Updated badge comment |
| `components/RightSidebar.tsx` | Already using `LABELS.FEASIBILITY_RESULTS` |
| `components/MissionPlanning.tsx` | "Mission Analysis" → "Feasibility Analysis" (3 locations) |
| `components/MissionParameters.tsx` | "Max Agility" → `LABELS.MAX_OFF_NADIR_ANGLE_SHORT`; comment |
| `components/MissionResultsPanel.tsx` | "Schedule" section → "Opportunities" |
| `components/MissionSidebar.tsx` | "Mission Results" → "Feasibility Results" |
| `components/AcceptedOrders.tsx` | "Commit to Schedule" → "Apply" |
| `components/features/mission-planning/PlanningResults.tsx` | "Commit to Schedule" → "Apply" |
| `components/SchedulePanel.tsx` | Removed `useConflictStore`; hardcoded `has_conflict: false` |
| `components/ScheduleTimeline.tsx` | Removed conflicts chip/badge/filter/footer; cleaned imports |
| `utils/errorMapper.ts` | "Mission Analysis" → "Feasibility Analysis" (2 suggestions) |
