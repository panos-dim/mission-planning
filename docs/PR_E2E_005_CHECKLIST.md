# PR E2E-005: Dev Demo Runner — Scalability Scenario (1000t / 14d / 50sats)

## Goal

Add a dev-only scalability stress scenario to the existing DemoScenarioRunner that
executes a large feasibility run (1000 targets / 14 days / 50 satellites) and produces
a runtime + memory report artifact. No scheduling algorithm changes.

**Hardening iteration:** Added response-bloat guardrails, configurable PASS/WARN/FAIL
thresholds, satellite count selector, risk scoring, bottleneck reporting, and extended
backend dev metrics — preserving the "no algorithm changes" rule.

## Checklist

### A) Scenario Preset: "Scalability"

- [x] New preset visible in Demo Runner UI: **Scalability (1000 targets / 14 days / 50 sats)**
- [x] Deterministic target generation via seeded PRNG (mulberry32, seed=42)
- [x] 1000 targets on global grid (lat -60°..+60°, lon -180°..+180°) with jitter
- [x] Default priority = 5 for all generated targets
- [x] Satellite count capped at 50 (uses first N active managed satellites)

### B) Run Mode: Feasibility-only (default)

- [x] Default runs feasibility only — no Apply
- [x] "Also Apply" checkbox (OFF by default)
- [x] Request includes all 1000 targets in a single call

### C) Performance Measurement

- [x] **Frontend timings**: `t_request_start`, `t_response_end`, wall time (ms)
- [x] **Payload sizes**: request/response bytes via `Blob.size`
- [x] **Backend RSS**: before/after via `GET /api/v1/dev/metrics`
- [x] **Backend VMS**: reported when available (Linux `/proc/self/status`)
- [x] **Last feasibility stats**: captured from `/dev/metrics` response
- [x] No algorithm changes

### D) Artifacts Output

- [x] `artifacts/demo/SCALE_TEST_EVIDENCE.json` — full report object
- [x] `artifacts/demo/SCALE_TEST_EVIDENCE.md` — human-readable markdown with:
  - Scenario parameters (1000/14d/50)
  - Total runtime
  - Memory snapshots
  - **PASS/WARN/FAIL threshold table** per metric
  - **Bottleneck analysis** when response > 50 MB (with recommended next actions)
  - Errors/timeouts
  - Environment (DEV_MODE, server host, timestamp)
- [x] Written via existing `POST /api/v1/dev/write-artifacts` (now supports `filename_prefix`)

### E) Safety & Guardrails

- [x] Only visible when `DEV_MODE=1` and `import.meta.env.DEV`
- [x] Confirmation dialog before run ("This may take time and load the server")
- [x] Cancel button (aborts fetch via `AbortController`)
- [x] **Risk warning banner** when `targets × sats × days > 200,000` (configurable)
- [x] **Satellite count selector** — quick switch between 10 / 20 / 50 sats
- [x] High-risk confirmation distinguishes normal vs high-risk runs visually

### F) Response-Bloat Guardrails (new)

- [x] Risk score computed as `targets × sats × days`; threshold at 200,000
- [x] Warning banner shown when risk score exceeds threshold (before confirming run)
- [x] Confirmation dialog shows risk score and warns about expected response size
- [x] High-risk runs require explicit "Confirm High-Risk Run" click (red button)
- [x] Satellite count selector defaults to 50 but allows 10/20/50 for safe quick runs

### G) PASS / WARN / FAIL Thresholds (new)

- [x] Thresholds defined as a `DEV_THRESHOLDS` config object in `scenarios.ts`
- [x] Evaluated after each scalability run via `evaluateThresholds()`
- [x] Displayed inline in the Demo Runner UI after run completes
- [x] Written to the markdown artifact report

### H) Backend Dev Metrics Improvements (new)

- [x] `last_response_bytes` — last feasibility response size in bytes
- [x] `last_pass_count` — number of passes in last feasibility result
- [x] `last_request_params` — `{ target_count, satellite_count, duration_days }`
- [x] `gc_stats` — GC generation counts, thresholds, uncollectable object count
- [x] All fields DEV_MODE guarded only

## Scenario Parameters

| Parameter | Value | Notes |
| --------- | ----- | ----- |
| Targets | 1000 | Global grid, lat -60°..+60°, lon -180°..+180°, ±0.5° jitter |
| Duration | 14 days | From `now` to `now + 14d` |
| Satellites | up to 50 | Selectable: 10 / 20 / 50 via satellite count selector |
| PRNG seed | 42 | mulberry32 — deterministic across runs |
| Priority | 5 (all) | Default; not varied |
| Mission type | imaging / optical | Same as existing demo presets |

## Threshold Configuration

| Threshold | Default | Level |
| --------- | ------- | ----- |
| Max wall time | 600 s | FAIL if exceeded |
| Response size (warn) | 100 MB | WARN |
| Response size (fail) | 250 MB | FAIL |
| Backend RSS (warn) | 4 GB | WARN |
| Backend RSS (fail) | 6 GB | FAIL |
| Risk score (warn) | 200,000 | Pre-run warning banner |

Thresholds are defined in `frontend/src/dev/demo/scenarios.ts` as `DEV_THRESHOLDS`.

## Runtime & Memory Numbers

> **Baseline run:** 2026-02-20 @ 16:06 UTC — macOS, 14 active satellites, DEV_MODE=1.
> Re-run whenever algorithms or infra change.

| Metric | Value | Notes |
| ------ | ----- | ----- |
| Wall time (feasibility) | **474,536 ms (474.5 s)** | End-to-end HTTP round-trip |
| Request payload | **85.5 KB** (87,594 bytes) | 1000 targets + 14 satellites JSON |
| Response payload | **294.2 MB** (301,291 KB) | 115,516 passes serialised as JSON |
| Backend RSS before | **147.2 MB** | `GET /api/v1/dev/metrics` |
| Backend RSS after | **3,202.4 MB** | `GET /api/v1/dev/metrics` |
| RSS delta | **+3,055.2 MB** | Dominated by response serialisation |
| Backend VMS | N/A | macOS — `/proc/self/status` unavailable |
| Passes found | **115,516** | Across 14 satellites × 1000 targets × 14 days |
| Opportunities | 0 | Passes reported at top level, not nested as opportunities |
| Apply committed | N/A | Feasibility-only mode ("Also Apply" was OFF) |

## Artifact Paths

| Artifact | Path | Format |
| -------- | ---- | ------ |
| JSON report | `artifacts/demo/SCALE_TEST_EVIDENCE.json` | Full `ScaleTestReport` object |
| Markdown report | `artifacts/demo/SCALE_TEST_EVIDENCE.md` | Human-readable summary with thresholds + bottleneck notes |

Both are written by `POST /api/v1/dev/write-artifacts` with `filename_prefix=SCALE_TEST_EVIDENCE`.
Both are git-ignored via `artifacts/demo/SCALE_TEST_EVIDENCE.*` in `.gitignore`.

## Known Bottlenecks

| Area | Observation | Mitigation |
| ---- | ----------- | ---------- |
| **Feasibility compute** | 474 s for 14 sats × 1000 targets × 14d — adaptive time-stepping helps but still O(n²) | Parallel workers active; future: batch chunking, caching |
| **Response payload** | **294 MB** JSON — 115k passes serialised in a single response | Critical: add pagination, streaming, or summary-only mode |
| **Memory growth** | RSS jumps from 147 MB → 3.2 GB (+3 GB) — mostly from building 294 MB JSON in-memory | Consider streaming JSON serialisation or CZML-only responses |
| **No GC reclaim** | RSS stays elevated after response is sent | Python GC doesn't return arena memory to OS; restart or pool recycling needed |
| **Single response** | Client must hold 294 MB in memory to parse | Paginate or stream results; return pass IDs + summary first |

> When response > 50 MB, the artifact markdown now includes a highlighted
> **"Primary Bottleneck: Response Serialization"** section with recommended next actions.

## Pass / Fail Criteria

| Criterion | Threshold | Result | Status |
| --------- | --------- | ------ | ------ |
| Feasibility completes without crash | HTTP 200 or captured error | HTTP 200, 115k passes | ✅ PASS |
| Wall time | < 600 s (10 min budget) | 474.5 s | ✅ PASS |
| Response size | < 100 MB warn / < 250 MB fail | 294.2 MB | ❌ FAIL |
| Backend RSS after | < 4 GB warn / < 6 GB fail | 3,202 MB | ⚠️ WARN |
| Artifacts written | Both `.json` and `.md` exist | Written to `artifacts/demo/` | ✅ PASS |
| Request contains 1000 targets | `request_payload_bytes > 0`, target count = 1000 | 85.5 KB, 1000 targets | ✅ PASS |
| Report includes memory metric | `backend_rss_mb_after` is non-null | 3,202.4 MB | ✅ PASS |
| Dev gating: 403 when DEV_MODE=0 | `GET /api/v1/dev/metrics` returns 403 | Verified | ✅ PASS |
| Dev gating: UI hidden outside dev | Scalability section absent in production build | By design (`import.meta.env.DEV`) | ✅ PASS |

> **Note:** RSS at 3.2 GB triggers WARN (< 4 GB threshold). Response at 294 MB triggers
> FAIL (> 250 MB threshold). Lower satellite count (e.g. 10) to stay within safe budgets.
> The 294 MB response payload is the primary driver — consider pagination for production use.

## Guardrail UX Behavior

1. **Satellite selector** — 3 buttons (10 / 20 / 50) above the run button; default = 50
2. **Risk score display** — shown next to selector as `risk: N` (targets × sats × days)
3. **Warning banner** — red banner appears when risk > 200,000; advises lowering sat count
4. **Confirmation dialog** — shows risk score; high-risk runs get red "Confirm High-Risk Run" button
5. **Threshold results** — displayed inline after run with ✅/⚠️/❌ per metric
6. **Artifact bottleneck section** — when response > 50 MB, markdown report includes analysis + recommended next actions

## Verification Steps

1. **Start dev servers**: `make dev` (backend on :8000, frontend on :3000)
2. **Open Demo Runner** panel in the left sidebar (requires Developer Mode ON)
3. **Select satellite count** — click "10" in the satellite selector
4. **Click "Scalability (1000t / 14d / 10s)"** button
5. **Confirm** in the dialog that appears (should NOT show high-risk warning at 10 sats)
6. **Observe** step log: target generation → satellite load → metrics → feasibility → thresholds → artifacts
7. **Verify threshold results** — inline PASS/WARN/FAIL display appears below the run section
8. **Check artifacts**:
   - `artifacts/demo/SCALE_TEST_EVIDENCE.json` — verify `params.target_count === 1000`
   - `artifacts/demo/SCALE_TEST_EVIDENCE.md` — verify thresholds table + bottleneck section (if response > 50 MB)
9. **Test high-risk warning**: select 50 sats → verify red warning banner + "Confirm High-Risk Run" button
10. **Check `/api/v1/dev/metrics` new fields**:
    - `curl localhost:8000/api/v1/dev/metrics` → verify `last_response_bytes`, `last_pass_count`, `last_request_params`, `gc_stats` present
11. **Check dev gating**:
    - `DEV_MODE=0 curl localhost:8000/api/v1/dev/metrics` → expect 403
    - Production build (`npm run build`) → Demo Runner panel should not render
12. **Update this doc** with actual numbers from the run

## Files Changed

| File | Change |
| ---- | ------ |
| `backend/routers/dev.py` | Extended `GET /metrics` with `last_response_bytes`, `last_pass_count`, `last_request_params`, `gc_stats`. Added `LastRequestParams` and `GcStats` models. |
| `frontend/src/api/config.ts` | Added `DEV_METRICS` endpoint constant |
| `frontend/src/dev/demo/scenarios.ts` | Added `SAT_COUNT_OPTIONS`, `DEV_THRESHOLDS` config, `computeRiskScore()`, `evaluateThresholds()`, threshold types |
| `frontend/src/components/DemoScenarioRunner.tsx` | Added satellite selector, risk warning banner, threshold evaluation + display, updated `buildScaleMarkdown` with thresholds table + bottleneck section |
| `.gitignore` | Added `artifacts/demo/SCALE_TEST_EVIDENCE.*` |
| `docs/PR_E2E_005_CHECKLIST.md` | Updated with guardrail behavior, threshold config, verification steps |

## Non-Goals

- No scheduling algorithm changes
- No UI changes outside dev runner panel
- No persistence schema migrations
- No production endpoint changes
- No pagination implementation (only reporting + guardrails)
