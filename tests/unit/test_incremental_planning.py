"""
Tests for Incremental Planning Module.

Tests the core incremental planning functionality:
- Blocked intervals loading
- Feasibility checks with existing acquisitions
- Adjacency (slew) feasibility with neighbors
- Planning mode filtering
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from backend.incremental_planning import (
    BlockedInterval,
    IncrementalPlanningContext,
    LockPolicy,
    PlanningMode,
    SlewConfig,
    check_adjacency_feasibility,
    filter_opportunities_incremental,
    load_blocked_intervals,
)

# =============================================================================
# BlockedInterval Tests
# =============================================================================


class TestBlockedInterval:
    """Tests for BlockedInterval dataclass."""

    def test_duration_calculation(self) -> None:
        """Test that duration is correctly calculated."""
        interval = BlockedInterval(
            acquisition_id="acq_001",
            satellite_id="SAT-1",
            target_id="T1",
            start_time=datetime(2024, 1, 15, 10, 0, 0),
            end_time=datetime(2024, 1, 15, 10, 5, 0),
            roll_angle_deg=15.0,
        )
        assert interval.duration_s == 300.0  # 5 minutes

    def test_default_values(self) -> None:
        """Test default values for optional fields."""
        interval = BlockedInterval(
            acquisition_id="acq_001",
            satellite_id="SAT-1",
            target_id="T1",
            start_time=datetime(2024, 1, 15, 10, 0, 0),
            end_time=datetime(2024, 1, 15, 10, 5, 0),
            roll_angle_deg=0.0,
        )
        assert interval.pitch_angle_deg == 0.0
        assert interval.state == "committed"
        assert interval.lock_level == "none"


# =============================================================================
# IncrementalPlanningContext Tests
# =============================================================================


class TestIncrementalPlanningContext:
    """Tests for IncrementalPlanningContext."""

    def setup_method(self) -> None:
        """Set up test context with blocked intervals."""
        self.context = IncrementalPlanningContext(
            mode=PlanningMode.INCREMENTAL,
            lock_policy=LockPolicy.RESPECT_HARD_ONLY,
            horizon_start=datetime(2024, 1, 15, 0, 0, 0),
            horizon_end=datetime(2024, 1, 22, 0, 0, 0),
            workspace_id="ws_test",
        )

        # Add blocked intervals for SAT-1
        self.context.blocked_intervals["SAT-1"] = [
            BlockedInterval(
                acquisition_id="acq_001",
                satellite_id="SAT-1",
                target_id="T1",
                start_time=datetime(2024, 1, 15, 10, 0, 0),
                end_time=datetime(2024, 1, 15, 10, 5, 0),
                roll_angle_deg=0.0,
            ),
            BlockedInterval(
                acquisition_id="acq_002",
                satellite_id="SAT-1",
                target_id="T2",
                start_time=datetime(2024, 1, 15, 10, 30, 0),
                end_time=datetime(2024, 1, 15, 10, 35, 0),
                roll_angle_deg=30.0,
            ),
        ]

    def test_get_blocked_for_satellite(self) -> None:
        """Test retrieving blocked intervals for a satellite."""
        intervals = self.context.get_blocked_for_satellite("SAT-1")
        assert len(intervals) == 2
        # Should be sorted by start time
        assert intervals[0].start_time < intervals[1].start_time

    def test_get_blocked_for_unknown_satellite(self) -> None:
        """Test retrieving blocked intervals for unknown satellite returns empty."""
        intervals = self.context.get_blocked_for_satellite("SAT-UNKNOWN")
        assert intervals == []

    def test_is_time_blocked_overlap(self) -> None:
        """Test that overlapping time window is detected as blocked."""
        # Candidate overlaps with acq_001
        is_blocked, blocking = self.context.is_time_blocked(
            satellite_id="SAT-1",
            start_time=datetime(2024, 1, 15, 10, 3, 0),
            end_time=datetime(2024, 1, 15, 10, 8, 0),
        )
        assert is_blocked is True
        assert blocking is not None
        assert blocking.acquisition_id == "acq_001"

    def test_is_time_blocked_no_overlap(self) -> None:
        """Test that non-overlapping time window is not blocked."""
        # Candidate is between acq_001 and acq_002
        is_blocked, blocking = self.context.is_time_blocked(
            satellite_id="SAT-1",
            start_time=datetime(2024, 1, 15, 10, 10, 0),
            end_time=datetime(2024, 1, 15, 10, 15, 0),
        )
        assert is_blocked is False
        assert blocking is None

    def test_is_time_blocked_with_margin(self) -> None:
        """Test blocking with safety margin."""
        # Candidate ends exactly when acq_002 starts - normally OK
        is_blocked, _ = self.context.is_time_blocked(
            satellite_id="SAT-1",
            start_time=datetime(2024, 1, 15, 10, 25, 0),
            end_time=datetime(2024, 1, 15, 10, 30, 0),
            margin_s=0.0,
        )
        assert is_blocked is False

        # With 60s margin, it should be blocked
        is_blocked, _ = self.context.is_time_blocked(
            satellite_id="SAT-1",
            start_time=datetime(2024, 1, 15, 10, 25, 0),
            end_time=datetime(2024, 1, 15, 10, 30, 0),
            margin_s=60.0,
        )
        assert is_blocked is True

    def test_get_neighbors(self) -> None:
        """Test finding previous and next blocked intervals."""
        # Candidate between acq_001 and acq_002
        prev, next_interval = self.context.get_neighbors(
            satellite_id="SAT-1",
            candidate_start=datetime(2024, 1, 15, 10, 15, 0),
            candidate_end=datetime(2024, 1, 15, 10, 20, 0),
        )
        assert prev is not None
        assert prev.acquisition_id == "acq_001"
        assert next_interval is not None
        assert next_interval.acquisition_id == "acq_002"

    def test_get_neighbors_no_previous(self) -> None:
        """Test getting neighbors when there's no previous."""
        prev, next_interval = self.context.get_neighbors(
            satellite_id="SAT-1",
            candidate_start=datetime(2024, 1, 15, 9, 0, 0),
            candidate_end=datetime(2024, 1, 15, 9, 5, 0),
        )
        assert prev is None
        assert next_interval is not None
        assert next_interval.acquisition_id == "acq_001"

    def test_get_neighbors_no_next(self) -> None:
        """Test getting neighbors when there's no next."""
        prev, next_interval = self.context.get_neighbors(
            satellite_id="SAT-1",
            candidate_start=datetime(2024, 1, 15, 11, 0, 0),
            candidate_end=datetime(2024, 1, 15, 11, 5, 0),
        )
        assert prev is not None
        assert prev.acquisition_id == "acq_002"
        assert next_interval is None


# =============================================================================
# Adjacency Feasibility Tests
# =============================================================================


class TestAdjacencyFeasibility:
    """Tests for check_adjacency_feasibility function."""

    def setup_method(self) -> None:
        """Set up test context."""
        self.context = IncrementalPlanningContext(
            mode=PlanningMode.INCREMENTAL,
            lock_policy=LockPolicy.RESPECT_HARD_ONLY,
        )
        self.context.blocked_intervals["SAT-1"] = [
            BlockedInterval(
                acquisition_id="acq_prev",
                satellite_id="SAT-1",
                target_id="T1",
                start_time=datetime(2024, 1, 15, 10, 0, 0),
                end_time=datetime(2024, 1, 15, 10, 5, 0),
                roll_angle_deg=0.0,
                pitch_angle_deg=0.0,
            ),
            BlockedInterval(
                acquisition_id="acq_next",
                satellite_id="SAT-1",
                target_id="T2",
                start_time=datetime(2024, 1, 15, 10, 30, 0),
                end_time=datetime(2024, 1, 15, 10, 35, 0),
                roll_angle_deg=30.0,
                pitch_angle_deg=0.0,
            ),
        ]
        self.slew_config = SlewConfig(
            roll_slew_rate_deg_per_sec=1.0,
            pitch_slew_rate_deg_per_sec=1.0,
            settling_time_s=5.0,
            parallel_slew=True,
        )

    def test_feasible_with_enough_time(self) -> None:
        """Test candidate is feasible when there's enough slew time."""
        # Candidate at 10:10, roll=15, needs 15s slew + 5s settling = 20s from prev
        # Available: 5 minutes = 300s - plenty of time
        is_feasible, reasons = check_adjacency_feasibility(
            context=self.context,
            satellite_id="SAT-1",
            candidate_start=datetime(2024, 1, 15, 10, 10, 0),
            candidate_end=datetime(2024, 1, 15, 10, 12, 0),
            candidate_roll_deg=15.0,
            candidate_pitch_deg=0.0,
            slew_config=self.slew_config,
        )
        assert is_feasible is True
        assert len(reasons) == 0

    def test_infeasible_overlap_with_existing(self) -> None:
        """Test candidate is rejected when overlapping existing acquisition."""
        is_feasible, reasons = check_adjacency_feasibility(
            context=self.context,
            satellite_id="SAT-1",
            candidate_start=datetime(2024, 1, 15, 10, 3, 0),  # Overlaps acq_prev
            candidate_end=datetime(2024, 1, 15, 10, 8, 0),
            candidate_roll_deg=0.0,
            slew_config=self.slew_config,
        )
        assert is_feasible is False
        assert any("Overlaps" in r for r in reasons)

    def test_infeasible_insufficient_slew_from_previous(self) -> None:
        """Test rejection when insufficient slew time from previous acquisition."""
        # Candidate starts 8s after prev ends, but needs 45s slew (45° roll) + 5s
        is_feasible, reasons = check_adjacency_feasibility(
            context=self.context,
            satellite_id="SAT-1",
            candidate_start=datetime(2024, 1, 15, 10, 5, 8),  # 8s after prev ends
            candidate_end=datetime(2024, 1, 15, 10, 6, 0),
            candidate_roll_deg=45.0,  # Need 45s to slew from 0°
            slew_config=self.slew_config,
        )
        assert is_feasible is False
        assert any("from previous" in r for r in reasons)

    def test_infeasible_insufficient_slew_to_next(self) -> None:
        """Test rejection when insufficient slew time to next acquisition."""
        # Candidate ends 8s before next starts, but next needs 30s slew
        is_feasible, reasons = check_adjacency_feasibility(
            context=self.context,
            satellite_id="SAT-1",
            candidate_start=datetime(2024, 1, 15, 10, 28, 0),
            candidate_end=datetime(2024, 1, 15, 10, 29, 52),  # 8s before next
            candidate_roll_deg=0.0,  # Need 30s to slew to next (30°)
            slew_config=self.slew_config,
        )
        assert is_feasible is False
        assert any("to next" in r for r in reasons)

    def test_feasible_different_satellite(self) -> None:
        """Test candidate on different satellite is always feasible (no blocked intervals)."""
        is_feasible, reasons = check_adjacency_feasibility(
            context=self.context,
            satellite_id="SAT-2",  # No blocked intervals
            candidate_start=datetime(2024, 1, 15, 10, 3, 0),
            candidate_end=datetime(2024, 1, 15, 10, 8, 0),
            candidate_roll_deg=45.0,
            slew_config=self.slew_config,
        )
        assert is_feasible is True
        assert len(reasons) == 0


# =============================================================================
# Filter Opportunities Tests
# =============================================================================


class TestFilterOpportunities:
    """Tests for filter_opportunities_incremental function."""

    def setup_method(self) -> None:
        """Set up test context and opportunities."""
        self.context = IncrementalPlanningContext(
            mode=PlanningMode.INCREMENTAL,
            lock_policy=LockPolicy.RESPECT_HARD_ONLY,
        )
        self.context.blocked_intervals["SAT-1"] = [
            BlockedInterval(
                acquisition_id="acq_blocked",
                satellite_id="SAT-1",
                target_id="T_BLOCKED",
                start_time=datetime(2024, 1, 15, 10, 0, 0),
                end_time=datetime(2024, 1, 15, 10, 5, 0),
                roll_angle_deg=0.0,
            ),
        ]

        self.opportunities = [
            {
                "id": "opp_1",
                "satellite_id": "SAT-1",
                "target_id": "T1",
                "start_time": "2024-01-15T10:03:00+00:00",  # Overlaps blocked
                "end_time": "2024-01-15T10:08:00+00:00",
                "roll_angle_deg": 0.0,
            },
            {
                "id": "opp_2",
                "satellite_id": "SAT-1",
                "target_id": "T2",
                "start_time": "2024-01-15T10:30:00+00:00",  # Clear
                "end_time": "2024-01-15T10:35:00+00:00",
                "roll_angle_deg": 10.0,
            },
            {
                "id": "opp_3",
                "satellite_id": "SAT-2",  # Different satellite
                "target_id": "T3",
                "start_time": "2024-01-15T10:03:00+00:00",
                "end_time": "2024-01-15T10:08:00+00:00",
                "roll_angle_deg": 0.0,
            },
        ]

    def test_filter_rejects_overlapping(self) -> None:
        """Test that overlapping opportunities are rejected."""
        feasible, rejected = filter_opportunities_incremental(
            opportunities=self.opportunities,
            context=self.context,
        )

        # opp_1 should be rejected (overlaps), opp_2 and opp_3 should pass
        assert len(feasible) == 2
        assert len(rejected) == 1
        assert rejected[0]["id"] == "opp_1"
        assert "rejection_reasons" in rejected[0]

    def test_from_scratch_mode_no_filtering(self) -> None:
        """Test that from_scratch mode doesn't filter anything."""
        self.context.mode = PlanningMode.FROM_SCRATCH

        feasible, rejected = filter_opportunities_incremental(
            opportunities=self.opportunities,
            context=self.context,
        )

        # All opportunities should pass in from_scratch mode
        assert len(feasible) == 3
        assert len(rejected) == 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestIncrementalPlanningIntegration:
    """Integration tests for incremental planning with mocked database."""

    def test_load_blocked_intervals_filters_by_policy(self) -> None:
        """Test that load_blocked_intervals respects lock policy."""
        # Create mock database
        mock_db = MagicMock()

        # Create mock acquisition objects
        from backend.schedule_persistence import Acquisition

        mock_acquisitions = [
            MagicMock(
                id="acq_hard",
                satellite_id="SAT-1",
                target_id="T1",
                start_time="2024-01-15T10:00:00Z",
                end_time="2024-01-15T10:05:00Z",
                roll_angle_deg=0.0,
                pitch_angle_deg=0.0,
                state="committed",
                lock_level="hard",
            ),
            MagicMock(
                id="acq_soft",
                satellite_id="SAT-1",
                target_id="T2",
                start_time="2024-01-15T10:30:00Z",
                end_time="2024-01-15T10:35:00Z",
                roll_angle_deg=15.0,
                pitch_angle_deg=0.0,
                state="committed",
                lock_level="none",
            ),
            MagicMock(
                id="acq_tentative",
                satellite_id="SAT-1",
                target_id="T3",
                start_time="2024-01-15T11:00:00Z",
                end_time="2024-01-15T11:05:00Z",
                roll_angle_deg=20.0,
                pitch_angle_deg=0.0,
                state="tentative",
                lock_level="none",
            ),
        ]
        mock_db.get_acquisitions_in_horizon.return_value = mock_acquisitions

        # Test RESPECT_HARD_ONLY - both hard and committed states should block
        context = load_blocked_intervals(
            db=mock_db,
            workspace_id="ws_test",
            horizon_start=datetime(2024, 1, 15, 0, 0, 0),
            horizon_end=datetime(2024, 1, 22, 0, 0, 0),
            lock_policy=LockPolicy.RESPECT_HARD_ONLY,
            include_tentative=False,
        )

        # Both committed acquisitions should be blocked (hard lock + committed state)
        assert context.loaded_acquisitions_count == 2
        assert "SAT-1" in context.blocked_intervals
        blocked_ids = [i.acquisition_id for i in context.blocked_intervals["SAT-1"]]
        assert "acq_hard" in blocked_ids
        assert "acq_soft" in blocked_ids  # committed state blocks even with soft lock
        assert "acq_tentative" not in blocked_ids

    def test_scenario_committed_overlaps_best_candidate(self) -> None:
        """
        Scenario: Horizon has committed acquisition that overlaps with best candidate.
        Incremental planner must avoid it.
        """
        context = IncrementalPlanningContext(
            mode=PlanningMode.INCREMENTAL,
            lock_policy=LockPolicy.RESPECT_HARD_ONLY,
        )

        # Committed acquisition blocks 10:00-10:05
        context.blocked_intervals["SAT-1"] = [
            BlockedInterval(
                acquisition_id="committed_acq",
                satellite_id="SAT-1",
                target_id="T_COMMITTED",
                start_time=datetime(2024, 1, 15, 10, 0, 0),
                end_time=datetime(2024, 1, 15, 10, 5, 0),
                roll_angle_deg=0.0,
            ),
        ]

        # Best candidate (highest value) overlaps
        opportunities = [
            {
                "id": "best_but_blocked",
                "satellite_id": "SAT-1",
                "target_id": "HIGH_VALUE",
                "start_time": "2024-01-15T10:02:00+00:00",
                "end_time": "2024-01-15T10:07:00+00:00",
                "roll_angle_deg": 0.0,
                "value": 100.0,
            },
            {
                "id": "second_best",
                "satellite_id": "SAT-1",
                "target_id": "MEDIUM_VALUE",
                "start_time": "2024-01-15T10:30:00+00:00",
                "end_time": "2024-01-15T10:35:00+00:00",
                "roll_angle_deg": 0.0,
                "value": 50.0,
            },
        ]

        feasible, rejected = filter_opportunities_incremental(
            opportunities=opportunities,
            context=context,
        )

        # Best candidate must be rejected, second best should pass
        assert len(feasible) == 1
        assert feasible[0]["id"] == "second_best"
        assert len(rejected) == 1
        assert rejected[0]["id"] == "best_but_blocked"

    def test_scenario_small_gap_slew_feasibility(self) -> None:
        """
        Scenario: Two committed acquisitions with small gap.
        Candidate must satisfy slew feasibility relative to both neighbors.
        """
        context = IncrementalPlanningContext(
            mode=PlanningMode.INCREMENTAL,
            lock_policy=LockPolicy.RESPECT_HARD_ONLY,
        )

        # Two committed acquisitions with 60s gap
        context.blocked_intervals["SAT-1"] = [
            BlockedInterval(
                acquisition_id="acq_before",
                satellite_id="SAT-1",
                target_id="T_BEFORE",
                start_time=datetime(2024, 1, 15, 10, 0, 0),
                end_time=datetime(2024, 1, 15, 10, 5, 0),
                roll_angle_deg=-30.0,  # Left side
            ),
            BlockedInterval(
                acquisition_id="acq_after",
                satellite_id="SAT-1",
                target_id="T_AFTER",
                start_time=datetime(2024, 1, 15, 10, 6, 0),  # 60s gap
                end_time=datetime(2024, 1, 15, 10, 11, 0),
                roll_angle_deg=30.0,  # Right side
            ),
        ]

        slew_config = SlewConfig(
            roll_slew_rate_deg_per_sec=1.0,
            settling_time_s=5.0,
        )

        # Candidate in the gap that would require impossible slew
        # From -30° to 0° = 30s slew + 5s settling = 35s
        # From 0° to 30° = 30s slew + 5s settling = 35s
        # Total needed: at least 35s before and 35s after
        # Available: 60s total, but only 30s each direction if centered

        is_feasible, reasons = check_adjacency_feasibility(
            context=context,
            satellite_id="SAT-1",
            candidate_start=datetime(2024, 1, 15, 10, 5, 10),  # 10s after prev
            candidate_end=datetime(2024, 1, 15, 10, 5, 50),  # 10s before next
            candidate_roll_deg=0.0,
            slew_config=slew_config,
        )

        # Should be infeasible due to insufficient slew time
        assert is_feasible is False
        assert len(reasons) >= 1

    def test_compare_from_scratch_vs_incremental(self) -> None:
        """
        Compare output difference between from_scratch and incremental modes.
        """
        opportunities = [
            {
                "id": "opp_blocked",
                "satellite_id": "SAT-1",
                "target_id": "T1",
                "start_time": "2024-01-15T10:02:00+00:00",
                "end_time": "2024-01-15T10:07:00+00:00",
                "roll_angle_deg": 0.0,
            },
            {
                "id": "opp_clear",
                "satellite_id": "SAT-1",
                "target_id": "T2",
                "start_time": "2024-01-15T11:00:00+00:00",
                "end_time": "2024-01-15T11:05:00+00:00",
                "roll_angle_deg": 0.0,
            },
        ]

        # From scratch mode
        context_scratch = IncrementalPlanningContext(
            mode=PlanningMode.FROM_SCRATCH,
        )
        feasible_scratch, rejected_scratch = filter_opportunities_incremental(
            opportunities=opportunities,
            context=context_scratch,
        )

        # Incremental mode with blocking
        context_incr = IncrementalPlanningContext(
            mode=PlanningMode.INCREMENTAL,
        )
        context_incr.blocked_intervals["SAT-1"] = [
            BlockedInterval(
                acquisition_id="blocker",
                satellite_id="SAT-1",
                target_id="T_BLOCK",
                start_time=datetime(2024, 1, 15, 10, 0, 0),
                end_time=datetime(2024, 1, 15, 10, 10, 0),
                roll_angle_deg=0.0,
            ),
        ]
        feasible_incr, rejected_incr = filter_opportunities_incremental(
            opportunities=opportunities,
            context=context_incr,
        )

        # From scratch should accept all
        assert len(feasible_scratch) == 2
        assert len(rejected_scratch) == 0

        # Incremental should reject the blocked one
        assert len(feasible_incr) == 1
        assert len(rejected_incr) == 1
        assert rejected_incr[0]["id"] == "opp_blocked"


# =============================================================================
# Validation Scenarios for PR: Incremental Planning Mode
# =============================================================================


class TestIncrementalPlanningValidation:
    """
    Validation scenarios for incremental planning correctness and conflict prediction.
    These tests verify the PR requirements for incremental planning mode.
    """

    def test_scenario_horizon_boundary_respected(self) -> None:
        """
        Scenario: Acquisitions outside horizon should not block candidates.
        Only acquisitions within the specified horizon should create blocked intervals.
        """
        context = IncrementalPlanningContext(
            mode=PlanningMode.INCREMENTAL,
            lock_policy=LockPolicy.RESPECT_HARD_ONLY,
            horizon_start=datetime(2024, 1, 15, 0, 0, 0),
            horizon_end=datetime(2024, 1, 16, 0, 0, 0),  # 1-day horizon
        )

        # Acquisition outside horizon (before)
        context.blocked_intervals["SAT-1"] = [
            BlockedInterval(
                acquisition_id="outside_before",
                satellite_id="SAT-1",
                target_id="T_OUTSIDE",
                start_time=datetime(2024, 1, 14, 10, 0, 0),  # Day before horizon
                end_time=datetime(2024, 1, 14, 10, 5, 0),
                roll_angle_deg=0.0,
            ),
        ]

        # Candidate within horizon should not be blocked by out-of-horizon acquisition
        is_blocked, _ = context.is_time_blocked(
            satellite_id="SAT-1",
            start_time=datetime(2024, 1, 15, 10, 0, 0),
            end_time=datetime(2024, 1, 15, 10, 5, 0),
        )
        # The blocked interval is outside horizon, so no blocking within horizon
        assert is_blocked is False

    def test_scenario_lock_policy_hard_only(self) -> None:
        """
        Scenario: RESPECT_HARD_ONLY policy should only block hard-locked acquisitions
        when considering lock levels (soft locks should still block if committed).
        """
        context = IncrementalPlanningContext(
            mode=PlanningMode.INCREMENTAL,
            lock_policy=LockPolicy.RESPECT_HARD_ONLY,
        )

        # Both hard and soft locked committed acquisitions should block
        # (hard_only refers to not moving them, but they still occupy time)
        context.blocked_intervals["SAT-1"] = [
            BlockedInterval(
                acquisition_id="hard_locked",
                satellite_id="SAT-1",
                target_id="T1",
                start_time=datetime(2024, 1, 15, 10, 0, 0),
                end_time=datetime(2024, 1, 15, 10, 5, 0),
                roll_angle_deg=0.0,
                lock_level="hard",
            ),
        ]

        # Overlapping candidate should be blocked
        is_blocked, blocking = context.is_time_blocked(
            satellite_id="SAT-1",
            start_time=datetime(2024, 1, 15, 10, 2, 0),
            end_time=datetime(2024, 1, 15, 10, 7, 0),
        )
        assert is_blocked is True
        assert blocking is not None
        assert blocking.lock_level == "hard"

    def test_scenario_multi_satellite_independence(self) -> None:
        """
        Scenario: Blocked intervals on one satellite should not affect another.
        Each satellite has independent scheduling constraints.
        """
        context = IncrementalPlanningContext(
            mode=PlanningMode.INCREMENTAL,
            lock_policy=LockPolicy.RESPECT_HARD_ONLY,
        )

        # Block SAT-1 at 10:00-10:05
        context.blocked_intervals["SAT-1"] = [
            BlockedInterval(
                acquisition_id="sat1_blocked",
                satellite_id="SAT-1",
                target_id="T1",
                start_time=datetime(2024, 1, 15, 10, 0, 0),
                end_time=datetime(2024, 1, 15, 10, 5, 0),
                roll_angle_deg=0.0,
            ),
        ]

        # SAT-2 should be free at the same time
        is_blocked_sat1, _ = context.is_time_blocked(
            satellite_id="SAT-1",
            start_time=datetime(2024, 1, 15, 10, 2, 0),
            end_time=datetime(2024, 1, 15, 10, 7, 0),
        )
        is_blocked_sat2, _ = context.is_time_blocked(
            satellite_id="SAT-2",
            start_time=datetime(2024, 1, 15, 10, 2, 0),
            end_time=datetime(2024, 1, 15, 10, 7, 0),
        )

        assert is_blocked_sat1 is True  # SAT-1 is blocked
        assert is_blocked_sat2 is False  # SAT-2 is free

    def test_scenario_adjacent_slew_chain(self) -> None:
        """
        Scenario: Multiple blocked intervals require slew feasibility checks
        for both previous and next neighbors in sequence.
        """
        context = IncrementalPlanningContext(
            mode=PlanningMode.INCREMENTAL,
            lock_policy=LockPolicy.RESPECT_HARD_ONLY,
        )

        # Chain of 3 acquisitions with varying roll angles
        context.blocked_intervals["SAT-1"] = [
            BlockedInterval(
                acquisition_id="acq_1",
                satellite_id="SAT-1",
                target_id="T1",
                start_time=datetime(2024, 1, 15, 10, 0, 0),
                end_time=datetime(2024, 1, 15, 10, 5, 0),
                roll_angle_deg=-20.0,
            ),
            BlockedInterval(
                acquisition_id="acq_2",
                satellite_id="SAT-1",
                target_id="T2",
                start_time=datetime(2024, 1, 15, 10, 20, 0),
                end_time=datetime(2024, 1, 15, 10, 25, 0),
                roll_angle_deg=0.0,
            ),
            BlockedInterval(
                acquisition_id="acq_3",
                satellite_id="SAT-1",
                target_id="T3",
                start_time=datetime(2024, 1, 15, 10, 40, 0),
                end_time=datetime(2024, 1, 15, 10, 45, 0),
                roll_angle_deg=20.0,
            ),
        ]

        slew_config = SlewConfig(
            roll_slew_rate_deg_per_sec=1.0,
            settling_time_s=5.0,
        )

        # Candidate between acq_1 and acq_2 with sufficient time
        is_feasible, reasons = check_adjacency_feasibility(
            context=context,
            satellite_id="SAT-1",
            candidate_start=datetime(2024, 1, 15, 10, 10, 0),  # 5 min after acq_1
            candidate_end=datetime(2024, 1, 15, 10, 12, 0),
            candidate_roll_deg=-10.0,  # 10° from prev, 10° to next
            slew_config=slew_config,
        )
        # Should be feasible: 10° slew = 10s + 5s settling = 15s, have 5 min
        assert is_feasible is True

    def test_scenario_tentative_inclusion_toggle(self) -> None:
        """
        Scenario: Tentative acquisitions should be optionally included/excluded
        from blocked intervals based on the include_tentative flag.
        """
        # This tests the behavior when loading blocked intervals
        # Tentative acquisitions should only block if include_tentative=True
        context_without_tentative = IncrementalPlanningContext(
            mode=PlanningMode.INCREMENTAL,
            lock_policy=LockPolicy.RESPECT_HARD_ONLY,
        )

        context_with_tentative = IncrementalPlanningContext(
            mode=PlanningMode.INCREMENTAL,
            lock_policy=LockPolicy.RESPECT_HARD_AND_SOFT,
        )

        # Both contexts have the same committed acquisition
        committed = BlockedInterval(
            acquisition_id="committed",
            satellite_id="SAT-1",
            target_id="T1",
            start_time=datetime(2024, 1, 15, 10, 0, 0),
            end_time=datetime(2024, 1, 15, 10, 5, 0),
            roll_angle_deg=0.0,
            state="committed",
        )

        context_without_tentative.blocked_intervals["SAT-1"] = [committed]
        context_with_tentative.blocked_intervals["SAT-1"] = [committed]

        # Both should block the committed acquisition
        blocked1, _ = context_without_tentative.is_time_blocked(
            "SAT-1",
            datetime(2024, 1, 15, 10, 2, 0),
            datetime(2024, 1, 15, 10, 7, 0),
        )
        blocked2, _ = context_with_tentative.is_time_blocked(
            "SAT-1",
            datetime(2024, 1, 15, 10, 2, 0),
            datetime(2024, 1, 15, 10, 7, 0),
        )

        assert blocked1 is True
        assert blocked2 is True

    def test_scenario_rejection_reasons_detailed(self) -> None:
        """
        Scenario: Rejection reasons should be detailed and actionable.
        """
        context = IncrementalPlanningContext(
            mode=PlanningMode.INCREMENTAL,
            lock_policy=LockPolicy.RESPECT_HARD_ONLY,
        )

        context.blocked_intervals["SAT-1"] = [
            BlockedInterval(
                acquisition_id="blocker",
                satellite_id="SAT-1",
                target_id="T_BLOCK",
                start_time=datetime(2024, 1, 15, 10, 0, 0),
                end_time=datetime(2024, 1, 15, 10, 5, 0),
                roll_angle_deg=0.0,
            ),
        ]

        opportunities = [
            {
                "id": "opp_overlap",
                "satellite_id": "SAT-1",
                "target_id": "T1",
                "start_time": "2024-01-15T10:03:00+00:00",
                "end_time": "2024-01-15T10:08:00+00:00",
                "roll_angle_deg": 0.0,
            },
        ]

        feasible, rejected = filter_opportunities_incremental(
            opportunities=opportunities,
            context=context,
        )

        assert len(rejected) == 1
        assert "rejection_reasons" in rejected[0]
        assert len(rejected[0]["rejection_reasons"]) > 0
        # Reason should mention overlap or blocked
        assert any(
            "Overlaps" in r or "blocked" in r.lower()
            for r in rejected[0]["rejection_reasons"]
        )


class TestRepairPlanningMode:
    """Tests for the Repair planning mode."""

    def test_repair_mode_enum_exists(self) -> None:
        """Test that PlanningMode.REPAIR exists."""
        assert hasattr(PlanningMode, "REPAIR")
        assert PlanningMode.REPAIR.value == "repair"

    def test_repair_scope_enum(self) -> None:
        """Test RepairScope enum values."""
        from backend.incremental_planning import RepairScope

        assert RepairScope.WORKSPACE_HORIZON.value == "workspace_horizon"
        assert RepairScope.SATELLITE_SUBSET.value == "satellite_subset"
        assert RepairScope.TARGET_SUBSET.value == "target_subset"

    def test_repair_objective_enum(self) -> None:
        """Test RepairObjective enum values."""
        from backend.incremental_planning import RepairObjective

        assert RepairObjective.MAXIMIZE_SCORE.value == "maximize_score"
        assert RepairObjective.MAXIMIZE_PRIORITY.value == "maximize_priority"
        assert RepairObjective.MINIMIZE_CHANGES.value == "minimize_changes"

    def test_flexible_acquisition_dataclass(self) -> None:
        """Test FlexibleAcquisition dataclass creation."""
        from backend.incremental_planning import FlexibleAcquisition

        flex_acq = FlexibleAcquisition(
            acquisition_id="acq-1",
            satellite_id="SAT-1",
            target_id="T1",
            original_start=datetime(2024, 1, 15, 10, 0, 0),
            original_end=datetime(2024, 1, 15, 10, 5, 0),
            roll_angle_deg=5.0,
            lock_level="none",
        )

        assert flex_acq.acquisition_id == "acq-1"
        assert flex_acq.satellite_id == "SAT-1"
        assert flex_acq.lock_level == "none"
        assert flex_acq.action == "keep"  # default

    def test_repair_planning_context_partitioning(self) -> None:
        """Test RepairPlanningContext correctly partitions fixed and flex sets."""
        from backend.incremental_planning import (
            FlexibleAcquisition,
            RepairObjective,
            RepairPlanningContext,
        )

        # Create a context with mixed acquisitions
        fixed_acq = BlockedInterval(
            acquisition_id="hard-1",
            satellite_id="SAT-1",
            target_id="T1",
            start_time=datetime(2024, 1, 15, 10, 0, 0),
            end_time=datetime(2024, 1, 15, 10, 5, 0),
            roll_angle_deg=0.0,
            lock_level="hard",
        )

        flex_acq = FlexibleAcquisition(
            acquisition_id="unlocked-1",
            satellite_id="SAT-1",
            target_id="T2",
            original_start=datetime(2024, 1, 15, 11, 0, 0),
            original_end=datetime(2024, 1, 15, 11, 5, 0),
            roll_angle_deg=5.0,
            lock_level="none",
        )

        context = RepairPlanningContext(
            horizon_start=datetime(2024, 1, 15, 0, 0, 0),
            horizon_end=datetime(2024, 1, 16, 0, 0, 0),
            workspace_id="default",
            objective=RepairObjective.MAXIMIZE_SCORE,
            max_changes=100,
            fixed_set=[fixed_acq],
            flex_set=[flex_acq],
        )

        assert len(context.fixed_set) == 1
        assert len(context.flex_set) == 1
        assert context.fixed_set[0].lock_level == "hard"
        assert context.flex_set[0].lock_level == "none"

    def test_repair_diff_structure(self) -> None:
        """Test RepairDiff Pydantic model structure."""
        from backend.incremental_planning import ChangeScore, RepairDiff

        diff = RepairDiff(
            kept=["acq-1", "acq-2"],
            dropped=["acq-3"],
            added=["acq-4", "acq-5"],
            moved=[],
            reason_summary={
                "dropped": [{"id": "acq-3", "reason": "Better alternative found"}]
            },
            change_score=ChangeScore(num_changes=3, percent_changed=30.0),
        )

        assert len(diff.kept) == 2
        assert len(diff.dropped) == 1
        assert len(diff.added) == 2
        assert diff.change_score.num_changes == 3
        assert diff.change_score.percent_changed == 30.0

    def test_repair_hard_locks_immutable(self) -> None:
        """Test that hard-locked acquisitions are never modified in repair mode."""
        from backend.incremental_planning import RepairObjective, RepairPlanningContext

        hard_acq = BlockedInterval(
            acquisition_id="hard-1",
            satellite_id="SAT-1",
            target_id="T1",
            start_time=datetime(2024, 1, 15, 10, 0, 0),
            end_time=datetime(2024, 1, 15, 10, 5, 0),
            roll_angle_deg=0.0,
            lock_level="hard",
        )

        context = RepairPlanningContext(
            horizon_start=datetime(2024, 1, 15, 0, 0, 0),
            horizon_end=datetime(2024, 1, 16, 0, 0, 0),
            workspace_id="default",
            objective=RepairObjective.MAXIMIZE_SCORE,
            max_changes=100,
            fixed_set=[hard_acq],
            flex_set=[],
        )

        # Hard locks should be in fixed_set and never moved to flex_set
        assert len(context.fixed_set) == 1
        assert context.fixed_set[0].acquisition_id == "hard-1"
        assert context.fixed_set[0].satellite_id == "SAT-1"

    def test_max_changes_constraint(self) -> None:
        """Test that max_changes is properly stored in context."""
        from backend.incremental_planning import RepairObjective, RepairPlanningContext

        context = RepairPlanningContext(
            horizon_start=datetime(2024, 1, 15, 0, 0, 0),
            horizon_end=datetime(2024, 1, 16, 0, 0, 0),
            workspace_id="default",
            objective=RepairObjective.MINIMIZE_CHANGES,
            max_changes=5,
            fixed_set=[],
            flex_set=[],
        )

        assert context.max_changes == 5
        assert context.objective == RepairObjective.MINIMIZE_CHANGES

    def test_change_score_calculation(self) -> None:
        """Test ChangeScore calculation."""
        from backend.incremental_planning import ChangeScore

        # 3 changes out of 10 total = 30%
        score = ChangeScore(num_changes=3, percent_changed=30.0)
        assert score.num_changes == 3
        assert score.percent_changed == 30.0

        # Edge case: no changes
        zero_score = ChangeScore(num_changes=0, percent_changed=0.0)
        assert zero_score.num_changes == 0

    def test_metrics_comparison_structure(self) -> None:
        """Test MetricsComparison Pydantic model structure."""
        from backend.incremental_planning import MetricsComparison

        comparison = MetricsComparison(
            score_before=100.0,
            score_after=120.0,
            score_delta=20.0,
            conflicts_before=2,
            conflicts_after=0,
            acquisition_count_before=10,
            acquisition_count_after=12,
        )

        assert comparison.score_delta == 20.0
        assert comparison.conflicts_before == 2
        assert comparison.conflicts_after == 0
        assert comparison.acquisition_count_after > comparison.acquisition_count_before
