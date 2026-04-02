"""
Dev-only Router for Mission Planning.

Provides endpoints used exclusively by the Demo Runner and DX tooling.
These endpoints are read-only and guarded behind DEV_MODE plus local/token access.

Endpoints:
- GET  /api/v1/dev/schedule-snapshot  — snapshot metadata + acquisition IDs for a workspace
- POST /api/v1/dev/write-artifacts    — write demo evidence artifacts to disk
- GET  /api/v1/dev/metrics            — process RSS/VMS + last feasibility timing
- GET  /api/v1/dev/route-latency      — inspect in-memory route latency batches
"""

import gc
import json
import logging
import resource
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.security import require_dev_access
from backend.schedule_persistence import get_schedule_db

# ---------------------------------------------------------------------------
# Lightweight process-level metrics (no psutil dependency)
# ---------------------------------------------------------------------------


def _get_process_rss_mb() -> float:
    """Return current process RSS in MB via resource module (macOS/Linux)."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # macOS reports in bytes, Linux in KB
    if hasattr(os, "uname") and os.uname().sysname == "Darwin":
        return usage.ru_maxrss / (1024 * 1024)
    return usage.ru_maxrss / 1024


def _get_process_vms_mb() -> Optional[float]:
    """Return process VMS in MB by reading /proc/self/status (Linux only)."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmSize:"):
                    return int(line.split()[1]) / 1024  # KB → MB
    except (FileNotFoundError, PermissionError, ValueError):
        pass
    return None


# Module-level timing store: last feasibility run stats.
# Written by the /mission/analyze handler if DEV_MODE (see note below).
_last_feasibility_stats: Dict[str, Any] = {}

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/dev",
    tags=["dev"],
    dependencies=[Depends(require_dev_access)],
)


# =============================================================================
# Response Models
# =============================================================================


class AcquisitionSnapshot(BaseModel):
    id: str
    satellite_id: str
    target_id: str
    start_time: str
    end_time: str
    state: str
    lock_level: str
    plan_id: Optional[str] = None
    order_id: Optional[str] = None
    template_id: Optional[str] = None
    instance_key: Optional[str] = None
    canonical_target_id: Optional[str] = None
    display_target_name: Optional[str] = None


class PlanSnapshot(BaseModel):
    id: str
    created_at: str
    algorithm: str
    status: str
    workspace_id: Optional[str] = None


class ScheduleSnapshotResponse(BaseModel):
    """Full snapshot of schedule state for a workspace — used for reshuffle evidence."""

    success: bool
    workspace_id: str
    captured_at: str
    acquisition_count: int
    acquisitions: List[AcquisitionSnapshot] = Field(default_factory=list)
    plans: List[PlanSnapshot] = Field(default_factory=list)
    plan_count: int = 0
    acquisition_ids: List[str] = Field(default_factory=list)
    by_target: Dict[str, int] = Field(default_factory=dict)
    by_satellite: Dict[str, int] = Field(default_factory=dict)
    by_state: Dict[str, int] = Field(default_factory=dict)


class WriteArtifactsRequest(BaseModel):
    json_content: Dict[str, Any]
    markdown_content: str
    output_dir: str = "artifacts/demo"
    filename_prefix: str = "RESHUFFLE_EVIDENCE"


class WriteArtifactsResponse(BaseModel):
    success: bool
    json_path: str
    md_path: str


class ProcessMetrics(BaseModel):
    process_rss_mb: float
    process_vms_mb: Optional[float] = None
    uptime_seconds: Optional[float] = None


class LastRequestParams(BaseModel):
    target_count: Optional[int] = None
    satellite_count: Optional[int] = None
    duration_days: Optional[float] = None


class GcStats(BaseModel):
    collections: List[int] = Field(
        default_factory=list, description="GC collection counts per generation"
    )
    thresholds: List[int] = Field(default_factory=list)
    uncollectable: int = 0


class MetricsResponse(BaseModel):
    success: bool
    process: ProcessMetrics
    last_feasibility: Dict[str, Any] = Field(default_factory=dict)
    last_response_bytes: Optional[int] = None
    last_pass_count: Optional[int] = None
    last_request_params: Optional[LastRequestParams] = None
    gc_stats: Optional[GcStats] = None


class RouteLatencyEntry(BaseModel):
    """Single in-memory route latency batch."""

    route: str
    route_family: str
    count: int
    avg_ms: float
    p95_ms: float
    max_ms: float
    slow_count: int
    error_count: int
    status_counts: Dict[str, int] = Field(default_factory=dict)
    profile: str
    slow_threshold_ms: float
    baseline_windows: Optional[int] = None
    baseline_avg_ms: Optional[float] = None
    baseline_p95_ms: Optional[float] = None
    avg_delta_ms: Optional[float] = None
    p95_delta_ms: Optional[float] = None
    is_hot: bool = False
    hot_reason: Optional[str] = None


class RouteLatencyHistoryEntry(BaseModel):
    """Previously emitted route latency summary."""

    route: str
    route_family: str
    emitted_at: str
    count: int
    avg_ms: float
    p95_ms: float
    max_ms: float
    slow_count: int
    error_count: int
    status_counts: Dict[str, int] = Field(default_factory=dict)
    profile: str
    slow_threshold_ms: float
    is_hot: bool = False
    hot_reason: Optional[str] = None


class RouteLatencyFamilyEntry(BaseModel):
    """Aggregate latency and status counters for a route family."""

    family: str
    route_count: int
    request_count: int
    avg_ms: float
    p95_ms: float
    max_ms: float
    slow_count: int
    error_count: int
    hot_count: int
    status_counts: Dict[str, int] = Field(default_factory=dict)


class RecentRouteErrorEntry(BaseModel):
    """Single recent non-success request outcome."""

    occurred_at: str
    method: str
    route: str
    route_family: str
    status_code: int
    status_class: str
    duration_ms: float
    profile: str


class RecentErrorFamilyEntry(BaseModel):
    """Aggregate recent errors for a route family."""

    family: str
    error_count: int
    route_count: int
    max_duration_ms: float
    latest_occurred_at: Optional[str] = None
    status_counts: Dict[str, int] = Field(default_factory=dict)


class RouteLatencyResponse(BaseModel):
    """Dev snapshot of active route latency batches."""

    success: bool
    captured_at: str
    summary_every: int
    history_limit: int
    baseline_windows: int
    status_counts: Dict[str, int] = Field(default_factory=dict)
    history_status_counts: Dict[str, int] = Field(default_factory=dict)
    recent_error_limit: int
    recent_error_count: int = 0
    recent_error_status_counts: Dict[str, int] = Field(default_factory=dict)
    error_family_count: int = 0
    error_families: List[RecentErrorFamilyEntry] = Field(default_factory=list)
    recent_errors: List[RecentRouteErrorEntry] = Field(default_factory=list)
    family_count: int = 0
    families: List[RouteLatencyFamilyEntry] = Field(default_factory=list)
    route_count: int
    routes: List[RouteLatencyEntry] = Field(default_factory=list)
    history_count: int = 0
    history: List[RouteLatencyHistoryEntry] = Field(default_factory=list)


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/schedule-snapshot", response_model=ScheduleSnapshotResponse)
async def get_schedule_snapshot(
    workspace_id: str = Query(..., description="Workspace ID to snapshot"),
) -> ScheduleSnapshotResponse:
    """
    Get a complete snapshot of schedule metadata for a workspace.

    Returns all acquisitions, plans, and summary statistics.
    Used by the Demo Runner to capture reshuffle evidence after each Apply.
    """
    db = get_schedule_db()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Get acquisitions strictly for this workspace (no NULL fallback)
    # list_acquisitions includes workspace_id IS NULL by default, so we
    # query directly for strict matching.
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM acquisitions WHERE workspace_id = ? LIMIT 500",
            (workspace_id,),
        )
        rows = cursor.fetchall()

    acquisitions = [db._row_to_acquisition(r) for r in rows]

    acq_snapshots = [
        AcquisitionSnapshot(
            id=a.id,
            satellite_id=a.satellite_id,
            target_id=a.target_id,
            start_time=a.start_time,
            end_time=a.end_time,
            state=a.state,
            lock_level=a.lock_level,
            plan_id=a.plan_id,
            order_id=a.order_id,
            template_id=a.template_id,
            instance_key=a.instance_key,
            canonical_target_id=a.canonical_target_id,
            display_target_name=a.display_target_name,
        )
        for a in acquisitions
    ]

    # Get commit audit logs for workspace (serves as plan revision history)
    audit_logs = db.get_commit_audit_logs(workspace_id=workspace_id, limit=100)
    plan_snapshots = [
        PlanSnapshot(
            id=log.plan_id,
            created_at=log.created_at,
            algorithm=log.commit_type,
            status="committed",
            workspace_id=log.workspace_id,
        )
        for log in audit_logs
    ]

    # Build summaries
    by_target: Dict[str, int] = {}
    by_satellite: Dict[str, int] = {}
    by_state: Dict[str, int] = {}
    acq_ids: List[str] = []

    for a in acquisitions:
        acq_ids.append(a.id)
        by_target[a.target_id] = by_target.get(a.target_id, 0) + 1
        by_satellite[a.satellite_id] = by_satellite.get(a.satellite_id, 0) + 1
        by_state[a.state] = by_state.get(a.state, 0) + 1

    logger.info(
        f"[Dev Snapshot] workspace={workspace_id}: "
        f"{len(acquisitions)} acquisitions, {len(audit_logs)} plans"
    )

    return ScheduleSnapshotResponse(
        success=True,
        workspace_id=workspace_id,
        captured_at=now,
        acquisition_count=len(acquisitions),
        acquisitions=acq_snapshots,
        plans=plan_snapshots,
        plan_count=len(plan_snapshots),
        acquisition_ids=acq_ids,
        by_target=by_target,
        by_satellite=by_satellite,
        by_state=by_state,
    )


@router.post("/write-artifacts", response_model=WriteArtifactsResponse)
async def write_artifacts(request: WriteArtifactsRequest) -> WriteArtifactsResponse:
    """
    Write demo evidence artifacts to disk.

    Creates JSON and Markdown files in the specified output directory.
    Used by the Demo Runner to persist reshuffle evidence.
    """
    output_dir = Path(request.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"{request.filename_prefix}.json"
    md_path = output_dir / f"{request.filename_prefix}.md"

    try:
        with open(json_path, "w") as f:
            json.dump(request.json_content, f, indent=2)

        with open(md_path, "w") as f:
            f.write(request.markdown_content)

        logger.info(f"[Dev Artifacts] Written to {output_dir}")

        return WriteArtifactsResponse(
            success=True,
            json_path=str(json_path),
            md_path=str(md_path),
        )
    except Exception as e:
        logger.error(f"[Dev Artifacts] Failed to write: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Process metrics endpoint
# ---------------------------------------------------------------------------

_server_start_time = time.monotonic()


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """
    Dev-only endpoint returning process-level metrics.

    Returns RSS/VMS memory usage, last feasibility timing stats,
    last response/pass metadata, and GC collection counts.
    """
    # GC stats
    gc_counts = list(gc.get_count())
    gc_thresholds = list(gc.get_threshold())
    gc_info = GcStats(
        collections=gc_counts,
        thresholds=gc_thresholds,
        uncollectable=len(gc.garbage),
    )

    # Build last_request_params from stored stats
    last_req_params: Optional[LastRequestParams] = None
    if _last_feasibility_stats:
        last_req_params = LastRequestParams(
            target_count=_last_feasibility_stats.get("target_count"),
            satellite_count=_last_feasibility_stats.get("satellite_count"),
            duration_days=_last_feasibility_stats.get("duration_days"),
        )

    return MetricsResponse(
        success=True,
        process=ProcessMetrics(
            process_rss_mb=round(_get_process_rss_mb(), 2),
            process_vms_mb=(
                round(v, 2) if (v := _get_process_vms_mb()) is not None else None
            ),
            uptime_seconds=round(time.monotonic() - _server_start_time, 1),
        ),
        last_feasibility=dict(_last_feasibility_stats),
        last_response_bytes=_last_feasibility_stats.get("response_bytes"),
        last_pass_count=_last_feasibility_stats.get("pass_count"),
        last_request_params=last_req_params,
        gc_stats=gc_info,
    )


@router.get("/route-latency", response_model=RouteLatencyResponse)
async def get_route_latency(
    limit: int = Query(20, ge=1, le=200, description="Max route batches to return"),
    reset: bool = Query(False, description="Clear batches after capturing snapshot"),
) -> RouteLatencyResponse:
    """
    Dev-only endpoint returning current in-memory route latency batches.

    Useful when diagnosing hot routes without waiting for periodic summary log lines.
    """
    from backend.main import get_route_latency_snapshot

    snapshot = get_route_latency_snapshot(limit=limit, reset=reset)
    routes = [RouteLatencyEntry(**route) for route in snapshot["routes"]]
    history = [RouteLatencyHistoryEntry(**entry) for entry in snapshot["history"]]
    families = [RouteLatencyFamilyEntry(**entry) for entry in snapshot["families"]]
    error_families = [
        RecentErrorFamilyEntry(**entry) for entry in snapshot["error_families"]
    ]
    recent_errors = [
        RecentRouteErrorEntry(**entry) for entry in snapshot["recent_errors"]
    ]

    return RouteLatencyResponse(
        success=True,
        captured_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        summary_every=int(snapshot["summary_every"]),
        history_limit=int(snapshot["history_limit"]),
        baseline_windows=int(snapshot["baseline_windows"]),
        status_counts=dict(snapshot["status_counts"]),
        history_status_counts=dict(snapshot["history_status_counts"]),
        recent_error_limit=int(snapshot["recent_error_limit"]),
        recent_error_count=int(snapshot["recent_error_count"]),
        recent_error_status_counts=dict(snapshot["recent_error_status_counts"]),
        error_family_count=len(error_families),
        error_families=error_families,
        recent_errors=recent_errors,
        family_count=len(families),
        families=families,
        route_count=len(routes),
        routes=routes,
        history_count=len(history),
        history=history,
    )


# ---------------------------------------------------------------------------
# Last planning run diagnostics (PR_SCHED_001)
# ---------------------------------------------------------------------------


class LastPlanningRunResponse(BaseModel):
    """Diagnostics from the last scheduling pipeline run."""

    success: bool
    has_data: bool
    run_id: Optional[str] = None
    workspace_id: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    breadcrumb_count: int = 0
    breadcrumbs: List[Dict[str, Any]] = Field(default_factory=list)


@router.get("/last-planning-run", response_model=LastPlanningRunResponse)
async def get_last_planning_run() -> LastPlanningRunResponse:
    """
    Dev-only endpoint returning diagnostics from the last scheduling pipeline run.

    Returns the full audit trail including:
    - Chosen mode and reason
    - Request payload hash
    - Schedule revision IDs before/after
    - Acquisition IDs before/after
    - Diff counts (added/removed/kept)
    """
    from backend.scheduling_mode import get_last_planning_run as _get_last

    data = _get_last()
    if not data:
        return LastPlanningRunResponse(success=True, has_data=False)

    return LastPlanningRunResponse(
        success=True,
        has_data=True,
        run_id=data.get("run_id"),
        workspace_id=data.get("workspace_id"),
        started_at=data.get("started_at"),
        completed_at=data.get("completed_at"),
        breadcrumb_count=data.get("breadcrumb_count", 0),
        breadcrumbs=data.get("breadcrumbs", []),
    )


def record_feasibility_timing(
    duration_seconds: float,
    target_count: int,
    satellite_count: int,
    **extra: Any,
) -> None:
    """Called from mission/analyze handler to record timing (DEV_MODE only)."""
    _last_feasibility_stats.clear()
    _last_feasibility_stats.update(
        {
            "duration_seconds": round(duration_seconds, 3),
            "target_count": target_count,
            "satellite_count": satellite_count,
            "recorded_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            **extra,
        }
    )
