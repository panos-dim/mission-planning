"""
Dev-only Router for Mission Planning.

Provides endpoints used exclusively by the Demo Runner and DX tooling.
These endpoints are read-only and guarded behind DEV_MODE env var.

Endpoints:
- GET  /api/v1/dev/schedule-snapshot  — snapshot metadata + acquisition IDs for a workspace
- POST /api/v1/dev/write-artifacts    — write demo evidence artifacts to disk
- GET  /api/v1/dev/metrics            — process RSS/VMS + last feasibility timing
"""

import gc
import json
import logging
import os
import resource
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

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

router = APIRouter(prefix="/api/v1/dev", tags=["dev"])


# =============================================================================
# Guard: only register if DEV_MODE
# =============================================================================

_DEV_MODE = os.environ.get("DEV_MODE", "1") == "1"  # default ON for local dev


def _check_dev_mode() -> None:
    if not _DEV_MODE:
        raise HTTPException(
            status_code=403,
            detail="Dev endpoints are disabled (set DEV_MODE=1 to enable)",
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
    _check_dev_mode()

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
    _check_dev_mode()

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
    _check_dev_mode()

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
