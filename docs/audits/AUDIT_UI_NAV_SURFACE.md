# AUDIT: UI Navigation Surface

> PR-AUD-OPS-UI-LOCKS-PARITY — Ops Readiness Audit
> Generated: 2025-02-10

---

## 1. Summary of Current Behavior

The COSMOS42 UI uses a **dual-sidebar layout** with a 3D Cesium globe in the center:

- **Left Sidebar** (`LeftSidebar.tsx`): Vertical icon rail (48px) + expandable panel (432–864px). Contains all workflow panels.
- **Right Sidebar** (`RightSidebar.tsx`): Mirror layout. Contains results inspection, layers, and AI assistant.
- **Header** (`App.tsx`): Fixed 64px bar with branding, UTC clock, UI mode toggle (Simple/Developer), view mode toggle.
- **Center Canvas**: Cesium/Resium 3D globe (`LazyMultiViewContainer`) with dynamic padding based on sidebar open state.
- **Admin Panel**: Full-screen modal overlay, opened from bottom of left sidebar icon rail.

### 1.1 Left Sidebar Panels

| Panel ID | Label | Icon | Component | Simple Mode |
|---|---|---|---|---|
| `explorer` | Object Explorer | `GitBranch` | `ObjectExplorerTree` | Yes |
| `workspaces` | Workspaces | `FolderOpen` | `WorkspacePanel` | Yes |
| `mission` | Mission Analysis | `Satellite` | `MissionControls` | Yes |
| `planning` | Planning | `Calendar` | `MissionPlanning` | Yes |
| `schedule` | Schedule | `CheckSquare` | `SchedulePanel` | Yes |

- **Admin button** (bottom icon rail): Opens `AdminPanel` modal.
- All 5 panels visible in both Simple and Developer mode (see `SIMPLE_MODE_LEFT_PANELS` in `constants/simpleMode.ts:39-45`).

### 1.2 Right Sidebar Panels

| Panel ID | Label | Icon | Component | Simple Mode |
|---|---|---|---|---|
| `mission` | Mission Results | `BarChart2` | `MissionResultsPanel` | Yes |
| `inspector` | Inspector | `FileSearch` | `Inspector` (ObjectExplorer) | Yes |
| `layers` | Layers | `Layers` | Layer toggle controls | Yes |
| `ai_assistant` | AI Assistant | `Bot` | Placeholder (disabled) | Yes |

### 1.3 Schedule Panel Tabs (Left Sidebar → Schedule)

| Tab ID | Label | Icon | Visible |
|---|---|---|---|
| `committed` | Committed | `CheckSquare` | Always |
| `timeline` | Timeline | `Clock` | Always |
| `conflicts` | Conflicts | `AlertTriangle` | Always |
| `history` | History | — | Developer mode only |

- Defined in `constants/simpleMode.ts:72-83`.
- Conflicts tab shows badge counts from `conflictStore`.

### 1.4 Component Entry Points

```
App.tsx
├── Header (branding, UTC clock, UIModeToggle, ViewModeToggle)
├── LeftSidebar
│   ├── ObjectExplorerTree
│   ├── WorkspacePanel
│   ├── MissionControls
│   │   ├── TargetInput
│   │   └── MissionParameters
│   ├── MissionPlanning
│   │   ├── RepairDiffPanel
│   │   ├── ConflictWarningModal
│   │   └── RepairSettingsPresets
│   └── SchedulePanel
│       ├── AcceptedOrders (committed tab)
│       ├── ScheduleTimeline (timeline tab)
│       ├── ConflictsPanel (conflicts tab)
│       └── ScheduledAcquisitionsList
├── Center Canvas (LazyMultiViewContainer)
│   ├── CesiumViewer
│   ├── ObjectMapViewer
│   └── WhatIfCesiumControls
├── RightSidebar
│   ├── MissionResultsPanel
│   ├── Inspector
│   ├── Layers
│   └── AI Assistant (placeholder)
├── AdminPanel (modal)
└── LockToastContainer (fixed overlay)
```

---

## 2. Where Key Concepts Live

### Schedule / Acquisitions
- **Committed tab**: `SchedulePanel.tsx:84-91` → renders `AcceptedOrders.tsx`
- **Timeline tab**: `SchedulePanel.tsx:93-102` → renders `ScheduleTimeline.tsx`
- **Scheduled Acquisitions List**: `ScheduledAcquisitionsList.tsx` — reusable list with lock toggles, used inside schedule context

### Opportunities
- Currently embedded in `MissionResultsPanel.tsx` (right sidebar) — pass list after mission analysis
- Also shown in `MissionPlanning.tsx` results table after planning runs
- **No standalone "Opportunities" panel** exists currently

### Conflicts
- **Conflicts tab**: `SchedulePanel.tsx:103-114` → renders `ConflictsPanel.tsx`
- Conflict store: `store/conflictStore.ts` — Zustand store with summary counts
- Badge on Schedule icon: `LeftSidebar.tsx:418-425`

---

## 3. Duplication Points

| Data Concept | Location 1 | Location 2 | Location 3 |
|---|---|---|---|
| Pass/opportunity list | `MissionResultsPanel` (right) | `MissionPlanning` results table (left) | `ObjectExplorerTree` nodes |
| Schedule items | `SchedulePanel > AcceptedOrders` | `SchedulePanel > ScheduleTimeline` | `ScheduledAcquisitionsList` |
| Conflict counts | `conflictStore` badge on Schedule icon | `ConflictsPanel` tab | `SchedulePanel` tab badge |

---

## 4. Risks / Inconsistencies

1. **"Mission Results" on right sidebar shows opportunity list** that overlaps with the planning results on the left sidebar. Users may see the same passes in two panels.
2. **Conflicts tab in Schedule panel** — review team wants this removed from planner UX. Currently wired to `conflictStore` and displayed with badge.
3. **Schedule panel on left** — review team dislikes "schedule left" placement but says keep for now. The right sidebar has Mission Results (which is pass-level, not schedule-level).
4. **No dedicated "Opportunities" panel** — review wants right sidebar "Schedule" renamed to "Opportunities" with per-target dropdown counts.
5. **Object Explorer** shows algorithm results and orders in tree form — potential confusion with schedule list.

---

## 5. File References

| File | Key Lines | Purpose |
|---|---|---|
| `frontend/src/App.tsx` | 95-173 | Main layout: header + left + canvas + right + admin + toast |
| `frontend/src/components/LeftSidebar.tsx` | 334-447 | Panel definitions, filtering by UI mode |
| `frontend/src/components/RightSidebar.tsx` | 68-459 | Right panel definitions |
| `frontend/src/components/SchedulePanel.tsx` | 37-216 | Schedule tabs (committed, timeline, conflicts, history) |
| `frontend/src/constants/simpleMode.ts` | 30-103 | Panel IDs, simple mode filters, schedule tabs, collapsed defaults |
| `frontend/src/components/MissionResultsPanel.tsx` | 1-1212 | Right sidebar results (pass list, SAR filters, export) |
| `frontend/src/components/MissionPlanning.tsx` | 1-2106 | Left sidebar planning panel (config, results, repair) |
| `frontend/src/components/ConflictsPanel.tsx` | 1-~280 | Conflicts display panel |
| `frontend/src/store/conflictStore.ts` | 1-~80 | Zustand conflict summary store |

---

## 6. Recommended Minimal Change Strategy

1. **Remove Conflicts tab** from `SCHEDULE_TABS` and `SchedulePanel.tsx` tab array; move any critical conflict info to a badge/indicator only.
2. **Rename right sidebar "Mission Results"** to "Opportunities" and restructure content to show per-target opportunity counts with dropdowns.
3. **Consolidate duplication** by making `MissionResultsPanel` the single source of opportunity browsing, removing redundant pass table from `MissionPlanning.tsx`.
