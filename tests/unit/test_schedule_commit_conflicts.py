"""
Regression tests for schedule commit conflict handling.

These tests exercise the API layer with an isolated SQLite database so we can
verify the full plan -> commit workflow without needing a live server.
"""

import hashlib
import os
import sys
import tempfile
import threading
import types
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator, Optional, Tuple

import pytest
from fastapi.testclient import TestClient


def _install_orbit_predictor_stub() -> None:
    """Provide a lightweight orbit_predictor stub for import-only test coverage.

    These API tests exercise schedule commit endpoints and do not rely on real
    orbit propagation. Importing backend.main pulls in mission_planner modules
    that import orbit_predictor, which fails in this local environment due to a
    numba/scipy binary mismatch. A minimal stub keeps the schedule stack
    importable without changing production code paths.
    """

    if "orbit_predictor" in sys.modules:
        return

    orbit_predictor = types.ModuleType("orbit_predictor")
    sources = types.ModuleType("orbit_predictor.sources")
    predictors = types.ModuleType("orbit_predictor.predictors")
    locations = types.ModuleType("orbit_predictor.locations")

    class _DummyPosition:
        position_llh = (0.0, 0.0, 500.0)
        altitude_km = 500.0

    class _DummyPredictor:
        period = 90.0

        def get_position(self, _timestamp):
            return _DummyPosition()

    class MemoryTLESource:
        pass

    class TLEPredictor(_DummyPredictor):
        pass

    class Location:
        def __init__(self, name: str = "stub", latitude_deg: float = 0.0, longitude_deg: float = 0.0, elevation_m: float = 0.0):
            self.name = name
            self.latitude_deg = latitude_deg
            self.longitude_deg = longitude_deg
            self.elevation_m = elevation_m

    def get_predictor_from_tle_lines(_tle_lines):
        return _DummyPredictor()

    sources.get_predictor_from_tle_lines = get_predictor_from_tle_lines
    sources.MemoryTLESource = MemoryTLESource
    predictors.TLEPredictor = TLEPredictor
    locations.Location = Location

    orbit_predictor.sources = sources
    orbit_predictor.predictors = predictors
    orbit_predictor.locations = locations

    sys.modules["orbit_predictor"] = orbit_predictor
    sys.modules["orbit_predictor.sources"] = sources
    sys.modules["orbit_predictor.predictors"] = predictors
    sys.modules["orbit_predictor.locations"] = locations


_install_orbit_predictor_stub()

from backend.main import (
    app,
    get_cached_opportunities,
    set_cached_opportunities,
    set_current_mission_data,
)
from backend.routers import schedule as schedule_router
from backend.schedule_persistence import (
    DEFAULT_WORKSPACE_ID,
    ScheduleDB,
    get_schedule_db,
    reset_schedule_db,
)
from backend.workspace_persistence import get_workspace_db, reset_workspace_db
from backend.schemas.target import TargetData


@pytest.fixture
def isolated_schedule_api() -> Generator[Tuple[TestClient, ScheduleDB, str], None, None]:
    """Run API tests against a temporary schedule/workspace database."""
    original_schedule_path = get_schedule_db().db_path
    original_workspace_path = get_workspace_db().db_path

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    reset_schedule_db(db_path)
    reset_workspace_db(db_path)

    db = get_schedule_db()
    workspace_id = get_workspace_db().create_workspace(
        name="Conflict Audit Workspace",
        mission_mode="OPTICAL",
    )

    with TestClient(app) as client:
        yield client, db, workspace_id

    reset_schedule_db(original_schedule_path)
    reset_workspace_db(original_workspace_path)
    if db_path.exists():
        os.unlink(db_path)


def _iso(dt: datetime) -> str:
    """Format a UTC datetime with a trailing Z."""
    return dt.isoformat().replace("+00:00", "Z")


def _state_iso(dt: datetime) -> str:
    """Format a UTC datetime for app-state fixtures that parse via fromisoformat."""
    return dt.isoformat()


def _create_plan(
    db: ScheduleDB,
    workspace_id: Optional[str],
    *,
    run_suffix: str,
    satellite_id: str,
    target_id: str,
    start_time: str,
    end_time: str,
) -> str:
    """Create a plan with a single plan item for commit testing."""
    plan = db.create_plan(
        algorithm="roll_pitch_best_fit",
        config={"planning_mode": "from_scratch"},
        input_hash=f"sha256:{hashlib.sha256(run_suffix.encode()).hexdigest()[:16]}",
        run_id=f"run_{run_suffix}",
        metrics={},
        workspace_id=workspace_id,
    )
    db.create_plan_item(
        plan_id=plan.id,
        opportunity_id=f"opp_{run_suffix}",
        satellite_id=satellite_id,
        target_id=target_id,
        start_time=start_time,
        end_time=end_time,
        roll_angle_deg=0.0,
        pitch_angle_deg=0.0,
        value=1.0,
        quality_score=1.0,
    )
    return plan.id


def _set_current_targets(target_names: list[str]) -> dict:
    """Build a minimal mission-data payload for backend mode-selection tests."""
    return {
        "mission_data": {
            "targets": [{"name": name} for name in target_names],
        }
    }


def _sample_tle_payload() -> dict:
    """Return a stable TLE payload for mission-analysis regression tests."""
    return {
        "name": "ICEYE-X53",
        "line1": "1 64584U 25135BJ  26064.28789825  .00007988  00000+0  63127-3 0  9993",
        "line2": "2 64584  97.7436 181.4786 0000928 206.1630 153.9547 15.00931401 38499",
    }


def _snapshot_analysis_state() -> dict:
    """Capture mutable app-state caches so tests can restore them safely."""
    return {
        "current_mission_data": getattr(app.state, "current_mission_data", {}),
        "current_mission_data_by_workspace": dict(
            getattr(app.state, "current_mission_data_by_workspace", {})
        ),
        "opportunities_cache": list(getattr(app.state, "opportunities_cache", [])),
        "opportunities_cache_by_workspace": dict(
            getattr(app.state, "opportunities_cache_by_workspace", {})
        ),
    }


def _restore_analysis_state(snapshot: dict) -> None:
    """Restore mutable app-state caches after a test."""
    app.state.current_mission_data = snapshot["current_mission_data"]
    app.state.current_mission_data_by_workspace = snapshot[
        "current_mission_data_by_workspace"
    ]
    app.state.opportunities_cache = snapshot["opportunities_cache"]
    app.state.opportunities_cache_by_workspace = snapshot[
        "opportunities_cache_by_workspace"
    ]


class TestScheduleCommitConflictDetection:
    """Regression coverage for far-horizon conflict detection."""

    def test_commit_without_workspace_uses_default_workspace_conflict_guard(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Implicit default-workspace commits should still detect overlaps."""
        client, db, _workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=16)
        base_end = base_start + timedelta(minutes=5)

        first_plan = _create_plan(
            db,
            DEFAULT_WORKSPACE_ID,
            run_suffix="default-first",
            satellite_id="SAT-1",
            target_id="D1",
            start_time=_iso(base_start),
            end_time=_iso(base_end),
        )
        first_commit = client.post(
            "/api/v1/schedule/commit",
            json={
                "plan_id": first_plan,
                "lock_level": "none",
            },
        )
        assert first_commit.status_code == 200, first_commit.json()

        default_state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": DEFAULT_WORKSPACE_ID},
        )
        assert default_state.status_code == 200, default_state.json()
        assert len(default_state.json()["state"]["acquisitions"]) == 1, default_state.json()

        second_plan = _create_plan(
            db,
            DEFAULT_WORKSPACE_ID,
            run_suffix="default-second",
            satellite_id="SAT-1",
            target_id="D2",
            start_time=_iso(base_start + timedelta(minutes=2)),
            end_time=_iso(base_start + timedelta(minutes=7)),
        )
        second_commit = client.post(
            "/api/v1/schedule/commit",
            json={
                "plan_id": second_plan,
                "lock_level": "none",
            },
        )

        assert second_commit.status_code == 409, second_commit.json()
        detail = second_commit.json()["detail"]
        assert detail["predicted_conflicts"], detail

    def test_commit_rejects_far_future_overlap(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """A far-future overlap should still be rejected during commit preview."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=10)
        base_end = base_start + timedelta(minutes=5)

        first_plan = _create_plan(
            db,
            workspace_id,
            run_suffix="first",
            satellite_id="SAT-1",
            target_id="T1",
            start_time=_iso(base_start),
            end_time=_iso(base_end),
        )
        first_commit = client.post(
            "/api/v1/schedule/commit",
            json={
                "plan_id": first_plan,
                "workspace_id": workspace_id,
                "lock_level": "none",
            },
        )
        assert first_commit.status_code == 200, first_commit.json()

        overlap_start = base_start + timedelta(minutes=2)
        overlap_end = overlap_start + timedelta(minutes=5)
        second_plan = _create_plan(
            db,
            workspace_id,
            run_suffix="second",
            satellite_id="SAT-1",
            target_id="T2",
            start_time=_iso(overlap_start),
            end_time=_iso(overlap_end),
        )
        second_commit = client.post(
            "/api/v1/schedule/commit",
            json={
                "plan_id": second_plan,
                "workspace_id": workspace_id,
                "lock_level": "none",
            },
        )

        assert second_commit.status_code == 409, second_commit.json()
        detail = second_commit.json()["detail"]
        predicted = detail["predicted_conflicts"]
        assert predicted, detail
        assert any(
            conflict["type"] == "temporal_overlap" for conflict in predicted
        ), predicted

    def test_force_commit_recomputes_far_future_conflicts(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Force-committed far-future overlaps should be persisted as conflicts."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=10)
        base_end = base_start + timedelta(minutes=5)

        first_plan = _create_plan(
            db,
            workspace_id,
            run_suffix="force-first",
            satellite_id="SAT-1",
            target_id="T1",
            start_time=_iso(base_start),
            end_time=_iso(base_end),
        )
        first_commit = client.post(
            "/api/v1/schedule/commit",
            json={
                "plan_id": first_plan,
                "workspace_id": workspace_id,
                "lock_level": "none",
            },
        )
        assert first_commit.status_code == 200, first_commit.json()

        overlap_start = base_start + timedelta(minutes=2)
        overlap_end = overlap_start + timedelta(minutes=5)
        second_plan = _create_plan(
            db,
            workspace_id,
            run_suffix="force-second",
            satellite_id="SAT-1",
            target_id="T2",
            start_time=_iso(overlap_start),
            end_time=_iso(overlap_end),
        )
        second_commit = client.post(
            "/api/v1/schedule/commit",
            json={
                "plan_id": second_plan,
                "workspace_id": workspace_id,
                "lock_level": "none",
                "force": True,
            },
        )

        assert second_commit.status_code == 200, second_commit.json()
        payload = second_commit.json()
        assert payload["conflicts_detected"] >= 1, payload
        assert len(payload["conflict_ids"]) == payload["conflicts_detected"], payload

    def test_force_commit_without_workspace_recomputes_default_workspace_conflicts(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Force commits in the implicit default workspace should persist conflicts."""
        client, db, _workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=17)
        base_end = base_start + timedelta(minutes=5)

        first_plan = _create_plan(
            db,
            DEFAULT_WORKSPACE_ID,
            run_suffix="default-force-first",
            satellite_id="SAT-1",
            target_id="DF-1",
            start_time=_iso(base_start),
            end_time=_iso(base_end),
        )
        first_commit = client.post(
            "/api/v1/schedule/commit",
            json={"plan_id": first_plan, "lock_level": "none"},
        )
        assert first_commit.status_code == 200, first_commit.json()

        second_plan = _create_plan(
            db,
            DEFAULT_WORKSPACE_ID,
            run_suffix="default-force-second",
            satellite_id="SAT-1",
            target_id="DF-2",
            start_time=_iso(base_start + timedelta(minutes=2)),
            end_time=_iso(base_start + timedelta(minutes=7)),
        )
        second_commit = client.post(
            "/api/v1/schedule/commit",
            json={
                "plan_id": second_plan,
                "lock_level": "none",
                "force": True,
            },
        )

        assert second_commit.status_code == 200, second_commit.json()
        payload = second_commit.json()
        assert payload["conflicts_detected"] >= 1, payload

        conflicts = client.get(
            "/api/v1/schedule/conflicts",
            params={"workspace_id": DEFAULT_WORKSPACE_ID},
        )
        assert conflicts.status_code == 200, conflicts.json()
        assert len(conflicts.json()["conflicts"]) >= 1, conflicts.json()

    def test_commit_ignores_unrelated_existing_conflicts(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Existing conflicts elsewhere in the workspace should not block a clean commit."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=10)

        # Seed an unrelated conflict on a different satellite inside the same broad window.
        db.create_acquisition(
            satellite_id="SAT-9",
            target_id="U1",
            start_time=_iso(base_start),
            end_time=_iso(base_start + timedelta(minutes=5)),
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
            state="committed",
        )
        db.create_acquisition(
            satellite_id="SAT-9",
            target_id="U2",
            start_time=_iso(base_start + timedelta(minutes=2)),
            end_time=_iso(base_start + timedelta(minutes=7)),
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
            state="committed",
        )

        clean_plan = _create_plan(
            db,
            workspace_id,
            run_suffix="unrelated-clean",
            satellite_id="SAT-1",
            target_id="T-clean",
            start_time=_iso(base_start + timedelta(minutes=20)),
            end_time=_iso(base_start + timedelta(minutes=25)),
        )
        clean_commit = client.post(
            "/api/v1/schedule/commit",
            json={
                "plan_id": clean_plan,
                "workspace_id": workspace_id,
                "lock_level": "none",
            },
        )

        assert clean_commit.status_code == 200, clean_commit.json()
        assert clean_commit.json()["committed"] == 1, clean_commit.json()

    def test_direct_commit_without_workspace_does_not_conflict_with_other_workspaces(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Implicit default direct commits should ignore unrelated workspace acquisitions."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=18)
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="OTHER-WS",
            start_time=_iso(base_start),
            end_time=_iso(base_start + timedelta(minutes=5)),
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
            state="committed",
        )

        direct_commit = client.post(
            "/api/v1/schedule/commit/direct",
            json={
                "algorithm": "regression_test",
                "lock_level": "none",
                "items": [
                    {
                        "opportunity_id": "default-direct-1",
                        "satellite_id": "SAT-1",
                        "target_id": "DEFAULT-WS",
                        "start_time": _iso(base_start),
                        "end_time": _iso(base_start + timedelta(minutes=5)),
                        "roll_angle_deg": 0.0,
                        "pitch_angle_deg": 0.0,
                    }
                ],
            },
        )
        assert direct_commit.status_code == 200, direct_commit.json()

        default_state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": DEFAULT_WORKSPACE_ID},
        )
        assert default_state.status_code == 200, default_state.json()
        assert len(default_state.json()["state"]["acquisitions"]) == 1, default_state.json()

    def test_direct_commit_rejects_identical_retry_after_success(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """A repeated direct-commit payload should be rejected as a duplicate retry."""
        client, _db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=19)
        request_body = {
            "workspace_id": workspace_id,
            "algorithm": "regression_test",
            "lock_level": "none",
            "items": [
                {
                    "opportunity_id": "retry-direct-1",
                    "satellite_id": "SAT-1",
                    "target_id": "RETRY-A",
                    "start_time": _iso(base_start),
                    "end_time": _iso(base_start + timedelta(minutes=5)),
                    "roll_angle_deg": 0.0,
                    "pitch_angle_deg": 0.0,
                },
                {
                    "opportunity_id": "retry-direct-2",
                    "satellite_id": "SAT-1",
                    "target_id": "RETRY-B",
                    "start_time": _iso(base_start + timedelta(minutes=10)),
                    "end_time": _iso(base_start + timedelta(minutes=15)),
                    "roll_angle_deg": 0.0,
                    "pitch_angle_deg": 0.0,
                },
            ],
        }

        first_commit = client.post("/api/v1/schedule/commit/direct", json=request_body)
        assert first_commit.status_code == 200, first_commit.json()
        assert first_commit.json()["committed"] == 2, first_commit.json()

        duplicate_preview = client.post(
            "/api/v1/schedule/commit/direct/preview",
            json={
                "workspace_id": workspace_id,
                "items": request_body["items"],
            },
        )
        assert duplicate_preview.status_code == 200, duplicate_preview.json()
        preview_payload = duplicate_preview.json()
        assert preview_payload["conflicts_count"] >= 1, preview_payload
        assert any(
            conflict["type"] == "duplicate_commit"
            for conflict in preview_payload["conflicts"]
        ), preview_payload

        second_commit = client.post("/api/v1/schedule/commit/direct", json=request_body)
        assert second_commit.status_code == 409, second_commit.json()
        detail = second_commit.json()["detail"]
        assert "Duplicate commit detected" in detail["message"], detail

        state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id},
        )
        assert state.status_code == 200, state.json()
        assert len(state.json()["state"]["acquisitions"]) == 2, state.json()

    def test_direct_commit_retry_recovers_after_internal_commit_failure(
        self,
        isolated_schedule_api: Tuple[TestClient, ScheduleDB, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failed commit attempt must not poison a later identical retry."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=19)
        request_body = {
            "workspace_id": workspace_id,
            "algorithm": "regression_test",
            "lock_level": "none",
            "items": [
                {
                    "opportunity_id": "retry-after-failure-1",
                    "satellite_id": "SAT-1",
                    "target_id": "RECOVER-A",
                    "start_time": _iso(base_start),
                    "end_time": _iso(base_start + timedelta(minutes=5)),
                    "roll_angle_deg": 0.0,
                    "pitch_angle_deg": 0.0,
                }
            ],
        }

        original_commit_plan = db.commit_plan_atomic
        commit_attempts = 0

        def flaky_commit_plan(*args, **kwargs):
            nonlocal commit_attempts
            commit_attempts += 1
            if commit_attempts == 1:
                raise RuntimeError("simulated commit_plan_atomic failure")
            return original_commit_plan(*args, **kwargs)

        monkeypatch.setattr(db, "commit_plan_atomic", flaky_commit_plan)

        first_commit = client.post("/api/v1/schedule/commit/direct", json=request_body)
        assert first_commit.status_code == 500, first_commit.json()
        assert "simulated commit_plan_atomic failure" in first_commit.json()["detail"]

        state_after_failure = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id},
        )
        assert state_after_failure.status_code == 200, state_after_failure.json()
        assert (
            len(state_after_failure.json()["state"]["acquisitions"]) == 0
        ), state_after_failure.json()

        second_commit = client.post("/api/v1/schedule/commit/direct", json=request_body)
        assert second_commit.status_code == 200, second_commit.json()
        assert second_commit.json()["committed"] == 1, second_commit.json()
        assert second_commit.json()["audit_log_id"], second_commit.json()
        assert commit_attempts == 2

        third_commit = client.post("/api/v1/schedule/commit/direct", json=request_body)
        assert third_commit.status_code == 409, third_commit.json()
        detail = third_commit.json()["detail"]
        assert "Duplicate commit detected" in detail["message"], detail

        final_state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id},
        )
        assert final_state.status_code == 200, final_state.json()
        acquisitions = final_state.json()["state"]["acquisitions"]
        assert len(acquisitions) == 1, final_state.json()
        assert acquisitions[0]["target_id"] == "RECOVER-A", final_state.json()

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status FROM plans WHERE workspace_id = ? ORDER BY created_at ASC",
                (workspace_id,),
            )
            statuses = [row["status"] for row in cursor.fetchall()]

        assert statuses == ["candidate", "committed"], statuses

    def test_direct_commit_writes_commit_history_audit_log(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Successful direct commits should create a traceable audit log entry."""
        client, _db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=19)
        direct_commit = client.post(
            "/api/v1/schedule/commit/direct",
            json={
                "workspace_id": workspace_id,
                "algorithm": "audit_regression",
                "lock_level": "none",
                "notes": "operator promoted approved schedule",
                "items": [
                    {
                        "opportunity_id": "audit-direct-1",
                        "satellite_id": "SAT-1",
                        "target_id": "AUDIT-A",
                        "start_time": _iso(base_start),
                        "end_time": _iso(base_start + timedelta(minutes=5)),
                        "roll_angle_deg": 0.0,
                        "pitch_angle_deg": 0.0,
                    }
                ],
            },
        )
        assert direct_commit.status_code == 200, direct_commit.json()
        payload = direct_commit.json()
        assert payload["audit_log_id"], payload

        history = client.get(
            "/api/v1/schedule/commit-history",
            params={"workspace_id": workspace_id},
        )
        assert history.status_code == 200, history.json()
        body = history.json()
        assert body["total"] == 1, body
        audit_log = body["audit_logs"][0]
        assert audit_log["id"] == payload["audit_log_id"], body
        assert audit_log["plan_id"] == payload["plan_id"], body
        assert audit_log["commit_type"] == "normal", body
        assert audit_log["acquisitions_created"] == 1, body
        assert audit_log["acquisitions_dropped"] == 0, body
        assert audit_log["conflicts_before"] == 0, body
        assert audit_log["conflicts_after"] == 0, body
        assert audit_log["notes"] == "operator promoted approved schedule", body

    def test_direct_commit_rejects_zero_created_duplicate_race_result(
        self,
        isolated_schedule_api: Tuple[TestClient, ScheduleDB, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A duplicate race that creates zero acquisitions must fail closed."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=19)
        request_body = {
            "workspace_id": workspace_id,
            "algorithm": "regression_test",
            "lock_level": "none",
            "items": [
                {
                    "opportunity_id": "duplicate-race-1",
                    "satellite_id": "SAT-1",
                    "target_id": "RACE-A",
                    "start_time": _iso(base_start),
                    "end_time": _iso(base_start + timedelta(minutes=5)),
                    "roll_angle_deg": 0.0,
                    "pitch_angle_deg": 0.0,
                }
            ],
        }

        first_commit = client.post("/api/v1/schedule/commit/direct", json=request_body)
        assert first_commit.status_code == 200, first_commit.json()
        first_plan_id = first_commit.json()["plan_id"]

        original_find_duplicate = schedule_router._find_existing_direct_commit_plan
        duplicate_lookup_calls = 0

        def bypass_first_duplicate_lookup(*args, **kwargs):
            nonlocal duplicate_lookup_calls
            duplicate_lookup_calls += 1
            if duplicate_lookup_calls == 1:
                return None
            return original_find_duplicate(*args, **kwargs)

        monkeypatch.setattr(
            schedule_router,
            "_find_existing_direct_commit_plan",
            bypass_first_duplicate_lookup,
        )
        monkeypatch.setattr(
            schedule_router,
            "_predict_direct_commit_conflicts",
            lambda *_args, **_kwargs: [],
        )

        second_commit = client.post("/api/v1/schedule/commit/direct", json=request_body)
        assert second_commit.status_code == 409, second_commit.json()
        detail = second_commit.json()["detail"]
        assert "Duplicate commit detected" in detail["message"], detail
        assert detail["duplicate_plan_id"] == first_plan_id, detail

        state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id},
        )
        assert state.status_code == 200, state.json()
        acquisitions = state.json()["state"]["acquisitions"]
        assert len(acquisitions) == 1, state.json()
        assert acquisitions[0]["target_id"] == "RACE-A", state.json()

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, status FROM plans WHERE workspace_id = ? ORDER BY created_at ASC",
                (workspace_id,),
            )
            plans = [(row["id"], row["status"]) for row in cursor.fetchall()]

        assert plans[0] == (first_plan_id, "committed"), plans
        assert plans[1][1] == "superseded", plans

    def test_parallel_identical_direct_commits_allow_only_one_winner(
        self,
        isolated_schedule_api: Tuple[TestClient, ScheduleDB, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Two identical in-flight direct commits must resolve to one success and one duplicate."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=19)
        request_body = {
            "workspace_id": workspace_id,
            "algorithm": "regression_test",
            "lock_level": "none",
            "items": [
                {
                    "opportunity_id": "parallel-duplicate-1",
                    "satellite_id": "SAT-1",
                    "target_id": "PARALLEL-A",
                    "start_time": _iso(base_start),
                    "end_time": _iso(base_start + timedelta(minutes=5)),
                    "roll_angle_deg": 0.0,
                    "pitch_angle_deg": 0.0,
                }
            ],
        }

        original_find_duplicate = schedule_router._find_existing_direct_commit_plan
        duplicate_lookup_calls = 0
        duplicate_lookup_lock = threading.Lock()
        precheck_barrier = threading.Barrier(2)

        def synchronize_duplicate_precheck(db_arg, input_hash):
            nonlocal duplicate_lookup_calls
            with duplicate_lookup_lock:
                duplicate_lookup_calls += 1
                current_call = duplicate_lookup_calls
            if current_call <= 2:
                precheck_barrier.wait(timeout=5)
                return None
            return original_find_duplicate(db_arg, input_hash)

        monkeypatch.setattr(
            schedule_router,
            "_find_existing_direct_commit_plan",
            synchronize_duplicate_precheck,
        )
        monkeypatch.setattr(
            schedule_router,
            "_predict_direct_commit_conflicts",
            lambda *_args, **_kwargs: [],
        )

        with TestClient(app) as client_a, TestClient(app) as client_b:
            def submit_commit(thread_client: TestClient):
                return thread_client.post("/api/v1/schedule/commit/direct", json=request_body)

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(submit_commit, client_a),
                    executor.submit(submit_commit, client_b),
                ]
                responses = [future.result() for future in futures]

        statuses = sorted(response.status_code for response in responses)
        assert statuses == [200, 409], [response.json() for response in responses]

        success_payload = next(
            response.json() for response in responses if response.status_code == 200
        )
        conflict_payload = next(
            response.json()["detail"] for response in responses if response.status_code == 409
        )

        assert "Duplicate commit detected" in conflict_payload["message"], conflict_payload
        assert conflict_payload["duplicate_plan_id"] == success_payload["plan_id"], (
            success_payload,
            conflict_payload,
        )

        state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id},
        )
        assert state.status_code == 200, state.json()
        acquisitions = state.json()["state"]["acquisitions"]
        assert len(acquisitions) == 1, state.json()
        assert acquisitions[0]["target_id"] == "PARALLEL-A", state.json()

    def test_parallel_duplicate_burst_allows_only_one_committed_result(
        self,
        isolated_schedule_api: Tuple[TestClient, ScheduleDB, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A burst of identical direct commits must collapse to one success."""
        client, _db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=19)
        request_body = {
            "workspace_id": workspace_id,
            "algorithm": "regression_test",
            "lock_level": "none",
            "items": [
                {
                    "opportunity_id": "parallel-burst-1",
                    "satellite_id": "SAT-1",
                    "target_id": "BURST-A",
                    "start_time": _iso(base_start),
                    "end_time": _iso(base_start + timedelta(minutes=5)),
                    "roll_angle_deg": 0.0,
                    "pitch_angle_deg": 0.0,
                }
            ],
        }

        burst_size = 5
        original_find_duplicate = schedule_router._find_existing_direct_commit_plan
        duplicate_lookup_calls = 0
        duplicate_lookup_lock = threading.Lock()
        precheck_barrier = threading.Barrier(burst_size)

        def synchronize_duplicate_precheck(db_arg, input_hash):
            nonlocal duplicate_lookup_calls
            with duplicate_lookup_lock:
                duplicate_lookup_calls += 1
                current_call = duplicate_lookup_calls
            if current_call <= burst_size:
                precheck_barrier.wait(timeout=5)
                return None
            return original_find_duplicate(db_arg, input_hash)

        monkeypatch.setattr(
            schedule_router,
            "_find_existing_direct_commit_plan",
            synchronize_duplicate_precheck,
        )
        monkeypatch.setattr(
            schedule_router,
            "_predict_direct_commit_conflicts",
            lambda *_args, **_kwargs: [],
        )

        with ExitStack() as stack:
            clients = [stack.enter_context(TestClient(app)) for _ in range(burst_size)]

            def submit_commit(thread_client: TestClient):
                return thread_client.post("/api/v1/schedule/commit/direct", json=request_body)

            with ThreadPoolExecutor(max_workers=burst_size) as executor:
                responses = list(executor.map(submit_commit, clients))

        status_counts = {
            200: sum(1 for response in responses if response.status_code == 200),
            409: sum(1 for response in responses if response.status_code == 409),
        }
        assert status_counts == {200: 1, 409: burst_size - 1}, [
            response.json() for response in responses
        ]

        success_payload = next(
            response.json() for response in responses if response.status_code == 200
        )
        for response in responses:
            if response.status_code != 409:
                continue
            detail = response.json()["detail"]
            assert "Duplicate commit detected" in detail["message"], detail
            assert detail["duplicate_plan_id"] == success_payload["plan_id"], detail

        state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id},
        )
        assert state.status_code == 200, state.json()
        acquisitions = state.json()["state"]["acquisitions"]
        assert len(acquisitions) == 1, state.json()
        assert acquisitions[0]["target_id"] == "BURST-A", state.json()

    def test_parallel_overlapping_direct_commits_allow_only_one_winner(
        self,
        isolated_schedule_api: Tuple[TestClient, ScheduleDB, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Concurrent overlapping direct commits must not both persist."""
        client, _db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=19)
        request_a = {
            "workspace_id": workspace_id,
            "algorithm": "operator_a",
            "lock_level": "none",
            "items": [
                {
                    "opportunity_id": "parallel-overlap-a",
                    "satellite_id": "SAT-1",
                    "target_id": "OVERLAP-A",
                    "start_time": _iso(base_start),
                    "end_time": _iso(base_start + timedelta(minutes=5)),
                    "roll_angle_deg": 0.0,
                    "pitch_angle_deg": 0.0,
                }
            ],
        }
        request_b = {
            "workspace_id": workspace_id,
            "algorithm": "operator_b",
            "lock_level": "none",
            "items": [
                {
                    "opportunity_id": "parallel-overlap-b",
                    "satellite_id": "SAT-1",
                    "target_id": "OVERLAP-B",
                    "start_time": _iso(base_start + timedelta(minutes=2)),
                    "end_time": _iso(base_start + timedelta(minutes=7)),
                    "roll_angle_deg": 0.0,
                    "pitch_angle_deg": 0.0,
                }
            ],
        }

        precheck_barrier = threading.Barrier(2)

        original_predict = schedule_router._predict_direct_commit_conflicts

        def synchronized_predict(db_arg, items, workspace_id_arg):
            precheck_barrier.wait(timeout=5)
            return original_predict(db_arg, items, workspace_id_arg)

        monkeypatch.setattr(
            schedule_router,
            "_predict_direct_commit_conflicts",
            synchronized_predict,
        )

        with ExitStack() as stack:
            client_a = stack.enter_context(TestClient(app))
            client_b = stack.enter_context(TestClient(app))

            with ThreadPoolExecutor(max_workers=2) as executor:
                future_a = executor.submit(
                    client_a.post, "/api/v1/schedule/commit/direct", json=request_a
                )
                future_b = executor.submit(
                    client_b.post, "/api/v1/schedule/commit/direct", json=request_b
                )
                response_a = future_a.result()
                response_b = future_b.result()

        statuses = sorted([response_a.status_code, response_b.status_code])
        assert statuses == [200, 409], [response_a.json(), response_b.json()]

        state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id},
        )
        assert state.status_code == 200, state.json()
        acquisitions = state.json()["state"]["acquisitions"]
        assert len(acquisitions) == 1, state.json()

    def test_parallel_mixed_overlap_burst_keeps_only_non_conflicting_winners(
        self,
        isolated_schedule_api: Tuple[TestClient, ScheduleDB, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Concurrent mixed bursts should serialize to one clean winner per workspace revision."""
        client, _db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=19)
        request_bodies = [
            {
                "workspace_id": workspace_id,
                "algorithm": "burst_cluster_a_1",
                "lock_level": "none",
                "items": [
                    {
                        "opportunity_id": "mixed-overlap-a1",
                        "satellite_id": "SAT-1",
                        "target_id": "MIX-A1",
                        "start_time": _iso(base_start),
                        "end_time": _iso(base_start + timedelta(minutes=5)),
                        "roll_angle_deg": 0.0,
                        "pitch_angle_deg": 0.0,
                    }
                ],
            },
            {
                "workspace_id": workspace_id,
                "algorithm": "burst_cluster_a_2",
                "lock_level": "none",
                "items": [
                    {
                        "opportunity_id": "mixed-overlap-a2",
                        "satellite_id": "SAT-1",
                        "target_id": "MIX-A2",
                        "start_time": _iso(base_start + timedelta(minutes=2)),
                        "end_time": _iso(base_start + timedelta(minutes=7)),
                        "roll_angle_deg": 0.0,
                        "pitch_angle_deg": 0.0,
                    }
                ],
            },
            {
                "workspace_id": workspace_id,
                "algorithm": "burst_cluster_b_1",
                "lock_level": "none",
                "items": [
                    {
                        "opportunity_id": "mixed-overlap-b1",
                        "satellite_id": "SAT-1",
                        "target_id": "MIX-B1",
                        "start_time": _iso(base_start + timedelta(minutes=10)),
                        "end_time": _iso(base_start + timedelta(minutes=15)),
                        "roll_angle_deg": 0.0,
                        "pitch_angle_deg": 0.0,
                    }
                ],
            },
            {
                "workspace_id": workspace_id,
                "algorithm": "burst_cluster_b_2",
                "lock_level": "none",
                "items": [
                    {
                        "opportunity_id": "mixed-overlap-b2",
                        "satellite_id": "SAT-1",
                        "target_id": "MIX-B2",
                        "start_time": _iso(base_start + timedelta(minutes=12)),
                        "end_time": _iso(base_start + timedelta(minutes=17)),
                        "roll_angle_deg": 0.0,
                        "pitch_angle_deg": 0.0,
                    }
                ],
            },
        ]

        burst_size = len(request_bodies)
        original_predict = schedule_router._predict_direct_commit_conflicts
        precheck_calls = 0
        precheck_lock = threading.Lock()
        precheck_barrier = threading.Barrier(burst_size)

        def synchronized_predict(db_arg, items, workspace_id_arg):
            nonlocal precheck_calls
            with precheck_lock:
                precheck_calls += 1
                current_call = precheck_calls
            if current_call <= burst_size:
                precheck_barrier.wait(timeout=5)
            return original_predict(db_arg, items, workspace_id_arg)

        monkeypatch.setattr(
            schedule_router,
            "_predict_direct_commit_conflicts",
            synchronized_predict,
        )

        with ExitStack() as stack:
            clients = [stack.enter_context(TestClient(app)) for _ in range(burst_size)]

            def submit_commit(args):
                thread_client, request_body = args
                return thread_client.post(
                    "/api/v1/schedule/commit/direct", json=request_body
                )

            with ThreadPoolExecutor(max_workers=burst_size) as executor:
                responses = list(executor.map(submit_commit, zip(clients, request_bodies)))

        status_counts = {
            200: sum(1 for response in responses if response.status_code == 200),
            409: sum(1 for response in responses if response.status_code == 409),
        }
        assert status_counts == {200: 1, 409: 3}, [response.json() for response in responses]

        state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id},
        )
        assert state.status_code == 200, state.json()
        acquisitions = state.json()["state"]["acquisitions"]
        assert len(acquisitions) == 1, state.json()
        assert acquisitions[0]["target_id"] in {"MIX-A1", "MIX-A2", "MIX-B1", "MIX-B2"}, (
            state.json()
        )

        conflicts = client.get(
            "/api/v1/schedule/conflicts",
            params={"workspace_id": workspace_id},
        )
        assert conflicts.status_code == 200, conflicts.json()
        assert len(conflicts.json()["conflicts"]) == 0, conflicts.json()

        history = client.get(
            "/api/v1/schedule/commit-history",
            params={"workspace_id": workspace_id},
        )
        assert history.status_code == 200, history.json()
        audit_logs = history.json()["audit_logs"]
        assert history.json()["total"] == 1, history.json()
        assert all(log["acquisitions_created"] == 1 for log in audit_logs), history.json()
        assert all(log["commit_type"] == "normal" for log in audit_logs), history.json()

    def test_direct_commit_materializes_missing_workspace_scope(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Direct commit should not 500 when the client sends a new workspace ID."""
        client, _db, _workspace_id = isolated_schedule_api
        requested_workspace_id = "workspace_ephemeral_e2e"

        base_start = datetime.now(timezone.utc) + timedelta(days=19)
        direct_commit = client.post(
            "/api/v1/schedule/commit/direct",
            json={
                "algorithm": "regression_test",
                "workspace_id": requested_workspace_id,
                "lock_level": "none",
                "items": [
                    {
                        "opportunity_id": "unknown-ws-direct-1",
                        "satellite_id": "SAT-1",
                        "target_id": "UNKNOWN-WS",
                        "start_time": _iso(base_start),
                        "end_time": _iso(base_start + timedelta(minutes=5)),
                        "roll_angle_deg": 0.0,
                        "pitch_angle_deg": 0.0,
                    }
                ],
            },
        )

        assert direct_commit.status_code == 200, direct_commit.json()

        state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": requested_workspace_id},
        )
        assert state.status_code == 200, state.json()
        assert len(state.json()["state"]["acquisitions"]) == 1, state.json()

        placeholder_workspace = get_workspace_db().get_workspace(
            requested_workspace_id, include_czml=False
        )
        assert placeholder_workspace is not None
        assert placeholder_workspace.id == requested_workspace_id

    def test_direct_commit_preview_reports_conflicts_before_apply(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Preview should expose enriched conflict metadata for the exact commit payload."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=20)
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="EXISTING",
            start_time=_iso(base_start),
            end_time=_iso(base_start + timedelta(minutes=5)),
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
            state="committed",
        )

        preview = client.post(
            "/api/v1/schedule/commit/direct/preview",
            json={
                "workspace_id": workspace_id,
                "items": [
                    {
                        "opportunity_id": "preview-overlap-1",
                        "satellite_id": "SAT-1",
                        "target_id": "NEW-TARGET",
                        "start_time": _iso(base_start + timedelta(minutes=2)),
                        "end_time": _iso(base_start + timedelta(minutes=7)),
                        "roll_angle_deg": 0.0,
                        "pitch_angle_deg": 0.0,
                    }
                ],
            },
        )

        assert preview.status_code == 200, preview.json()
        payload = preview.json()
        assert payload["conflicts_count"] >= 1, payload
        overlap = next(
            (
                conflict
                for conflict in payload["conflicts"]
                if conflict["type"] == "temporal_overlap"
            ),
            None,
        )
        assert overlap is not None, payload
        assert overlap["details"]["satellite_id"] == "SAT-1"
        assert overlap["details"]["acq1_target"] == "EXISTING"
        assert overlap["details"]["acq2_target"] == "NEW-TARGET"

    def test_force_direct_commit_recomputes_and_persists_conflicts(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Forced direct commits should still refresh persisted conflict state for the UI."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=21)
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="EXISTING",
            start_time=_iso(base_start),
            end_time=_iso(base_start + timedelta(minutes=5)),
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
            state="committed",
        )

        direct_commit = client.post(
            "/api/v1/schedule/commit/direct",
            json={
                "workspace_id": workspace_id,
                "algorithm": "regression_test",
                "lock_level": "none",
                "force": True,
                "items": [
                    {
                        "opportunity_id": "forced-overlap-1",
                        "satellite_id": "SAT-1",
                        "target_id": "NEW-TARGET",
                        "start_time": _iso(base_start + timedelta(minutes=2)),
                        "end_time": _iso(base_start + timedelta(minutes=7)),
                        "roll_angle_deg": 0.0,
                        "pitch_angle_deg": 0.0,
                    }
                ],
            },
        )
        assert direct_commit.status_code == 200, direct_commit.json()
        payload = direct_commit.json()
        assert payload["conflicts_detected"] >= 1, payload
        assert payload["conflict_ids"], payload

        conflicts = client.get(
            "/api/v1/schedule/conflicts",
            params={"workspace_id": workspace_id},
        )
        assert conflicts.status_code == 200, conflicts.json()
        assert len(conflicts.json()["conflicts"]) >= 1, conflicts.json()

    def test_direct_commit_rechecks_conflicts_after_preview_when_state_changes(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Commit must fail closed if schedule state changes after a clean preview."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=22)
        candidate_item = {
            "opportunity_id": "stale-preview-1",
            "satellite_id": "SAT-1",
            "target_id": "RACE-TARGET",
            "start_time": _iso(base_start),
            "end_time": _iso(base_start + timedelta(minutes=5)),
            "roll_angle_deg": 0.0,
            "pitch_angle_deg": 0.0,
        }

        preview = client.post(
            "/api/v1/schedule/commit/direct/preview",
            json={
                "workspace_id": workspace_id,
                "items": [candidate_item],
            },
        )
        assert preview.status_code == 200, preview.json()
        assert preview.json()["conflicts_count"] == 0, preview.json()

        # Simulate another operator or process committing a conflicting acquisition
        # after preview but before the original operator applies.
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="OTHER-OPERATOR",
            start_time=_iso(base_start + timedelta(minutes=1)),
            end_time=_iso(base_start + timedelta(minutes=6)),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )

        direct_commit = client.post(
            "/api/v1/schedule/commit/direct",
            json={
                "workspace_id": workspace_id,
                "algorithm": "regression_test",
                "lock_level": "none",
                "items": [candidate_item],
            },
        )

        assert direct_commit.status_code == 409, direct_commit.json()
        detail = direct_commit.json()["detail"]
        assert "predicted_conflicts" in detail, detail
        assert detail["predicted_conflicts"], detail
        assert detail["predicted_conflicts"][0]["type"] == "temporal_overlap", detail

    def test_second_operator_commit_is_blocked_after_first_operator_applies_overlap(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Two clean previews must not allow overlapping commits in the same workspace."""
        client, _db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=23)
        operator_a_item = {
            "opportunity_id": "operator-a-1",
            "satellite_id": "SAT-1",
            "target_id": "A-TARGET",
            "start_time": _iso(base_start),
            "end_time": _iso(base_start + timedelta(minutes=5)),
            "roll_angle_deg": 0.0,
            "pitch_angle_deg": 0.0,
        }
        operator_b_item = {
            "opportunity_id": "operator-b-1",
            "satellite_id": "SAT-1",
            "target_id": "B-TARGET",
            "start_time": _iso(base_start + timedelta(minutes=2)),
            "end_time": _iso(base_start + timedelta(minutes=7)),
            "roll_angle_deg": 0.0,
            "pitch_angle_deg": 0.0,
        }

        preview_a = client.post(
            "/api/v1/schedule/commit/direct/preview",
            json={"workspace_id": workspace_id, "items": [operator_a_item]},
        )
        assert preview_a.status_code == 200, preview_a.json()
        assert preview_a.json()["conflicts_count"] == 0, preview_a.json()

        preview_b = client.post(
            "/api/v1/schedule/commit/direct/preview",
            json={"workspace_id": workspace_id, "items": [operator_b_item]},
        )
        assert preview_b.status_code == 200, preview_b.json()
        assert preview_b.json()["conflicts_count"] == 0, preview_b.json()

        commit_a = client.post(
            "/api/v1/schedule/commit/direct",
            json={
                "workspace_id": workspace_id,
                "algorithm": "operator_a",
                "lock_level": "none",
                "items": [operator_a_item],
            },
        )
        assert commit_a.status_code == 200, commit_a.json()
        assert commit_a.json()["committed"] == 1, commit_a.json()

        commit_b = client.post(
            "/api/v1/schedule/commit/direct",
            json={
                "workspace_id": workspace_id,
                "algorithm": "operator_b",
                "lock_level": "none",
                "items": [operator_b_item],
            },
        )
        assert commit_b.status_code == 409, commit_b.json()
        detail = commit_b.json()["detail"]
        assert detail["predicted_conflicts"], detail
        assert any(
            conflict["type"] == "temporal_overlap"
            for conflict in detail["predicted_conflicts"]
        ), detail

        state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id},
        )
        assert state.status_code == 200, state.json()
        acquisitions = state.json()["state"]["acquisitions"]
        assert len(acquisitions) == 1, state.json()
        assert acquisitions[0]["target_id"] == "A-TARGET", state.json()

    def test_second_operator_force_commit_persists_conflicts_after_overlap_race(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """A forced second operator commit should persist the overlap conflict for review."""
        client, _db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=24)
        operator_a_item = {
            "opportunity_id": "operator-a-force-1",
            "satellite_id": "SAT-1",
            "target_id": "A-FORCE",
            "start_time": _iso(base_start),
            "end_time": _iso(base_start + timedelta(minutes=5)),
            "roll_angle_deg": 0.0,
            "pitch_angle_deg": 0.0,
        }
        operator_b_item = {
            "opportunity_id": "operator-b-force-1",
            "satellite_id": "SAT-1",
            "target_id": "B-FORCE",
            "start_time": _iso(base_start + timedelta(minutes=2)),
            "end_time": _iso(base_start + timedelta(minutes=7)),
            "roll_angle_deg": 0.0,
            "pitch_angle_deg": 0.0,
        }

        commit_a = client.post(
            "/api/v1/schedule/commit/direct",
            json={
                "workspace_id": workspace_id,
                "algorithm": "operator_a_force",
                "lock_level": "none",
                "items": [operator_a_item],
            },
        )
        assert commit_a.status_code == 200, commit_a.json()

        commit_b = client.post(
            "/api/v1/schedule/commit/direct",
            json={
                "workspace_id": workspace_id,
                "algorithm": "operator_b_force",
                "lock_level": "none",
                "force": True,
                "items": [operator_b_item],
            },
        )
        assert commit_b.status_code == 200, commit_b.json()
        payload = commit_b.json()
        assert payload["conflicts_detected"] >= 1, payload
        assert payload["conflict_ids"], payload

        conflicts = client.get(
            "/api/v1/schedule/conflicts",
            params={"workspace_id": workspace_id},
        )
        assert conflicts.status_code == 200, conflicts.json()
        conflict_payload = conflicts.json()
        assert len(conflict_payload["conflicts"]) >= 1, conflict_payload
        assert any(
            conflict["type"] == "temporal_overlap"
            for conflict in conflict_payload["conflicts"]
        ), conflict_payload

    def test_schedule_plan_accepts_future_aware_opportunities(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Planning preview should handle future aware timestamps without crashing."""
        client, _, workspace_id = isolated_schedule_api

        future_start = datetime.now(timezone.utc) + timedelta(days=14)
        original_state = _snapshot_analysis_state()
        set_current_mission_data(
            {
            "passes": [
                {
                    "satellite_name": "SAT-FUTURE",
                    "target_name": "FutureTarget",
                    "max_elevation_time": future_start.isoformat(),
                    "start_time": future_start.isoformat(),
                }
            ],
            "mission_data": {
                "targets": [{"name": "FutureTarget"}],
                "satellite_agility": 1.0,
            },
            },
            workspace_id,
        )

        try:
            plan = client.post(
                "/api/v1/schedule/plan",
                json={
                    "planning_mode": "from_scratch",
                    "workspace_id": workspace_id,
                },
            )
        finally:
            _restore_analysis_state(original_state)

        assert plan.status_code == 200, plan.text
        payload = plan.json()
        assert payload["success"], payload
        assert payload["new_plan_items"], payload
        assert "conflicts_if_committed" in payload, payload

    def test_repair_commit_recomputes_far_future_conflicts(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Repair commit should recompute conflicts across the full workspace horizon."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=12)
        base_end = base_start + timedelta(minutes=5)

        existing_plan = _create_plan(
            db,
            workspace_id,
            run_suffix="repair-base",
            satellite_id="SAT-1",
            target_id="T1",
            start_time=_iso(base_start),
            end_time=_iso(base_end),
        )
        existing_commit = client.post(
            "/api/v1/schedule/commit",
            json={
                "plan_id": existing_plan,
                "workspace_id": workspace_id,
                "lock_level": "none",
            },
        )
        assert existing_commit.status_code == 200, existing_commit.json()

        overlap_start = base_start + timedelta(minutes=2)
        overlap_end = overlap_start + timedelta(minutes=5)
        repair_plan = _create_plan(
            db,
            workspace_id,
            run_suffix="repair-overlap",
            satellite_id="SAT-1",
            target_id="T2",
            start_time=_iso(overlap_start),
            end_time=_iso(overlap_end),
        )
        repair_commit = client.post(
            "/api/v1/schedule/repair/commit",
            json={
                "plan_id": repair_plan,
                "workspace_id": workspace_id,
                "lock_level": "none",
                "mode": "OPTICAL",
            },
        )

        assert repair_commit.status_code == 400, repair_commit.json()
        assert "Concurrent schedule conflict detected" in repair_commit.json()["detail"]

        forced_repair_commit = client.post(
            "/api/v1/schedule/repair/commit",
            json={
                "plan_id": repair_plan,
                "workspace_id": workspace_id,
                "lock_level": "none",
                "mode": "OPTICAL",
                "force": True,
            },
        )

        assert forced_repair_commit.status_code == 200, forced_repair_commit.json()
        payload = forced_repair_commit.json()
        assert payload["conflicts_after"] >= 1, payload

    def test_recompute_conflicts_defaults_to_workspace_horizon(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Conflict recompute without explicit bounds should still cover far-future items."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=30)
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="HF-1",
            start_time=_iso(base_start),
            end_time=_iso(base_start + timedelta(minutes=10)),
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
            state="committed",
        )
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="HF-2",
            start_time=_iso(base_start + timedelta(minutes=5)),
            end_time=_iso(base_start + timedelta(minutes=12)),
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
            state="committed",
        )

        recompute = client.post(
            "/api/v1/schedule/conflicts/recompute",
            json={"workspace_id": workspace_id},
        )

        assert recompute.status_code == 200, recompute.json()
        payload = recompute.json()
        assert payload["detected"] >= 1, payload
        assert payload["persisted"] >= 1, payload

    def test_conflict_list_includes_enriched_details(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Conflict list readback should expose target/time details for inspection."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=25)
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="DET-1",
            start_time=_iso(base_start),
            end_time=_iso(base_start + timedelta(minutes=10)),
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
            state="committed",
        )
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="DET-2",
            start_time=_iso(base_start + timedelta(minutes=4)),
            end_time=_iso(base_start + timedelta(minutes=12)),
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
            state="committed",
        )

        recompute = client.post(
            "/api/v1/schedule/conflicts/recompute",
            json={"workspace_id": workspace_id},
        )
        assert recompute.status_code == 200, recompute.json()

        conflicts = client.get(
            "/api/v1/schedule/conflicts",
            params={"workspace_id": workspace_id},
        )
        assert conflicts.status_code == 200, conflicts.json()
        temporal = [
            conflict
            for conflict in conflicts.json()["conflicts"]
            if conflict["type"] == "temporal_overlap"
        ]
        assert temporal, conflicts.json()
        details = temporal[0]["details"]
        assert details["acq1_target"] == "DET-1"
        assert details["acq2_target"] == "DET-2"
        assert details["satellite_id"] == "SAT-1"
        assert details["overlap_seconds"] > 0

    def test_delete_refreshes_conflicts_after_mutation(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Deleting one side of a conflict should clear the persisted conflict state."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=9)
        first = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="DEL-1",
            start_time=_iso(base_start),
            end_time=_iso(base_start + timedelta(minutes=10)),
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
            state="committed",
        )
        second = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="DEL-2",
            start_time=_iso(base_start + timedelta(minutes=4)),
            end_time=_iso(base_start + timedelta(minutes=12)),
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
            state="committed",
        )

        recompute = client.post(
            "/api/v1/schedule/conflicts/recompute",
            json={"workspace_id": workspace_id},
        )
        assert recompute.status_code == 200, recompute.json()

        conflicts_before = client.get(
            "/api/v1/schedule/conflicts",
            params={"workspace_id": workspace_id},
        )
        assert conflicts_before.status_code == 200, conflicts_before.json()
        assert len(conflicts_before.json()["conflicts"]) >= 1, conflicts_before.json()

        deleted = client.delete(
            f"/api/v1/schedule/acquisition/{second.id}",
            params={"workspace_id": workspace_id},
        )
        assert deleted.status_code == 200, deleted.json()

        state = client.get(
            "/api/v1/schedule/conflicts",
            params={"workspace_id": workspace_id},
        )
        assert state.status_code == 200, state.json()
        assert len(state.json()["conflicts"]) == 0, state.json()
        assert db.get_acquisition(first.id) is not None

    def test_bulk_delete_refreshes_conflicts_after_mutation(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Bulk delete should also clear stale conflicts for affected workspaces."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=11)
        first = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="BDEL-1",
            start_time=_iso(base_start),
            end_time=_iso(base_start + timedelta(minutes=10)),
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
            state="committed",
        )
        second = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="BDEL-2",
            start_time=_iso(base_start + timedelta(minutes=3)),
            end_time=_iso(base_start + timedelta(minutes=12)),
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
            state="committed",
        )

        recompute = client.post(
            "/api/v1/schedule/conflicts/recompute",
            json={"workspace_id": workspace_id},
        )
        assert recompute.status_code == 200, recompute.json()

        deleted = client.post(
            "/api/v1/schedule/acquisitions/bulk-delete",
            json={
                "acquisition_ids": [first.id],
                "workspace_id": workspace_id,
            },
        )
        assert deleted.status_code == 200, deleted.json()

        conflicts_after = client.get(
            "/api/v1/schedule/conflicts",
            params={"workspace_id": workspace_id},
        )
        assert conflicts_after.status_code == 200, conflicts_after.json()
        assert len(conflicts_after.json()["conflicts"]) == 0, conflicts_after.json()
        assert db.get_acquisition(second.id) is not None

    def test_bulk_delete_reports_all_skip_reasons(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Bulk delete should surface freeze and workspace skips alongside deletions."""
        client, db, workspace_id = isolated_schedule_api
        other_workspace_id = get_workspace_db().create_workspace(
            name="Other workspace",
            mission_mode="OPTICAL",
        )

        now = datetime.now(timezone.utc)
        frozen = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="SKIP-FROZEN",
            start_time=_iso(now + timedelta(minutes=30)),
            end_time=_iso(now + timedelta(minutes=35)),
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
            state="committed",
        )
        safe = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="SKIP-SAFE",
            start_time=_iso(now + timedelta(hours=6)),
            end_time=_iso(now + timedelta(hours=6, minutes=5)),
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
            state="committed",
        )
        cross_workspace = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="SKIP-CROSS",
            start_time=_iso(now + timedelta(hours=8)),
            end_time=_iso(now + timedelta(hours=8, minutes=5)),
            roll_angle_deg=0.0,
            workspace_id=other_workspace_id,
            state="committed",
        )

        deleted = client.post(
            "/api/v1/schedule/acquisitions/bulk-delete",
            json={
                "acquisition_ids": [frozen.id, safe.id, cross_workspace.id],
                "workspace_id": workspace_id,
            },
        )

        assert deleted.status_code == 200, deleted.json()
        payload = deleted.json()
        assert payload["deleted"] == 1, payload
        assert payload["failed"] == [], payload
        assert payload["skipped_frozen"] == [frozen.id], payload
        assert payload["skipped_workspace"] == [cross_workspace.id], payload
        assert payload["skipped_hard_locked"] == [], payload
        assert db.get_acquisition(safe.id) is None
        assert db.get_acquisition(frozen.id) is not None
        assert db.get_acquisition(cross_workspace.id) is not None

    def test_rollback_refreshes_conflicts_after_mutation(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Rollback should restore the snapshot and clear conflicts that no longer apply."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=13)
        base_end = base_start + timedelta(minutes=5)

        first_plan = _create_plan(
            db,
            workspace_id,
            run_suffix="rollback-first",
            satellite_id="SAT-1",
            target_id="RB-1",
            start_time=_iso(base_start),
            end_time=_iso(base_end),
        )
        first_commit = client.post(
            "/api/v1/schedule/commit",
            json={
                "plan_id": first_plan,
                "workspace_id": workspace_id,
                "lock_level": "none",
            },
        )
        assert first_commit.status_code == 200, first_commit.json()

        second_plan = _create_plan(
            db,
            workspace_id,
            run_suffix="rollback-second",
            satellite_id="SAT-1",
            target_id="RB-2",
            start_time=_iso(base_start + timedelta(minutes=2)),
            end_time=_iso(base_start + timedelta(minutes=7)),
        )
        second_commit = client.post(
            "/api/v1/schedule/commit",
            json={
                "plan_id": second_plan,
                "workspace_id": workspace_id,
                "lock_level": "none",
                "force": True,
            },
        )
        assert second_commit.status_code == 200, second_commit.json()
        assert second_commit.json()["conflicts_detected"] >= 1, second_commit.json()

        conflicts_before = client.get(
            "/api/v1/schedule/conflicts",
            params={"workspace_id": workspace_id},
        )
        assert conflicts_before.status_code == 200, conflicts_before.json()
        assert len(conflicts_before.json()["conflicts"]) >= 1, conflicts_before.json()

        snapshots = db.list_snapshots(workspace_id)
        snapshot_id = next(
            snapshot["id"] for snapshot in snapshots if snapshot["plan_id"] == second_plan
        )

        rollback = client.post(
            "/api/v1/schedule/rollback",
            json={
                "snapshot_id": snapshot_id,
                "workspace_id": workspace_id,
            },
        )
        assert rollback.status_code == 200, rollback.json()
        assert rollback.json()["restored"] == 1, rollback.json()
        assert rollback.json()["conflicts_detected"] == 0, rollback.json()

        conflicts_after = client.get(
            "/api/v1/schedule/conflicts",
            params={"workspace_id": workspace_id},
        )
        assert conflicts_after.status_code == 200, conflicts_after.json()
        assert len(conflicts_after.json()["conflicts"]) == 0, conflicts_after.json()

    def test_schedule_state_freeze_cutoff_uses_single_utc_suffix(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Schedule state should not emit timestamps like +00:00Z."""
        client, db, workspace_id = isolated_schedule_api

        base_start = datetime.now(timezone.utc) + timedelta(days=3)
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="STATE-1",
            start_time=_iso(base_start),
            end_time=_iso(base_start + timedelta(minutes=5)),
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
            state="committed",
        )

        state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id},
        )
        assert state.status_code == 200, state.json()
        freeze_cutoff = state.json()["state"]["horizon"]["freeze_cutoff"]
        assert freeze_cutoff.endswith("Z")
        assert "+00:00Z" not in freeze_cutoff


class TestPlanningModeSelection:
    """Regression coverage for frontend/backend auto-mode alignment."""

    def test_mission_analysis_clears_stale_workspace_opportunity_cache(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """A fresh feasibility run must invalidate stale planner opportunities."""
        client, _db, workspace_id = isolated_schedule_api
        original_state = _snapshot_analysis_state()
        set_cached_opportunities(
            [{"id": "stale-opp", "target_id": "STALE"}], workspace_id
        )

        start = datetime.now(timezone.utc) + timedelta(days=1)
        end = start + timedelta(days=1)

        try:
            response = client.post(
                "/api/v1/mission/analyze",
                json={
                    "workspace_id": workspace_id,
                    "tle": _sample_tle_payload(),
                    "targets": [
                        {
                            "name": "FreshTarget",
                            "latitude": 25.0,
                            "longitude": 55.0,
                            "priority": 3,
                        }
                    ],
                    "start_time": _iso(start),
                    "end_time": _iso(end),
                    "mission_type": "imaging",
                    "imaging_type": "optical",
                },
            )
            assert response.status_code == 200, response.text
            assert get_cached_opportunities(workspace_id) == []
        finally:
            _restore_analysis_state(original_state)

    def test_mode_selection_returns_from_scratch_without_existing_schedule(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """No active acquisitions should keep the planner in from-scratch mode."""
        client, _db, workspace_id = isolated_schedule_api
        original_state = _snapshot_analysis_state()
        set_current_mission_data(_set_current_targets(["TGT-1"]), workspace_id)

        try:
            response = client.post(
                "/api/v1/schedule/mode-selection",
                json={"workspace_id": workspace_id},
            )
        finally:
            _restore_analysis_state(original_state)

        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["success"] is True
        assert body["planning_mode"] == "from_scratch"
        assert body["existing_acquisition_count"] == 0

    def test_mode_selection_returns_repair_for_same_target_set(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Existing schedule with the same targets should select repair."""
        client, db, workspace_id = isolated_schedule_api
        original_state = _snapshot_analysis_state()
        set_current_mission_data(_set_current_targets(["TGT-1"]), workspace_id)

        start = datetime.now(timezone.utc) + timedelta(days=1)
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="TGT-1",
            start_time=_iso(start),
            end_time=_iso(start + timedelta(minutes=2)),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )

        try:
            response = client.post(
                "/api/v1/schedule/mode-selection",
                json={"workspace_id": workspace_id},
            )
        finally:
            _restore_analysis_state(original_state)

        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["success"] is True
        assert body["planning_mode"] == "repair"
        assert body["existing_acquisition_count"] == 1
        assert body["new_target_count"] == 0

    def test_mode_selection_returns_incremental_for_new_targets(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Adding new targets on top of an existing schedule should select incremental."""
        client, db, workspace_id = isolated_schedule_api
        original_state = _snapshot_analysis_state()
        set_current_mission_data(_set_current_targets(["TGT-1", "TGT-2"]), workspace_id)

        start = datetime.now(timezone.utc) + timedelta(days=1)
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="TGT-1",
            start_time=_iso(start),
            end_time=_iso(start + timedelta(minutes=2)),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )

        try:
            response = client.post(
                "/api/v1/schedule/mode-selection",
                json={"workspace_id": workspace_id},
            )
        finally:
            _restore_analysis_state(original_state)

        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["success"] is True
        assert body["planning_mode"] == "incremental"
        assert body["existing_acquisition_count"] == 1
        assert body["new_target_count"] == 1

    def test_mode_selection_returns_repair_when_scheduled_target_is_removed(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Removing currently scheduled work from scope must trigger repair."""
        client, db, workspace_id = isolated_schedule_api
        original_state = _snapshot_analysis_state()
        set_current_mission_data(
            _set_current_targets(["TGT-1", "TGT-3"]),
            workspace_id,
        )

        start = datetime.now(timezone.utc) + timedelta(days=1)
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="TGT-1",
            start_time=_iso(start),
            end_time=_iso(start + timedelta(minutes=2)),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="TGT-2",
            start_time=_iso(start + timedelta(minutes=10)),
            end_time=_iso(start + timedelta(minutes=12)),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )

        try:
            response = client.post(
                "/api/v1/schedule/mode-selection",
                json={"workspace_id": workspace_id},
            )
        finally:
            _restore_analysis_state(original_state)

        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["success"] is True
        assert body["planning_mode"] == "repair"
        assert body["removed_scheduled_target_count"] == 1
        assert "no longer in scope" in body["reason"]

    def test_mode_selection_keeps_incremental_when_only_unscheduled_baseline_target_is_removed(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Removing an unscheduled baseline-only target should not force repair."""
        client, db, workspace_id = isolated_schedule_api
        original_state = _snapshot_analysis_state()
        set_current_mission_data(
            _set_current_targets(["TGT-1", "TGT-2", "TGT-4"]),
            workspace_id,
        )

        get_workspace_db().update_workspace(
            workspace_id=workspace_id,
            planning_state={
                "current_target_ids": ["TGT-1", "TGT-2", "TGT-3"],
            },
        )

        start = datetime.now(timezone.utc) + timedelta(days=1)
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="TGT-1",
            start_time=_iso(start),
            end_time=_iso(start + timedelta(minutes=2)),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )

        try:
            response = client.post(
                "/api/v1/schedule/mode-selection",
                json={"workspace_id": workspace_id},
            )
        finally:
            _restore_analysis_state(original_state)

        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["success"] is True
        assert body["planning_mode"] == "incremental"
        assert body["removed_scheduled_target_count"] == 0
        assert body["new_target_count"] == 1

    def test_mode_selection_escalates_to_repair_for_higher_priority_new_targets(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """High-priority new work should trigger repair so the scheduler can reshuffle."""
        client, db, workspace_id = isolated_schedule_api
        original_state = _snapshot_analysis_state()
        set_current_mission_data(
            {
                "mission_data": {
                    "targets": [
                        {"name": "TGT-1", "priority": 5},
                        {"name": "TGT-2", "priority": 1},
                    ]
                }
            },
            workspace_id,
        )

        start = datetime.now(timezone.utc) + timedelta(days=1)
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="TGT-1",
            start_time=_iso(start),
            end_time=_iso(start + timedelta(minutes=2)),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )

        try:
            response = client.post(
                "/api/v1/schedule/mode-selection",
                json={"workspace_id": workspace_id},
            )
        finally:
            _restore_analysis_state(original_state)

        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["success"] is True
        assert body["planning_mode"] == "repair"
        assert "higher-priority" in body["reason"]
        assert body["new_target_count"] == 1

    def test_mode_selection_keeps_incremental_when_priority_weight_is_zero(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Priority-only escalation should not fire when priority has no scoring weight."""
        client, db, workspace_id = isolated_schedule_api
        original_state = _snapshot_analysis_state()
        set_current_mission_data(
            {
                "mission_data": {
                    "targets": [
                        {"name": "TGT-1", "priority": 5},
                        {"name": "TGT-2", "priority": 1},
                    ]
                }
            },
            workspace_id,
        )

        start = datetime.now(timezone.utc) + timedelta(days=1)
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="TGT-1",
            start_time=_iso(start),
            end_time=_iso(start + timedelta(minutes=2)),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )

        try:
            response = client.post(
                "/api/v1/schedule/mode-selection",
                json={
                    "workspace_id": workspace_id,
                    "weight_priority": 0,
                    "weight_geometry": 100,
                    "weight_timing": 0,
                },
            )
        finally:
            _restore_analysis_state(original_state)

        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["success"] is True
        assert body["planning_mode"] == "incremental"
        assert "Planning incrementally" in body["reason"]
        assert body["new_target_count"] == 1

    def test_mode_selection_accepts_explicit_utc_horizon_with_existing_schedule(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Explicit Z-suffixed horizons should not crash auto-mode selection."""
        client, db, workspace_id = isolated_schedule_api
        original_state = _snapshot_analysis_state()
        set_current_mission_data(_set_current_targets(["TGT-1", "TGT-2"]), workspace_id)

        start = datetime.now(timezone.utc) + timedelta(days=1)
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="TGT-1",
            start_time=_iso(start),
            end_time=_iso(start + timedelta(minutes=2)),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )

        try:
            response = client.post(
                "/api/v1/schedule/mode-selection",
                json={
                    "workspace_id": workspace_id,
                    "horizon_from": _iso(start - timedelta(hours=1)),
                    "horizon_to": _iso(start + timedelta(days=1)),
                },
            )
        finally:
            _restore_analysis_state(original_state)

        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["success"] is True
        assert body["planning_mode"] == "incremental"
        assert body["existing_acquisition_count"] == 1
        assert body["new_target_count"] == 1

    def test_mode_selection_uses_workspace_target_baseline_not_only_committed_targets(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Previously planned-but-unscheduled targets must not be miscounted as newly added."""
        client, db, workspace_id = isolated_schedule_api
        original_state = _snapshot_analysis_state()
        set_current_mission_data(
            _set_current_targets(["TGT-1", "TGT-2", "TGT-3", "TGT-4"]),
            workspace_id,
        )

        get_workspace_db().update_workspace(
            workspace_id=workspace_id,
            planning_state={
                "current_target_ids": ["TGT-1", "TGT-2", "TGT-3"],
            },
        )

        start = datetime.now(timezone.utc) + timedelta(days=1)
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="TGT-1",
            start_time=_iso(start),
            end_time=_iso(start + timedelta(minutes=2)),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )

        try:
            response = client.post(
                "/api/v1/schedule/mode-selection",
                json={"workspace_id": workspace_id},
            )
        finally:
            _restore_analysis_state(original_state)

        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["success"] is True
        assert body["planning_mode"] == "incremental"
        assert body["existing_target_ids"] == ["TGT-1", "TGT-2", "TGT-3"]
        assert body["current_target_ids"] == ["TGT-1", "TGT-2", "TGT-3", "TGT-4"]
        assert body["new_target_count"] == 1

    def test_incremental_planning_only_returns_new_targets(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Incremental planning should not return alternate opportunities for already planned targets."""
        client, db, workspace_id = isolated_schedule_api
        original_state = _snapshot_analysis_state()

        existing_start = datetime.now(timezone.utc) + timedelta(days=1)
        alternate_existing_slot = _iso(existing_start + timedelta(minutes=20))
        new_target_slot = _iso(existing_start + timedelta(minutes=30))

        get_workspace_db().update_workspace(
            workspace_id=workspace_id,
            planning_state={"current_target_ids": ["TGT-1"]},
        )

        set_current_mission_data(
            {
                "passes": [
                    {
                        "satellite_name": "SAT-1",
                        "target_name": "TGT-1",
                        "start_time": _state_iso(existing_start + timedelta(minutes=20)),
                        "end_time": _state_iso(existing_start + timedelta(minutes=20)),
                        "max_elevation_time": _state_iso(
                            existing_start + timedelta(minutes=20)
                        ),
                        "max_elevation": 42.0,
                        "start_azimuth": 180.0,
                    },
                    {
                        "satellite_name": "SAT-1",
                        "target_name": "TGT-2",
                        "start_time": _state_iso(existing_start + timedelta(minutes=30)),
                        "end_time": _state_iso(existing_start + timedelta(minutes=30)),
                        "max_elevation_time": _state_iso(
                            existing_start + timedelta(minutes=30)
                        ),
                        "max_elevation": 40.0,
                        "start_azimuth": 182.0,
                    },
                ],
                "targets": [
                    TargetData(name="TGT-1", latitude=25.0, longitude=55.0, priority=5),
                    TargetData(name="TGT-2", latitude=25.5, longitude=55.5, priority=1),
                ],
                "mission_data": {
                    "start_time": _state_iso(existing_start),
                    "end_time": _state_iso(existing_start + timedelta(hours=1)),
                    "max_spacecraft_pitch_deg": 45.0,
                },
                "satellites_dict": {},
            },
            workspace_id,
        )

        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="TGT-1",
            start_time=_iso(existing_start),
            end_time=_iso(existing_start),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )

        try:
            response = client.post(
                "/api/v1/planning/schedule",
                json={
                    "algorithms": ["roll_pitch_best_fit"],
                    "mode": "incremental",
                    "workspace_id": workspace_id,
                },
            )
        finally:
            _restore_analysis_state(original_state)

        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["success"] is True, body
        schedule = body["results"]["roll_pitch_best_fit"]["schedule"]
        assert [item["target_id"] for item in schedule] == ["TGT-2"], body

    def test_schedule_state_excludes_failed_acquisitions_by_default(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Active schedule state should hide superseded failed acquisitions unless explicitly requested."""
        client, db, workspace_id = isolated_schedule_api
        base_start = datetime.now(timezone.utc) + timedelta(days=1)

        active = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="ACTIVE-1",
            start_time=_iso(base_start),
            end_time=_iso(base_start),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )
        failed = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="FAILED-1",
            start_time=_iso(base_start + timedelta(minutes=15)),
            end_time=_iso(base_start + timedelta(minutes=15)),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="failed",
            workspace_id=workspace_id,
        )

        default_state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id},
        )
        assert default_state.status_code == 200, default_state.json()
        default_ids = {
            acq["id"] for acq in default_state.json()["state"]["acquisitions"]
        }
        assert active.id in default_ids, default_state.json()
        assert failed.id not in default_ids, default_state.json()

        historical_state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id, "include_failed": "true"},
        )
        assert historical_state.status_code == 200, historical_state.json()
        historical_by_id = {
            acq["id"]: acq for acq in historical_state.json()["state"]["acquisitions"]
        }
        assert failed.id in historical_by_id, historical_state.json()
        assert historical_by_id[failed.id]["state"] == "failed"

    def test_schedule_horizon_excludes_failed_acquisitions_by_default(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Horizon reads should treat failed acquisitions as history unless include_failed=true."""
        client, db, workspace_id = isolated_schedule_api
        base_start = datetime.now(timezone.utc) + timedelta(days=2)

        active = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="ACTIVE-H",
            start_time=_iso(base_start),
            end_time=_iso(base_start + timedelta(minutes=5)),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )
        failed = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="FAILED-H",
            start_time=_iso(base_start + timedelta(minutes=10)),
            end_time=_iso(base_start + timedelta(minutes=15)),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="failed",
            workspace_id=workspace_id,
        )

        params = {
            "workspace_id": workspace_id,
            "from": _iso(base_start - timedelta(minutes=1)),
            "to": _iso(base_start + timedelta(hours=1)),
        }

        default_horizon = client.get("/api/v1/schedule/horizon", params=params)
        assert default_horizon.status_code == 200, default_horizon.json()
        default_ids = {acq["id"] for acq in default_horizon.json()["acquisitions"]}
        assert active.id in default_ids, default_horizon.json()
        assert failed.id not in default_ids, default_horizon.json()

        historical_horizon = client.get(
            "/api/v1/schedule/horizon",
            params={**params, "include_failed": "true"},
        )
        assert historical_horizon.status_code == 200, historical_horizon.json()
        historical_by_id = {
            acq["id"]: acq for acq in historical_horizon.json()["acquisitions"]
        }
        assert failed.id in historical_by_id, historical_horizon.json()
        assert historical_by_id[failed.id]["state"] == "failed"

    def test_repair_drops_acquisitions_for_targets_removed_from_current_scope(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Repair mode should remove flex acquisitions whose targets are no longer in the current mission."""
        client, db, workspace_id = isolated_schedule_api
        original_state = _snapshot_analysis_state()

        base_start = datetime.now(timezone.utc) + timedelta(days=1)
        keep_slot = _iso(base_start)
        removed_slot = _iso(base_start + timedelta(minutes=20))

        set_current_mission_data(
            {
                "passes": [
                    {
                        "satellite_name": "SAT-1",
                        "target_name": "ACTIVE-TGT",
                        "start_time": keep_slot,
                        "end_time": keep_slot,
                        "max_elevation_time": keep_slot,
                        "max_elevation": 42.0,
                        "start_azimuth": 180.0,
                    }
                ],
                "targets": [
                    TargetData(
                        name="ACTIVE-TGT", latitude=25.0, longitude=55.0, priority=5
                    ),
                ],
                "mission_data": {
                    "targets": [
                        {"name": "ACTIVE-TGT", "priority": 5},
                    ],
                    "start_time": keep_slot,
                    "end_time": _iso(base_start + timedelta(hours=1)),
                },
            },
            workspace_id,
        )

        active = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="ACTIVE-TGT",
            start_time=keep_slot,
            end_time=keep_slot,
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )
        removed = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="REMOVED-TGT",
            start_time=removed_slot,
            end_time=removed_slot,
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )

        try:
            repair = client.post(
                "/api/v1/schedule/repair",
                json={
                    "workspace_id": workspace_id,
                    "planning_mode": "repair",
                    "target_priorities": {"ACTIVE-TGT": 5},
                },
            )
            assert repair.status_code == 200, repair.json()
            repair_body = repair.json()
            assert removed.id in repair_body["repair_diff"]["dropped"], repair_body

            commit = client.post(
                "/api/v1/schedule/repair/commit",
                json={
                    "workspace_id": workspace_id,
                    "plan_id": repair_body["plan_id"],
                    "drop_acquisition_ids": repair_body["repair_diff"]["dropped"],
                    "force": True,
                },
            )
        finally:
            _restore_analysis_state(original_state)

        assert commit.status_code == 200, commit.json()

        active_state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id},
        )
        assert active_state.status_code == 200, active_state.json()
        active_ids = {
            acq["id"] for acq in active_state.json()["state"]["acquisitions"]
        }
        assert active.id in active_ids, active_state.json()
        assert removed.id not in active_ids, active_state.json()

        historical_state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id, "include_failed": "true"},
        )
        assert historical_state.status_code == 200, historical_state.json()
        historical_by_id = {
            acq["id"]: acq for acq in historical_state.json()["state"]["acquisitions"]
        }
        assert removed.id in historical_by_id, historical_state.json()
        assert historical_by_id[removed.id]["state"] == "failed"

    def test_repair_commit_applies_persisted_added_plan_items(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Repair commits should create the newly added acquisitions produced by the repair plan."""
        client, db, workspace_id = isolated_schedule_api
        original_state = _snapshot_analysis_state()

        existing_start = datetime.now(timezone.utc) + timedelta(days=1)
        added_slot = _state_iso(existing_start + timedelta(minutes=30))
        set_cached_opportunities([], workspace_id)
        set_current_mission_data(
            {
                "passes": [
                    {
                        "satellite_name": "SAT-1",
                        "target_name": "TGT-2",
                        "start_time": added_slot,
                        "end_time": added_slot,
                        "max_elevation_time": added_slot,
                        "max_elevation": 44.0,
                        "start_azimuth": 180.0,
                    }
                ],
                "targets": [
                    TargetData(name="TGT-1", latitude=25.0, longitude=55.0, priority=5),
                    TargetData(name="TGT-2", latitude=25.5, longitude=55.5, priority=1),
                ],
                "mission_data": {
                    "start_time": _state_iso(existing_start),
                    "end_time": _state_iso(existing_start + timedelta(hours=1)),
                    "max_spacecraft_pitch_deg": 45.0,
                },
                "satellites_dict": {},
            },
            workspace_id,
        )

        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="TGT-1",
            start_time=_iso(existing_start),
            end_time=_iso(existing_start),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )

        try:
            repair = client.post(
                "/api/v1/schedule/repair",
                json={
                    "workspace_id": workspace_id,
                    "target_priorities": {"TGT-1": 5, "TGT-2": 1},
                },
            )
            assert repair.status_code == 200, repair.json()
            repair_body = repair.json()
            assert repair_body["repair_diff"]["added"], repair_body

            commit = client.post(
                "/api/v1/schedule/repair/commit",
                json={
                    "plan_id": repair_body["plan_id"],
                    "workspace_id": workspace_id,
                    "drop_acquisition_ids": repair_body["repair_diff"]["dropped"],
                    "force": True,
                },
            )
        finally:
            _restore_analysis_state(original_state)

        assert commit.status_code == 200, commit.json()
        commit_body = commit.json()
        assert commit_body["committed"] == len(repair_body["repair_diff"]["added"])

        state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id},
        )
        assert state.status_code == 200, state.json()
        target_ids = {acq["target_id"] for acq in state.json()["state"]["acquisitions"]}
        assert "TGT-2" in target_ids

    def test_repair_commit_rejects_stale_second_operator_commit(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Two repair plans from the same revision should resolve to one winner and one stale 409."""
        client, db, workspace_id = isolated_schedule_api
        original_state = _snapshot_analysis_state()

        keep_slot = _state_iso(datetime.now(timezone.utc) + timedelta(days=2))
        removed_slot = _state_iso(datetime.now(timezone.utc) + timedelta(days=2, minutes=20))
        set_cached_opportunities([], workspace_id)
        set_current_mission_data(
            {
                "targets": [
                    TargetData(
                        name="ACTIVE-TGT", latitude=25.0, longitude=55.0, priority=5
                    ),
                ],
                "mission_data": {
                    "targets": [
                        {"name": "ACTIVE-TGT", "priority": 5},
                    ],
                    "start_time": keep_slot,
                    "end_time": _state_iso(
                        datetime.now(timezone.utc) + timedelta(days=2, hours=1)
                    ),
                },
            },
            workspace_id,
        )

        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="ACTIVE-TGT",
            start_time=keep_slot,
            end_time=keep_slot,
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="REMOVED-TGT",
            start_time=removed_slot,
            end_time=removed_slot,
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )

        try:
            repair_a = client.post(
                "/api/v1/schedule/repair",
                json={
                    "workspace_id": workspace_id,
                    "planning_mode": "repair",
                    "target_priorities": {"ACTIVE-TGT": 5},
                },
            )
            repair_b = client.post(
                "/api/v1/schedule/repair",
                json={
                    "workspace_id": workspace_id,
                    "planning_mode": "repair",
                    "target_priorities": {"ACTIVE-TGT": 5},
                },
            )
        finally:
            _restore_analysis_state(original_state)

        assert repair_a.status_code == 200, repair_a.json()
        assert repair_b.status_code == 200, repair_b.json()
        repair_a_body = repair_a.json()
        repair_b_body = repair_b.json()
        assert repair_a_body["plan_id"] != repair_b_body["plan_id"], (
            repair_a_body,
            repair_b_body,
        )
        assert repair_a_body["expected_revision"] == repair_b_body["expected_revision"], (
            repair_a_body,
            repair_b_body,
        )

        commit_a = client.post(
            "/api/v1/schedule/repair/commit",
            json={
                "workspace_id": workspace_id,
                "plan_id": repair_a_body["plan_id"],
                "drop_acquisition_ids": repair_a_body["repair_diff"]["dropped"],
                "expected_revision": repair_a_body["expected_revision"],
                "force": True,
            },
        )
        assert commit_a.status_code == 200, commit_a.json()

        commit_b = client.post(
            "/api/v1/schedule/repair/commit",
            json={
                "workspace_id": workspace_id,
                "plan_id": repair_b_body["plan_id"],
                "drop_acquisition_ids": repair_b_body["repair_diff"]["dropped"],
                "expected_revision": repair_b_body["expected_revision"],
                "force": True,
            },
        )
        assert commit_b.status_code == 409, commit_b.json()
        detail = commit_b.json()["detail"]
        assert "Schedule changed before apply completed" in detail["message"], detail

        state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id},
        )
        assert state.status_code == 200, state.json()
        target_ids = {acq["target_id"] for acq in state.json()["state"]["acquisitions"]}
        assert "ACTIVE-TGT" in target_ids
        assert "REMOVED-TGT" not in target_ids

    def test_planning_opportunities_are_workspace_scoped(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Opportunity queries must not leak the last analyzed mission from another workspace."""
        client, _db, workspace_id = isolated_schedule_api
        other_workspace_id = get_workspace_db().create_workspace(name="Other Workspace")
        original_state = _snapshot_analysis_state()

        set_current_mission_data(
            {
                "passes": [
                    {
                        "satellite_name": "SAT-1",
                        "target_name": "ScopedTarget",
                        "start_time": _state_iso(
                            datetime.now(timezone.utc) + timedelta(days=2)
                        ),
                        "end_time": _state_iso(
                            datetime.now(timezone.utc) + timedelta(days=2, minutes=5)
                        ),
                        "max_elevation": 42.0,
                        "start_azimuth": 180.0,
                    }
                ],
                "targets": [{"name": "ScopedTarget"}],
                "mission_data": {
                    "targets": [{"name": "ScopedTarget"}],
                },
            },
            workspace_id,
        )

        try:
            own_response = client.get(
                "/api/v1/planning/opportunities",
                params={"workspace_id": workspace_id},
            )
            other_response = client.get(
                "/api/v1/planning/opportunities",
                params={"workspace_id": other_workspace_id},
            )
        finally:
            _restore_analysis_state(original_state)

        assert own_response.status_code == 200, own_response.json()
        own_body = own_response.json()
        assert own_body["success"] is True
        assert own_body["count"] == 1
        assert own_body["opportunities"][0]["target_id"] == "ScopedTarget"

        assert other_response.status_code == 404, other_response.text

    def test_incremental_planning_blocks_exactly_matching_committed_opportunities(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Incremental planning must not re-propose an already committed point opportunity."""
        client, db, workspace_id = isolated_schedule_api
        original_state = _snapshot_analysis_state()

        base_start = datetime.now(timezone.utc) + timedelta(days=1)
        exact_slot = _iso(base_start)
        later_slot = _iso(base_start + timedelta(minutes=10))

        set_current_mission_data(
            {
                "passes": [
                    {
                        "satellite_name": "SAT-1",
                        "target_name": "TGT-1",
                        "start_time": _state_iso(base_start),
                        "end_time": _state_iso(base_start),
                        "max_elevation_time": _state_iso(base_start),
                        "max_elevation": 42.0,
                        "start_azimuth": 180.0,
                    },
                    {
                        "satellite_name": "SAT-1",
                        "target_name": "TGT-2",
                        "start_time": _state_iso(base_start + timedelta(minutes=10)),
                        "end_time": _state_iso(base_start + timedelta(minutes=10)),
                        "max_elevation_time": _state_iso(
                            base_start + timedelta(minutes=10)
                        ),
                        "max_elevation": 40.0,
                        "start_azimuth": 182.0,
                    },
                ],
                "targets": [
                    TargetData(name="TGT-1", latitude=25.0, longitude=55.0, priority=5),
                    TargetData(name="TGT-2", latitude=25.5, longitude=55.5, priority=1),
                ],
                "mission_data": {
                    "start_time": _state_iso(base_start),
                    "end_time": _state_iso(base_start + timedelta(hours=1)),
                    "max_spacecraft_pitch_deg": 45.0,
                },
                "satellites_dict": {},
            },
            workspace_id,
        )

        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="TGT-1",
            start_time=exact_slot,
            end_time=exact_slot,
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            state="committed",
            workspace_id=workspace_id,
        )

        try:
            response = client.post(
                "/api/v1/planning/schedule",
                json={
                    "algorithms": ["roll_pitch_best_fit"],
                    "mode": "incremental",
                    "workspace_id": workspace_id,
                },
            )
        finally:
            _restore_analysis_state(original_state)

        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["success"] is True, body
        schedule = body["results"]["roll_pitch_best_fit"]["schedule"]
        assert [item["target_id"] for item in schedule] == ["TGT-2"], body
