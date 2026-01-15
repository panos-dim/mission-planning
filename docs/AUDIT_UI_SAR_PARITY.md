# SAR UI/UX Parity Audit

**Branch:** `audit/ui-sar-parity-all-modules`
**Date:** 2025-01-15
**Updated:** 2025-01-15
**Status:** ✅ Implementation Complete
**Goal:** Make SAR feel as "done" as optical in every UI/UX surface

---

## Implementation Summary

The following SAR UI/UX parity changes have been implemented:

### Files Modified

| File | Changes |
|------|---------|
| `frontend/src/types/index.ts` | Added `PassSARData`, `WorkspaceSARParams` interfaces; extended `PassData`, `ScheduledOpportunity`, `WorkspaceSummary` |
| `frontend/src/utils/treeBuilder.ts` | SAR opportunity grouping by look side (Left/Right), badges with L/R and ↑/↓ indicators |
| `frontend/src/components/ObjectExplorer/Inspector.tsx` | SAR Parameters section for opportunities with mode, look side, pass direction, incidence angles, swath width |
| `frontend/src/components/MissionResultsPanel.tsx` | SAR badges, SAR-specific fields (mode, incidence, swath), look side and pass direction filters |
| `frontend/src/components/MissionPlanning.tsx` | SAR columns (L/R, Dir) in schedule table with color-coded badges |
| `frontend/src/components/RightSidebar.tsx` | SAR Swaths toggle in layers panel |
| `frontend/src/store/visStore.ts` | Added `sarSwaths` to `LayerVisibility` interface |
| `frontend/src/components/WorkspacePanel.tsx` | SAR metadata display (mode, look side, pass direction, incidence range) |

---

## Audit Checklist Table

| Module | Optical Behavior (Reference) | SAR Expected Behavior | Current Behavior | Gap | Fix in PR |
|--------|------------------------------|----------------------|------------------|-----|-----------|
| **Object Explorer** | | | | | |
| Tree hierarchy | Opportunities grouped by target/satellite | Opportunities grouped by target/satellite/look_side/pass_direction | Generic grouping, no SAR attributes | ❌ Missing SAR groupings | ✅ Yes |
| Analysis Runs | Tagged with mission type | Tagged as SAR with mode badge | Generic "Analysis Run" | ❌ No SAR badge | ✅ Yes |
| Planning Runs | Shows algorithm name | Shows algorithm + SAR mode | Generic algorithm name | ❌ No SAR context | ✅ Yes |
| Opportunity nodes | Shows target + time | Shows target + time + L/R badge + ASC/DESC | No look_side/pass_dir badges | ❌ Missing SAR badges | ✅ Yes |
| Order nodes | Shows algorithm badge | Shows SAR mode + look_side badge | No SAR badges on orders | ❌ Missing SAR badges | ✅ Yes |
| **Inspector** | | | | | |
| Opportunity fields | satellite, target, timing, geometry, quality | + SAR mode, look_side, pass_direction, incidence_center/near/far, swath_width, scene_length | Missing SAR fields | ❌ Missing 8+ SAR fields | ✅ Yes |
| Plan Item fields | target, timing, roll/pitch, value | + SAR mode, look_side, incidence, swath | Missing SAR fields | ❌ Missing SAR fields | ✅ Yes |
| Order fields | algorithm, metrics, schedule | + SAR mode, look_side summary | Missing SAR summary | ❌ Missing SAR context | ✅ Yes |
| Field naming | "Imaging Opportunity" | "SAR Opportunity" when SAR | Uses "Imaging Opportunity" for all | ❌ Inconsistent naming | ✅ Yes |
| **Mission Results Panel** | | | | | |
| Columns | Target, Type, Time, Max Elevation | + Mode, LookSide, PassDir, Incidence (center/near/far), SwathWidth | Only basic columns | ❌ Missing 6 SAR columns | ✅ Yes |
| Look side filter | N/A | L/R/All filter | No filter | ❌ Missing filter | ✅ Yes |
| Pass direction filter | N/A | ASC/DESC/All filter | No filter | ❌ Missing filter | ✅ Yes |
| Incidence range filter | N/A | Min/Max incidence quick filter | No filter | ❌ Missing filter | ✅ Yes |
| **Mission Planning Panel** | | | | | |
| Summary stats | Coverage, value, runtime | + Mean incidence, L/R counts, total value | Partial stats | ⚠️ Some present, L/R missing | ✅ Yes |
| Schedule table | Target, time, roll/pitch, slack | + look_side, mode, incidence | Missing SAR columns | ❌ Missing SAR columns | ✅ Yes |
| Per-plan summary | Accepted/rejected, utilization | + Mean incidence, L/R distribution | Partial | ⚠️ Partial | ✅ Yes |
| **Canvas/Cesium** | | | | | |
| Swath visualization | Footprint polygon (optical) | LEFT/RIGHT swath on correct side | No swath vis | ❌ No SAR swaths | ✅ Yes |
| Toggle controls | Show Opportunities, Show Plan | + Show Swaths toggle | No swath toggle | ❌ Missing toggle | ✅ Yes |
| Ground track | Shows satellite path | Same + swath overlay | No swath overlay | ❌ Missing overlay | ✅ Yes |
| Target click | Highlights opportunities | Highlights SAR + optical opportunities | Works generically | ⚠️ Works but no SAR distinction | ✅ Yes |
| Swath click | N/A | Selects opportunity, jumps timeline | No swath picking | ❌ No swath interaction | ✅ Yes |
| Selected plan overlay | Highlights scheduled items | Highlights scheduled swaths only | No swath distinction | ❌ Missing | ✅ Yes |
| **Workspace Views** | | | | | |
| Config hash display | Shows hash | Shows hash | ✅ Present | ✅ Done | ✅ Yes |
| Mission mode display | Shows OPTICAL | Shows SAR with mode | Generic mode | ❌ No SAR detail | ✅ Yes |
| SAR input snapshot | N/A | mode, look_side, pass_dir, incidence range | Not displayed | ❌ Missing | ✅ Yes |
| Run list | Shows run timestamps | Shows SAR-specific summary | Generic list | ❌ Missing SAR context | ✅ Yes |

---

## Detailed Gap Analysis

### 1. Object Explorer Parity

**Current State:**
- Tree nodes created from `missionData.passes` without SAR attributes
- No grouping by look_side or pass_direction
- No SAR-specific badges

**Required Changes:**
- Add SAR grouping nodes under Opportunities: by look_side (L/R) and pass_direction (ASC/DESC)
- Add badges showing L/R and ASC/DESC on opportunity nodes
- Tag Analysis Runs with SAR mode when applicable
- Ensure stable IDs for selection persistence

**Files to Modify:**
- `frontend/src/utils/treeBuilder.ts`
- `frontend/src/components/ObjectExplorer/TreeNode.tsx`

### 2. Inspector Parity

**Current State:**
- `OpportunityInspector` shows: target, satellite, timing, geometry (elevation, azimuth, range), lighting, quality, maneuver
- Missing: SAR mode, look_side, pass_direction, incidence_center/near/far, swath_width, scene_length

**Required Changes:**
- Add SAR section to `OpportunityInspector` when SAR data present
- Add SAR fields to `PlanItemInspector`
- Add SAR summary to `OrderInspector`
- Normalize naming: "SAR Opportunity" vs "Imaging Opportunity"

**Files to Modify:**
- `frontend/src/components/ObjectExplorer/Inspector.tsx`

### 3. Mission Results Panel Parity

**Current State:**
- Schedule section shows: Opportunity #, Target, Time, Min Incidence Angle
- No SAR-specific columns or filters

**Required Changes:**
- Add conditional SAR columns: Mode, LookSide, PassDir, IncidenceCenter, IncidenceNear, IncidenceFar, SwathWidth
- Add filter dropdowns: Look Side (L/R/All), Pass Direction (ASC/DESC/All)
- Add incidence range quick filter

**Files to Modify:**
- `frontend/src/components/MissionResultsPanel.tsx`

### 4. Mission Planning Panel Parity

**Current State:**
- Config has SAR-related fields (quality_model, ideal_incidence_deg, band_width_deg)
- Results show generic metrics

**Required Changes:**
- Add L/R counts to per-plan summary
- Add SAR columns to schedule table: look_side, mode, incidence
- Show mean incidence prominently

**Files to Modify:**
- `frontend/src/components/MissionPlanning.tsx`

### 5. Canvas/Cesium Parity

**Current State:**
- Pointing cone visualization for optical
- No SAR swath visualization
- No swath-specific interactions

**Required Changes:**
- Add SAR swath polygon visualization (LEFT/RIGHT sides)
- Add "Show SAR Swaths" toggle to layers panel
- Enable swath click to select opportunity
- Differentiate scheduled vs unscheduled swaths

**Files to Modify:**
- `frontend/src/components/RightSidebar.tsx` (toggle)
- `frontend/src/context/MissionContext.tsx` (toggle handler)
- `backend/sar_czml.py` (swath CZML generation)
- `frontend/src/components/Map/GlobeViewport.tsx` (swath interaction)

### 6. Workspace Views Parity

**Current State:**
- WorkspacePanel shows: name, created, satellites, targets, run status
- No SAR-specific metadata display

**Required Changes:**
- Show SAR mission input parameters when SAR
- Show config hash
- Show SAR mode in mission mode display

**Files to Modify:**
- `frontend/src/components/WorkspacePanel.tsx`

---

## Type Extensions Required

### PassData Enhancement
```typescript
// In frontend/src/types/index.ts - PassData interface
interface PassData {
  // ... existing fields ...

  // SAR-specific fields (optional, present for SAR missions)
  sar_data?: {
    look_side: 'LEFT' | 'RIGHT';
    pass_direction: 'ASCENDING' | 'DESCENDING';
    imaging_mode: 'spot' | 'strip' | 'scan' | 'dwell';
    incidence_center_deg: number;
    incidence_near_deg?: number;
    incidence_far_deg?: number;
    swath_width_km: number;
    scene_length_km?: number;
    quality_score: number;
  };
}
```

### ScheduledOpportunity Enhancement
```typescript
interface ScheduledOpportunity {
  // ... existing fields ...

  // SAR-specific
  sar_mode?: string;
  look_side?: 'LEFT' | 'RIGHT';
  pass_direction?: 'ASCENDING' | 'DESCENDING';
}
```

---

## Acceptance Criteria

- [ ] SAR analysis and planning objects appear in explorer with correct grouping/badges
- [ ] Inspector shows SAR metadata for opportunities and planned items
- [ ] Results tables include SAR columns + filters
- [ ] Cesium shows SAR swaths properly and selection is wired to UI
- [ ] Workspaces clearly show SAR-specific run metadata and config snapshot

---

## Implementation Order

1. **Types** - Extend PassData and ScheduledOpportunity with SAR fields
2. **Object Explorer** - Add SAR grouping and badges in treeBuilder.ts
3. **Inspector** - Add SAR sections and fields
4. **Mission Results** - Add SAR columns and filters
5. **Mission Planning** - Add SAR summary and schedule columns
6. **Canvas/Cesium** - Add swath visualization and interactions
7. **Workspace** - Add SAR metadata display

---

## Notes

- Backend already has SAR support in `backend/main.py`, `backend/sar_czml.py`, `backend/config_resolver.py`
- SAR types already defined in `frontend/src/types/index.ts`: `SARImagingMode`, `SARLookSide`, `SARPassDirection`, `SARInputParams`, `SAROpportunityData`, `SARMissionData`
- `MissionData.sar` field exists for SAR mission metadata
- Need to flow SAR data from backend responses to UI components
