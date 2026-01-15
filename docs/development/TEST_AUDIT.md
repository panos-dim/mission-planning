# Test Suite Audit & Coverage Improvement Plan

**Generated**: December 2025
**Current Status**: 60 tests passing, 9% coverage

---

## Executive Summary

The test suite has structural issues preventing proper execution:

| Issue | Count | Impact |
|-------|-------|--------|
| Scripts masquerading as tests | 25+ files | Hang on collection |
| Tests requiring live server | 10+ files | Fail without backend |
| Proper pytest tests | ~15 files | Work correctly |

**Root Cause**: Many "test" files are actually debug/analysis scripts with module-level code that executes during pytest collection, causing hangs and failures.

---

## Current Test Inventory

### ✅ Working Tests (60 total)

#### Unit Tests (`tests/unit/`) - **37 tests, 2.3s**

| File | Tests | Status |
|------|-------|--------|
| `test_conflict_resolution.py` | 12 | ✅ Pass |
| `test_constellation_models.py` | 10 | ✅ Pass |
| `test_orbit.py` | 6 | ✅ Pass |
| `test_satellite_factory.py` | 9 | ✅ Pass |

#### Frontend Tests (`frontend/src/`) - **23 tests, 5.7s**

| File | Tests | Status |
|------|-------|--------|
| `Button.test.tsx` | 7 | ✅ Pass |
| `Card.test.tsx` | 8 | ✅ Pass |
| `Input.test.tsx` | 8 | ✅ Pass |

### ⚠️ Problematic Tests

#### Integration Tests with Module-Level Code (SCRIPTS)

These files execute code at import time, causing pytest to hang:

| File | Issue | Fix Required |
|------|-------|--------------|
| `test_45deg_analysis.py` | Script, not test | Refactor to functions |
| `test_aggressive_maneuvers.py` | Script, not test | Refactor to functions |
| `test_all_algorithms.py` | Script, not test | Refactor to functions |
| `test_complex_scenario.py` | Script, not test | Refactor to functions |
| `test_edge_of_fov.py` | Script, not test | Refactor to functions |
| `test_extended_mission_planning.py` | Script, not test | Refactor to functions |
| `test_extreme_pitch.py` | Script, not test | Refactor to functions |
| `test_extreme_slews.py` | Script, not test | Refactor to functions |
| `test_fov_impact_on_passes.py` | Script, not test | Refactor to functions |
| `test_full_pass_pitch.py` | Script, not test | Refactor to functions |
| `test_greece_mission.py` | Script, not test | Refactor to functions |
| `test_greece_validation.py` | Script, not test | Refactor to functions |
| `test_imaging_debug.py` | Script, not test | Refactor to functions |
| `test_pitch_tight_scenario.py` | Script, not test | Refactor to functions |
| `test_pointing_cone_debug.py` | Script, not test | Refactor to functions |
| `test_production_endpoint.py` | Script, not test | Refactor to functions |
| `test_realistic_scenario.py` | Script, not test | Refactor to functions |
| `test_roll_vs_pitch_comparison.py` | Script, not test | Refactor to functions |
| `test_scheduler_algorithms.py` | Script, not test | Refactor to functions |
| `test_sequential_imaging.py` | Script, not test | Refactor to functions |
| `test_tight_limits.py` | Script, not test | Refactor to functions |

#### Tests Requiring Live Server

| File | Tests | Requires |
|------|-------|----------|
| `test_backend_api.py` | 5 | Backend on :8000 |
| `test_incidence_angle_api.py` | 2 | Backend on :8000 |
| `test_production_endpoint.py` | 0 | Backend on :8000 |

#### Properly Structured Integration Tests

| File | Tests | Status |
|------|-------|--------|
| `test_audit_planning.py` | 4 | ✅ Proper structure |
| `test_audit_scenarios.py` | 4 | ✅ Proper structure |
| `test_dynamic_pitch.py` | 3 | ✅ Proper structure |
| `test_parallel_validation.py` | 5 | ✅ Proper structure |
| `test_pitch_maneuvers.py` | 5 | ✅ Proper structure |
| `test_multi_target_optical.py` | 1 | ✅ Proper structure |
| `test_sign_convention.py` | 1 | ✅ Proper structure |
| `test_roll_pitch_algorithm.py` | 1 | ✅ Proper structure |
| `test_mixed_maneuvers.py` | 2 | ✅ Proper structure |
| `test_target_attributes.py` | 1 | ✅ Proper structure |

---

## Coverage Analysis

### Current Coverage: 9%

```
Name                                          Stmts   Miss  Cover
-----------------------------------------------------------------
src/mission_planner/__init__.py                   7      0   100%
src/mission_planner/orbit.py                     90     28    69%
src/mission_planner/targets.py                  138     93    33%
src/mission_planner/utils.py                    104     80    23%
src/mission_planner/sunlight.py                  64     54    16%
src/mission_planner/planner.py                  294    264    10%
src/mission_planner/visibility.py               706    626    11%
src/mission_planner/visualization.py            179    152    15%
src/mission_planner/scheduler.py                756    756     0%
src/mission_planner/parallel.py                 133    133     0%
src/mission_planner/quality_scoring.py           76     76     0%
src/mission_planner/cli.py                      172    172     0%
-----------------------------------------------------------------
TOTAL                                          3170   2885     9%
```

### Target Coverage: 60%+

| Module | Current | Target | Priority |
|--------|---------|--------|----------|
| `scheduler.py` | 0% | 70% | **HIGH** |
| `visibility.py` | 11% | 60% | **HIGH** |
| `planner.py` | 10% | 50% | MEDIUM |
| `quality_scoring.py` | 0% | 80% | MEDIUM |
| `parallel.py` | 0% | 50% | LOW |
| `cli.py` | 0% | 30% | LOW |

---

## Fix Plan

### Phase 1: Immediate Fixes (1-2 hours)

#### 1.1 Move Scripts Out of Tests

Move non-test scripts to `scripts/` folder:

```bash
# Create analysis scripts folder
mkdir -p scripts/analysis

# Move script files (not actual tests)
mv tests/integration/test_45deg_analysis.py scripts/analysis/
mv tests/integration/test_aggressive_maneuvers.py scripts/analysis/
mv tests/integration/test_all_algorithms.py scripts/analysis/
mv tests/integration/test_complex_scenario.py scripts/analysis/
mv tests/integration/test_edge_of_fov.py scripts/analysis/
mv tests/integration/test_extreme_pitch.py scripts/analysis/
mv tests/integration/test_extreme_slews.py scripts/analysis/
mv tests/integration/test_greece_mission.py scripts/analysis/
mv tests/integration/test_greece_validation.py scripts/analysis/
mv tests/integration/test_imaging_debug.py scripts/analysis/
mv tests/integration/test_pitch_tight_scenario.py scripts/analysis/
mv tests/integration/test_pointing_cone_debug.py scripts/analysis/
mv tests/integration/test_realistic_scenario.py scripts/analysis/
mv tests/integration/test_roll_vs_pitch_comparison.py scripts/analysis/
mv tests/integration/test_scheduler_algorithms.py scripts/analysis/
mv tests/integration/test_sequential_imaging.py scripts/analysis/
mv tests/integration/test_tight_limits.py scripts/analysis/
```

Rename files to remove `test_` prefix:

```bash
cd scripts/analysis
for f in test_*.py; do mv "$f" "${f#test_}"; done
```

#### 1.2 Mark Server-Dependent Tests

Add pytest markers for tests requiring a live server:

```python
# tests/conftest.py
import pytest

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "requires_server: test requires backend server running"
    )

@pytest.fixture
def skip_without_server():
    """Skip test if server is not running."""
    import requests
    try:
        requests.get("http://localhost:8000/", timeout=1)
    except requests.exceptions.ConnectionError:
        pytest.skip("Backend server not running")
```

Then mark tests:

```python
@pytest.mark.requires_server
def test_health():
    ...
```

### Phase 2: Add Missing Unit Tests (4-8 hours)

#### 2.1 Scheduler Tests (Priority: HIGH)

Create `tests/unit/test_scheduler.py`:

```python
"""Unit tests for scheduler module."""
import pytest
from datetime import datetime, timedelta
from mission_planner.scheduler import (
    Scheduler,
    SchedulerConfig,
    Opportunity,
    ScheduledOpportunity,
)

class TestSchedulerConfig:
    def test_default_config(self):
        config = SchedulerConfig()
        assert config.max_roll_deg == 45.0
        assert config.max_pitch_deg == 30.0

    def test_custom_config(self):
        config = SchedulerConfig(max_roll_deg=30.0)
        assert config.max_roll_deg == 30.0

class TestOpportunity:
    def test_opportunity_creation(self):
        opp = Opportunity(
            id="test_opp",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(minutes=5),
            incidence_angle=20.0,
        )
        assert opp.id == "test_opp"

    def test_opportunity_duration(self):
        start = datetime.now()
        end = start + timedelta(minutes=5)
        opp = Opportunity(
            id="test",
            satellite_id="sat1",
            target_id="target1",
            start_time=start,
            end_time=end,
            incidence_angle=20.0,
        )
        assert (opp.end_time - opp.start_time).total_seconds() == 300

class TestScheduler:
    def test_first_fit_empty_opportunities(self):
        scheduler = Scheduler(SchedulerConfig())
        result = scheduler.first_fit([])
        assert result == []

    def test_first_fit_single_opportunity(self):
        # Test with single opportunity
        ...

    def test_best_fit_geometry_optimization(self):
        # Test that best_fit prefers better geometry
        ...

    def test_is_feasible_roll_limit(self):
        # Test roll limit enforcement
        ...

    def test_is_feasible_pitch_limit(self):
        # Test pitch limit enforcement
        ...
```

#### 2.2 Visibility Tests (Priority: HIGH)

Create `tests/unit/test_visibility.py`:

```python
"""Unit tests for visibility module."""
import pytest
from datetime import datetime, timedelta
from mission_planner.visibility import VisibilityCalculator
from mission_planner.orbit import SatelliteOrbit
from mission_planner.targets import GroundTarget

class TestVisibilityCalculator:
    @pytest.fixture
    def sample_satellite(self):
        # Create mock or real satellite
        ...

    @pytest.fixture
    def sample_target(self):
        return GroundTarget(
            name="Test",
            latitude=24.44,
            longitude=54.83,
            elevation_mask=10.0,
        )

    def test_elevation_calculation(self):
        # Test elevation angle calculation
        ...

    def test_pass_detection(self):
        # Test that passes are detected correctly
        ...

    def test_imaging_cone(self):
        # Test imaging cone calculation
        ...
```

#### 2.3 Quality Scoring Tests (Priority: MEDIUM)

Create `tests/unit/test_quality_scoring.py`:

```python
"""Unit tests for quality scoring module."""
import pytest
from mission_planner.quality_scoring import (
    monotonic_quality,
    band_quality,
    compute_opportunity_value,
)

class TestMonotonicQuality:
    def test_zero_incidence(self):
        assert monotonic_quality(0.0) == 1.0

    def test_high_incidence(self):
        quality = monotonic_quality(45.0)
        assert 0.0 < quality < 0.5

    def test_negative_incidence_uses_abs(self):
        assert monotonic_quality(-20.0) == monotonic_quality(20.0)

class TestBandQuality:
    def test_optimal_band(self):
        # Test quality in optimal range
        ...

    def test_outside_band(self):
        # Test quality outside optimal range
        ...
```

### Phase 3: Integration Tests (4-8 hours)

#### 3.1 API Integration Tests

Create `tests/integration/test_api_integration.py`:

```python
"""Integration tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app

@pytest.fixture
def client():
    return TestClient(app)

class TestMissionAnalysis:
    def test_analyze_basic(self, client):
        response = client.post("/api/mission/analyze", json={
            "satellite": {...},
            "targets": [...],
            "start_time": "2025-01-01T00:00:00Z",
            "duration_hours": 24,
        })
        assert response.status_code == 200

    def test_analyze_invalid_tle(self, client):
        response = client.post("/api/mission/analyze", json={
            "satellite": {"tle_line1": "invalid"},
            ...
        })
        assert response.status_code == 422

class TestPlanning:
    def test_schedule_first_fit(self, client):
        ...

    def test_schedule_best_fit(self, client):
        ...
```

### Phase 4: Frontend Tests (2-4 hours)

#### 4.1 Component Tests

Add tests for remaining components:

```typescript
// src/components/MissionParameters/__tests__/MissionParameters.test.tsx
describe('MissionParameters', () => {
  it('renders form fields', () => {...})
  it('validates duration', () => {...})
  it('submits form data', () => {...})
})

// src/components/Map/__tests__/GlobeViewport.test.tsx
describe('GlobeViewport', () => {
  it('renders Cesium viewer', () => {...})
  it('handles 2D/3D mode switch', () => {...})
})
```

---

## Execution Commands

### Run All Working Tests

```bash
# Unit tests only (fast, always works)
make test-py

# Or manually
.venv/bin/pytest tests/unit/ -v

# Frontend
cd frontend && npm run test:run
```

### Run with Coverage

```bash
.venv/bin/pytest tests/unit/ --cov=src/mission_planner --cov-report=html
```

### Run Integration Tests (requires server)

```bash
# Start server first
make backend &

# Run integration tests
.venv/bin/pytest tests/integration/ -v -m "not requires_server"
```

---

## Estimated Effort

| Phase | Tasks | Time | Impact |
|-------|-------|------|--------|
| Phase 1 | Move scripts, add markers | 1-2h | Tests stop hanging |
| Phase 2 | Unit tests for core modules | 4-8h | Coverage 9% → 40% |
| Phase 3 | Integration tests with TestClient | 4-8h | Coverage 40% → 60% |
| Phase 4 | Frontend component tests | 2-4h | Full stack coverage |

**Total: 11-22 hours**

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Tests passing | 60 | 150+ |
| Coverage | 9% | 60% |
| Test runtime | 8s | <30s |
| Hanging tests | Many | 0 |

---

## Quick Win: Move Scripts Now

Run this to immediately fix the hanging issue:

```bash
cd /Users/panagiotis.d/CascadeProjects/mission-planning

# Create analysis folder
mkdir -p scripts/analysis

# Move scripts (files with 0 test functions)
mv tests/integration/test_45deg_analysis.py scripts/analysis/analysis_45deg.py
mv tests/integration/test_aggressive_maneuvers.py scripts/analysis/aggressive_maneuvers.py
mv tests/integration/test_all_algorithms.py scripts/analysis/all_algorithms.py
mv tests/integration/test_complex_scenario.py scripts/analysis/complex_scenario.py
mv tests/integration/test_edge_of_fov.py scripts/analysis/edge_of_fov.py
mv tests/integration/test_extreme_pitch.py scripts/analysis/extreme_pitch.py
mv tests/integration/test_extreme_slews.py scripts/analysis/extreme_slews.py
mv tests/integration/test_greece_mission.py scripts/analysis/greece_mission.py
mv tests/integration/test_greece_validation.py scripts/analysis/greece_validation.py
mv tests/integration/test_imaging_debug.py scripts/analysis/imaging_debug.py
mv tests/integration/test_pitch_tight_scenario.py scripts/analysis/pitch_tight_scenario.py
mv tests/integration/test_pointing_cone_debug.py scripts/analysis/pointing_cone_debug.py
mv tests/integration/test_realistic_scenario.py scripts/analysis/realistic_scenario.py
mv tests/integration/test_roll_vs_pitch_comparison.py scripts/analysis/roll_vs_pitch_comparison.py
mv tests/integration/test_scheduler_algorithms.py scripts/analysis/scheduler_algorithms.py
mv tests/integration/test_sequential_imaging.py scripts/analysis/sequential_imaging.py
mv tests/integration/test_tight_limits.py scripts/analysis/tight_limits.py
mv tests/integration/test_fov_impact_on_passes.py scripts/analysis/fov_impact_on_passes.py
mv tests/integration/test_full_pass_pitch.py scripts/analysis/full_pass_pitch.py
mv tests/integration/test_extended_mission_planning.py scripts/analysis/extended_mission_planning.py
mv tests/integration/test_production_endpoint.py scripts/analysis/production_endpoint.py

echo "✅ Scripts moved - tests should no longer hang"
```

After moving, tests will run without hanging.
