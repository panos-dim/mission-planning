# Mission Planning

Interactive satellite mission planning system with:

- FastAPI backend for feasibility, planning, repair, scheduling, and workspace persistence
- React + Vite frontend for mission planners
- Shared planning engine and legacy CLI modules in `src/mission_planner/`

The day-to-day product is the web app, not the old static Cartopy flow.

## Prerequisites

- Python `3.11+`
- Node `22.x`
- npm `10+`
- `pdm` for dependency installation

Node version is pinned in [`./.nvmrc`](./.nvmrc). If you use `nvm`:

```bash
nvm install
nvm use
```

## Quick Start

Install everything:

```bash
make install
```

Start backend + frontend together:

```bash
make dev
```

Or directly:

```bash
./run_dev.sh
```

App URLs:

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend: [http://localhost:8000](http://localhost:8000)
- OpenAPI: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

Notes:

- `run_dev.sh` uses `.venv/bin/python` automatically when present, so `pdm` does not need to be on `PATH` for normal dev runs.
- The script now refuses to kill unrelated processes already using ports `3000` or `8000`.
- After backend startup it regenerates frontend API types from the live OpenAPI schema.

## Common Commands

```bash
make dev
make test
make lint
make build
make release-gate
```

Useful focused commands:

```bash
make backend
make frontend
make test-py
make test-fe
make lint-fe
make lint-fe-strict
```

## Verification

Local release verification:

```bash
make release-gate
```

This starts the backend on a disposable port, checks `/health` and `/ready`, runs backend suites, runs frontend tests, builds the frontend bundle, and fails if the route-latency snapshot contains `5xx` responses.

## Repository Layout

```text
mission-planning/
├── backend/                 FastAPI app, routers, schedulers, persistence
├── frontend/                React/Vite mission planner UI
├── src/mission_planner/     Shared legacy planning/CLI modules
├── tests/                   Unit, integration, and E2E coverage
├── scripts/                 Dev and release helpers
├── run_dev.sh               Local full-stack startup
└── Makefile                 Common developer commands
```

## Legacy CLI

The legacy Python package still exists and is useful for lower-level algorithm work, but the primary operator workflow is the web application.

If you need the older CLI-oriented docs, see [`scripts/README.md`](./scripts/README.md) and the modules under [`src/mission_planner`](./src/mission_planner).

## Troubleshooting

- `make install` fails with missing `pdm`:
  Install it with `python3 -m pip install pdm`
- `make dev` says a port is already in use:
  Stop the listed process, then rerun
- Frontend schema feels stale:
  Restart `make dev` or run `cd frontend && npm run generate:api-types`
- Strict frontend lint still fails:
  Run `npm run lint` for the local warning view and `npm run lint:strict` when cleaning the backlog

## License

MIT. See [`LICENSE`](./LICENSE).
