# PR-PARAM-GOV-01: Parameter Governance Checklist

## Summary

Centralise platform/sensor constants in YAML/admin config, reduce UI noise, add
robust validation with safe fallbacks, and hide advanced options behind an
accordion collapsed by default.

---

## Changes

### Documentation

- [x] `docs/PARAMETER_GOVERNANCE_RULES.md` — governance tiers, enforcement matrix

### Backend

- [x] `backend/routers/config_admin.py` — `GET /api/v1/config/satellite-config-summary`
  endpoint returning read-only bus limits, sensor specs, SAR defaults
- [x] `backend/config_resolver.py` — existing `ADMIN_ONLY_PARAMS` enforcement
  (no changes needed, already rejects overrides)

### Frontend — MissionPlanning.tsx

- [x] **Imports**: added `ChevronDown`, `ChevronUp`, `Settings`, `Shield`,
  `COLLAPSED_BY_DEFAULT`, `ApiError`, `NetworkError`, `TimeoutError`
- [x] **State**: `showAdvancedPlanning` (collapsed by default), `configSummary`
  fetched from `/api/v1/config/satellite-config-summary`
- [x] **Basic section** (always visible): Scoring Strategy preset buttons +
  weight visualisation bar
- [x] **Advanced accordion** (collapsed by default): Imaging Time, Look Window,
  Value Source, Quality Model, Band params, Fine-tune weight sliders
- [x] **Developer-only section** (inside Advanced, gated on `showAdvancedOptions`):
  Spacecraft Agility inputs (roll/pitch rate/accel)
- [x] **Config Summary** (read-only): platform config block inside Advanced
  accordion showing bus + sensor specs per satellite
- [x] **Dead code removal**: removed `SoftLockPolicy` import, state, request
  payload field, and UI select (soft locks removed in backend migration v2.2)
- [x] **Error handling**: HTTP error extraction for standard planning path;
  human-readable messages for `ApiError`, `NetworkError`, `TimeoutError`

---

## What is NOT changed

- No scheduling algorithm changes
- No changes to mission analysis flow
- No changes to YAML config file structure
- No backend schema migrations
- No changes to existing API contracts (only additions)

---

## Verification

### Manual

1. Open Mission Planning panel — confirm "Scoring Strategy" presets visible, Advanced accordion collapsed
2. Expand Advanced — confirm Imaging Time, Look Window, Value Source, Quality Model, weight sliders visible
3. In developer/debug mode — confirm Spacecraft Agility inputs appear inside Advanced
4. Confirm Config Summary shows satellite bus/sensor specs (read-only)
5. Confirm Soft Lock Policy dropdown is gone from repair mode
6. Trigger a backend error — confirm human-readable message appears (not generic "Failed to run planning")

### Automated

```bash
# Backend tests (existing — should still pass)
make test-backend

# Frontend lint
cd frontend && npm run lint

# Frontend type-check
cd frontend && npx tsc --noEmit
```

---

## Rollback

All changes are additive to the frontend and a single new endpoint on the backend.
Revert the commit to restore previous behaviour. No migrations to reverse.
