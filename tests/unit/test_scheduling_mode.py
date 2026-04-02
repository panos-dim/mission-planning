"""Focused regression coverage for automatic scheduling-mode resolution."""

from __future__ import annotations

import os
import sys
import tempfile
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator, Tuple

import pytest
from fastapi.testclient import TestClient


def _install_orbit_predictor_stub() -> None:
    """Keep backend.main importable in lightweight unit-test environments."""
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
        def __init__(
            self,
            name: str = "stub",
            latitude_deg: float = 0.0,
            longitude_deg: float = 0.0,
            elevation_m: float = 0.0,
        ):
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

from backend.main import app, set_cached_opportunities, set_current_mission_data
from backend.order_materialization import materialize_recurring_orders_for_horizon
from backend.schedule_persistence import ScheduleDB, get_schedule_db, reset_schedule_db
from backend.workspace_persistence import get_workspace_db, reset_workspace_db


@pytest.fixture
def isolated_schedule_mode_api() -> Generator[Tuple[TestClient, ScheduleDB, str], None, None]:
    """Run scheduling-mode tests against a temporary shared DB."""
    original_schedule_path = get_schedule_db().db_path
    original_workspace_path = get_workspace_db().db_path

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    reset_schedule_db(db_path)
    reset_workspace_db(db_path)

    db = get_schedule_db()
    workspace_id = get_workspace_db().create_workspace(
        name="Scheduling Mode Workspace",
        mission_mode="OPTICAL",
    )

    with TestClient(app) as client:
        yield client, db, workspace_id

    reset_schedule_db(original_schedule_path)
    reset_workspace_db(original_workspace_path)
    if db_path.exists():
        os.unlink(db_path)


def _snapshot_analysis_state() -> dict:
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
    app.state.current_mission_data = snapshot["current_mission_data"]
    app.state.current_mission_data_by_workspace = snapshot[
        "current_mission_data_by_workspace"
    ]
    app.state.opportunities_cache = snapshot["opportunities_cache"]
    app.state.opportunities_cache_by_workspace = snapshot[
        "opportunities_cache_by_workspace"
    ]


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _opp(
    target_id: str,
    *,
    start: str,
    satellite_id: str = "SAT-1",
    value: float = 1.0,
) -> dict:
    return {
        "id": f"{satellite_id}_{target_id}_{start}",
        "opportunity_id": f"{satellite_id}_{target_id}_{start}",
        "satellite_id": satellite_id,
        "target_id": target_id,
        "start_time": start,
        "end_time": start,
        "roll_angle_deg": 0.0,
        "pitch_angle_deg": 0.0,
        "value": value,
        "priority": 3,
    }


def _set_planning_inputs(
    workspace_id: str,
    *,
    target_names: list[str],
    opportunities: list[dict],
) -> None:
    set_current_mission_data(
        {
            "mission_data": {
                "targets": [{"name": target_name, "priority": 3} for target_name in target_names]
            }
        },
        workspace_id,
    )
    set_cached_opportunities(opportunities, workspace_id)


def _create_template(
    db: ScheduleDB,
    workspace_id: str,
    **overrides,
):
    payload = {
        "workspace_id": workspace_id,
        "name": "Recurring Port Collect",
        "canonical_target_id": "PORT_A",
        "target_lat": 29.3772,
        "target_lon": 47.9906,
        "priority": 2,
        "constraints": {"max_incidence_deg": 30},
        "requested_satellite_group": None,
        "recurrence_type": "daily",
        "interval": 1,
        "days_of_week": None,
        "window_start_hhmm": "09:00",
        "window_end_hhmm": "10:00",
        "timezone_name": "UTC",
        "effective_start_date": "2026-04-02",
        "effective_end_date": "2026-04-04",
        "notes": "Daily collect",
        "external_ref": "EXT-REC-1",
    }
    payload.update(overrides)
    return db.create_order_template(
        workspace_id=payload["workspace_id"],
        name=payload["name"],
        canonical_target_id=payload["canonical_target_id"],
        target_lat=payload["target_lat"],
        target_lon=payload["target_lon"],
        priority=payload["priority"],
        constraints=payload["constraints"],
        requested_satellite_group=payload["requested_satellite_group"],
        recurrence_type=payload["recurrence_type"],
        interval=payload["interval"],
        days_of_week=payload["days_of_week"],
        window_start_hhmm=payload["window_start_hhmm"],
        window_end_hhmm=payload["window_end_hhmm"],
        timezone_name=payload["timezone_name"],
        effective_start_date=payload["effective_start_date"],
        effective_end_date=payload["effective_end_date"],
        notes=payload["notes"],
        external_ref=payload["external_ref"],
    )


def _post_mode_selection(
    client: TestClient,
    workspace_id: str,
    *,
    horizon_from: str = "2026-04-02T00:00:00Z",
    horizon_to: str = "2026-04-05T00:00:00Z",
):
    return client.post(
        "/api/v1/schedule/mode-selection",
        json={
            "workspace_id": workspace_id,
            "horizon_from": horizon_from,
            "horizon_to": horizon_to,
        },
    )


def test_mode_selection_uses_from_scratch_when_workspace_has_no_schedule(
    isolated_schedule_mode_api: Tuple[TestClient, ScheduleDB, str],
) -> None:
    client, _db, workspace_id = isolated_schedule_mode_api
    original_state = _snapshot_analysis_state()
    _set_planning_inputs(workspace_id, target_names=["TGT-1"], opportunities=[])

    try:
        response = _post_mode_selection(client, workspace_id)
    finally:
        _restore_analysis_state(original_state)

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["planning_mode"] == "from_scratch"
    assert body["existing_acquisition_count"] == 0
    assert body["current_materialized_instance_count"] == 0


def test_mode_selection_uses_incremental_for_newly_materialized_recurring_instances(
    isolated_schedule_mode_api: Tuple[TestClient, ScheduleDB, str],
) -> None:
    client, db, workspace_id = isolated_schedule_mode_api
    original_state = _snapshot_analysis_state()

    db.create_acquisition(
        satellite_id="SAT-1",
        target_id="LEGACY_TGT",
        start_time="2026-04-02T01:00:00Z",
        end_time="2026-04-02T01:05:00Z",
        roll_angle_deg=0.0,
        pitch_angle_deg=0.0,
        state="committed",
        workspace_id=workspace_id,
    )
    template = _create_template(db, workspace_id, effective_end_date="2026-04-02")
    _set_planning_inputs(
        workspace_id,
        target_names=["LEGACY_TGT", "PORT_A"],
        opportunities=[_opp("PORT_A", start="2026-04-02T09:00:00Z")],
    )

    try:
        response = _post_mode_selection(client, workspace_id)
    finally:
        _restore_analysis_state(original_state)

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["planning_mode"] == "incremental"
    assert body["current_materialized_instance_count"] == 1
    assert body["outstanding_instance_count"] == 1
    assert body["new_instance_count"] == 1
    assert f"{template.id}::2026-04-02" in body["current_target_ids"]


def test_mode_selection_stays_non_incremental_when_no_new_work_exists(
    isolated_schedule_mode_api: Tuple[TestClient, ScheduleDB, str],
) -> None:
    client, db, workspace_id = isolated_schedule_mode_api
    original_state = _snapshot_analysis_state()

    db.create_acquisition(
        satellite_id="SAT-1",
        target_id="TGT-1",
        start_time="2026-04-02T01:00:00Z",
        end_time="2026-04-02T01:05:00Z",
        roll_angle_deg=0.0,
        pitch_angle_deg=0.0,
        state="committed",
        workspace_id=workspace_id,
    )
    _set_planning_inputs(
        workspace_id,
        target_names=["TGT-1"],
        opportunities=[_opp("TGT-1", start="2026-04-02T01:00:00Z")],
    )

    try:
        response = _post_mode_selection(client, workspace_id)
    finally:
        _restore_analysis_state(original_state)

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["planning_mode"] == "repair"
    assert body["new_target_count"] == 0
    assert body["new_instance_count"] == 0
    assert body["fallback_from_mode"] is None


def test_mode_selection_falls_back_to_repair_when_incremental_input_is_invalid(
    isolated_schedule_mode_api: Tuple[TestClient, ScheduleDB, str],
) -> None:
    client, db, workspace_id = isolated_schedule_mode_api
    original_state = _snapshot_analysis_state()

    db.create_acquisition(
        satellite_id="SAT-1",
        target_id="TGT-1",
        start_time="2026-04-02T01:00:00Z",
        end_time="2026-04-02T01:05:00Z",
        roll_angle_deg=0.0,
        pitch_angle_deg=0.0,
        state="committed",
        workspace_id=workspace_id,
    )
    db.create_acquisition(
        satellite_id="SAT-1",
        target_id="STALE_TGT",
        start_time="2026-04-02T02:00:00Z",
        end_time="2026-04-02T02:05:00Z",
        roll_angle_deg=0.0,
        pitch_angle_deg=0.0,
        state="committed",
        workspace_id=workspace_id,
    )
    _set_planning_inputs(
        workspace_id,
        target_names=["TGT-1", "TGT-2"],
        opportunities=[
            _opp("TGT-1", start="2026-04-02T01:00:00Z"),
            _opp("TGT-2", start="2026-04-02T03:00:00Z"),
        ],
    )

    try:
        response = _post_mode_selection(client, workspace_id)
    finally:
        _restore_analysis_state(original_state)

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["planning_mode"] == "repair"
    assert body["fallback_from_mode"] == "incremental"
    assert body["removed_scheduled_target_count"] == 1
    assert body["new_target_count"] == 1


def test_mode_selection_treats_same_canonical_target_on_new_day_as_new_instance(
    isolated_schedule_mode_api: Tuple[TestClient, ScheduleDB, str],
) -> None:
    client, db, workspace_id = isolated_schedule_mode_api
    original_state = _snapshot_analysis_state()

    _create_template(db, workspace_id, effective_end_date="2026-04-03")
    orders, _summary = materialize_recurring_orders_for_horizon(
        db,
        workspace_id=workspace_id,
        horizon_start=datetime(2026, 4, 2, 0, 0, tzinfo=timezone.utc),
        horizon_end=datetime(2026, 4, 4, 0, 0, tzinfo=timezone.utc),
    )
    first_day = orders[0]
    db.create_acquisition(
        satellite_id="SAT-1",
        target_id=first_day.planner_target_id or first_day.target_id,
        start_time=first_day.requested_window_start or "2026-04-02T09:00:00Z",
        end_time=first_day.requested_window_end or "2026-04-02T10:00:00Z",
        roll_angle_deg=0.0,
        pitch_angle_deg=0.0,
        state="committed",
        workspace_id=workspace_id,
        order_id=first_day.id,
        template_id=first_day.template_id,
        instance_key=first_day.instance_key,
        canonical_target_id=first_day.canonical_target_id,
        display_target_name=first_day.canonical_target_id,
    )
    _set_planning_inputs(
        workspace_id,
        target_names=["PORT_A"],
        opportunities=[
            _opp("PORT_A", start="2026-04-02T09:00:00Z"),
            _opp("PORT_A", start="2026-04-03T09:00:00Z"),
        ],
    )

    try:
        response = _post_mode_selection(client, workspace_id)
    finally:
        _restore_analysis_state(original_state)

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["planning_mode"] == "incremental"
    assert body["current_materialized_instance_count"] == 2
    assert body["outstanding_instance_count"] == 1
    assert body["new_instance_count"] == 1


def test_mode_selection_handles_mixed_one_time_and_recurring_workloads(
    isolated_schedule_mode_api: Tuple[TestClient, ScheduleDB, str],
) -> None:
    client, db, workspace_id = isolated_schedule_mode_api
    original_state = _snapshot_analysis_state()

    db.create_acquisition(
        satellite_id="SAT-1",
        target_id="TGT-1",
        start_time="2026-04-02T01:00:00Z",
        end_time="2026-04-02T01:05:00Z",
        roll_angle_deg=0.0,
        pitch_angle_deg=0.0,
        state="committed",
        workspace_id=workspace_id,
    )
    _create_template(db, workspace_id, effective_end_date="2026-04-02")
    _set_planning_inputs(
        workspace_id,
        target_names=["TGT-1", "TGT-2", "PORT_A"],
        opportunities=[
            _opp("TGT-2", start="2026-04-02T04:00:00Z"),
            _opp("PORT_A", start="2026-04-02T09:00:00Z"),
        ],
    )

    try:
        response = _post_mode_selection(client, workspace_id)
    finally:
        _restore_analysis_state(original_state)

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["planning_mode"] == "incremental"
    assert body["new_target_count"] == 1
    assert body["outstanding_instance_count"] == 1
