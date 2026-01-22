"""
Unit tests for Conflict Detection.

Tests cover:
- Temporal overlap detection
- Slew infeasibility detection
- Conflict persistence
- Conflict statistics
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from backend.conflict_detection import (
    ConflictDetectionConfig,
    ConflictDetector,
    DetectedConflict,
    detect_and_persist_conflicts,
)
from backend.schedule_persistence import ScheduleDB


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    db = ScheduleDB(db_path)
    yield db
    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def workspace_with_acquisitions(temp_db):
    """Create a workspace with test acquisitions."""
    from backend.workspace_persistence import WorkspaceDB

    # Create workspace
    workspace_db = WorkspaceDB(temp_db.db_path)
    workspace_id = workspace_db.create_workspace(
        name="Test Workspace",
        mission_mode="OPTICAL",
    )

    return workspace_id, temp_db


class TestTemporalOverlapDetection:
    """Tests for temporal overlap conflict detection."""

    def test_no_overlap_sequential_acquisitions(self, workspace_with_acquisitions):
        """Sequential acquisitions should not produce overlap conflicts."""
        workspace_id, db = workspace_with_acquisitions

        # Create two sequential acquisitions (no overlap)
        now = datetime.utcnow()

        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T1",
            start_time=(now + timedelta(minutes=0)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=5)).isoformat() + "Z",
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T2",
            start_time=(now + timedelta(minutes=10)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=15)).isoformat() + "Z",
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        # Detect conflicts
        detector = ConflictDetector(db)
        conflicts = detector.detect_conflicts(
            workspace_id=workspace_id,
            start_time=now.isoformat() + "Z",
            end_time=(now + timedelta(hours=1)).isoformat() + "Z",
        )

        # Should have no temporal overlap conflicts
        overlap_conflicts = [c for c in conflicts if c.type == "temporal_overlap"]
        assert len(overlap_conflicts) == 0

    def test_overlap_detected(self, workspace_with_acquisitions):
        """Overlapping acquisitions should produce a conflict."""
        workspace_id, db = workspace_with_acquisitions

        # Create two overlapping acquisitions
        now = datetime.utcnow()

        acq1 = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T1",
            start_time=(now + timedelta(minutes=0)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=10)).isoformat() + "Z",
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        acq2 = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T2",
            start_time=(now + timedelta(minutes=5)).isoformat() + "Z",  # Overlaps!
            end_time=(now + timedelta(minutes=15)).isoformat() + "Z",
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        # Detect conflicts
        detector = ConflictDetector(db)
        conflicts = detector.detect_conflicts(
            workspace_id=workspace_id,
            start_time=now.isoformat() + "Z",
            end_time=(now + timedelta(hours=1)).isoformat() + "Z",
        )

        # Should have one temporal overlap conflict
        overlap_conflicts = [c for c in conflicts if c.type == "temporal_overlap"]
        assert len(overlap_conflicts) == 1

        conflict = overlap_conflicts[0]
        assert conflict.severity == "error"
        assert acq1.id in conflict.acquisition_ids
        assert acq2.id in conflict.acquisition_ids
        assert "overlap" in conflict.description.lower()

    def test_different_satellites_no_conflict(self, workspace_with_acquisitions):
        """Overlapping acquisitions on different satellites should not conflict."""
        workspace_id, db = workspace_with_acquisitions

        now = datetime.utcnow()

        # Same time, but different satellites
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T1",
            start_time=(now + timedelta(minutes=0)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=10)).isoformat() + "Z",
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        db.create_acquisition(
            satellite_id="SAT-2",
            target_id="T2",
            start_time=(now + timedelta(minutes=5)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=15)).isoformat() + "Z",
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        detector = ConflictDetector(db)
        conflicts = detector.detect_conflicts(
            workspace_id=workspace_id,
            start_time=now.isoformat() + "Z",
            end_time=(now + timedelta(hours=1)).isoformat() + "Z",
        )

        overlap_conflicts = [c for c in conflicts if c.type == "temporal_overlap"]
        assert len(overlap_conflicts) == 0


class TestSlewInfeasibleDetection:
    """Tests for slew infeasibility conflict detection (roll + pitch)."""

    def test_sufficient_slew_time_roll_only(self, workspace_with_acquisitions):
        """Sufficient gap between acquisitions should not produce slew conflict (roll only)."""
        workspace_id, db = workspace_with_acquisitions

        now = datetime.utcnow()

        # Two acquisitions with plenty of time to slew 30 degrees roll
        # At 1 deg/s, 30 deg takes 30s + 5s settling = 35s
        # Gap is 60 seconds, so should be fine
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T1",
            start_time=(now + timedelta(minutes=0)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=5)).isoformat() + "Z",
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T2",
            start_time=(now + timedelta(minutes=6)).isoformat() + "Z",  # 60s gap
            end_time=(now + timedelta(minutes=11)).isoformat() + "Z",
            roll_angle_deg=30.0,  # 30 degree roll change
            pitch_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        detector = ConflictDetector(db)
        conflicts = detector.detect_conflicts(
            workspace_id=workspace_id,
            start_time=now.isoformat() + "Z",
            end_time=(now + timedelta(hours=1)).isoformat() + "Z",
        )

        slew_conflicts = [c for c in conflicts if c.type == "slew_infeasible"]
        assert len(slew_conflicts) == 0

    def test_insufficient_slew_time_roll_error(self, workspace_with_acquisitions):
        """Insufficient slew time for roll should produce an error conflict."""
        workspace_id, db = workspace_with_acquisitions

        now = datetime.utcnow()

        # Two acquisitions with only 10s gap but 45 degree roll slew needed
        # At 1 deg/s, 45 deg takes 45s + 5s settling = 50s
        # Gap is only 10 seconds, so deficit is ~40s (error severity)
        acq1 = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T1",
            start_time=(now + timedelta(minutes=0)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=5)).isoformat() + "Z",
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        acq2 = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T2",
            start_time=(now + timedelta(minutes=5, seconds=10)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=10)).isoformat() + "Z",
            roll_angle_deg=45.0,  # 45 degree roll change
            pitch_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        detector = ConflictDetector(db)
        conflicts = detector.detect_conflicts(
            workspace_id=workspace_id,
            start_time=now.isoformat() + "Z",
            end_time=(now + timedelta(hours=1)).isoformat() + "Z",
        )

        slew_conflicts = [c for c in conflicts if c.type == "slew_infeasible"]
        assert len(slew_conflicts) == 1

        conflict = slew_conflicts[0]
        assert conflict.severity == "error"
        assert acq1.id in conflict.acquisition_ids
        assert acq2.id in conflict.acquisition_ids
        assert "slew" in conflict.description.lower()

    def test_insufficient_slew_time_pitch_error(self, workspace_with_acquisitions):
        """Insufficient slew time for pitch should produce an error conflict."""
        workspace_id, db = workspace_with_acquisitions

        now = datetime.utcnow()

        # Two acquisitions with only 10s gap but 45 degree pitch slew needed
        acq1 = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T1",
            start_time=(now + timedelta(minutes=0)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=5)).isoformat() + "Z",
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        acq2 = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T2",
            start_time=(now + timedelta(minutes=5, seconds=10)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=10)).isoformat() + "Z",
            roll_angle_deg=0.0,
            pitch_angle_deg=45.0,  # 45 degree pitch change
            workspace_id=workspace_id,
        )

        detector = ConflictDetector(db)
        conflicts = detector.detect_conflicts(
            workspace_id=workspace_id,
            start_time=now.isoformat() + "Z",
            end_time=(now + timedelta(hours=1)).isoformat() + "Z",
        )

        slew_conflicts = [c for c in conflicts if c.type == "slew_infeasible"]
        assert len(slew_conflicts) == 1
        assert slew_conflicts[0].severity == "error"
        assert "pitch" in slew_conflicts[0].description.lower()

    def test_roll_and_pitch_parallel_slew(self, workspace_with_acquisitions):
        """Roll and pitch slew in parallel - max of both times used."""
        workspace_id, db = workspace_with_acquisitions

        now = datetime.utcnow()

        # Roll: 30 deg at 1 deg/s = 30s
        # Pitch: 20 deg at 1 deg/s = 20s
        # Parallel: max(30, 20) + 5s settling = 35s
        # Gap: 40s - should be OK
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T1",
            start_time=(now + timedelta(minutes=0)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=5)).isoformat() + "Z",
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T2",
            start_time=(now + timedelta(minutes=5, seconds=40)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=10)).isoformat() + "Z",
            roll_angle_deg=30.0,
            pitch_angle_deg=20.0,
            workspace_id=workspace_id,
        )

        config = ConflictDetectionConfig(parallel_slew=True)
        detector = ConflictDetector(db, config)
        conflicts = detector.detect_conflicts(
            workspace_id=workspace_id,
            start_time=now.isoformat() + "Z",
            end_time=(now + timedelta(hours=1)).isoformat() + "Z",
        )

        slew_conflicts = [c for c in conflicts if c.type == "slew_infeasible"]
        assert len(slew_conflicts) == 0

    def test_roll_and_pitch_sequential_slew(self, workspace_with_acquisitions):
        """Roll and pitch slew sequential - sum of both times used."""
        workspace_id, db = workspace_with_acquisitions

        now = datetime.utcnow()

        # Roll: 30 deg at 1 deg/s = 30s
        # Pitch: 20 deg at 1 deg/s = 20s
        # Sequential: 30 + 20 + 5s settling = 55s
        # Gap: 40s - should produce conflict
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T1",
            start_time=(now + timedelta(minutes=0)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=5)).isoformat() + "Z",
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T2",
            start_time=(now + timedelta(minutes=5, seconds=40)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=10)).isoformat() + "Z",
            roll_angle_deg=30.0,
            pitch_angle_deg=20.0,
            workspace_id=workspace_id,
        )

        config = ConflictDetectionConfig(parallel_slew=False)  # Sequential
        detector = ConflictDetector(db, config)
        conflicts = detector.detect_conflicts(
            workspace_id=workspace_id,
            start_time=now.isoformat() + "Z",
            end_time=(now + timedelta(hours=1)).isoformat() + "Z",
        )

        slew_conflicts = [c for c in conflicts if c.type == "slew_infeasible"]
        assert len(slew_conflicts) == 1
        assert slew_conflicts[0].severity == "error"

    def test_marginal_slew_time_warning(self, workspace_with_acquisitions):
        """Marginal slew time should produce a warning conflict."""
        workspace_id, db = workspace_with_acquisitions

        now = datetime.utcnow()

        # 15 degree roll slew, 15s + 5s = 20s needed
        # Gap is 15s, deficit is 5s (warning severity)
        acq1 = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T1",
            start_time=(now + timedelta(minutes=0)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=5)).isoformat() + "Z",
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        acq2 = db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T2",
            start_time=(now + timedelta(minutes=5, seconds=15)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=10)).isoformat() + "Z",
            roll_angle_deg=15.0,  # 15 degree roll change
            pitch_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        detector = ConflictDetector(db)
        conflicts = detector.detect_conflicts(
            workspace_id=workspace_id,
            start_time=now.isoformat() + "Z",
            end_time=(now + timedelta(hours=1)).isoformat() + "Z",
        )

        slew_conflicts = [c for c in conflicts if c.type == "slew_infeasible"]
        assert len(slew_conflicts) == 1
        assert slew_conflicts[0].severity == "warning"


class TestConflictPersistence:
    """Tests for conflict persistence operations."""

    def test_persist_and_retrieve_conflicts(self, workspace_with_acquisitions):
        """Conflicts should be persisted and retrievable."""
        workspace_id, db = workspace_with_acquisitions

        # Create a conflict directly
        conflict = db.create_conflict(
            conflict_type="temporal_overlap",
            severity="error",
            description="Test overlap conflict",
            acquisition_ids=["acq_1", "acq_2"],
            workspace_id=workspace_id,
        )

        assert conflict.id.startswith("conflict_")
        assert conflict.type == "temporal_overlap"
        assert conflict.severity == "error"

        # Retrieve it
        retrieved = db.get_conflict(conflict.id)
        assert retrieved is not None
        assert retrieved.id == conflict.id
        assert retrieved.type == "temporal_overlap"

    def test_list_conflicts_by_workspace(self, workspace_with_acquisitions):
        """Conflicts should be listable by workspace."""
        workspace_id, db = workspace_with_acquisitions

        # Create multiple conflicts
        db.create_conflict(
            conflict_type="temporal_overlap",
            severity="error",
            description="Overlap 1",
            acquisition_ids=["acq_1", "acq_2"],
            workspace_id=workspace_id,
        )

        db.create_conflict(
            conflict_type="slew_infeasible",
            severity="warning",
            description="Slew issue",
            acquisition_ids=["acq_2", "acq_3"],
            workspace_id=workspace_id,
        )

        # List all conflicts
        conflicts = db.list_conflicts(workspace_id=workspace_id)
        assert len(conflicts) == 2

        # List by type
        overlap_conflicts = db.list_conflicts(
            workspace_id=workspace_id,
            conflict_type="temporal_overlap",
        )
        assert len(overlap_conflicts) == 1

        # List by severity
        error_conflicts = db.list_conflicts(
            workspace_id=workspace_id,
            severity="error",
        )
        assert len(error_conflicts) == 1

    def test_resolve_conflict(self, workspace_with_acquisitions):
        """Conflicts should be resolvable."""
        workspace_id, db = workspace_with_acquisitions

        conflict = db.create_conflict(
            conflict_type="temporal_overlap",
            severity="error",
            description="Test conflict",
            acquisition_ids=["acq_1", "acq_2"],
            workspace_id=workspace_id,
        )

        # Resolve it
        success = db.resolve_conflict(
            conflict_id=conflict.id,
            resolution_action="removed_acquisition",
            resolution_notes="Removed acq_2 from schedule",
        )
        assert success

        # Verify resolution
        resolved = db.get_conflict(conflict.id)
        assert resolved.resolved_at is not None
        assert resolved.resolution_action == "removed_acquisition"

        # Should not appear in unresolved list
        unresolved = db.list_conflicts(workspace_id=workspace_id, resolved=False)
        assert len(unresolved) == 0

    def test_clear_unresolved_conflicts(self, workspace_with_acquisitions):
        """Unresolved conflicts should be clearable."""
        workspace_id, db = workspace_with_acquisitions

        # Create some conflicts
        c1 = db.create_conflict(
            conflict_type="temporal_overlap",
            severity="error",
            description="Conflict 1",
            acquisition_ids=["acq_1", "acq_2"],
            workspace_id=workspace_id,
        )

        db.create_conflict(
            conflict_type="slew_infeasible",
            severity="warning",
            description="Conflict 2",
            acquisition_ids=["acq_2", "acq_3"],
            workspace_id=workspace_id,
        )

        # Resolve one
        db.resolve_conflict(c1.id, "manual", "Fixed")

        # Clear unresolved
        deleted = db.clear_unresolved_conflicts(workspace_id)
        assert deleted == 1  # Only one was unresolved

        # Only resolved should remain
        remaining = db.list_conflicts(workspace_id=workspace_id, resolved=None)
        assert len(remaining) == 1
        assert remaining[0].resolved_at is not None


class TestConflictStatistics:
    """Tests for conflict statistics."""

    def test_conflict_statistics(self, workspace_with_acquisitions):
        """Statistics should correctly summarize conflicts."""
        workspace_id, db = workspace_with_acquisitions

        # Create various conflicts
        db.create_conflict(
            conflict_type="temporal_overlap",
            severity="error",
            description="Overlap 1",
            acquisition_ids=["acq_1", "acq_2"],
            workspace_id=workspace_id,
        )

        db.create_conflict(
            conflict_type="temporal_overlap",
            severity="error",
            description="Overlap 2",
            acquisition_ids=["acq_3", "acq_4"],
            workspace_id=workspace_id,
        )

        db.create_conflict(
            conflict_type="slew_infeasible",
            severity="warning",
            description="Slew issue",
            acquisition_ids=["acq_2", "acq_3"],
            workspace_id=workspace_id,
        )

        stats = db.get_conflict_statistics(workspace_id=workspace_id)

        assert stats["total"] == 3
        assert stats["by_type"]["temporal_overlap"] == 2
        assert stats["by_type"]["slew_infeasible"] == 1
        assert stats["by_severity"]["error"] == 2
        assert stats["by_severity"]["warning"] == 1


class TestDetectAndPersistConflicts:
    """Tests for the convenience function that detects and persists in one call."""

    def test_detect_and_persist(self, workspace_with_acquisitions):
        """detect_and_persist_conflicts should detect and store conflicts."""
        workspace_id, db = workspace_with_acquisitions

        now = datetime.utcnow()

        # Create overlapping acquisitions
        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T1",
            start_time=(now + timedelta(minutes=0)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=10)).isoformat() + "Z",
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        db.create_acquisition(
            satellite_id="SAT-1",
            target_id="T2",
            start_time=(now + timedelta(minutes=5)).isoformat() + "Z",
            end_time=(now + timedelta(minutes=15)).isoformat() + "Z",
            roll_angle_deg=0.0,
            workspace_id=workspace_id,
        )

        # Run detection and persistence
        detected, conflict_ids = detect_and_persist_conflicts(
            db=db,
            workspace_id=workspace_id,
            start_time=now.isoformat() + "Z",
            end_time=(now + timedelta(hours=1)).isoformat() + "Z",
        )

        assert len(detected) >= 1
        assert len(conflict_ids) >= 1

        # Verify persistence
        stored = db.list_conflicts(workspace_id=workspace_id)
        assert len(stored) >= 1
