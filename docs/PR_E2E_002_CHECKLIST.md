# PR E2E-002: Dev Demo Runner — Reshuffle Scenarios 10/15/20

## Goal

Dev-only Demo Runner that executes the E2E flow (Feasibility → Schedule → Apply (force-commit) → Recompute Conflicts → Capture Snapshot) for three scenarios (10/15/20 targets) in the **Eastern Mediterranean corridor** and produces automatic evidence of DB schedule reshuffling, conflict accumulation, and acquisition growth across revisions.

## Runner UI

The Demo Runner appears as a **flask icon** (🧪) in the left sidebar, visible only in **Developer UI mode** on **DEV builds**. It provides:

- **Per-scenario buttons** — Run Scenario 1 / 2 / 3 individually
- **Run All (1→2→3)** — Sequential execution of all three scenarios
- **Step log** — Real-time status per step (idle → running → success/failed), including conflict analysis steps
- **Failure detail** — Failed steps show endpoint path + HTTP status code
- **Summary footer** — Acquisition counts per revision + reshuffle diffs + conflict counts
- **Download JSON** — Client-side download of evidence JSON

## Scenario Definitions

All targets are placed in the **Eastern Mediterranean corridor** so satellite passes overlap, forcing the scheduler to make trade-offs when higher-priority targets are added.

| Scenario | Targets | Cities | Priority | Behaviour |
|----------|---------|--------|----------|-----------|
| **Scenario 1** | 10 | Athens, Istanbul, Ankara, Nicosia, Beirut, Sofia, Bucharest, Cairo, Tel Aviv, Thessaloniki | 3 (medium) | Fresh schedule — baseline 10 targets |
| **Scenario 2** | 15 | All 10 above + Izmir, Antalya, Damascus, Alexandria, Plovdiv | **1–2 (high)** | **Appends** 5 high-priority targets near existing ones → forces conflicts |
| **Scenario 3** | 20 | All 15 above + Heraklion, Amman, Bursa, Constanta, Varna | **1–2 (high)** | **Appends** 5 more high-priority targets → more conflicts |

All scenarios share the **same `workspace_id`** (DB-assigned UUID from `POST /api/v1/workspaces`), ensuring the DB accumulates acquisitions across revisions.

### Why Eastern Med Corridor?

Placing targets in a geographically concentrated corridor means:

- **Same satellite passes** cover multiple targets
- Adding high-priority targets **near existing ones** forces the scheduler to pack more acquisitions into shared time windows
- This produces **temporal overlaps** and **slew infeasibility conflicts** — exactly the reshuffle evidence we need

### Flow Per Scenario (6 steps)

1. **Feasibility** — `POST /api/v1/mission/analyze` with N targets + 5 active ICEYE satellites
2. **Schedule** — `POST /api/v1/planning/schedule` (roll_pitch_best_fit, from_scratch)
3. **Apply** — `POST /api/v1/schedule/commit/direct` with `force=true` to persist acquisitions despite conflicts
4. **Recompute Conflicts** — `POST /api/v1/schedule/conflicts/recompute` to detect temporal overlaps and slew infeasibility
5. **Fetch Conflict Details** — `GET /api/v1/schedule/conflicts?workspace_id=...` to capture full conflict descriptions
6. **Snapshot** — `GET /api/v1/dev/schedule-snapshot?workspace_id=...` to capture workspace state

## Evidence Fields Captured

### Per-Revision Snapshot (`ScheduleSnapshotResponse`)

| Field | Description |
|-------|-------------|
| `workspace_id` | Shared workspace across all revisions |
| `captured_at` | ISO timestamp of snapshot |
| `acquisition_count` | Total acquisitions in workspace at this point |
| `acquisition_ids` | Ordered list of all acquisition IDs |
| `plans` | List of committed plans (id, created_at, algorithm, status) |
| `plan_count` | Number of committed plans |
| `by_target` | Acquisition count per target_id |
| `by_satellite` | Acquisition count per satellite_id |
| `by_state` | Acquisition count per state (committed, etc.) |

### Per-Revision Conflict Analysis (`ConflictEvidence`)

| Field | Description |
|-------|-------------|
| `detected` | Number of conflicts detected after recompute |
| `persisted` | Number of new conflicts persisted to DB |
| `active_conflicts[]` | Full list with id, type, severity, description, acquisition_ids |
| `summary` | Aggregate by type (`temporal_overlap`, `slew_infeasible`) and severity (`error`, `warning`, `info`) |

### Per-Diff (`DiffEntry`)

| Field | Description |
|-------|-------------|
| `from_scenario` / `to_scenario` | Which revisions are being compared |
| `added_ids` | Acquisition IDs present in rev(N) but not rev(N-1) |
| `removed_ids` | Acquisition IDs present in rev(N-1) but not rev(N) |
| `kept_ids` | Acquisition IDs present in both revisions |
| `target_count_before` / `after` | Target count change |
| `acquisition_count_before` / `after` | Total acquisition count change |
| `conflicts_before` / `conflicts_after` | Conflict count change |

## E2E Verification Results (5 ICEYE satellites)

Run on 2026-02-19 with ICEYE-X65, X57, X56, X55, X53:

| Scenario | Targets | Opps | Scheduled | Total Acqs | Conflicts | Breakdown |
|----------|---------|------|-----------|------------|-----------|-----------|
| **Scenario 1** | 10 (pri 3) | 24 | 9 | 9 | 1 | 1 slew_infeasible |
| **Scenario 2** | 15 (+5 pri 1-2) | 35 | 14 | 23 | 13 | 7 temporal_overlap, 6 slew |
| **Scenario 3** | 20 (+5 pri 1) | 47 | 19 | 42 | 27 | 21 temporal_overlap, 6 slew |

### Diffs

| Transition | Added | Removed | Kept | Targets | Acqs | Conflicts |
|------------|-------|---------|------|---------|------|-----------|
| rev1 → rev2 | +14 | -0 | =9 | 10→15 | 9→23 | 1→13 |
| rev2 → rev3 | +19 | -0 | =23 | 15→20 | 23→42 | 13→27 |

### Conflict Examples Captured

- `[ERROR] temporal_overlap` — "Satellite ICEYE-X55: acquisitions overlap by 5.0s. Tel Aviv ends at 2026-02-19T..."
- `[ERROR] slew_infeasible` — "Satellite ICEYE-X56: insufficient slew time. Need 79.7s to slew (roll 74.7°)..."
- `[WARNING] slew_infeasible` — "Satellite ICEYE-X55: insufficient slew time. Need 39.5s to slew (roll 0.6°)..."

## Generated Artifact Paths

| File | Path | Format |
|------|------|--------|
| JSON evidence | `artifacts/demo/RESHUFFLE_EVIDENCE.json` | Structured: `{ workspace_id, generated_at, satellites, revisions[], diffs[] }` |
| Markdown report | `artifacts/demo/RESHUFFLE_EVIDENCE.md` | Human-readable: revision summaries + conflict tables + diff tables |
| Client download | `RESHUFFLE_EVIDENCE_<workspace_id>.json` | Same JSON, downloaded via browser |

## Files Changed

### Backend

- [x] `backend/routers/dev.py` — **NEW** Dev-only router with:
  - `GET /api/v1/dev/schedule-snapshot` — read-only snapshot with **strict workspace_id matching** (no NULL fallback)
  - `POST /api/v1/dev/write-artifacts` — write JSON/MD evidence to disk
  - Guarded by `DEV_MODE=1` env var (default ON for local dev, 403 when OFF)
- [x] `backend/routers/schedule.py` — Added `force` field to `DirectCommitRequest`, allowing commits despite conflicts (logged as warning)
- [x] `backend/main.py` — Import and register `dev_router`

### Frontend

- [x] `frontend/src/components/DemoScenarioRunner.tsx` — **NEW** Dev-only E2E harness with:
  - Eastern Med corridor targets with escalating priorities
  - Workspace creation step (required for FK constraint)
  - `force=true` on commits to allow conflicting schedules
  - Conflict recompute + fetch steps after each commit
  - Rich evidence including conflict type, severity, descriptions, affected acquisition IDs
  - Markdown builder with conflict tables per revision
- [x] `frontend/src/components/LeftSidebar.tsx` — Mount DemoRunner panel (dev mode + DEV build only)
- [x] `frontend/src/api/config.ts` — Add `DEV_SCHEDULE_SNAPSHOT`, `DEV_WRITE_ARTIFACTS` endpoints

### Artifacts & Config

- [x] `artifacts/demo/.gitkeep` — Output directory for evidence files
- [x] `.gitignore` — Ignore generated `RESHUFFLE_EVIDENCE.*` files (keep `.gitkeep`)"

### Docs

- [x] `docs/PR_E2E_002_CHECKLIST.md` — This file

## Verification

### Manual Testing

1. Start backend: `make dev` or `uvicorn backend.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Ensure 5 active ICEYE satellites exist in Admin Panel (X65, X57, X56, X55, X53)
4. Switch UI mode to **Developer** (top-right toggle)
5. Open **Demo Runner** panel (flask icon in left sidebar)
6. Click **Run All (1→2→3)** — verify:
   - All steps show ✅ green checkmarks (including workspace creation + conflict analysis steps)
   - Conflict steps show increasing counts across scenarios
   - Summary shows acquisition counts and conflict counts for each scenario
   - Reshuffle diffs show `+added / -removed / =kept` counts
   - `artifacts/demo/RESHUFFLE_EVIDENCE.json` is written
   - `artifacts/demo/RESHUFFLE_EVIDENCE.md` is written
7. Click **Download JSON** — verify local download works
8. Open `RESHUFFLE_EVIDENCE.json` and confirm:
   - Three entries in `revisions[]`, each with `snapshot` + `conflicts` data
   - Feasibility targets are 10, 15, 20 respectively
   - `diffs[0]` = rev1→rev2, `diffs[1]` = rev2→rev3
   - `added_ids.length > 0` in each diff (new acquisitions for new targets)
   - Conflict counts grow across revisions (1 → 13 → 27 in reference run)
   - Conflict descriptions include specific satellite names, overlap durations, and slew angles

### Manual Validation: Conflicts Make Sense

- **Scenario 1 (10 targets, priority 3)** — Minimal conflicts (typically 1 slew_infeasible). Satellites have enough capacity for the baseline targets.
- **Scenario 2 (+5 high-priority targets)** — Significant conflicts. High-priority Izmir/Antalya/Alexandria targets are near Athens/Nicosia/Cairo, sharing the same satellite passes → temporal overlaps.
- **Scenario 3 (+5 more high-priority)** — Most conflicts. Heraklion/Amman/Bursa/Constanta/Varna pack the same corridor further → 21+ temporal overlaps.
- **Conflict types**: `temporal_overlap` = two acquisitions for same satellite overlap in time; `slew_infeasible` = insufficient time to slew between consecutive targets.

### Dev-Only Guard Verification

- [ ] With `DEV_MODE=0`: `curl localhost:8000/api/v1/dev/schedule-snapshot?workspace_id=test` → 403
- [ ] With `DEV_MODE=1` (default): same URL → 200

### Automated Checks

- [x] `cd frontend && npx tsc --noEmit` — TypeScript compiles clean
- [x] `python -c "from backend.main import app"` — Backend starts without import errors
- [x] E2E test script (`/tmp/demo_e2e_test.py`) — All 3 scenarios pass with conflict evidence
- [ ] Dev endpoints return 403 when `DEV_MODE=0`

## Constraints Met

- ✅ No algorithm/scoring changes
- ✅ No new planner knobs
- ✅ Dev-only guarded (DEV build + developer UI mode + `DEV_MODE` env)
- ✅ Reuses existing endpoints and stores — no mock data paths
- ✅ No giant refactors
- ✅ `schedule-snapshot` endpoint is read-only (GET, no mutations)
- ✅ `force=true` on `commit/direct` is opt-in (default `false`), existing behaviour unchanged
- ✅ Conflict analysis uses existing `conflicts/recompute` + `conflicts` endpoints
