"""
Tests proving the coverage swap fix for the greedy scheduling bug.

Bug: _roll_pitch_best_fit greedily assigns targets to satellites in value order.
When a target (e.g., Bandar Abbas) is assigned to satellite X55, it blocks another
target (e.g., Manama) that can ONLY fit on X55. The greedy algorithm never backtracks.

Fix: Added a coverage improvement pass that detects uncovered targets and tries
cross-satellite swaps — moving a blocker to a different satellite to free the slot.

These tests simulate the exact Gulf targets scenario reported by the user:
- 10 targets, 3 satellites (X55, X57, X65)
- Without fix: 9/10 (Manama missed)
- With fix: 10/10 (Bandar Abbas moved from X55 to X57, Manama gets X55)
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import pytest

from mission_planner.scheduler import (
    AlgorithmType,
    MissionScheduler,
    Opportunity,
    SchedulerConfig,
)

# =============================================================================
# Helpers
# =============================================================================


def _make_opp(
    target: str,
    satellite: str,
    minute_offset: float,
    incidence_deg: float = 15.0,
    pitch_deg: float = 0.0,
    value: float = 0.5,
    base_time: datetime = datetime(2026, 2, 23, 13, 0, 0),
) -> Opportunity:
    """Create a test opportunity with realistic parameters."""
    start = base_time + timedelta(minutes=minute_offset)
    end = start + timedelta(seconds=10)
    return Opportunity(
        id=f"opp_{target}_{satellite}_{int(minute_offset)}",
        satellite_id=satellite,
        target_id=target,
        start_time=start,
        end_time=end,
        incidence_angle=incidence_deg,
        pitch_angle=pitch_deg,
        value=value,
    )


def _build_gulf_scenario() -> Tuple[List[Opportunity], Dict[str, Tuple[float, float]]]:
    """
    Build a scenario that triggers the greedy blocking bug.

    Key constraint: Manama and Bandar Abbas BOTH need ICEYE-X55 at the SAME time slot.
    Only one can fit. Bandar Abbas also has an opportunity on ICEYE-X57 (alternative).
    Manama has NO alternative — X55 is its only option.

    The greedy algorithm sorts by (pitch, -value). Bandar Abbas has higher value (0.60)
    than Manama (0.50), so it gets assigned to X55 first, blocking Manama.

    The coverage improvement pass should detect Manama is uncovered, find that Bandar
    Abbas blocks it on X55, and swap Bandar Abbas to its X57 alternative.
    """
    base_x65 = datetime(2026, 2, 23, 13, 40, 0)  # X65 pass over Gulf
    base_x57 = datetime(2026, 2, 24, 9, 20, 0)  # X57 pass
    base_x55 = datetime(2026, 2, 24, 9, 44, 0)  # X55 pass

    target_positions = {
        "Jeddah": (21.4858, 39.1925),
        "Riyadh": (24.7136, 46.6753),
        "Kuwait City": (29.3759, 47.9774),
        "Muscat": (23.5880, 58.3829),
        "Bandar Abbas": (27.1865, 56.2808),
        "Abu Dhabi": (24.4539, 54.3773),
        "Doha": (25.2854, 51.5310),
        "Salalah": (17.0151, 54.0924),
        "Dubai": (25.2048, 55.2708),
        "Manama": (26.2285, 50.5860),
    }

    opportunities = [
        # ── ICEYE-X65 pass (13:42-13:45 UTC) ──
        _make_opp(
            "Jeddah", "X65", 0, incidence_deg=12.0, value=0.55, base_time=base_x65
        ),
        _make_opp(
            "Riyadh", "X65", 2, incidence_deg=18.0, value=0.50, base_time=base_x65
        ),
        _make_opp(
            "Kuwait City", "X65", 3, incidence_deg=20.0, value=0.48, base_time=base_x65
        ),
        # ── ICEYE-X57 pass (09:20-09:22 UTC) ──
        _make_opp(
            "Muscat", "X57", 0, incidence_deg=15.0, value=0.52, base_time=base_x57
        ),
        # Bandar Abbas on X57 — the ALTERNATIVE that the swap should use
        _make_opp(
            "Bandar Abbas", "X57", 1, incidence_deg=22.0, value=0.42, base_time=base_x57
        ),
        # ── ICEYE-X55 pass (09:44-09:49 UTC) ──
        # CRITICAL: Bandar Abbas and Manama at the SAME time on X55 (only 2s apart)
        # With imaging_time_s=1.0 and MIN_GAP_SECONDS, they conflict.
        # Bandar Abbas has HIGHER value (0.60 > 0.50), so greedy picks it first.
        _make_opp(
            "Bandar Abbas", "X55", 0, incidence_deg=14.0, value=0.60, base_time=base_x55
        ),
        # Manama 2 seconds later — too close, conflicts with Bandar Abbas!
        # incidence_angle diff = |16 - 14| = 2°, roll_time = 2/1 = 2s, but gap is only 2s
        # and MIN_GAP_SECONDS = 5, so min_gap = max(5, 2) = 5 > 2 → CONFLICT
        _make_opp(
            "Manama", "X55", 0.033, incidence_deg=16.0, value=0.50, base_time=base_x55
        ),
        _make_opp(
            "Abu Dhabi", "X55", 2, incidence_deg=10.0, value=0.52, base_time=base_x55
        ),
        _make_opp("Doha", "X55", 3, incidence_deg=12.0, value=0.51, base_time=base_x55),
        _make_opp(
            "Salalah", "X55", 4, incidence_deg=25.0, value=0.45, base_time=base_x55
        ),
        # ── ICEYE-X65 second pass (11:53 UTC) ──
        _make_opp(
            "Dubai",
            "X65",
            0,
            incidence_deg=18.0,
            value=0.50,
            base_time=datetime(2026, 2, 24, 11, 53, 0),
        ),
    ]

    return opportunities, target_positions


# =============================================================================
# Test: from_scratch scheduling — coverage swap fix
# =============================================================================


class TestCoverageSwapFix:
    """Prove that _roll_pitch_best_fit now achieves 10/10 coverage."""

    def _make_scheduler(self) -> MissionScheduler:
        config = SchedulerConfig(
            imaging_time_s=1.0,
            max_roll_rate_dps=1.0,
            max_roll_accel_dps2=10000.0,
            max_pitch_rate_dps=1.0,
            max_pitch_accel_dps2=10000.0,
            max_spacecraft_roll_deg=45.0,
            max_spacecraft_pitch_deg=45.0,
            look_window_s=600.0,
        )
        return MissionScheduler(config)

    def test_all_10_targets_scheduled(self) -> None:
        """The main bug scenario: all 10 Gulf targets must be scheduled."""
        opportunities, target_positions = _build_gulf_scenario()
        scheduler = self._make_scheduler()

        schedule, metrics = scheduler.schedule(
            opportunities, target_positions, AlgorithmType.ROLL_PITCH_BEST_FIT
        )

        scheduled_targets = set(s.target_id for s in schedule)
        all_targets = set(t for t in target_positions.keys())

        assert len(scheduled_targets) == 10, (
            f"Expected 10/10 targets scheduled, got {len(scheduled_targets)}/10. "
            f"Missing: {all_targets - scheduled_targets}"
        )
        assert (
            "Manama" in scheduled_targets
        ), "Manama must be scheduled (was the bug target)"
        assert "Bandar Abbas" in scheduled_targets, "Bandar Abbas must still be covered"

    def test_manama_on_x55_bandar_on_x57(self) -> None:
        """Bandar Abbas should be moved from X55 to X57 to free slot for Manama."""
        opportunities, target_positions = _build_gulf_scenario()
        scheduler = self._make_scheduler()

        schedule, _ = scheduler.schedule(
            opportunities, target_positions, AlgorithmType.ROLL_PITCH_BEST_FIT
        )

        scheduled_map = {s.target_id: s for s in schedule}

        # Both must be covered
        assert "Manama" in scheduled_map, "Manama must be scheduled"
        assert "Bandar Abbas" in scheduled_map, "Bandar Abbas must be scheduled"

        # If both are covered and Manama only has X55 opportunities,
        # then Manama must be on X55 and Bandar Abbas must have moved to X57
        assert (
            scheduled_map["Manama"].satellite_id == "X55"
        ), f"Manama should be on X55 (its only option), got {scheduled_map['Manama'].satellite_id}"
        assert (
            scheduled_map["Bandar Abbas"].satellite_id == "X57"
        ), f"Bandar Abbas should be swapped to X57, got {scheduled_map['Bandar Abbas'].satellite_id}"

    def test_no_duplicate_targets(self) -> None:
        """Each target must appear exactly once in the schedule."""
        opportunities, target_positions = _build_gulf_scenario()
        scheduler = self._make_scheduler()

        schedule, _ = scheduler.schedule(
            opportunities, target_positions, AlgorithmType.ROLL_PITCH_BEST_FIT
        )

        target_counts = {}
        for s in schedule:
            target_counts[s.target_id] = target_counts.get(s.target_id, 0) + 1

        for target, count in target_counts.items():
            assert count == 1, f"Target {target} scheduled {count} times (expected 1)"

    def test_no_satellite_time_conflicts(self) -> None:
        """No two acquisitions on the same satellite should overlap in time."""
        opportunities, target_positions = _build_gulf_scenario()
        scheduler = self._make_scheduler()

        schedule, _ = scheduler.schedule(
            opportunities, target_positions, AlgorithmType.ROLL_PITCH_BEST_FIT
        )

        # Group by satellite
        by_sat = {}
        for s in schedule:
            by_sat.setdefault(s.satellite_id, []).append(s)

        for sat_id, items in by_sat.items():
            items.sort(key=lambda x: x.start_time)
            for i in range(1, len(items)):
                prev = items[i - 1]
                curr = items[i]
                assert curr.start_time >= prev.end_time, (
                    f"Time conflict on {sat_id}: "
                    f"{prev.target_id} ends {prev.end_time}, "
                    f"{curr.target_id} starts {curr.start_time}"
                )


# =============================================================================
# Test: Repair planning — priority-driven eviction
# =============================================================================


class TestRepairPriorityEviction:
    """Prove that the repair planner respects updated target priorities."""

    def test_priority_eviction_drops_low_for_high(self) -> None:
        """
        Stage F: uncovered high-priority target evicts a covered low-priority one.

        Scenario: 9 targets scheduled (all priority 5), Manama unscheduled.
        User sets Manama to priority 1. Repair should evict a P5 target to add Manama.
        """
        from backend.incremental_planning import (
            BlockedInterval,
            FlexibleAcquisition,
            IncrementalPlanningContext,
            PlanningMode,
            RepairObjective,
            RepairPlanningContext,
            SlewConfig,
            execute_repair_planning,
        )

        base_time = datetime(2026, 2, 24, 9, 44, 0)

        # Existing schedule: Salalah on X55 at 09:48 (priority 5, low value)
        flex_set = [
            FlexibleAcquisition(
                acquisition_id="acq_salalah",
                satellite_id="X55",
                target_id="Salalah",
                original_start=base_time + timedelta(minutes=4),
                original_end=base_time + timedelta(minutes=4, seconds=1),
                roll_angle_deg=25.0,
                value=0.15,  # Low value (priority 5)
                lock_level="none",
            ),
        ]

        repair_ctx = RepairPlanningContext(
            mode=PlanningMode.REPAIR,
            objective=RepairObjective.MAXIMIZE_SCORE,
            flex_set=flex_set,
            fixed_set=[],
            original_acquisition_count=1,
        )

        # Manama opportunity on X55 at 09:48 — conflicts with Salalah's slot
        # (same satellite, close in time)
        manama_opp = {
            "id": "opp_manama_x55",
            "opportunity_id": "opp_manama_x55",
            "satellite_id": "X55",
            "target_id": "Manama",
            "start_time": (base_time + timedelta(minutes=4)).isoformat(),
            "end_time": (base_time + timedelta(minutes=4, seconds=1)).isoformat(),
            "roll_angle_deg": 16.0,
            "pitch_angle_deg": 0.0,
            "value": 0.85,  # High value (re-scored with priority 1)
            "quality_score": 0.5,
            "priority": 1,
        }

        target_priorities = {
            "Manama": 1,  # User set to max priority
            "Salalah": 5,  # Default low priority
        }

        slew_config = SlewConfig(
            roll_slew_rate_deg_per_sec=1.0,
            pitch_slew_rate_deg_per_sec=1.0,
        )

        proposed, diff, metrics = execute_repair_planning(
            repair_context=repair_ctx,
            opportunities=[manama_opp],
            max_changes=100,
            objective=RepairObjective.MAXIMIZE_SCORE,
            slew_config=slew_config,
            target_priorities=target_priorities,
        )

        # Manama should be added, Salalah should be dropped
        assert (
            diff.change_score.num_changes > 0
        ), "Expected changes but got 0 — priority eviction did not trigger"
        assert (
            "acq_salalah" in diff.dropped
        ), f"Expected Salalah to be dropped, dropped: {diff.dropped}"
        assert any(
            "manama" in aid.lower() or "Manama" in aid for aid in diff.added
        ), f"Expected Manama to be added, added: {diff.added}"

    def test_no_eviction_when_same_priority(self) -> None:
        """Stage F should NOT evict when priorities are equal (both P5)."""
        from backend.incremental_planning import (
            FlexibleAcquisition,
            PlanningMode,
            RepairObjective,
            RepairPlanningContext,
            SlewConfig,
            execute_repair_planning,
        )

        base_time = datetime(2026, 2, 24, 9, 44, 0)

        flex_set = [
            FlexibleAcquisition(
                acquisition_id="acq_salalah",
                satellite_id="X55",
                target_id="Salalah",
                original_start=base_time + timedelta(minutes=4),
                original_end=base_time + timedelta(minutes=4, seconds=1),
                roll_angle_deg=25.0,
                value=0.15,
                lock_level="none",
            ),
        ]

        repair_ctx = RepairPlanningContext(
            mode=PlanningMode.REPAIR,
            objective=RepairObjective.MAXIMIZE_SCORE,
            flex_set=flex_set,
            fixed_set=[],
            original_acquisition_count=1,
        )

        manama_opp = {
            "id": "opp_manama_x55",
            "opportunity_id": "opp_manama_x55",
            "satellite_id": "X55",
            "target_id": "Manama",
            "start_time": (base_time + timedelta(minutes=4)).isoformat(),
            "end_time": (base_time + timedelta(minutes=4, seconds=1)).isoformat(),
            "roll_angle_deg": 16.0,
            "pitch_angle_deg": 0.0,
            "value": 0.15,
            "quality_score": 0.5,
            "priority": 5,
        }

        # Both targets same priority — should NOT evict
        target_priorities = {
            "Manama": 5,
            "Salalah": 5,
        }

        slew_config = SlewConfig(
            roll_slew_rate_deg_per_sec=1.0,
            pitch_slew_rate_deg_per_sec=1.0,
        )

        proposed, diff, metrics = execute_repair_planning(
            repair_context=repair_ctx,
            opportunities=[manama_opp],
            max_changes=100,
            objective=RepairObjective.MAXIMIZE_SCORE,
            slew_config=slew_config,
            target_priorities=target_priorities,
        )

        # No eviction should happen — same priority
        assert (
            "acq_salalah" not in diff.dropped
        ), "Should NOT evict when priorities are equal"


# =============================================================================
# Test: Re-scoring of cached opportunities
# =============================================================================


class TestOpportunityRescoring:
    """Prove that compute_composite_value correctly re-scores with new priorities."""

    def test_priority_1_scores_higher_than_priority_5(self) -> None:
        """A target with priority 1 should have much higher composite value."""
        from mission_planner.quality_scoring import (
            MultiCriteriaWeights,
            compute_composite_value,
        )

        weights = MultiCriteriaWeights(priority=40, geometry=40, timing=20)

        value_p1 = compute_composite_value(
            priority=1.0, quality_score=0.5, timing_score=0.5, weights=weights
        )
        value_p5 = compute_composite_value(
            priority=5.0, quality_score=0.5, timing_score=0.5, weights=weights
        )

        assert (
            value_p1 > value_p5
        ), f"Priority 1 value ({value_p1:.4f}) should be > priority 5 ({value_p5:.4f})"
        assert (
            value_p1 - value_p5 >= 0.3
        ), f"Expected significant delta, got {value_p1 - value_p5:.4f}"

    def test_priority_preset_weights_amplify_difference(self) -> None:
        """The 'Priority' preset (70/20/10) should amplify the priority difference."""
        from mission_planner.quality_scoring import (
            MultiCriteriaWeights,
            compute_composite_value,
        )

        balanced = MultiCriteriaWeights(priority=40, geometry=40, timing=20)
        priority_heavy = MultiCriteriaWeights(priority=70, geometry=20, timing=10)

        delta_balanced = compute_composite_value(
            1.0, 0.5, 0.5, balanced
        ) - compute_composite_value(5.0, 0.5, 0.5, balanced)
        delta_priority = compute_composite_value(
            1.0, 0.5, 0.5, priority_heavy
        ) - compute_composite_value(5.0, 0.5, 0.5, priority_heavy)

        assert delta_priority > delta_balanced, (
            f"Priority preset delta ({delta_priority:.4f}) should be > "
            f"balanced delta ({delta_balanced:.4f})"
        )
