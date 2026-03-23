"""
Regression tests for schedule commit conflict handling.

These tests exercise the API layer with an isolated SQLite database so we can
verify the full plan -> commit workflow without needing a live server.
"""

import hashlib
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator, Optional, Tuple

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.schedule_persistence import (
    DEFAULT_WORKSPACE_ID,
    ScheduleDB,
    get_schedule_db,
    reset_schedule_db,
)
from backend.workspace_persistence import get_workspace_db, reset_workspace_db


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

        other_state = client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": workspace_id},
        )
        assert other_state.status_code == 200, other_state.json()
        assert len(other_state.json()["state"]["acquisitions"]) == 1, other_state.json()

    def test_schedule_plan_accepts_future_aware_opportunities(
        self, isolated_schedule_api: Tuple[TestClient, ScheduleDB, str]
    ) -> None:
        """Planning preview should handle future aware timestamps without crashing."""
        client, _, workspace_id = isolated_schedule_api

        future_start = datetime.now(timezone.utc) + timedelta(days=14)
        original_state = getattr(app.state, "current_mission_data", {})
        app.state.current_mission_data = {
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
        }

        try:
            plan = client.post(
                "/api/v1/schedule/plan",
                json={
                    "planning_mode": "from_scratch",
                    "workspace_id": workspace_id,
                },
            )
        finally:
            app.state.current_mission_data = original_state

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

        assert repair_commit.status_code == 200, repair_commit.json()
        payload = repair_commit.json()
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
