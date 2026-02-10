# Mission Planner Readiness Audit

**Branch:** `audit/mission-planner-readiness-e2e`  
**Date:** 2026-02-05  
**Scope:** End-to-end audit of frontend, API, DB, and scheduling wiring

---

## 1. System Map (Single Page)

### Frontend Routes → UI Components → API Endpoints → Backend Handlers → DB Tables

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (React + TypeScript)                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ App.tsx                                                                             │
│   ├── LeftSidebar.tsx (6 panels)                                                    │
│   │     ├── ObjectExplorerTree      [No direct API - uses MissionContext state]     │
│   │     ├── WorkspacePanel          → /api/v1/workspaces/*                          │
│   │     ├── MissionControls         → /api/analyze, /api/satellites, /api/targets   │
│   │     ├── MissionPlanning         → /api/planning/schedule, /api/v1/schedule/*    │
│   │     ├── AcceptedOrders          → /api/v1/schedule/commit/direct                │
│   │     └── ConflictsPanel          → /api/v1/schedule/conflicts                    │
│   ├── MultiViewContainer (Cesium)                                                   │
│   │     └── CesiumViewer.tsx        [Uses CZML from MissionContext]                 │
│   ├── RightSidebar.tsx (6 panels)                                                   │
│   │     ├── Inspector               [Local state from selection]                    │
│   │     ├── MissionResultsPanel     [Uses MissionContext state]                     │
│   │     ├── Layers                  [Local state + visStore]                        │
│   │     ├── Data Window             [Uses MissionContext state]                     │
│   │     ├── Properties              [Local UI state]                                │
│   │     └── Information             [Static help content]                           │
│   └── AdminPanel.tsx                → /api/config/*, /api/satellites, /api/v1/batches│
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND (FastAPI + Python)                             │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ main.py (includes routers)                                                          │
│   ├── workspaces_router   → /api/v1/workspaces                                      │
│   ├── validation_router   → /api/v1/validation                                      │
│   ├── config_admin_router → /api/v1/config, /api/satellites, /api/config/*          │
│   ├── schedule_router     → /api/v1/schedule                                        │
│   ├── orders_router       → /api/v1/orders                                          │
│   └── batching_router     → /api/v1/batches                                         │
│                                                                                     │
│ Direct endpoints in main.py:                                                        │
│   ├── POST /api/analyze         → Mission analysis with CZML generation             │
│   ├── GET  /api/satellites      → List configured satellites                        │
│   ├── GET  /api/targets         → List targets                                      │
│   ├── POST /api/planning/schedule → Run scheduling algorithms                       │
│   └── GET  /api/planning/opportunities → Get cached opportunities                   │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              DATABASE (SQLite)                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ data/workspaces.db (Schema v2.1)                                                    │
│                                                                                     │
│ Tables:                                                                             │
│   ├── workspaces          - Saved workspace state (scenario, analysis, orders)      │
│   ├── orders              - User imaging requests with lifecycle state              │
│   ├── order_batches       - Batch groupings for planning                            │
│   ├── batch_members       - Order-to-batch relationships                            │
│   ├── acquisitions        - Committed schedule slots (the truth)                    │
│   ├── plans               - Candidate schedules                                     │
│   ├── plan_items          - Individual scheduled opportunities in a plan            │
│   ├── conflicts           - Detected scheduling conflicts                           │
│   └── commit_audit_log    - Audit trail for commit operations                       │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Data Flows

| Flow | UI Entry Point | API Call | DB Operation |
|------|----------------|----------|--------------|
| **Analysis** | MissionControls → "Analyze" | POST /api/analyze | None (in-memory + CZML) |
| **Planning** | MissionPlanning → "Run Planning" | POST /api/planning/schedule | Creates Plan + PlanItems |
| **Commit** | MissionPlanning → "Accept Plan" | POST /api/v1/schedule/commit/direct | Creates Acquisitions |
| **Horizon View** | ConflictsPanel (auto) | GET /api/v1/schedule/horizon | Reads Acquisitions |
| **Conflicts** | ConflictsPanel | GET /api/v1/schedule/conflicts | Reads Conflicts |
| **Repair** | MissionPlanning (repair mode) | POST /api/v1/schedule/repair | Reads Acquisitions |
| **Repair Commit** | RepairCommitModal | POST /api/v1/schedule/repair/commit | Updates Acquisitions |
| **Workspace Save** | WorkspacePanel | POST /api/v1/workspaces/save-current | Writes Workspace |
| **Workspace Load** | WorkspacePanel | GET /api/v1/workspaces/{id} | Reads Workspace |

---

## 2. Dead Path Report

### ✅ UI Buttons/Tabs That ARE Connected

| UI Element | Location | Status |
|------------|----------|--------|
| Analyze Mission | MissionControls | ✅ Calls POST /api/analyze |
| Run Planning | MissionPlanning | ✅ Calls POST /api/planning/schedule |
| Accept Plan → Orders | MissionPlanning | ✅ Calls commitScheduleDirect |
| Save Workspace | WorkspacePanel | ✅ Calls saveCurrentMission |
| Load Workspace | WorkspacePanel | ✅ Calls getWorkspace |
| Recompute Conflicts | ConflictsPanel | ✅ Calls recomputeConflicts |
| Export CSV/JSON | AcceptedOrders | ✅ Client-side export |

### ⚠️ UI Elements with Partial/Limited Wiring

| UI Element | Location | Issue |
|------------|----------|-------|
| Properties sliders | RightSidebar | ⚠️ UI exists but sliders have no effect (defaultValue only) |
| Object Explorer selection | ObjectExplorerTree | ⚠️ Selection logged but map sync incomplete for all node types |
| Timeline click sync | MissionResultsPanel | ⚠️ Works for time jump, but swath highlight not always synced |

### ❌ Dead/Orphaned Code Identified

| Item | Location | Recommendation |
|------|----------|----------------|
| `algorithmNames` map includes "first_fit", "best_fit", "optimal" | AcceptedOrders.tsx:10-14 | **KEEP** - legacy orders may have these values |
| `WEIGHT_PRESETS` in MissionPlanning | MissionPlanning.tsx:124-169 | ✅ Used - apply preset function is called |
| `editingOrderId` state | AcceptedOrders.tsx | ✅ Used - inline rename functionality |

### API Endpoints Not Used by UI

| Endpoint | Router | Status |
|----------|--------|--------|
| POST /api/v1/orders | orders.py | ⚠️ Create order endpoint exists but UI uses "promote" flow instead |
| POST /api/v1/orders/import | orders.py | ⚠️ Bulk import exists but no UI (only API use) |
| GET /api/v1/orders/inbox | orders.py | ⚠️ Inbox scoring - no dedicated UI panel |
| POST /api/v1/orders/{id}/reject | orders.py | ⚠️ Reject endpoint - no UI button |
| POST /api/v1/orders/{id}/defer | orders.py | ⚠️ Defer endpoint - no UI button |
| POST /api/v1/batches/create | batching.py | ⚠️ Batch planning - AdminPanel has partial UI |
| POST /api/v1/batches/{id}/plan | batching.py | ⚠️ Batch plan - AdminPanel only |
| POST /api/v1/batches/{id}/commit | batching.py | ⚠️ Batch commit - AdminPanel only |

### DB Tables Read/Write Analysis

| Table | Written By | Read By | Status |
|-------|------------|---------|--------|
| workspaces | WorkspacePanel save | WorkspacePanel load | ✅ Active |
| orders | commitScheduleDirect (indirect) | Not directly read by UI | ⚠️ Underused |
| acquisitions | commitScheduleDirect, repair commit | horizon, conflicts | ✅ Active |
| plans | planning endpoints | horizon (plan_id ref) | ✅ Active |
| plan_items | planning endpoints | commit operations | ✅ Active |
| conflicts | recomputeConflicts | ConflictsPanel | ✅ Active |
| commit_audit_log | repair commit | Not exposed in UI | ⚠️ Admin only |
| order_batches | batching endpoints | AdminPanel | ⚠️ Admin only |
| batch_members | batching endpoints | AdminPanel | ⚠️ Admin only |

### localStorage Keys in Use

| Key | Used By | Purpose | Status |
|-----|---------|---------|--------|
| `acceptedOrders` | LeftSidebar | Persist accepted orders across sessions | ⚠️ Legacy - should migrate to DB |
| `selectedSatellites` | MissionControls | Remember constellation selection | ✅ Valid UX |
| `selectedSatellite` | MissionControls | Legacy single satellite | ⚠️ Deprecated |
| `selectedSatelliteId` | MissionControls | Admin selection tracking | ✅ Valid |

---

## 3. Critical User Journeys

### J1: Create/Load Workspace → Run Analysis → View Opportunities

**Steps:**
1. User opens app → `App.tsx` renders with LeftSidebar defaulting to "mission" panel
2. User clicks "Workspaces" icon → `WorkspacePanel.tsx` loads
3. (Option A) Click "Save Current" → calls `saveCurrentMission()` in `@/api/workspaces.ts:183`
4. (Option B) Click workspace card "Load" → calls `getWorkspace()` in `@/api/workspaces.ts:59`
5. Workspace load calls `handleWorkspaceLoad()` in `LeftSidebar.tsx:77` which:
   - Dispatches `SET_SCENE_OBJECTS` to MissionContext
   - Dispatches `SET_ACTIVE_WORKSPACE`
   - Restores `SET_MISSION_DATA` if available
   - Restores planning results via `usePlanningStore`
6. User clicks "Mission Analysis" icon → `MissionControls.tsx` renders
7. User configures satellites (from Admin selection) and targets
8. User clicks "Analyze Mission" → `handleAnalyzeMission()` at `MissionControls.tsx:293`
9. Calls POST `/api/analyze` → `backend/main.py` endpoint
10. Response with CZML data dispatched to MissionContext
11. CesiumViewer auto-updates to show satellite orbit and targets

**Code Locations:**
- `@/components/WorkspacePanel.tsx:124` - handleLoad
- `@/components/LeftSidebar.tsx:77` - handleWorkspaceLoad
- `@/components/MissionControls.tsx:293` - handleAnalyzeMission
- `@/context/MissionContext.tsx` - analyzeMission action
- `backend/main.py` - /api/analyze endpoint

**Status:** ✅ **WORKING** - Full path verified

---

### J2: Plan (Incremental) → View Plan → Commit → Horizon Reflects Change

**Steps:**
1. After J1, user clicks "Mission Planning" icon → `MissionPlanning.tsx`
2. User selects "Incremental" mode → sets `planningMode = "incremental"`
3. Schedule context loads via `loadScheduleContext()` at line 231
4. User clicks "Run Planning" → `handleRunPlanning()` at line 280
5. For incremental: POST `/api/planning/schedule` with mode flag
6. Results stored in `usePlanningStore` and displayed in table
7. User clicks "Accept Plan → Orders" → `handleAcceptPlan()` at line 453
8. Shows `ConflictWarningModal` with commit preview
9. User clicks "Commit" → `handleConfirmCommit()` at line 478
10. Calls `commitScheduleDirect()` in `@/api/scheduleApi.ts:104`
11. Backend creates acquisitions in DB
12. User opens "Conflicts" panel → `ConflictsPanel.tsx`
13. Panel auto-fetches via `getConflicts()` which reads acquisitions from horizon

**Code Locations:**
- `@/components/MissionPlanning.tsx:280` - handleRunPlanning
- `@/components/MissionPlanning.tsx:453` - handleAcceptPlan
- `@/components/LeftSidebar.tsx:212` - handlePromoteToOrders
- `@/api/scheduleApi.ts:104` - commitScheduleDirect
- `backend/routers/schedule.py:767` - commit_plan endpoint

**Status:** ✅ **WORKING** - Full commit flow verified

---

### J3: Conflicts Appear → Inspect → Resolve via Repair → Commit Repair

**Steps:**
1. User has committed acquisitions with conflicts
2. User clicks "Conflicts" icon → `ConflictsPanel.tsx`
3. `fetchConflicts()` called at line 45 → GET `/api/v1/schedule/conflicts`
4. Conflicts displayed with severity badges (error/warning)
5. User clicks a conflict → `handleConflictClick()` at line 113
6. `selectConflict()` updates `useConflictStore` with highlighted acquisition IDs
7. User switches to "Mission Planning" and selects "Repair" mode
8. User clicks "Run Planning" → calls `createRepairPlan()` at `@/api/scheduleApi.ts:687`
9. Repair result shows `RepairDiffPanel` with kept/dropped/added counts
10. User clicks "Commit Repair" → opens `RepairCommitModal.tsx`
11. Modal shows score delta, conflict predictions, force checkbox if needed
12. User clicks "Commit" → calls `commitRepairPlan()` at `@/api/scheduleApi.ts:853`
13. Backend atomically drops old acquisitions, creates new ones

**Code Locations:**
- `@/components/ConflictsPanel.tsx:45` - fetchConflicts
- `@/store/conflictStore.ts:65` - selectConflict
- `@/components/MissionPlanning.tsx:287` - repair mode handling
- `@/components/RepairDiffPanel.tsx` - diff visualization
- `@/components/RepairCommitModal.tsx:49` - handleCommit
- `backend/routers/schedule.py` - repair endpoints

**Status:** ✅ **WORKING** - Repair flow complete

---

### J4: SAR Workflow Parity with Optical

**Steps:**
1. User configures SAR mode in MissionControls (`imagingType: "sar"`)
2. Analysis returns SAR-specific pass data with look_side, pass_direction
3. MissionPlanning shows SAR fields in schedule table (sar_mode, look_side, incidence)
4. Commit includes SAR fields: `DirectCommitItem` has sar_mode, look_side, pass_direction
5. Explorer shows SAR-specific metadata in Inspector
6. Cesium shows SAR swath geometry (via SwathLayerControl)

**SAR Field Verification:**

| Field | API Request | API Response | DB Column | UI Display |
|-------|-------------|--------------|-----------|------------|
| sar_mode | ✅ DirectCommitItem | ✅ Acquisition | ✅ acquisitions.sar_mode | ✅ MissionPlanning table |
| look_side | ✅ DirectCommitItem | ✅ Acquisition | ✅ acquisitions.look_side | ✅ MissionPlanning table |
| pass_direction | ✅ DirectCommitItem | ✅ Acquisition | ✅ acquisitions.pass_direction | ✅ MissionPlanning table |
| incidence_angle | ✅ DirectCommitItem | ✅ Acquisition | ✅ acquisitions.incidence_angle_deg | ✅ Column in table |

**Status:** ✅ **PARITY ACHIEVED** - SAR fields flow end-to-end

---

## 4. UX Simplicity Recommendations

### What to Remove/Hide by Default

| Item | Current Location | Recommendation |
|------|------------------|----------------|
| Properties panel sliders | RightSidebar | **HIDE** - Non-functional, confusing |
| Algorithm debug stats | MissionPlanning | **COLLAPSE** into "Advanced" |
| Batch planning UI | AdminPanel | **ADMIN ONLY** - Not for mission planners |
| Policy editor | AdminPanel | **ADMIN ONLY** |
| Config editor tabs | AdminPanel | **ADMIN ONLY** |
| Verbose console logging | Multiple | **DEV ONLY** - Use debug flag |

### What to Rename (Consistency)

| Current | Proposed | Reason |
|---------|----------|--------|
| "Accept Plan → Orders" | "Commit to Schedule" | Clearer action |
| "AcceptedOrders" component | "CommittedSchedule" | Matches terminology |
| "Promote to Orders" | "Commit Plan" | Consistent with DB terms |
| "Opportunities" | "Acquisition Windows" | Mission planner language |

### What to Collapse

| Current | Recommendation |
|---------|----------------|
| Planning mode toggles (3) | Show "Standard" by default, "Advanced" accordion for incremental/repair |
| Weight preset + manual sliders | Show presets only, "Custom" expands sliders |
| Lock policy options | Hide in "Advanced" accordion |
| Repair settings | Hide in "Advanced" accordion when repair mode selected |

### Maximum Recommended Surface Area Per Panel

| Panel | Current Items | Recommended Max | Action |
|-------|---------------|-----------------|--------|
| Mission Analysis | 8+ input groups | 5 | Collapse satellite/target configs |
| Mission Planning | 15+ controls | 8 | Hide advanced in accordion |
| Inspector | Variable | 12 fields | Paginate or scroll |
| Conflicts | Good | Good | No change |

---

## 5. Readiness Scorecard

| Category | Status | Notes |
|----------|--------|-------|
| **Data Integrity** | ✅ Ready | Atomic commits, audit logging, config hash tracking |
| **Determinism & Reproducibility** | ✅ Ready | Config snapshot saved with workspace, input_hash on plans |
| **UX Clarity** | ⚠️ Risk | Too many exposed controls; needs "simple mode" |
| **Performance (Large Scenarios)** | ⚠️ Risk | No pagination in results table; may lag with 500+ opportunities |
| **SAR Parity** | ✅ Ready | All SAR fields flow through complete stack |
| **Error Messages** | ⚠️ Risk | Some errors show raw "HTTP 500"; need user-friendly messages |

### Detailed Scores

#### Data Integrity: ✅ Ready
- Transactions used for commit operations
- Audit log captures all commits with before/after metrics
- Config hash stored for reproducibility
- Workspace save includes full state snapshot

#### Determinism: ✅ Ready
- `input_hash` on plans enables reproducibility checks
- Config snapshot stored with workspace
- Algorithm uses deterministic scheduling (no random in production)

#### UX Clarity: ⚠️ Risk
- Too many visible controls for mission planner role
- Planning modes (3) shown simultaneously
- Advanced settings not collapsed
- **Action Required:** Implement "Simple Mode" defaults

#### Performance: ⚠️ Risk
- Results table renders all rows (no virtualization)
- Large CZML can slow Cesium
- No limit on opportunities display
- **Action Required:** Add pagination or virtualization for >100 items

#### SAR Parity: ✅ Ready
- SAR fields in request, response, DB, and UI
- Swath visualization working
- Look side filter working

#### Error Messages: ⚠️ Risk
- API errors sometimes show raw detail
- "Unknown error" fallback too generic
- Missing specific messages for:
  - No opportunities generated
  - Commit rejected due to hard locks
  - Invalid SAR mode
- **Action Required:** Add error code mapping to user-friendly messages

---

## 6. Mission Planner Simple Mode (Proposed)

### Default Sidebar (Max 4 visible):

1. **Workspaces** - Load/save session state
2. **Analysis** - Configure and run mission analysis
3. **Planning** - Run scheduler, review results, commit
4. **Schedule** - View committed acquisitions + conflicts (combined)

### Hidden in Advanced / Dev:

- Object Explorer (dev debugging)
- Batch planning (admin workflow)
- Policy editor (admin)
- Config editor (admin)
- Algorithm debug stats
- Verbose planning mode options

### Verification: Hidden Items Still Work

| Hidden Item | Activation Method | Verified |
|-------------|-------------------|----------|
| Object Explorer | Enable in settings or URL param `?debug=explorer` | ⬜ TODO |
| Batch planning | Admin Panel access | ✅ Works |
| Repair mode | "Advanced" accordion in Planning panel | ⬜ TODO |
| Debug overlays | Ctrl+Shift+D keyboard shortcut | ✅ Works |

---

## 7. Quick Fixes Recommended for This PR

### 7.1 Remove/Hide Dead UI

| Fix | File | Line | Action |
|-----|------|------|--------|
| Hide Properties sliders | RightSidebar.tsx | 223-263 | Wrap in `{DEV_MODE && ...}` |
| Hide batch UI for non-admin | AdminPanel.tsx | - | Add role check |

### 7.2 Fix Broken Links/Wiring

| Issue | File | Fix |
|-------|------|-----|
| Orders inbox not exposed | - | **DEFER** - requires new UI panel |
| Reject/Defer buttons missing | - | **DEFER** - requires new UI |

### 7.3 Terminology Unification

| File | Current | Change To |
|------|---------|-----------|
| LeftSidebar.tsx:389 | "Orders" | "Schedule" |
| AcceptedOrders.tsx:114 | "Accepted Orders" | "Committed Schedule" |
| MissionPlanning.tsx | "Accept This Plan" | "Commit to Schedule" |

### 7.4 Add Missing Error Messages

| Error Case | Current | Proposed |
|------------|---------|----------|
| No opportunities | Silent 404 | "No imaging windows found. Check constraints and time range." |
| Commit conflict | Raw error | "Cannot commit: overlapping acquisition exists. Use Repair mode." |
| Hard lock block | Generic | "Cannot modify: acquisition is hard-locked." |

---

## Appendix A: Frontend Navigation Graph

See `frontend_nav_graph.json` in the same directory for machine-readable graph.

## Appendix B: API Surface Table

See `docs/API_SURFACE_USED_BY_UI.md` for complete endpoint mapping.

## Appendix C: UX Minimal Spec

See `docs/UX_MINIMAL_SPEC.md` for "mission planner mode" specification.
