# PR-COMMIT-PREVIEW-01 — Commit Gate with Risk Summary

## Overview

Lightweight commit preview "gate" before writing schedule changes. When the user
clicks **Commit to Schedule** in repair mode, a modal summarises what will change
and highlights any risks. No new panels, routes, or algorithm changes.

---

## Checklist

### 1. Commit Preview shows correct counts + priority impact

- [ ] Modal opens on "Commit to Schedule" click (repair mode only)
- [ ] **Added / Dropped / Moved / Kept** counts match `repair_diff`
- [ ] Hard-locked preserved count shown when > 0
- [ ] Score delta (before → after) displayed
- [ ] Conflicts after commit count displayed
- [ ] Priority Impact section shows per-priority-level (P1–P5) dropped/added breakdown
- [ ] Plan ID shown in footer

### 2. Warning appears under risk conditions

Risk rules trigger a yellow **"Risk Detected"** banner when any of:

- [ ] Conflicts after commit > 0
- [ ] Dropped includes any P4 or P5 acquisitions
- [ ] Any hard-lock violation present (`hard_lock_warnings`)
- [ ] Large change: moved + dropped + added > 20

### 3. Conflicts require checkbox confirmation

- [ ] When conflicts > 0, "Confirm Commit" button is **disabled** by default
- [ ] Checkbox: *"I understand this will create conflicts"* appears
- [ ] Checking the box enables the commit button
- [ ] Top 3 conflict summaries shown with severity indicators
- [ ] "+N more" shown when conflicts exceed 3

### 4. "Review Changes" jumps and highlights correctly

- [ ] "Review Changes" button closes modal
- [ ] Scrolls to RepairDiffPanel (smooth scroll)
- [ ] RepairDiffPanel re-mounts (key bump) → sections auto-expand
- [ ] First dropped (or first moved) item auto-selected
- [ ] Map + timeline highlighting activates via `repairHighlightStore`

### 5. Commit still works normally when safe

- [ ] No-risk commits: "Confirm Commit" is immediately clickable
- [ ] Commit executes via existing `onPromoteToOrders` path
- [ ] Modal closes after commit completes
- [ ] Non-repair modes continue to use legacy `ConflictWarningModal`
- [ ] Simple Mode surface unchanged (modal only appears in repair flow)

---

## Data Sourcing

All data comes from the existing `RepairPlanResponse`:

| Field                   | Source                                   |
|-------------------------|------------------------------------------|
| Change counts           | `repair_diff.kept / dropped / added / moved` |
| Hard-locked count       | `useLockStore.levels` (derived)          |
| Score delta             | `metrics_comparison.score_delta`         |
| Conflicts after commit  | `commit_preview.will_conflict_with` or `conflicts_if_committed.length` |
| Priority impact         | `repair_diff.change_log` + `TargetData.priority` |
| Hard-lock violations    | `repair_diff.hard_lock_warnings`         |
| Conflict details        | `conflicts_if_committed` (top 3)         |

**No new backend endpoints required.**

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/components/RepairCommitModal.tsx` | Rewritten as Commit Preview Gate with risk assessment, priority impact, conflict summaries, review navigation |
| `frontend/src/components/MissionPlanning.tsx` | Repair mode → `RepairCommitModal`; added state, handlers, ref for scroll-to-review |
| `docs/PR_COMMIT_PREVIEW_01_CHECKLIST.md` | This file |

---

## Acceptance Criteria

1. **Planner always understands what commit will do before it happens** — modal shows full change summary with counts, score delta, and priority impact.
2. **Risky commits require explicit acknowledgement** — conflicts gate behind checkbox; high-priority drops and large changes flagged in warning banner.
3. **No extra noise during normal operation** — modal only appears on commit click; no persistent UI elements added.
