"""Automatic scheduling-mode resolution for planning and repair orchestration.

Architectural rule:
- ``order_templates`` represent recurring business intent.
- ``orders`` represent actionable dated instances.
- ``order_id`` is the dated-instance identity.
- ``template_id`` is the recurring template identity.
- ``planner_target_id`` is the unique scheduler-facing identity for one instance.
- ``canonical_target_id`` is the physical target identity used for grouping.

This module decides whether the scheduling pipeline should behave as:
- ``from_scratch``: no active schedule exists to extend
- ``incremental``: new actionable work exists and the current schedule is safe to extend
- ``repair``: existing schedule state must be corrected or reshuffled
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from backend.schedule_persistence import Order, ScheduleDB
from backend.workspace_persistence import get_workspace_db
from src.mission_planner.quality_scoring import MultiCriteriaWeights

logger = logging.getLogger(__name__)

_TERMINAL_ACQUISITION_STATES = {"failed", "cancelled", "completed"}
_TERMINAL_ORDER_STATUSES = {
    "cancelled",
    "committed",
    "completed",
    "expired",
    "failed",
    "rejected",
}

# ---------------------------------------------------------------------------
# Module-level store for last planning run diagnostics (DEV_MODE only)
# ---------------------------------------------------------------------------

_last_planning_run: Dict[str, Any] = {}


def get_last_planning_run() -> Dict[str, Any]:
    """Return diagnostics from the last planning run (dev-only)."""
    return dict(_last_planning_run)


def clear_last_planning_run() -> None:
    """Clear last planning run diagnostics."""
    _last_planning_run.clear()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def compute_request_hash(payload: Dict[str, Any]) -> str:
    """Compute a deterministic hash of a request payload for audit breadcrumbs."""
    stable = {
        key: value
        for key, value in sorted(payload.items())
        if key not in ("horizon_from", "horizon_to")
    }
    raw = json.dumps(stable, sort_keys=True, default=str)
    return f"sha256:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse an ISO datetime into aware UTC, returning ``None`` on bad input."""
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _to_utc_naive(value: datetime) -> datetime:
    """Normalize a datetime to naive UTC for internal comparisons."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _active_existing_acquisitions(
    db: ScheduleDB,
    *,
    workspace_id: str,
    horizon_start: datetime,
) -> List[Any]:
    """Return active acquisitions that can influence scheduling decisions."""
    try:
        existing_acqs = db.get_acquisitions_by_lock_level(workspace_id)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("[Auto Mode] Failed to query existing acquisitions: %s", exc)
        return []

    normalized_horizon_start = _to_utc_naive(horizon_start)
    active_existing: List[Any] = []
    for acquisition in existing_acqs:
        if acquisition.state in _TERMINAL_ACQUISITION_STATES:
            continue
        acq_end = _parse_datetime(acquisition.end_time)
        if acq_end and _to_utc_naive(acq_end) <= normalized_horizon_start:
            continue
        active_existing.append(acquisition)
    return active_existing


def _load_workspace_target_baseline(workspace_id: Optional[str]) -> set[str]:
    """Load the backend baseline target set used for mode comparisons."""
    if not workspace_id:
        return set()

    previous_target_ids: set[str] = set()
    try:
        workspace = get_workspace_db().get_workspace(workspace_id, include_czml=False)
        if not workspace:
            return previous_target_ids

        planning_state = workspace.planning_state or {}
        stored_target_ids = planning_state.get("current_target_ids", [])
        if isinstance(stored_target_ids, list):
            previous_target_ids = {
                str(target_id) for target_id in stored_target_ids if target_id
            }

        if not previous_target_ids and workspace.scenario_config:
            previous_target_ids = {
                str(target.get("name", ""))
                for target in workspace.scenario_config.get("targets", [])
                if target.get("name")
            }

        if not previous_target_ids and workspace.analysis_state:
            analysis_targets = workspace.analysis_state.get("mission_data", {}).get(
                "targets", []
            )
            previous_target_ids = {
                str(target.get("name", ""))
                for target in analysis_targets
                if isinstance(target, dict) and target.get("name")
            }
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("[Auto Mode] Failed to load workspace target baseline: %s", exc)

    return previous_target_ids


def _build_current_target_ids(
    mission_data: Dict[str, Any],
    raw_opportunities: Sequence[Any],
) -> set[str]:
    """Build the current scheduler-visible target set.

    We intentionally union canonical mission targets with opportunity target IDs
    so recurring instance ``planner_target_id`` values are not lost when the
    mission payload still only lists the canonical target once.
    """

    current_target_ids: set[str] = set()

    for target in mission_data.get("targets", []):
        if isinstance(target, dict):
            target_name = target.get("name", "")
        else:
            target_name = getattr(target, "name", "")
        if target_name:
            current_target_ids.add(str(target_name))

    for opportunity in raw_opportunities:
        if isinstance(opportunity, dict):
            target_id = opportunity.get("target_id", "")
        else:
            target_id = getattr(opportunity, "target_id", "")
        if target_id:
            current_target_ids.add(str(target_id))

    return current_target_ids


def _build_target_priorities(
    mission_data: Dict[str, Any],
    recurring_orders: Sequence[Order],
) -> Dict[str, int]:
    """Build target priorities from mission data plus materialized recurring orders."""
    priorities: Dict[str, int] = {}

    for target in mission_data.get("targets", []):
        if isinstance(target, dict):
            target_name = str(target.get("name", "")).strip()
            priority_raw = target.get("priority", 5)
        else:
            target_name = str(getattr(target, "name", "")).strip()
            priority_raw = getattr(target, "priority", 5)

        if not target_name:
            continue

        try:
            priority = int(priority_raw)
        except (TypeError, ValueError):
            priority = 5
        priorities[target_name] = min(5, max(1, priority))

    for order in recurring_orders:
        planner_target_id = str(order.planner_target_id or order.target_id or "").strip()
        if not planner_target_id:
            continue
        try:
            priority = int(order.priority)
        except (TypeError, ValueError):
            priority = 5
        priorities[planner_target_id] = min(5, max(1, priority))

    return priorities


def _current_actionable_recurring_orders(
    recurring_orders: Sequence[Order],
) -> List[Order]:
    """Filter horizon materialized orders down to actionable recurring instances."""
    actionable: List[Order] = []
    for order in recurring_orders:
        if not order.template_id:
            continue
        if order.status in _TERMINAL_ORDER_STATUSES:
            continue
        actionable.append(order)
    return actionable


def _new_one_time_order_target_ids(
    db: ScheduleDB,
    *,
    workspace_id: str,
    latest_commit_at: Optional[datetime],
    scheduled_target_ids: Set[str],
) -> Set[str]:
    """Return one-time order targets added since the last committed revision."""
    try:
        orders = db.list_orders(workspace_id=workspace_id, limit=10_000)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("[Auto Mode] Failed to query orders: %s", exc)
        return set()

    new_targets: Set[str] = set()
    for order in orders:
        if order.template_id:
            continue
        if order.status in _TERMINAL_ORDER_STATUSES:
            continue
        created_at = _parse_datetime(order.created_at)
        if latest_commit_at and created_at and created_at <= latest_commit_at:
            continue
        target_id = str(order.target_id or "").strip()
        if target_id and target_id not in scheduled_target_ids:
            new_targets.add(target_id)
    return new_targets


def _stale_acquisition_details(
    db: ScheduleDB,
    *,
    active_existing: Sequence[Any],
    current_target_ids: Set[str],
) -> Tuple[Set[str], int]:
    """Identify stale scheduled targets and invalid acquisition lineage rows."""
    removed_scheduled_targets: Set[str] = set()
    invalid_acquisition_count = 0
    order_cache: Dict[str, Optional[Order]] = {}

    for acquisition in active_existing:
        target_id = str(acquisition.target_id or "").strip()
        if target_id and target_id not in current_target_ids:
            removed_scheduled_targets.add(target_id)

        order_id = str(acquisition.order_id or "").strip()
        if not order_id:
            continue
        if order_id not in order_cache:
            order_cache[order_id] = db.get_order(order_id)
        order = order_cache[order_id]
        if order is None or order.status in _TERMINAL_ORDER_STATUSES:
            invalid_acquisition_count += 1

    return removed_scheduled_targets, invalid_acquisition_count


def _priority_repair_reason(
    *,
    existing_target_ids: Set[str],
    new_target_ids: Set[str],
    target_priorities: Dict[str, int],
    weight_priority: float,
    weight_geometry: float,
    weight_timing: float,
) -> Optional[str]:
    """Return a repair reason when priority-weighted reshuffling is warranted."""
    if not new_target_ids:
        return None

    existing_target_priorities = [
        target_priorities[target_id]
        for target_id in existing_target_ids
        if target_id in target_priorities and isinstance(target_priorities[target_id], int)
    ]
    new_target_priorities = [
        target_priorities[target_id]
        for target_id in new_target_ids
        if target_id in target_priorities and isinstance(target_priorities[target_id], int)
    ]

    best_existing_priority = (
        min(existing_target_priorities) if existing_target_priorities else None
    )
    best_new_priority = min(new_target_priorities) if new_target_priorities else None
    if best_existing_priority is None or best_new_priority is None:
        return None

    weights = MultiCriteriaWeights(
        priority=weight_priority,
        geometry=weight_geometry,
        timing=weight_timing,
    )
    priority_gap = best_existing_priority - best_new_priority
    priority_uplift = weights.norm_priority * max(priority_gap, 0) / 4.0
    if best_new_priority < best_existing_priority and priority_uplift >= 0.25:
        return (
            f"{len(new_target_ids)} new target(s) detected "
            f"({', '.join(sorted(new_target_ids)[:5])}) and they include higher-priority work "
            f"(best new P{best_new_priority} vs existing best P{best_existing_priority}, "
            f"priority weight {weights.norm_priority:.0%}). "
            "Repairing the current schedule to allow weight-aware reshuffling."
        )
    return None


# ---------------------------------------------------------------------------
# Audit breadcrumbs — dev-only instrumentation
# ---------------------------------------------------------------------------


@dataclass
class AuditBreadcrumb:
    """Single breadcrumb in the scheduling pipeline audit trail."""

    stage: str
    timestamp: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "timestamp": self.timestamp,
            "data": self.data,
        }


class PipelineAuditTrail:
    """Collect breadcrumbs throughout a single scheduling pipeline run."""

    def __init__(self, run_id: str, workspace_id: str):
        self.run_id = run_id
        self.workspace_id = workspace_id
        self.breadcrumbs: List[AuditBreadcrumb] = []
        self.started_at = datetime.now(timezone.utc).isoformat() + "Z"

    def add(self, stage: str, **data: Any) -> None:
        crumb = AuditBreadcrumb(
            stage=stage,
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            data=data,
        )
        self.breadcrumbs.append(crumb)
        logger.debug(
            "[Audit Trail] run=%s stage=%s data=%s",
            self.run_id,
            stage,
            json.dumps(data, default=str)[:400],
        )

    def finalize(self) -> Dict[str, Any]:
        trail = {
            "run_id": self.run_id,
            "workspace_id": self.workspace_id,
            "started_at": self.started_at,
            "completed_at": datetime.now(timezone.utc).isoformat() + "Z",
            "breadcrumb_count": len(self.breadcrumbs),
            "breadcrumbs": [breadcrumb.to_dict() for breadcrumb in self.breadcrumbs],
        }
        _last_planning_run.clear()
        _last_planning_run.update(trail)
        return trail


def record_schedule_diff(
    trail: PipelineAuditTrail,
    acq_ids_before: List[str],
    acq_ids_after: List[str],
) -> Dict[str, Any]:
    """Record acquisition ID diff between schedule revisions."""
    before_set = set(acq_ids_before)
    after_set = set(acq_ids_after)
    diff = {
        "kept": sorted(before_set & after_set),
        "added": sorted(after_set - before_set),
        "removed": sorted(before_set - after_set),
        "kept_count": len(before_set & after_set),
        "added_count": len(after_set - before_set),
        "removed_count": len(before_set - after_set),
    }
    trail.add(
        "schedule_diff",
        acq_ids_before_count=len(acq_ids_before),
        acq_ids_after_count=len(acq_ids_after),
        **{key: value for key, value in diff.items() if key.endswith("_count")},
    )
    return diff


# ---------------------------------------------------------------------------
# Scheduling mode result
# ---------------------------------------------------------------------------


@dataclass
class ModeSelectionResult:
    """Resolved planning mode plus explicit audit context."""

    mode: str
    reason: str
    workspace_id: str
    previous_schedule_revision_id: int = 1
    existing_acquisition_count: int = 0
    existing_committed_acquisition_count: int = 0
    current_materialized_instance_count: int = 0
    outstanding_instance_count: int = 0
    new_instance_count: int = 0
    new_target_count: int = 0
    new_one_time_order_count: int = 0
    removed_scheduled_target_count: int = 0
    stale_acquisition_count: int = 0
    conflict_count: int = 0
    request_payload_hash: str = ""
    fallback_from_mode: Optional[str] = None
    existing_target_ids: Set[str] = field(default_factory=set)
    current_target_ids: Set[str] = field(default_factory=set)
    new_target_ids: Set[str] = field(default_factory=set)

    def to_log_dict(self) -> Dict[str, Any]:
        """Structured audit/log payload for a mode decision."""
        return {
            "chosen_mode": self.mode,
            "reason": self.reason,
            "workspace_id": self.workspace_id,
            "previous_schedule_revision_id": self.previous_schedule_revision_id,
            "existing_committed_acquisition_count": self.existing_committed_acquisition_count,
            "current_materialized_instance_count": self.current_materialized_instance_count,
            "outstanding_instance_count": self.outstanding_instance_count,
            "new_instance_count": self.new_instance_count,
            "new_target_count": self.new_target_count,
            "new_one_time_order_count": self.new_one_time_order_count,
            "removed_scheduled_target_count": self.removed_scheduled_target_count,
            "stale_acquisition_count": self.stale_acquisition_count,
            "conflict_count": self.conflict_count,
            "fallback_from_mode": self.fallback_from_mode,
            "request_payload_hash": self.request_payload_hash,
        }


def resolve_scheduling_mode(
    db: ScheduleDB,
    *,
    workspace_id: Optional[str],
    horizon_start: datetime,
    horizon_end: datetime,
    mission_data: Dict[str, Any],
    raw_opportunities: Sequence[Any],
    recurring_orders: Optional[Sequence[Order]] = None,
    request_payload_hash: str = "",
    weight_priority: float = 40.0,
    weight_geometry: float = 40.0,
    weight_timing: float = 20.0,
    force_mode: Optional[str] = None,
) -> tuple[ModeSelectionResult, Dict[str, Any]]:
    """Resolve the internal scheduling mode for one planning horizon."""
    auto_workspace = workspace_id or "default"
    recurring_orders = list(recurring_orders or [])
    actionable_recurring_orders = _current_actionable_recurring_orders(recurring_orders)
    active_existing = _active_existing_acquisitions(
        db,
        workspace_id=auto_workspace,
        horizon_start=horizon_start,
    )

    current_target_ids = _build_current_target_ids(mission_data, raw_opportunities)
    scheduled_target_ids = {
        str(acquisition.target_id)
        for acquisition in active_existing
        if acquisition.target_id
    }
    previous_target_ids = _load_workspace_target_baseline(workspace_id)
    existing_target_ids = previous_target_ids | scheduled_target_ids

    latest_commit = db.get_latest_commit_audit_log(auto_workspace)
    latest_commit_at = _parse_datetime(latest_commit.created_at) if latest_commit else None
    previous_revision_id = db.get_schedule_revision(auto_workspace)

    recurring_target_ids = {
        str(order.planner_target_id or order.target_id)
        for order in actionable_recurring_orders
        if (order.planner_target_id or order.target_id)
    }
    managed_recurring_canonical_target_ids = {
        str(order.canonical_target_id or order.target_id)
        for order in actionable_recurring_orders
        if (order.canonical_target_id or order.target_id)
    }
    outstanding_recurring_orders = [
        order
        for order in actionable_recurring_orders
        if str(order.planner_target_id or order.target_id) not in scheduled_target_ids
    ]
    new_recurring_orders_since_revision = [
        order
        for order in outstanding_recurring_orders
        if latest_commit_at is None
        or (
            _parse_datetime(order.created_at) is not None
            and _parse_datetime(order.created_at) > latest_commit_at
        )
    ]

    new_one_time_order_target_ids = _new_one_time_order_target_ids(
        db,
        workspace_id=auto_workspace,
        latest_commit_at=latest_commit_at,
        scheduled_target_ids=scheduled_target_ids,
    )
    new_target_ids = (
        current_target_ids
        - existing_target_ids
        - recurring_target_ids
        - managed_recurring_canonical_target_ids
    ) | new_one_time_order_target_ids

    removed_scheduled_targets, invalid_acquisition_count = _stale_acquisition_details(
        db,
        active_existing=active_existing,
        current_target_ids=current_target_ids,
    )

    conflict_count = 0
    if active_existing:
        try:
            conflicts = db.get_conflicts_in_horizon(
                start_time=horizon_start.replace(tzinfo=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                end_time=horizon_end.replace(tzinfo=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                workspace_id=auto_workspace,
                include_resolved=False,
            )
            conflict_count = len(conflicts)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("[Auto Mode] Failed to query conflicts: %s", exc)

    result = ModeSelectionResult(
        mode="from_scratch",
        reason="",
        workspace_id=auto_workspace,
        previous_schedule_revision_id=previous_revision_id,
        existing_acquisition_count=len(active_existing),
        existing_committed_acquisition_count=len(active_existing),
        current_materialized_instance_count=len(actionable_recurring_orders),
        outstanding_instance_count=len(outstanding_recurring_orders),
        new_instance_count=len(new_recurring_orders_since_revision),
        new_target_count=len(new_target_ids),
        new_one_time_order_count=len(new_one_time_order_target_ids),
        removed_scheduled_target_count=len(removed_scheduled_targets),
        stale_acquisition_count=len(removed_scheduled_targets) + invalid_acquisition_count,
        conflict_count=conflict_count,
        request_payload_hash=request_payload_hash,
        existing_target_ids=existing_target_ids,
        current_target_ids=current_target_ids,
        new_target_ids=new_target_ids,
    )

    if force_mode and force_mode in {"from_scratch", "incremental", "repair"}:
        result.mode = force_mode
        result.reason = f"Explicitly requested mode: {force_mode}"
        _log_mode_selection(result)
        return result, {
            "workspace_id": auto_workspace,
            "existing_acquisition_count": len(active_existing),
            "existing_committed_acquisition_count": len(active_existing),
            "current_target_ids": sorted(current_target_ids),
            "existing_target_ids": sorted(existing_target_ids),
            "scheduled_target_ids": sorted(scheduled_target_ids),
            "current_materialized_instance_count": len(actionable_recurring_orders),
            "outstanding_instance_count": len(outstanding_recurring_orders),
            "new_instance_count": len(new_recurring_orders_since_revision),
            "stale_acquisition_count": result.stale_acquisition_count,
            "new_target_count": len(new_target_ids),
            "conflict_count": conflict_count,
            "previous_schedule_revision_id": previous_revision_id,
            "latest_commit_audit_log_id": latest_commit.id if latest_commit else None,
            "active_existing": active_existing,
        }

    has_existing_schedule = len(active_existing) > 0
    has_new_work = bool(outstanding_recurring_orders or new_target_ids)
    has_invalid_schedule = bool(
        removed_scheduled_targets or invalid_acquisition_count or conflict_count
    )

    if not has_existing_schedule:
        if previous_revision_id > 1:
            result.reason = (
                "Existing schedule was cleared or is currently empty. "
                "Building a fresh schedule from the active horizon."
            )
        else:
            result.reason = (
                "No existing schedule revision with active acquisitions was found. "
                "Building a fresh schedule from all actionable work."
            )
        _log_mode_selection(result)
        return result, {
            "workspace_id": auto_workspace,
            "existing_acquisition_count": len(active_existing),
            "existing_committed_acquisition_count": len(active_existing),
            "current_target_ids": sorted(current_target_ids),
            "existing_target_ids": sorted(existing_target_ids),
            "scheduled_target_ids": sorted(scheduled_target_ids),
            "current_materialized_instance_count": len(actionable_recurring_orders),
            "outstanding_instance_count": len(outstanding_recurring_orders),
            "new_instance_count": len(new_recurring_orders_since_revision),
            "stale_acquisition_count": result.stale_acquisition_count,
            "new_target_count": len(new_target_ids),
            "conflict_count": conflict_count,
            "previous_schedule_revision_id": previous_revision_id,
            "latest_commit_audit_log_id": latest_commit.id if latest_commit else None,
            "active_existing": active_existing,
        }

    if has_new_work and not has_invalid_schedule:
        target_priorities = _build_target_priorities(mission_data, actionable_recurring_orders)
        repair_reason = _priority_repair_reason(
            existing_target_ids=existing_target_ids,
            new_target_ids=new_target_ids,
            target_priorities=target_priorities,
            weight_priority=weight_priority,
            weight_geometry=weight_geometry,
            weight_timing=weight_timing,
        )
        if repair_reason:
            result.mode = "repair"
            result.reason = repair_reason
            _log_mode_selection(result)
            return result, {
                "workspace_id": auto_workspace,
                "existing_acquisition_count": len(active_existing),
                "existing_committed_acquisition_count": len(active_existing),
                "current_target_ids": sorted(current_target_ids),
                "existing_target_ids": sorted(existing_target_ids),
                "scheduled_target_ids": sorted(scheduled_target_ids),
                "current_materialized_instance_count": len(actionable_recurring_orders),
                "outstanding_instance_count": len(outstanding_recurring_orders),
                "new_instance_count": len(new_recurring_orders_since_revision),
                "stale_acquisition_count": result.stale_acquisition_count,
                "new_target_count": len(new_target_ids),
                "conflict_count": conflict_count,
                "previous_schedule_revision_id": previous_revision_id,
                "latest_commit_audit_log_id": latest_commit.id if latest_commit else None,
                "active_existing": active_existing,
            }

    if has_new_work and has_invalid_schedule:
        result.mode = "repair"
        result.fallback_from_mode = "incremental"
        reasons: List[str] = []
        if removed_scheduled_targets:
            reasons.append(
                f"{len(removed_scheduled_targets)} scheduled target(s) are no longer in scope"
            )
        if invalid_acquisition_count:
            reasons.append(
                f"{invalid_acquisition_count} acquisition(s) reference missing or inactive orders"
            )
        if conflict_count:
            reasons.append(f"{conflict_count} unresolved conflict(s) exist")
        result.reason = (
            "New actionable work was detected, but incremental extension is not safe because "
            + "; ".join(reasons)
            + ". Falling back to repair."
        )
        _log_mode_selection(result)
        return result, {
            "workspace_id": auto_workspace,
            "existing_acquisition_count": len(active_existing),
            "existing_committed_acquisition_count": len(active_existing),
            "current_target_ids": sorted(current_target_ids),
            "existing_target_ids": sorted(existing_target_ids),
            "scheduled_target_ids": sorted(scheduled_target_ids),
            "current_materialized_instance_count": len(actionable_recurring_orders),
            "outstanding_instance_count": len(outstanding_recurring_orders),
            "new_instance_count": len(new_recurring_orders_since_revision),
            "stale_acquisition_count": result.stale_acquisition_count,
            "new_target_count": len(new_target_ids),
            "conflict_count": conflict_count,
            "previous_schedule_revision_id": previous_revision_id,
            "latest_commit_audit_log_id": latest_commit.id if latest_commit else None,
            "active_existing": active_existing,
        }

    if has_new_work:
        result.mode = "incremental"
        result.reason = (
            f"Detected {len(outstanding_recurring_orders)} new recurring instance(s) "
            f"and {len(new_target_ids)} new one-time/target addition(s). "
            f"Planning incrementally around {len(active_existing)} committed acquisition(s)."
        )
        _log_mode_selection(result)
        return result, {
            "workspace_id": auto_workspace,
            "existing_acquisition_count": len(active_existing),
            "existing_committed_acquisition_count": len(active_existing),
            "current_target_ids": sorted(current_target_ids),
            "existing_target_ids": sorted(existing_target_ids),
            "scheduled_target_ids": sorted(scheduled_target_ids),
            "current_materialized_instance_count": len(actionable_recurring_orders),
            "outstanding_instance_count": len(outstanding_recurring_orders),
            "new_instance_count": len(new_recurring_orders_since_revision),
            "stale_acquisition_count": result.stale_acquisition_count,
            "new_target_count": len(new_target_ids),
            "conflict_count": conflict_count,
            "previous_schedule_revision_id": previous_revision_id,
            "latest_commit_audit_log_id": latest_commit.id if latest_commit else None,
            "active_existing": active_existing,
        }

    result.mode = "repair"
    if removed_scheduled_targets:
        result.reason = (
            f"{len(removed_scheduled_targets)} scheduled target(s) are no longer in scope. "
            "Repairing the current schedule so removed work can be dropped safely."
        )
    elif invalid_acquisition_count:
        result.reason = (
            f"{invalid_acquisition_count} acquisition(s) reference missing or inactive orders. "
            "Repairing the schedule to restore lineage integrity."
        )
    elif conflict_count:
        result.reason = (
            f"Existing schedule has {conflict_count} conflict(s). "
            "Repairing while preserving locked items."
        )
    else:
        result.reason = (
            "Existing schedule is still valid, but there is no newly actionable work to extend. "
            "Keeping the pipeline in repair mode so reshuffle/correction remains available without "
            "inventing a false incremental run."
        )

    _log_mode_selection(result)
    return result, {
        "workspace_id": auto_workspace,
        "existing_acquisition_count": len(active_existing),
        "existing_committed_acquisition_count": len(active_existing),
        "current_target_ids": sorted(current_target_ids),
        "existing_target_ids": sorted(existing_target_ids),
        "scheduled_target_ids": sorted(scheduled_target_ids),
        "current_materialized_instance_count": len(actionable_recurring_orders),
        "outstanding_instance_count": len(outstanding_recurring_orders),
        "new_instance_count": len(new_recurring_orders_since_revision),
        "stale_acquisition_count": result.stale_acquisition_count,
        "new_target_count": len(new_target_ids),
        "conflict_count": conflict_count,
        "previous_schedule_revision_id": previous_revision_id,
        "latest_commit_audit_log_id": latest_commit.id if latest_commit else None,
        "active_existing": active_existing,
    }


def _log_mode_selection(result: ModeSelectionResult) -> None:
    """Log a mode decision with structured fields."""
    logger.info(
        "[Auto Mode] mode=%s workspace=%s revision=%s existing_committed=%s "
        "materialized_instances=%s outstanding_instances=%s new_instances=%s new_targets=%s "
        "stale=%s conflicts=%s fallback_from=%s reason=%s",
        result.mode,
        result.workspace_id,
        result.previous_schedule_revision_id,
        result.existing_committed_acquisition_count,
        result.current_materialized_instance_count,
        result.outstanding_instance_count,
        result.new_instance_count,
        result.new_target_count,
        result.stale_acquisition_count,
        result.conflict_count,
        result.fallback_from_mode,
        result.reason,
    )


# ---------------------------------------------------------------------------
# Backward-compatible helper
# ---------------------------------------------------------------------------


def select_planning_mode(
    workspace_id: str,
    existing_acquisition_count: int,
    existing_target_ids: Optional[Set[str]],
    current_target_ids: Optional[Set[str]],
    scheduled_target_ids: Optional[Set[str]] = None,
    target_priorities: Optional[Dict[str, int]] = None,
    weight_priority: float = 40.0,
    weight_geometry: float = 40.0,
    weight_timing: float = 20.0,
    conflict_count: int = 0,
    previous_plan_count: int = 0,
    request_payload_hash: str = "",
    force_mode: Optional[str] = None,
) -> ModeSelectionResult:
    """Backward-compatible pure target-set selector retained for older callers."""
    scheduled_targets = scheduled_target_ids or set()
    existing_targets = existing_target_ids or set()
    current_targets = current_target_ids or set()
    new_targets = current_targets - existing_targets
    removed_targets = scheduled_targets - current_targets

    result = ModeSelectionResult(
        mode="from_scratch",
        reason="",
        workspace_id=workspace_id,
        existing_acquisition_count=existing_acquisition_count,
        existing_committed_acquisition_count=existing_acquisition_count,
        new_target_count=len(new_targets),
        removed_scheduled_target_count=len(removed_targets),
        conflict_count=conflict_count,
        request_payload_hash=request_payload_hash,
        existing_target_ids=existing_targets,
        current_target_ids=current_targets,
        new_target_ids=new_targets,
    )

    if force_mode and force_mode in {"from_scratch", "incremental", "repair"}:
        result.mode = force_mode
        result.reason = f"Explicitly requested mode: {force_mode}"
        return result

    if existing_acquisition_count == 0:
        result.reason = (
            "No existing schedule found for workspace. Building a fresh schedule."
        )
        return result

    if removed_targets:
        result.mode = "repair"
        result.reason = (
            f"{len(removed_targets)} scheduled target(s) are no longer in scope. "
            "Repairing the schedule."
        )
        return result

    priority_reason = _priority_repair_reason(
        existing_target_ids=existing_targets,
        new_target_ids=new_targets,
        target_priorities=target_priorities or {},
        weight_priority=weight_priority,
        weight_geometry=weight_geometry,
        weight_timing=weight_timing,
    )
    if priority_reason:
        result.mode = "repair"
        result.reason = priority_reason
        return result

    if new_targets:
        result.mode = "incremental"
        result.reason = (
            f"{len(new_targets)} new target(s) detected. Planning incrementally around "
            f"{existing_acquisition_count} existing acquisition(s)."
        )
        return result

    if conflict_count > 0:
        result.mode = "repair"
        result.reason = (
            f"Existing schedule has {conflict_count} conflict(s). Repairing current state."
        )
        return result

    result.mode = "repair"
    result.reason = (
        f"Found {existing_acquisition_count} existing acquisition(s). "
        "Locked items preserved, unlocked items may be adjusted."
    )
    return result
