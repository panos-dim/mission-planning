from datetime import datetime, timezone

from backend.planning_demands import build_planning_demand_contract
from backend.schemas.mission import (
    RunOrderRecurrenceRequest,
    RunOrderRequest,
    RunOrderTargetBinding,
)
from backend.schemas.target import TargetData


def _target(name: str, *, priority: int = 1) -> TargetData:
    return TargetData(name=name, latitude=24.5, longitude=54.3, priority=priority)


def test_builds_one_time_demand_summary() -> None:
    horizon_start = datetime(2026, 4, 2, 0, 0, tzinfo=timezone.utc)
    horizon_end = datetime(2026, 4, 3, 0, 0, tzinfo=timezone.utc)
    run_order = RunOrderRequest(
        id="order-1",
        name="Order 1",
        order_type="one_time",
        targets=[
            RunOrderTargetBinding(
                canonical_target_id="Alpha",
                display_target_name="Alpha",
            )
        ],
    )
    passes = [
        {
            "target": "Alpha",
            "start_time": "2026-04-02T09:00:00Z",
            "end_time": "2026-04-02T09:05:00Z",
            "max_elevation": 47,
        },
        {
            "target": "Alpha",
            "start_time": "2026-04-02T11:00:00Z",
            "end_time": "2026-04-02T11:05:00Z",
            "max_elevation": 61,
        },
    ]

    run_order_summary, planning_demands, aggregate = build_planning_demand_contract(
        run_order=run_order,
        targets=[_target("Alpha")],
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        passes=passes,
    )

    assert run_order_summary.planning_demand_count == 1
    assert aggregate.total_demands == 1
    assert aggregate.feasible_demands == 1
    assert planning_demands[0].demand_type == "one_time"
    assert planning_demands[0].matching_pass_indexes == [0, 1]
    assert planning_demands[0].matching_pass_count == 2
    assert planning_demands[0].best_pass_index == 1
    assert planning_demands[0].best_max_elevation == 61
    assert planning_demands[0].requested_window_start == "2026-04-02T00:00:00Z"
    assert planning_demands[0].requested_window_end == "2026-04-03T00:00:00Z"


def test_materializes_recurring_instance_demands_with_window_filtering() -> None:
    horizon_start = datetime(2026, 4, 2, 0, 0, tzinfo=timezone.utc)
    horizon_end = datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc)
    run_order = RunOrderRequest(
        id="order-2",
        name="Recurring Order",
        order_type="repeats",
        targets=[
            RunOrderTargetBinding(
                canonical_target_id="Port Alpha",
                display_target_name="Port Alpha",
                template_id="tmpl-1",
            )
        ],
        recurrence=RunOrderRecurrenceRequest(
            recurrence_type="daily",
            interval=1,
            days_of_week=None,
            window_start_hhmm="09:00",
            window_end_hhmm="11:00",
            timezone_name="UTC",
            effective_start_date="2026-04-02",
            effective_end_date="2026-04-04",
        ),
    )
    passes = [
        {
            "target": "Port Alpha",
            "start_time": "2026-04-02T09:30:00Z",
            "end_time": "2026-04-02T09:35:00Z",
            "max_elevation": 44,
        },
        {
            "target": "Port Alpha",
            "start_time": "2026-04-02T13:00:00Z",
            "end_time": "2026-04-02T13:05:00Z",
            "max_elevation": 60,
        },
        {
            "target": "Port Alpha",
            "start_time": "2026-04-03T10:00:00Z",
            "end_time": "2026-04-03T10:05:00Z",
            "max_elevation": 58,
        },
    ]

    _, planning_demands, aggregate = build_planning_demand_contract(
        run_order=run_order,
        targets=[_target("Port Alpha")],
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        passes=passes,
    )

    assert len(planning_demands) == 3
    assert aggregate.total_demands == 3
    assert aggregate.recurring_instance_demands == 3
    assert aggregate.feasible_demands == 2
    assert planning_demands[0].local_date == "2026-04-02"
    assert planning_demands[0].matching_pass_indexes == [0]
    assert planning_demands[0].template_id == "tmpl-1"
    assert planning_demands[1].local_date == "2026-04-03"
    assert planning_demands[1].matching_pass_indexes == [2]
    assert planning_demands[2].local_date == "2026-04-04"
    assert planning_demands[2].feasibility_status == "no_opportunity"
    assert planning_demands[2].matching_pass_indexes == []
