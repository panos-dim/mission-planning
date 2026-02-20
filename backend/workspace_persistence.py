"""
Workspace Persistence Layer for Mission Planning.

Provides SQLite-based persistence for workspace state, enabling:
- Save/Load/List/Delete workspaces
- JSON blob storage for analysis, planning, and orders state
- Schema versioning for future migrations
- Export/Import capabilities
"""

import json
import logging
import os
import sqlite3
import uuid
import zlib
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

# Schema version for migration support
SCHEMA_VERSION = "1.0"

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "workspaces.db"


@dataclass
class WorkspaceSummary:
    """Summary information for workspace listing."""

    id: str
    name: str
    created_at: str
    updated_at: str
    mission_mode: Optional[str]
    time_window_start: Optional[str]
    time_window_end: Optional[str]
    satellites_count: int
    targets_count: int
    last_run_status: Optional[str]
    schema_version: str
    app_version: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "mission_mode": self.mission_mode,
            "time_window_start": self.time_window_start,
            "time_window_end": self.time_window_end,
            "satellites_count": self.satellites_count,
            "targets_count": self.targets_count,
            "last_run_status": self.last_run_status,
            "schema_version": self.schema_version,
            "app_version": self.app_version,
        }


@dataclass
class WorkspaceData:
    """Complete workspace data including all state blobs."""

    id: str
    name: str
    created_at: str
    updated_at: str
    schema_version: str
    app_version: Optional[str]
    mission_mode: Optional[str]
    time_window_start: Optional[str]
    time_window_end: Optional[str]
    satellites_count: int
    targets_count: int
    last_run_status: Optional[str]
    last_run_timestamp: Optional[str]

    # State blobs (JSON strings)
    scenario_config: Optional[Dict[str, Any]]
    analysis_state: Optional[Dict[str, Any]]
    planning_state: Optional[Dict[str, Any]]
    orders_state: Optional[Dict[str, Any]]
    ui_state: Optional[Dict[str, Any]]

    # CZML blob (compressed)
    czml_blob: Optional[bytes]

    def to_dict(self, include_czml: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "schema_version": self.schema_version,
            "app_version": self.app_version,
            "mission_mode": self.mission_mode,
            "time_window_start": self.time_window_start,
            "time_window_end": self.time_window_end,
            "satellites_count": self.satellites_count,
            "targets_count": self.targets_count,
            "last_run_status": self.last_run_status,
            "last_run_timestamp": self.last_run_timestamp,
            "scenario_config": self.scenario_config,
            "analysis_state": self.analysis_state,
            "planning_state": self.planning_state,
            "orders_state": self.orders_state,
            "ui_state": self.ui_state,
        }
        if include_czml and self.czml_blob:
            # Decompress and parse CZML
            try:
                czml_json = zlib.decompress(self.czml_blob).decode("utf-8")
                result["czml_data"] = json.loads(czml_json)
            except Exception as e:
                logger.warning(f"Failed to decompress CZML: {e}")
                result["czml_data"] = None
        return result


class WorkspaceDB:
    """SQLite-based workspace persistence manager."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Uses default if not specified.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_directory()
        self._init_schema()

    def _ensure_directory(self) -> None:
        """Ensure the database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Initialize database schema if not exists."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Core workspace table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    schema_version TEXT DEFAULT '1.0',
                    app_version TEXT,

                    -- Scenario summary (denormalized for listing)
                    mission_mode TEXT,
                    time_window_start TEXT,
                    time_window_end TEXT,
                    satellites_count INTEGER DEFAULT 0,
                    targets_count INTEGER DEFAULT 0,

                    -- Status
                    last_run_status TEXT,
                    last_run_timestamp TEXT
                )
            """
            )

            # Workspace state blobs (JSON storage for v1 simplicity)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS workspace_blobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

                    -- State snapshots (JSON blobs)
                    scenario_config_json TEXT,
                    analysis_state_json TEXT,
                    planning_state_json TEXT,
                    orders_state_json TEXT,
                    ui_state_json TEXT,

                    -- Large binary data (compressed)
                    czml_blob BLOB,

                    -- Metadata
                    config_hash TEXT,
                    created_at TEXT DEFAULT (datetime('now')),

                    UNIQUE(workspace_id)
                )
            """
            )

            # Indexes for fast lookups
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workspace_blobs_workspace_id
                ON workspace_blobs(workspace_id)
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workspaces_updated_at
                ON workspaces(updated_at DESC)
            """
            )

            conn.commit()
            logger.info(f"Workspace database initialized at {self.db_path}")

    def create_workspace(
        self,
        name: str,
        scenario_config: Optional[Dict[str, Any]] = None,
        analysis_state: Optional[Dict[str, Any]] = None,
        planning_state: Optional[Dict[str, Any]] = None,
        orders_state: Optional[Dict[str, Any]] = None,
        ui_state: Optional[Dict[str, Any]] = None,
        czml_data: Optional[List[Dict[str, Any]]] = None,
        mission_mode: Optional[str] = None,
        time_window_start: Optional[str] = None,
        time_window_end: Optional[str] = None,
        app_version: Optional[str] = None,
    ) -> str:
        """Create a new workspace.

        Args:
            name: Workspace name
            scenario_config: Satellites, targets, constraints config
            analysis_state: Passes, opportunities, statistics
            planning_state: Algorithm results, metrics
            orders_state: Accepted schedules
            ui_state: Optional UI state (tabs, selections)
            czml_data: CZML visualization data
            mission_mode: OPTICAL, SAR, or COMMUNICATION
            time_window_start: Mission start time (ISO format)
            time_window_end: Mission end time (ISO format)
            app_version: Application version string

        Returns:
            Workspace ID
        """
        workspace_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat() + "Z"

        # Extract counts from scenario config
        satellites_count = 0
        targets_count = 0
        if scenario_config:
            satellites_count = len(scenario_config.get("satellites", []))
            targets_count = len(scenario_config.get("targets", []))

        # Determine last run status
        last_run_status = None
        last_run_timestamp = None
        if analysis_state:
            last_run_status = "success"
            last_run_timestamp = analysis_state.get("run_timestamp", now)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Insert workspace record
            cursor.execute(
                """
                INSERT INTO workspaces (
                    id, name, created_at, updated_at, schema_version, app_version,
                    mission_mode, time_window_start, time_window_end,
                    satellites_count, targets_count,
                    last_run_status, last_run_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    workspace_id,
                    name,
                    now,
                    now,
                    SCHEMA_VERSION,
                    app_version,
                    mission_mode,
                    time_window_start,
                    time_window_end,
                    satellites_count,
                    targets_count,
                    last_run_status,
                    last_run_timestamp,
                ),
            )

            # Compress CZML if provided
            czml_blob = None
            if czml_data:
                czml_json = json.dumps(czml_data)
                czml_blob = zlib.compress(czml_json.encode("utf-8"))

            # Insert state blobs
            cursor.execute(
                """
                INSERT INTO workspace_blobs (
                    workspace_id,
                    scenario_config_json, analysis_state_json,
                    planning_state_json, orders_state_json, ui_state_json,
                    czml_blob, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    workspace_id,
                    json.dumps(scenario_config) if scenario_config else None,
                    json.dumps(analysis_state) if analysis_state else None,
                    json.dumps(planning_state) if planning_state else None,
                    json.dumps(orders_state) if orders_state else None,
                    json.dumps(ui_state) if ui_state else None,
                    czml_blob,
                    now,
                ),
            )

            conn.commit()
            logger.info(f"Created workspace '{name}' with ID: {workspace_id}")
            return workspace_id

    def update_workspace(
        self,
        workspace_id: str,
        name: Optional[str] = None,
        scenario_config: Optional[Dict[str, Any]] = None,
        analysis_state: Optional[Dict[str, Any]] = None,
        planning_state: Optional[Dict[str, Any]] = None,
        orders_state: Optional[Dict[str, Any]] = None,
        ui_state: Optional[Dict[str, Any]] = None,
        czml_data: Optional[List[Dict[str, Any]]] = None,
        mission_mode: Optional[str] = None,
        time_window_start: Optional[str] = None,
        time_window_end: Optional[str] = None,
    ) -> bool:
        """Update an existing workspace.

        Args:
            workspace_id: Workspace to update
            name: New name (optional)
            scenario_config: Updated scenario config (optional)
            analysis_state: Updated analysis state (optional)
            planning_state: Updated planning state (optional)
            orders_state: Updated orders state (optional)
            ui_state: Updated UI state (optional)
            czml_data: Updated CZML data (optional)
            mission_mode: Updated mission mode (optional)
            time_window_start: Updated start time (optional)
            time_window_end: Updated end time (optional)

        Returns:
            True if update succeeded
        """
        now = datetime.now(timezone.utc).isoformat() + "Z"

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check workspace exists
            cursor.execute("SELECT id FROM workspaces WHERE id = ?", (workspace_id,))
            if not cursor.fetchone():
                logger.warning(f"Workspace not found: {workspace_id}")
                return False

            # Build workspace update
            updates = ["updated_at = ?"]
            params: List[Any] = [now]

            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if mission_mode is not None:
                updates.append("mission_mode = ?")
                params.append(mission_mode)
            if time_window_start is not None:
                updates.append("time_window_start = ?")
                params.append(time_window_start)
            if time_window_end is not None:
                updates.append("time_window_end = ?")
                params.append(time_window_end)
            if scenario_config is not None:
                updates.append("satellites_count = ?")
                params.append(len(scenario_config.get("satellites", [])))
                updates.append("targets_count = ?")
                params.append(len(scenario_config.get("targets", [])))
            if analysis_state is not None:
                updates.append("last_run_status = ?")
                params.append("success")
                updates.append("last_run_timestamp = ?")
                params.append(analysis_state.get("run_timestamp", now))

            params.append(workspace_id)
            cursor.execute(
                f"UPDATE workspaces SET {', '.join(updates)} WHERE id = ?", params
            )

            # Update blobs
            blob_updates = []
            blob_params: List[Any] = []

            if scenario_config is not None:
                blob_updates.append("scenario_config_json = ?")
                blob_params.append(json.dumps(scenario_config))
            if analysis_state is not None:
                blob_updates.append("analysis_state_json = ?")
                blob_params.append(json.dumps(analysis_state))
            if planning_state is not None:
                blob_updates.append("planning_state_json = ?")
                blob_params.append(json.dumps(planning_state))
            if orders_state is not None:
                blob_updates.append("orders_state_json = ?")
                blob_params.append(json.dumps(orders_state))
            if ui_state is not None:
                blob_updates.append("ui_state_json = ?")
                blob_params.append(json.dumps(ui_state))
            if czml_data is not None:
                czml_json = json.dumps(czml_data)
                czml_blob = zlib.compress(czml_json.encode("utf-8"))
                blob_updates.append("czml_blob = ?")
                blob_params.append(czml_blob)

            if blob_updates:
                blob_params.append(workspace_id)
                cursor.execute(
                    f"UPDATE workspace_blobs SET {', '.join(blob_updates)} WHERE workspace_id = ?",
                    blob_params,
                )

            conn.commit()
            logger.info(f"Updated workspace: {workspace_id}")
            return True

    def get_workspace(
        self, workspace_id: str, include_czml: bool = True
    ) -> Optional[WorkspaceData]:
        """Get a workspace by ID.

        Args:
            workspace_id: Workspace ID
            include_czml: Whether to include CZML data

        Returns:
            WorkspaceData or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    w.id, w.name, w.created_at, w.updated_at,
                    w.schema_version, w.app_version,
                    w.mission_mode, w.time_window_start, w.time_window_end,
                    w.satellites_count, w.targets_count,
                    w.last_run_status, w.last_run_timestamp,
                    b.scenario_config_json, b.analysis_state_json,
                    b.planning_state_json, b.orders_state_json, b.ui_state_json,
                    b.czml_blob
                FROM workspaces w
                LEFT JOIN workspace_blobs b ON w.id = b.workspace_id
                WHERE w.id = ?
            """,
                (workspace_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return WorkspaceData(
                id=row["id"],
                name=row["name"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                schema_version=row["schema_version"],
                app_version=row["app_version"],
                mission_mode=row["mission_mode"],
                time_window_start=row["time_window_start"],
                time_window_end=row["time_window_end"],
                satellites_count=row["satellites_count"],
                targets_count=row["targets_count"],
                last_run_status=row["last_run_status"],
                last_run_timestamp=row["last_run_timestamp"],
                scenario_config=(
                    json.loads(row["scenario_config_json"])
                    if row["scenario_config_json"]
                    else None
                ),
                analysis_state=(
                    json.loads(row["analysis_state_json"])
                    if row["analysis_state_json"]
                    else None
                ),
                planning_state=(
                    json.loads(row["planning_state_json"])
                    if row["planning_state_json"]
                    else None
                ),
                orders_state=(
                    json.loads(row["orders_state_json"])
                    if row["orders_state_json"]
                    else None
                ),
                ui_state=(
                    json.loads(row["ui_state_json"]) if row["ui_state_json"] else None
                ),
                czml_blob=row["czml_blob"] if include_czml else None,
            )

    def list_workspaces(
        self, limit: int = 50, offset: int = 0
    ) -> List[WorkspaceSummary]:
        """List all workspaces.

        Args:
            limit: Maximum number of workspaces to return
            offset: Offset for pagination

        Returns:
            List of WorkspaceSummary objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    id, name, created_at, updated_at,
                    mission_mode, time_window_start, time_window_end,
                    satellites_count, targets_count,
                    last_run_status, schema_version, app_version
                FROM workspaces
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            """,
                (limit, offset),
            )

            return [
                WorkspaceSummary(
                    id=row["id"],
                    name=row["name"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    mission_mode=row["mission_mode"],
                    time_window_start=row["time_window_start"],
                    time_window_end=row["time_window_end"],
                    satellites_count=row["satellites_count"],
                    targets_count=row["targets_count"],
                    last_run_status=row["last_run_status"],
                    schema_version=row["schema_version"],
                    app_version=row["app_version"],
                )
                for row in cursor.fetchall()
            ]

    def delete_workspace(self, workspace_id: str) -> bool:
        """Delete a workspace.

        Args:
            workspace_id: Workspace to delete

        Returns:
            True if deleted, False if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Delete blobs first (FK cascade should handle this, but be explicit)
            cursor.execute(
                "DELETE FROM workspace_blobs WHERE workspace_id = ?", (workspace_id,)
            )

            # Delete workspace
            cursor.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))

            deleted = cursor.rowcount > 0
            conn.commit()

            if deleted:
                logger.info(f"Deleted workspace: {workspace_id}")
            else:
                logger.warning(f"Workspace not found for deletion: {workspace_id}")

            return deleted

    def export_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Export workspace as a portable JSON structure.

        Args:
            workspace_id: Workspace to export

        Returns:
            Exportable dictionary or None if not found
        """
        workspace = self.get_workspace(workspace_id, include_czml=True)
        if not workspace:
            return None

        export_data = workspace.to_dict(include_czml=True)
        export_data["export_timestamp"] = datetime.now(timezone.utc).isoformat() + "Z"
        export_data["export_version"] = SCHEMA_VERSION

        return export_data

    def import_workspace(
        self, data: Dict[str, Any], new_name: Optional[str] = None
    ) -> str:
        """Import workspace from exported JSON.

        Args:
            data: Exported workspace data
            new_name: Override name (optional)

        Returns:
            New workspace ID
        """
        # Create new workspace with imported data
        workspace_id = self.create_workspace(
            name=new_name or data.get("name", "Imported Workspace"),
            scenario_config=data.get("scenario_config"),
            analysis_state=data.get("analysis_state"),
            planning_state=data.get("planning_state"),
            orders_state=data.get("orders_state"),
            ui_state=data.get("ui_state"),
            czml_data=data.get("czml_data"),
            mission_mode=data.get("mission_mode"),
            time_window_start=data.get("time_window_start"),
            time_window_end=data.get("time_window_end"),
            app_version=data.get("app_version"),
        )

        logger.info(f"Imported workspace as: {workspace_id}")
        return workspace_id

    def get_workspace_count(self) -> int:
        """Get total number of workspaces.

        Returns:
            Number of workspaces
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM workspaces")
            result = cursor.fetchone()
            return int(result[0]) if result else 0


# Global database instance
_workspace_db: Optional[WorkspaceDB] = None


def get_workspace_db() -> WorkspaceDB:
    """Get the global workspace database instance."""
    global _workspace_db
    if _workspace_db is None:
        _workspace_db = WorkspaceDB()
    return _workspace_db


def reset_workspace_db(db_path: Optional[Path] = None) -> WorkspaceDB:
    """Reset the global workspace database instance.

    Args:
        db_path: Optional custom database path

    Returns:
        New WorkspaceDB instance
    """
    global _workspace_db
    _workspace_db = WorkspaceDB(db_path)
    return _workspace_db
