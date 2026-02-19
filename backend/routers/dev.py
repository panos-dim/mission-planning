"""
Dev-only Router for Mission Planning.

Provides endpoints used exclusively by the Demo Runner and DX tooling.
These endpoints are read-only and guarded behind DEV_MODE env var.

Endpoints:
- GET  /api/v1/dev/schedule-snapshot  — snapshot metadata + acquisition IDs for a workspace
- POST /api/v1/dev/write-artifacts    — write demo evidence artifacts to disk
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.schedule_persistence import get_schedule_db

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


class WriteArtifactsResponse(BaseModel):
    success: bool
    json_path: str
    md_path: str


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
    now = datetime.utcnow().isoformat() + "Z"

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

    json_path = output_dir / "RESHUFFLE_EVIDENCE.json"
    md_path = output_dir / "RESHUFFLE_EVIDENCE.md"

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
