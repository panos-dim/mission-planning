---
description: Developer experience and workflow optimization rules
---

# Developer Experience Rules

**Always On**

## Code Change Discipline

- Prefer minimal, focused edits. One logical change per edit.
- Always read the target file before editing. Preserve existing patterns and style.
- Do not refactor unrelated code while fixing a bug.
- When adding to a file >300 lines, consider if the addition belongs in a new module.
- Imports always at the top of the file, never inline.

## Debugging

- Address root cause, not symptoms.
- Add descriptive log messages with variable state before guessing at fixes.
- Use `make test-py` to verify Python changes. Use `make test-fe` for frontend.
- For backend API issues: check `backend/routers/` first, then `backend/main.py`.
- For frontend rendering issues: check component → store → API layer in that order.

## Performance Awareness

- Backend hot-reloads via `uvicorn --reload`. Frontend hot-reloads via Vite HMR.
- Cesium is heavy — avoid unnecessary re-renders of globe components.
- Use React Query caching. Don't refetch data that hasn't changed.
- Python `parallel.py` uses process pools — always call `cleanup_process_pool()` on shutdown.
- Scheduler uses PuLP for ILP — large problem instances can be slow; consider greedy fallback.

## Common Pitfalls

- `backend/main.py` is 4000+ lines. Adding endpoints there is WRONG — use routers.
- `MissionContext.tsx` is 983 lines. Add new state to Zustand stores, not here.
- Cesium token must be in `frontend/.env.local` as `VITE_CESIUM_ION_TOKEN=...`.
- Python path setup in `backend/main.py` uses `sys.path.insert` — fragile but necessary.
- Frontend proxy in `vite.config.ts` forwards `/api` to port 8000 — both servers must be running.
- YAML config files in `config/` are loaded at backend startup via `ConfigManager`.

## Git & Pre-commit

- Pre-commit hooks: trailing-whitespace, end-of-file-fixer, Black, isort, flake8, Prettier, ESLint.
- Run `make precommit` before pushing to verify everything passes.
- Large files (>1000KB) are blocked by pre-commit. Keep assets out of git.

## Formatting

- Python: Black + isort (via `make format-py`).
- Frontend: Prettier (via `make format-fe`). Config in `frontend/.prettierrc.json`.
- `make format` runs both Python and frontend formatters.
- ESLint uses flat config (`frontend/eslint.config.js`) with `eslint-config-prettier` to avoid conflicts.

## Dependency Management

- Python: PDM with lockfile (`pdm.lock`). Use `pdm add <pkg>` / `pdm install --dev`.
- Frontend: npm with `package-lock.json`. Use `npm install` / `npm ci`.
- All Makefile targets use `pdm run` instead of `.venv/bin/...`.

## API Types

- `run_dev.sh` auto-generates TypeScript types from the backend OpenAPI schema on startup.
- Manual: `cd frontend && npm run generate:api-types` (backend must be running).
- Generated types land in `frontend/src/api/generated/api-types.ts`.

## CI

- GitHub Actions in `.github/workflows/ci.yml`.
- PR: lint + typecheck + unit tests (Python parallel via xdist, frontend via vitest).
- Push to main: also runs integration tests.

## Helpful Shortcuts

- `make dev` — Start everything (kills existing port users, auto-generates API types, starts backend + frontend).
- `./run_dev.sh --monitor` — Start with CPU/memory monitoring.
- `make backend` — Backend only with hot reload.
- `make frontend` — Frontend only.
- `make format` — Format all code (Python + frontend).
- Node 22 required (Vite 7). Use `nvm use 22`.
- Python 3.11 pinned via `.python-version`.
