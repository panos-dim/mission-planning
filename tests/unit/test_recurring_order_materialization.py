"""Regression coverage for recurring-order materialization and planning inputs."""

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
from backend.order_materialization import (
    materialize_recurring_orders_for_horizon,
    prepare_recurring_planner_inputs,
)
from backend.schedule_persistence import ScheduleDB, get_schedule_db, reset_schedule_db
from backend.schemas.target import TargetData
from backend.workspace_persistence import get_workspace_db, reset_workspace_db


@pytest.fixture
def isolated_recurring_planning_api() -> Generator[Tuple[TestClient, ScheduleDB, str], None, None]:
    """Run recurring-planning tests against a temporary shared workspace DB."""
    original_schedule_path = get_schedule_db().db_path
    original_workspace_path = get_workspace_db().db_path

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    reset_schedule_db(db_path)
    reset_workspace_db(db_path)

    db = get_schedule_db()
    workspace_id = get_workspace_db().create_workspace(
        name="Recurring Planning Workspace",
        mission_mode="OPTICAL",
    )

    with TestClient(app) as client:
        yield client, db, workspace_id

    reset_schedule_db(original_schedule_path)
    reset_workspace_db(original_workspace_path)
    if db_path.exists():
        os.unlink(db_path)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _state_iso(dt: datetime) -> str:
    return dt.isoformat()


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
        "effective_end_date": "2026-04-10",
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


def test_daily_recurrence_materializes_one_instance_per_local_day(
    isolated_recurring_planning_api: Tuple[TestClient, ScheduleDB, str],
) -> None:
    _client, db, workspace_id = isolated_recurring_planning_api
    _create_template(
        db,
        workspace_id,
        timezone_name="Asia/Dubai",
        window_start_hhmm="15:00",
        window_end_hhmm="17:00",
        effective_end_date="2026-04-04",
    )

    orders, summary = materialize_recurring_orders_for_horizon(
        db,
        workspace_id=workspace_id,
        horizon_start=datetime(2026, 4, 2, 0, 0, tzinfo=timezone.utc),
        horizon_end=datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc),
    )

    assert summary.created_instances == 3
    assert [order.instance_local_date for order in orders] == [
        "2026-04-02",
        "2026-04-03",
        "2026-04-04",
    ]
    assert orders[0].requested_window_start == "2026-04-02T11:00:00Z"
    assert orders[0].requested_window_end == "2026-04-02T13:00:00Z"


def test_weekly_recurrence_respects_weekday_filter(
    isolated_recurring_planning_api: Tuple[TestClient, ScheduleDB, str],
) -> None:
    _client, db, workspace_id = isolated_recurring_planning_api
    _create_template(
        db,
        workspace_id,
        recurrence_type="weekly",
        interval=1,
        days_of_week=["mon", "wed"],
        effective_start_date="2026-04-06",
        effective_end_date="2026-04-12",
    )

    orders, summary = materialize_recurring_orders_for_horizon(
        db,
        workspace_id=workspace_id,
        horizon_start=datetime(2026, 4, 6, 0, 0, tzinfo=timezone.utc),
        horizon_end=datetime(2026, 4, 13, 0, 0, tzinfo=timezone.utc),
    )

    assert summary.created_instances == 2
    assert [order.instance_local_date for order in orders] == [
        "2026-04-06",
        "2026-04-08",
    ]


def test_timezone_boundary_uses_template_local_date_not_utc_day(
    isolated_recurring_planning_api: Tuple[TestClient, ScheduleDB, str],
) -> None:
    _client, db, workspace_id = isolated_recurring_planning_api
    _create_template(
        db,
        workspace_id,
        timezone_name="Asia/Tokyo",
        window_start_hhmm="00:30",
        window_end_hhmm="01:30",
        effective_start_date="2026-04-02",
        effective_end_date="2026-04-02",
    )

    orders, summary = materialize_recurring_orders_for_horizon(
        db,
        workspace_id=workspace_id,
        horizon_start=datetime(2026, 4, 1, 15, 0, tzinfo=timezone.utc),
        horizon_end=datetime(2026, 4, 1, 18, 0, tzinfo=timezone.utc),
    )

    assert summary.created_instances == 1
    assert orders[0].instance_local_date == "2026-04-02"
    assert orders[0].requested_window_start == "2026-04-01T15:30:00Z"


def test_midnight_crossing_window_expands_into_next_utc_day(
    isolated_recurring_planning_api: Tuple[TestClient, ScheduleDB, str],
) -> None:
    _client, db, workspace_id = isolated_recurring_planning_api
    _create_template(
        db,
        workspace_id,
        window_start_hhmm="23:00",
        window_end_hhmm="01:00",
        effective_start_date="2026-04-02",
        effective_end_date="2026-04-02",
    )

    orders, summary = materialize_recurring_orders_for_horizon(
        db,
        workspace_id=workspace_id,
        horizon_start=datetime(2026, 4, 2, 22, 0, tzinfo=timezone.utc),
        horizon_end=datetime(2026, 4, 3, 2, 0, tzinfo=timezone.utc),
    )

    assert summary.created_instances == 1
    assert orders[0].instance_local_date == "2026-04-02"
    assert orders[0].requested_window_start == "2026-04-02T23:00:00Z"
    assert orders[0].requested_window_end == "2026-04-03T01:00:00Z"


def test_repeated_materialization_prevents_duplicates_and_keeps_distinct_planner_targets(
    isolated_recurring_planning_api: Tuple[TestClient, ScheduleDB, str],
) -> None:
    _client, db, workspace_id = isolated_recurring_planning_api
    template = _create_template(
        db,
        workspace_id,
        effective_end_date="2026-04-03",
    )

    first_orders, first_summary = materialize_recurring_orders_for_horizon(
        db,
        workspace_id=workspace_id,
        horizon_start=datetime(2026, 4, 2, 0, 0, tzinfo=timezone.utc),
        horizon_end=datetime(2026, 4, 4, 0, 0, tzinfo=timezone.utc),
    )
    second_orders, second_summary = materialize_recurring_orders_for_horizon(
        db,
        workspace_id=workspace_id,
        horizon_start=datetime(2026, 4, 2, 0, 0, tzinfo=timezone.utc),
        horizon_end=datetime(2026, 4, 4, 0, 0, tzinfo=timezone.utc),
    )

    assert first_summary.created_instances == 2
    assert second_summary.created_instances == 0
    assert second_summary.reused_instances == 2
    assert len(db.list_orders(workspace_id=workspace_id, limit=100)) == 2
    assert [order.planner_target_id for order in first_orders] == [
        f"{template.id}::2026-04-02",
        f"{template.id}::2026-04-03",
    ]
    assert [order.planner_target_id for order in second_orders] == [
        f"{template.id}::2026-04-02",
        f"{template.id}::2026-04-03",
    ]


def test_planning_input_assembly_rewrites_canonical_target_to_materialized_instances(
    isolated_recurring_planning_api: Tuple[TestClient, ScheduleDB, str],
) -> None:
    _client, db, workspace_id = isolated_recurring_planning_api
    template = _create_template(
        db,
        workspace_id,
        effective_end_date="2026-04-03",
    )
    base_opportunities = [
        {
            "id": "opp-1",
            "opportunity_id": "opp-1",
            "satellite_id": "SAT-1",
            "target_id": "PORT_A",
            "start_time": "2026-04-02T09:30:00Z",
            "end_time": "2026-04-02T09:30:00Z",
            "roll_angle_deg": 2.0,
            "pitch_angle_deg": 0.0,
            "value": 1.0,
        },
        {
            "id": "opp-2",
            "opportunity_id": "opp-2",
            "satellite_id": "SAT-1",
            "target_id": "PORT_A",
            "start_time": "2026-04-03T09:30:00Z",
            "end_time": "2026-04-03T09:30:00Z",
            "roll_angle_deg": 2.5,
            "pitch_angle_deg": 0.0,
            "value": 1.0,
        },
        {
            "id": "opp-other",
            "opportunity_id": "opp-other",
            "satellite_id": "SAT-1",
            "target_id": "OTHER_TARGET",
            "start_time": "2026-04-03T12:00:00Z",
            "end_time": "2026-04-03T12:00:00Z",
            "roll_angle_deg": 1.0,
            "pitch_angle_deg": 0.0,
            "value": 1.0,
        },
    ]

    bundle = prepare_recurring_planner_inputs(
        db,
        workspace_id=workspace_id,
        horizon_start=datetime(2026, 4, 2, 0, 0, tzinfo=timezone.utc),
        horizon_end=datetime(2026, 4, 4, 0, 0, tzinfo=timezone.utc),
        base_opportunities=base_opportunities,
        target_positions={"PORT_A": (29.3772, 47.9906), "OTHER_TARGET": (1.0, 2.0)},
    )

    assert bundle.materialization.created_instances == 2
    assert [opp["target_id"] for opp in bundle.opportunities] == [
        f"{template.id}::2026-04-02",
        f"{template.id}::2026-04-03",
        "OTHER_TARGET",
    ]
    assert bundle.target_positions[f"{template.id}::2026-04-02"] == pytest.approx(
        (29.3772, 47.9906)
    )
    recurring_lineages = [
        bundle.lineage_by_opportunity_id[opp["id"]]
        for opp in bundle.opportunities
        if opp["target_id"].startswith(template.id)
    ]
    assert all(lineage["template_id"] == template.id for lineage in recurring_lineages)
    assert all(lineage["canonical_target_id"] == "PORT_A" for lineage in recurring_lineages)


def test_schedule_plan_persists_lineage_for_materialized_instances(
    isolated_recurring_planning_api: Tuple[TestClient, ScheduleDB, str],
) -> None:
    client, db, workspace_id = isolated_recurring_planning_api
    template = _create_template(
        db,
        workspace_id,
        effective_end_date="2026-04-03",
    )
    original_state = _snapshot_analysis_state()
    set_current_mission_data(
        {
            "mission_data": {"targets": [{"name": "PORT_A"}]},
        },
        workspace_id,
    )
    set_cached_opportunities(
        [
            {
                "id": "opp-1",
                "opportunity_id": "opp-1",
                "satellite_id": "SAT-1",
                "target_id": "PORT_A",
                "start_time": "2026-04-02T09:30:00Z",
                "end_time": "2026-04-02T09:30:00Z",
                "roll_angle_deg": 2.0,
                "pitch_angle_deg": 0.0,
                "value": 1.0,
            },
            {
                "id": "opp-2",
                "opportunity_id": "opp-2",
                "satellite_id": "SAT-1",
                "target_id": "PORT_A",
                "start_time": "2026-04-03T09:30:00Z",
                "end_time": "2026-04-03T09:30:00Z",
                "roll_angle_deg": 2.5,
                "pitch_angle_deg": 0.0,
                "value": 1.0,
            },
        ],
        workspace_id,
    )

    try:
        response = client.post(
            "/api/v1/schedule/plan",
            json={
                "planning_mode": "from_scratch",
                "workspace_id": workspace_id,
                "horizon_from": "2026-04-02T00:00:00Z",
                "horizon_to": "2026-04-04T00:00:00Z",
            },
        )
    finally:
        _restore_analysis_state(original_state)

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["success"] is True
    assert [item["target_id"] for item in payload["new_plan_items"]] == [
        f"{template.id}::2026-04-02",
        f"{template.id}::2026-04-03",
    ]
    assert all(item["template_id"] == template.id for item in payload["new_plan_items"])
    assert all(item["canonical_target_id"] == "PORT_A" for item in payload["new_plan_items"])

    plan_items = db.get_plan_items(payload["plan_id"])
    assert [item.target_id for item in plan_items] == [
        f"{template.id}::2026-04-02",
        f"{template.id}::2026-04-03",
    ]
    assert all(item.order_id for item in plan_items)
    assert all(item.template_id == template.id for item in plan_items)
    assert all(item.instance_key for item in plan_items)
    assert all(item.canonical_target_id == "PORT_A" for item in plan_items)

    commit = client.post(
        "/api/v1/schedule/commit",
        json={
            "plan_id": payload["plan_id"],
            "workspace_id": workspace_id,
            "lock_level": "none",
        },
    )
    assert commit.status_code == 200, commit.json()

    acquisitions = db.list_acquisitions(workspace_id=workspace_id, limit=10)
    assert [acq.target_id for acq in acquisitions] == [
        f"{template.id}::2026-04-02",
        f"{template.id}::2026-04-03",
    ]
    assert all(acq.order_id for acq in acquisitions)
    assert all(acq.template_id == template.id for acq in acquisitions)
    assert all(acq.instance_key for acq in acquisitions)
    assert all(acq.canonical_target_id == "PORT_A" for acq in acquisitions)


def test_scheduler_runs_on_materialized_instances_without_algorithm_changes(
    isolated_recurring_planning_api: Tuple[TestClient, ScheduleDB, str],
) -> None:
    client, db, workspace_id = isolated_recurring_planning_api
    template = _create_template(
        db,
        workspace_id,
        effective_end_date="2026-04-03",
    )
    base_start = datetime(2026, 4, 2, 9, 30, tzinfo=timezone.utc)
    original_state = _snapshot_analysis_state()
    set_current_mission_data(
        {
            "passes": [
                {
                    "satellite_name": "SAT-1",
                    "target_name": "PORT_A",
                    "start_time": _state_iso(base_start),
                    "end_time": _state_iso(base_start),
                    "max_elevation_time": _state_iso(base_start),
                    "max_elevation": 40.0,
                    "start_azimuth": 180.0,
                },
                {
                    "satellite_name": "SAT-1",
                    "target_name": "PORT_A",
                    "start_time": _state_iso(base_start + timedelta(days=1)),
                    "end_time": _state_iso(base_start + timedelta(days=1)),
                    "max_elevation_time": _state_iso(base_start + timedelta(days=1)),
                    "max_elevation": 42.0,
                    "start_azimuth": 182.0,
                },
            ],
            "targets": [
                TargetData(name="PORT_A", latitude=29.3772, longitude=47.9906, priority=2)
            ],
            "mission_data": {
                "start_time": _state_iso(base_start - timedelta(hours=1)),
                "end_time": _state_iso(base_start + timedelta(days=1, hours=2)),
                "max_spacecraft_pitch_deg": 45.0,
            },
            "satellites_dict": {},
        },
        workspace_id,
    )

    try:
        response = client.post(
            "/api/v1/planning/schedule",
            json={
                "algorithms": ["roll_pitch_best_fit"],
                "mode": "from_scratch",
                "workspace_id": workspace_id,
            },
        )
    finally:
        _restore_analysis_state(original_state)

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["success"] is True
    schedule = payload["results"]["roll_pitch_best_fit"]["schedule"]
    assert [item["target_id"] for item in schedule] == [
        f"{template.id}::2026-04-02",
        f"{template.id}::2026-04-03",
    ]
    assert all(item["template_id"] == template.id for item in schedule)
    assert all(item["instance_key"] in {"2026-04-02", "2026-04-03"} for item in schedule)
    assert all(item["canonical_target_id"] == "PORT_A" for item in schedule)
