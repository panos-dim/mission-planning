---
description: Codebase audit findings and optimization roadmap — reference for Cascade and developers
---

# Codebase Audit — Findings & Optimization Roadmap

**Model Decision: Reference when discussing refactoring, architecture improvements, or DX optimization**

## Severity Legend

- P0 — Critical architecture debt (blocks scaling)
- P1 — High impact DX/quality improvement
- P2 — Medium improvement (nice-to-have)

---

## P0 — Critical Architecture Issues

### 1. `backend/main.py` is a 4058-line monolith with 44 endpoints

- **Problem**: All Pydantic schemas (~30 models), helper functions, global state, and 44 `@app.*` route handlers live in one file. This violates single-responsibility and makes the file nearly impossible to navigate or safely modify.
- **Industry standard**: FastAPI apps should use `APIRouter` per domain, with schemas in separate `schemas.py` files and business logic in service modules.
- **Fix**: Extract into layered modules:
  - `backend/schemas/` — All Pydantic request/response models (TLEData, TargetData, MissionRequest, etc.)
  - `backend/services/` — Business logic (mission analysis, constellation support, pass enrichment)
  - `backend/routers/mission.py` — Mission endpoints (analyze, plan, enrich)
  - `backend/routers/tle.py` — TLE validation/search endpoints
  - `backend/routers/debug.py` — Debug/benchmark endpoints
  - `backend/deps.py` — Dependency injection (config_manager, satellite_manager, etc.)
- **Effort**: Large, multi-PR refactor. Start with schemas extraction.

### 2. Global mutable state in `backend/main.py`

- **Problem**: `_opportunities_cache`, `current_mission_data` are module-level mutable globals — not thread-safe, not testable, will break under concurrent requests.
- **Industry standard**: Use FastAPI dependency injection with `app.state`, or a proper cache (Redis, lru_cache with TTL).
- **Fix**: Move to `app.state` or inject via `Depends()`.

### 3. `MissionContext.tsx` (984 lines) mixes concerns

- **Problem**: Contains reducer, 14 action types, API calls (validateTLE, analyzeMission), Cesium viewer management, workspace persistence, and scene object CRUD — all in one context.
- **Industry standard**: Split into domain-specific Zustand stores (the project already has 14 stores — this context should follow the same pattern).
- **Fix**: Migrate remaining state to Zustand stores:
  - `missionDataStore` — mission results, CZML, loading state
  - `workspaceStore` — workspace CRUD (partially done in `workspaces.ts` API)
  - `sceneObjectStore` — scene object management
  - Keep `MissionContext` as a thin provider for Cesium viewer ref only.

---

## P1 — High Impact DX Improvements

### 4. No FastAPI lifespan handler (deprecated `on_event`)

- **Problem**: Uses `@app.on_event("shutdown")` which is deprecated in FastAPI 0.109+.
- **Fix**: Migrate to the `lifespan` context manager pattern:
  ```python
  from contextlib import asynccontextmanager

  @asynccontextmanager
  async def lifespan(app: FastAPI):
      # Startup
      config_manager.load_config()
      yield
      # Shutdown
      cleanup_process_pool()

  app = FastAPI(lifespan=lifespan)
  ```

### 5. No query key factory pattern in React Query

- **Problem**: `queryKeys` exist in `lib/queryClient.ts` but `scheduleApi.ts` hardcodes its own `API_BASE_URL` and doesn't use the shared API client or query keys.
- **Industry standard**: All API modules should use the shared `apiClient` from `api/client.ts` and all queries should use centralized query key factories.
- **Fix**: Refactor `scheduleApi.ts` to use `apiClient` and add schedule query keys to the factory.

### 6. `scheduleApi.ts` duplicates API client logic

- **Problem**: This 1344-line file defines its own `fetch` calls with `API_BASE_URL` instead of using the shared `apiClient` with retry/timeout/error handling.
- **Fix**: Refactor to use `apiClient.get()`, `apiClient.post()`, etc.

### 7. Frontend types duplicated between backend and frontend

- **Problem**: `TLEData`, `TargetData`, `AcquisitionSummary`, `HorizonInfo` etc. are defined independently in both `backend/main.py` (Pydantic) and `frontend/src/types/index.ts` + `frontend/src/api/scheduleApi.ts` (TypeScript). They can drift.
- **Industry standard**: Generate TypeScript types from OpenAPI spec (FastAPI auto-generates `/docs`).
- **Fix**: Use a tool like `openapi-typescript` to generate frontend types from backend's OpenAPI JSON.

### 8. `AdminPanel.tsx` (2867 lines) — monolith component

- **Problem**: Single component handling satellite config, ground station management, SAR modes, config snapshots, workflow validation — all with inline state and API calls.
- **Fix**: Split into sub-components:
  - `AdminPanel/SatelliteConfig.tsx`
  - `AdminPanel/GroundStationManager.tsx`
  - `AdminPanel/SARModeEditor.tsx`
  - `AdminPanel/ConfigSnapshots.tsx`
  - `AdminPanel/WorkflowValidation.tsx`

### 9. Zustand stores lack `devtools` middleware

- **Problem**: None of the 14 Zustand stores use `devtools()` middleware, making state debugging harder.
- **Industry standard**: Wrap all stores with `devtools()` in development for Redux DevTools integration.
- **Fix**: Add `devtools()` wrapper to each store (conditionally in dev mode).

### 10. No `React.memo` on heavy list item components

- **Problem**: Components like opportunity lists, acquisition tables, and target lists re-render on every parent update. No `React.memo` wrappers found on list item components.
- **Fix**: Add `React.memo` to row/item components in results tables and lists. Use `useCallback` for event handlers passed as props.

### 11. Missing Zustand shallow selectors

- **Problem**: Stores like `useVisStore`, `useSelectionStore` are consumed with object destructuring which causes re-renders on any state change.
- **Industry standard**: Use `useShallow` from `zustand/shallow` when selecting multiple fields.
- **Fix**: Replace `const { a, b } = useStore()` with `const { a, b } = useStore(useShallow(s => ({ a: s.a, b: s.b })))` in performance-critical components (especially Cesium-related).

---

## P2 — Medium Improvements

### 12. CORS allows all origins

- **Problem**: `allow_origins=["*"]` is fine for dev but should be restricted in production.
- **Fix**: Use environment variable for allowed origins.

### 13. No structured logging

- **Problem**: Backend uses basic `logging` module with string formatting (`f"..."`).
- **Industry standard**: Use structured logging (e.g., `structlog` or JSON formatter) for production observability.
- **Fix**: Add `structlog` or configure JSON log formatter for production mode.

### 14. `sys.path.insert` for imports in `backend/main.py`

- **Problem**: Manual `sys.path` manipulation is fragile and non-standard.
- **Fix**: Use proper package installation (`pip install -e .`) and relative imports. The `pyproject.toml` already supports this via `mission-planner` entry point.

### 15. No API versioning consistency

- **Problem**: Some routes use `/api/v1/schedule/...`, others use `/api/mission/...`, `/api/tle/...` — inconsistent versioning.
- **Fix**: Standardize all routes under `/api/v1/` prefix.

### 16. Lazy loading defined but not fully used

- **Problem**: `lazy.ts` defines lazy components but `App.tsx` directly imports `MultiViewContainer` and `LeftSidebar` without lazy loading.
- **Fix**: Use `LazyMultiViewContainer` with `Suspense` in `App.tsx` for the heavy Cesium components.

### 17. `useReducer` in `MissionContext` — legacy pattern

- **Problem**: `useReducer` with string action types is verbose and error-prone vs Zustand's direct state mutations.
- **Fix**: When migrating to Zustand stores (P0-3), use direct `set()` calls instead of reducer dispatch.

### 18. No `ErrorBoundary` around lazy-loaded components

- **Problem**: `lazy.ts` defines lazy components but there's no `Suspense` fallback wrapper co-located with them.
- **Fix**: Create a `SuspenseWrapper` component that combines `Suspense` + `ErrorBoundary`.

---

## What's Already Good

- **API client** (`api/client.ts`) — Well-structured with retry, timeout, abort signal merging, and typed error classes.
- **Error hierarchy** (`api/errors.ts`) — Clean class hierarchy with type guards.
- **Zustand store architecture** — 14 focused stores with barrel exports, good naming convention.
- **React Query hooks** — Proper mutation/query separation with cache invalidation.
- **Pre-commit hooks** — Black, isort, flake8, ESLint all configured.
- **EditorConfig** — Consistent formatting across editors.
- **Router pattern** — 6 routers already extracted (schedule, workspaces, orders, batching, config_admin, validation).
- **Type safety** — mypy strict mode for Python, TypeScript strict mode for frontend.
- **Config management** — YAML-based with ConfigManager, good separation of concerns.
- **Lazy loading foundation** — `lazy.ts` exists as a starting point.
- **Test infrastructure** — Good fixture catalog in conftest.py, proper marker system.
