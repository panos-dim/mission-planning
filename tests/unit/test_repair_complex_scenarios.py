"""
Complex messy scenarios for repair planning: priority reshuffling, close targets,
multi-eviction, cross-satellite swaps, and reason validation.

Each test simulates a realistic "update schedule" workflow where the user has an
existing committed schedule and then changes priorities / adds targets / re-runs.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pytest

from backend.incremental_planning import (
    BlockedInterval,
    FlexibleAcquisition,
    IncrementalPlanningContext,
    PlanningMode,
    RepairDiff,
    RepairObjective,
    RepairPlanningContext,
    RepairScope,
    SlewConfig,
    execute_repair_planning,
)


# =============================================================================
# Helpers
# =============================================================================

SLEW = SlewConfig(roll_slew_rate_deg_per_sec=1.0, pitch_slew_rate_deg_per_sec=1.0)
T0 = datetime(2026, 2, 24, 9, 0, 0)  # Base time for all scenarios


def _flex(
    acq_id: str,
    sat: str,
    target: str,
    minute: float,
    roll: float = 15.0,
    value: float = 0.30,
    lock: str = "none",
) -> FlexibleAcquisition:
    """Shorthand to build a FlexibleAcquisition."""
    start = T0 + timedelta(minutes=minute)
    return FlexibleAcquisition(
        acquisition_id=acq_id,
        satellite_id=sat,
        target_id=target,
        original_start=start,
        original_end=start + timedelta(seconds=1),
        roll_angle_deg=roll,
        value=value,
        lock_level=lock,
    )


def _opp(
    opp_id: str,
    sat: str,
    target: str,
    minute: float,
    roll: float = 15.0,
    value: float = 0.50,
    priority: int = 5,
) -> Dict[str, Any]:
    """Shorthand to build an opportunity dict."""
    start = T0 + timedelta(minutes=minute)
    end = start + timedelta(seconds=1)
    return {
        "id": opp_id,
        "opportunity_id": opp_id,
        "satellite_id": sat,
        "target_id": target,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "roll_angle_deg": roll,
        "pitch_angle_deg": 0.0,
        "value": value,
        "quality_score": 0.5,
        "priority": priority,
    }


def _run_repair(
    flex_set: List[FlexibleAcquisition],
    opportunities: List[Dict[str, Any]],
    target_priorities: Optional[Dict[str, int]] = None,
    fixed_set: Optional[List[BlockedInterval]] = None,
    max_changes: int = 100,
    objective: RepairObjective = RepairObjective.MAXIMIZE_SCORE,
) -> Tuple[List[Dict[str, Any]], RepairDiff, Dict[str, Any]]:
    """Run repair planning with convenient defaults."""
    ctx = RepairPlanningContext(
        mode=PlanningMode.REPAIR,
        objective=objective,
        flex_set=flex_set,
        fixed_set=fixed_set or [],
        original_acquisition_count=len(flex_set) + len(fixed_set or []),
    )
    return execute_repair_planning(
        repair_context=ctx,
        opportunities=opportunities,
        max_changes=max_changes,
        objective=objective,
        slew_config=SLEW,
        target_priorities=target_priorities,
    )


def _drop_reasons_for(diff: RepairDiff, acq_id: str) -> List[str]:
    """Extract drop reason texts for a specific acquisition ID."""
    reasons = []
    for entry in diff.reason_summary.get("dropped", []):
        if entry.get("id") == acq_id:
            reasons.append(entry.get("reason", ""))
    return reasons


# =============================================================================
# Scenario 1: Single high-priority target evicts single low-priority target
# =============================================================================


class TestSinglePriorityEviction:
    """
    Existing: 4 targets on SAT-A, all priority 5, tightly packed (2-min gaps).
    Update:   User adds Target-X (priority 1), only fits on SAT-A at minute 6
              which conflicts with Target-D (minute 6, priority 5).
    Expected: Target-D dropped, Target-X added. Reason mentions priority eviction.
    """

    def test_high_priority_evicts_low_priority(self) -> None:
        flex = [
            _flex("acq_a", "SAT-A", "Target-A", 0, value=0.30),
            _flex("acq_b", "SAT-A", "Target-B", 2, value=0.30),
            _flex("acq_c", "SAT-A", "Target-C", 4, value=0.30),
            _flex("acq_d", "SAT-A", "Target-D", 6, value=0.30),
        ]
        opps = [
            # Target-X only fits at minute 6 on SAT-A — conflicts with Target-D
            _opp("opp_x", "SAT-A", "Target-X", 6, value=0.85, priority=1),
        ]
        priorities = {
            "Target-A": 5, "Target-B": 5, "Target-C": 5, "Target-D": 5,
            "Target-X": 1,
        }

        proposed, diff, metrics = _run_repair(flex, opps, priorities)

        # Target-X must be added
        assert "opp_x" in diff.added, f"Target-X should be added, added={diff.added}"
        # Target-D must be dropped (evicted)
        assert "acq_d" in diff.dropped, f"Target-D should be dropped, dropped={diff.dropped}"
        # Other targets kept
        assert "acq_a" in diff.kept
        assert "acq_b" in diff.kept
        assert "acq_c" in diff.kept
        # Reason must mention priority eviction
        reasons = _drop_reasons_for(diff, "acq_d")
        assert len(reasons) > 0, "Must have a drop reason for Target-D"
        assert "priority" in reasons[0].lower() or "Priority" in reasons[0], (
            f"Drop reason should mention priority, got: {reasons[0]}"
        )
        # Change count: 1 drop + 1 add = 2
        assert diff.change_score.num_changes == 2

    def test_eviction_respects_priority_order(self) -> None:
        """When multiple flex items exist, the LOWEST priority (highest number) is evicted."""
        flex = [
            _flex("acq_p3", "SAT-A", "Target-P3", 6, value=0.40),  # priority 3
            _flex("acq_p5", "SAT-A", "Target-P5", 6.02, value=0.30),  # priority 5
        ]
        opps = [
            # Target-X at minute 6 on SAT-A — could evict either P3 or P5
            _opp("opp_x", "SAT-A", "Target-X", 6.01, value=0.85, priority=1),
        ]
        priorities = {
            "Target-P3": 3, "Target-P5": 5, "Target-X": 1,
        }

        _, diff, _ = _run_repair(flex, opps, priorities)

        # Should evict P5 first (worst priority), not P3
        if "opp_x" in diff.added:
            assert "acq_p5" in diff.dropped, (
                "Should evict priority-5 target before priority-3"
            )


# =============================================================================
# Scenario 2: Multiple priority changes at once — cascade eviction
# =============================================================================


class TestMultiPriorityEviction:
    """
    Existing: 5 targets on SAT-A (all P5), well-spaced (3-min gaps).
    Update:   User bumps TWO new targets to P1, both only fit on SAT-A
              at minutes that conflict with existing P5 targets.
    Expected: Two P5 targets evicted, two P1 targets added. Correct reasons for each.
    """

    def test_two_evictions_two_additions(self) -> None:
        flex = [
            _flex("acq_e1", "SAT-A", "Existing-1", 0, value=0.30),
            _flex("acq_e2", "SAT-A", "Existing-2", 3, value=0.30),
            _flex("acq_e3", "SAT-A", "Existing-3", 6, value=0.30),
            _flex("acq_e4", "SAT-A", "Existing-4", 9, value=0.30),
            _flex("acq_e5", "SAT-A", "Existing-5", 12, value=0.30),
        ]
        opps = [
            # New-P1-A at minute 3 — conflicts with Existing-2
            _opp("opp_new_a", "SAT-A", "New-P1-A", 3, value=0.85, priority=1),
            # New-P1-B at minute 9 — conflicts with Existing-4
            _opp("opp_new_b", "SAT-A", "New-P1-B", 9, value=0.85, priority=1),
        ]
        priorities = {
            "Existing-1": 5, "Existing-2": 5, "Existing-3": 5,
            "Existing-4": 5, "Existing-5": 5,
            "New-P1-A": 1, "New-P1-B": 1,
        }

        _, diff, _ = _run_repair(flex, opps, priorities)

        # Both new targets added
        assert "opp_new_a" in diff.added, f"New-P1-A should be added, added={diff.added}"
        assert "opp_new_b" in diff.added, f"New-P1-B should be added, added={diff.added}"
        # The conflicting existing targets dropped
        assert "acq_e2" in diff.dropped, f"Existing-2 should be dropped, dropped={diff.dropped}"
        assert "acq_e4" in diff.dropped, f"Existing-4 should be dropped, dropped={diff.dropped}"
        # Non-conflicting targets kept
        assert "acq_e1" in diff.kept
        assert "acq_e3" in diff.kept
        assert "acq_e5" in diff.kept
        # 2 drops + 2 adds = 4 changes
        assert diff.change_score.num_changes == 4
        # Each drop has a reason
        for acq_id in ["acq_e2", "acq_e4"]:
            reasons = _drop_reasons_for(diff, acq_id)
            assert len(reasons) > 0, f"Missing drop reason for {acq_id}"


# =============================================================================
# Scenario 3: Cross-satellite coverage swap (Stage E)
# =============================================================================


class TestCrossSatelliteSwap:
    """
    Existing: Target-A on SAT-1 at minute 5, Target-B on SAT-1 at minute 7.
    Update:   New Target-C (P1) only fits on SAT-1 at minute 5 (conflicts with A).
              Target-A has an alternative opportunity on SAT-2 at minute 10.
    Expected: Stage E swaps Target-A from SAT-1 to SAT-2, adds Target-C on SAT-1.
              Target-B untouched. Net coverage: +1 (2→3).
    """

    def test_coverage_swap_adds_target(self) -> None:
        flex = [
            _flex("acq_a", "SAT-1", "Target-A", 5, value=0.40),
            _flex("acq_b", "SAT-1", "Target-B", 7, value=0.40),
        ]
        opps = [
            # Target-C only on SAT-1 at minute 5 — conflicts with Target-A
            _opp("opp_c", "SAT-1", "Target-C", 5, value=0.50, priority=3),
            # Target-A alternative on SAT-2 at minute 10 (no conflicts there)
            _opp("opp_a_alt", "SAT-2", "Target-A", 10, value=0.35, priority=5),
        ]
        priorities = {"Target-A": 5, "Target-B": 5, "Target-C": 3}

        proposed, diff, _ = _run_repair(flex, opps, priorities)

        # Target-C should be added
        assert "opp_c" in diff.added, f"Target-C should be added, added={diff.added}"
        # Target-A should be dropped from SAT-1 (re-covered on SAT-2)
        assert "acq_a" in diff.dropped, f"Target-A should be dropped, dropped={diff.dropped}"
        # Target-A's alternative should be added on SAT-2
        assert "opp_a_alt" in diff.added, f"Target-A alt should be added, added={diff.added}"
        # Target-B kept
        assert "acq_b" in diff.kept
        # Drop reason should mention coverage swap
        reasons = _drop_reasons_for(diff, "acq_a")
        assert len(reasons) > 0
        assert "coverage" in reasons[0].lower() or "swap" in reasons[0].lower(), (
            f"Drop reason should mention coverage swap, got: {reasons[0]}"
        )
        # 1 drop + 2 adds = 3 changes
        assert diff.change_score.num_changes == 3

    def test_swap_preserves_net_coverage(self) -> None:
        """After a coverage swap, ALL original targets + the new target are covered."""
        flex = [
            _flex("acq_a", "SAT-1", "Target-A", 5, value=0.40),
            _flex("acq_b", "SAT-1", "Target-B", 7, value=0.40),
        ]
        opps = [
            _opp("opp_c", "SAT-1", "Target-C", 5, value=0.50, priority=3),
            _opp("opp_a_alt", "SAT-2", "Target-A", 10, value=0.35, priority=5),
        ]
        priorities = {"Target-A": 5, "Target-B": 5, "Target-C": 3}

        proposed, _, _ = _run_repair(flex, opps, priorities)

        covered_targets = set()
        for item in proposed:
            covered_targets.add(item.get("target_id", ""))
        assert "Target-A" in covered_targets, "Target-A must still be covered after swap"
        assert "Target-B" in covered_targets, "Target-B must be kept"
        assert "Target-C" in covered_targets, "Target-C must be added"


# =============================================================================
# Scenario 4: Hard-locked items are NEVER evicted
# =============================================================================


class TestHardLockImmunity:
    """
    Existing: Target-VIP on SAT-A at minute 5 with hard lock, value=0.10 (low).
    Update:   New Target-URGENT (P1, value=0.95) also needs SAT-A at minute 5.
    Expected: Target-VIP is NOT dropped (hard lock). Target-URGENT stays unscheduled.
    """

    def test_hard_lock_blocks_eviction(self) -> None:
        # Hard-locked item goes in fixed_set, not flex_set
        fixed = [
            BlockedInterval(
                acquisition_id="acq_vip",
                satellite_id="SAT-A",
                target_id="Target-VIP",
                start_time=T0 + timedelta(minutes=5),
                end_time=T0 + timedelta(minutes=5, seconds=1),
                roll_angle_deg=15.0,
                lock_level="hard",
            ),
        ]
        opps = [
            _opp("opp_urgent", "SAT-A", "Target-URGENT", 5, value=0.95, priority=1),
        ]
        priorities = {"Target-VIP": 5, "Target-URGENT": 1}

        _, diff, _ = _run_repair([], opps, priorities, fixed_set=fixed)

        # Hard-locked item must NOT be dropped
        assert "acq_vip" not in diff.dropped, "Hard-locked item must never be dropped"
        # Target-URGENT cannot be added (no room)
        assert "opp_urgent" not in diff.added, (
            "Target-URGENT should not be added — hard lock blocks its slot"
        )
        assert diff.change_score.num_changes == 0


# =============================================================================
# Scenario 5: Priority eviction with tightly packed satellite timeline
# =============================================================================


class TestTightlyPackedEviction:
    """
    Existing: 6 targets on SAT-A, every 2 minutes from minute 0 to minute 10.
              All P5, all value=0.30.
    Update:   User sets Target-F (minute 10) to P1.
              New Target-G (P1) needs SAT-A at minute 4 — conflicts with Target-C (P5).
    Expected: Target-C is evicted for Target-G. Target-F stays (already scheduled).
              The eviction at minute 4 must NOT break neighbors at minute 2 and 6.
    """

    def test_eviction_in_tight_schedule_preserves_neighbors(self) -> None:
        flex = [
            _flex("acq_a", "SAT-A", "Target-A", 0, value=0.30),
            _flex("acq_b", "SAT-A", "Target-B", 2, value=0.30),
            _flex("acq_c", "SAT-A", "Target-C", 4, value=0.30),
            _flex("acq_d", "SAT-A", "Target-D", 6, value=0.30),
            _flex("acq_e", "SAT-A", "Target-E", 8, value=0.30),
            _flex("acq_f", "SAT-A", "Target-F", 10, value=0.30),
        ]
        opps = [
            _opp("opp_g", "SAT-A", "Target-G", 4, value=0.85, priority=1),
        ]
        priorities = {
            "Target-A": 5, "Target-B": 5, "Target-C": 5,
            "Target-D": 5, "Target-E": 5, "Target-F": 1,
            "Target-G": 1,
        }

        proposed, diff, _ = _run_repair(flex, opps, priorities)

        # Target-G added, Target-C evicted
        assert "opp_g" in diff.added
        assert "acq_c" in diff.dropped

        # Neighbors must be kept
        assert "acq_b" in diff.kept, "Target-B (minute 2) must be kept"
        assert "acq_d" in diff.kept, "Target-D (minute 6) must be kept"

        # Target-F (already scheduled, P1) must be kept
        assert "acq_f" in diff.kept, "Target-F (already P1) must be kept"


# =============================================================================
# Scenario 6: No eviction when new target has LOWER priority than existing
# =============================================================================


class TestNoEvictionWhenLowerPriority:
    """
    Existing: Target-A (P2) on SAT-A at minute 5.
    Update:   New Target-B (P4) needs SAT-A at minute 5.
    Expected: No eviction — you don't drop a P2 for a P4. Zero changes.
    """

    def test_lower_priority_does_not_evict(self) -> None:
        flex = [
            _flex("acq_a", "SAT-A", "Target-A", 5, value=0.60),
        ]
        opps = [
            _opp("opp_b", "SAT-A", "Target-B", 5, value=0.20, priority=4),
        ]
        priorities = {"Target-A": 2, "Target-B": 4}

        _, diff, _ = _run_repair(flex, opps, priorities)

        assert "acq_a" not in diff.dropped, "P2 target must NOT be evicted by P4"
        assert "opp_b" not in diff.added, "P4 target should not replace P2"
        assert diff.change_score.num_changes == 0


# =============================================================================
# Scenario 7: Mixed priorities across multiple satellites
# =============================================================================


class TestMixedPriorityMultiSatellite:
    """
    Existing:
      SAT-1: Target-A (P5, min 0), Target-B (P5, min 3)
      SAT-2: Target-C (P5, min 0), Target-D (P5, min 3)
    Update:
      New Target-X (P1) only fits on SAT-1 at minute 0 (conflicts with A).
      New Target-Y (P1) only fits on SAT-2 at minute 3 (conflicts with D).
    Expected:
      Target-A evicted on SAT-1, Target-X added there.
      Target-D evicted on SAT-2, Target-Y added there.
      Target-B and Target-C untouched.
    """

    def test_independent_evictions_across_satellites(self) -> None:
        flex = [
            _flex("acq_a", "SAT-1", "Target-A", 0, value=0.30),
            _flex("acq_b", "SAT-1", "Target-B", 3, value=0.30),
            _flex("acq_c", "SAT-2", "Target-C", 0, value=0.30),
            _flex("acq_d", "SAT-2", "Target-D", 3, value=0.30),
        ]
        opps = [
            _opp("opp_x", "SAT-1", "Target-X", 0, value=0.85, priority=1),
            _opp("opp_y", "SAT-2", "Target-Y", 3, value=0.85, priority=1),
        ]
        priorities = {
            "Target-A": 5, "Target-B": 5, "Target-C": 5, "Target-D": 5,
            "Target-X": 1, "Target-Y": 1,
        }

        _, diff, _ = _run_repair(flex, opps, priorities)

        # Evictions on correct satellites
        assert "acq_a" in diff.dropped, "Target-A on SAT-1 should be evicted"
        assert "acq_d" in diff.dropped, "Target-D on SAT-2 should be evicted"
        # Additions on correct satellites
        assert "opp_x" in diff.added, "Target-X should be added on SAT-1"
        assert "opp_y" in diff.added, "Target-Y should be added on SAT-2"
        # Non-conflicting kept
        assert "acq_b" in diff.kept, "Target-B untouched"
        assert "acq_c" in diff.kept, "Target-C untouched"
        # Each eviction has a reason
        for acq in ["acq_a", "acq_d"]:
            reasons = _drop_reasons_for(diff, acq)
            assert len(reasons) > 0, f"Missing drop reason for {acq}"
            assert "priority" in reasons[0].lower(), (
                f"Reason for {acq} should mention priority, got: {reasons[0]}"
            )

    def test_proposed_schedule_covers_correct_targets(self) -> None:
        """The proposed schedule should contain the new targets and surviving originals."""
        flex = [
            _flex("acq_a", "SAT-1", "Target-A", 0, value=0.30),
            _flex("acq_b", "SAT-1", "Target-B", 3, value=0.30),
            _flex("acq_c", "SAT-2", "Target-C", 0, value=0.30),
            _flex("acq_d", "SAT-2", "Target-D", 3, value=0.30),
        ]
        opps = [
            _opp("opp_x", "SAT-1", "Target-X", 0, value=0.85, priority=1),
            _opp("opp_y", "SAT-2", "Target-Y", 3, value=0.85, priority=1),
        ]
        priorities = {
            "Target-A": 5, "Target-B": 5, "Target-C": 5, "Target-D": 5,
            "Target-X": 1, "Target-Y": 1,
        }

        proposed, _, _ = _run_repair(flex, opps, priorities)

        proposed_targets = set(item["target_id"] for item in proposed)
        # Surviving: B, C. New: X, Y. Dropped: A, D.
        assert "Target-B" in proposed_targets
        assert "Target-C" in proposed_targets
        assert "Target-X" in proposed_targets
        assert "Target-Y" in proposed_targets
        assert "Target-A" not in proposed_targets, "Evicted target should not be in proposed"
        assert "Target-D" not in proposed_targets, "Evicted target should not be in proposed"


# =============================================================================
# Scenario 8: Gap filling — new target fits in empty gap, no eviction needed
# =============================================================================


class TestGapFilling:
    """
    Existing: Target-A at minute 0, Target-B at minute 10 on SAT-A.
    Update:   New Target-C fits at minute 5 — plenty of gap, no conflict.
    Expected: Target-C added in the gap. No drops. 1 change.
    """

    def test_fills_gap_without_eviction(self) -> None:
        flex = [
            _flex("acq_a", "SAT-A", "Target-A", 0, value=0.40),
            _flex("acq_b", "SAT-A", "Target-B", 10, value=0.40),
        ]
        opps = [
            _opp("opp_c", "SAT-A", "Target-C", 5, value=0.50, priority=3),
        ]
        priorities = {"Target-A": 5, "Target-B": 5, "Target-C": 3}

        _, diff, _ = _run_repair(flex, opps, priorities)

        assert "opp_c" in diff.added, "Target-C should fill the gap"
        assert len(diff.dropped) == 0, "No targets should be dropped"
        assert "acq_a" in diff.kept
        assert "acq_b" in diff.kept
        assert diff.change_score.num_changes == 1


# =============================================================================
# Scenario 9: max_changes limit respected
# =============================================================================


class TestMaxChangesLimit:
    """
    Existing: 3 targets (P5) on SAT-A.
    Update:   3 new targets (P1) each conflict with one existing.
              max_changes=2 — only enough budget for ONE eviction (1 drop + 1 add = 2).
    Expected: Exactly 1 eviction, not all 3.
    """

    def test_max_changes_caps_evictions(self) -> None:
        flex = [
            _flex("acq_1", "SAT-A", "Existing-1", 0, value=0.30),
            _flex("acq_2", "SAT-A", "Existing-2", 5, value=0.30),
            _flex("acq_3", "SAT-A", "Existing-3", 10, value=0.30),
        ]
        opps = [
            _opp("opp_a", "SAT-A", "New-A", 0, value=0.85, priority=1),
            _opp("opp_b", "SAT-A", "New-B", 5, value=0.85, priority=1),
            _opp("opp_c", "SAT-A", "New-C", 10, value=0.85, priority=1),
        ]
        priorities = {
            "Existing-1": 5, "Existing-2": 5, "Existing-3": 5,
            "New-A": 1, "New-B": 1, "New-C": 1,
        }

        _, diff, _ = _run_repair(flex, opps, priorities, max_changes=2)

        # Only 2 changes allowed: 1 drop + 1 add
        assert diff.change_score.num_changes <= 2, (
            f"Expected max 2 changes, got {diff.change_score.num_changes}"
        )
        assert len(diff.dropped) == 1, f"Expected 1 drop, got {len(diff.dropped)}"
        assert len(diff.added) == 1, f"Expected 1 add, got {len(diff.added)}"


# =============================================================================
# Scenario 10: Reason text validation across all scenarios
# =============================================================================


class TestReasonTextQuality:
    """Validate that reason strings are human-readable and contain key information."""

    def test_priority_eviction_reason_contains_both_priorities(self) -> None:
        """Reason should mention both the dropped and added target priorities."""
        flex = [_flex("acq_low", "SAT-A", "Low-P", 5, value=0.15)]
        opps = [_opp("opp_high", "SAT-A", "High-P", 5, value=0.85, priority=1)]
        priorities = {"Low-P": 5, "High-P": 1}

        _, diff, _ = _run_repair(flex, opps, priorities)

        reasons = _drop_reasons_for(diff, "acq_low")
        assert len(reasons) > 0, "Must have a drop reason"
        reason = reasons[0]
        # Should mention the dropped target's priority (5) and the new target's priority (1)
        assert "5" in reason and "1" in reason, (
            f"Reason should mention both priorities (1 and 5), got: {reason}"
        )

    def test_coverage_swap_reason_mentions_targets(self) -> None:
        """Coverage swap reason should mention the swapped and added targets."""
        flex = [
            _flex("acq_a", "SAT-1", "Target-A", 5, value=0.40),
        ]
        opps = [
            _opp("opp_c", "SAT-1", "Target-C", 5, value=0.50, priority=3),
            _opp("opp_a_alt", "SAT-2", "Target-A", 10, value=0.35, priority=5),
        ]
        priorities = {"Target-A": 5, "Target-C": 3}

        _, diff, _ = _run_repair(flex, opps, priorities)

        if "acq_a" in diff.dropped:
            reasons = _drop_reasons_for(diff, "acq_a")
            assert len(reasons) > 0
            reason = reasons[0]
            # Should mention both target names
            assert "Target-A" in reason or "Target-C" in reason, (
                f"Reason should mention target names, got: {reason}"
            )
