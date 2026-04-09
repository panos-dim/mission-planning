"""Demand-aware feasibility contract helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Optional, Sequence

from backend.schemas.mission import (
    PlanningDemandAggregateSummary,
    PlanningDemandSummary,
    RunOrderRecurrenceRequest,
    RunOrderRecurrenceResponse,
    RunOrderRequest,
    RunOrderSummary,
)
from backend.schemas.target import TargetData
from backend.time_windows import get_time_zone, parse_hhmm_time

_LEGACY_RUN_ORDER_ID = "legacy-run-order"
_LEGACY_RUN_ORDER_NAME = "Legacy Run Order"
_ONE_TIME_DEMAND = "one_time"
_RECURRING_INSTANCE_DEMAND = "recurring_instance"


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _isoformat_z(value: datetime) -> str:
    return _ensure_utc(value).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: str) -> datetime:
    return _ensure_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _iter_local_dates(start_date: date, end_date: date) -> Iterable[date]:
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _start_of_week(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _overlaps(
    start_a: datetime,
    end_a: datetime,
    start_b: datetime,
    end_b: datetime,
) -> bool:
    return start_a < end_b and end_a > start_b


def _pass_end(pass_data: dict[str, Any]) -> datetime:
    end_text = str(pass_data.get("end_time") or pass_data.get("start_time") or "")
    end_time = _parse_datetime(end_text)
    start_time = _parse_datetime(str(pass_data.get("start_time") or end_text))
    if end_time <= start_time:
        return start_time + timedelta(microseconds=1)
    return end_time


@dataclass(frozen=True)
class _TargetBinding:
    canonical_target_id: str
    display_target_name: str
    template_id: Optional[str]
    priority: int


@dataclass(frozen=True)
class _NormalizedRunOrder:
    id: str
    name: str
    order_type: str
    recurrence: Optional[RunOrderRecurrenceRequest]
    targets: list[_TargetBinding]


@dataclass(frozen=True)
class _PlanningDemand:
    run_order_id: str
    demand_id: str
    canonical_target_id: str
    display_target_name: str
    demand_type: str
    template_id: Optional[str]
    instance_key: Optional[str]
    requested_window_start: Optional[str]
    requested_window_end: Optional[str]
    local_date: Optional[str]
    priority: int


def _normalize_run_order(
    run_order: Optional[RunOrderRequest],
    targets: Sequence[TargetData],
) -> _NormalizedRunOrder:
    normalized_targets: list[_TargetBinding] = []
    bindings = run_order.targets if run_order else []

    for index, target in enumerate(targets):
        binding = bindings[index] if index < len(bindings) else None
        canonical_target_id = (
            binding.canonical_target_id.strip()
            if binding and binding.canonical_target_id
            else target.name.strip()
        )
        display_target_name = (
            binding.display_target_name.strip()
            if binding and binding.display_target_name
            else target.name.strip()
        )
        normalized_targets.append(
            _TargetBinding(
                canonical_target_id=canonical_target_id,
                display_target_name=display_target_name,
                template_id=binding.template_id if binding else None,
                priority=target.priority if target.priority is not None else 5,
            )
        )

    if run_order is None:
        return _NormalizedRunOrder(
            id=_LEGACY_RUN_ORDER_ID,
            name=_LEGACY_RUN_ORDER_NAME,
            order_type=_ONE_TIME_DEMAND,
            recurrence=None,
            targets=normalized_targets,
        )

    return _NormalizedRunOrder(
        id=run_order.id,
        name=run_order.name,
        order_type=run_order.order_type,
        recurrence=run_order.recurrence,
        targets=normalized_targets,
    )


def _build_recurring_window(
    recurrence: Optional[RunOrderRecurrenceRequest],
    local_date: date,
) -> tuple[datetime, datetime]:
    if recurrence is None:
        raise ValueError("Recurring window requires recurrence configuration")

    recurrence_tz = get_time_zone(recurrence.timezone_name)
    start_time = parse_hhmm_time(recurrence.window_start_hhmm)
    end_time = parse_hhmm_time(recurrence.window_end_hhmm)

    local_start = datetime.combine(local_date, start_time, tzinfo=recurrence_tz)
    local_end_date = local_date
    if start_time >= end_time:
        local_end_date = local_date + timedelta(days=1)
    local_end = datetime.combine(local_end_date, end_time, tzinfo=recurrence_tz)

    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


def _matches_recurrence(
    recurrence: Optional[RunOrderRecurrenceRequest],
    local_date: date,
) -> bool:
    if recurrence is None:
        return False

    start_date = date.fromisoformat(recurrence.effective_start_date)
    if local_date < start_date:
        return False

    if recurrence.effective_end_date:
        end_date = date.fromisoformat(recurrence.effective_end_date)
        if local_date > end_date:
            return False

    interval = max(1, int(recurrence.interval))
    if recurrence.recurrence_type == "daily":
        return (local_date - start_date).days % interval == 0

    if recurrence.recurrence_type == "weekly":
        if not recurrence.days_of_week:
            return False
        weekday_lookup = {
            "mon": 0,
            "tue": 1,
            "wed": 2,
            "thu": 3,
            "fri": 4,
            "sat": 5,
            "sun": 6,
        }
        local_week = _start_of_week(local_date)
        start_week = _start_of_week(start_date)
        weeks_since_start = (local_week - start_week).days // 7
        return (
            weeks_since_start >= 0
            and weeks_since_start % interval == 0
            and local_date.weekday()
            in {weekday_lookup[day] for day in recurrence.days_of_week}
        )

    return False


def _materialize_demands(
    run_order: _NormalizedRunOrder,
    horizon_start: datetime,
    horizon_end: datetime,
) -> list[_PlanningDemand]:
    if run_order.order_type != "repeats" or run_order.recurrence is None:
        window_start = _isoformat_z(horizon_start)
        window_end = _isoformat_z(horizon_end)
        return [
            _PlanningDemand(
                run_order_id=run_order.id,
                demand_id=f"{run_order.id}::one_time::{binding.canonical_target_id}",
                canonical_target_id=binding.canonical_target_id,
                display_target_name=binding.display_target_name,
                demand_type=_ONE_TIME_DEMAND,
                template_id=None,
                instance_key=None,
                requested_window_start=window_start,
                requested_window_end=window_end,
                local_date=None,
                priority=binding.priority,
            )
            for binding in run_order.targets
        ]

    recurrence = run_order.recurrence
    recurrence_tz = get_time_zone(recurrence.timezone_name)
    local_range_start = horizon_start.astimezone(recurrence_tz).date() - timedelta(days=1)
    local_range_end = horizon_end.astimezone(recurrence_tz).date() + timedelta(days=1)
    effective_start = date.fromisoformat(recurrence.effective_start_date)
    effective_end = (
        date.fromisoformat(recurrence.effective_end_date)
        if recurrence.effective_end_date
        else local_range_end
    )
    scan_start = max(local_range_start, effective_start)
    scan_end = min(local_range_end, effective_end)

    demands: list[_PlanningDemand] = []
    if scan_end < scan_start:
        return demands

    for binding in run_order.targets:
        for local_date in _iter_local_dates(scan_start, scan_end):
            if not _matches_recurrence(recurrence, local_date):
                continue

            window_start, window_end = _build_recurring_window(recurrence, local_date)
            if not _overlaps(window_start, window_end, horizon_start, horizon_end):
                continue

            instance_key = local_date.isoformat()
            lineage_source = binding.template_id or binding.canonical_target_id
            demands.append(
                _PlanningDemand(
                    run_order_id=run_order.id,
                    demand_id=f"{run_order.id}::{lineage_source}::{instance_key}",
                    canonical_target_id=binding.canonical_target_id,
                    display_target_name=binding.display_target_name,
                    demand_type=_RECURRING_INSTANCE_DEMAND,
                    template_id=binding.template_id,
                    instance_key=instance_key,
                    requested_window_start=_isoformat_z(window_start),
                    requested_window_end=_isoformat_z(window_end),
                    local_date=instance_key,
                    priority=binding.priority,
                )
            )

    return demands


def _matching_pass_indexes(
    demand: _PlanningDemand,
    passes: Sequence[dict[str, Any]],
) -> list[int]:
    matching_indexes: list[int] = []
    allowed_targets = {
        demand.display_target_name.strip(),
        demand.canonical_target_id.strip(),
    }
    window_start = (
        _parse_datetime(demand.requested_window_start)
        if demand.requested_window_start
        else None
    )
    window_end = (
        _parse_datetime(demand.requested_window_end) if demand.requested_window_end else None
    )

    for index, pass_data in enumerate(passes):
        target_name = str(pass_data.get("target") or "").strip()
        if target_name not in allowed_targets:
            continue

        pass_start = _parse_datetime(str(pass_data.get("start_time") or ""))
        pass_end = _pass_end(pass_data)
        if window_start and window_end and not _overlaps(pass_start, pass_end, window_start, window_end):
            continue
        matching_indexes.append(index)

    return matching_indexes


def _best_pass_index(
    matching_indexes: Sequence[int],
    passes: Sequence[dict[str, Any]],
) -> Optional[int]:
    best_index: Optional[int] = None
    best_elevation = float("-inf")

    for index in matching_indexes:
        max_elevation = float(passes[index].get("max_elevation") or 0.0)
        if max_elevation > best_elevation:
            best_elevation = max_elevation
            best_index = index

    return best_index


def build_planning_demand_contract(
    *,
    run_order: Optional[RunOrderRequest],
    targets: Sequence[TargetData],
    horizon_start: datetime,
    horizon_end: datetime,
    passes: Sequence[dict[str, Any]],
) -> tuple[RunOrderSummary, list[PlanningDemandSummary], PlanningDemandAggregateSummary]:
    """Build additive demand-aware summaries for mission feasibility results."""

    normalized_horizon_start = _ensure_utc(horizon_start)
    normalized_horizon_end = _ensure_utc(horizon_end)
    normalized_run_order = _normalize_run_order(run_order, targets)
    demands = _materialize_demands(
        normalized_run_order,
        normalized_horizon_start,
        normalized_horizon_end,
    )

    planning_demands: list[PlanningDemandSummary] = []
    for demand in demands:
        matching_indexes = _matching_pass_indexes(demand, passes)
        best_index = _best_pass_index(matching_indexes, passes)
        first_pass_start = (
            str(passes[matching_indexes[0]].get("start_time")) if matching_indexes else None
        )
        last_pass_end = (
            str(passes[matching_indexes[-1]].get("end_time")) if matching_indexes else None
        )
        best_pass = passes[best_index] if best_index is not None else None

        planning_demands.append(
            PlanningDemandSummary(
                run_order_id=demand.run_order_id,
                demand_id=demand.demand_id,
                canonical_target_id=demand.canonical_target_id,
                display_target_name=demand.display_target_name,
                demand_type=demand.demand_type,
                template_id=demand.template_id,
                instance_key=demand.instance_key,
                requested_window_start=demand.requested_window_start,
                requested_window_end=demand.requested_window_end,
                local_date=demand.local_date,
                priority=demand.priority,
                feasibility_status=(
                    "feasible" if matching_indexes else "no_opportunity"
                ),
                has_feasible_pass=bool(matching_indexes),
                matching_pass_count=len(matching_indexes),
                matching_pass_indexes=matching_indexes,
                first_pass_start=first_pass_start,
                last_pass_end=last_pass_end,
                best_pass_index=best_index,
                best_pass_start=(
                    str(best_pass.get("start_time")) if best_pass is not None else None
                ),
                best_pass_end=(
                    str(best_pass.get("end_time")) if best_pass is not None else None
                ),
                best_max_elevation=(
                    float(best_pass.get("max_elevation"))
                    if best_pass is not None and best_pass.get("max_elevation") is not None
                    else None
                ),
            )
        )

    recurrence = normalized_run_order.recurrence
    run_order_summary = RunOrderSummary(
        id=normalized_run_order.id,
        name=normalized_run_order.name,
        order_type=(
            "repeats"
            if normalized_run_order.order_type == "repeats" and recurrence is not None
            else "one_time"
        ),
        target_count=len(normalized_run_order.targets),
        planning_demand_count=len(planning_demands),
        recurrence=(
            RunOrderRecurrenceResponse(**recurrence.model_dump())
            if recurrence is not None and normalized_run_order.order_type == "repeats"
            else None
        ),
    )

    feasible_demands = sum(1 for demand in planning_demands if demand.has_feasible_pass)
    aggregate_summary = PlanningDemandAggregateSummary(
        run_order_id=normalized_run_order.id,
        total_demands=len(planning_demands),
        feasible_demands=feasible_demands,
        infeasible_demands=len(planning_demands) - feasible_demands,
        one_time_demands=sum(
            1 for demand in planning_demands if demand.demand_type == _ONE_TIME_DEMAND
        ),
        recurring_instance_demands=sum(
            1
            for demand in planning_demands
            if demand.demand_type == _RECURRING_INSTANCE_DEMAND
        ),
    )

    return run_order_summary, planning_demands, aggregate_summary
