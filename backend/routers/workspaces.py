"""
Workspace API Router for Mission Planning.

Provides CRUD endpoints for workspace management:
- POST   /api/v1/workspaces           - Create new workspace
- GET    /api/v1/workspaces           - List all workspaces
- GET    /api/v1/workspaces/{id}      - Get workspace by ID
- PUT    /api/v1/workspaces/{id}      - Update workspace
- DELETE /api/v1/workspaces/{id}      - Delete workspace
- POST   /api/v1/workspaces/{id}/export  - Export workspace
- POST   /api/v1/workspaces/import    - Import workspace
- POST   /api/v1/workspaces/save-current - Save current mission state

Includes config snapshot support for reproducibility.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config_resolver import get_config_hash, get_config_snapshot
from backend.schedule_persistence import get_schedule_db
from backend.workspace_persistence import get_workspace_db

logger = logging.getLogger(__name__)


def _migrate_orders_state_to_v2(
    workspace_id: str,
    orders_state: Optional[Dict[str, Any]],
) -> int:
    """
    Migrate legacy orders_state_json blob to normalized v2 tables.

    This is a one-time migration that runs when loading a workspace that has
    orders_state_json but no corresponding rows in the v2 acquisitions table.

    Args:
        workspace_id: Workspace ID to associate migrated data with
        orders_state: Legacy orders_state dict from workspace blob

    Returns:
        Number of acquisitions migrated
    """
    if not orders_state:
        return 0

    orders_list = orders_state.get("orders", [])
    if not orders_list:
        return 0

    schedule_db = get_schedule_db()

    # Check if we've already migrated this workspace
    existing = schedule_db.list_acquisitions(workspace_id=workspace_id, limit=1)
    if existing:
        logger.info(
            f"[Migration] Workspace {workspace_id} already has v2 acquisitions, skipping migration"
        )
        return 0

    logger.info(
        f"[Migration] Migrating {len(orders_list)} AcceptedOrders from workspace {workspace_id}"
    )

    migrated_count = 0

    for order in orders_list:
        order_id = order.get("order_id", "")
        algorithm = order.get("algorithm", "unknown")
        schedule = order.get("schedule", [])

        if not schedule:
            continue

        # Create a plan record for this AcceptedOrder
        import hashlib
        import uuid
        from datetime import datetime, timezone

        run_id = f"migrated_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        input_hash = f"sha256:{hashlib.sha256(order_id.encode()).hexdigest()[:16]}"

        metrics = order.get("metrics", {})

        plan = schedule_db.create_plan(
            algorithm=algorithm,
            config={"source": "migrated_from_v1", "original_order_id": order_id},
            input_hash=input_hash,
            run_id=run_id,
            metrics=metrics,
            workspace_id=workspace_id,
        )

        # Create plan items and acquisitions from schedule
        for item in schedule:
            # Create plan item
            schedule_db.create_plan_item(
                plan_id=plan.id,
                opportunity_id=item.get("opportunity_id", ""),
                satellite_id=item.get("satellite_id", ""),
                target_id=item.get("target_id", ""),
                start_time=item.get("start_time", ""),
                end_time=item.get("end_time", ""),
                roll_angle_deg=item.get("droll_deg", 0.0),
                pitch_angle_deg=0.0,
                value=item.get("value"),
            )

            # Create acquisition (committed)
            schedule_db.create_acquisition(
                satellite_id=item.get("satellite_id", ""),
                target_id=item.get("target_id", ""),
                start_time=item.get("start_time", ""),
                end_time=item.get("end_time", ""),
                roll_angle_deg=item.get("droll_deg", 0.0),
                pitch_angle_deg=0.0,
                mode="OPTICAL",  # Default, can't determine from legacy data
                state="committed",
                lock_level="none",
                source="auto",
                plan_id=plan.id,
                opportunity_id=item.get("opportunity_id", ""),
                workspace_id=workspace_id,
            )
            migrated_count += 1

        # Mark plan as committed
        schedule_db.update_plan_status(plan.id, "committed")

    logger.info(
        f"[Migration] Successfully migrated {migrated_count} acquisitions from workspace {workspace_id}"
    )

    return migrated_count


router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


# === Pydantic Models ===


class WorkspaceCreateRequest(BaseModel):
    """Request to create a new workspace."""

    name: str = Field(..., description="Workspace name")
    scenario_config: Optional[Dict[str, Any]] = Field(
        default=None, description="Satellites, targets, constraints config"
    )
    analysis_state: Optional[Dict[str, Any]] = Field(
        default=None, description="Passes, opportunities, statistics"
    )
    planning_state: Optional[Dict[str, Any]] = Field(
        default=None, description="Algorithm results, metrics"
    )
    orders_state: Optional[Dict[str, Any]] = Field(
        default=None, description="Accepted schedules"
    )
    ui_state: Optional[Dict[str, Any]] = Field(
        default=None, description="UI state (tabs, selections)"
    )
    czml_data: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="CZML visualization data"
    )
    mission_mode: Optional[str] = Field(
        default=None, description="OPTICAL, SAR, or COMMUNICATION"
    )
    time_window_start: Optional[str] = Field(
        default=None, description="Mission start time (ISO format)"
    )
    time_window_end: Optional[str] = Field(
        default=None, description="Mission end time (ISO format)"
    )
    # Config snapshot for reproducibility
    config_hash: Optional[str] = Field(
        default=None, description="SHA256 hash of config files at creation time"
    )
    config_snapshot: Optional[Dict[str, Any]] = Field(
        default=None, description="Snapshot of platform config for reproducibility"
    )


class WorkspaceUpdateRequest(BaseModel):
    """Request to update an existing workspace."""

    name: Optional[str] = Field(default=None, description="New workspace name")
    scenario_config: Optional[Dict[str, Any]] = Field(
        default=None, description="Updated scenario config"
    )
    analysis_state: Optional[Dict[str, Any]] = Field(
        default=None, description="Updated analysis state"
    )
    planning_state: Optional[Dict[str, Any]] = Field(
        default=None, description="Updated planning state"
    )
    orders_state: Optional[Dict[str, Any]] = Field(
        default=None, description="Updated orders state"
    )
    ui_state: Optional[Dict[str, Any]] = Field(
        default=None, description="Updated UI state"
    )
    czml_data: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Updated CZML data"
    )
    mission_mode: Optional[str] = Field(
        default=None, description="Updated mission mode"
    )
    time_window_start: Optional[str] = Field(
        default=None, description="Updated start time"
    )
    time_window_end: Optional[str] = Field(default=None, description="Updated end time")


class WorkspaceImportRequest(BaseModel):
    """Request to import a workspace."""

    data: Dict[str, Any] = Field(..., description="Exported workspace data")
    new_name: Optional[str] = Field(default=None, description="Override name")


class SaveCurrentRequest(BaseModel):
    """Request to save current mission state as workspace."""

    name: str = Field(..., description="Workspace name")
    include_ui_state: bool = Field(default=True, description="Include UI state in save")
    ui_state: Optional[Dict[str, Any]] = Field(
        default=None, description="UI state to save"
    )
    planning_state: Optional[Dict[str, Any]] = Field(
        default=None, description="Planning results from frontend store"
    )
    orders_state: Optional[Dict[str, Any]] = Field(
        default=None, description="Accepted orders from frontend store"
    )
    # Allow frontend to send mission data directly (for when backend lost in-memory state)
    mission_data: Optional[Dict[str, Any]] = Field(
        default=None, description="Mission data from frontend context"
    )


# === API Endpoints ===


@router.post("")
async def create_workspace(request: WorkspaceCreateRequest) -> Dict[str, Any]:
    """Create a new workspace.

    Returns the created workspace ID and summary.
    Automatically captures config snapshot for reproducibility.
    """
    try:
        db = get_workspace_db()

        # Auto-capture config snapshot if not provided
        config_hash = request.config_hash or get_config_hash()
        config_snapshot = request.config_snapshot or get_config_snapshot()

        # Add config info to scenario_config for storage
        scenario_config = request.scenario_config or {}
        scenario_config["config_hash"] = config_hash
        scenario_config["config_snapshot"] = config_snapshot

        workspace_id = db.create_workspace(
            name=request.name,
            scenario_config=scenario_config,
            analysis_state=request.analysis_state,
            planning_state=request.planning_state,
            orders_state=request.orders_state,
            ui_state=request.ui_state,
            czml_data=request.czml_data,
            mission_mode=request.mission_mode,
            time_window_start=request.time_window_start,
            time_window_end=request.time_window_end,
        )

        workspace = db.get_workspace(workspace_id, include_czml=False)
        if not workspace:
            raise HTTPException(status_code=500, detail="Failed to create workspace")

        return {
            "success": True,
            "message": f"Workspace '{request.name}' created successfully",
            "workspace_id": workspace_id,
            "config_hash": config_hash,
            "workspace": {
                "id": workspace.id,
                "name": workspace.name,
                "created_at": workspace.created_at,
                "mission_mode": workspace.mission_mode,
                "satellites_count": workspace.satellites_count,
                "targets_count": workspace.targets_count,
            },
        }

    except Exception as e:
        logger.error(f"Error creating workspace: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_workspaces(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """List all workspaces.

    Returns paginated list of workspace summaries.
    """
    try:
        db = get_workspace_db()

        workspaces = db.list_workspaces(limit=limit, offset=offset)
        total = db.get_workspace_count()

        return {
            "success": True,
            "workspaces": [w.to_dict() for w in workspaces],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"Error listing workspaces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}")
async def get_workspace(workspace_id: str, include_czml: bool = True) -> Dict[str, Any]:
    """Get a workspace by ID.

    Returns complete workspace data including state blobs.
    Also triggers migration of legacy orders_state to v2 tables if needed.
    """
    try:
        db = get_workspace_db()

        workspace = db.get_workspace(workspace_id, include_czml=include_czml)
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        # Backward compatibility: migrate legacy orders_state to v2 tables
        # This is a one-time migration that runs on first load after upgrade
        migrated_count = 0
        if workspace.orders_state:
            migrated_count = _migrate_orders_state_to_v2(
                workspace_id=workspace_id,
                orders_state=workspace.orders_state,
            )

        response_data = workspace.to_dict(include_czml=include_czml)

        # Add migration info to response
        if migrated_count > 0:
            response_data["_migration"] = {
                "migrated_acquisitions": migrated_count,
                "message": f"Migrated {migrated_count} acquisitions from legacy orders_state to v2 tables",
            }

        return {
            "success": True,
            "workspace": response_data,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workspace {workspace_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{workspace_id}")
async def update_workspace(
    workspace_id: str, request: WorkspaceUpdateRequest
) -> Dict[str, Any]:
    """Update an existing workspace.

    Partial updates supported - only provided fields are updated.
    """
    try:
        db = get_workspace_db()

        success = db.update_workspace(
            workspace_id=workspace_id,
            name=request.name,
            scenario_config=request.scenario_config,
            analysis_state=request.analysis_state,
            planning_state=request.planning_state,
            orders_state=request.orders_state,
            ui_state=request.ui_state,
            czml_data=request.czml_data,
            mission_mode=request.mission_mode,
            time_window_start=request.time_window_start,
            time_window_end=request.time_window_end,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Workspace not found")

        workspace = db.get_workspace(workspace_id, include_czml=False)

        return {
            "success": True,
            "message": "Workspace updated successfully",
            "workspace": (
                {
                    "id": workspace.id,
                    "name": workspace.name,
                    "updated_at": workspace.updated_at,
                }
                if workspace
                else None
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating workspace {workspace_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: str) -> Dict[str, Any]:
    """Delete a workspace.

    Permanently removes the workspace and all associated data.
    """
    try:
        db = get_workspace_db()

        deleted = db.delete_workspace(workspace_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Workspace not found")

        return {
            "success": True,
            "message": "Workspace deleted successfully",
            "workspace_id": workspace_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting workspace {workspace_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workspace_id}/export")
async def export_workspace(workspace_id: str) -> Dict[str, Any]:
    """Export a workspace as portable JSON.

    Returns complete workspace data for backup/transfer.
    """
    try:
        db = get_workspace_db()

        export_data = db.export_workspace(workspace_id)

        if not export_data:
            raise HTTPException(status_code=404, detail="Workspace not found")

        return {
            "success": True,
            "message": "Workspace exported successfully",
            "export": export_data,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting workspace {workspace_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
async def import_workspace(request: WorkspaceImportRequest) -> Dict[str, Any]:
    """Import a workspace from exported JSON.

    Creates a new workspace from previously exported data.
    """
    try:
        db = get_workspace_db()

        workspace_id = db.import_workspace(data=request.data, new_name=request.new_name)

        workspace = db.get_workspace(workspace_id, include_czml=False)

        return {
            "success": True,
            "message": "Workspace imported successfully",
            "workspace_id": workspace_id,
            "workspace": (
                {
                    "id": workspace.id,
                    "name": workspace.name,
                    "created_at": workspace.created_at,
                }
                if workspace
                else None
            ),
        }

    except Exception as e:
        logger.error(f"Error importing workspace: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save-current")
async def save_current_mission(request: SaveCurrentRequest) -> Dict[str, Any]:
    """Save the current mission state as a new workspace.

    Captures the current mission analysis, planning results, and optionally UI state.
    This endpoint reads from the global current_mission_data in main.py.
    """
    try:
        # Import module to get live reference to global variable
        # (importing the variable directly gives a snapshot, not a reference)
        import backend.main as main_module

        current_mission_data = main_module.current_mission_data

        logger.info(f"[Workspace Save] Request name: {request.name}")
        logger.info(
            f"[Workspace Save] current_mission_data exists: {current_mission_data is not None}"
        )
        logger.info(
            f"[Workspace Save] planning_state: {request.planning_state is not None}"
        )
        logger.info(
            f"[Workspace Save] orders_state: {request.orders_state is not None}"
        )
        logger.info(
            f"[Workspace Save] frontend mission_data: {request.mission_data is not None}"
        )

        # If backend lost in-memory data but frontend sent mission_data, use that
        if not current_mission_data and request.mission_data:
            logger.info("[Workspace Save] Using frontend-provided mission data")
            current_mission_data = {
                "mission_data": request.mission_data,
                "czml_data": request.mission_data.get("czml_data", []),
                "passes": request.mission_data.get("passes", []),
                "targets": request.mission_data.get("targets", []),
            }

        if not current_mission_data:
            raise HTTPException(
                status_code=400,
                detail="No mission data available. Run mission analysis first.",
            )

        db = get_workspace_db()

        # Extract data from current mission
        mission_data = current_mission_data.get("mission_data", {})
        czml_data = current_mission_data.get("czml_data", [])
        passes = current_mission_data.get("passes", [])
        targets = current_mission_data.get("targets", [])

        # Build scenario config
        satellites = mission_data.get("satellites", [])
        if not satellites and mission_data.get("satellite_name"):
            # Legacy single satellite mode
            satellites = [{"name": mission_data.get("satellite_name"), "id": "sat_0"}]

        scenario_config = {
            "satellites": satellites,
            "targets": [
                {
                    "name": t.name if hasattr(t, "name") else t.get("name"),
                    "latitude": (
                        t.latitude if hasattr(t, "latitude") else t.get("latitude")
                    ),
                    "longitude": (
                        t.longitude if hasattr(t, "longitude") else t.get("longitude")
                    ),
                    "priority": (
                        getattr(t, "priority", 5)
                        if hasattr(t, "priority")
                        else t.get("priority", 5)
                    ),
                }
                for t in targets
            ],
            "constraints": {
                "elevation_mask_deg": mission_data.get("elevation_mask", 10),
                "max_spacecraft_roll_deg": mission_data.get(
                    "max_spacecraft_roll_deg", 45
                ),
                "sensor_fov_half_angle_deg": mission_data.get(
                    "sensor_fov_half_angle_deg"
                ),
            },
        }

        # Build analysis state with FULL mission_data for proper restoration
        analysis_state = {
            "run_timestamp": mission_data.get("analysis_timestamp"),
            "passes": [p.to_dict() if hasattr(p, "to_dict") else p for p in passes],
            "statistics": {
                "total_passes": len(passes),
            },
            # Store full mission_data for complete restoration on load
            "mission_data": {
                "satellite_name": mission_data.get("satellite_name"),
                "satellites": mission_data.get("satellites", []),
                "is_constellation": mission_data.get("is_constellation", False),
                "mission_type": mission_data.get("mission_type", "imaging"),
                "start_time": mission_data.get("start_time"),
                "end_time": mission_data.get("end_time"),
                "elevation_mask": mission_data.get("elevation_mask", 10),
                "sensor_fov_half_angle_deg": mission_data.get(
                    "sensor_fov_half_angle_deg"
                ),
                "max_spacecraft_roll_deg": mission_data.get(
                    "max_spacecraft_roll_deg", 45
                ),
                "total_passes": len(passes),
                "targets": [
                    {
                        "name": t.name if hasattr(t, "name") else t.get("name"),
                        "latitude": (
                            t.latitude if hasattr(t, "latitude") else t.get("latitude")
                        ),
                        "longitude": (
                            t.longitude
                            if hasattr(t, "longitude")
                            else t.get("longitude")
                        ),
                        "priority": (
                            getattr(t, "priority", 5)
                            if hasattr(t, "priority")
                            else t.get("priority", 5)
                        ),
                        "color": (
                            getattr(t, "color", None)
                            if hasattr(t, "color")
                            else t.get("color")
                        ),
                    }
                    for t in targets
                ],
                "passes": [p.to_dict() if hasattr(p, "to_dict") else p for p in passes],
                "coverage_percentage": mission_data.get("coverage_percentage"),
                "pass_statistics": mission_data.get("pass_statistics"),
            },
        }

        # Mission mode
        mission_type = mission_data.get("mission_type", "imaging")
        mission_mode = mission_type.upper() if mission_type else "IMAGING"

        # Create workspace
        workspace_id = db.create_workspace(
            name=request.name,
            scenario_config=scenario_config,
            analysis_state=analysis_state,
            planning_state=request.planning_state,  # From frontend planning store
            orders_state=request.orders_state,  # From frontend orders store
            ui_state=request.ui_state if request.include_ui_state else None,
            czml_data=czml_data,
            mission_mode=mission_mode,
            time_window_start=mission_data.get("start_time"),
            time_window_end=mission_data.get("end_time"),
        )

        workspace = db.get_workspace(workspace_id, include_czml=False)

        return {
            "success": True,
            "message": f"Current mission saved as workspace '{request.name}'",
            "workspace_id": workspace_id,
            "workspace": (
                {
                    "id": workspace.id,
                    "name": workspace.name,
                    "created_at": workspace.created_at,
                    "mission_mode": workspace.mission_mode,
                    "satellites_count": workspace.satellites_count,
                    "targets_count": workspace.targets_count,
                }
                if workspace
                else None
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving current mission: {e}")
        raise HTTPException(status_code=500, detail=str(e))
