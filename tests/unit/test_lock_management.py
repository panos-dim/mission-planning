"""
Tests for lock management functionality.

Tests cover:
- Lock level updates (single acquisition)
- Bulk lock operations
- Hard lock validation in repair mode
- Commit audit trail
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Generator, List, Tuple

import pytest

from backend.schedule_persistence import Acquisition, ScheduleDB
from backend.workspace_persistence import WorkspaceDB


@pytest.fixture
def temp_db() -> Generator[ScheduleDB, None, None]:
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    db = ScheduleDB(db_path)
    yield db

    # Cleanup
    os.unlink(db_path)


@pytest.fixture
def sample_acquisitions(
    temp_db: ScheduleDB,
) -> Tuple[str, List[Acquisition]]:
    """Create sample acquisitions with different lock levels."""
    # Create workspace via WorkspaceDB (manages workspaces table)
    workspace_db = WorkspaceDB(temp_db.db_path)
    workspace_id = workspace_db.create_workspace(
        name="Test Workspace",
        mission_mode="OPTICAL",
    )
    now = datetime.utcnow()

    acquisitions: List[Acquisition] = []
    for i, lock_level in enumerate(["none", "none", "hard", "none", "hard"]):
        acq = temp_db.create_acquisition(
            satellite_id=f"SAT-{i}",
            target_id=f"TARGET-{i}",
            start_time=(now + timedelta(hours=i)).isoformat() + "Z",
            end_time=(now + timedelta(hours=i, minutes=30)).isoformat() + "Z",
            mode="OPTICAL",
            roll_angle_deg=float(i * 5),
            pitch_angle_deg=0.0,
            state="committed",
            lock_level=lock_level,
            workspace_id=workspace_id,
        )
        acquisitions.append(acq)

    return workspace_id, acquisitions


class TestLockLevelUpdates:
    """Tests for single acquisition lock level updates."""

    def test_update_lock_level_to_hard(
        self,
        temp_db: ScheduleDB,
        sample_acquisitions: Tuple[str, List[Acquisition]],
    ) -> None:
        """Test updating lock level from none to hard."""
        _workspace_id, acquisitions = sample_acquisitions

        # Get an acquisition with lock_level=none
        acq = [a for a in acquisitions if a.lock_level == "none"][0]

        # Update to hard
        result = temp_db.update_acquisition_lock_level(acq.id, "hard")
        assert result is True

        # Verify update
        updated = temp_db.get_acquisition(acq.id)
        assert updated is not None
        assert updated.lock_level == "hard"

    def test_update_lock_level_to_none(
        self,
        temp_db: ScheduleDB,
        sample_acquisitions: Tuple[str, List[Acquisition]],
    ) -> None:
        """Test updating lock level from hard to none (unlock)."""
        _workspace_id, acquisitions = sample_acquisitions

        # Get an acquisition with lock_level=hard
        acq = [a for a in acquisitions if a.lock_level == "hard"][0]

        # Update to none
        result = temp_db.update_acquisition_lock_level(acq.id, "none")
        assert result is True

        # Verify update
        updated = temp_db.get_acquisition(acq.id)
        assert updated is not None
        assert updated.lock_level == "none"

    def test_update_lock_level_invalid(
        self,
        temp_db: ScheduleDB,
        sample_acquisitions: Tuple[str, List[Acquisition]],
    ) -> None:
        """Test that invalid lock levels are rejected."""
        _workspace_id, acquisitions = sample_acquisitions
        acq = acquisitions[0]

        with pytest.raises(ValueError, match="Invalid lock_level"):
            temp_db.update_acquisition_state(acq.id, lock_level="invalid")

    def test_update_nonexistent_acquisition(self, temp_db: ScheduleDB) -> None:
        """Test updating a non-existent acquisition returns False."""
        result = temp_db.update_acquisition_lock_level("nonexistent_id", "none")
        assert result is False


class TestBulkLockOperations:
    """Tests for bulk lock operations."""

    def test_bulk_update_to_hard(
        self,
        temp_db: ScheduleDB,
        sample_acquisitions: Tuple[str, List[Acquisition]],
    ) -> None:
        """Test bulk update of all acquisitions to hard lock."""
        _workspace_id, acquisitions = sample_acquisitions

        all_ids = [a.id for a in acquisitions]
        result = temp_db.bulk_update_lock_levels(all_ids, "hard")

        assert result["updated"] == len(all_ids)

        # Verify all are now hard
        for acq_id in all_ids:
            acq = temp_db.get_acquisition(acq_id)
            assert acq is not None
            assert acq.lock_level == "hard"

    def test_bulk_update_with_invalid_ids(
        self,
        temp_db: ScheduleDB,
        sample_acquisitions: Tuple[str, List[Acquisition]],
    ) -> None:
        """Test bulk update with some invalid IDs."""
        _workspace_id, acquisitions = sample_acquisitions

        valid_ids = [acquisitions[0].id, acquisitions[1].id]
        invalid_ids = ["invalid_1", "invalid_2"]
        all_ids = valid_ids + invalid_ids

        result = temp_db.bulk_update_lock_levels(all_ids, "none")

        assert result["updated"] == 2
        assert len(result["failed"]) == 2
        assert set(result["failed"]) == set(invalid_ids)

    def test_bulk_update_invalid_lock_level(
        self,
        temp_db: ScheduleDB,
        sample_acquisitions: Tuple[str, List[Acquisition]],
    ) -> None:
        """Test bulk update with invalid lock level."""
        _workspace_id, acquisitions = sample_acquisitions

        with pytest.raises(ValueError, match="Invalid lock_level"):
            temp_db.bulk_update_lock_levels([acquisitions[0].id], "invalid")

    def test_hard_lock_all_committed(
        self,
        temp_db: ScheduleDB,
        sample_acquisitions: Tuple[str, List[Acquisition]],
    ) -> None:
        """Test hard-locking all committed acquisitions."""
        workspace_id, acquisitions = sample_acquisitions

        # Count non-hard acquisitions
        non_hard_count = len([a for a in acquisitions if a.lock_level != "hard"])

        result = temp_db.hard_lock_all_committed(workspace_id)

        assert result["updated"] == non_hard_count

        # Verify all are now hard
        updated_acqs = temp_db.get_acquisitions_by_lock_level(workspace_id)
        for acq in updated_acqs:
            assert acq.lock_level == "hard"


class TestCommitAuditLog:
    """Tests for commit audit log functionality."""

    def test_create_audit_log_normal(
        self,
        temp_db: ScheduleDB,
        sample_acquisitions: Tuple[str, List[Acquisition]],
    ) -> None:
        """Test creating a normal commit audit log."""
        workspace_id, _ = sample_acquisitions

        # Create a plan first
        plan = temp_db.create_plan(
            algorithm="test",
            config={"test": True},
            input_hash="sha256:abc123",
            run_id="test_run_1",
            metrics={"score": 10.0},
            workspace_id=workspace_id,
        )

        audit_log = temp_db.create_commit_audit_log(
            plan_id=plan.id,
            commit_type="normal",
            config_hash="sha256:test",
            acquisitions_created=5,
            acquisitions_dropped=0,
            workspace_id=workspace_id,
            score_before=10.0,
            score_after=15.0,
            conflicts_before=2,
            conflicts_after=0,
            notes="Test commit",
        )

        assert audit_log.id.startswith("audit_")
        assert audit_log.commit_type == "normal"
        assert audit_log.acquisitions_created == 5
        assert audit_log.acquisitions_dropped == 0
        assert audit_log.score_before == 10.0
        assert audit_log.score_after == 15.0

    def test_create_audit_log_repair(
        self,
        temp_db: ScheduleDB,
        sample_acquisitions: Tuple[str, List[Acquisition]],
    ) -> None:
        """Test creating a repair commit audit log with diff."""
        workspace_id, _ = sample_acquisitions

        plan = temp_db.create_plan(
            algorithm="repair_mode",
            config={"planning_mode": "repair"},
            input_hash="sha256:def456",
            run_id="repair_run_1",
            metrics={"score": 20.0},
            workspace_id=workspace_id,
        )

        repair_diff: dict[str, Any] = {
            "kept": ["acq_1", "acq_2"],
            "dropped": ["acq_3"],
            "added": ["acq_4"],
            "moved": [],
        }

        audit_log = temp_db.create_commit_audit_log(
            plan_id=plan.id,
            commit_type="repair",
            config_hash="sha256:repair",
            acquisitions_created=1,
            acquisitions_dropped=1,
            workspace_id=workspace_id,
            repair_diff=repair_diff,
            score_before=15.0,
            score_after=18.0,
            conflicts_before=1,
            conflicts_after=0,
        )

        assert audit_log.commit_type == "repair"
        assert audit_log.acquisitions_dropped == 1

        # Check repair diff was stored
        log_dict = audit_log.to_dict()
        assert log_dict["repair_diff"] is not None
        assert log_dict["repair_diff"]["dropped"] == ["acq_3"]

    def test_get_audit_logs(
        self,
        temp_db: ScheduleDB,
        sample_acquisitions: Tuple[str, List[Acquisition]],
    ) -> None:
        """Test retrieving audit logs."""
        workspace_id, _ = sample_acquisitions

        # Create multiple audit logs
        for i in range(3):
            plan = temp_db.create_plan(
                algorithm="test",
                config={},
                input_hash=f"sha256:hash{i}",
                run_id=f"run_{i}",
                metrics={},
                workspace_id=workspace_id,
            )
            temp_db.create_commit_audit_log(
                plan_id=plan.id,
                commit_type="normal",
                config_hash=f"sha256:config{i}",
                acquisitions_created=i + 1,
                workspace_id=workspace_id,
            )

        # Retrieve logs
        logs = temp_db.get_commit_audit_logs(workspace_id=workspace_id)

        assert len(logs) == 3
        # Should be ordered by created_at DESC
        assert logs[0].acquisitions_created >= logs[1].acquisitions_created


class TestAtomicCommit:
    """Tests for atomic commit with rollback."""

    def test_atomic_commit_success(
        self,
        temp_db: ScheduleDB,
        sample_acquisitions: Tuple[str, List[Acquisition]],
    ) -> None:
        """Test successful atomic commit."""
        workspace_id, _ = sample_acquisitions

        # Create a plan with items
        plan = temp_db.create_plan(
            algorithm="test",
            config={},
            input_hash="sha256:atomic",
            run_id="atomic_run",
            metrics={},
            workspace_id=workspace_id,
        )

        now = datetime.utcnow()
        temp_db.create_plan_item(
            plan_id=plan.id,
            opportunity_id="opp_1",
            satellite_id="SAT-A",
            target_id="TARGET-A",
            start_time=(now + timedelta(hours=10)).isoformat() + "Z",
            end_time=(now + timedelta(hours=10, minutes=30)).isoformat() + "Z",
            roll_angle_deg=5.0,
            pitch_angle_deg=0.0,
        )

        result = temp_db.commit_plan_atomic(
            plan_id=plan.id,
            item_ids=[],
            lock_level="none",
            mode="OPTICAL",
            workspace_id=workspace_id,
        )

        assert result["success"] is True
        assert result["committed"] == 1
        assert len(result["acquisitions_created"]) == 1

    def test_atomic_commit_with_drops(
        self,
        temp_db: ScheduleDB,
        sample_acquisitions: Tuple[str, List[Acquisition]],
    ) -> None:
        """Test atomic commit that drops acquisitions."""
        workspace_id, acquisitions = sample_acquisitions

        # Get a non-hard acquisition to drop
        to_drop = [a for a in acquisitions if a.lock_level != "hard"][0]

        # Create a plan
        plan = temp_db.create_plan(
            algorithm="repair_mode",
            config={},
            input_hash="sha256:repair",
            run_id="repair_run",
            metrics={},
            workspace_id=workspace_id,
        )

        result = temp_db.commit_plan_atomic(
            plan_id=plan.id,
            item_ids=[],
            lock_level="none",
            mode="OPTICAL",
            workspace_id=workspace_id,
            drop_acquisition_ids=[to_drop.id],
        )

        assert result["success"] is True
        assert result["dropped"] == 1
        assert to_drop.id in result["acquisitions_dropped"]

        # Verify dropped acquisition state
        dropped_acq = temp_db.get_acquisition(to_drop.id)
        assert dropped_acq is not None
        assert dropped_acq.state == "failed"
        assert dropped_acq.lock_level == "none"

    def test_atomic_commit_already_committed(
        self,
        temp_db: ScheduleDB,
        sample_acquisitions: Tuple[str, List[Acquisition]],
    ) -> None:
        """Test that committing an already committed plan fails."""
        workspace_id, _ = sample_acquisitions

        plan = temp_db.create_plan(
            algorithm="test",
            config={},
            input_hash="sha256:test",
            run_id="test_run",
            metrics={},
            workspace_id=workspace_id,
        )

        # First commit
        temp_db.commit_plan_atomic(
            plan_id=plan.id,
            item_ids=[],
            workspace_id=workspace_id,
        )

        # Second commit should fail
        with pytest.raises(ValueError, match="already committed"):
            temp_db.commit_plan_atomic(
                plan_id=plan.id,
                item_ids=[],
                workspace_id=workspace_id,
            )

    def test_atomic_commit_plan_not_found(self, temp_db: ScheduleDB) -> None:
        """Test that committing a non-existent plan fails."""
        with pytest.raises(ValueError, match="Plan not found"):
            temp_db.commit_plan_atomic(
                plan_id="nonexistent",
                item_ids=[],
            )


class TestLockLevelFiltering:
    """Tests for filtering acquisitions by lock level."""

    def test_get_acquisitions_by_lock_level_all(
        self,
        temp_db: ScheduleDB,
        sample_acquisitions: Tuple[str, List[Acquisition]],
    ) -> None:
        """Test getting all acquisitions without filter."""
        workspace_id, acquisitions = sample_acquisitions

        result = temp_db.get_acquisitions_by_lock_level(workspace_id)
        assert len(result) == len(acquisitions)

    def test_get_acquisitions_by_lock_level_hard(
        self,
        temp_db: ScheduleDB,
        sample_acquisitions: Tuple[str, List[Acquisition]],
    ) -> None:
        """Test getting only hard-locked acquisitions."""
        workspace_id, acquisitions = sample_acquisitions

        expected_count = len([a for a in acquisitions if a.lock_level == "hard"])
        result = temp_db.get_acquisitions_by_lock_level(workspace_id, "hard")

        assert len(result) == expected_count
        for acq in result:
            assert acq.lock_level == "hard"

    def test_get_acquisitions_by_lock_level_none(
        self,
        temp_db: ScheduleDB,
        sample_acquisitions: Tuple[str, List[Acquisition]],
    ) -> None:
        """Test getting only unlocked acquisitions."""
        workspace_id, acquisitions = sample_acquisitions

        expected_count = len([a for a in acquisitions if a.lock_level == "none"])
        result = temp_db.get_acquisitions_by_lock_level(workspace_id, "none")

        assert len(result) == expected_count
        for acq in result:
            assert acq.lock_level == "none"
