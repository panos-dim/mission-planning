"""
Configuration Admin Router for Mission Planning.

Provides endpoints for managing platform configuration with versioning:
- SAR modes configuration
- Satellite bus specifications
- Config versioning and snapshots
- Resolved config introspection
"""

import hashlib
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml  # type: ignore[import-untyped]
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.config_resolver import (
    ConfigResolver,
    get_config_hash,
    get_config_resolver,
    get_config_snapshot,
    resolve_mission_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/config", tags=["config-admin"])

# Config directory path
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
SNAPSHOTS_DIR = CONFIG_DIR / "snapshots"


# === Pydantic Models ===


class SARModeIncidence(BaseModel):
    """SAR mode incidence angle configuration."""

    recommended_min: float = Field(ge=5, le=55)
    recommended_max: float = Field(ge=10, le=60)
    absolute_min: float = Field(ge=0, le=45)
    absolute_max: float = Field(ge=20, le=70)


class SARModeScene(BaseModel):
    """SAR mode scene configuration."""

    width_km: float = Field(gt=0, le=500)
    length_km: float = Field(gt=0, le=1000)
    max_length_km: Optional[float] = Field(default=None, gt=0, le=2000)


class SARModeCollection(BaseModel):
    """SAR mode collection parameters."""

    duration_s: Optional[float] = Field(default=None, ge=0, le=120)
    azimuth_resolution_m: float = Field(gt=0, le=100)
    range_resolution_m: float = Field(gt=0, le=100)


class SARModeQuality(BaseModel):
    """SAR mode quality scoring configuration."""

    optimal_incidence_deg: float = Field(ge=10, le=50)
    quality_model: str = Field(default="band", pattern="^(band|monotonic)$")


class SARModeConfig(BaseModel):
    """Complete SAR mode configuration."""

    display_name: str
    description: str
    incidence_angle: SARModeIncidence
    scene: SARModeScene
    collection: SARModeCollection
    quality: SARModeQuality


class SARModesUpdateRequest(BaseModel):
    """Request to update SAR modes configuration."""

    modes: Dict[str, SARModeConfig]


class SpacecraftBusConfig(BaseModel):
    """Spacecraft bus configuration."""

    max_roll_deg: float = Field(ge=0, le=90)
    max_roll_rate_dps: float = Field(gt=0, le=10)
    max_roll_accel_dps2: float = Field(gt=0, le=100)
    max_pitch_deg: float = Field(ge=0, le=90, default=0)
    max_pitch_rate_dps: float = Field(ge=0, le=10, default=0)
    max_pitch_accel_dps2: float = Field(ge=0, le=100, default=0)
    settling_time_s: float = Field(ge=0, le=60, default=3)


class SatelliteBusUpdateRequest(BaseModel):
    """Request to update satellite bus configuration."""

    satellite_id: str
    bus_config: SpacecraftBusConfig


class ConfigSnapshotInfo(BaseModel):
    """Config snapshot information."""

    id: str
    timestamp: str
    description: Optional[str] = None
    config_hash: str
    files: List[str]


class CreateSnapshotRequest(BaseModel):
    """Request to create a config snapshot."""

    description: Optional[str] = None


class ConfigDiffResponse(BaseModel):
    """Response with config diff."""

    has_changes: bool
    changes: List[Dict[str, Any]]


# === Helper Functions ===
# Note: get_config_hash is imported from config_resolver


def load_yaml_config(filename: str) -> Dict[str, Any]:
    """Load a YAML config file."""
    filepath = CONFIG_DIR / filename
    if not filepath.exists():
        raise HTTPException(
            status_code=404, detail=f"Config file not found: {filename}"
        )
    with open(filepath, "r") as f:
        return yaml.safe_load(f) or {}


def save_yaml_config(filename: str, data: Dict[str, Any]) -> None:
    """Save a YAML config file."""
    filepath = CONFIG_DIR / filename
    with open(filepath, "w") as f:
        yaml.dump(
            data, f, default_flow_style=False, sort_keys=False, allow_unicode=True
        )


def ensure_snapshots_dir() -> None:
    """Ensure snapshots directory exists."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


# === SAR Modes Endpoints ===


@router.get("/sar-modes")
async def get_sar_modes() -> Dict[str, Any]:
    """Get current SAR modes configuration."""
    try:
        config = load_yaml_config("sar_modes.yaml")
        return {
            "success": True,
            "modes": config.get("modes", {}),
            "look_side": config.get("look_side", {}),
            "pass_direction": config.get("pass_direction", {}),
            "spacecraft": config.get("spacecraft", {}),
            "constraints": config.get("constraints", {}),
        }
    except Exception as e:
        logger.error(f"Error loading SAR modes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/sar-modes")
async def update_sar_modes(request: SARModesUpdateRequest) -> Dict[str, Any]:
    """Update SAR modes configuration."""
    try:
        # Load existing config to preserve non-mode sections
        config = load_yaml_config("sar_modes.yaml")

        # Convert Pydantic models to dicts
        modes_dict = {}
        for mode_name, mode_config in request.modes.items():
            modes_dict[mode_name] = {
                "display_name": mode_config.display_name,
                "description": mode_config.description,
                "incidence_angle": mode_config.incidence_angle.model_dump(),
                "scene": mode_config.scene.model_dump(exclude_none=True),
                "collection": mode_config.collection.model_dump(exclude_none=True),
                "quality": mode_config.quality.model_dump(),
            }

        config["modes"] = modes_dict
        save_yaml_config("sar_modes.yaml", config)

        return {
            "success": True,
            "message": "SAR modes updated successfully",
            "config_hash": get_config_hash(),
        }
    except Exception as e:
        logger.error(f"Error updating SAR modes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/sar-modes/{mode_name}")
async def update_sar_mode(mode_name: str, mode_config: SARModeConfig) -> Dict[str, Any]:
    """Update a single SAR mode."""
    try:
        config = load_yaml_config("sar_modes.yaml")

        if "modes" not in config:
            config["modes"] = {}

        config["modes"][mode_name] = {
            "display_name": mode_config.display_name,
            "description": mode_config.description,
            "incidence_angle": mode_config.incidence_angle.model_dump(),
            "scene": mode_config.scene.model_dump(exclude_none=True),
            "collection": mode_config.collection.model_dump(exclude_none=True),
            "quality": mode_config.quality.model_dump(),
        }

        save_yaml_config("sar_modes.yaml", config)

        return {
            "success": True,
            "message": f"SAR mode '{mode_name}' updated successfully",
            "config_hash": get_config_hash(),
        }
    except Exception as e:
        logger.error(f"Error updating SAR mode {mode_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === Satellite Bus Config Endpoints ===


@router.get("/satellite-bus/{satellite_id}")
async def get_satellite_bus_config(satellite_id: str) -> Dict[str, Any]:
    """Get spacecraft bus configuration for a satellite."""
    try:
        config = load_yaml_config("satellites.yaml")
        satellites = config.get("satellites", [])

        # Find satellite
        satellite = None
        for sat in satellites:
            if sat.get("id") == satellite_id:
                satellite = sat
                break

        if not satellite:
            raise HTTPException(
                status_code=404, detail=f"Satellite not found: {satellite_id}"
            )

        # Get type-specific defaults
        imaging_type = satellite.get("imaging_type", "optical")
        settings = config.get("satellite_settings", {}).get(imaging_type, {})
        spacecraft_defaults = settings.get("spacecraft", {})

        # Build bus config with defaults
        bus_config = {
            "max_roll_deg": satellite.get(
                "max_spacecraft_roll_deg",
                spacecraft_defaults.get("max_spacecraft_roll_deg", 45),
            ),
            "max_roll_rate_dps": satellite.get(
                "max_roll_rate_dps", spacecraft_defaults.get("max_roll_rate_dps", 1.0)
            ),
            "max_roll_accel_dps2": satellite.get(
                "max_roll_accel_dps2",
                spacecraft_defaults.get("max_roll_accel_dps2", 1.0),
            ),
            "max_pitch_deg": satellite.get(
                "max_spacecraft_pitch_deg",
                spacecraft_defaults.get("max_spacecraft_pitch_deg", 0),
            ),
            "max_pitch_rate_dps": satellite.get(
                "max_pitch_rate_dps", spacecraft_defaults.get("max_pitch_rate_dps", 0)
            ),
            "max_pitch_accel_dps2": satellite.get(
                "max_pitch_accel_dps2",
                spacecraft_defaults.get("max_pitch_accel_dps2", 0),
            ),
            "settling_time_s": satellite.get(
                "settling_time_s", spacecraft_defaults.get("settling_time_s", 5.0)
            ),
        }

        return {
            "success": True,
            "satellite_id": satellite_id,
            "satellite_name": satellite.get("name"),
            "imaging_type": imaging_type,
            "bus_config": bus_config,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting satellite bus config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/satellite-bus/{satellite_id}")
async def update_satellite_bus_config(
    satellite_id: str, bus_config: SpacecraftBusConfig
) -> Dict[str, Any]:
    """Update spacecraft bus configuration for a satellite."""
    try:
        config = load_yaml_config("satellites.yaml")
        satellites = config.get("satellites", [])

        # Find and update satellite
        found = False
        for i, sat in enumerate(satellites):
            if sat.get("id") == satellite_id:
                satellites[i]["max_spacecraft_roll_deg"] = bus_config.max_roll_deg
                satellites[i]["max_roll_rate_dps"] = bus_config.max_roll_rate_dps
                satellites[i]["max_roll_accel_dps2"] = bus_config.max_roll_accel_dps2
                satellites[i]["max_spacecraft_pitch_deg"] = bus_config.max_pitch_deg
                satellites[i]["max_pitch_rate_dps"] = bus_config.max_pitch_rate_dps
                satellites[i]["max_pitch_accel_dps2"] = bus_config.max_pitch_accel_dps2
                satellites[i]["settling_time_s"] = bus_config.settling_time_s
                found = True
                break

        if not found:
            raise HTTPException(
                status_code=404, detail=f"Satellite not found: {satellite_id}"
            )

        config["satellites"] = satellites
        save_yaml_config("satellites.yaml", config)

        return {
            "success": True,
            "message": f"Bus configuration updated for satellite '{satellite_id}'",
            "config_hash": get_config_hash(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating satellite bus config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === Config Versioning Endpoints ===


@router.get("/snapshots")
async def list_snapshots() -> Dict[str, Any]:
    """List all config snapshots."""
    try:
        ensure_snapshots_dir()

        snapshots = []
        for snapshot_dir in sorted(SNAPSHOTS_DIR.iterdir(), reverse=True):
            if snapshot_dir.is_dir():
                meta_file = snapshot_dir / "metadata.json"
                if meta_file.exists():
                    with open(meta_file, "r") as f:
                        meta = json.load(f)
                    snapshots.append(meta)

        return {
            "success": True,
            "snapshots": snapshots,
            "current_hash": get_config_hash(),
        }
    except Exception as e:
        logger.error(f"Error listing snapshots: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/snapshots")
async def create_snapshot(request: CreateSnapshotRequest) -> Dict[str, Any]:
    """Create a new config snapshot."""
    try:
        ensure_snapshots_dir()

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        snapshot_id = f"snapshot_{timestamp}"
        snapshot_dir = SNAPSHOTS_DIR / snapshot_id
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Copy config files
        config_files = [
            "satellites.yaml",
            "sar_modes.yaml",
            "mission_settings.yaml",
            "ground_stations.yaml",
        ]
        copied_files = []
        for filename in config_files:
            src = CONFIG_DIR / filename
            if src.exists():
                shutil.copy2(src, snapshot_dir / filename)
                copied_files.append(filename)

        # Create metadata
        metadata = {
            "id": snapshot_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "description": request.description,
            "config_hash": get_config_hash(),
            "files": copied_files,
        }

        with open(snapshot_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        return {
            "success": True,
            "message": "Config snapshot created",
            "snapshot": metadata,
        }
    except Exception as e:
        logger.error(f"Error creating snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/snapshots/{snapshot_id}/restore")
async def restore_snapshot(snapshot_id: str) -> Dict[str, Any]:
    """Restore config from a snapshot."""
    try:
        snapshot_dir = SNAPSHOTS_DIR / snapshot_id
        if not snapshot_dir.exists():
            raise HTTPException(
                status_code=404, detail=f"Snapshot not found: {snapshot_id}"
            )

        # Create backup of current config before restore
        backup_timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_id = f"pre_restore_{backup_timestamp}"
        backup_dir = SNAPSHOTS_DIR / backup_id
        backup_dir.mkdir(parents=True, exist_ok=True)

        config_files = [
            "satellites.yaml",
            "sar_modes.yaml",
            "mission_settings.yaml",
            "ground_stations.yaml",
        ]

        # Backup current
        for filename in config_files:
            src = CONFIG_DIR / filename
            if src.exists():
                shutil.copy2(src, backup_dir / filename)

        # Restore from snapshot
        restored_files = []
        for filename in config_files:
            src = snapshot_dir / filename
            if src.exists():
                shutil.copy2(src, CONFIG_DIR / filename)
                restored_files.append(filename)

        return {
            "success": True,
            "message": f"Config restored from snapshot '{snapshot_id}'",
            "backup_id": backup_id,
            "restored_files": restored_files,
            "config_hash": get_config_hash(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/snapshots/{snapshot_id}")
async def delete_snapshot(snapshot_id: str) -> Dict[str, Any]:
    """Delete a config snapshot."""
    try:
        snapshot_dir = SNAPSHOTS_DIR / snapshot_id
        if not snapshot_dir.exists():
            raise HTTPException(
                status_code=404, detail=f"Snapshot not found: {snapshot_id}"
            )

        shutil.rmtree(snapshot_dir)

        return {
            "success": True,
            "message": f"Snapshot '{snapshot_id}' deleted",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hash")
async def get_current_hash() -> Dict[str, Any]:
    """Get current config hash."""
    return {
        "success": True,
        "config_hash": get_config_hash(),
    }


@router.post("/restore-defaults")
async def restore_defaults() -> Dict[str, Any]:
    """Restore default configuration (requires backup snapshot first)."""
    try:
        # Create snapshot before restore
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_id = f"pre_default_restore_{timestamp}"
        backup_dir = SNAPSHOTS_DIR / backup_id
        ensure_snapshots_dir()
        backup_dir.mkdir(parents=True, exist_ok=True)

        config_files = [
            "satellites.yaml",
            "sar_modes.yaml",
            "mission_settings.yaml",
            "ground_stations.yaml",
        ]

        # Backup current
        for filename in config_files:
            src = CONFIG_DIR / filename
            if src.exists():
                shutil.copy2(src, backup_dir / filename)

        # Save metadata
        metadata = {
            "id": backup_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "description": "Auto-backup before restoring defaults",
            "config_hash": get_config_hash(),
            "files": config_files,
        }
        with open(backup_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        return {
            "success": True,
            "message": "Backup created. Default restoration must be done manually by copying from defaults/ directory.",
            "backup_id": backup_id,
        }
    except Exception as e:
        logger.error(f"Error creating backup before restore: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === Resolved Config Endpoints ===


class ResolveMissionConfigRequest(BaseModel):
    """Request to resolve mission configuration."""

    mission_input: Dict[str, Any]
    satellite_ids: List[str]
    clamp_on_warning: bool = True


@router.post("/resolved")
async def resolve_config(request: ResolveMissionConfigRequest) -> Dict[str, Any]:
    """
    Resolve mission configuration by combining platform truth with mission inputs.

    This endpoint validates mission inputs against platform constraints and
    returns the fully resolved configuration that will be used for the run.

    Use this to preview what configuration will be applied before running.
    """
    try:
        result = resolve_mission_config(
            mission_input=request.mission_input,
            satellite_ids=request.satellite_ids,
            clamp_on_warning=request.clamp_on_warning,
        )
        return result.to_dict()
    except Exception as e:
        logger.error(f"Error resolving config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resolved")
async def get_resolved_config(
    run_id: Optional[str] = Query(
        None, description="Workspace run ID to get resolved config for"
    ),
) -> Dict[str, Any]:
    """
    Get resolved configuration for a previous run.

    If run_id is provided, returns the config snapshot stored with that workspace.
    Otherwise, returns the current platform configuration state.
    """
    try:
        if run_id:
            # TODO: Load config snapshot from workspace database
            # For now, return current config
            pass

        # Return current config snapshot
        snapshot = get_config_snapshot()
        return {
            "success": True,
            "config_hash": snapshot["config_hash"],
            "timestamp": snapshot["timestamp"],
            "snapshot": snapshot,
        }
    except Exception as e:
        logger.error(f"Error getting resolved config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/governance")
async def get_governance_rules() -> Dict[str, Any]:
    """
    Get parameter governance rules.

    Returns which parameters are admin-only vs mission-input configurable.
    """
    resolver = get_config_resolver()
    return {
        "success": True,
        "admin_only_params": list(resolver.ADMIN_ONLY_PARAMS),
        "mission_input_params": {
            "common": ["start_time", "end_time", "targets", "satellites"],
            "sar": [
                "sar.imaging_mode",
                "sar.look_side",
                "sar.pass_direction",
                "sar.incidence_min_deg",
                "sar.incidence_max_deg",
            ],
            "optical": ["pointingAngle", "illumination_filter"],
        },
        "derived_params": [
            "pass_duration_s",
            "incidence_angle_deg",
            "elevation_deg",
            "maneuver_time_s",
            "slew_angle_deg",
        ],
    }


@router.post("/reload")
async def reload_configs() -> Dict[str, Any]:
    """Reload all configuration files from disk."""
    try:
        resolver = get_config_resolver()
        resolver.load_configs(force_reload=True)
        return {
            "success": True,
            "message": "Configuration reloaded",
            "config_hash": resolver.get_config_hash(),
        }
    except Exception as e:
        logger.error(f"Error reloading config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
