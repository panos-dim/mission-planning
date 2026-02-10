# PR-LOCK-OPS-01 — Hard-Lock Actions Everywhere

## Summary

Hard-lock controls (`hard` / `none`) across Timeline, Inspector, and Repair Report.
Planners can lock acquisitions they want to preserve, then re-run repair to reshape everything else.

**Lock levels**: `none` (fully flexible) | `hard` (immutable, never touched by repair)

---

## Architecture

| Layer | File | Role |
| ----- | ---- | ---- |
| Store | `frontend/src/store/lockStore.ts` | Zustand store — optimistic lock state, API calls, rollback, toasts |
| Toast | `frontend/src/components/LockToast.tsx` | Lightweight fixed-position toast for lock feedback |
| Timeline | `frontend/src/components/ScheduleTimeline.tsx` | Lock toggle button on each `TimelineCard` |
| Panel | `frontend/src/components/SchedulePanel.tsx` | Merges lockStore levels into timeline acquisitions |
| Inspector | `frontend/src/components/ObjectExplorer/Inspector.tsx` | Lock control section for selected acquisitions |
| Repair | `frontend/src/components/RepairDiffPanel.tsx` | Per-row lock buttons + bulk lock actions |
| API | `frontend/src/api/scheduleApi.ts` | `updateAcquisitionLock`, `bulkUpdateLocks` (pre-existing) |
| Backend | `backend/routers/schedule.py` | `PATCH /acquisition/{id}/lock`, `POST /acquisitions/bulk-lock` (pre-existing) |

### Design decisions

- **Repair-preview guard**: When an acquisition is selected from the Repair Report (source = `"repair"`), the Inspector shows "Locking available after commit" instead of a toggle. Only committed acquisitions can be locked.
- **Optimistic UI**: Lock state updates immediately in the store. On API error, the store rolls back to the previous level and shows an error toast.
- **Visual language**: `Shield` icon = locked/hard (red palette), `Unlock` icon = unlocked/none (gray palette). Consistent across all surfaces.
- **No new endpoints**: Uses existing `update_acquisition_lock` and `bulk_update_lock` backend endpoints.

---

## Verification Checklist

### 1. Timeline lock toggle

- [ ] Each acquisition card in Timeline shows a lock icon button (appears on hover when unlocked)
- [ ] Clicking the lock icon toggles between `none` → `hard` and `hard` → `none`
- [ ] Locked card shows "Locked" badge and red-tinted background
- [ ] Lock toggle stops propagation (does not select the card)
- [ ] Optimistic update: card updates immediately before API response
- [ ] On API error: card reverts to previous state, error toast appears

### 2. Inspector lock control

- [ ] Selecting an acquisition (from Timeline or table) opens Inspector with "Lock Control" section
- [ ] Lock Control shows current state (`Hard Locked` / `Unlocked`) with toggle button
- [ ] Clicking the toggle calls `toggleLock` and updates state
- [ ] When acquisition is selected from Repair Report (preview): shows "Locking available after commit" message instead of toggle
- [ ] Pending state disables the button (no double-click)

### 3. Repair Report — per-row lock actions

- [ ] **Kept** items: Shield icon button per row, toggles lock on click
- [ ] **Moved** items: Shield icon button per row, toggles lock on click
- [ ] **Added** items: Disabled Lock icon with "Lock after commit" tooltip
- [ ] **Dropped** items: No lock button (item is being removed)
- [ ] Locked items show filled red shield icon

### 4. Repair Report — bulk lock actions

- [ ] "Lock all Kept (N)" button appears in bulk actions bar
- [ ] "Lock Kept + Moved (N)" button appears in bulk actions bar
- [ ] Clicking "Lock all Kept" calls `bulkSetLockLevel` for all kept IDs not already locked
- [ ] Clicking "Lock Kept + Moved" calls `bulkSetLockLevel` for all kept + moved IDs not already locked
- [ ] Success toast shows count of locked items
- [ ] On partial failure: failed items roll back, success toast + error toast both appear
- [ ] Buttons disabled when no items in respective categories

### 5. Repair respects hard locks after re-run

- [ ] After locking items and re-running repair, locked items remain in "kept" category
- [ ] Repair only rearranges unlocked items
- [ ] Backend validates lock levels and refuses to move hard-locked acquisitions

### 6. Error handling

- [ ] "Lock update failed, please retry" toast on generic API error
- [ ] "Cannot unlock executed acquisition" toast when backend returns that specific error
- [ ] "Acquisition not found" toast when acquisition doesn't exist
- [ ] "Bulk lock update failed, please retry" toast on bulk API error
- [ ] Toasts auto-dismiss after 3 seconds
- [ ] Toasts can be manually dismissed via X button

### 7. Visual consistency

- [ ] `Shield` icon (red) used for locked state across Timeline, Inspector, Repair Report
- [ ] `Unlock` icon (gray) used for unlocked state
- [ ] `Lock` icon (gray, disabled) used for "lock after commit" state on Added items
- [ ] "Locked" badge in Timeline uses `bg-red-900/40 text-red-300 border-red-800/30`
- [ ] Locked cards have subtle red-tinted background (`bg-red-950/20`)
- [ ] Lock button hidden by default on unlocked cards, appears on hover (`group-hover:opacity-100`)

---

## Files changed

### New files

- `frontend/src/store/lockStore.ts` — Lock state management store
- `frontend/src/components/LockToast.tsx` — Toast notification component
- `docs/PR_LOCK_OPS_01_CHECKLIST.md` — This checklist

### Modified files

- `frontend/src/App.tsx` — Added `LockToastContainer` for global toast rendering
- `frontend/src/components/ScheduleTimeline.tsx` — Lock toggle on `TimelineCard`, threading through `DaySection`/`SatelliteSection`
- `frontend/src/components/SchedulePanel.tsx` — Merges lockStore levels into timeline acquisitions, passes `onLockToggle`
- `frontend/src/components/ObjectExplorer/Inspector.tsx` — Lock control section for acquisitions with repair-preview guard
- `frontend/src/components/RepairDiffPanel.tsx` — Per-row lock buttons on Kept/Moved/Added items + bulk lock actions bar
