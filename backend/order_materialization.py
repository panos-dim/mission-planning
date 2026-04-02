"""Recurring order horizon materialization and planner-input assembly."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from backend.schedule_persistence import Order, OrderTemplate, ScheduleDB
from backend.time_windows import get_time_zone, parse_hhmm_time

logger = logging.getLogger(__name__)

_TERMINAL_ORDER_STATUSES = {
    "cancelled",
    "committed",
    "completed",
    "expired",
    "failed",
    "rejected",
}
_WEEKDAY_INDEX = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


@dataclass
class MaterializationSummary:
    """Counts and scope for one horizon materialization run."""

    templates_considered: int = 0
    created_instances: int = 0
    reused_instances: int = 0
    total_instances: int = 0
    managed_canonical_target_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a response-safe summary."""
        return {
            "templates_considered": self.templates_considered,
            "created_instances": self.created_instances,
            "reused_instances": self.reused_instances,
            "total_instances": self.total_instances,
            "managed_canonical_target_ids": list(self.managed_canonical_target_ids),
        }


@dataclass
class RecurringPlanningBundle:
    """Planner-facing recurring-order preparation output."""

    opportunities: List[Any]
    target_positions: Dict[str, Tuple[float, float]]
    lineage_by_opportunity_id: Dict[str, Dict[str, Any]]
    recurring_orders: List[Order]
    materialization: MaterializationSummary


def _ensure_utc(value: datetime) -> datetime:
    """Normalize datetimes to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_datetime(value: Any) -> datetime:
    """Parse ISO datetimes while preserving UTC semantics."""
    if isinstance(value, datetime):
        return _ensure_utc(value)

    text = str(value)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return _ensure_utc(parsed)


def _isoformat_z(value: datetime) -> str:
    """Format datetimes with a single trailing Z."""
    return _ensure_utc(value).isoformat().replace("+00:00", "Z")


def _parse_days_of_week(value: Optional[str]) -> List[str]:
    """Parse template weekday JSON into normalized weekday tokens."""
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    normalized: List[str] = []
    for item in parsed:
        day = str(item).strip().lower()
        if day in _WEEKDAY_INDEX and day not in normalized:
            normalized.append(day)
    return normalized


def _iter_local_dates(start_date: date, end_date: date) -> Iterable[date]:
    """Yield each local date in an inclusive range."""
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _start_of_week(value: date) -> date:
    """Return the Monday-anchored week start for interval calculations."""
    return value - timedelta(days=value.weekday())


def _matches_recurrence(template: OrderTemplate, local_date: date) -> bool:
    """Check whether a local date produces an instance for this template."""
    start_date = date.fromisoformat(template.effective_start_date)
    if local_date < start_date:
        return False

    if template.effective_end_date:
        end_date = date.fromisoformat(template.effective_end_date)
        if local_date > end_date:
            return False

    interval = max(1, int(template.interval))
    if template.recurrence_type == "daily":
        return (local_date - start_date).days % interval == 0

    if template.recurrence_type == "weekly":
        days_of_week = _parse_days_of_week(template.days_of_week_json)
        if not days_of_week:
            return False
        local_week = _start_of_week(local_date)
        start_week = _start_of_week(start_date)
        weeks_since_start = (local_week - start_week).days // 7
        return (
            weeks_since_start >= 0
            and weeks_since_start % interval == 0
            and local_date.weekday() in {_WEEKDAY_INDEX[day] for day in days_of_week}
        )

    return False


def _build_instance_window(template: OrderTemplate, local_date: date) -> tuple[datetime, datetime]:
    """Expand a template occurrence into UTC requested-window bounds."""
    template_tz = get_time_zone(template.timezone_name)
    start_time = parse_hhmm_time(template.window_start_hhmm)
    end_time = parse_hhmm_time(template.window_end_hhmm)

    local_start = datetime.combine(local_date, start_time, tzinfo=template_tz)
    local_end_date = local_date
    if start_time >= end_time:
        local_end_date = local_date + timedelta(days=1)
    local_end = datetime.combine(local_end_date, end_time, tzinfo=template_tz)

    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


def _overlaps(
    start_a: datetime,
    end_a: datetime,
    start_b: datetime,
    end_b: datetime,
) -> bool:
    """Return true when two UTC windows intersect."""
    return start_a < end_b and end_a > start_b


def _instance_key(local_date: date) -> str:
    """Build the deterministic occurrence key used for idempotent inserts."""
    return local_date.isoformat()


def _planner_target_id(template_id: str, local_date: date) -> str:
    """Build the scheduler-visible identity for one dated instance."""
    return f"{template_id}::{local_date.isoformat()}"


def materialize_recurring_orders_for_horizon(
    db: ScheduleDB,
    *,
    workspace_id: Optional[str],
    horizon_start: datetime,
    horizon_end: datetime,
) -> tuple[List[Order], MaterializationSummary]:
    """Create all missing recurring instances intersecting the active horizon."""
    summary = MaterializationSummary()
    effective_workspace_id = workspace_id or "default"
    horizon_start_utc = _ensure_utc(horizon_start)
    horizon_end_utc = _ensure_utc(horizon_end)

    templates = db.list_order_templates(
        workspace_id=effective_workspace_id,
        status="active",
        limit=10_000,
    )
    summary.templates_considered = len(templates)

    recurring_orders: List[Order] = []
    managed_targets: set[str] = set()

    for template in templates:
        template_tz = get_time_zone(template.timezone_name)
        local_range_start = horizon_start_utc.astimezone(template_tz).date() - timedelta(
            days=1
        )
        local_range_end = horizon_end_utc.astimezone(template_tz).date() + timedelta(
            days=1
        )
        template_start = date.fromisoformat(template.effective_start_date)
        template_end = (
            date.fromisoformat(template.effective_end_date)
            if template.effective_end_date
            else local_range_end
        )

        scan_start = max(local_range_start, template_start)
        scan_end = min(local_range_end, template_end)
        if scan_end < scan_start:
            continue

        for local_date in _iter_local_dates(scan_start, scan_end):
            if not _matches_recurrence(template, local_date):
                continue

            window_start_utc, window_end_utc = _build_instance_window(
                template,
                local_date,
            )
            if not _overlaps(
                window_start_utc,
                window_end_utc,
                horizon_start_utc,
                horizon_end_utc,
            ):
                continue

            order, created_now = db.get_or_create_materialized_order(
                workspace_id=effective_workspace_id,
                template_id=template.id,
                instance_key=_instance_key(local_date),
                instance_local_date=local_date.isoformat(),
                planner_target_id=_planner_target_id(template.id, local_date),
                canonical_target_id=template.canonical_target_id,
                target_lat=template.target_lat,
                target_lon=template.target_lon,
                priority=template.priority,
                requested_window_start=_isoformat_z(window_start_utc),
                requested_window_end=_isoformat_z(window_end_utc),
                constraints=_parse_template_constraints(template.constraints_json),
                requested_satellite_group=template.requested_satellite_group,
                notes=template.notes,
                external_ref=template.external_ref,
            )
            recurring_orders.append(order)
            managed_targets.add(order.canonical_target_id or order.target_id)
            if created_now:
                summary.created_instances += 1
            else:
                summary.reused_instances += 1

    summary.total_instances = len(recurring_orders)
    summary.managed_canonical_target_ids = sorted(managed_targets)
    return recurring_orders, summary


def _parse_template_constraints(value: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse stored template constraints JSON into a dictionary."""
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _opportunity_get(opp: Any, key: str, default: Any = None) -> Any:
    """Read a field from dict or object opportunities."""
    if isinstance(opp, dict):
        return opp.get(key, default)
    return getattr(opp, key, default)


def _opportunity_identifier(opp: Any) -> str:
    """Get a stable opportunity identifier."""
    identifier = _opportunity_get(opp, "id")
    if identifier:
        return str(identifier)
    identifier = _opportunity_get(opp, "opportunity_id")
    if identifier:
        return str(identifier)
    start_time = _opportunity_get(opp, "start_time", "")
    satellite_id = _opportunity_get(opp, "satellite_id", "sat")
    target_id = _opportunity_get(opp, "target_id", "target")
    return f"{satellite_id}::{target_id}::{start_time}"


def _clone_opportunity_for_order(opp: Any, order: Order) -> Any:
    """Clone one canonical opportunity into an instance-scoped planner opportunity."""
    planner_target_id = order.planner_target_id or order.target_id
    canonical_target_id = order.canonical_target_id or order.target_id
    base_identifier = _opportunity_identifier(opp)
    clone_identifier = f"{base_identifier}::{order.instance_key or order.id}"

    if isinstance(opp, dict):
        cloned = dict(opp)
        cloned["id"] = clone_identifier
        cloned["opportunity_id"] = clone_identifier
        cloned["target_id"] = planner_target_id
        cloned["order_id"] = order.id
        cloned["template_id"] = order.template_id
        cloned["instance_key"] = order.instance_key
        cloned["canonical_target_id"] = canonical_target_id
        cloned["display_target_name"] = canonical_target_id
        return cloned

    if is_dataclass(opp):
        payload = asdict(opp)
    else:
        payload = dict(vars(opp))
    payload["id"] = clone_identifier
    payload["target_id"] = planner_target_id
    cloned = type(opp)(**payload)
    setattr(cloned, "order_id", order.id)
    setattr(cloned, "template_id", order.template_id)
    setattr(cloned, "instance_key", order.instance_key)
    setattr(cloned, "canonical_target_id", canonical_target_id)
    setattr(cloned, "display_target_name", canonical_target_id)
    return cloned


def _opportunity_overlaps_order_window(opp: Any, order: Order) -> bool:
    """Check whether a canonical opportunity falls inside one materialized order window."""
    if not order.requested_window_start or not order.requested_window_end:
        return True

    opp_start = _parse_datetime(_opportunity_get(opp, "start_time"))
    opp_end_value = _opportunity_get(opp, "end_time", _opportunity_get(opp, "start_time"))
    opp_end = _parse_datetime(opp_end_value)
    if opp_end < opp_start:
        opp_end = opp_start
    if opp_end == opp_start:
        opp_end = opp_end + timedelta(microseconds=1)

    order_start = _parse_datetime(order.requested_window_start)
    order_end = _parse_datetime(order.requested_window_end)
    return _overlaps(opp_start, opp_end, order_start, order_end)


def prepare_recurring_planner_inputs(
    db: ScheduleDB,
    *,
    workspace_id: Optional[str],
    horizon_start: datetime,
    horizon_end: datetime,
    base_opportunities: List[Any],
    target_positions: Optional[Dict[str, Tuple[float, float]]] = None,
) -> RecurringPlanningBundle:
    """Materialize recurring instances and project them into planner-visible inputs.

    The scheduler keeps operating on ``target_id`` only. For recurring work we
    therefore replace canonical target opportunities with dated instance target
    IDs (`planner_target_id`) while keeping canonical lineage on the side.
    """
    recurring_orders, materialization = materialize_recurring_orders_for_horizon(
        db,
        workspace_id=workspace_id,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
    )

    planner_positions = dict(target_positions or {})
    lineage_by_opportunity_id: Dict[str, Dict[str, Any]] = {}
    managed_targets = set(materialization.managed_canonical_target_ids)
    actionable_orders = [
        order
        for order in recurring_orders
        if (order.template_id and order.status not in _TERMINAL_ORDER_STATUSES)
    ]
    actionable_orders.sort(
        key=lambda order: (
            order.canonical_target_id or order.target_id,
            order.instance_local_date or "",
            order.id,
        )
    )

    orders_by_canonical: Dict[str, List[Order]] = {}
    for order in actionable_orders:
        canonical_target_id = order.canonical_target_id or order.target_id
        orders_by_canonical.setdefault(canonical_target_id, []).append(order)
        if order.target_lat is not None and order.target_lon is not None:
            planner_positions[canonical_target_id] = (order.target_lat, order.target_lon)
            planner_positions[order.planner_target_id or order.target_id] = (
                order.target_lat,
                order.target_lon,
            )

    transformed_opportunities: List[Any] = []
    for opp in base_opportunities:
        canonical_target_id = str(_opportunity_get(opp, "target_id", "") or "")
        recurring_candidates = orders_by_canonical.get(canonical_target_id, [])
        if recurring_candidates:
            for order in recurring_candidates:
                if not _opportunity_overlaps_order_window(opp, order):
                    continue
                cloned = _clone_opportunity_for_order(opp, order)
                transformed_opportunities.append(cloned)
                lineage_by_opportunity_id[_opportunity_identifier(cloned)] = {
                    "order_id": order.id,
                    "template_id": order.template_id,
                    "instance_key": order.instance_key,
                    "canonical_target_id": order.canonical_target_id or order.target_id,
                    "display_target_name": order.canonical_target_id or order.target_id,
                }
            continue

        if canonical_target_id in managed_targets:
            continue
        transformed_opportunities.append(opp)

    if managed_targets:
        logger.info(
            "[Recurring Orders] Prepared %d planner opportunities (%d recurring instances, %d managed canonical targets)",
            len(transformed_opportunities),
            materialization.total_instances,
            len(managed_targets),
        )

    return RecurringPlanningBundle(
        opportunities=transformed_opportunities,
        target_positions=planner_positions,
        lineage_by_opportunity_id=lineage_by_opportunity_id,
        recurring_orders=recurring_orders,
        materialization=materialization,
    )
