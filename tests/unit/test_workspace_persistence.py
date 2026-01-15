"""
Unit tests for workspace persistence layer.

Tests workspace CRUD operations, JSON blob storage,
export/import functionality, and schema versioning.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator

import pytest

from backend.workspace_persistence import (
    SCHEMA_VERSION,
    WorkspaceData,
    WorkspaceDB,
    WorkspaceSummary,
    get_workspace_db,
    reset_workspace_db,
)


@pytest.fixture
def temp_db() -> Generator[WorkspaceDB, None, None]:
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    db = WorkspaceDB(db_path)
    yield db

    # Cleanup
    if db_path.exists():
        os.unlink(db_path)


@pytest.fixture
def sample_scenario_config() -> Dict[str, Any]:
    """Sample scenario configuration for tests."""
    return {
        "satellites": [
            {
                "id": "sat_ICEYE-X44",
                "name": "ICEYE-X44",
                "tle": {
                    "line1": "1 62707U 25009DC  25306.22031033  .00004207  00000+0  39848-3 0  9995",
                    "line2": "2 62707  97.7269  23.9854 0002193 135.9671 224.1724 14.94137357 66022",
                },
                "color": "#FFD700",
            }
        ],
        "targets": [
            {
                "name": "Athens",
                "latitude": 37.9838,
                "longitude": 23.7275,
                "priority": 5,
            },
            {
                "name": "Istanbul",
                "latitude": 41.0082,
                "longitude": 28.9784,
                "priority": 3,
            },
        ],
        "constraints": {
            "elevation_mask_deg": 10.0,
            "max_spacecraft_roll_deg": 45.0,
        },
    }


@pytest.fixture
def sample_analysis_state() -> Dict[str, Any]:
    """Sample analysis state for tests."""
    return {
        "run_timestamp": "2026-01-06T10:30:00Z",
        "passes": [
            {
                "target_name": "Athens",
                "satellite_name": "ICEYE-X44",
                "start_time": "2026-01-06T12:15:00Z",
                "end_time": "2026-01-06T12:22:00Z",
                "max_elevation": 45.2,
            }
        ],
        "statistics": {"total_passes": 1},
    }


class TestWorkspaceCreation:
    """Tests for workspace creation."""

    def test_create_empty_workspace(self, temp_db: WorkspaceDB) -> None:
        """Test creating a workspace with just a name."""
        workspace_id = temp_db.create_workspace(name="Test Workspace")

        assert workspace_id is not None
        assert len(workspace_id) == 36  # UUID format

        # Verify workspace exists
        workspace = temp_db.get_workspace(workspace_id)
        assert workspace is not None
        assert workspace.name == "Test Workspace"
        assert workspace.schema_version == SCHEMA_VERSION

    def test_create_workspace_with_config(
        self, temp_db: WorkspaceDB, sample_scenario_config: Dict[str, Any]
    ) -> None:
        """Test creating a workspace with scenario configuration."""
        workspace_id = temp_db.create_workspace(
            name="Configured Workspace",
            scenario_config=sample_scenario_config,
            mission_mode="OPTICAL",
            time_window_start="2026-01-06T00:00:00Z",
            time_window_end="2026-01-07T00:00:00Z",
        )

        workspace = temp_db.get_workspace(workspace_id)
        assert workspace is not None

        assert workspace.mission_mode == "OPTICAL"
        assert workspace.satellites_count == 1
        assert workspace.targets_count == 2
        assert workspace.scenario_config is not None
        assert len(workspace.scenario_config["satellites"]) == 1
        assert len(workspace.scenario_config["targets"]) == 2

    def test_create_workspace_with_analysis(
        self,
        temp_db: WorkspaceDB,
        sample_scenario_config: Dict[str, Any],
        sample_analysis_state: Dict[str, Any],
    ) -> None:
        """Test creating a workspace with analysis results."""
        workspace_id = temp_db.create_workspace(
            name="Analyzed Workspace",
            scenario_config=sample_scenario_config,
            analysis_state=sample_analysis_state,
        )

        workspace = temp_db.get_workspace(workspace_id)
        assert workspace is not None

        assert workspace.last_run_status == "success"
        assert workspace.analysis_state is not None
        assert len(workspace.analysis_state["passes"]) == 1


class TestWorkspaceRetrieval:
    """Tests for workspace retrieval."""

    def test_get_nonexistent_workspace(self, temp_db: WorkspaceDB) -> None:
        """Test getting a workspace that doesn't exist."""
        workspace = temp_db.get_workspace("nonexistent-id")
        assert workspace is None

    def test_list_empty_workspaces(self, temp_db: WorkspaceDB) -> None:
        """Test listing when no workspaces exist."""
        workspaces = temp_db.list_workspaces()
        assert workspaces == []
        assert temp_db.get_workspace_count() == 0

    def test_list_workspaces_ordering(self, temp_db: WorkspaceDB) -> None:
        """Test that workspaces are listed by updated_at descending."""
        # Create workspaces
        id1 = temp_db.create_workspace(name="First")
        id2 = temp_db.create_workspace(name="Second")
        id3 = temp_db.create_workspace(name="Third")

        # Update first workspace to make it most recent
        temp_db.update_workspace(id1, name="First Updated")

        workspaces = temp_db.list_workspaces()

        assert len(workspaces) == 3
        assert workspaces[0].id == id1  # Most recently updated
        assert workspaces[1].id == id3
        assert workspaces[2].id == id2

    def test_list_workspaces_pagination(self, temp_db: WorkspaceDB) -> None:
        """Test workspace listing with pagination."""
        # Create 5 workspaces
        for i in range(5):
            temp_db.create_workspace(name=f"Workspace {i}")

        # Get first 2
        page1 = temp_db.list_workspaces(limit=2, offset=0)
        assert len(page1) == 2

        # Get next 2
        page2 = temp_db.list_workspaces(limit=2, offset=2)
        assert len(page2) == 2

        # Get last 1
        page3 = temp_db.list_workspaces(limit=2, offset=4)
        assert len(page3) == 1


class TestWorkspaceUpdate:
    """Tests for workspace updates."""

    def test_update_workspace_name(self, temp_db: WorkspaceDB) -> None:
        """Test updating workspace name."""
        workspace_id = temp_db.create_workspace(name="Original Name")

        success = temp_db.update_workspace(workspace_id, name="New Name")

        assert success is True
        workspace = temp_db.get_workspace(workspace_id)
        assert workspace is not None
        assert workspace.name == "New Name"

    def test_update_nonexistent_workspace(self, temp_db: WorkspaceDB) -> None:
        """Test updating a workspace that doesn't exist."""
        success = temp_db.update_workspace("nonexistent-id", name="New Name")
        assert success is False

    def test_update_workspace_state_blobs(
        self,
        temp_db: WorkspaceDB,
        sample_scenario_config: Dict[str, Any],
        sample_analysis_state: Dict[str, Any],
    ) -> None:
        """Test updating workspace state blobs."""
        workspace_id = temp_db.create_workspace(name="Test")

        # Update with new state
        temp_db.update_workspace(
            workspace_id,
            scenario_config=sample_scenario_config,
            analysis_state=sample_analysis_state,
        )

        workspace = temp_db.get_workspace(workspace_id)
        assert workspace is not None

        assert workspace.scenario_config is not None
        assert workspace.analysis_state is not None
        assert workspace.satellites_count == 1
        assert workspace.targets_count == 2


class TestWorkspaceDeletion:
    """Tests for workspace deletion."""

    def test_delete_workspace(self, temp_db: WorkspaceDB) -> None:
        """Test deleting a workspace."""
        workspace_id = temp_db.create_workspace(name="To Delete")

        assert temp_db.get_workspace_count() == 1

        deleted = temp_db.delete_workspace(workspace_id)

        assert deleted is True
        assert temp_db.get_workspace_count() == 0
        assert temp_db.get_workspace(workspace_id) is None

    def test_delete_nonexistent_workspace(self, temp_db: WorkspaceDB) -> None:
        """Test deleting a workspace that doesn't exist."""
        deleted = temp_db.delete_workspace("nonexistent-id")
        assert deleted is False


class TestWorkspaceExportImport:
    """Tests for workspace export/import."""

    def test_export_workspace(
        self,
        temp_db: WorkspaceDB,
        sample_scenario_config: Dict[str, Any],
        sample_analysis_state: Dict[str, Any],
    ) -> None:
        """Test exporting a workspace."""
        workspace_id = temp_db.create_workspace(
            name="Export Test",
            scenario_config=sample_scenario_config,
            analysis_state=sample_analysis_state,
            mission_mode="OPTICAL",
        )

        export_data = temp_db.export_workspace(workspace_id)

        assert export_data is not None
        assert export_data["name"] == "Export Test"
        assert export_data["mission_mode"] == "OPTICAL"
        assert export_data["scenario_config"] is not None
        assert "export_timestamp" in export_data
        assert "export_version" in export_data

    def test_export_nonexistent_workspace(self, temp_db: WorkspaceDB) -> None:
        """Test exporting a workspace that doesn't exist."""
        export_data = temp_db.export_workspace("nonexistent-id")
        assert export_data is None

    def test_import_workspace(
        self,
        temp_db: WorkspaceDB,
        sample_scenario_config: Dict[str, Any],
        sample_analysis_state: Dict[str, Any],
    ) -> None:
        """Test importing a workspace."""
        # Create and export
        original_id = temp_db.create_workspace(
            name="Original",
            scenario_config=sample_scenario_config,
            analysis_state=sample_analysis_state,
            mission_mode="OPTICAL",
        )
        export_data = temp_db.export_workspace(original_id)
        assert export_data is not None

        # Import
        imported_id = temp_db.import_workspace(export_data)

        assert imported_id != original_id  # New workspace

        imported = temp_db.get_workspace(imported_id)
        assert imported is not None
        assert imported.name == "Original"
        assert imported.mission_mode == "OPTICAL"
        assert imported.scenario_config is not None

    def test_import_workspace_with_new_name(
        self,
        temp_db: WorkspaceDB,
        sample_scenario_config: Dict[str, Any],
        sample_analysis_state: Dict[str, Any],
    ) -> None:
        """Test importing a workspace with a custom name."""
        original_id = temp_db.create_workspace(
            name="Original",
            scenario_config=sample_scenario_config,
        )
        export_data = temp_db.export_workspace(original_id)
        assert export_data is not None

        imported_id = temp_db.import_workspace(export_data, new_name="Imported Copy")

        imported = temp_db.get_workspace(imported_id)
        assert imported is not None
        assert imported.name == "Imported Copy"


class TestCZMLCompression:
    """Tests for CZML blob compression."""

    def test_czml_storage_and_retrieval(self, temp_db: WorkspaceDB) -> None:
        """Test that CZML data is compressed and decompressed correctly."""
        czml_data: list[Dict[str, Any]] = [
            {"id": "document", "name": "Test Mission"},
            {
                "id": "satellite",
                "position": {"cartographicDegrees": [0, 37.9838, 23.7275, 600000]},
            },
        ]

        workspace_id = temp_db.create_workspace(
            name="CZML Test",
            czml_data=czml_data,
        )

        # Retrieve without CZML
        workspace_no_czml = temp_db.get_workspace(workspace_id, include_czml=False)
        assert workspace_no_czml is not None
        assert workspace_no_czml.czml_blob is None

        # Retrieve with CZML
        workspace_with_czml = temp_db.get_workspace(workspace_id, include_czml=True)
        assert workspace_with_czml is not None
        assert workspace_with_czml.czml_blob is not None

        # Check decompressed data
        workspace_dict = workspace_with_czml.to_dict(include_czml=True)
        assert workspace_dict["czml_data"] is not None
        assert len(workspace_dict["czml_data"]) == 2
        assert workspace_dict["czml_data"][0]["id"] == "document"


class TestSchemaVersion:
    """Tests for schema versioning."""

    def test_schema_version_set(self, temp_db: WorkspaceDB) -> None:
        """Test that schema version is set on creation."""
        workspace_id = temp_db.create_workspace(name="Version Test")
        workspace = temp_db.get_workspace(workspace_id)
        assert workspace is not None

        assert workspace.schema_version == SCHEMA_VERSION

    def test_app_version_stored(self, temp_db: WorkspaceDB) -> None:
        """Test that app version can be stored."""
        workspace_id = temp_db.create_workspace(
            name="App Version Test",
            app_version="1.2.3",
        )
        workspace = temp_db.get_workspace(workspace_id)
        assert workspace is not None

        assert workspace.app_version == "1.2.3"


class TestWorkspaceDBSingleton:
    """Tests for workspace database singleton."""

    def test_get_workspace_db_returns_same_instance(self) -> None:
        """Test that get_workspace_db returns the same instance."""
        db1 = get_workspace_db()
        db2 = get_workspace_db()

        assert db1 is db2

    def test_reset_workspace_db(self) -> None:
        """Test that reset_workspace_db creates a new instance."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            db1 = get_workspace_db()
            db2 = reset_workspace_db(db_path)
            db3 = get_workspace_db()

            assert db2 is db3
            assert db2 is not db1
        finally:
            if db_path.exists():
                os.unlink(db_path)
