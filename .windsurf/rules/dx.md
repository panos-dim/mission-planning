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

- Pre-commit hooks: trailing-whitespace, end-of-file-fixer, Black, isort, flake8, ESLint.
- Run `make precommit` before pushing to verify everything passes.
- Large files (>1000KB) are blocked by pre-commit. Keep assets out of git.

## Helpful Shortcuts

- `make dev` — Start everything (kills existing port users, starts backend + frontend).
- `./run_dev.sh --monitor` — Start with CPU/memory monitoring.
- `make backend` — Backend only with hot reload.
- `make frontend` — Frontend only.
- Node 22 required (Vite 7). Use `nvm use 22`.
