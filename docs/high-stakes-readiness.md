# High-Stakes Readiness

This project is not yet signed off for life-critical operator use.

## What Is Proven

- The non-live planning/apply/conflict UI flow passes local Playwright coverage.
- The direct-commit path now rechecks conflicts at commit time and persists conflict state.
- Backend regression coverage now exercises direct preview, forced conflict persistence, workspace scoping, and incremental planning invariants.
- At least one real live drill passed against the actual backend and frontend:
  - `frontend/tests/e2e/multi-satellite-visualization.spec.ts`

## What Is Not Yet Proven

- Full live operator drills are not yet green end to end.
- Multi-operator races are only partially covered in backend tests.
- We do not yet have a formal fail-closed safety case for all commit paths.
- We do not yet have replay packs from real historical mission scenarios with expected outcomes.
- We do not yet have large randomized stress coverage for schedule-state transitions under concurrency and degraded network conditions.

## Current Blocking Risks

1. Live-drill instability still exists.
   Real backend/UI runs are now possible, but some live Playwright drills still need harness hardening and deeper investigation.

2. Default-workspace contamination is operationally risky.
   Ad hoc runs against the shared default workspace can accumulate acquisitions and persisted conflicts that confuse later operator flows.

3. Force-apply remains dangerous.
   The system now predicts and persists conflicts more reliably, but a force path still exists and needs stronger procedural and product guardrails.

4. Performance under conflict-heavy commits is not yet acceptable for trust.
   In live backend logs, some direct commits and conflict reads can become slow when conflict volume rises.

5. Safety evidence is still fragmented.
   We have stronger automated proof than before, but not yet the full validation package expected for high-stakes deployment.

## Required Next Steps

1. Green the remaining live Playwright drills with `PLAYWRIGHT_LIVE_OPERATOR=1`.
2. Add race-condition and stale-preview commit tests for all commit variants.
3. Isolate or reset the default workspace during test and operator flows.
4. Add scenario replay suites with known-good expected schedules and known-bad rejection cases.
5. Add load and latency thresholds for conflict detection and direct commit.
6. Add stronger product interlocks around force-apply and unresolved conflicts.

## Recommendation

Treat the system as suitable for internal evaluation and supervised test operations, not unsupervised high-stakes operator use, until the blockers above are closed.
