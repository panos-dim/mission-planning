# PR-OPS-REPAIR-REPORT-01: Repair Report Checklist

## Overview

Enhance the repair-first workflow to produce a structured "Repair Report" with
a precise change log explaining what was moved, dropped, added, or kept — and why.

**Constraints:**
- No new panels, tabs, routes, or charts
- No new algorithms — repair scheduling logic unchanged
- No new endpoints unless absolutely necessary
- Payload size kept reasonable (structured entries are dict-serialized)

---

## Backend Changes

### `backend/incremental_planning.py`

- [x] Add `RepairReasonCode` enum with deterministic reason codes:
  `HARD_LOCK_CONSTRAINT`, `CONFLICT_RESOLUTION`, `PRIORITY_UPGRADE`,
  `QUALITY_SCORE_UPGRADE`, `SLEW_CHAIN_FEASIBILITY`, `HORIZON_LIMIT`,
  `RESOURCE_LIMIT`, `KEPT_UNCHANGED`, `ADDED_NEW`
- [x] Add Pydantic models: `DroppedEntry`, `AddedEntry`, `MovedEntry`
  with fields: `acquisition_id`, `satellite_id`, `target_id`, `start`, `end`,
  `reason_code`, `reason_text`, plus type-specific fields (`replaced_by`,
  `replaces`, `value`, `from_start`/`to_start` etc.)
- [x] Add `change_log` field to `RepairDiff` model (Dict with
  `dropped`, `added`, `moved` entry lists and `kept_count`)
- [x] Populate `change_log` in `execute_repair_planning` by:
  - Building lookup maps for flex items, opportunities
  - Deriving reason codes from existing free-text reasons via `_derive_reason_code`
  - Linking dropped↔added via satellite_id for replacement tracking
- [x] No changes to repair scheduling algorithm

### `backend/routers/schedule.py`

- [x] Add `change_log: Dict[str, Any]` field to `RepairDiffResponse`
- [x] Pass `repair_diff.change_log` through in response builder

---

## Frontend Changes

### `frontend/src/api/scheduleApi.ts`

- [x] Add TypeScript interfaces: `DroppedEntry`, `AddedEntry`, `MovedEntry`, `ChangeLog`
- [x] Add optional `change_log?: ChangeLog` field to `RepairDiff` interface

### `frontend/src/adapters/repairReasons.ts`

- [x] Align `RepairReasonCode` enum with backend enum values
  (e.g. `HARD_LOCK_CONSTRAINT`, `PRIORITY_UPGRADE`, `QUALITY_SCORE_UPGRADE`)
- [x] Update `REASON_CODE_LABELS` and `REASON_CODE_COLORS` to use new codes
- [x] Add safe accessor helpers: `getReasonColor(code)`, `getReasonLabel(code)`
- [x] Update `REASON_PATTERN_MAP` to reference new enum members
- [x] Update `buildReasonMap` to prefer structured `change_log` data when available,
  falling back to `reason_summary` derivation for backwards compatibility

### `frontend/src/store/selectionStore.ts`

- [x] Add `"repair"` to `lastSelectionSource` union type

### `frontend/src/components/RepairDiffPanel.tsx`

- [x] Header renamed from "Repair Preview" to "Repair Report"
- [x] `DiffItemRow`: enriched with satellite ID (🛰), target ID (📍),
  UTC time range (🕐), and reason code badge from `change_log` entries
- [x] `MovedItemRow`: enriched with satellite/target from `movedLogEntry`,
  reason code badge
- [x] `DiffSection`: accepts `changeLogLookup` and `movedLogLookup` props,
  passes structured entries to item rows
- [x] `PriorityImpactBlock`: expandable section showing before/after
  acquisition counts + scores, and top 5 clickable wins with reason badges
- [x] Click-to-focus: `handleItemClick` bridges to both `repairHighlightStore`
  (Cesium highlighting + timeline focus) and `selectionStore.selectAcquisition`
  (opens Inspector with repair context)
- [x] Main component builds `change_log` lookup maps from `repair_diff.change_log`

---

## Acceptance Criteria

1. **Mission planner can answer "what changed exactly?" without guessing**
   - Each dropped/added/moved item shows satellite, target, time range, and reason
2. **Report entries are actionable (click → see on timeline/map)**
   - Click any item → Cesium highlights entity, timeline focuses, Inspector opens
3. **Reasons and priority impact visible but not noisy by default**
   - PriorityImpactBlock and diff sections are collapsed by default
   - Reason badges are compact (9px text)
4. **Repair remains deterministic and fast**
   - No algorithm changes; structured data derived from existing computation
5. **Backwards compatible**
   - `change_log` is optional; frontend falls back to `reason_summary` derivation

---

## Files Modified

| File | Type | Summary |
|------|------|---------|
| `backend/incremental_planning.py` | Backend | `RepairReasonCode` enum, entry models, `change_log` population |
| `backend/routers/schedule.py` | Backend | `change_log` field on response model, passthrough |
| `frontend/src/api/scheduleApi.ts` | Types | `DroppedEntry`, `AddedEntry`, `MovedEntry`, `ChangeLog` interfaces |
| `frontend/src/adapters/repairReasons.ts` | Adapter | Aligned enum, safe accessors, `buildReasonMap` prefers `change_log` |
| `frontend/src/store/selectionStore.ts` | Store | `"repair"` source in union type |
| `frontend/src/components/RepairDiffPanel.tsx` | UI | Enriched rows, PriorityImpactBlock, click-to-focus bridge |
