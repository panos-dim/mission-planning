# PR Simple Mode 01 - Verification Checklist

**PR Title:** Implement Mission Planner Simple Mode  
**Date:** 2024-01-XX  
**Author:** Cascade AI  

## Overview

This PR implements the "Mission Planner Simple Mode" as defined in `UX_MINIMAL_SPEC.md` and quick fixes from `AUDIT_MISSION_PLANNER_READINESS.md`. The changes reduce UI noise, remove dead/partial panels, unify terminology, and harden user-facing error messages while keeping all existing functionality working.

## Changes Summary

### 1. Simple Mode UI Surface
- [x] Left sidebar enforces 4 panels visible by default: **Workspaces, Mission Analysis, Planning, Schedule**
- [x] Object Explorer hidden by default (only visible with `?debug=explorer` URL param)
- [x] Orders + Conflicts merged into unified **Schedule** panel with internal tabs (Committed, Conflicts)
- [x] Right sidebar shows only 3 panels: **Inspector, Layers, Help**
- [x] Properties, Data Window, Mission Results panels hidden by default

### 2. Dead UI Removed/Hidden
- [x] Properties panel sliders hidden (non-functional per audit)
- [x] Mission Results panel hidden (redundant with Planning panel)
- [x] Object Explorer conditionally hidden (incomplete sync per audit)

### 3. Terminology Unified
- [x] "Accept Plan → Orders" renamed to "**Commit to Schedule**"
- [x] "Accepted Orders" component displays as "**Committed Schedule**"
- [x] Button labels use consistent "Commit to Schedule" terminology

### 4. Error Message Hardening
- [x] Created `frontend/src/utils/errorMapper.ts` with user-friendly error templates
- [x] Maps common API failures to clear messages with suggested actions
- [x] Technical details logged to console only in dev mode

### 5. Large Table Performance
- [x] Results table pagination implemented (triggers when >50 rows)
- [x] Page size options: 25, 50, 100, 200 rows
- [x] Pagination controls with first/prev/next/last navigation

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/constants/simpleMode.ts` | **New** | Simple Mode configuration constants |
| `frontend/src/utils/errorMapper.ts` | **New** | User-friendly error message mapper |
| `frontend/src/components/SchedulePanel.tsx` | **New** | Unified Schedule panel with tabs |
| `frontend/src/components/LeftSidebar.tsx` | Modified | Simple Mode panel filtering |
| `frontend/src/components/RightSidebar.tsx` | Modified | Simple Mode panel filtering |
| `frontend/src/components/MissionPlanning.tsx` | Modified | Pagination for results table |

## User Journey Verification

Per `AUDIT_MISSION_PLANNER_READINESS.md`, verify these journeys still work:

### J1: First-time Analysis
- [ ] Open app → Mission Analysis panel visible
- [ ] Configure satellites and targets
- [ ] Set time window
- [ ] Run analysis → Results display correctly
- [ ] Map shows opportunities

### J2: Planning from Analysis
- [ ] After J1, switch to Planning panel
- [ ] Run planning algorithm
- [ ] Results table shows with pagination (if >50 rows)
- [ ] "Commit to Schedule" button visible
- [ ] Click commit → Preview modal appears
- [ ] Confirm commit → Schedule updates

### J3: Schedule Management
- [ ] Switch to Schedule panel
- [ ] **Committed** tab shows committed items
- [ ] **Conflicts** tab shows any conflicts
- [ ] Badge on Schedule icon shows conflict count (if any)

### J4: Conflict Resolution
- [ ] Create conflict scenario (overlapping acquisitions)
- [ ] Conflicts tab shows errors/warnings
- [ ] Use Repair mode in Planning panel
- [ ] Resolve conflicts → Badge clears

### J5: Workspace Save/Load
- [ ] Save workspace with committed schedule
- [ ] Reload page
- [ ] Load workspace → Schedule restored
- [ ] Planning state preserved

## Simple Mode Panel Verification

### Left Sidebar (Default View)
- [ ] Only 4 icons visible: Workspaces, Mission Analysis, Planning, Schedule
- [ ] Object Explorer NOT visible
- [ ] Schedule panel shows tabbed interface

### Left Sidebar (Debug Mode: `?debug=explorer`)
- [ ] Object Explorer icon appears
- [ ] All 5 panels accessible

### Right Sidebar (Default View)
- [ ] Only 3 icons visible: Inspector, Layers, Help
- [ ] Properties NOT visible
- [ ] Mission Results NOT visible
- [ ] Data Window NOT visible

## Table Performance Verification

- [ ] Run planning with <50 opportunities → No pagination shown
- [ ] Run planning with >50 opportunities → Pagination controls appear
- [ ] Page size dropdown works
- [ ] Navigation buttons (⟪ ← → ⟫) work correctly
- [ ] Row count display accurate (e.g., "showing 1-50")

## No Dead Paths Added

Per `frontend_nav_graph.json`, verify:
- [ ] All panel transitions work
- [ ] No broken links or missing components
- [ ] Tab navigation in Schedule panel functional

## Regression Checks

- [ ] TypeScript compiles without new errors
- [ ] ESLint passes (or only warnings)
- [ ] Existing unit tests pass
- [ ] API calls unchanged (no endpoint migrations)

## Not Included in This PR

Per spec requirements, the following are explicitly **NOT** part of this PR:
- Auto-run / background scheduling
- New planning algorithms
- New "orders inbox" workflow
- Endpoint migrations to /api/v1
- Major refactors

## Sign-off

- [ ] Code reviewed
- [ ] Tested locally with dev server
- [ ] Tested with large dataset (500+ opportunities)
- [ ] Documentation updated
- [ ] Ready for merge

---

## Quick Test Commands

```bash
# Start frontend dev server
cd frontend && npm run dev

# Run TypeScript check
cd frontend && npx tsc --noEmit

# Test with debug explorer
# Navigate to: http://localhost:5173/?debug=explorer
```
