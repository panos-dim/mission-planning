"""
Schedule State Router for Mission Planning.

Provides endpoints for inspecting and managing schedule state.
Implements persistent scheduling with v2.0 schema.

Endpoints:
- GET /api/v1/schedule/state - Returns current schedule state
- GET /api/v1/schedule/horizon - Returns schedule horizon with acquisitions
- POST /api/v1/schedule/commit - Commit a plan to create acquisitions
- GET /api/v1/schedule/conflicts - Get scheduling conflicts
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from backend.auto_mode_selection import (
    PipelineAuditTrail,
    compute_request_hash,
    record_schedule_diff,
    select_planning_mode,
)
from backend.schedule_persistence import (
    DEFAULT_WORKSPACE_ID,
    Acquisition,
    ScheduleDB,
    get_schedule_db,
)
from backend.workspace_persistence import get_workspace_db
from mission_planner.utils import update_log_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schedule", tags=["schedule"])
CONFLICT_HORIZON_PADDING = timedelta(hours=1)


def _bind_schedule_log_context(
    workspace_id: Optional[str] = None,
    **extra: Any,
) -> None:
    """Attach schedule-scoped context to the current request logs."""
    context: Dict[str, Any] = dict(extra)
    if workspace_id:
        context["workspace_id"] = workspace_id
    if context:
        update_log_context(**context)


# =============================================================================
# Response Models
# =============================================================================


class AcquisitionSummary(BaseModel):
    """Summary of a scheduled acquisition."""

    id: str
    satellite_id: str
    target_id: str
    start_time: str
    end_time: str
    state: str = "tentative"  # tentative | locked | committed | executing | completed
    lock_level: str = "none"  # none | hard
    order_id: Optional[str] = None


class OrderSummary(BaseModel):
    """Summary of an order."""

    id: str
    target_id: str
    priority: int = 3
    status: str = "new"  # new | planned | committed | cancelled | completed
    requested_window_start: Optional[str] = None
    requested_window_end: Optional[str] = None


class ConflictSummary(BaseModel):
    """Summary of a conflict."""

    id: str
    type: str  # temporal_overlap | slew_infeasible | resource_contention
    severity: str = "error"  # error | warning | info
    acquisition_ids: List[str]
    description: Optional[str] = None


class HorizonInfo(BaseModel):
    """Schedule horizon information."""

    start: Optional[str] = None
    end: Optional[str] = None
    freeze_cutoff: Optional[str] = None  # Time before which acquisitions are frozen


class ScheduleState(BaseModel):
    """Current schedule state."""

    acquisitions: List[AcquisitionSummary] = Field(default_factory=list)
    orders: List[OrderSummary] = Field(default_factory=list)
    conflicts: List[ConflictSummary] = Field(default_factory=list)
    horizon: Optional[HorizonInfo] = None


class ScheduleStateMeta(BaseModel):
    """Metadata about schedule state implementation."""

    persistence_enabled: bool = True
    schema_version: str = "2.5"
    implementation_status: str = "active"


class ScheduleStateResponse(BaseModel):
    """Response from schedule state endpoint."""

    success: bool
    message: str
    state: ScheduleState
    _meta: ScheduleStateMeta


class ConflictsSummary(BaseModel):
    """Summary of conflicts for horizon response."""

    total: int = 0
    by_type: Dict[str, int] = Field(default_factory=dict)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    error_count: int = 0
    warning_count: int = 0
    conflict_ids: List[str] = Field(default_factory=list)


class ScheduleHorizonResponse(BaseModel):
    """Response from schedule horizon endpoint."""

    success: bool
    horizon: HorizonInfo
    acquisitions: List[AcquisitionSummary] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)
    conflicts_summary: Optional[ConflictsSummary] = None


def _parse_iso_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO timestamp, accepting a trailing Z."""
    if not value:
        return None
    try:
        normalized = value
        if value.endswith("Z"):
            normalized = value[:-1]
            if not (
                normalized.endswith("+00:00") or normalized.endswith("-00:00")
            ):
                normalized = f"{normalized}+00:00"
        return datetime.fromisoformat(normalized)
    except (AttributeError, ValueError):
        return None


def _isoformat_z(value: datetime) -> str:
    """Format a datetime as UTC with a trailing Z."""
    if value.tzinfo is None:
        return value.isoformat() + "Z"
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _derive_horizon_from_timestamps(
    windows: List[tuple[str, str]],
    *,
    fallback_start: datetime,
    fallback_end: datetime,
    padding: timedelta = CONFLICT_HORIZON_PADDING,
) -> tuple[datetime, datetime]:
    """Derive a padded horizon from timestamp windows."""
    parsed_windows: List[tuple[datetime, datetime]] = []
    for start_raw, end_raw in windows:
        start_dt = _parse_iso_timestamp(start_raw)
        end_dt = _parse_iso_timestamp(end_raw)
        if start_dt is None or end_dt is None:
            continue
        parsed_windows.append((start_dt, end_dt))

    if not parsed_windows:
        return fallback_start, fallback_end

    horizon_start = min(start for start, _ in parsed_windows) - padding
    horizon_end = max(end for _, end in parsed_windows) + padding
    return horizon_start, horizon_end


def _derive_plan_items_horizon(
    plan_items: List[Any],
    *,
    fallback_start: datetime,
    fallback_end: datetime,
    padding: timedelta = CONFLICT_HORIZON_PADDING,
) -> tuple[datetime, datetime]:
    """Derive a padded horizon from plan items."""
    return _derive_horizon_from_timestamps(
        [(item.start_time, item.end_time) for item in plan_items],
        fallback_start=fallback_start,
        fallback_end=fallback_end,
        padding=padding,
    )


def _derive_workspace_conflict_horizon(
    db: ScheduleDB,
    workspace_id: str,
    *,
    fallback_start: datetime,
    fallback_end: datetime,
    padding: timedelta = CONFLICT_HORIZON_PADDING,
) -> tuple[datetime, datetime]:
    """Derive a padded horizon covering the workspace's active acquisitions."""
    min_start_time, max_end_time = db.get_acquisition_horizon_bounds(
        workspace_id=workspace_id,
        include_tentative=True,
    )
    if min_start_time is None or max_end_time is None:
        return fallback_start, fallback_end

    return _derive_horizon_from_timestamps(
        [(min_start_time, max_end_time)],
        fallback_start=fallback_start,
        fallback_end=fallback_end,
        padding=padding,
    )


def _calculate_temporal_overlap_seconds(
    acq1: Acquisition,
    acq2: Acquisition,
) -> Optional[float]:
    """Compute overlap seconds using the same point/interval rules as detection."""
    start1 = _parse_iso_timestamp(acq1.start_time)
    end1 = _parse_iso_timestamp(acq1.end_time)
    start2 = _parse_iso_timestamp(acq2.start_time)
    end2 = _parse_iso_timestamp(acq2.end_time)
    if not all((start1, end1, start2, end2)):
        return None

    if start1 == end1 and start2 == end2:
        return 0.0 if start1 == start2 else None
    if start1 == end1:
        return 0.0 if start2 <= start1 <= end2 else None
    if start2 == end2:
        return 0.0 if start1 <= start2 <= end1 else None

    overlap_seconds = (min(end1, end2) - max(start1, start2)).total_seconds()
    return overlap_seconds if overlap_seconds > 0 else None


def _build_conflict_details(
    conflict: Any,
    acquisition_map: Dict[str, Acquisition],
) -> Optional[Dict[str, Any]]:
    """Enrich persisted conflicts with acquisition metadata for readback/debugging."""
    try:
        acquisition_ids = json.loads(conflict.acquisition_ids_json)
    except (AttributeError, TypeError, json.JSONDecodeError):
        return None

    if len(acquisition_ids) < 2:
        return None

    acq1 = acquisition_map.get(acquisition_ids[0])
    acq2 = acquisition_map.get(acquisition_ids[1])
    if acq1 is None or acq2 is None:
        return None

    details: Dict[str, Any] = {
        "acq1_id": acq1.id,
        "acq2_id": acq2.id,
        "acq1_target": acq1.target_id,
        "acq2_target": acq2.target_id,
        "acq1_satellite_id": acq1.satellite_id,
        "acq2_satellite_id": acq2.satellite_id,
        "acq1_start": acq1.start_time,
        "acq1_end": acq1.end_time,
        "acq2_start": acq2.start_time,
        "acq2_end": acq2.end_time,
        "satellite_id": (
            acq1.satellite_id if acq1.satellite_id == acq2.satellite_id else None
        ),
    }

    if conflict.type == "temporal_overlap":
        overlap_seconds = _calculate_temporal_overlap_seconds(acq1, acq2)
        if overlap_seconds is not None:
            details["overlap_seconds"] = overlap_seconds
    elif conflict.type == "slew_infeasible":
        end1 = _parse_iso_timestamp(acq1.end_time)
        start2 = _parse_iso_timestamp(acq2.start_time)
        if end1 is not None and start2 is not None:
            details["gap_seconds"] = (start2 - end1).total_seconds()
        details["acq1_roll_deg"] = acq1.roll_angle_deg
        details["acq1_pitch_deg"] = acq1.pitch_angle_deg
        details["acq2_roll_deg"] = acq2.roll_angle_deg
        details["acq2_pitch_deg"] = acq2.pitch_angle_deg

    return details


def _refresh_workspace_conflicts_after_mutation(
    db: ScheduleDB,
    workspace_id: Optional[str],
) -> tuple[int, List[str]]:
    """Refresh persisted conflicts after schedule mutations like delete/rollback."""
    if not workspace_id:
        return 0, []

    from backend.conflict_detection import detect_and_persist_conflicts

    now = datetime.now(timezone.utc)
    recompute_start, recompute_end = _derive_workspace_conflict_horizon(
        db,
        workspace_id,
        fallback_start=now,
        fallback_end=now + timedelta(days=7),
    )

    # If the workspace has no remaining acquisitions, clear stale conflicts.
    min_start_time, max_end_time = db.get_acquisition_horizon_bounds(
        workspace_id=workspace_id,
        include_tentative=True,
    )
    if min_start_time is None or max_end_time is None:
        db.clear_unresolved_conflicts(workspace_id)
        return 0, []

    detected_conflicts, conflict_ids = detect_and_persist_conflicts(
        db=db,
        workspace_id=workspace_id,
        start_time=_isoformat_z(recompute_start),
        end_time=_isoformat_z(recompute_end),
    )
    return len(detected_conflicts), conflict_ids


def _build_current_target_ids(
    mission_data: Dict[str, Any],
    raw_opportunities: List[Dict[str, Any]],
) -> set[str]:
    """Build current target IDs from mission data, falling back to opportunities."""
    current_target_ids: set[str] = set()

    for target in mission_data.get("targets", []):
        if isinstance(target, dict):
            target_name = target.get("name", "")
        else:
            target_name = getattr(target, "name", "")
        if target_name:
            current_target_ids.add(target_name)

    if current_target_ids:
        return current_target_ids

    return {
        opp["target_id"] if isinstance(opp, dict) else getattr(opp, "target_id", "")
        for opp in raw_opportunities
        if (
            opp["target_id"] if isinstance(opp, dict) else getattr(opp, "target_id", "")
        )
    }


def _build_target_priorities(mission_data: Dict[str, Any]) -> Dict[str, int]:
    """Build target priorities from the active mission data."""
    target_priorities: Dict[str, int] = {}

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

        target_priorities[target_name] = min(5, max(1, priority))

    return target_priorities


def _load_workspace_target_baseline(workspace_id: Optional[str]) -> set[str]:
    """Load the backend baseline target set used for auto-mode comparisons."""
    if not workspace_id:
        return set()

    previous_target_ids: set[str] = set()

    try:
        ws_db = get_workspace_db()
        workspace = ws_db.get_workspace(workspace_id, include_czml=False)
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
    except Exception as e:
        logger.warning(f"[Auto Mode] Failed to load workspace target baseline: {e}")

    return previous_target_ids


def _to_utc_naive(value: datetime) -> datetime:
    """Normalize a datetime to naive UTC for internal schedule comparisons."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _resolve_auto_mode_selection(
    db: ScheduleDB,
    *,
    workspace_id: Optional[str],
    planning_mode: str,
    horizon_start: datetime,
    horizon_end: datetime,
    raw_opportunities: List[Dict[str, Any]],
    mission_data: Dict[str, Any],
    request_payload_hash: str,
    weight_priority: float = 40.0,
    weight_geometry: float = 40.0,
    weight_timing: float = 20.0,
) -> tuple[Any, Dict[str, Any]]:
    """Resolve backend auto-mode selection and return planner-facing context."""
    auto_workspace = workspace_id or "default"
    normalized_horizon_start = _to_utc_naive(horizon_start)
    normalized_horizon_end = _to_utc_naive(horizon_end)

    try:
        existing_acqs = db.get_acquisitions_by_lock_level(auto_workspace)
    except Exception as e:
        logger.warning(f"[Auto Mode] Failed to query existing acquisitions: {e}")
        existing_acqs = []

    active_existing = []
    for acq in existing_acqs:
        if acq.state in ("failed", "cancelled", "completed"):
            continue
        try:
            acq_end = _to_utc_naive(
                datetime.fromisoformat(acq.end_time.replace("Z", "+00:00"))
            )
            if acq_end <= normalized_horizon_start:
                continue
        except ValueError:
            pass
        active_existing.append(acq)

    current_target_ids = _build_current_target_ids(mission_data, raw_opportunities)
    target_priorities = _build_target_priorities(mission_data)
    previous_target_ids = _load_workspace_target_baseline(workspace_id)
    scheduled_target_ids = {
        acquisition.target_id for acquisition in active_existing if acquisition.target_id
    }
    existing_target_ids = previous_target_ids or scheduled_target_ids

    conflict_count = 0
    if active_existing:
        try:
            conflicts = db.get_conflicts_in_horizon(
                start_time=_isoformat_z(normalized_horizon_start),
                end_time=_isoformat_z(normalized_horizon_end),
                workspace_id=auto_workspace,
                include_resolved=False,
            )
            conflict_count = len(conflicts)
        except Exception as e:
            logger.warning(f"[Auto Mode] Failed to query conflicts: {e}")

    force_mode = None
    if planning_mode != "from_scratch":
        force_mode = planning_mode

    mode_result = select_planning_mode(
        workspace_id=auto_workspace,
        existing_acquisition_count=len(active_existing),
        existing_target_ids=existing_target_ids,
        current_target_ids=current_target_ids,
        scheduled_target_ids=scheduled_target_ids,
        target_priorities=target_priorities,
        weight_priority=weight_priority,
        weight_geometry=weight_geometry,
        weight_timing=weight_timing,
        conflict_count=conflict_count,
        previous_plan_count=0,
        request_payload_hash=request_payload_hash,
        force_mode=force_mode,
    )

    mode_context = {
        "workspace_id": auto_workspace,
        "existing_acquisition_count": len(active_existing),
        "new_target_count": mode_result.new_target_count,
        "conflict_count": conflict_count,
        "current_target_ids": sorted(current_target_ids),
        "existing_target_ids": sorted(existing_target_ids),
        "scheduled_target_ids": sorted(scheduled_target_ids),
        "active_existing": active_existing,
    }
    return mode_result, mode_context


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/state", response_model=ScheduleStateResponse)
async def get_schedule_state(
    workspace_id: Optional[str] = Query(None, description="Filter by workspace ID"),
    include_failed: bool = Query(
        False,
        description="Include superseded failed acquisitions in the response",
    ),
) -> ScheduleStateResponse:
    """
    Get current schedule state.

    Returns the current state of:
    - Acquisitions (scheduled observations)
    - Orders (user requests)
    - Conflicts (scheduling conflicts)
    - Horizon (time window)

    Returns:
        ScheduleStateResponse with current state from persistence layer
    """
    _bind_schedule_log_context(workspace_id=workspace_id)
    db = get_schedule_db()

    # Get recent acquisitions and orders
    acquisition_limit = 100 if workspace_id else 200
    ancillary_limit = 100
    acquisitions = db.list_acquisitions(
        workspace_id=workspace_id,
        include_failed=include_failed,
        limit=acquisition_limit,
    )
    orders_list = db.list_orders(workspace_id=workspace_id, limit=ancillary_limit)

    # Convert to summary models
    acq_summaries = [
        AcquisitionSummary(
            id=a.id,
            satellite_id=a.satellite_id,
            target_id=a.target_id,
            start_time=a.start_time,
            end_time=a.end_time,
            state=a.state,
            lock_level=a.lock_level,
            order_id=a.order_id,
        )
        for a in acquisitions
    ]

    order_summaries = [
        OrderSummary(
            id=o.id,
            target_id=o.target_id,
            priority=o.priority,
            status=o.status,
            requested_window_start=o.requested_window_start,
            requested_window_end=o.requested_window_end,
        )
        for o in orders_list
    ]

    # Build horizon from acquisitions if any exist
    horizon = None
    if acquisitions:
        start_times = [a.start_time for a in acquisitions]
        end_times = [a.end_time for a in acquisitions]
        now = datetime.now(timezone.utc)
        horizon = HorizonInfo(
            start=min(start_times),
            end=max(end_times),
            freeze_cutoff=_isoformat_z(now + timedelta(hours=2)),
        )

    # Query actual conflicts for this workspace
    conflict_summaries = []
    try:
        conflicts = db.list_conflicts(
            workspace_id=workspace_id,
            resolved=False,
            limit=ancillary_limit,
        )
        conflict_summaries = [
            ConflictSummary(
                id=c.id,
                type=c.type,
                severity=c.severity,
                acquisition_ids=(
                    json.loads(c.acquisition_ids_json) if c.acquisition_ids_json else []
                ),
                description=c.description,
            )
            for c in conflicts
        ]
    except Exception as e:
        logger.warning(f"[Schedule State] Failed to load conflicts: {e}")

    state = ScheduleState(
        acquisitions=acq_summaries,
        orders=order_summaries,
        conflicts=conflict_summaries,
        horizon=horizon,
    )

    meta = ScheduleStateMeta(
        persistence_enabled=True,
        schema_version="2.5",
        implementation_status="active",
    )

    logger.info(
        f"[Schedule State] Returning {len(acq_summaries)} acquisitions, "
        f"{len(order_summaries)} orders"
        f"{' (including failed)' if include_failed else ''}"
    )

    return ScheduleStateResponse(
        success=True,
        message=f"Schedule state: {len(acq_summaries)} acquisitions, {len(order_summaries)} orders",
        state=state,
        _meta=meta,
    )


@router.get("/horizon", response_model=ScheduleHorizonResponse)
async def get_schedule_horizon(
    from_time: Optional[str] = Query(
        None, alias="from", description="Horizon start (ISO datetime, default: now)"
    ),
    to_time: Optional[str] = Query(
        None, alias="to", description="Horizon end (ISO datetime, default: +7 days)"
    ),
    workspace_id: Optional[str] = Query(None, description="Filter by workspace ID"),
    satellite_group: Optional[str] = Query(
        None, description="Filter by satellite group ID"
    ),
    include_tentative: bool = Query(True, description="Include tentative acquisitions"),
    include_failed: bool = Query(
        False,
        description="Include superseded failed acquisitions",
    ),
    include_conflicts: bool = Query(False, description="Include conflicts summary"),
) -> ScheduleHorizonResponse:
    """
    Get schedule horizon with acquisitions.

    Returns all acquisitions within the specified time window.
    This is the key query endpoint for viewing the current schedule.

    Args:
        from_time: Start of horizon (default: now)
        to_time: End of horizon (default: +7 days)
        workspace_id: Filter by workspace
        satellite_group: Filter by satellite group
        include_tentative: Include tentative acquisitions

    Returns:
        ScheduleHorizonResponse with horizon info and acquisitions
    """
    _bind_schedule_log_context(workspace_id=workspace_id)
    db = get_schedule_db()

    # Parse or default times
    now = datetime.now(timezone.utc)

    if from_time:
        try:
            horizon_start = datetime.fromisoformat(from_time.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid from_time format: {from_time}"
            )
    else:
        horizon_start = now

    if to_time:
        try:
            horizon_end = datetime.fromisoformat(to_time.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid to_time format: {to_time}"
            )
    else:
        horizon_end = now + timedelta(days=7)

    # Freeze cutoff is 2 hours from now (standard operational practice)
    freeze_cutoff = now + timedelta(hours=2)

    logger.info(
        f"[Schedule Horizon] from={horizon_start.isoformat()}, "
        f"to={horizon_end.isoformat()}, "
        f"workspace_id={workspace_id}, "
        f"include_tentative={include_tentative}, "
        f"include_failed={include_failed}"
    )

    # Query acquisitions from persistence layer
    start_str = _isoformat_z(horizon_start)
    end_str = _isoformat_z(horizon_end)

    acquisitions = db.get_acquisitions_in_horizon(
        start_time=start_str,
        end_time=end_str,
        workspace_id=workspace_id,
        include_tentative=include_tentative,
        include_failed=include_failed,
    )

    # Convert to summary models
    acq_summaries = [
        AcquisitionSummary(
            id=a.id,
            satellite_id=a.satellite_id,
            target_id=a.target_id,
            start_time=a.start_time,
            end_time=a.end_time,
            state=a.state,
            lock_level=a.lock_level,
            order_id=a.order_id,
        )
        for a in acquisitions
    ]

    # Get statistics
    statistics = db.get_acquisition_statistics(
        start_time=start_str,
        end_time=end_str,
        workspace_id=workspace_id,
        include_tentative=include_tentative,
        include_failed=include_failed,
    )

    horizon = HorizonInfo(
        start=_isoformat_z(horizon_start),
        end=_isoformat_z(horizon_end),
        freeze_cutoff=_isoformat_z(freeze_cutoff),
    )

    # Optionally include conflicts summary
    conflicts_summary_data = None
    if include_conflicts and workspace_id:
        conflicts = db.get_conflicts_in_horizon(
            start_time=start_str,
            end_time=end_str,
            workspace_id=workspace_id,
            include_resolved=False,
        )

        conflict_stats = db.get_conflict_statistics(
            workspace_id=workspace_id,
            include_resolved=False,
        )

        conflicts_summary_data = ConflictsSummary(
            total=conflict_stats.get("total", 0),
            by_type=conflict_stats.get("by_type", {}),
            by_severity=conflict_stats.get("by_severity", {}),
            error_count=conflict_stats.get("by_severity", {}).get("error", 0),
            warning_count=conflict_stats.get("by_severity", {}).get("warning", 0),
            conflict_ids=[c.id for c in conflicts],
        )

    logger.info(
        f"[Schedule Horizon] Returning {len(acq_summaries)} acquisitions in horizon"
        + (
            f", {len(conflicts_summary_data.conflict_ids)} conflicts"
            if conflicts_summary_data
            else ""
        )
    )

    return ScheduleHorizonResponse(
        success=True,
        horizon=horizon,
        acquisitions=acq_summaries,
        statistics=statistics,
        conflicts_summary=conflicts_summary_data,
    )


# =============================================================================
# Master Schedule Endpoint (v2.5)
# =============================================================================


class MasterScheduleBucket(BaseModel):
    """Aggregated acquisition bucket for zoomed-out view."""

    target_id: str
    satellite_id: str
    mode: str
    bucket_start: str
    bucket_end: str
    count: int
    target_lat: Optional[float] = None
    target_lon: Optional[float] = None
    avg_off_nadir_deg: Optional[float] = None


class MasterScheduleResponse(BaseModel):
    """Response from master schedule endpoint."""

    success: bool
    zoom: str  # 'detail' | 'aggregate'
    total: int
    items: List[Dict[str, Any]] = Field(default_factory=list)
    buckets: List[MasterScheduleBucket] = Field(default_factory=list)
    t_start: str
    t_end: str
    fetch_ms: Optional[float] = None


@router.get("/master", response_model=MasterScheduleResponse)
async def get_master_schedule(
    workspace_id: str = Query(..., description="Workspace ID"),
    t_start: Optional[str] = Query(
        None, description="Visible range start (ISO datetime, default: now)"
    ),
    t_end: Optional[str] = Query(
        None, description="Visible range end (ISO datetime, default: +7 days)"
    ),
    zoom: str = Query(
        "detail",
        description="Zoom level: 'detail' for individual items, 'aggregate' for bucketed",
    ),
    limit: int = Query(2000, ge=1, le=5000, description="Max items in detail mode"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> MasterScheduleResponse:
    """
    Get master schedule for the Schedule menu timeline view.

    Returns all scheduled acquisitions in the visible time range with full
    fields needed for timeline rendering, map placement, and hover tooltips.

    When zoom='aggregate', returns bucketed counts per target/satellite
    instead of individual acquisitions (for zoomed-out performance).

    Required fields per item: acquisition_id, workspace_id, scheduled_start_time,
    satellite_id + display name, target_id + lat/lon, off_nadir_deg, mode.
    """
    _bind_schedule_log_context(workspace_id=workspace_id)
    import time

    t0 = time.monotonic()
    db = get_schedule_db()

    # Parse or default times
    now = datetime.now(timezone.utc)

    if t_start:
        try:
            start_dt = datetime.fromisoformat(t_start.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid t_start format: {t_start}"
            )
    else:
        start_dt = now

    if t_end:
        try:
            end_dt = datetime.fromisoformat(t_end.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid t_end format: {t_end}"
            )
    else:
        end_dt = now + timedelta(days=7)

    start_str = _isoformat_z(start_dt)
    end_str = _isoformat_z(end_dt)

    result = db.get_master_schedule(
        workspace_id=workspace_id,
        t_start=start_str,
        t_end=end_str,
        zoom=zoom,
        limit=limit,
        offset=offset,
    )

    fetch_ms = round((time.monotonic() - t0) * 1000, 1)

    logger.info(
        f"[Master Schedule] workspace={workspace_id}, zoom={zoom}, "
        f"total={result['total']}, items={len(result['items'])}, "
        f"buckets={len(result['buckets'])}, fetch_ms={fetch_ms}"
    )

    buckets = [MasterScheduleBucket(**b) for b in result["buckets"]]

    return MasterScheduleResponse(
        success=True,
        zoom=result["zoom"],
        total=result["total"],
        items=result["items"],
        buckets=buckets,
        t_start=start_str,
        t_end=end_str,
        fetch_ms=fetch_ms,
    )


class TargetLocation(BaseModel):
    """A target with its geographic position."""

    target_id: str
    latitude: float
    longitude: float


class TargetLocationsResponse(BaseModel):
    """Response from target-locations endpoint."""

    success: bool
    targets: List[TargetLocation]


@router.get("/target-locations", response_model=TargetLocationsResponse)
async def get_schedule_target_locations(
    workspace_id: Optional[str] = Query(
        None,
        description="Scope to a specific workspace. Recommended to avoid cross-workspace leaks.",
    ),
) -> TargetLocationsResponse:
    """
    Get geographic positions for all targets that have scheduled acquisitions.

    Primary source: acquisitions.target_lat / target_lon (v2.5 geo-backfill).
    Fallback: workspace scenario_config blobs.
    When workspace_id is provided, results are scoped to that workspace only.
    """
    _bind_schedule_log_context(workspace_id=workspace_id)
    from backend.workspace_persistence import get_workspace_db

    db = get_schedule_db()
    target_positions: Dict[str, TargetLocation] = {}

    # 1. Primary: get target positions directly from acquisitions table (v2.5 fields)
    with db._get_connection() as conn:
        cursor = conn.cursor()
        if workspace_id:
            cursor.execute(
                """SELECT DISTINCT target_id, target_lat, target_lon
                   FROM acquisitions
                   WHERE workspace_id = ? AND state != 'failed'""",
                (workspace_id,),
            )
        else:
            cursor.execute(
                "SELECT DISTINCT target_id, target_lat, target_lon FROM acquisitions WHERE state != 'failed'"
            )
        for row in cursor.fetchall():
            tid = row["target_id"]
            if tid and row["target_lat"] is not None and row["target_lon"] is not None:
                target_positions[tid] = TargetLocation(
                    target_id=tid,
                    latitude=row["target_lat"],
                    longitude=row["target_lon"],
                )

        # Collect target_ids that still need geo resolution
        if workspace_id:
            cursor.execute(
                """SELECT DISTINCT target_id FROM acquisitions
                   WHERE workspace_id = ? AND state != 'failed'""",
                (workspace_id,),
            )
        else:
            cursor.execute(
                "SELECT DISTINCT target_id FROM acquisitions WHERE state != 'failed'"
            )
        all_target_ids = {row["target_id"] for row in cursor.fetchall()}

    missing_ids = all_target_ids - set(target_positions.keys())

    # 2. Fallback: look up missing positions from workspace scenario_configs
    if missing_ids:
        ws_db = get_workspace_db()
        with ws_db._get_connection() as conn:
            cursor = conn.cursor()
            if workspace_id:
                cursor.execute(
                    "SELECT scenario_config_json FROM workspace_blobs WHERE workspace_id = ? AND scenario_config_json IS NOT NULL",
                    (workspace_id,),
                )
            else:
                cursor.execute(
                    "SELECT scenario_config_json FROM workspace_blobs WHERE scenario_config_json IS NOT NULL"
                )
            for row in cursor.fetchall():
                try:
                    config = json.loads(row["scenario_config_json"])
                    for t in config.get("targets", []):
                        name = t.get("name", "")
                        if name in missing_ids and name not in target_positions:
                            target_positions[name] = TargetLocation(
                                target_id=name,
                                latitude=t["latitude"],
                                longitude=t["longitude"],
                            )
                except (json.JSONDecodeError, KeyError):
                    continue

    logger.info(
        f"[TargetLocations] Resolved {len(target_positions)}/{len(all_target_ids)} target positions"
        + (f" for workspace {workspace_id}" if workspace_id else "")
    )

    return TargetLocationsResponse(
        success=True,
        targets=list(target_positions.values()),
    )


class ConflictResponse(BaseModel):
    """Response model for a single conflict."""

    id: str
    detected_at: str
    type: str
    severity: str
    description: Optional[str]
    acquisition_ids: List[str]
    details: Optional[Dict[str, Any]] = None
    resolved_at: Optional[str] = None
    resolution_action: Optional[str] = None


class ConflictListResponse(BaseModel):
    """Response from conflicts list endpoint."""

    success: bool
    conflicts: List[ConflictResponse]
    summary: Dict[str, Any]


class RecomputeConflictsRequest(BaseModel):
    """Request to recompute conflicts."""

    workspace_id: str = Field(..., description="Workspace ID to analyze")
    from_time: Optional[str] = Field(
        default=None, description="Horizon start (ISO datetime, default: now)"
    )
    to_time: Optional[str] = Field(
        default=None, description="Horizon end (ISO datetime, default: +7 days)"
    )
    satellite_id: Optional[str] = Field(
        default=None, description="Filter to single satellite"
    )


class RecomputeConflictsResponse(BaseModel):
    """Response from recompute conflicts endpoint."""

    success: bool
    message: str
    detected: int
    persisted: int
    conflict_ids: List[str]
    summary: Dict[str, Any]


@router.get("/conflicts", response_model=ConflictListResponse)
async def get_schedule_conflicts(
    workspace_id: Optional[str] = Query(None, description="Filter by workspace ID"),
    from_time: Optional[str] = Query(
        None, alias="from", description="Horizon start (ISO datetime)"
    ),
    to_time: Optional[str] = Query(
        None, alias="to", description="Horizon end (ISO datetime)"
    ),
    satellite_id: Optional[str] = Query(None, description="Filter by satellite"),
    conflict_type: Optional[str] = Query(
        None, description="Filter by type: temporal_overlap | slew_infeasible"
    ),
    severity: Optional[str] = Query(
        None, description="Filter by severity: error | warning | info"
    ),
    include_resolved: bool = Query(False, description="Include resolved conflicts"),
) -> ConflictListResponse:
    """
    Get schedule conflicts.

    Returns conflicts from the database, optionally filtered by:
    - workspace_id: Associated workspace
    - from/to: Time horizon (only conflicts for acquisitions in this window)
    - satellite_id: Only conflicts involving this satellite
    - conflict_type: temporal_overlap | slew_infeasible
    - severity: error | warning | info
    - include_resolved: Whether to include already-resolved conflicts

    Conflict types:
    - temporal_overlap: Two acquisitions for the same satellite overlap in time
    - slew_infeasible: Insufficient time to slew between consecutive acquisitions
    """
    _bind_schedule_log_context(
        workspace_id=workspace_id,
        satellite_id=satellite_id,
    )
    db = get_schedule_db()

    logger.info(
        f"[Schedule Conflicts] workspace_id={workspace_id}, "
        f"from={from_time}, to={to_time}, satellite_id={satellite_id}"
    )

    # If horizon specified, use horizon-based query
    if from_time or to_time:
        now = datetime.now(timezone.utc)
        start_str = from_time or _isoformat_z(now)
        end_str = to_time or _isoformat_z(now + timedelta(days=7))

        conflicts = db.get_conflicts_in_horizon(
            start_time=start_str,
            end_time=end_str,
            workspace_id=workspace_id,
            satellite_id=satellite_id,
            include_resolved=include_resolved,
        )
    else:
        # List all conflicts with filters
        conflicts = db.list_conflicts(
            workspace_id=workspace_id,
            conflict_type=conflict_type,
            severity=severity,
            resolved=None if include_resolved else False,
        )

    acquisition_ids: List[str] = []
    for conflict in conflicts:
        try:
            acquisition_ids.extend(json.loads(conflict.acquisition_ids_json))
        except (TypeError, json.JSONDecodeError):
            continue

    acquisition_map = db.get_acquisitions_by_ids(sorted(set(acquisition_ids)))

    # Convert to response format
    conflict_responses = [
        ConflictResponse(
            **{
                **c.to_dict(),
                "details": _build_conflict_details(c, acquisition_map),
            }
        )
        for c in conflicts
    ]

    # Get statistics
    summary = db.get_conflict_statistics(
        workspace_id=workspace_id,
        include_resolved=include_resolved,
    )

    return ConflictListResponse(
        success=True,
        conflicts=conflict_responses,
        summary=summary,
    )


@router.post("/conflicts/recompute", response_model=RecomputeConflictsResponse)
async def recompute_conflicts(
    request: RecomputeConflictsRequest,
) -> RecomputeConflictsResponse:
    """
    Recompute conflicts for a workspace within a time horizon.

    This endpoint:
    1. Clears existing unresolved conflicts for the workspace
    2. Analyzes all acquisitions in the horizon
    3. Detects temporal overlaps and slew infeasibility
    4. Persists new conflicts to the database

    Use this after making changes to the schedule to refresh conflict state.
    """
    from backend.conflict_detection import detect_and_persist_conflicts

    _bind_schedule_log_context(
        workspace_id=request.workspace_id,
        satellite_id=request.satellite_id,
    )
    db = get_schedule_db()

    # Parse or default times
    now = datetime.now(timezone.utc)
    if request.from_time or request.to_time:
        start_str = request.from_time or _isoformat_z(now)
        end_str = request.to_time or _isoformat_z(now + timedelta(days=7))
    elif request.workspace_id:
        recompute_start, recompute_end = _derive_workspace_conflict_horizon(
            db,
            request.workspace_id,
            fallback_start=now,
            fallback_end=now + timedelta(days=7),
        )
        start_str = _isoformat_z(recompute_start)
        end_str = _isoformat_z(recompute_end)
    else:
        start_str = _isoformat_z(now)
        end_str = _isoformat_z(now + timedelta(days=7))

    logger.info(
        f"[Recompute Conflicts] workspace={request.workspace_id}, "
        f"from={start_str}, to={end_str}, satellite={request.satellite_id}"
    )

    try:
        # Detect and persist conflicts
        detected_conflicts, conflict_ids = detect_and_persist_conflicts(
            db=db,
            workspace_id=request.workspace_id,
            start_time=start_str,
            end_time=end_str,
            satellite_id=request.satellite_id,
        )

        # Get updated statistics
        summary = db.get_conflict_statistics(
            workspace_id=request.workspace_id,
            include_resolved=False,
        )

        return RecomputeConflictsResponse(
            success=True,
            message=f"Detected {len(detected_conflicts)} conflicts, persisted {len(conflict_ids)}",
            detected=len(detected_conflicts),
            persisted=len(conflict_ids),
            conflict_ids=conflict_ids,
            summary=summary,
        )

    except Exception as e:
        logger.error(f"Failed to recompute conflicts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Commit Plan Endpoint
# =============================================================================


# =============================================================================
# Lock Management Endpoints
# =============================================================================


class UpdateLockRequest(BaseModel):
    """Request to update acquisition lock level."""

    acquisition_id: str = Field(..., description="Acquisition ID to update")
    lock_level: str = Field(..., description="New lock level: none | hard")


class UpdateLockResponse(BaseModel):
    """Response from lock update."""

    success: bool
    message: str
    acquisition_id: str
    lock_level: str


class BulkLockRequest(BaseModel):
    """Request for bulk lock operations."""

    acquisition_ids: List[str] = Field(..., description="Acquisition IDs to update")
    lock_level: str = Field(..., description="Lock level: none | hard")


class BulkLockResponse(BaseModel):
    """Response from bulk lock operation."""

    success: bool
    message: str
    updated: int
    failed: List[str]
    lock_level: str


class HardLockCommittedRequest(BaseModel):
    """Request to hard-lock all committed acquisitions."""

    workspace_id: str = Field(..., description="Workspace ID")


class HardLockCommittedResponse(BaseModel):
    """Response from hard-lock all committed."""

    success: bool
    message: str
    updated: int
    workspace_id: str


@router.patch("/acquisition/{acquisition_id}/lock", response_model=UpdateLockResponse)
async def update_acquisition_lock(
    acquisition_id: str,
    lock_level: str = Query(..., description="New lock level: none | hard"),
) -> UpdateLockResponse:
    """
    Update the lock level of a single acquisition.

    Lock levels (PR-OPS-REPAIR-DEFAULT-01: simplified to hard/none only):
    - none: Fully flexible, can be rearranged by repair
    - hard: Immutable, never touched by repair mode

    Note: Cannot unlock (set to none) acquisitions in 'executing' or 'locked' state.
    """
    db = get_schedule_db()

    # PR-OPS-REPAIR-DEFAULT-01: Normalize soft → none
    if lock_level == "soft":
        lock_level = "none"

    # Validate lock level
    valid_locks = ["none", "hard"]
    if lock_level not in valid_locks:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid lock_level: {lock_level}. Must be one of {valid_locks}",
        )

    # Check acquisition exists
    acq = db.get_acquisition(acquisition_id)
    if not acq:
        raise HTTPException(
            status_code=404, detail=f"Acquisition not found: {acquisition_id}"
        )

    # Prevent unlocking executing/locked state acquisitions
    if lock_level == "none" and acq.state in ("executing", "locked"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot unlock acquisition in state '{acq.state}'",
        )

    # Update lock level
    success = db.update_acquisition_lock_level(acquisition_id, lock_level)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update lock level")

    logger.info(
        f"Updated lock level for {acquisition_id}: {acq.lock_level} -> {lock_level}"
    )

    return UpdateLockResponse(
        success=True,
        message=f"Lock level updated to '{lock_level}'",
        acquisition_id=acquisition_id,
        lock_level=lock_level,
    )


@router.post("/acquisitions/bulk-lock", response_model=BulkLockResponse)
async def bulk_update_lock(request: BulkLockRequest) -> BulkLockResponse:
    """
    Update lock level for multiple acquisitions.

    PR-OPS-REPAIR-DEFAULT-01: Only hard/none lock levels supported.

    Useful for:
    - "Hard-lock selected" - Protect acquisitions from repair
    - "Unlock selected" - Make acquisitions flexible for repair

    Note: Acquisitions in 'executing' state cannot be unlocked.
    """
    db = get_schedule_db()

    # PR-OPS-REPAIR-DEFAULT-01: Normalize soft → none
    lock_level = request.lock_level
    if lock_level == "soft":
        lock_level = "none"

    # Validate lock level
    valid_locks = ["none", "hard"]
    if lock_level not in valid_locks:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid lock_level: {lock_level}. Must be one of {valid_locks}",
        )

    if not request.acquisition_ids:
        raise HTTPException(status_code=400, detail="No acquisition IDs provided")

    result = db.bulk_update_lock_levels(request.acquisition_ids, lock_level)

    message = f"Updated {result['updated']} acquisitions to '{lock_level}'"
    if result["failed"]:
        message += f" ({len(result['failed'])} failed)"

    logger.info(message)

    return BulkLockResponse(
        success=True,
        message=message,
        updated=result["updated"],
        failed=result["failed"],
        lock_level=request.lock_level,
    )


@router.post(
    "/acquisitions/hard-lock-committed", response_model=HardLockCommittedResponse
)
async def hard_lock_all_committed(
    request: HardLockCommittedRequest,
) -> HardLockCommittedResponse:
    """
    Hard-lock all committed acquisitions in a workspace.

    This is a convenience operation for mission planners who want to
    "freeze" all committed work before running repair mode.
    """
    _bind_schedule_log_context(workspace_id=request.workspace_id)
    db = get_schedule_db()

    result = db.hard_lock_all_committed(request.workspace_id)

    return HardLockCommittedResponse(
        success=True,
        message=f"Hard-locked {result['updated']} committed acquisitions",
        updated=result["updated"],
        workspace_id=request.workspace_id,
    )


# =============================================================================
# Auto Lock Escalation
# =============================================================================


class AutoEscalateLocksRequest(BaseModel):
    """Request for automatic lock escalation."""

    workspace_id: str = Field(..., description="Workspace to escalate")
    escalation_window_hours: Optional[int] = Field(
        default=None,
        description="Hours before execution to escalate (defaults to freeze window)",
    )


class AutoEscalateLocksResponse(BaseModel):
    """Response from auto lock escalation."""

    success: bool
    message: str
    escalated: int
    acquisition_ids: List[str] = Field(default_factory=list)


@router.post(
    "/acquisitions/auto-escalate-locks", response_model=AutoEscalateLocksResponse
)
async def auto_escalate_locks(
    request: AutoEscalateLocksRequest,
) -> AutoEscalateLocksResponse:
    """
    Auto-promote unlocked acquisitions approaching execution to hard lock.

    Acquisitions with lock_level='none' that start within the freeze window
    are promoted to 'hard' lock to prevent repair plans from displacing them.

    This can be called manually or integrated with a cron/background task.
    """
    _bind_schedule_log_context(workspace_id=request.workspace_id)
    db = get_schedule_db()

    result = db.auto_escalate_locks(
        workspace_id=request.workspace_id,
        escalation_window_hours=request.escalation_window_hours,
    )

    return AutoEscalateLocksResponse(
        success=True,
        message=f"Escalated {result['escalated']} acquisitions to hard lock",
        escalated=result["escalated"],
        acquisition_ids=result["acquisition_ids"],
    )


# =============================================================================
# Acquisition Deletion Endpoints
# =============================================================================


class DeleteAcquisitionResponse(BaseModel):
    """Response from acquisition deletion."""

    success: bool
    message: str
    acquisition_id: str


class BulkDeleteAcquisitionsRequest(BaseModel):
    """Request for bulk acquisition deletion."""

    acquisition_ids: List[str] = Field(..., description="Acquisition IDs to delete")
    force: bool = Field(
        default=False,
        description="Force delete even hard-locked/frozen acquisitions",
    )
    workspace_id: Optional[str] = Field(
        default=None,
        description="Workspace ID for ownership verification",
    )


class BulkDeleteAcquisitionsResponse(BaseModel):
    """Response from bulk acquisition deletion."""

    success: bool
    message: str
    deleted: int
    failed: List[str]
    skipped_hard_locked: List[str] = Field(default_factory=list)
    skipped_frozen: List[str] = Field(default_factory=list)
    skipped_workspace: List[str] = Field(default_factory=list)


@router.delete(
    "/acquisition/{acquisition_id}", response_model=DeleteAcquisitionResponse
)
async def delete_acquisition(
    acquisition_id: str,
    force: bool = Query(False, description="Force delete even if hard-locked"),
    workspace_id: Optional[str] = Query(
        None, description="Workspace ID for ownership verification"
    ),
) -> DeleteAcquisitionResponse:
    """
    Delete a single acquisition from the schedule.

    By default, hard-locked acquisitions cannot be deleted.
    Acquisitions within the freeze window (next 2 hours) are protected.
    Cross-workspace deletion requires matching workspace_id.
    Use force=true to override all protections.
    """
    _bind_schedule_log_context(
        workspace_id=workspace_id,
        acquisition_id=acquisition_id,
    )
    db = get_schedule_db()

    # Check acquisition exists
    acq = db.get_acquisition(acquisition_id)
    if not acq:
        raise HTTPException(
            status_code=404, detail=f"Acquisition not found: {acquisition_id}"
        )

    # C1-FIX: Workspace isolation — verify ownership
    if (
        not force
        and workspace_id
        and acq.workspace_id
        and acq.workspace_id != workspace_id
    ):
        raise HTTPException(
            status_code=403,
            detail=f"Acquisition {acquisition_id} belongs to workspace "
            f"'{acq.workspace_id}', not '{workspace_id}'. "
            f"Cross-workspace deletion is not allowed.",
        )

    # C2-FIX: Freeze cutoff enforcement — protect near-execution acquisitions
    if not force:
        now = datetime.now(timezone.utc)
        freeze_cutoff = now + timedelta(hours=2)
        try:
            acq_start = datetime.fromisoformat(acq.start_time.replace("Z", "+00:00"))
            if acq_start <= freeze_cutoff:
                raise HTTPException(
                    status_code=409,
                    detail=f"Acquisition {acquisition_id} starts at {acq.start_time} "
                    f"which is within the freeze window (before "
                    f"{freeze_cutoff.isoformat()}Z). Acquisitions near execution "
                    f"cannot be deleted. Use force=true to override.",
                )
        except (ValueError, AttributeError):
            pass  # If time parsing fails, skip freeze check

    # Protect hard-locked acquisitions unless force
    if acq.lock_level == "hard" and not force:
        raise HTTPException(
            status_code=409,
            detail=f"Acquisition {acquisition_id} is hard-locked. "
            f"Use force=true to delete it.",
        )

    # Pass force=True since the router already validated protections above
    success = db.delete_acquisition(acquisition_id, force=True)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete acquisition")

    _refresh_workspace_conflicts_after_mutation(db, acq.workspace_id or workspace_id)

    logger.info(
        f"Deleted acquisition {acquisition_id} "
        f"(was {acq.state}, lock={acq.lock_level}, workspace={acq.workspace_id})"
    )

    return DeleteAcquisitionResponse(
        success=True,
        message=f"Acquisition {acquisition_id} deleted",
        acquisition_id=acquisition_id,
    )


@router.post(
    "/acquisitions/bulk-delete",
    response_model=BulkDeleteAcquisitionsResponse,
)
async def bulk_delete_acquisitions(
    request: BulkDeleteAcquisitionsRequest,
) -> BulkDeleteAcquisitionsResponse:
    """
    Delete multiple acquisitions from the schedule.

    By default, hard-locked acquisitions are skipped.
    Use force=true to delete them as well.
    """
    _bind_schedule_log_context(workspace_id=request.workspace_id)
    db = get_schedule_db()

    if not request.acquisition_ids:
        raise HTTPException(status_code=400, detail="No acquisition IDs provided")

    ids_to_delete = list(request.acquisition_ids)
    skipped_hard_locked: List[str] = []
    skipped_frozen: List[str] = []
    skipped_workspace: List[str] = []

    # Unless force, filter out protected acquisitions
    if not request.force:
        now = datetime.now(timezone.utc)
        freeze_cutoff = now + timedelta(hours=2)
        filtered_ids: List[str] = []
        for acq_id in ids_to_delete:
            acq = db.get_acquisition(acq_id)
            if not acq:
                filtered_ids.append(acq_id)  # Let bulk_delete handle not-found
                continue
            # Workspace isolation
            if (
                request.workspace_id
                and acq.workspace_id
                and acq.workspace_id != request.workspace_id
            ):
                skipped_workspace.append(acq_id)
                continue
            # Freeze cutoff
            try:
                acq_start = datetime.fromisoformat(
                    acq.start_time.replace("Z", "+00:00")
                )
                if acq_start <= freeze_cutoff:
                    skipped_frozen.append(acq_id)
                    continue
            except (ValueError, AttributeError):
                pass
            # Hard-lock
            if acq.lock_level == "hard":
                skipped_hard_locked.append(acq_id)
                continue
            filtered_ids.append(acq_id)
        ids_to_delete = filtered_ids

    # Pass force=True since the router already validated protections above
    refresh_workspace_ids = {
        acq.workspace_id
        for acq_id in ids_to_delete
        if (acq := db.get_acquisition(acq_id)) is not None and acq.workspace_id
    }
    result = db.bulk_delete_acquisitions(ids_to_delete, force=True)

    for affected_workspace_id in sorted(refresh_workspace_ids):
        _refresh_workspace_conflicts_after_mutation(db, affected_workspace_id)

    message = f"Deleted {result['deleted']} acquisitions"
    if result["failed"]:
        message += f" ({len(result['failed'])} not found)"
    if skipped_hard_locked:
        message += f" ({len(skipped_hard_locked)} hard-locked skipped)"
    if skipped_frozen:
        message += f" ({len(skipped_frozen)} frozen skipped)"
    if skipped_workspace:
        message += f" ({len(skipped_workspace)} cross-workspace skipped)"

    logger.info(message)

    return BulkDeleteAcquisitionsResponse(
        success=True,
        message=message,
        deleted=result["deleted"],
        failed=result["failed"],
        skipped_hard_locked=skipped_hard_locked,
        skipped_frozen=skipped_frozen,
        skipped_workspace=skipped_workspace,
    )


# =============================================================================
# Commit Plan Endpoint
# =============================================================================


class CommitPlanRequest(BaseModel):
    """Request to commit a plan."""

    plan_id: str = Field(..., description="Plan ID to commit")
    items_to_commit: Optional[List[str]] = Field(
        default=None, description="Specific plan item IDs to commit (all if empty)"
    )
    lock_level: str = Field(
        default="none", description="Lock level for acquisitions: none | hard"
    )
    mode: str = Field(default="OPTICAL", description="Mission mode: OPTICAL | SAR")
    workspace_id: Optional[str] = Field(
        default=None, description="Workspace ID for created acquisitions"
    )
    notes: Optional[str] = Field(default=None, description="Optional commit notes")
    force: bool = Field(
        default=False,
        description="Force commit even if it introduces severity=error conflicts",
    )
    recompute_conflicts: bool = Field(
        default=True,
        description="Recompute conflicts after commit",
    )


class CommitPlanResponse(BaseModel):
    """Response from commit plan endpoint."""

    success: bool
    message: str
    committed: int
    acquisitions_created: List[Dict[str, str]]
    orders_updated: List[str]
    conflicts_detected: int = 0
    conflict_ids: List[str] = Field(default_factory=list)


@router.post("/commit", response_model=CommitPlanResponse)
async def commit_plan(request: CommitPlanRequest) -> CommitPlanResponse:
    """
    Commit a plan to create acquisitions.

    This is the key operation that turns a candidate plan into committed
    acquisitions that are persisted in the database.

    The commit operation:
    1. (Optional) Checks for existing conflicts - rejects if severity=error unless force=true
    2. Creates acquisition records from plan items
    3. Updates order statuses to 'committed'
    4. Marks the plan as 'committed'
    5. (Optional) Recomputes conflicts for the workspace

    Args:
        request: CommitPlanRequest with plan_id and options

    Returns:
        CommitPlanResponse with count of committed acquisitions and any detected conflicts
    """
    from backend.conflict_detection import detect_and_persist_conflicts

    effective_workspace_id = request.workspace_id or DEFAULT_WORKSPACE_ID
    _bind_schedule_log_context(
        workspace_id=effective_workspace_id,
        plan_id=request.plan_id,
    )
    db = get_schedule_db()

    # Validate lock level
    if request.lock_level not in ["none", "hard"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid lock_level: {request.lock_level}. Must be 'none' or 'hard'",
        )

    # Check plan exists
    plan = db.get_plan(request.plan_id)
    if not plan:
        raise HTTPException(
            status_code=404, detail=f"Plan not found: {request.plan_id}"
        )

    if plan.status == "committed":
        raise HTTPException(
            status_code=400,
            detail=f"Plan {request.plan_id} is already committed",
        )

    # Pre-commit conflict prediction: reject if error-severity conflicts
    # would be introduced, unless force=true
    if not request.force:
        from backend.incremental_planning import predict_commit_conflicts

        plan_items = db.get_plan_items(request.plan_id)
        if plan_items:
            items_as_dicts = [
                {
                    "satellite_id": item.satellite_id,
                    "target_id": item.target_id,
                    "start_time": item.start_time,
                    "end_time": item.end_time,
                    "roll_angle_deg": item.roll_angle_deg,
                    "pitch_angle_deg": item.pitch_angle_deg,
                }
                for item in plan_items
            ]
            now = datetime.now(timezone.utc)
            prediction_start, prediction_end = _derive_plan_items_horizon(
                plan_items,
                fallback_start=now,
                fallback_end=now + timedelta(days=7),
            )
            predicted, count = predict_commit_conflicts(
                db=db,
                workspace_id=effective_workspace_id,
                new_items=items_as_dicts,
                horizon_start=prediction_start,
                horizon_end=prediction_end,
            )
            error_predicted = [c for c in predicted if c.get("severity") == "error"]
            if error_predicted:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": (
                            f"Commit would introduce {len(error_predicted)} "
                            f"error-severity conflict(s)"
                        ),
                        "predicted_conflicts": error_predicted,
                        "hint": "Set force=true to commit anyway, or adjust your plan",
                    },
                )

    try:
        result = db.commit_plan(
            plan_id=request.plan_id,
            item_ids=request.items_to_commit or [],
            lock_level=request.lock_level,
            mode=request.mode,
            workspace_id=effective_workspace_id,
        )

        logger.info(
            f"[Commit Plan] Committed plan {request.plan_id}: "
            f"{result['committed']} acquisitions created"
        )

        # Post-commit: recompute and persist conflicts for monitoring
        conflicts_detected = 0
        conflict_ids: List[str] = []

        if request.recompute_conflicts:
            now = datetime.now(timezone.utc)
            recompute_start, recompute_end = _derive_workspace_conflict_horizon(
                db,
                effective_workspace_id,
                fallback_start=now,
                fallback_end=now + timedelta(days=7),
            )
            start_str = _isoformat_z(recompute_start)
            end_str = _isoformat_z(recompute_end)

            detected_conflicts, new_conflict_ids = detect_and_persist_conflicts(
                db=db,
                workspace_id=effective_workspace_id,
                start_time=start_str,
                end_time=end_str,
            )

            conflicts_detected = len(detected_conflicts)
            conflict_ids = new_conflict_ids

        message = (
            f"Committed {result['committed']} acquisitions from plan {request.plan_id}"
        )
        if conflicts_detected > 0:
            message += f" ({conflicts_detected} conflicts detected)"

        return CommitPlanResponse(
            success=True,
            message=message,
            committed=result["committed"],
            acquisitions_created=result["acquisitions_created"],
            orders_updated=result["orders_updated"],
            conflicts_detected=conflicts_detected,
            conflict_ids=conflict_ids,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to commit plan {request.plan_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Direct Acquisition Commit (for frontend "Promote to Orders")
# =============================================================================


def _compute_direct_commit_input_hash(items: List["DirectCommitItem"]) -> str:
    """Build a deterministic fingerprint for a direct-commit payload."""
    item_fingerprints = sorted(
        f"{item.satellite_id}|{item.target_id}|{item.start_time}|{item.end_time}"
        for item in items
    )
    content_hash = hashlib.sha256("|".join(item_fingerprints).encode()).hexdigest()[:24]
    return f"sha256:{content_hash}"


def _find_existing_direct_commit_plan(
    db: ScheduleDB,
    input_hash: str,
) -> Optional[str]:
    """Return a previously committed plan with the same direct-commit payload."""
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM plans WHERE input_hash = ? AND status = 'committed' LIMIT 1",
            (input_hash,),
        )
        row = cursor.fetchone()
    return row["id"] if row else None


def _predict_direct_commit_conflicts(
    db: ScheduleDB,
    items: List["DirectCommitItem"],
    workspace_id: Optional[str],
) -> List[Dict[str, Any]]:
    """Predict conflicts for direct-commit items using the same backend detector as commit."""
    from backend.incremental_planning import predict_commit_conflicts

    effective_workspace_id = workspace_id or DEFAULT_WORKSPACE_ID
    if not items:
        return []

    now = datetime.now(timezone.utc)
    horizon_start, horizon_end = _derive_horizon_from_timestamps(
        [(item.start_time, item.end_time) for item in items],
        fallback_start=now,
        fallback_end=now + timedelta(days=7),
    )

    new_items = [
        {
            "satellite_id": item.satellite_id,
            "target_id": item.target_id,
            "start_time": item.start_time,
            "end_time": item.end_time,
            "roll_angle_deg": item.roll_angle_deg,
            "pitch_angle_deg": item.pitch_angle_deg,
        }
        for item in items
    ]

    predicted_conflicts, _ = predict_commit_conflicts(
        db=db,
        workspace_id=effective_workspace_id,
        new_items=new_items,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
    )

    normalized_conflicts: List[Dict[str, Any]] = []
    for conflict in predicted_conflicts:
        normalized_ids: List[str] = []
        for acquisition_id in conflict.get("acquisition_ids", []):
            if isinstance(acquisition_id, str) and acquisition_id.startswith("pseudo_"):
                try:
                    pseudo_index = int(acquisition_id.split("_", 1)[1])
                except (IndexError, ValueError):
                    normalized_ids.append(acquisition_id)
                    continue
                if 0 <= pseudo_index < len(items):
                    normalized_ids.append(f"new:{items[pseudo_index].opportunity_id}")
                else:
                    normalized_ids.append(acquisition_id)
            else:
                normalized_ids.append(acquisition_id)

        normalized_conflicts.append(
            {
                **conflict,
                "acquisition_ids": normalized_ids,
            }
        )

    return normalized_conflicts


class DirectCommitItem(BaseModel):
    """Single item to commit directly (from frontend)."""

    opportunity_id: str
    satellite_id: str
    target_id: str
    start_time: str
    end_time: str
    roll_angle_deg: float
    pitch_angle_deg: float = 0.0
    value: Optional[float] = None
    incidence_angle_deg: Optional[float] = None
    # SAR fields
    sar_mode: Optional[str] = None
    look_side: Optional[str] = None
    pass_direction: Optional[str] = None


class DirectCommitPreviewRequest(BaseModel):
    """Request to preview a direct commit without mutating persistence."""

    items: List[DirectCommitItem]
    workspace_id: Optional[str] = None


class DirectCommitPreviewResponse(BaseModel):
    """Response from direct-commit preview."""

    success: bool
    message: str
    new_items_count: int
    conflicts_count: int
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class DirectCommitRequest(BaseModel):
    """Request to directly commit acquisitions (bypass plan creation)."""

    items: List[DirectCommitItem]
    algorithm: str = Field(
        default="unknown", description="Algorithm that generated this schedule"
    )
    mode: str = Field(default="OPTICAL", description="Mission mode: OPTICAL | SAR")
    lock_level: str = Field(default="none", description="Lock level: none | hard")
    workspace_id: Optional[str] = None
    notes: Optional[str] = None
    force: bool = Field(
        default=False,
        description="Force commit even with conflicts (for reshuffle scenarios)",
    )


class DirectCommitResponse(BaseModel):
    """Response from direct commit."""

    success: bool
    message: str
    plan_id: str
    committed: int
    acquisition_ids: List[str]
    conflicts_detected: int = 0
    conflict_ids: List[str] = Field(default_factory=list)


@router.post("/commit/direct/preview", response_model=DirectCommitPreviewResponse)
async def preview_commit_direct(
    request: DirectCommitPreviewRequest,
) -> DirectCommitPreviewResponse:
    """Preview direct-commit conflicts using the same backend rules as the actual commit."""
    db = get_schedule_db()
    effective_workspace_id = request.workspace_id or DEFAULT_WORKSPACE_ID
    _bind_schedule_log_context(workspace_id=effective_workspace_id)

    if not request.items:
        raise HTTPException(status_code=400, detail="No items to preview")

    conflicts = _predict_direct_commit_conflicts(
        db,
        request.items,
        effective_workspace_id,
    )

    duplicate_plan_id = _find_existing_direct_commit_plan(
        db,
        _compute_direct_commit_input_hash(request.items),
    )
    if duplicate_plan_id:
        conflicts.append(
            {
                "type": "duplicate_commit",
                "severity": "error",
                "description": (
                    "This exact schedule was already committed earlier. "
                    "Applying again would create a duplicate schedule."
                ),
                "acquisition_ids": [],
                "reason": (
                    "The direct-commit payload matches a previously committed plan. "
                    "This usually means the operator retried an already applied schedule."
                ),
                "details": {"existing_plan_id": duplicate_plan_id},
            }
        )

    error_count = sum(1 for conflict in conflicts if conflict.get("severity") == "error")
    message = (
        f"Preview found {len(conflicts)} conflict(s)"
        if conflicts
        else f"Preview ready for {len(request.items)} new item(s)"
    )
    if duplicate_plan_id:
        message += f" (duplicate of {duplicate_plan_id})"
    if error_count:
        message += f"; {error_count} require force to apply"

    return DirectCommitPreviewResponse(
        success=True,
        message=message,
        new_items_count=len(request.items),
        conflicts_count=len(conflicts),
        conflicts=conflicts,
        warnings=[],
    )


@router.post("/commit/direct", response_model=DirectCommitResponse)
async def commit_direct(request: DirectCommitRequest) -> DirectCommitResponse:
    """
    Directly commit acquisitions without a pre-existing plan.

    This endpoint supports the frontend's "Promote to Orders" workflow by:
    1. Checking for conflicts with existing committed acquisitions
    2. Creating a plan record for audit/traceability
    3. Creating plan items from the provided schedule
    4. Committing the plan to create acquisitions

    This is a convenience endpoint that wraps plan creation + commit in one call.
    """
    import uuid

    from backend.conflict_detection import detect_and_persist_conflicts

    db = get_schedule_db()
    effective_workspace_id = request.workspace_id or DEFAULT_WORKSPACE_ID
    _bind_schedule_log_context(workspace_id=effective_workspace_id)

    logger.info(
        f"[Direct Commit] Received request: items={len(request.items)}, "
        f"algorithm={request.algorithm}, mode={request.mode}, "
        f"workspace_id={effective_workspace_id}"
    )

    if not request.items:
        raise HTTPException(status_code=400, detail="No items to commit")

    expected_revision = db.get_schedule_revision(effective_workspace_id)
    predicted_conflicts = _predict_direct_commit_conflicts(
        db,
        request.items,
        effective_workspace_id,
    )
    duplicate_plan_id = _find_existing_direct_commit_plan(
        db,
        _compute_direct_commit_input_hash(request.items),
    )

    if duplicate_plan_id:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "Duplicate commit detected. This exact schedule was already applied."
                ),
                "duplicate_plan_id": duplicate_plan_id,
            },
        )

    error_predicted = [
        conflict for conflict in predicted_conflicts if conflict.get("severity") == "error"
    ]
    if error_predicted and not request.force:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    f"Commit would introduce {len(error_predicted)} error-severity conflict(s)"
                ),
                "predicted_conflicts": error_predicted,
                "hint": "Set force=true to commit anyway, or adjust your plan",
            },
        )
    if predicted_conflicts and request.force:
        logger.warning(
            f"[Direct Commit] Force-committing with {len(predicted_conflicts)} predicted conflict(s)"
        )

    try:
        input_hash = _compute_direct_commit_input_hash(request.items)

        # Generate run_id
        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        _bind_schedule_log_context(workspace_id=effective_workspace_id, run_id=run_id)

        # Build metrics from items
        metrics = {
            "accepted": len(request.items),
            "algorithm": request.algorithm,
            "committed_at": _isoformat_z(datetime.now(timezone.utc)),
        }

        # Create plan record
        plan = db.create_plan(
            algorithm=request.algorithm,
            config={"mode": request.mode, "source": "direct_commit"},
            input_hash=input_hash,
            run_id=run_id,
            metrics=metrics,
            workspace_id=effective_workspace_id,
        )
        _bind_schedule_log_context(
            workspace_id=effective_workspace_id,
            run_id=run_id,
            plan_id=plan.id,
        )

        # Create plan items
        for item in request.items:
            db.create_plan_item(
                plan_id=plan.id,
                opportunity_id=item.opportunity_id,
                satellite_id=item.satellite_id,
                target_id=item.target_id,
                start_time=item.start_time,
                end_time=item.end_time,
                roll_angle_deg=item.roll_angle_deg,
                pitch_angle_deg=item.pitch_angle_deg,
                value=item.value,
                quality_score=item.value,
            )

        # Commit the plan
        try:
            result = db.commit_plan_atomic(
                plan_id=plan.id,
                item_ids=[],  # Commit all items
                lock_level=request.lock_level,
                mode=request.mode,
                workspace_id=effective_workspace_id,
                expected_revision=expected_revision,
                enforce_current_conflict_check=True,
                allow_conflicts=request.force,
            )
        except ValueError as exc:
            error_message = str(exc)
            if "Schedule revision conflict" in error_message:
                db.update_plan_status(plan.id, "superseded")
                current_conflicts: List[Dict[str, Any]] = []
                try:
                    current_conflicts = _predict_direct_commit_conflicts(
                        db,
                        request.items,
                        effective_workspace_id,
                    )
                except Exception:
                    logger.warning(
                        "[Direct Commit] Failed to recompute conflicts after revision conflict",
                        exc_info=True,
                    )
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": (
                            "Schedule changed before apply completed. "
                            "Review the latest conflicts and re-plan before retrying."
                        ),
                        "reason": "schedule_revision_conflict",
                        "stale_detail": error_message,
                        "predicted_conflicts": current_conflicts,
                    },
                ) from exc
            if "Concurrent schedule conflict detected" in error_message:
                db.update_plan_status(plan.id, "superseded")
                duplicate_plan_id = _find_existing_direct_commit_plan(db, input_hash)
                if duplicate_plan_id and duplicate_plan_id != plan.id:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "message": (
                                "Duplicate commit detected. This exact schedule was already applied."
                            ),
                            "duplicate_plan_id": duplicate_plan_id,
                        },
                    ) from exc
                current_conflicts: List[Dict[str, Any]] = []
                try:
                    current_conflicts = _predict_direct_commit_conflicts(
                        db,
                        request.items,
                        effective_workspace_id,
                    )
                except Exception:
                    logger.warning(
                        "[Direct Commit] Failed to recompute conflicts after concurrent conflict",
                        exc_info=True,
                    )
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": (
                            "Schedule changed during apply and now conflicts with "
                            "another committed acquisition."
                        ),
                        "reason": "concurrent_schedule_conflict",
                        "stale_detail": error_message,
                        "predicted_conflicts": current_conflicts,
                    },
                ) from exc
            raise
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed: acquisitions." not in str(exc):
                raise
            duplicate_plan_id = _find_existing_direct_commit_plan(db, input_hash)
            db.update_plan_status(plan.id, "superseded")
            raise HTTPException(
                status_code=409,
                detail={
                    "message": (
                        "Duplicate commit detected. This exact schedule was already applied."
                    ),
                    "duplicate_plan_id": duplicate_plan_id or plan.id,
                },
            ) from exc

        # A concurrent identical request can slip past the pre-check if another
        # commit reaches persistence first. In that case the acquisition unique
        # index can still surface through lower layers; treat that as a duplicate
        # race instead of reporting a false success.
        if result["committed"] == 0:
            duplicate_plan_id = _find_existing_direct_commit_plan(db, input_hash)
            db.update_plan_status(plan.id, "superseded")
            raise HTTPException(
                status_code=409,
                detail={
                    "message": (
                        "Duplicate commit detected. This exact schedule was already applied."
                    ),
                    "duplicate_plan_id": duplicate_plan_id or plan.id,
                },
            )

        logger.info(
            f"[Direct Commit] Created and committed plan {plan.id}: "
            f"{result['committed']} acquisitions"
        )

        conflicts_detected = 0
        conflict_ids: List[str] = []
        now = datetime.now(timezone.utc)
        recompute_start, recompute_end = _derive_workspace_conflict_horizon(
            db,
            effective_workspace_id,
            fallback_start=now,
            fallback_end=now + timedelta(days=7),
        )
        detected_conflicts, new_conflict_ids = detect_and_persist_conflicts(
            db=db,
            workspace_id=effective_workspace_id,
            start_time=_isoformat_z(recompute_start),
            end_time=_isoformat_z(recompute_end),
        )
        conflicts_detected = len(detected_conflicts)
        conflict_ids = new_conflict_ids

        return DirectCommitResponse(
            success=True,
            message=f"Created {result['committed']} acquisitions",
            plan_id=plan.id,
            committed=result["committed"],
            acquisition_ids=[a["id"] for a in result["acquisitions_created"]],
            conflicts_detected=conflicts_detected,
            conflict_ids=conflict_ids,
        )

    except HTTPException:
        raise  # Don't swallow 409/4xx as 500
    except Exception as e:
        logger.error(f"Failed direct commit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Planning Mode Selection Endpoint
# =============================================================================


class PlanningModeSelectionRequest(BaseModel):
    """Request to resolve backend auto-mode selection without creating a plan."""

    planning_mode: str = Field(
        default="from_scratch",
        description="Optional override. Leave default to let backend auto-select.",
    )
    horizon_from: Optional[str] = Field(default=None, description="Horizon start (ISO)")
    horizon_to: Optional[str] = Field(default=None, description="Horizon end (ISO)")
    workspace_id: Optional[str] = Field(default=None, description="Workspace ID")
    weight_priority: float = Field(default=40.0, ge=0.0)
    weight_geometry: float = Field(default=40.0, ge=0.0)
    weight_timing: float = Field(default=20.0, ge=0.0)


class PlanningModeSelectionResponse(BaseModel):
    """Resolved planning mode and the backend reasoning behind it."""

    success: bool
    planning_mode: str
    reason: str
    workspace_id: str
    existing_acquisition_count: int = 0
    new_target_count: int = 0
    removed_scheduled_target_count: int = 0
    conflict_count: int = 0
    current_target_ids: List[str] = Field(default_factory=list)
    existing_target_ids: List[str] = Field(default_factory=list)
    request_payload_hash: str = ""


@router.post("/mode-selection", response_model=PlanningModeSelectionResponse)
async def get_planning_mode_selection(
    request: PlanningModeSelectionRequest,
) -> PlanningModeSelectionResponse:
    """Resolve planning mode using the same backend logic as the planning pipeline."""
    db = get_schedule_db()
    _bind_schedule_log_context(workspace_id=request.workspace_id)

    now = datetime.now(timezone.utc)

    if request.horizon_from:
        try:
            horizon_start = _to_utc_naive(
                datetime.fromisoformat(request.horizon_from.replace("Z", "+00:00"))
            )
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid horizon_from: {request.horizon_from}"
            )
    else:
        horizon_start = now.replace(tzinfo=None)

    if request.horizon_to:
        try:
            horizon_end = _to_utc_naive(
                datetime.fromisoformat(request.horizon_to.replace("Z", "+00:00"))
            )
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid horizon_to: {request.horizon_to}"
            )
    else:
        horizon_end = (now + timedelta(days=7)).replace(tzinfo=None)

    from backend.main import get_cached_opportunities, get_current_mission_data

    mission_data = get_current_mission_data(request.workspace_id).get("mission_data", {})
    raw_opportunities = get_cached_opportunities(request.workspace_id) or []

    request_hash = compute_request_hash(request.model_dump())
    mode_result, mode_context = _resolve_auto_mode_selection(
        db,
        workspace_id=request.workspace_id,
        planning_mode=request.planning_mode,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        raw_opportunities=raw_opportunities,
        mission_data=mission_data,
        request_payload_hash=request_hash,
        weight_priority=request.weight_priority,
        weight_geometry=request.weight_geometry,
        weight_timing=request.weight_timing,
    )

    return PlanningModeSelectionResponse(
        success=True,
        planning_mode=mode_result.mode,
        reason=mode_result.reason,
        workspace_id=mode_context["workspace_id"],
        existing_acquisition_count=mode_context["existing_acquisition_count"],
        new_target_count=mode_context["new_target_count"],
        removed_scheduled_target_count=mode_result.removed_scheduled_target_count,
        conflict_count=mode_context["conflict_count"],
        current_target_ids=mode_context["current_target_ids"],
        existing_target_ids=mode_context["existing_target_ids"],
        request_payload_hash=request_hash,
    )


# =============================================================================
# Incremental Planning Endpoint
# =============================================================================


class IncrementalPlanRequest(BaseModel):
    """Request for incremental planning."""

    # Planning mode
    planning_mode: str = Field(
        default="from_scratch",
        description="Planning mode: 'from_scratch', 'incremental', or 'repair'. "
        "Default auto-selects based on workspace state.",
    )

    # Horizon parameters
    horizon_from: Optional[str] = Field(
        default=None,
        description="Horizon start time (ISO format). Default: now",
    )
    horizon_to: Optional[str] = Field(
        default=None,
        description="Horizon end time (ISO format). Default: +7 days",
    )

    # Workspace and filtering
    workspace_id: Optional[str] = Field(
        default=None,
        description="Workspace ID to load existing acquisitions from",
    )
    include_tentative: bool = Field(
        default=False,
        description="Include tentative acquisitions as blocked intervals",
    )
    lock_policy: str = Field(
        default="respect_hard_only",
        description="Lock policy: 'respect_hard_only' or 'respect_hard_and_soft'",
    )

    # Planning parameters (forwarded to mission planner)
    imaging_time_s: float = Field(
        default=1.0, description="Imaging duration per target"
    )
    max_roll_rate_dps: float = Field(default=1.0, description="Max roll rate deg/s")
    max_roll_accel_dps2: float = Field(
        default=10000.0, description="Max roll acceleration"
    )
    max_pitch_rate_dps: float = Field(default=1.0, description="Max pitch rate deg/s")
    max_pitch_accel_dps2: float = Field(
        default=10000.0, description="Max pitch acceleration"
    )
    look_window_s: float = Field(default=600.0, description="Look-ahead window seconds")
    value_source: str = Field(
        default="target_priority", description="Value source for scoring"
    )
    weight_priority: float = Field(
        default=40.0, ge=0.0, description="Weight for target priority"
    )
    weight_geometry: float = Field(
        default=40.0, ge=0.0, description="Weight for imaging geometry quality"
    )
    weight_timing: float = Field(
        default=20.0, ge=0.0, description="Weight for timing preference"
    )


class ExistingAcquisitionsSummaryResponse(BaseModel):
    """Summary of existing acquisitions in horizon."""

    count: int = 0
    by_state: Dict[str, int] = Field(default_factory=dict)
    by_satellite: Dict[str, int] = Field(default_factory=dict)
    acquisition_ids: List[str] = Field(default_factory=list)
    horizon_start: Optional[str] = None
    horizon_end: Optional[str] = None


class PlanItemPreviewResponse(BaseModel):
    """Preview of a single plan item."""

    opportunity_id: str
    satellite_id: str
    target_id: str
    start_time: str
    end_time: str
    roll_angle_deg: float
    pitch_angle_deg: float = 0.0
    value: Optional[float] = None
    quality_score: Optional[float] = None
    incidence_angle_deg: Optional[float] = None


class CommitPreviewResponse(BaseModel):
    """Preview of what will happen on commit."""

    will_create: int = 0
    will_conflict_with: int = 0
    conflict_details: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class IncrementalPlanResponse(BaseModel):
    """Response from incremental planning endpoint."""

    success: bool
    message: str
    planning_mode: str
    existing_acquisitions: ExistingAcquisitionsSummaryResponse
    new_plan_items: List[PlanItemPreviewResponse] = Field(default_factory=list)
    conflicts_if_committed: List[Dict[str, Any]] = Field(default_factory=list)
    commit_preview: CommitPreviewResponse
    algorithm_metrics: Dict[str, Any] = Field(default_factory=dict)
    plan_id: Optional[str] = None
    schedule_context: Dict[str, Any] = Field(default_factory=dict)


@router.post("/plan", response_model=IncrementalPlanResponse)
async def create_incremental_plan(
    request: IncrementalPlanRequest,
) -> IncrementalPlanResponse:
    """
    Create a plan with incremental planning support.

    In incremental mode, this endpoint:
    1. Loads existing committed/locked acquisitions from the database
    2. Builds blocked intervals per satellite
    3. Filters candidate opportunities to avoid conflicts
    4. Runs planning on feasible opportunities only
    5. Returns plan + preview with conflict prediction

    Args:
        request: IncrementalPlanRequest with planning mode and parameters

    Returns:
        IncrementalPlanResponse with plan items and commit preview
    """
    from backend.incremental_planning import (
        IncrementalPlanningContext,
        LockPolicy,
        PlanningMode,
        SlewConfig,
        filter_opportunities_incremental,
        load_blocked_intervals,
        predict_commit_conflicts,
    )

    db = get_schedule_db()
    _bind_schedule_log_context(workspace_id=request.workspace_id)

    # Parse horizon times
    now = datetime.now(timezone.utc)

    if request.horizon_from:
        try:
            horizon_start = _to_utc_naive(
                datetime.fromisoformat(request.horizon_from.replace("Z", "+00:00"))
            )
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid horizon_from: {request.horizon_from}"
            )
    else:
        horizon_start = now.replace(tzinfo=None)

    if request.horizon_to:
        try:
            horizon_end = _to_utc_naive(
                datetime.fromisoformat(request.horizon_to.replace("Z", "+00:00"))
            )
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid horizon_to: {request.horizon_to}"
            )
    else:
        horizon_end = (now + timedelta(days=7)).replace(tzinfo=None)

    # Parse planning mode and lock policy
    try:
        planning_mode = PlanningMode(request.planning_mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid planning_mode: {request.planning_mode}. "
            f"Must be 'from_scratch', 'incremental', or 'repair'",
        )

    try:
        lock_policy = LockPolicy(request.lock_policy)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid lock_policy: {request.lock_policy}. "
            f"Must be 'respect_hard_only' or 'respect_hard_and_soft'",
        )

    # --- Audit trail (dev-only breadcrumbs) ---
    import uuid as _uuid

    _run_id = f"plan_{now.strftime('%Y%m%d_%H%M%S')}_{_uuid.uuid4().hex[:8]}"
    _audit = PipelineAuditTrail(
        run_id=_run_id, workspace_id=request.workspace_id or "default"
    )
    _bind_schedule_log_context(workspace_id=request.workspace_id, run_id=_run_id)
    _req_hash = compute_request_hash(request.model_dump())
    _audit.add(
        "request_received",
        planning_mode=planning_mode.value,
        workspace_id=request.workspace_id,
        horizon_start=horizon_start.isoformat(),
        horizon_end=horizon_end.isoformat(),
        request_hash=_req_hash,
    )

    logger.info(
        f"[Incremental Plan] mode={planning_mode.value}, "
        f"workspace={request.workspace_id}, "
        f"horizon={horizon_start.isoformat()} to {horizon_end.isoformat()}, "
        f"run_id={_run_id}, request_hash={_req_hash}"
    )

    # Initialize response components
    existing_summary = ExistingAcquisitionsSummaryResponse(
        horizon_start=_isoformat_z(horizon_start),
        horizon_end=_isoformat_z(horizon_end),
    )
    schedule_context: Dict[str, Any] = {
        "planning_mode": planning_mode.value,
        "lock_policy": lock_policy.value,
        "include_tentative": request.include_tentative,
    }

    # Get satellite agility from cached mission data (used for slew config)
    from backend.main import get_current_mission_data

    _current_mission = get_current_mission_data(request.workspace_id)
    _mission_data = _current_mission.get("mission_data", {})
    _sat_agility = _mission_data.get("satellite_agility", request.max_roll_rate_dps)
    _agility_source = (
        "config" if "satellite_agility" in _mission_data else "request default"
    )
    logger.info(
        f"[Plan] Using satellite agility: {_sat_agility}°/s (from {_agility_source})"
    )

    # Blocked intervals context — loaded after auto-mode selection below
    context: Optional[IncrementalPlanningContext] = None

    raw_opportunities: List[Dict[str, Any]] = []

    try:
        from datetime import datetime as _dt

        _cmd = _current_mission
        if _cmd and "passes" in _cmd:
            passes = _cmd["passes"]
            now_naive = now.replace(tzinfo=None)
            for idx, p in enumerate(passes):
                if isinstance(p, dict):
                    sat = p["satellite_name"]
                    tgt = p["target_name"]
                    met = p.get("max_elevation_time")
                    st = (
                        _dt.fromisoformat(met)
                        if met
                        else _dt.fromisoformat(p["start_time"])
                    )
                    inc = p.get("incidence_angle_deg")
                else:
                    sat = p.satellite_name
                    tgt = p.target_name
                    st = getattr(p, "max_elevation_time", None) or p.start_time
                    inc = getattr(p, "incidence_angle_deg", None)
                if hasattr(st, "tzinfo") and st.tzinfo is not None:
                    st = st.replace(tzinfo=None)
                if st < now_naive:
                    continue
                raw_opportunities.append(
                    {
                        "id": f"{sat}_{tgt}_{idx}",
                        "opportunity_id": f"{sat}_{tgt}_{idx}",
                        "satellite_id": sat,
                        "target_id": tgt,
                        "start_time": (
                            f"{st.isoformat()}Z"
                            if hasattr(st, "isoformat")
                            else str(st)
                        ),
                        "end_time": (
                            f"{st.isoformat()}Z"
                            if hasattr(st, "isoformat")
                            else str(st)
                        ),
                        "roll_angle_deg": inc if inc is not None else 0.0,
                        "pitch_angle_deg": 0.0,
                        "value": 1.0,
                    }
                )
            if raw_opportunities:
                logger.info(
                    f"[Incremental Plan] Loaded {len(raw_opportunities)} opportunities from current mission data"
                )
    except Exception as e:
        logger.warning(
            f"[Incremental Plan] Failed to build opportunities from mission data: {e}"
        )

    if not raw_opportunities:
        try:
            from backend.main import get_cached_opportunities

            raw_opportunities = get_cached_opportunities(request.workspace_id) or []
        except (ImportError, AttributeError):
            pass

    if raw_opportunities:
        deduped_opportunities: List[Dict[str, Any]] = []
        seen_opportunity_keys: set[tuple[str, str, str]] = set()
        for opp in raw_opportunities:
            opp_key = (
                opp.get("satellite_id", ""),
                opp.get("target_id", ""),
                opp.get("start_time", ""),
            )
            if opp_key in seen_opportunity_keys:
                continue
            seen_opportunity_keys.add(opp_key)
            deduped_opportunities.append(opp)
        raw_opportunities = deduped_opportunities

    if not raw_opportunities:
        logger.info(
            "[Incremental Plan] No cached opportunities - returning empty plan. "
            "Run mission analysis first to generate opportunities."
        )

    # =========================================================================
    # AUTO-MODE SELECTION: Determine planning mode from workspace state.
    # The client-sent mode is treated as a force override only when it
    # differs from the default "from_scratch".  Otherwise, the system
    # inspects existing acquisitions vs. current targets to auto-pick
    # FROM_SCRATCH / INCREMENTAL / REPAIR.
    # =========================================================================
    mode_result, mode_context = _resolve_auto_mode_selection(
        db,
        workspace_id=request.workspace_id,
        planning_mode=request.planning_mode,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        raw_opportunities=raw_opportunities,
        mission_data=_mission_data,
        request_payload_hash=_req_hash,
        weight_priority=request.weight_priority,
        weight_geometry=request.weight_geometry,
        weight_timing=request.weight_timing,
    )
    _auto_workspace = mode_context["workspace_id"]
    _active_existing = mode_context["active_existing"]
    _conflict_count = mode_context["conflict_count"]

    planning_mode = PlanningMode(mode_result.mode)
    _audit.add("mode_selection", **mode_result.to_log_dict())
    schedule_context["planning_mode"] = planning_mode.value
    schedule_context["mode_selection_reason"] = mode_result.reason
    schedule_context["existing_acquisition_count"] = mode_context["existing_acquisition_count"]
    schedule_context["new_target_count"] = mode_context["new_target_count"]
    schedule_context["conflict_count"] = _conflict_count

    logger.info(
        f"[Auto Mode] Selected: {planning_mode.value} | "
        f"existing={mode_context['existing_acquisition_count']}, "
        f"new_targets={mode_context['new_target_count']} | "
        f"reason={mode_result.reason[:100]}"
    )

    # Load blocked intervals for INCREMENTAL mode (must happen after mode selection)
    if planning_mode == PlanningMode.INCREMENTAL and request.workspace_id:
        context = load_blocked_intervals(
            db=db,
            workspace_id=request.workspace_id,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            lock_policy=lock_policy,
            include_tentative=request.include_tentative,
        )

        all_acq_ids = []
        by_satellite: Dict[str, int] = {}

        for sat_id, intervals in context.blocked_intervals.items():
            by_satellite[sat_id] = len(intervals)
            all_acq_ids.extend([i.acquisition_id for i in intervals])

        existing_summary = ExistingAcquisitionsSummaryResponse(
            count=context.loaded_acquisitions_count,
            by_state=context.loaded_acquisitions_by_state,
            by_satellite=by_satellite,
            acquisition_ids=all_acq_ids,
            horizon_start=_isoformat_z(horizon_start),
            horizon_end=_isoformat_z(horizon_end),
        )

        schedule_context["loaded_acquisitions"] = context.loaded_acquisitions_count
        schedule_context["blocked_satellites"] = list(context.blocked_intervals.keys())

        logger.info(
            f"[Incremental Plan] Loaded {context.loaded_acquisitions_count} blocked acquisitions"
        )

    # =========================================================================
    # TARGET DEDUP: Skip opportunities for targets that already have a future
    # acquisition in this workspace.  Past acquisitions (end_time < now) do NOT
    # block — the mission planner is allowed to re-schedule a target whose
    # previous pass is already in the past.
    # =========================================================================
    dedup_skipped: List[Dict[str, Any]] = []
    future_sat_targets = {(acq.satellite_id, acq.target_id) for acq in _active_existing}
    if raw_opportunities and future_sat_targets:
        filtered_opps: List[Dict[str, Any]] = []
        for opp in raw_opportunities:
            opp_sat = (
                opp.get("satellite_id", "")
                if isinstance(opp, dict)
                else getattr(opp, "satellite_id", "")
            )
            opp_tgt = (
                opp.get("target_id", "")
                if isinstance(opp, dict)
                else getattr(opp, "target_id", "")
            )
            if (opp_sat, opp_tgt) in future_sat_targets:
                dedup_skipped.append(
                    opp
                    if isinstance(opp, dict)
                    else {"satellite_id": opp_sat, "target_id": opp_tgt}
                )
            else:
                filtered_opps.append(opp)
        logger.info(
            f"[Plan] Target dedup: {len(dedup_skipped)} opportunities skipped "
            f"({len(future_sat_targets)} sat-target pairs already scheduled), "
            f"{len(filtered_opps)} remaining"
        )
        raw_opportunities = filtered_opps

    # Filter opportunities based on blocked intervals (incremental mode)
    feasible_opportunities: List[Any] = raw_opportunities
    rejected_opportunities: List[Dict[str, Any]] = []

    if context and planning_mode == PlanningMode.INCREMENTAL:
        # Convert opportunities to dict format for filtering
        opp_dicts = []
        for opp in raw_opportunities:
            if hasattr(opp, "to_dict"):
                opp_dicts.append(opp.to_dict())
            elif hasattr(opp, "__dict__"):
                opp_dicts.append(vars(opp))
            else:
                opp_dicts.append(opp)

        # Get satellite agility from cached mission data
        from backend.main import get_current_mission_data

        _mission_data = get_current_mission_data(request.workspace_id).get(
            "mission_data", {}
        )
        _sat_agility = _mission_data.get("satellite_agility", request.max_roll_rate_dps)
        _agility_source = (
            "config" if "satellite_agility" in _mission_data else "request default"
        )
        logger.info(
            f"[Incremental Plan] Using satellite agility: {_sat_agility}\u00b0/s (from {_agility_source})"
        )

        slew_config = SlewConfig(
            roll_slew_rate_deg_per_sec=_sat_agility,
            pitch_slew_rate_deg_per_sec=request.max_pitch_rate_dps,
            settling_time_s=5.0,
            parallel_slew=True,
        )

        feasible_dicts, rejected_dicts = filter_opportunities_incremental(
            opportunities=opp_dicts,
            context=context,
            slew_config=slew_config,
        )

        # Map back to opportunity objects if needed
        feasible_opportunities: List[Any] = feasible_dicts  # type: ignore[no-redef]
        rejected_opportunities = rejected_dicts

        schedule_context["opportunities_total"] = len(raw_opportunities)
        schedule_context["opportunities_feasible"] = len(feasible_opportunities)
        schedule_context["opportunities_rejected"] = len(rejected_opportunities)

        logger.info(
            f"[Incremental Plan] Filtered: {len(feasible_opportunities)} feasible, "
            f"{len(rejected_opportunities)} rejected"
        )

    # Run planning on feasible opportunities
    # For now, we'll create plan items directly from feasible opportunities
    # In a full implementation, this would call the mission scheduler

    import hashlib
    import uuid

    run_id = f"run_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    input_hash = f"sha256:{hashlib.sha256(run_id.encode()).hexdigest()[:16]}"

    # BUG FIX (PR_SCHED_001): Always propagate workspace_id to plans.
    # Previously, effective_workspace_id was set to None for from_scratch plans
    # (no existing acquisitions loaded). This caused acquisitions committed from
    # those plans to have NULL workspace_id, leaking into ALL workspace queries
    # via the "OR workspace_id IS NULL" fallback in persistence layer queries.
    effective_workspace_id = request.workspace_id or "default"

    # Create plan record
    plan = db.create_plan(
        algorithm="roll_pitch_best_fit",
        config={
            "planning_mode": planning_mode.value,
            "lock_policy": lock_policy.value,
            "workspace_id": request.workspace_id,
            "imaging_time_s": request.imaging_time_s,
        },
        input_hash=input_hash,
        run_id=run_id,
        metrics={
            "total_opportunities": len(raw_opportunities),
            "feasible_opportunities": len(feasible_opportunities),
            "rejected_opportunities": len(rejected_opportunities),
        },
        workspace_id=effective_workspace_id,
    )
    _bind_schedule_log_context(
        workspace_id=effective_workspace_id,
        run_id=_run_id,
        plan_id=plan.id,
    )

    if request.workspace_id:
        try:
            ws_db = get_workspace_db()
            workspace = ws_db.get_workspace(request.workspace_id, include_czml=False)
            if workspace:
                planning_state = dict(workspace.planning_state or {})
                planning_state.update(
                    {
                        "current_target_ids": mode_context["current_target_ids"],
                        "last_planning_mode": planning_mode.value,
                        "last_plan_id": plan.id,
                        "last_schedule_context": {
                            "existing_acquisition_count": mode_context[
                                "existing_acquisition_count"
                            ],
                            "new_target_count": mode_context["new_target_count"],
                            "conflict_count": _conflict_count,
                        },
                    }
                )
                ws_db.update_workspace(
                    workspace_id=request.workspace_id,
                    planning_state=planning_state,
                )
        except Exception as e:
            logger.warning(f"[Plan] Failed to persist workspace planning state: {e}")

    # Create plan items from feasible opportunities
    new_items: List[PlanItemPreviewResponse] = []

    for opp in feasible_opportunities[:100]:
        # Extract fields from opportunity (handle both dict and object)
        opp_item: Any = opp  # Allow type checker to see both branches
        if isinstance(opp_item, dict):
            opp_id = opp_item.get(
                "id", opp_item.get("opportunity_id", f"opp_{uuid.uuid4().hex[:8]}")
            )
            sat_id = opp_item.get("satellite_id", "unknown")
            target_id = opp_item.get("target_id", "unknown")
            start_time = opp_item.get("start_time", "")
            end_time = opp_item.get("end_time", "")
            roll_deg = opp_item.get("roll_angle_deg", opp_item.get("roll_angle", 0.0))
            pitch_deg = opp_item.get(
                "pitch_angle_deg", opp_item.get("pitch_angle", 0.0)
            )
            value = opp_item.get("value", 1.0)
            quality = opp_item.get("quality_score", opp_item.get("quality", None))
            incidence = opp_item.get(
                "incidence_angle_deg", opp_item.get("incidence_angle", None)
            )
        else:
            opp_id = getattr(opp_item, "id", f"opp_{uuid.uuid4().hex[:8]}")
            sat_id = getattr(opp_item, "satellite_id", "unknown")
            target_id = getattr(opp_item, "target_id", "unknown")
            start_time = getattr(opp_item, "start_time", "")
            end_time = getattr(opp_item, "end_time", "")
            roll_deg = getattr(
                opp_item, "roll_angle_deg", getattr(opp_item, "roll_angle", 0.0)
            )
            pitch_deg = getattr(
                opp_item, "pitch_angle_deg", getattr(opp_item, "pitch_angle", 0.0)
            )
            value = getattr(opp_item, "value", 1.0)
            quality = getattr(
                opp_item, "quality_score", getattr(opp_item, "quality", None)
            )
            incidence = getattr(
                opp_item,
                "incidence_angle_deg",
                getattr(opp_item, "incidence_angle", None),
            )

        # Create plan item in database
        db.create_plan_item(
            plan_id=plan.id,
            opportunity_id=str(opp_id),
            satellite_id=sat_id,
            target_id=target_id,
            start_time=start_time,
            end_time=end_time,
            roll_angle_deg=float(roll_deg) if roll_deg else 0.0,
            pitch_angle_deg=float(pitch_deg) if pitch_deg else 0.0,
            value=float(value) if value else None,
            quality_score=float(quality) if quality else None,
        )

        # Add to response
        new_items.append(
            PlanItemPreviewResponse(
                opportunity_id=str(opp_id),
                satellite_id=sat_id,
                target_id=target_id,
                start_time=start_time,
                end_time=end_time,
                roll_angle_deg=float(roll_deg) if roll_deg else 0.0,
                pitch_angle_deg=float(pitch_deg) if pitch_deg else 0.0,
                value=float(value) if value else None,
                quality_score=float(quality) if quality else None,
                incidence_angle_deg=float(incidence) if incidence else None,
            )
        )

    # Predict conflicts if committed
    conflicts_if_committed: List[Dict[str, Any]] = []

    if request.workspace_id and new_items:
        # Convert new_items to dicts for conflict prediction
        new_item_dicts = [
            {
                "satellite_id": item.satellite_id,
                "target_id": item.target_id,
                "start_time": item.start_time,
                "end_time": item.end_time,
                "roll_angle_deg": item.roll_angle_deg,
                "pitch_angle_deg": item.pitch_angle_deg,
            }
            for item in new_items
        ]

        conflicts_if_committed, conflict_count = predict_commit_conflicts(
            db=db,
            workspace_id=request.workspace_id,
            new_items=new_item_dicts,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
        )

        logger.info(
            f"[Incremental Plan] Predicted {conflict_count} conflicts if committed"
        )

    # Build commit preview
    error_conflicts = [
        c for c in conflicts_if_committed if c.get("severity") == "error"
    ]
    warning_conflicts = [
        c for c in conflicts_if_committed if c.get("severity") == "warning"
    ]

    commit_preview = CommitPreviewResponse(
        will_create=len(new_items),
        will_conflict_with=len(error_conflicts),
        conflict_details=error_conflicts,
        warnings=[
            f"Warning: {c.get('description', 'Unknown conflict')}"
            for c in warning_conflicts
        ],
    )

    # Build algorithm metrics
    algorithm_metrics = {
        "algorithm": "roll_pitch_best_fit",
        "total_opportunities": len(raw_opportunities),
        "feasible_after_filter": len(feasible_opportunities),
        "rejected_by_filter": len(rejected_opportunities),
        "plan_items_created": len(new_items),
        "predicted_conflicts": len(conflicts_if_committed),
    }

    message = f"Created plan with {len(new_items)} items"
    if planning_mode == PlanningMode.INCREMENTAL:
        message += (
            f" (incremental: avoided {existing_summary.count} existing acquisitions)"
        )
    if error_conflicts:
        message += f" - WARNING: {len(error_conflicts)} predicted conflicts"

    # --- Audit trail: finalize ---
    _audit.add(
        "plan_created",
        plan_id=plan.id,
        planning_mode=planning_mode.value,
        new_items_count=len(new_items),
        feasible_opportunities=len(feasible_opportunities),
        conflicts_predicted=len(conflicts_if_committed),
    )
    _audit.finalize()

    return IncrementalPlanResponse(
        success=True,
        message=f"Plan created: {len(new_items)} items from {len(feasible_opportunities)} feasible opportunities",
        planning_mode=planning_mode.value,
        existing_acquisitions=existing_summary,
        new_plan_items=new_items,
        conflicts_if_committed=conflicts_if_committed,
        commit_preview=commit_preview,
        algorithm_metrics=algorithm_metrics,
        plan_id=plan.id,
        schedule_context=schedule_context,
    )


# =============================================================================
# Repair Planning Endpoint
# =============================================================================


class RepairPlanRequestModel(BaseModel):
    """Request for repair planning."""

    planning_mode: str = Field(default="repair", description="Must be 'repair'")
    horizon_from: Optional[str] = Field(default=None, description="Horizon start (ISO)")
    horizon_to: Optional[str] = Field(default=None, description="Horizon end (ISO)")
    workspace_id: Optional[str] = Field(default=None, description="Workspace ID")
    include_tentative: bool = Field(default=True, description="Include tentative acqs")

    # Repair-specific
    # PR-OPS-REPAIR-DEFAULT-01: Full flexibility defaults
    repair_scope: str = Field(
        default="workspace_horizon",
        description="'workspace_horizon', 'satellite_subset', or 'target_subset'",
    )
    max_changes: int = Field(default=100, ge=0, description="Max changes allowed")
    objective: str = Field(
        default="maximize_score",
        description="'maximize_score', 'maximize_priority', or 'minimize_changes'",
    )

    # Scope filters
    satellite_subset: List[str] = Field(default_factory=list)
    target_subset: List[str] = Field(default_factory=list)

    # Per-target priorities (target_name → priority 1-5, 1=highest)
    # Used to re-score cached opportunities with current priorities
    target_priorities: Dict[str, int] = Field(
        default_factory=dict,
        description="Map of target name to priority (1=highest, 5=lowest). "
        "When provided, cached opportunity values are re-scored with these priorities.",
    )

    # Scoring weights (passed from frontend weightConfig)
    weight_priority: float = Field(
        default=40.0, description="Weight for target priority"
    )
    weight_geometry: float = Field(
        default=40.0, description="Weight for geometry quality"
    )
    weight_timing: float = Field(
        default=20.0, description="Weight for timing preference"
    )

    # Planning parameters
    imaging_time_s: float = Field(default=1.0)
    max_roll_rate_dps: float = Field(default=1.0)
    max_roll_accel_dps2: float = Field(default=10000.0)
    max_pitch_rate_dps: float = Field(default=1.0)
    max_pitch_accel_dps2: float = Field(default=10000.0)
    look_window_s: float = Field(default=600.0)
    value_source: str = Field(default="target_priority")


class MovedAcquisitionInfoResponse(BaseModel):
    """Info about a moved acquisition."""

    id: str
    from_start: str
    from_end: str
    to_start: str
    to_end: str
    from_roll_deg: Optional[float] = None
    to_roll_deg: Optional[float] = None


class ChangeScoreResponse(BaseModel):
    """Summary of changes made."""

    num_changes: int = 0
    percent_changed: float = 0.0


class RepairDiffResponse(BaseModel):
    """Diff showing what changed during repair."""

    kept: List[str] = Field(default_factory=list)
    dropped: List[str] = Field(default_factory=list)
    added: List[str] = Field(default_factory=list)
    moved: List[MovedAcquisitionInfoResponse] = Field(default_factory=list)
    reason_summary: Dict[str, List[Dict[str, str]]] = Field(default_factory=dict)
    change_score: ChangeScoreResponse = Field(default_factory=ChangeScoreResponse)
    hard_lock_warnings: List[str] = Field(
        default_factory=list,
        description="Warnings about hard-locked acquisitions that could not be resolved",
    )
    # PR-OPS-REPAIR-REPORT-01: Structured change log
    change_log: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured change log with dropped/added/moved entries and reason_codes",
    )


class MetricsComparisonResponse(BaseModel):
    """Before vs after metrics."""

    score_before: float = 0.0
    score_after: float = 0.0
    score_delta: float = 0.0
    mean_incidence_before: Optional[float] = None
    mean_incidence_after: Optional[float] = None
    conflicts_before: int = 0
    conflicts_after: int = 0
    acquisition_count_before: int = 0
    acquisition_count_after: int = 0


class RepairPlanResponseModel(BaseModel):
    """Response from repair planning endpoint."""

    success: bool
    message: str
    planning_mode: str = "repair"

    # Schedule context
    existing_acquisitions: ExistingAcquisitionsSummaryResponse
    fixed_count: int = 0
    flex_count: int = 0

    # Proposed schedule
    new_plan_items: List[PlanItemPreviewResponse] = Field(default_factory=list)

    # Repair diff (critical)
    repair_diff: RepairDiffResponse = Field(default_factory=RepairDiffResponse)

    # Metrics comparison
    metrics_before: Dict[str, Any] = Field(default_factory=dict)
    metrics_after: Dict[str, Any] = Field(default_factory=dict)
    metrics_comparison: MetricsComparisonResponse = Field(
        default_factory=MetricsComparisonResponse
    )

    # Conflict prediction
    conflicts_if_committed: List[Dict[str, Any]] = Field(default_factory=list)

    # Commit preview
    commit_preview: CommitPreviewResponse = Field(default_factory=CommitPreviewResponse)

    # Algorithm metrics
    algorithm_metrics: Dict[str, Any] = Field(default_factory=dict)
    plan_id: Optional[str] = None
    schedule_context: Dict[str, Any] = Field(default_factory=dict)

    # Planner-facing summary: per-target details for intelligent narrative
    planner_summary: Dict[str, Any] = Field(default_factory=dict)


@router.post("/repair", response_model=RepairPlanResponseModel)
async def create_repair_plan(
    request: RepairPlanRequestModel,
) -> RepairPlanResponseModel:
    """
    Create a repair plan that modifies an existing schedule.

    Repair mode:
    1. Loads existing acquisitions and partitions into fixed (hard-locked) and flex (unlocked)
    2. Hard-locked items are immutable
    3. Unlocked items may be replaced with better opportunities
    4. Fills gaps with new opportunities
    5. Returns a diff showing kept/dropped/added/moved items

    Args:
        request: RepairPlanRequestModel with repair parameters

    Returns:
        RepairPlanResponseModel with proposed schedule and diff
    """
    from backend.incremental_planning import (
        RepairObjective,
        RepairScope,
        SlewConfig,
        execute_repair_planning,
        load_repair_context,
        predict_commit_conflicts,
    )

    db = get_schedule_db()
    _bind_schedule_log_context(workspace_id=request.workspace_id)

    # Parse horizon times
    now = datetime.now(timezone.utc)
    workspace_horizon_start: Optional[datetime] = None
    workspace_horizon_end: Optional[datetime] = None

    if request.workspace_id and (not request.horizon_from or not request.horizon_to):
        workspace_acquisitions = db.list_acquisitions(
            workspace_id=request.workspace_id,
            include_tentative=request.include_tentative,
            limit=2000,
        )
        acquisition_starts: List[datetime] = []
        acquisition_ends: List[datetime] = []
        for acquisition in workspace_acquisitions:
            try:
                start_dt = datetime.fromisoformat(
                    acquisition.start_time.replace("Z", "+00:00")
                )
                end_dt = datetime.fromisoformat(
                    acquisition.end_time.replace("Z", "+00:00")
                )
            except ValueError:
                continue
            if start_dt.tzinfo is not None:
                start_dt = start_dt.replace(tzinfo=None)
            if end_dt.tzinfo is not None:
                end_dt = end_dt.replace(tzinfo=None)
            acquisition_starts.append(start_dt)
            acquisition_ends.append(end_dt)
        if acquisition_starts and acquisition_ends:
            workspace_horizon_start = min(acquisition_starts) - timedelta(minutes=5)
            workspace_horizon_end = max(acquisition_ends) + timedelta(minutes=5)

    if request.horizon_from:
        try:
            horizon_start = datetime.fromisoformat(
                request.horizon_from.replace("Z", "+00:00")
            )
            if horizon_start.tzinfo is not None:
                horizon_start = horizon_start.replace(tzinfo=None)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid horizon_from: {request.horizon_from}"
            )
    elif workspace_horizon_start is not None:
        horizon_start = workspace_horizon_start
    else:
        horizon_start = now.replace(tzinfo=None)

    if request.horizon_to:
        try:
            horizon_end = datetime.fromisoformat(
                request.horizon_to.replace("Z", "+00:00")
            )
            if horizon_end.tzinfo is not None:
                horizon_end = horizon_end.replace(tzinfo=None)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid horizon_to: {request.horizon_to}"
            )
    elif workspace_horizon_end is not None:
        horizon_end = workspace_horizon_end
    else:
        horizon_end = (now + timedelta(days=7)).replace(tzinfo=None)

    # Parse enums
    try:
        repair_scope = RepairScope(request.repair_scope)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid repair_scope: {request.repair_scope}. "
            f"Must be 'workspace_horizon', 'satellite_subset', or 'target_subset'",
        )

    try:
        objective = RepairObjective(request.objective)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid objective: {request.objective}. "
            f"Must be 'maximize_score', 'maximize_priority', or 'minimize_changes'",
        )

    # --- Audit trail (dev-only breadcrumbs) ---
    import uuid as _uuid

    _run_id = f"repair_{now.strftime('%Y%m%d_%H%M%S')}_{_uuid.uuid4().hex[:8]}"
    _audit = PipelineAuditTrail(
        run_id=_run_id, workspace_id=request.workspace_id or "default"
    )
    _bind_schedule_log_context(workspace_id=request.workspace_id, run_id=_run_id)
    _req_hash = compute_request_hash(request.model_dump())
    _audit.add(
        "request_received",
        planning_mode="repair",
        workspace_id=request.workspace_id,
        repair_scope=repair_scope.value,
        objective=objective.value,
        max_changes=request.max_changes,
        request_hash=_req_hash,
    )

    logger.info(
        f"[Repair Plan] workspace={request.workspace_id}, "
        f"scope={repair_scope.value}, "
        f"max_changes={request.max_changes}, objective={objective.value}, "
        f"run_id={_run_id}, request_hash={_req_hash}"
    )

    # Stage A: Load and partition acquisitions
    repair_context = load_repair_context(
        db=db,
        workspace_id=request.workspace_id or "default",
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        repair_scope=repair_scope,
        satellite_subset=request.satellite_subset or None,
        target_subset=request.target_subset or None,
        include_tentative=request.include_tentative,
    )

    # Build existing acquisitions summary
    all_acq_ids = [i.acquisition_id for i in repair_context.fixed_set] + [
        f.acquisition_id for f in repair_context.flex_set
    ]
    by_satellite: Dict[str, int] = {}
    for interval in repair_context.fixed_set:
        by_satellite[interval.satellite_id] = (
            by_satellite.get(interval.satellite_id, 0) + 1
        )
    for flex in repair_context.flex_set:
        by_satellite[flex.satellite_id] = by_satellite.get(flex.satellite_id, 0) + 1

    existing_summary = ExistingAcquisitionsSummaryResponse(
        count=repair_context.original_acquisition_count,
        by_state={
            "fixed": len(repair_context.fixed_set),
            "flex": len(repair_context.flex_set),
        },
        by_satellite=by_satellite,
        acquisition_ids=all_acq_ids,
        horizon_start=_isoformat_z(horizon_start),
        horizon_end=_isoformat_z(horizon_end),
    )

    # Get opportunities from cache
    raw_opportunities: List[Dict[str, Any]] = []
    current_mission_snapshot: Dict[str, Any] = {}
    current_target_ids: Optional[set[str]] = None
    effective_target_priorities: Dict[str, int] = dict(request.target_priorities or {})
    try:
        from backend.main import get_cached_opportunities, get_current_mission_data

        current_mission_snapshot = get_current_mission_data(request.workspace_id) or {}
        raw_opportunities = get_cached_opportunities(request.workspace_id) or []
    except (ImportError, AttributeError):
        pass

    # Fallback: read from current_mission_data if opportunities_cache is empty
    if not raw_opportunities:
        try:
            from datetime import datetime as _dt

            _cmd = current_mission_snapshot or {}
            if _cmd and "passes" in _cmd:
                passes = _cmd["passes"]
                for idx, p in enumerate(passes):
                    if isinstance(p, dict):
                        sat = p["satellite_name"]
                        tgt = p["target_name"]
                        # Use max_elevation_time as the imaging point (not full pass window)
                        met = p.get("max_elevation_time")
                        st = (
                            _dt.fromisoformat(met)
                            if met
                            else _dt.fromisoformat(p["start_time"])
                        )
                        et = st  # Point-in-time imaging opportunity
                        inc = p.get("incidence_angle_deg")
                    else:
                        sat = p.satellite_name
                        tgt = p.target_name
                        # Use max_elevation_time as the imaging point (not full pass window)
                        st = getattr(p, "max_elevation_time", None) or p.start_time
                        et = st  # Point-in-time imaging opportunity
                        inc = getattr(p, "incidence_angle_deg", None)
                    raw_opportunities.append(
                        {
                            "id": f"{sat}_{tgt}_{idx}",
                            "opportunity_id": f"{sat}_{tgt}_{idx}",
                            "satellite_id": sat,
                            "target_id": tgt,
                            "start_time": (
                                st.isoformat() if hasattr(st, "isoformat") else str(st)
                            ),
                            "end_time": (
                                et.isoformat() if hasattr(et, "isoformat") else str(et)
                            ),
                            "roll_angle_deg": inc if inc is not None else 0.0,
                            "pitch_angle_deg": 0.0,
                            "value": 1.0,
                        }
                    )
                logger.info(
                    f"[Repair Plan] Loaded {len(raw_opportunities)} opportunities from mission analysis fallback"
                )
        except Exception as e:
            logger.warning(f"[Repair Plan] Failed to load mission data fallback: {e}")

    if not raw_opportunities:
        logger.info(
            "[Repair Plan] No cached opportunities - repair will only adjust existing items"
        )

    mission_scope = current_mission_snapshot.get("mission_data", current_mission_snapshot)
    if not isinstance(mission_scope, dict):
        mission_scope = {}

    derived_target_ids = _build_current_target_ids(mission_scope, raw_opportunities)
    if derived_target_ids or "targets" in mission_scope:
        current_target_ids = derived_target_ids
    elif request.target_subset:
        current_target_ids = set(request.target_subset)

    derived_priorities = _build_target_priorities(mission_scope)
    if derived_priorities:
        effective_target_priorities = {
            **derived_priorities,
            **effective_target_priorities,
        }

    # Re-score opportunity values with current target priorities
    if effective_target_priorities and raw_opportunities:
        from src.mission_planner.quality_scoring import (
            MultiCriteriaWeights,
            compute_composite_value,
        )

        rescore_weights = MultiCriteriaWeights(
            priority=request.weight_priority,
            geometry=request.weight_geometry,
            timing=request.weight_timing,
        )
        rescored_count = 0
        for opp in raw_opportunities:
            tid = opp.get("target_id", "")
            if tid in effective_target_priorities:
                new_priority = float(effective_target_priorities[tid])
                old_priority = float(opp.get("priority", 5))
                quality = float(opp.get("quality_score") or 0.5)
                # Timing score not cached — use 0.5 as neutral default
                timing = 0.5
                new_value = compute_composite_value(
                    priority=new_priority,
                    quality_score=quality,
                    timing_score=timing,
                    weights=rescore_weights,
                )
                if new_priority != old_priority:
                    rescored_count += 1
                opp["value"] = new_value
                opp["priority"] = int(new_priority)
        if rescored_count > 0:
            logger.info(
                f"[Repair Plan] Re-scored {rescored_count} opportunities with updated target priorities"
            )

    # Configure slew
    slew_config = SlewConfig(
        roll_slew_rate_deg_per_sec=request.max_roll_rate_dps,
        pitch_slew_rate_deg_per_sec=request.max_pitch_rate_dps,
        settling_time_s=5.0,
        parallel_slew=True,
    )

    # Stage B & C: Execute repair planning
    proposed_schedule, repair_diff, metrics = execute_repair_planning(
        repair_context=repair_context,
        opportunities=raw_opportunities,
        max_changes=request.max_changes,
        objective=objective,
        slew_config=slew_config,
        target_priorities=effective_target_priorities or None,
        active_target_ids=current_target_ids,
    )

    # Create plan record
    import hashlib
    import uuid

    run_id = f"repair_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    input_hash = f"sha256:{hashlib.sha256(run_id.encode()).hexdigest()[:16]}"

    # BUG FIX (PR_SCHED_001): Always propagate workspace_id — see /plan fix above.
    effective_workspace_id = request.workspace_id or "default"

    plan = db.create_plan(
        algorithm="repair_mode",
        config={
            "planning_mode": "repair",
            "repair_scope": repair_scope.value,
            "objective": objective.value,
            "max_changes": request.max_changes,
            "workspace_id": request.workspace_id,
        },
        input_hash=input_hash,
        run_id=run_id,
        metrics=metrics,
        workspace_id=effective_workspace_id,
    )
    _bind_schedule_log_context(
        workspace_id=effective_workspace_id,
        run_id=_run_id,
        plan_id=plan.id,
    )

    # Persist newly created repair acquisitions as plan items so /repair/commit
    # has concrete rows to apply atomically.
    added_ids_set = set(repair_diff.added)
    persisted_plan_items = 0
    for item in proposed_schedule:
        candidate_id = item.get("opportunity_id", item.get("acquisition_id", ""))
        if item.get("action") != "added" and candidate_id not in added_ids_set:
            continue

        db.create_plan_item(
            plan_id=plan.id,
            opportunity_id=candidate_id,
            satellite_id=item.get("satellite_id", ""),
            target_id=item.get("target_id", ""),
            start_time=item.get("start_time", ""),
            end_time=item.get("end_time", ""),
            roll_angle_deg=item.get("roll_angle_deg", 0.0),
            pitch_angle_deg=item.get("pitch_angle_deg", 0.0),
            value=item.get("value", 1.0),
            quality_score=item.get("quality_score"),
        )
        persisted_plan_items += 1

    if persisted_plan_items:
        logger.info(
            "[Repair Plan] Persisted %d repair plan item(s) for commit",
            persisted_plan_items,
        )

    # Build plan items for response
    new_items: List[PlanItemPreviewResponse] = []
    for item in proposed_schedule:
        new_items.append(
            PlanItemPreviewResponse(
                opportunity_id=item.get(
                    "opportunity_id", item.get("acquisition_id", "")
                ),
                satellite_id=item.get("satellite_id", ""),
                target_id=item.get("target_id", ""),
                start_time=item.get("start_time", ""),
                end_time=item.get("end_time", ""),
                roll_angle_deg=item.get("roll_angle_deg", 0.0),
                pitch_angle_deg=item.get("pitch_angle_deg", 0.0),
                value=item.get("value"),
                quality_score=item.get("quality_score"),
                incidence_angle_deg=item.get("incidence_angle_deg"),
            )
        )

    # Predict conflicts if committed
    # Only check genuinely NEW items (added), not kept/moved items already in DB
    conflicts_if_committed: List[Dict[str, Any]] = []
    added_ids = set(repair_diff.added)
    truly_new_items = [
        item
        for item, sched in zip(new_items, proposed_schedule)
        if sched.get("action") == "added"
        or sched.get("acquisition_id", sched.get("opportunity_id", "")) in added_ids
    ]
    if request.workspace_id and truly_new_items:
        new_item_dicts = [
            {
                "satellite_id": item.satellite_id,
                "target_id": item.target_id,
                "start_time": item.start_time,
                "end_time": item.end_time,
                "roll_angle_deg": item.roll_angle_deg,
                "pitch_angle_deg": item.pitch_angle_deg,
            }
            for item in truly_new_items
        ]
        conflicts_if_committed, _ = predict_commit_conflicts(
            db=db,
            workspace_id=request.workspace_id,
            new_items=new_item_dicts,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
        )

    # Build metrics comparison
    score_before = repair_context.original_score
    score_after = sum(item.get("value", 1.0) for item in proposed_schedule)
    metrics_comparison = MetricsComparisonResponse(
        score_before=score_before,
        score_after=score_after,
        score_delta=score_after - score_before,
        conflicts_before=repair_context.original_conflict_count,
        conflicts_after=len(conflicts_if_committed),
        acquisition_count_before=repair_context.original_acquisition_count,
        acquisition_count_after=len(proposed_schedule),
    )

    # Build repair diff response
    repair_diff_response = RepairDiffResponse(
        kept=repair_diff.kept,
        dropped=repair_diff.dropped,
        added=repair_diff.added,
        moved=[
            MovedAcquisitionInfoResponse(
                id=m.id,
                from_start=m.from_start,
                from_end=m.from_end,
                to_start=m.to_start,
                to_end=m.to_end,
                from_roll_deg=m.from_roll_deg,
                to_roll_deg=m.to_roll_deg,
            )
            for m in repair_diff.moved
        ],
        reason_summary=repair_diff.reason_summary,
        change_score=ChangeScoreResponse(
            num_changes=repair_diff.change_score.num_changes,
            percent_changed=repair_diff.change_score.percent_changed,
        ),
        hard_lock_warnings=repair_diff.hard_lock_warnings,
        change_log=repair_diff.change_log,
    )

    # Build commit preview
    error_conflicts = [
        c for c in conflicts_if_committed if c.get("severity") == "error"
    ]
    commit_preview = CommitPreviewResponse(
        will_create=len(repair_diff.added),
        will_conflict_with=len(error_conflicts),
        conflict_details=error_conflicts,
        warnings=(
            [
                f"Dropping {len(repair_diff.dropped)} acquisitions",
            ]
            if repair_diff.dropped
            else []
        ),
    )

    # Build schedule context
    schedule_context = {
        "planning_mode": "repair",
        "repair_scope": repair_scope.value,
        "objective": objective.value,
        "max_changes": request.max_changes,
        "fixed_count": len(repair_context.fixed_set),
        "flex_count": len(repair_context.flex_set),
        "opportunities_available": len(raw_opportunities),
    }

    message = (
        f"Repair plan: {len(repair_diff.kept)} kept, "
        f"{len(repair_diff.dropped)} dropped, {len(repair_diff.added)} added. "
        f"Changes: {repair_diff.change_score.num_changes}/{request.max_changes}"
    )
    if error_conflicts:
        message += f" - WARNING: {len(error_conflicts)} predicted conflicts"

    logger.info(f"[Repair Plan] {message}")

    # ── Build planner_summary: per-target details for intelligent narrative ──
    # Scheduled targets: which satellite, when, action (kept/added)
    kept_ids = set(repair_diff.kept)
    added_ids_set = set(repair_diff.added)

    target_acquisitions: List[Dict[str, Any]] = []
    scheduled_target_ids: set[str] = set()
    satellites_used: set[str] = set()

    for item in proposed_schedule:
        tid = item.get("target_id", "")
        sid = item.get("satellite_id", "")
        acq_id = item.get("acquisition_id", item.get("opportunity_id", ""))

        action = "kept" if acq_id in kept_ids else "added"
        scheduled_target_ids.add(tid)
        satellites_used.add(sid)

        target_acquisitions.append(
            {
                "target_id": tid,
                "satellite_id": sid,
                "start_time": item.get("start_time", ""),
                "end_time": item.get("end_time", ""),
                "action": action,
            }
        )

    # All targets that had opportunities (from feasibility)
    all_opp_targets: set[str] = set()
    for opp in raw_opportunities:
        all_opp_targets.add(opp.get("target_id", ""))

    # Targets with opportunities but not scheduled
    targets_not_scheduled: List[Dict[str, str]] = []
    for tid in sorted(all_opp_targets - scheduled_target_ids):
        targets_not_scheduled.append(
            {
                "target_id": tid,
                "reason": "Lower priority or no feasible slot after scheduling constraints",
            }
        )

    planner_summary = {
        "target_acquisitions": target_acquisitions,
        "targets_not_scheduled": targets_not_scheduled,
        "horizon": {
            "start": _isoformat_z(horizon_start),
            "end": _isoformat_z(horizon_end),
        },
        "satellites_used": sorted(satellites_used),
        "total_targets_with_opportunities": len(all_opp_targets),
        "total_targets_covered": len(scheduled_target_ids),
    }

    # --- Audit trail: finalize ---
    _audit.add(
        "repair_plan_created",
        plan_id=plan.id,
        kept_count=len(repair_diff.kept),
        dropped_count=len(repair_diff.dropped),
        added_count=len(repair_diff.added),
        moved_count=len(repair_diff.moved),
        score_before=score_before,
        score_after=score_after,
        conflicts_predicted=len(conflicts_if_committed),
    )
    _audit.finalize()

    return RepairPlanResponseModel(
        success=True,
        message=message,
        planning_mode="repair",
        existing_acquisitions=existing_summary,
        fixed_count=len(repair_context.fixed_set),
        flex_count=len(repair_context.flex_set),
        new_plan_items=new_items,
        repair_diff=repair_diff_response,
        metrics_before={
            "score": score_before,
            "count": repair_context.original_acquisition_count,
        },
        metrics_after={"score": score_after, "count": len(proposed_schedule)},
        metrics_comparison=metrics_comparison,
        conflicts_if_committed=conflicts_if_committed,
        commit_preview=commit_preview,
        algorithm_metrics=metrics,
        plan_id=plan.id,
        schedule_context=schedule_context,
        planner_summary=planner_summary,
    )


# =============================================================================
# Repair Commit Endpoint (Atomic with Audit Trail)
# =============================================================================


class RepairCommitRequest(BaseModel):
    """Request to commit a repair plan."""

    plan_id: str = Field(..., description="Plan ID to commit")
    workspace_id: str = Field(..., description="Workspace ID")
    drop_acquisition_ids: List[str] = Field(
        default_factory=list, description="Acquisition IDs to drop"
    )
    lock_level: str = Field(
        default="none", description="Lock level for new acquisitions: none | hard"
    )
    mode: str = Field(default="OPTICAL", description="Mission mode")
    force: bool = Field(
        default=False,
        description="Force commit even with conflicts (requires explicit acknowledgment)",
    )
    notes: Optional[str] = Field(default=None, description="Commit notes")
    # Metrics for audit trail
    score_before: Optional[float] = None
    score_after: Optional[float] = None
    conflicts_before: int = 0


class RepairCommitResponse(BaseModel):
    """Response from repair commit."""

    success: bool
    message: str
    plan_id: str
    committed: int
    dropped: int
    audit_log_id: str
    conflicts_after: int = 0
    warnings: List[str] = Field(default_factory=list)
    acquisition_ids: List[str] = Field(
        default_factory=list,
        description="IDs of newly created acquisitions (NOT kept ones from previous orders)",
    )


@router.post("/repair/commit", response_model=RepairCommitResponse)
async def commit_repair_plan(request: RepairCommitRequest) -> RepairCommitResponse:
    """
    Commit a repair plan atomically with audit trail.

    This endpoint:
    1. Validates there are no hard lock conflicts
    2. Atomically drops specified acquisitions + creates new ones
    3. Creates an audit log entry for traceability
    4. Recomputes conflicts after commit

    If force=false and there are unresolved hard lock conflicts,
    the commit will be rejected with a clear error message.
    """
    import hashlib

    from backend.conflict_detection import detect_and_persist_conflicts

    db = get_schedule_db()
    _bind_schedule_log_context(
        workspace_id=request.workspace_id,
        plan_id=request.plan_id,
    )

    # Auto-escalate locks before commit — protect near-execution acquisitions
    escalation = db.auto_escalate_locks(workspace_id=request.workspace_id)
    if escalation["escalated"] > 0:
        logger.info(
            f"[Repair Commit] Auto-escalated {escalation['escalated']} acquisitions "
            f"to hard lock before commit"
        )

    # Validate lock level
    if request.lock_level not in ["none", "hard"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid lock_level: {request.lock_level}. Must be 'none' or 'hard'",
        )

    # Check plan exists
    plan = db.get_plan(request.plan_id)
    if not plan:
        raise HTTPException(
            status_code=404, detail=f"Plan not found: {request.plan_id}"
        )

    if plan.status == "committed":
        raise HTTPException(
            status_code=400,
            detail=f"Plan {request.plan_id} is already committed",
        )

    # Check for protection conflicts before committing
    warnings: List[str] = []
    hard_lock_conflicts: List[str] = []
    freeze_conflicts: List[str] = []
    workspace_conflicts: List[str] = []

    if request.drop_acquisition_ids:
        now = datetime.now(timezone.utc)
        freeze_cutoff = now + timedelta(hours=2)

        for acq_id in request.drop_acquisition_ids:
            acq = db.get_acquisition(acq_id)
            if not acq:
                continue
            # Workspace isolation check
            if acq.workspace_id and acq.workspace_id != request.workspace_id:
                workspace_conflicts.append(
                    f"Cannot drop acquisition {acq_id} ({acq.target_id}) — "
                    f"belongs to workspace '{acq.workspace_id}'"
                )
            # Freeze cutoff check
            try:
                acq_start = datetime.fromisoformat(
                    acq.start_time.replace("Z", "+00:00")
                )
                if acq_start <= freeze_cutoff:
                    freeze_conflicts.append(
                        f"Cannot drop acquisition {acq_id} ({acq.target_id}) — "
                        f"starts at {acq.start_time}, within freeze window"
                    )
            except (ValueError, AttributeError):
                pass
            # Hard-lock check
            if acq.lock_level == "hard":
                hard_lock_conflicts.append(
                    f"Cannot drop hard-locked acquisition {acq_id} ({acq.target_id})"
                )

    all_conflicts = workspace_conflicts + freeze_conflicts + hard_lock_conflicts

    if workspace_conflicts:
        # Workspace violations are never overridable
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Cannot commit: cross-workspace drop detected",
                "workspace_conflicts": workspace_conflicts,
            },
        )

    if (freeze_conflicts or hard_lock_conflicts) and not request.force:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Cannot commit: {len(all_conflicts)} protection conflict(s) detected",
                "hard_lock_conflicts": hard_lock_conflicts,
                "freeze_conflicts": freeze_conflicts,
                "hint": "Set force=true to override (not recommended), or adjust your repair plan",
            },
        )

    if (freeze_conflicts or hard_lock_conflicts) and request.force:
        # Force=true: proceed with the full drop list as requested.
        # The user explicitly acknowledged they want to override protections.
        # Log for audit trail but do NOT silently alter the drop list.
        warnings.append(
            f"Force override: dropping {len(freeze_conflicts)} freeze-protected + "
            f"{len(hard_lock_conflicts)} hard-locked acquisition(s) as requested"
        )
        logger.warning(
            f"[Repair Commit] Force override by user — dropping protected acquisitions: "
            f"freeze={freeze_conflicts}, hard_lock={hard_lock_conflicts}"
        )

    try:
        # Atomic commit
        result = db.commit_plan_atomic(
            plan_id=request.plan_id,
            item_ids=[],  # Commit all items
            lock_level=request.lock_level,
            mode=request.mode,
            workspace_id=request.workspace_id,
            drop_acquisition_ids=request.drop_acquisition_ids,
        )

        # Recompute conflicts
        now = datetime.now(timezone.utc)
        recompute_start, recompute_end = _derive_workspace_conflict_horizon(
            db,
            request.workspace_id,
            fallback_start=now,
            fallback_end=now + timedelta(days=7),
        )
        start_str = _isoformat_z(recompute_start)
        end_str = _isoformat_z(recompute_end)

        detected_conflicts, conflict_ids = detect_and_persist_conflicts(
            db=db,
            workspace_id=request.workspace_id,
            start_time=start_str,
            end_time=end_str,
        )

        conflicts_after = len(detected_conflicts)

        # Create audit log
        config_hash = (
            f"sha256:{hashlib.sha256(request.plan_id.encode()).hexdigest()[:16]}"
        )

        audit_log = db.create_commit_audit_log(
            plan_id=request.plan_id,
            commit_type="repair" if request.drop_acquisition_ids else "normal",
            config_hash=config_hash,
            acquisitions_created=result["committed"],
            acquisitions_dropped=result["dropped"],
            workspace_id=request.workspace_id,
            committed_by=None,  # Could be set from auth context
            repair_diff={
                "dropped": request.drop_acquisition_ids,
                "created": [a["id"] for a in result["acquisitions_created"]],
            },
            score_before=request.score_before,
            score_after=request.score_after,
            conflicts_before=request.conflicts_before,
            conflicts_after=conflicts_after,
            notes=request.notes,
        )

        message = (
            f"Committed repair plan: {result['committed']} created, "
            f"{result['dropped']} dropped"
        )
        if conflicts_after > 0:
            message += f" ({conflicts_after} conflicts remain)"
            warnings.append(f"{conflicts_after} conflicts detected after commit")

        logger.info(f"[Repair Commit] {message}")

        return RepairCommitResponse(
            success=True,
            message=message,
            plan_id=request.plan_id,
            committed=result["committed"],
            dropped=result["dropped"],
            audit_log_id=audit_log.id,
            conflicts_after=conflicts_after,
            warnings=warnings,
            acquisition_ids=[a["id"] for a in result["acquisitions_created"]],
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Repair commit failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Commit failed (rolled back): {str(e)}",
        )


# =============================================================================
# Commit Audit Log Endpoint
# =============================================================================


class AuditLogResponse(BaseModel):
    """Single audit log entry."""

    id: str
    created_at: str
    plan_id: str
    workspace_id: Optional[str]
    committed_by: Optional[str]
    commit_type: str
    config_hash: str
    repair_diff: Optional[Dict[str, Any]]
    acquisitions_created: int
    acquisitions_dropped: int
    score_before: Optional[float]
    score_after: Optional[float]
    conflicts_before: int
    conflicts_after: int
    notes: Optional[str]


class AuditLogListResponse(BaseModel):
    """Response with list of audit logs."""

    success: bool
    audit_logs: List[AuditLogResponse]
    total: int


@router.get("/commit-history", response_model=AuditLogListResponse)
async def get_commit_history(
    workspace_id: Optional[str] = Query(None, description="Filter by workspace"),
    plan_id: Optional[str] = Query(None, description="Filter by plan"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> AuditLogListResponse:
    """
    Get commit audit history.

    Returns a list of commit audit log entries for traceability.
    Useful for:
    - Reviewing what changes were made and when
    - Understanding who committed what
    - Auditing repair mode changes
    """
    _bind_schedule_log_context(workspace_id=workspace_id, plan_id=plan_id)
    db = get_schedule_db()

    audit_logs = db.get_commit_audit_logs(
        workspace_id=workspace_id,
        plan_id=plan_id,
        limit=limit,
        offset=offset,
    )

    return AuditLogListResponse(
        success=True,
        audit_logs=[AuditLogResponse(**log.to_dict()) for log in audit_logs],
        total=len(audit_logs),
    )


# =============================================================================
# Snapshot / Rollback Endpoints
# =============================================================================


@router.get("/snapshots")
async def list_snapshots(workspace_id: str = Query(..., description="Workspace ID")):
    """List available schedule snapshots for rollback."""
    _bind_schedule_log_context(workspace_id=workspace_id)
    db = get_schedule_db()
    snapshots = db.list_snapshots(workspace_id)
    return {"snapshots": snapshots, "count": len(snapshots)}


@router.post("/rollback")
async def rollback_schedule(
    snapshot_id: str = Body(..., embed=True),
    workspace_id: str = Body(..., embed=True),
):
    """Rollback workspace schedule to a previous snapshot."""
    _bind_schedule_log_context(workspace_id=workspace_id, snapshot_id=snapshot_id)
    db = get_schedule_db()
    try:
        result = db.rollback_to_snapshot(snapshot_id, workspace_id)
        detected_conflicts, conflict_ids = _refresh_workspace_conflicts_after_mutation(
            db, workspace_id
        )
        return {
            "success": True,
            "message": f"Rolled back to snapshot {snapshot_id}",
            **result,
            "conflicts_detected": detected_conflicts,
            "conflict_ids": conflict_ids,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
