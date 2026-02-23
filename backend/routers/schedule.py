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

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.schedule_persistence import ScheduleDB, get_schedule_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schedule", tags=["schedule"])


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
    schema_version: str = "2.0"
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


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/state", response_model=ScheduleStateResponse)
async def get_schedule_state(
    workspace_id: Optional[str] = Query(None, description="Filter by workspace ID"),
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
    db = get_schedule_db()

    # Get recent acquisitions and orders
    acquisitions = db.list_acquisitions(workspace_id=workspace_id, limit=100)
    orders_list = db.list_orders(workspace_id=workspace_id, limit=100)

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
            freeze_cutoff=(now + timedelta(hours=2)).isoformat() + "Z",
        )

    state = ScheduleState(
        acquisitions=acq_summaries,
        orders=order_summaries,
        conflicts=[],  # Conflict detection not implemented yet
        horizon=horizon,
    )

    meta = ScheduleStateMeta(
        persistence_enabled=True,
        schema_version="2.0",
        implementation_status="active",
    )

    logger.info(
        f"[Schedule State] Returning {len(acq_summaries)} acquisitions, "
        f"{len(order_summaries)} orders"
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
        f"include_tentative={include_tentative}"
    )

    # Query acquisitions from persistence layer
    start_str = horizon_start.isoformat() + "Z"
    end_str = horizon_end.isoformat() + "Z"

    acquisitions = db.get_acquisitions_in_horizon(
        start_time=start_str,
        end_time=end_str,
        workspace_id=workspace_id,
        include_tentative=include_tentative,
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
    )

    horizon = HorizonInfo(
        start=horizon_start.isoformat() + "Z",
        end=horizon_end.isoformat() + "Z",
        freeze_cutoff=freeze_cutoff.isoformat() + "Z",
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

    start_str = start_dt.isoformat() + "Z"
    end_str = end_dt.isoformat() + "Z"

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
    db = get_schedule_db()

    logger.info(
        f"[Schedule Conflicts] workspace_id={workspace_id}, "
        f"from={from_time}, to={to_time}, satellite_id={satellite_id}"
    )

    # If horizon specified, use horizon-based query
    if from_time or to_time:
        now = datetime.now(timezone.utc)
        start_str = from_time or (now.isoformat() + "Z")
        end_str = to_time or ((now + timedelta(days=7)).isoformat() + "Z")

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

    # Convert to response format
    conflict_responses = [ConflictResponse(**c.to_dict()) for c in conflicts]

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

    db = get_schedule_db()

    # Parse or default times
    now = datetime.now(timezone.utc)
    start_str = request.from_time or (now.isoformat() + "Z")
    end_str = request.to_time or ((now + timedelta(days=7)).isoformat() + "Z")

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
    db = get_schedule_db()

    result = db.hard_lock_all_committed(request.workspace_id)

    return HardLockCommittedResponse(
        success=True,
        message=f"Hard-locked {result['updated']} committed acquisitions",
        updated=result["updated"],
        workspace_id=request.workspace_id,
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
        description="Force delete even hard-locked acquisitions",
    )


class BulkDeleteAcquisitionsResponse(BaseModel):
    """Response from bulk acquisition deletion."""

    success: bool
    message: str
    deleted: int
    failed: List[str]
    skipped_hard_locked: List[str] = Field(default_factory=list)


@router.delete(
    "/acquisition/{acquisition_id}", response_model=DeleteAcquisitionResponse
)
async def delete_acquisition(
    acquisition_id: str,
    force: bool = Query(False, description="Force delete even if hard-locked"),
) -> DeleteAcquisitionResponse:
    """
    Delete a single acquisition from the schedule.

    By default, hard-locked acquisitions cannot be deleted.
    Use force=true to override this protection.
    """
    db = get_schedule_db()

    # Check acquisition exists
    acq = db.get_acquisition(acquisition_id)
    if not acq:
        raise HTTPException(
            status_code=404, detail=f"Acquisition not found: {acquisition_id}"
        )

    # Protect hard-locked acquisitions unless force
    if acq.lock_level == "hard" and not force:
        raise HTTPException(
            status_code=409,
            detail=f"Acquisition {acquisition_id} is hard-locked. "
            f"Use force=true to delete it.",
        )

    success = db.delete_acquisition(acquisition_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete acquisition")

    logger.info(
        f"Deleted acquisition {acquisition_id} "
        f"(was {acq.state}, lock={acq.lock_level})"
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
    db = get_schedule_db()

    if not request.acquisition_ids:
        raise HTTPException(status_code=400, detail="No acquisition IDs provided")

    ids_to_delete = list(request.acquisition_ids)
    skipped_hard_locked: List[str] = []

    # Unless force, filter out hard-locked acquisitions
    if not request.force:
        filtered_ids: List[str] = []
        for acq_id in ids_to_delete:
            acq = db.get_acquisition(acq_id)
            if acq and acq.lock_level == "hard":
                skipped_hard_locked.append(acq_id)
            else:
                filtered_ids.append(acq_id)
        ids_to_delete = filtered_ids

    result = db.bulk_delete_acquisitions(ids_to_delete)

    message = f"Deleted {result['deleted']} acquisitions"
    if result["failed"]:
        message += f" ({len(result['failed'])} not found)"
    if skipped_hard_locked:
        message += f" ({len(skipped_hard_locked)} hard-locked skipped)"

    logger.info(message)

    return BulkDeleteAcquisitionsResponse(
        success=True,
        message=message,
        deleted=result["deleted"],
        failed=result["failed"],
        skipped_hard_locked=skipped_hard_locked,
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
        default="soft", description="Lock level for acquisitions: soft | hard"
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

    try:
        result = db.commit_plan(
            plan_id=request.plan_id,
            item_ids=request.items_to_commit or [],
            lock_level=request.lock_level,
            mode=request.mode,
            workspace_id=request.workspace_id,
        )

        logger.info(
            f"[Commit Plan] Committed plan {request.plan_id}: "
            f"{result['committed']} acquisitions created"
        )

        # Recompute conflicts if requested and workspace is specified
        conflicts_detected = 0
        conflict_ids: List[str] = []

        if request.recompute_conflicts and request.workspace_id:
            now = datetime.now(timezone.utc)
            start_str = now.isoformat() + "Z"
            end_str = (now + timedelta(days=7)).isoformat() + "Z"

            detected_conflicts, new_conflict_ids = detect_and_persist_conflicts(
                db=db,
                workspace_id=request.workspace_id,
                start_time=start_str,
                end_time=end_str,
            )

            conflicts_detected = len(detected_conflicts)
            conflict_ids = new_conflict_ids

            # Check if we have error-severity conflicts and force wasn't set
            error_conflicts = [c for c in detected_conflicts if c.severity == "error"]
            if error_conflicts and not request.force:
                logger.warning(
                    f"[Commit Plan] Commit succeeded but {len(error_conflicts)} "
                    f"error-severity conflicts detected"
                )

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


def _check_commit_conflicts(
    db: ScheduleDB,
    items: List["DirectCommitItem"],
    workspace_id: Optional[str],
) -> List[str]:
    """
    Check if new items would conflict with existing committed acquisitions.

    Returns a list of conflict descriptions (empty if no conflicts).
    """
    from datetime import datetime as dt

    conflicts: List[str] = []

    # Get time range for the new items
    if not items:
        return conflicts

    start_times = [item.start_time for item in items]
    end_times = [item.end_time for item in items]
    min_time = min(start_times)
    max_time = max(end_times)

    # Get existing committed acquisitions in this time range
    existing = db.get_acquisitions_in_horizon(
        start_time=min_time,
        end_time=max_time,
        workspace_id=workspace_id,
        include_tentative=False,  # Only check against committed acquisitions
    )

    # Filter to only committed state
    existing = [a for a in existing if a.state == "committed"]

    if not existing:
        return conflicts

    # Group existing by satellite
    existing_by_sat: Dict[str, List] = {}
    for acq in existing:
        if acq.satellite_id not in existing_by_sat:
            existing_by_sat[acq.satellite_id] = []
        existing_by_sat[acq.satellite_id].append(acq)

    # Check each new item for conflicts
    for item in items:
        sat_existing = existing_by_sat.get(item.satellite_id, [])

        for existing_acq in sat_existing:
            # Parse times
            try:
                new_start = dt.fromisoformat(item.start_time.replace("Z", "+00:00"))
                new_end = dt.fromisoformat(item.end_time.replace("Z", "+00:00"))
                exist_start = dt.fromisoformat(
                    existing_acq.start_time.replace("Z", "+00:00")
                )
                exist_end = dt.fromisoformat(
                    existing_acq.end_time.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                continue

            # Check for overlap: two intervals overlap if start1 < end2 AND start2 < end1
            if new_start < exist_end and exist_start < new_end:
                conflicts.append(
                    f"{item.satellite_id}/{item.target_id} overlaps with "
                    f"existing {existing_acq.target_id} at {item.start_time[:19]}"
                )

    return conflicts


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
    import hashlib
    import uuid

    db = get_schedule_db()

    logger.info(
        f"[Direct Commit] Received request: items={len(request.items)}, "
        f"algorithm={request.algorithm}, mode={request.mode}, "
        f"workspace_id={request.workspace_id}"
    )

    if not request.items:
        raise HTTPException(status_code=400, detail="No items to commit")

    # Check for conflicts with existing committed acquisitions
    conflicts = _check_commit_conflicts(db, request.items, request.workspace_id)
    if conflicts and not request.force:
        conflict_details = "; ".join(conflicts[:3])  # Show first 3 conflicts
        more = f" (+{len(conflicts) - 3} more)" if len(conflicts) > 3 else ""
        raise HTTPException(
            status_code=409,
            detail=f"Cannot commit: {len(conflicts)} conflict(s) detected. {conflict_details}{more}",
        )
    if conflicts and request.force:
        logger.warning(
            f"[Direct Commit] Force-committing with {len(conflicts)} conflict(s)"
        )

    try:
        # Generate run_id and input hash
        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        input_data = f"{request.algorithm}:{len(request.items)}:{request.workspace_id}"
        input_hash = f"sha256:{hashlib.sha256(input_data.encode()).hexdigest()[:16]}"

        # Build metrics from items
        metrics = {
            "accepted": len(request.items),
            "algorithm": request.algorithm,
            "committed_at": datetime.now(timezone.utc).isoformat() + "Z",
        }

        # Create plan record
        plan = db.create_plan(
            algorithm=request.algorithm,
            config={"mode": request.mode, "source": "direct_commit"},
            input_hash=input_hash,
            run_id=run_id,
            metrics=metrics,
            workspace_id=request.workspace_id,
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
        result = db.commit_plan(
            plan_id=plan.id,
            item_ids=[],  # Commit all items
            lock_level=request.lock_level,
            mode=request.mode,
            workspace_id=request.workspace_id,
        )

        logger.info(
            f"[Direct Commit] Created and committed plan {plan.id}: "
            f"{result['committed']} acquisitions"
        )

        return DirectCommitResponse(
            success=True,
            message=f"Created {result['committed']} acquisitions",
            plan_id=plan.id,
            committed=result["committed"],
            acquisition_ids=[a["id"] for a in result["acquisitions_created"]],
        )

    except Exception as e:
        logger.error(f"Failed direct commit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Incremental Planning Endpoint
# =============================================================================


class IncrementalPlanRequest(BaseModel):
    """Request for incremental planning."""

    # Planning mode
    planning_mode: str = Field(
        default="from_scratch",
        description="Planning mode: 'from_scratch' or 'incremental'",
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

    # Parse horizon times
    now = datetime.now(timezone.utc)

    if request.horizon_from:
        try:
            horizon_start = datetime.fromisoformat(
                request.horizon_from.replace("Z", "+00:00")
            )
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid horizon_from: {request.horizon_from}"
            )
    else:
        horizon_start = now.replace(tzinfo=None)

    if request.horizon_to:
        try:
            horizon_end = datetime.fromisoformat(
                request.horizon_to.replace("Z", "+00:00")
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
            f"Must be 'from_scratch' or 'incremental'",
        )

    try:
        lock_policy = LockPolicy(request.lock_policy)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid lock_policy: {request.lock_policy}. "
            f"Must be 'respect_hard_only' or 'respect_hard_and_soft'",
        )

    logger.info(
        f"[Incremental Plan] mode={planning_mode.value}, "
        f"workspace={request.workspace_id}, "
        f"horizon={horizon_start.isoformat()} to {horizon_end.isoformat()}"
    )

    # Initialize response components
    existing_summary = ExistingAcquisitionsSummaryResponse(
        horizon_start=horizon_start.isoformat() + "Z",
        horizon_end=horizon_end.isoformat() + "Z",
    )
    schedule_context: Dict[str, Any] = {
        "planning_mode": planning_mode.value,
        "lock_policy": lock_policy.value,
        "include_tentative": request.include_tentative,
    }

    # Load blocked intervals for incremental mode
    context: Optional[IncrementalPlanningContext] = None

    if planning_mode == PlanningMode.INCREMENTAL and request.workspace_id:
        context = load_blocked_intervals(
            db=db,
            workspace_id=request.workspace_id,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            lock_policy=lock_policy,
            include_tentative=request.include_tentative,
        )

        # Build existing acquisitions summary
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
            horizon_start=horizon_start.isoformat() + "Z",
            horizon_end=horizon_end.isoformat() + "Z",
        )

        schedule_context["loaded_acquisitions"] = context.loaded_acquisitions_count
        schedule_context["blocked_satellites"] = list(context.blocked_intervals.keys())

        logger.info(
            f"[Incremental Plan] Loaded {context.loaded_acquisitions_count} blocked acquisitions"
        )

    # Get opportunities from the planning store
    # In a full implementation, opportunities would be passed via request or session
    # For now, we return an empty plan if no opportunities are cached
    raw_opportunities: List[Dict[str, Any]] = []

    # Try to get opportunities from the planning endpoint's cache if available
    try:
        from backend.main import get_cached_opportunities

        raw_opportunities = get_cached_opportunities() or []
    except (ImportError, AttributeError):
        # No cached opportunities available - this is expected
        pass

    # Fallback: read from current_mission_data if opportunities_cache is empty
    if not raw_opportunities:
        try:
            from datetime import datetime as _dt

            from backend.main import app as main_app

            _cmd = getattr(main_app.state, "current_mission_data", {})
            if _cmd and "passes" in _cmd:
                passes = _cmd["passes"]
                for idx, p in enumerate(passes):
                    if isinstance(p, dict):
                        sat = p["satellite_name"]
                        tgt = p["target_name"]
                        st = _dt.fromisoformat(p["start_time"])
                        et = _dt.fromisoformat(p["end_time"])
                    else:
                        sat = p.satellite_name
                        tgt = p.target_name
                        st = p.start_time
                        et = p.end_time
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
                            "roll_angle_deg": 0.0,
                            "pitch_angle_deg": 0.0,
                            "value": 1.0,
                        }
                    )
                logger.info(
                    f"[Incremental Plan] Loaded {len(raw_opportunities)} opportunities from mission analysis fallback"
                )
        except Exception as e:
            logger.warning(
                f"[Incremental Plan] Failed to load mission data fallback: {e}"
            )

    if not raw_opportunities:
        logger.info(
            "[Incremental Plan] No cached opportunities - returning empty plan. "
            "Run mission analysis first to generate opportunities."
        )

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

        slew_config = SlewConfig(
            roll_slew_rate_deg_per_sec=request.max_roll_rate_dps,
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

    # Only use workspace_id if acquisitions were loaded from it (otherwise FK constraint fails)
    effective_workspace_id = (
        request.workspace_id
        if context and context.loaded_acquisitions_count > 0
        else None
    )

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

    # Create plan items from feasible opportunities
    new_items: List[PlanItemPreviewResponse] = []

    for opp in feasible_opportunities[:100]:  # Limit for safety
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

    return IncrementalPlanResponse(
        success=True,
        message=message,
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

    # Parse horizon times
    now = datetime.now(timezone.utc)

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

    logger.info(
        f"[Repair Plan] workspace={request.workspace_id}, "
        f"scope={repair_scope.value}, "
        f"max_changes={request.max_changes}, objective={objective.value}"
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
        horizon_start=horizon_start.isoformat() + "Z",
        horizon_end=horizon_end.isoformat() + "Z",
    )

    # Get opportunities from cache
    raw_opportunities: List[Dict[str, Any]] = []
    try:
        from backend.main import get_cached_opportunities

        raw_opportunities = get_cached_opportunities() or []
    except (ImportError, AttributeError):
        pass

    # Fallback: read from current_mission_data if opportunities_cache is empty
    if not raw_opportunities:
        try:
            from datetime import datetime as _dt

            from backend.main import app as main_app

            _cmd = getattr(main_app.state, "current_mission_data", {})
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

    # Re-score opportunity values with current target priorities
    if request.target_priorities and raw_opportunities:
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
            if tid in request.target_priorities:
                new_priority = float(request.target_priorities[tid])
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
        target_priorities=request.target_priorities or None,
    )

    # Create plan record
    import hashlib
    import uuid

    run_id = f"repair_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    input_hash = f"sha256:{hashlib.sha256(run_id.encode()).hexdigest()[:16]}"

    # Only use workspace_id if acquisitions were loaded from it (otherwise FK constraint fails)
    effective_workspace_id = (
        request.workspace_id if repair_context.original_acquisition_count > 0 else None
    )

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
            "start": horizon_start.isoformat() + "Z",
            "end": horizon_end.isoformat() + "Z",
        },
        "satellites_used": sorted(satellites_used),
        "total_targets_with_opportunities": len(all_opp_targets),
        "total_targets_covered": len(scheduled_target_ids),
    }

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
        default="soft", description="Lock level for new acquisitions"
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

    # Check for hard lock conflicts before committing
    warnings: List[str] = []
    hard_lock_conflicts: List[str] = []

    if request.drop_acquisition_ids:
        for acq_id in request.drop_acquisition_ids:
            acq = db.get_acquisition(acq_id)
            if acq and acq.lock_level == "hard":
                hard_lock_conflicts.append(
                    f"Cannot drop hard-locked acquisition {acq_id} ({acq.target_id})"
                )

    if hard_lock_conflicts and not request.force:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Cannot commit: hard lock conflicts detected",
                "hard_lock_conflicts": hard_lock_conflicts,
                "hint": "Set force=true to override (not recommended), or adjust your repair plan",
            },
        )

    if hard_lock_conflicts and request.force:
        warnings.append(
            f"Force-committed with {len(hard_lock_conflicts)} hard lock conflicts"
        )
        # Filter out hard-locked acquisitions from drop list
        hard_locked_ids = set()
        for acq_id in request.drop_acquisition_ids:
            acq = db.get_acquisition(acq_id)
            if acq and acq.lock_level == "hard":
                hard_locked_ids.add(acq_id)
        request.drop_acquisition_ids = [
            aid for aid in request.drop_acquisition_ids if aid not in hard_locked_ids
        ]
        warnings.append(
            f"Skipped dropping {len(hard_locked_ids)} hard-locked acquisitions"
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
        start_str = now.isoformat() + "Z"
        end_str = (now + timedelta(days=7)).isoformat() + "Z"

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
