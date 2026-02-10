---
description: Testing rules and conventions for both Python and TypeScript test suites
---

# Testing Rules

**Glob: tests/**/*.py, frontend/src/**/__tests__/**/*.*

## General Principles

- Never delete or weaken existing tests without explicit direction.
- Write tests BEFORE or alongside implementation, not as an afterthought.
- Each test should be independent and not rely on execution order.
- Use descriptive test names that explain what is being tested and expected outcome.

## Python Tests (pytest)

- Location: `tests/unit/`, `tests/integration/`, `tests/e2e/`.
- Naming: `test_{module}.py` → `test_{module}_advanced.py` → `test_{module}_extended.py` for additional coverage.
- Use shared fixtures from `tests/conftest.py`:
  - `sample_tle_lines` — raw TLE strings for ICEYE-X44
  - `sample_satellite` — `SatelliteOrbit` instance
  - `sample_target` / `sample_targets` — `GroundTarget` instances
  - `base_datetime` / `time_range` — standard test time windows
  - `scheduler_config` — default `SchedulerConfig`
  - `test_client` — FastAPI `TestClient` (no server needed)
- Markers: `@pytest.mark.slow`, `@pytest.mark.requires_server`, `@pytest.mark.integration`.
- Timeout: 30s default. Adjust with `@pytest.mark.timeout(60)` for slow tests.
- Coverage: `--cov=src/mission_planner --cov-report=term-missing`.

## Frontend Tests (Vitest)

- Location: `frontend/src/components/ui/__tests__/`, `frontend/src/test/`.
- Use `@testing-library/react` for component rendering.
- Use `@testing-library/user-event` for user interaction simulation.
- Mock API calls; never make real HTTP requests in unit tests.

## Running Tests

- Python: `make test-py` or `.venv/bin/pytest tests/ -v`
- Frontend: `make test-fe` or `cd frontend && npm run test:run`
- Full suite: `make test`
- Watch mode (frontend): `cd frontend && npm run test`
