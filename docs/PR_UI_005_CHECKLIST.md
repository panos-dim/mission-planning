# PR UI-005: Priority Semantics — 1 Best, 5 Lowest, Default 5

**Branch:** `chore/priority-semantics-1-best-5-lowest-default-5`
**Scope:** End-to-end (FE + API + backend + scoring + persistence migration)

---

## Canonical Semantics

| Priority | Meaning | Normalized Score |
|----------|---------|-----------------|
| 1 | **Best** (highest importance) | 1.0 |
| 2 | High | 0.75 |
| 3 | Medium | 0.5 |
| 4 | Low | 0.25 |
| 5 | **Lowest** (default for new entities) | 0.0 |

**Default value:** `5` everywhere (new targets, new orders, fallback defaults).

**Normalization formula:** `(5 - priority) / 4` → maps 1→1.0, 5→0.0

---

## A) Defaults Changed (FE + BE)

### Backend

| File | Location | Old Default | New Default |
|------|----------|-------------|-------------|
| `backend/schemas/target.py` | `TargetData.priority` | 1 | **5** |
| `backend/routers/orders.py` | `CreateOrderRequest.priority` | 3 | **5** |
| `backend/routers/orders.py` | `ExtendedCreateOrderRequest.priority` | 3 | **5** |
| `backend/routers/orders.py` | `ImportOrderItem.priority` | 3 | **5** |
| `backend/schedule_persistence.py` | SQL `DEFAULT` clause | 3 | **5** |
| `backend/schedule_persistence.py` | `create_order()` param | 3 | **5** |
| `backend/schedule_persistence.py` | `import_orders_bulk()` fallback | 3 | **5** |
| `backend/routers/workspaces.py` | `getattr(t, "priority", ...)` fallback | 1 | **5** |
| `backend/main.py` | `target_priorities` fallback | 1 | **5** |
| `backend/main.py` | custom `value_source` fallback | 1.0 | **5.0** |
| `backend/main.py` | uniform `base_priority` | 1.0 | **5.0** |
| `backend/main.py` | `GroundTarget` construction fallback | 1 | **5** |
| `backend/main.py` | backend sample targets | inverted (5=best) | **inverted (1=best)** |
| `backend/main.py` | debug endpoint `getattr` fallback | 1 | **5** |
| `backend/routers/orders.py` | docstring | "5 is highest" | **"1 is best"** |
| `backend/policy_engine.py` | `order.get("priority", ...)` fallback | 3 | **5** |

### Core Library

| File | Location | Old Default | New Default |
|------|----------|-------------|-------------|
| `src/mission_planner/targets.py` | `GroundTarget.priority` | 1 | **5** |
| `src/mission_planner/scheduler.py` | `Opportunity.priority` | 1 | **5** |

### Frontend

| File | Location | Old Default | New Default |
|------|----------|-------------|-------------|
| `frontend/src/types/index.ts` | `TargetData.priority` comment | "default 1" | **"default 5"** |
| `frontend/src/components/TargetInput.tsx` | `newTarget` initial state | 1 | **5** |
| `frontend/src/components/TargetInput.tsx` | `newTarget` reset state | 1 | **5** |
| `frontend/src/components/TargetInput.tsx` | CSV upload fallback | 1 | **5** |
| `frontend/src/components/TargetInput.tsx` | Read-only `P{}` badge fallback | 1 | **5** |
| `frontend/src/components/TargetInput.tsx` | Edit `<select>` fallback | 1 | **5** |
| `frontend/src/components/Targets/TargetDetailsSheet.tsx` | `useState(priority)` | 1 | **5** |
| `frontend/src/components/Targets/TargetDetailsSheet.tsx` | `setPriority()` on new target | 1 | **5** |

---

## B) Normalization Mapping (Before / After)

### `quality_scoring.py` — `compute_composite_value()`

```
OLD: norm_priority = (priority - 1.0) / 4.0   →  1→0.0, 5→1.0  (5=best)
NEW: norm_priority = (5.0 - priority) / 4.0   →  1→1.0, 5→0.0  (1=best)
```

### `policy_engine.py` — `calculate_order_score()`

```
OLD: priority_score = (priority - 1) / 4      →  1→0.0, 5→1.0  (5=best)
NEW: priority_score = (5 - priority) / 4      →  1→1.0, 5→0.0  (1=best)
```

---

## C) SQL Ordering Changed

| File | Query Context | Old | New |
|------|--------------|-----|-----|
| `schedule_persistence.py` | `get_batch_orders()` | `ORDER BY priority DESC` | `ORDER BY priority ASC` |
| `schedule_persistence.py` | `list_orders_inbox()` | `ORDER BY priority DESC` | `ORDER BY priority ASC` |

Under new semantics, `ASC` puts highest-importance (1) first.

---

## D) Frontend Display Logic Inverted

### `OrdersArea.tsx` — `getPriorityColor()`

```
OLD: priority >= 4 → red,  priority >= 3 → yellow,  else gray  (high number = important)
NEW: priority <= 2 → red,  priority === 3 → yellow,  else gray  (low number = important)
```

### `RepairCommitModal.tsx` — dropped high-priority detection

```
OLD: prio >= 4 flags as "high priority dropped" (P4/P5 warning)
NEW: prio <= 2 flags as "high priority dropped" (P1/P2 warning)
```

### `RepairCommitModal.tsx` — priority impact sort order

```
OLD: descending (b[0] - a[0]) — highest number first
NEW: ascending  (a[0] - b[0]) — best priority (1) first
```

### `TargetDetailsSheet.tsx` — option labels

```
OLD: 1 (Low), 3 (Medium), 5 (High)
NEW: 1 (Best), 3 (Medium), 5 (Lowest)
```

### `TargetInput.tsx` — sample targets inverted

Athens P5→P1, Istanbul P4→P2, Sofia/Rhodes/Antalya P2→P4, Heraklion/Patras P1→P5. Middle targets (P3) unchanged.

---

## E) Compatibility Strategy

**Approach:** One-time database migration (schema v2.3) at startup.

### What it does

- `UPDATE orders SET priority = 6 - priority WHERE priority BETWEEN 1 AND 5`
- Formula `6 - p`: 1↔5, 2↔4, 3 stays 3
- Tracked in `schema_migrations` table (version `"2.3"`)
- Idempotent: only runs once, checked via `current_version < "2.3"`

### What it covers

| Data Source | Handling |
|-------------|----------|
| **Orders in SQLite** | Migrated automatically by v2.3 migration |
| **Workspace targets (browser → API)** | No migration needed — targets come from FE on each request, FE now sends new semantics |
| **Config YAML files** | No priority fields in config YAMLs |
| **In-flight API requests** | API schemas updated; new requests use new semantics immediately |

### How to verify legacy behavior

1. Before deploying, note existing order priorities in DB
2. Deploy and let v2.3 migration run (check logs for `"Inverted priorities for N orders"`)
3. Verify: old P5 orders now show as P1, old P1 orders now show as P5
4. Confirm `schema_migrations` table has row for version `"2.3"`

---

## F) Tests Updated

| Test File | Change |
|-----------|--------|
| `tests/unit/test_quality_scoring.py` | `test_balanced_weights`: priority=5→1 for max score; `test_min_values`: priority=1→5 for min; `test_priority_dominance`: asserts 1 > 5; new `test_priority_normalization_mapping`: exact 1→1.0, 3→0.5, 5→0.0 |
| `tests/unit/test_targets.py` | Default priority assertion 1→5 |
| `tests/unit/test_targets_extended.py` | Default priority assertion 1→5 |
| `tests/unit/test_scheduler.py` | Default priority assertion 1→5 |
| `tests/unit/test_scheduler_extended.py` | Inverted priority values in test data (opp_low: 1→5, opp_high: 5→1) |

---

## G) Manual Verification Steps

| # | Step | Expected Result | Status |
|---|------|-----------------|--------|
| 1 | Create a new target → check default priority | Default = 5 | TODO |
| 2 | Create a new order → check default priority | Default = 5 | TODO |
| 3 | Set target priority = 1, run planning → check it ranks as "best" | P1 gets highest composite value score | TODO |
| 4 | Set target priority = 5, run planning → check it ranks as "lowest" | P5 gets lowest composite value score | TODO |
| 5 | Load a known legacy workspace → confirm migration handled correctly | Old P5 orders → now P1 (or verify migration log) | TODO |
| 6 | Confirm API payload values match UI (no inversion) | Priority sent = priority displayed | TODO |
| 7 | Check priority color coding in OrdersArea | P1/P2 = red, P3 = yellow, P4/P5 = gray | TODO |

---

## H) Files Changed (Summary)

**Backend (7 files):**
- `backend/schemas/target.py`
- `backend/routers/orders.py`
- `backend/routers/workspaces.py`
- `backend/schedule_persistence.py`
- `backend/main.py`
- `backend/policy_engine.py`

**Core library (3 files):**
- `src/mission_planner/quality_scoring.py`
- `src/mission_planner/targets.py`
- `src/mission_planner/scheduler.py`

**Scripts (1 file):**
- `scripts/utilities/verify_kml_mission.py`

**Frontend (5 files):**
- `frontend/src/types/index.ts`
- `frontend/src/components/TargetInput.tsx`
- `frontend/src/components/Targets/TargetDetailsSheet.tsx`
- `frontend/src/components/OrdersArea.tsx`
- `frontend/src/components/RepairCommitModal.tsx`

**Tests (5 files):**
- `tests/unit/test_quality_scoring.py`
- `tests/unit/test_targets.py`
- `tests/unit/test_targets_extended.py`
- `tests/unit/test_scheduler.py`
- `tests/unit/test_scheduler_extended.py`

**Docs (1 file):**
- `docs/PR_UI_005_CHECKLIST.md` (this file)
