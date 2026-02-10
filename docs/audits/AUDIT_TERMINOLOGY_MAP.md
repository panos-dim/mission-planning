# AUDIT: Terminology Map

> PR-AUD-OPS-UI-LOCKS-PARITY — Ops Readiness Audit
> Generated: 2025-02-10

---

## 1. Summary of Current Behavior

The application uses terminology rooted in the original development phase. The review team has requested specific label changes to align with operational workflows. This document maps every current label to its desired replacement, with exact file locations and whether the label appears in API payloads.

---

## 2. Terminology Mapping Table

| Current Label | Desired Label | File(s) | Line(s) | In API Payload? | Notes |
| ------------- | ------------- | ------- | ------- | --------------- | ----- |
| Mission Analysis | Feasibility Analysis | `LeftSidebar.tsx` | 394-398 | No (UI only) | Left sidebar panel title + icon tooltip |
| Mission Analysis | Feasibility Analysis | `constants/simpleMode.ts` | 33 | No | Panel ID constant `MISSION_ANALYSIS: "mission"` — ID can stay, label changes |
| Analyze Mission (button) | Run Feasibility | `MissionControls.tsx` | 469 | No | Primary action button text |
| Analyzing... | Running Feasibility... | `MissionControls.tsx` | 460 | No | Loading state text |
| Mission Results | Feasibility Results | `RightSidebar.tsx` | 73 | No | Right sidebar panel title |
| Mission Results | Feasibility Results | `constants/simpleMode.ts` | 57 | No | Panel ID `MISSION_RESULTS: "mission"` — ID can stay |
| Planning | Planning | `LeftSidebar.tsx` | 400-404 | No | **Keep as-is** — review team did not request change |
| Commit to Schedule / Promote to Orders | Apply | `LeftSidebar.tsx` | 220-329 | Yes (`commitScheduleDirect`) | `handlePromoteToOrders` function; API endpoint unchanged |
| Commit to Schedule | Apply | `MissionPlanning.tsx` | ~1700+ | Yes | Button text for committing repair plans |
| Schedule (left sidebar) | Schedule | `LeftSidebar.tsx` | 408-409 | No | **Keep as-is** per review team (keep schedule on left for now) |
| Schedule (right sidebar concept) | Opportunities | N/A | N/A | No | Right sidebar doesn't currently have "Schedule" — review wants "Mission Results" → "Opportunities" |
| Plans (Object Explorer) | Schedule | `ObjectExplorer/` | various | No | Tree node label for algorithm plan results |
| Opportunities (in results table) | Opportunities | `MissionPlanning.tsx` | various | No | **Already correct** — results table header |
| Reset & New Analysis | Reset & New Feasibility | `MissionControls.tsx` | 434 | No | Reset button text |
| Mission Parameters | Scenario Parameters | `MissionControls.tsx` | 402 | No | Step 2 heading in analysis form |
| Scenario Inputs (governance tooltip) | Scenario Inputs | `MissionControls.tsx` | 21 | No | **Keep as-is** — already uses correct term |
| Repair Plan | Repair Plan | `MissionPlanning.tsx`, `RepairDiffPanel.tsx` | various | Yes | **Keep as-is** — review did not request change |

---

## 3. Orders Hierarchy (Current Tree)

The current order model has this hierarchy:

```
Workspace
└── Orders (from batch/manual creation)
    ├── order.id
    ├── order.target_id
    ├── order.priority
    ├── order.status (new | planned | committed | cancelled | completed)
    └── order.constraints
        
Plans (from algorithm runs)
└── plan.id
    └── Acquisitions
        ├── acquisition.id
        ├── acquisition.satellite_id
        ├── acquisition.target_id
        ├── acquisition.state (tentative | committed | executing | completed)
        └── acquisition.lock_level (none | hard)
```

### Object Explorer Tree Structure

```
Object Explorer
├── Satellites
│   └── ICEYE-X44
│       └── Opportunities (pass list)
├── Targets
│   └── T1 (Athens)
│       └── Opportunities (passes for this target)
├── Plans (algorithm results)
│   └── roll_pitch_best_fit
│       └── Scheduled items
└── Orders (accepted schedules)
    └── Schedule #1 - Feb 10
        └── Committed items
```

**Review team wants**: "Plans" → "Schedule" in the Object Explorer.

---

## 4. Labels Defined in API Payloads vs UI-Only

### API-Only Labels (backend response fields — DO NOT rename yet)

| Field | Endpoint | Notes |
| ----- | -------- | ----- |
| `planning_mode` | `/api/v1/schedule/plan`, `/api/v1/schedule/repair` | Values: `from_scratch`, `incremental`, `repair` |
| `mission_type` | `/api/v1/mission/analyze` | Values: `imaging`, `communication` |
| `state` | Acquisition responses | Values: `tentative`, `committed`, etc. |
| `lock_level` | Acquisition responses | Values: `none`, `hard` |
| `algorithm` | Planning responses | Values: `first_fit`, `best_fit`, etc. |

### UI-Only Labels (safe to rename without API changes)

- All sidebar panel titles
- All button text labels
- Tab labels (Committed, Timeline, Conflicts)
- Section headers in forms
- Tooltip text
- Badge text

---

## 5. Risks / Inconsistencies

1. **"Mission" is overloaded**: The panel ID `"mission"` is used for both left sidebar "Mission Analysis" and right sidebar "Mission Results". Renaming the label to "Feasibility Analysis/Results" won't break anything since IDs stay the same, but it's confusing in code.
2. **"Promote to Orders" vs "Commit to Schedule"**: Two different labels for the same action depending on context. `handlePromoteToOrders` (LeftSidebar) vs `commitScheduleDirect` (API). Should unify to "Apply".
3. **"Plans" in Object Explorer**: Currently shows algorithm result names (`roll_pitch_best_fit`). Renaming the category to "Schedule" while the parent sidebar panel is also called "Schedule" creates ambiguity.
4. **Backend endpoint names unchanged**: The review team explicitly says "DO NOT rename endpoints yet". All API paths (`/mission/analyze`, `/mission/plan`) will retain current names. Only UI labels change.

---

## 6. File References

| File | Key Lines | Purpose |
| ---- | --------- | ------- |
| `frontend/src/components/LeftSidebar.tsx` | 334-447 | Left panel titles and IDs |
| `frontend/src/components/RightSidebar.tsx` | 68-459 | Right panel titles |
| `frontend/src/components/MissionControls.tsx` | 293-482 | Analysis button labels, form headings |
| `frontend/src/components/MissionPlanning.tsx` | 1-2106 | Planning panel labels, commit button text |
| `frontend/src/components/MissionResultsPanel.tsx` | 1-1212 | Results panel labels and section headers |
| `frontend/src/constants/simpleMode.ts` | 30-66 | Panel ID constants |
| `frontend/src/components/ObjectExplorer/` | various | Tree node labels ("Plans", "Orders", etc.) |
| `frontend/src/components/RepairDiffPanel.tsx` | 1-1453 | Repair commit button labels |
| `frontend/src/components/RepairCommitModal.tsx` | 1-650 | Commit modal labels |

---

## 7. Recommended Minimal Change Strategy

1. **Create a single `labels.ts` constants file** with all user-facing strings. Replace hardcoded strings in components with references to this file. This makes future terminology changes trivial.
2. **Batch rename in one PR**: Change ~15 label strings across 6 component files. All are UI-only; no API contract changes.
3. **Rename "Plans" → "Schedule" in Object Explorer** separately, as it requires more careful testing of the tree node structure and any node-type-based logic.
