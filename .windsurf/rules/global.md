---
description: Global project rules for COSMOS42 - Satellite Mission Planning Tool
---

# COSMOS42 — Global Project Rules

**Always On**

## Project Overview

COSMOS42 is a fullstack satellite mission planning tool:
- **Backend**: Python 3.11+ / FastAPI (port 8000), PDM for deps
- **Frontend**: React 18 / TypeScript / Vite (port 3000), Cesium/Resium 3D globe
- **Core library**: `src/mission_planner/` — orbit propagation, visibility, scheduling, SAR
- **Config**: YAML files in `config/` (satellites, ground stations, SAR modes, policies)
- **State management**: Zustand stores (frontend), React Query for server state
- **Styling**: TailwindCSS with custom space theme (`space-blue`, `orbit-yellow`, etc.)

## Architecture Boundaries

<architecture>
- `src/mission_planner/` — Pure Python library. NO FastAPI imports. NO backend imports.
- `backend/` — FastAPI app. Imports from `src/mission_planner/`. Has its own routers, validation, persistence.
- `frontend/src/` — React app. Communicates with backend ONLY via `/api` proxy to port 8000.
- `config/` — YAML config files loaded by backend's `ConfigManager`. Never hardcode config values.
- `tests/` — Mirrors src structure. Unit tests in `tests/unit/`, integration in `tests/integration/`.
</architecture>

## Critical Conventions

<conventions>
- Python line length: 88 (Black). Indent: 4 spaces.
- TypeScript/TSX indent: 2 spaces. Strict mode enabled.
- All Python functions MUST have type hints (mypy strict).
- Use Pydantic v2 models for all API request/response schemas.
- Frontend path alias: `@/` maps to `frontend/src/`.
- Never commit `.env`, `.env.local`, or API keys.
- Cesium Ion token is loaded from `VITE_CESIUM_ION_TOKEN` env var.
- All coordinates use WGS84 (lat/lon in degrees). Elevations in degrees for masks.
- Time handling: UTC everywhere. Use `datetime` (Python) and `Date`/ISO-8601 (TypeScript).
</conventions>

## Dev Commands

<commands>
- `make dev` — Start both servers (backend:8000 + frontend:3000)
- `make test-py` — Run Python tests with pytest
- `make test-fe` — Run frontend tests with vitest
- `make lint` — Lint both Python and TypeScript
- `make format-py` — Black + isort
- `make precommit` — Full pre-commit check (format + lint + typecheck + test)
</commands>

## File Size Policy

<file_size>
- NEVER let a single file exceed 500 lines without proposing a refactor.
- When adding to large files (>300 lines), prefer extracting to a new module.
- Known large files that need eventual refactoring (do NOT make worse):
  - `backend/main.py` (4058 lines) — monolith, use routers instead
  - `backend/schedule_persistence.py` (3166 lines)
  - `src/mission_planner/visibility.py` (2697 lines)
  - `src/mission_planner/scheduler.py` (2344 lines)
  - `frontend/src/components/AdminPanel.tsx` (2867 lines)
  - `frontend/src/components/MissionPlanning.tsx` (2079 lines)
  - `frontend/src/context/MissionContext.tsx` (983 lines)
</file_size>

## Enforced Architecture Rules (from audit)

<enforced>
- NEVER add new Pydantic schemas to `backend/main.py` — put them in `backend/schemas/`.
- NEVER add new endpoints to `backend/main.py` — use routers in `backend/routers/`.
- NEVER add new state to `MissionContext.tsx` — use a Zustand store instead.
- NEVER use raw `fetch()` in frontend — use `apiClient` from `api/client.ts`.
- NEVER hardcode API base URLs in individual API modules — use `API_BASE_URL` from `api/config.ts`.
- ALL new Zustand stores MUST use `devtools()` middleware in dev mode.
- ALL new React Query hooks MUST use centralized query key factories.
- Prefer `useShallow` from `zustand/shallow` when selecting multiple store fields in perf-critical components.
- Use `React.memo` on list item/row components in data tables.
</enforced>

## Safety Rules

<safety>
- Never modify `config/*.yaml` without explicit user request.
- Never delete or weaken existing tests.
- Always preserve existing API contracts (request/response shapes).
- Prefer minimal upstream fixes over downstream workarounds.
</safety>
