---
description: Python backend rules for FastAPI API and core mission planner library
---

# Backend Rules

**Glob: backend/**/*.py, src/**/*.py**

## Python Style

- Formatter: Black (line-length 88). Import sorter: isort (profile "black").
- Type hints on ALL function signatures (mypy strict mode enforced).
- Docstrings: use Google-style for public functions/classes.
- Prefer early returns to reduce nesting.
- Use `logging` module, never `print()` in production code.
- Use `pathlib.Path` over `os.path` for file operations.

## FastAPI Backend (`backend/`)

- All new endpoints go in `backend/routers/*.py`, NEVER in `backend/main.py`.
- Use Pydantic v2 `BaseModel` for request/response schemas with `Field()` descriptions.
- Use `field_validator` and `model_validator` (Pydantic v2 API), not v1 `validator`.
- HTTP errors: raise `HTTPException` with meaningful detail messages.
- Router prefix convention: `/api/{resource}` (e.g., `/api/schedule`, `/api/workspaces`).
- Config is loaded via `backend.config_manager.ConfigManager` from YAML files in `config/`.
- Persistence layer: `backend/schedule_persistence.py` and `backend/workspace_persistence.py`.

## Core Library (`src/mission_planner/`)

- This is a PURE library — no FastAPI, no backend imports, no HTTP concerns.
- Entry point: `mission_planner.cli` (Click-based CLI).
- Key modules and their responsibilities:
  - `orbit.py` — `SatelliteOrbit` class, TLE parsing, orbit propagation via `orbit-predictor`
  - `visibility.py` — `VisibilityCalculator`, pass computation, elevation masks
  - `scheduler.py` — `MissionScheduler`, `SchedulerConfig`, `AlgorithmType`, optimization (PuLP)
  - `planner.py` — `MissionPlanner`, orchestrates orbit + visibility + scheduling
  - `targets.py` — `GroundTarget`, `TargetManager` with priority system (1-5)
  - `sar_visibility.py` / `sar_config.py` — SAR-specific imaging modes and calculations
  - `quality_scoring.py` — Multi-criteria quality model with weight presets
  - `parallel.py` — Process pool for parallel computation, cleanup on shutdown
  - `conflict_resolution.py` — Satellite conflict detection and resolution
  - `sunlight.py` — Solar illumination calculations

## Domain Conventions

- Angles: degrees (not radians) at API boundaries; convert internally as needed.
- Coordinates: WGS84, latitude before longitude in function signatures.
- Time: always UTC `datetime` objects. Never naive datetimes without explicit UTC.
- Distances: kilometers for orbital altitudes, meters for ground distances.
- TLE data: Two-Line Element format from CelesTrak. Satellite names are case-sensitive.
- Roll/pitch angles: degrees per second for slew rates.
- Elevation mask: minimum elevation angle (degrees) for satellite visibility.

## Testing

- Test files: `tests/unit/test_{module}.py` mirroring `src/mission_planner/{module}.py`.
- Use fixtures from `tests/conftest.py` (`sample_satellite`, `sample_target`, etc.).
- Integration tests that need the server: mark with `@pytest.mark.requires_server`.
- Default timeout: 30s per test. Mark slow tests with `@pytest.mark.slow`.
- Run: `make test-py` or `.venv/bin/pytest tests/ -v`.

## Dependencies

- Package manager: PDM. Lockfile: `pdm.lock`. Config: `pyproject.toml`.
- Key deps: `orbit-predictor`, `numpy`, `pandas`, `pydantic`, `fastapi`, `pulp`, `cartopy`.
- Dev deps: `pytest`, `pytest-cov`, `black`, `isort`, `mypy`, `flake8`, `httpx`.
- Python version: >=3.11.
