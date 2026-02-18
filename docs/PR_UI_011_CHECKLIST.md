# PR UI-011: Align Priority Defaults with New Semantics

> **PR**: chore/pr-ui-011-align-priority-defaults-with-new-semantics
>
> **Parent**: UI-010 (Pre-Feasibility Orders + Map-Click Target Workflow)
>
> **Corrects**: Priority defaults and payload examples in UI-010 to align with UI-005 canonical semantics (1 = best, 5 = lowest, default = 5).

---

## 1. Priority Default Verification Matrix

| Target Creation Path         | File                                    | Default Priority (Before) | Default Priority (After) | Status |
| ---------------------------- | --------------------------------------- | ------------------------- | ------------------------ | ------ |
| Inline add (manual entry)    | `OrdersPanel.tsx` → `InlineTargetAdd`   | 5 ✅                       | 5 ✅                      | No change needed |
| File upload fallback         | `OrdersPanel.tsx` → `handleFileUpload`  | `(t.priority) \|\| 5` ✅   | `(t.priority) \|\| 5` ✅  | No change needed |
| Gulf sample targets          | `OrdersPanel.tsx` → `GULF_SAMPLE_TARGETS` | 1/2/2/3/3/3/4/4/5/5 ❌   | All 5 ✅                  | **Fixed** |
| Map-click confirm            | `TargetConfirmPanel.tsx` → `useState`   | 5 ✅                       | 5 ✅                      | No change needed |
| Map-click confirm reset      | `TargetConfirmPanel.tsx` → `handleDiscard` | 5 ✅                    | 5 ✅                      | No change needed |
| Priority dropdown display    | `OrdersPanel.tsx` → `OrderTargetRow`    | `target.priority \|\| 5`  | `target.priority \|\| 5`  | No change needed |

---

## 2. Payload Evidence (Post-Fix)

Creating 2 orders with default targets (no user priority edits):

```json
{
  "satellites": [ ... ],
  "targets": [
    { "name": "Athens", "latitude": 37.98, "longitude": 23.73, "priority": 5 },
    { "name": "Thessaloniki", "latitude": 40.64, "longitude": 22.94, "priority": 5 },
    { "name": "Istanbul", "latitude": 41.01, "longitude": 28.98, "priority": 5 }
  ],
  "start_time": "...",
  "end_time": "...",
  "mission_type": "imaging"
}
```

All targets default to `priority: 5` unless the user explicitly selects a different value.

---

## 3. Documentation Corrections

| Document                      | Section Changed                    | What Changed                                                |
| ----------------------------- | ---------------------------------- | ----------------------------------------------------------- |
| `docs/PR_UI_010_CHECKLIST.md` | §4 Request Payload Evidence        | Priority values `1/3/2` → `5/5/5`                          |
| `docs/PR_UI_010_CHECKLIST.md` | §4 (new note)                      | Added priority semantics note aligned with UI-005           |

---

## 4. Regression Test

**File**: `frontend/src/components/__tests__/defaultPriority.test.ts`

| Test Case                                         | Assertion                              |
| ------------------------------------------------- | -------------------------------------- |
| Inline add → priority defaults to 5               | `target.priority === 5`               |
| File upload fallback (no priority field)           | `mapped.priority === 5`               |
| File upload with explicit priority                 | `mapped.priority === 2` (preserved)   |
| Gulf sample targets all have priority 5            | All `target.priority === 5`           |
| Map-click confirm default priority                 | `target.priority === 5`               |
| getAllTargets flattening preserves priorities       | Mixed priorities retained correctly    |

**Run**: `cd frontend && npx vitest run src/components/__tests__/defaultPriority.test.ts`

---

## 5. Files Changed

### Frontend

- `frontend/src/components/OrdersPanel.tsx` — `GULF_SAMPLE_TARGETS`: all priorities changed from 1–4 to 5

### Frontend — New Files

- `frontend/src/components/__tests__/defaultPriority.test.ts` — Regression tests for default priority = 5

### Docs

- `docs/PR_UI_010_CHECKLIST.md` — Corrected payload example priorities; added semantics note
- `docs/PR_UI_011_CHECKLIST.md` — This file

---

## 6. Non-goals (explicitly excluded)

- No changes to UI-010 workflows (orders, map-click confirm, validation) besides default priority
- No backend changes
- No target UID work
- No changes to priority dropdown behavior (user can still choose 1–5)

---

## 7. Acceptance Criteria

- [x] All UI-010-created targets default to priority 5 unless explicitly set by user
- [x] UI-010 checklist payload example shows correct default priorities
- [x] UI-010 checklist does not contradict UI-005 priority semantics
- [x] Automated regression test exists for default priority
- [x] Builds/tests pass
