"""Coverage for recurring order template + lineage persistence foundation."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Generator, Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.order_templates import router as order_templates_router
from backend.routers.orders import router as orders_router
from backend.schedule_persistence import (
    ScheduleDB,
    get_schedule_db,
    reset_schedule_db,
)
from backend.workspace_persistence import get_workspace_db, reset_workspace_db


@pytest.fixture
def isolated_order_api() -> Generator[Tuple[TestClient, ScheduleDB, str], None, None]:
    """Run order/template tests against a temporary shared workspace DB."""
    original_schedule_path = get_schedule_db().db_path
    original_workspace_path = get_workspace_db().db_path

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    reset_schedule_db(db_path)
    reset_workspace_db(db_path)

    db = get_schedule_db()
    workspace_id = get_workspace_db().create_workspace(
        name="Recurring Lineage Workspace",
        mission_mode="OPTICAL",
    )

    test_app = FastAPI()
    test_app.include_router(order_templates_router)
    test_app.include_router(orders_router)

    with TestClient(test_app) as client:
        yield client, db, workspace_id

    reset_schedule_db(original_schedule_path)
    reset_workspace_db(original_workspace_path)
    if db_path.exists():
        os.unlink(db_path)


def _template_payload(workspace_id: str) -> dict:
    return {
        "workspace_id": workspace_id,
        "name": "Daily Port Collect",
        "status": "active",
        "canonical_target_id": "PORT_A",
        "target_lat": 29.3772,
        "target_lon": 47.9906,
        "priority": 2,
        "constraints": {"max_incidence_deg": 30},
        "requested_satellite_group": "group-alpha",
        "recurrence_type": "daily",
        "interval": 1,
        "days_of_week": None,
        "window_start_hhmm": "15:00",
        "window_end_hhmm": "17:00",
        "timezone_name": "Asia/Dubai",
        "effective_start_date": "2026-04-01",
        "effective_end_date": "2026-06-30",
        "notes": "Primary daily port collect",
        "external_ref": "EXT-RO-1",
    }


def test_order_template_crud_and_order_instance_api(
    isolated_order_api: Tuple[TestClient, ScheduleDB, str],
) -> None:
    client, _db, workspace_id = isolated_order_api

    create_response = client.post(
        "/api/v1/order-templates",
        json=_template_payload(workspace_id),
    )
    assert create_response.status_code == 200
    created_template = create_response.json()["template"]
    template_id = created_template["id"]
    assert created_template["workspace_id"] == workspace_id
    assert created_template["recurrence_type"] == "daily"
    assert created_template["days_of_week"] is None

    list_response = client.get(
        "/api/v1/order-templates",
        params={"workspace_id": workspace_id},
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    get_response = client.get(f"/api/v1/order-templates/{template_id}")
    assert get_response.status_code == 200
    assert get_response.json()["template"]["canonical_target_id"] == "PORT_A"

    patch_response = client.patch(
        f"/api/v1/order-templates/{template_id}",
        json={"status": "paused", "notes": "Paused for review"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["template"]["status"] == "paused"
    assert patch_response.json()["template"]["notes"] == "Paused for review"

    one_time_order = client.post(
        "/api/v1/orders",
        json={
            "target_id": "ONE_OFF_TARGET",
            "workspace_id": workspace_id,
            "priority": 3,
        },
    )
    assert one_time_order.status_code == 200
    one_time_payload = one_time_order.json()["order"]
    assert one_time_payload["template_id"] is None
    assert one_time_payload["planner_target_id"] == "ONE_OFF_TARGET"
    assert one_time_payload["canonical_target_id"] == "ONE_OFF_TARGET"

    recurring_order_base = {
        "workspace_id": workspace_id,
        "target_id": "planner::PORT_A::2026-04-02",
        "template_id": template_id,
        "instance_key": "PORT_A:2026-04-02",
        "instance_local_date": "2026-04-02",
        "planner_target_id": "planner::PORT_A::2026-04-02",
        "canonical_target_id": "PORT_A",
        "target_lat": 29.3772,
        "target_lon": 47.9906,
    }

    first_instance = client.post("/api/v1/orders", json=recurring_order_base)
    assert first_instance.status_code == 200
    first_payload = first_instance.json()["order"]
    assert first_payload["template_id"] == template_id
    assert first_payload["instance_key"] == "PORT_A:2026-04-02"
    assert first_payload["planner_target_id"] == "planner::PORT_A::2026-04-02"
    assert first_payload["canonical_target_id"] == "PORT_A"

    second_instance = client.post(
        "/api/v1/orders",
        json={
            **recurring_order_base,
            "target_id": "planner::PORT_A::2026-04-03",
            "instance_key": "PORT_A:2026-04-03",
            "instance_local_date": "2026-04-03",
            "planner_target_id": "planner::PORT_A::2026-04-03",
        },
    )
    assert second_instance.status_code == 200

    duplicate_instance = client.post("/api/v1/orders", json=recurring_order_base)
    assert duplicate_instance.status_code == 409
    assert "template_id + instance_key" in duplicate_instance.json()["detail"]

    linked_delete = client.delete(f"/api/v1/order-templates/{template_id}")
    assert linked_delete.status_code == 409

    disposable_template = client.post(
        "/api/v1/order-templates",
        json={**_template_payload(workspace_id), "name": "Disposable Template"},
    )
    assert disposable_template.status_code == 200
    disposable_id = disposable_template.json()["template"]["id"]

    delete_response = client.delete(f"/api/v1/order-templates/{disposable_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["template_deleted"] is True


def test_lineage_persists_through_plan_items_commit_and_snapshot_rollback(
    isolated_order_api: Tuple[TestClient, ScheduleDB, str],
) -> None:
    _client, db, workspace_id = isolated_order_api

    template = db.create_order_template(
        workspace_id=workspace_id,
        name="Daily Port Collect",
        canonical_target_id="PORT_A",
        target_lat=29.3772,
        target_lon=47.9906,
        priority=2,
        recurrence_type="daily",
        interval=1,
        window_start_hhmm="15:00",
        window_end_hhmm="17:00",
        timezone_name="Asia/Dubai",
        effective_start_date="2026-04-01",
    )

    order = db.create_order(
        target_id="planner::PORT_A::2026-04-02",
        workspace_id=workspace_id,
        template_id=template.id,
        instance_key="PORT_A:2026-04-02",
        instance_local_date="2026-04-02",
        planner_target_id="planner::PORT_A::2026-04-02",
        canonical_target_id="PORT_A",
        target_lat=29.3772,
        target_lon=47.9906,
    )

    plan = db.create_plan(
        algorithm="roll_pitch_best_fit",
        config={"planning_mode": "from_scratch"},
        input_hash="sha256:recurring-lineage",
        run_id="run_recurring_lineage",
        metrics={},
        workspace_id=workspace_id,
    )
    db.create_plan_item(
        plan_id=plan.id,
        opportunity_id="opp_recurring_1",
        satellite_id="sat-1",
        target_id="planner::PORT_A::2026-04-02",
        start_time="2026-04-02T12:00:00Z",
        end_time="2026-04-02T12:02:00Z",
        roll_angle_deg=4.0,
        pitch_angle_deg=1.0,
        value=1.0,
        quality_score=0.9,
        order_id=order.id,
    )

    persisted_plan_item = db.get_plan_items(plan.id)[0]
    assert persisted_plan_item.order_id == order.id
    assert persisted_plan_item.template_id == template.id
    assert persisted_plan_item.instance_key == "PORT_A:2026-04-02"
    assert persisted_plan_item.canonical_target_id == "PORT_A"
    assert persisted_plan_item.display_target_name == "PORT_A"

    commit_result = db.commit_plan(plan.id, [], workspace_id=workspace_id)
    assert commit_result["committed"] == 1

    committed_acquisition = db.get_acquisition(
        commit_result["acquisitions_created"][0]["id"]
    )
    assert committed_acquisition is not None
    assert committed_acquisition.order_id == order.id
    assert committed_acquisition.template_id == template.id
    assert committed_acquisition.instance_key == "PORT_A:2026-04-02"
    assert committed_acquisition.canonical_target_id == "PORT_A"
    assert committed_acquisition.display_target_name == "PORT_A"
    assert committed_acquisition.target_lat == pytest.approx(29.3772)
    assert committed_acquisition.target_lon == pytest.approx(47.9906)

    with db._get_connection() as conn:
        cursor = conn.cursor()
        snapshot_id = db._create_snapshot(
            cursor,
            workspace_id,
            plan.id,
            description="Lineage preservation snapshot",
        )
        conn.commit()

    db.create_acquisition(
        satellite_id="sat-2",
        target_id="planner::PORT_A::2026-04-03",
        start_time="2026-04-03T12:00:00Z",
        end_time="2026-04-03T12:02:00Z",
        roll_angle_deg=6.0,
        workspace_id=workspace_id,
        order_id=order.id,
        template_id=template.id,
        instance_key="PORT_A:2026-04-03",
        canonical_target_id="PORT_A",
        display_target_name="PORT_A",
        target_lat=29.3772,
        target_lon=47.9906,
    )

    rollback_result = db.rollback_to_snapshot(snapshot_id, workspace_id)
    assert rollback_result["restored"] == 1

    restored_acquisitions = db.list_acquisitions(
        workspace_id=workspace_id,
        include_tentative=True,
        include_failed=True,
    )
    assert len(restored_acquisitions) == 1
    restored = restored_acquisitions[0]
    assert restored.id == committed_acquisition.id
    assert restored.template_id == template.id
    assert restored.instance_key == "PORT_A:2026-04-02"
    assert restored.canonical_target_id == "PORT_A"
    assert restored.display_target_name == "PORT_A"

    with pytest.raises(sqlite3.IntegrityError):
        db.create_order(
            target_id="planner::PORT_A::2026-04-02-dup",
            workspace_id=workspace_id,
            template_id=template.id,
            instance_key="PORT_A:2026-04-02",
            instance_local_date="2026-04-02",
            planner_target_id="planner::PORT_A::2026-04-02-dup",
            canonical_target_id="PORT_A",
            target_lat=29.3772,
            target_lon=47.9906,
        )

