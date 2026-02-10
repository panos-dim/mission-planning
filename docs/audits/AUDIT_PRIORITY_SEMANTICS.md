# AUDIT: Priority Semantics

> PR-AUD-OPS-UI-LOCKS-PARITY — Ops Readiness Audit
> Generated: 2025-02-10

---

## 1. Summary of Current Behavior

### Current Priority Scale

**Scale: 1–5, where higher number = more important (5 = highest priority)**

This is the **opposite** of the review team's desired semantics where **1 = best, 5 = lowest**.

### Default Priority Assignment

| Context | Default | File | Line |
| ------- | ------- | ---- | ---- |
| Frontend `TargetData` type | `priority?: number // 1-5, default 1` | `frontend/src/types/index.ts` | `78` |
| Frontend `TargetInput` new target | `priority: 1` | `frontend/src/components/TargetInput.tsx` | `43` |
| Frontend KML upload fallback | `priority: t.priority \|\| 1` | `frontend/src/components/TargetInput.tsx` | `146` |
| Frontend workspace load | `priority: target.priority \|\| 1` | `frontend/src/components/LeftSidebar.tsx` | `171` |
| Backend `TargetData` schema | `priority: Optional[int] = 1` | `backend/schemas/target.py` | `13` |
| Backend priority validator | `1 <= v <= 5` | `backend/schemas/target.py` | `30-35` |
| Backend `OrderSummary` | `priority: int = 3` | `backend/routers/schedule.py` | `51` |
| Core library `Target` dataclass | `priority: int = 1` | `src/mission_planner/targets.py` | `47` |
| Scheduler `Opportunity` dataclass | `priority: int = 1` | `src/mission_planner/scheduler.py` | `85` |

---

## 2. Priority in Composite Value Computation

The quality scoring module normalizes priority from 1–5 to 0–1 **with higher numbers mapping to higher value**:

```python
# src/mission_planner/quality_scoring.py:236-238
norm_priority = (priority - 1.0) / 4.0  # Maps 1→0, 5→1
norm_priority = max(0.0, min(1.0, norm_priority))
```

This means:
- Priority 1 → normalized 0.0 (lowest value)
- Priority 5 → normalized 1.0 (highest value)

The composite value formula (`quality_scoring.py:248-252`):

```python
value = (
    weights.norm_priority * norm_priority +
    weights.norm_geometry * norm_quality +
    weights.norm_timing * norm_timing
)
```

---

## 3. Sorting Usage

### 3.1 Feasibility Results Ordering

- **`MissionResultsPanel.tsx`**: Pass list is displayed in chronological order (by `start_time`). Priority is shown per-pass but does not affect ordering in the results panel.
- **Backend analysis endpoint** (`/api/v1/mission/analyze`): Returns passes sorted by start time per target. Priority is attached to the target, not the pass.

### 3.2 Planning Selection / Value Functions

| Algorithm | Sort Key | Effect of Priority | File:Lines |
| --------- | -------- | ------------------ | ---------- |
| `best_fit` | `-opp.value` (descending) | Higher priority → higher value → scheduled first | `scheduler.py:1706-1708` |
| `roll_pitch_best_fit` | `abs(pitch), -opp.value` | Pitch-first, then higher priority → higher value → preferred | `scheduler.py:1435-1440` |
| `first_fit` | Chronological | Priority used only if `value_source = "target_priority"` | `scheduler.py:~1100-1200` |
| `optimal` (ILP) | Maximize total value | Higher priority targets get higher value coefficients | `scheduler.py:~2100+` |

### 3.3 Repair Decisions

- **Fixed vs flex partition**: Based on `lock_level`, **not** priority (`incremental_planning.py:~1165-1226`)
- **Flex item replacement**: When `objective = maximize_score`, low-value (low priority) flex items may be replaced by high-value opportunities (`incremental_planning.py:~1409-1423`)
- **Repair value-based sorting**: `sorted(feasible_opps, key=lambda x: -x.get("value", 1.0))` — higher value (higher priority) opportunities are tried first for gap-filling

### 3.4 Batch Policy Scoring

- `BatchPolicy.weights.priority_weight` (`scheduleApi.ts:812`) — orders with higher priority get higher batch scores
- Order inbox scoring: Priority is a factor in order selection for batch planning

---

## 4. All Places Priorities Appear in UI

| Location | Component | Display | File:Lines |
| -------- | --------- | ------- | ---------- |
| Target input form | `TargetInput.tsx` | Priority field (1-5 selector) in new target form | `~38-43` |
| Target details sheet | `Targets/TargetDetailsSheet.tsx` | Priority display/edit | full file |
| Target list | `TargetInput.tsx` | Priority badge on each target row | throughout |
| Mission results | `MissionResultsPanel.tsx` | Per-pass priority from target | throughout |
| Planning results table | `MissionPlanning.tsx` | `value` column (derived from priority) | `~1200-1600` |
| Object explorer | `ObjectExplorer/` | Priority in target node metadata | throughout |
| Order creation | `scheduleApi.ts:219-225` | `priority` field in `createOrder()` | `219-225` |
| Order list | `scheduleApi.ts:169` | `priority: number` on Order type | `169` |
| Batch policy | `scheduleApi.ts:812` | `priority_weight` in batch scoring | `812` |

---

## 5. Risk Assessment for Flipping Priority Scale (1 = Best, 5 = Lowest)

### High-Risk Changes

1. **`quality_scoring.py:236-238`** — The normalization formula `(priority - 1.0) / 4.0` maps 1→0 and 5→1. After flip, this must become `(5.0 - priority) / 4.0` to map 1→1 and 5→0. **This is the single most critical change.**

2. **All sorting that uses `-opp.value`** — These sort descending (highest value first). Since value is derived from priority, flipping the normalization automatically fixes all sorting. No changes needed in sort comparators if the normalization is fixed.

3. **Backend validator** (`backend/schemas/target.py:30-35`) — The range `1 <= v <= 5` remains valid. Only the semantic meaning changes.

4. **Default priority** — Currently `1` (lowest under new scale: "best"). The review team wants default = 5 (lowest under new scale). Every default must change:
   - `frontend/src/types/index.ts:78` — `priority?: number // default 5`
   - `frontend/src/components/TargetInput.tsx:43` — `priority: 5`
   - `backend/schemas/target.py:13` — `priority: Optional[int] = 5`
   - `src/mission_planner/targets.py:47` — `priority: int = 5`
   - `src/mission_planner/scheduler.py:85` — `priority: int = 5`

### Medium-Risk Changes

5. **Batch policy weights** — `priority_weight` in batch scoring uses raw priority values. If scoring formula is `priority * weight`, flipping means high-priority (1) gets low score. The batch scoring formula must also invert.

6. **UI labels** — Any tooltip or label that says "higher = more important" must be updated.

7. **Existing data** — Any targets already saved in workspaces (SQLite) with priorities 1-5 will have inverted meaning. Need migration or re-interpretation.

### Low-Risk Changes

8. **Sort comparators in UI** — Frontend sorts by value (derived), not raw priority. Once the normalization formula is fixed, UI ordering follows automatically.

9. **Test fixtures** — Multiple test files use `priority=1` as default. All must be reviewed.

---

## 6. Risks / Inconsistencies

1. **Silent semantic mismatch**: The comment `// 1-5, default 1` in `types/index.ts:78` doesn't specify which end is "best". Different parts of the codebase may have different assumptions.
2. **OrderSummary default is 3** (`schedule.py:51`) while TargetData default is 1 — inconsistent defaults even within current semantics.
3. **No priority display in ScheduleTimeline** — timeline cards don't show target priority, making it invisible to the operator after planning.
4. **Composite value hides priority**: Since `value = P×priority + G×geometry + T×timing`, the user never sees the raw priority contribution. A target with priority=5 but bad geometry may have the same value as priority=1 with great geometry.

---

## 7. Recommended Minimal Change Strategy

1. **Single-point fix**: Change `quality_scoring.py:236-238` normalization to `(5.0 - priority) / 4.0`. This inverts priority semantics for all algorithms with zero changes to sort logic.
2. **Change all defaults** from `1` to `5` across frontend types, backend schemas, and core library (5 files, ~5 one-line changes).
3. **Add a migration note** for existing workspace data: either silently re-interpret (risky) or add a schema version bump that triggers priority inversion on load.
