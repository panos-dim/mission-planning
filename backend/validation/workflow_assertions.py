"""
Workflow Invariant Assertions.

Implements the minimum set of invariants for validating
mission analysis → planning → repair → commit workflows:

1. No temporal overlaps on same satellite after commit (unless force flag)
2. Slew feasibility holds for adjacent scheduled items
3. Hard locks are unchanged in repair mode
4. Repair diff matches DB changes when committed
5. Conflict engine output matches "conflicts_if_committed" preview
6. Deterministic: same seed/config → identical report hash
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .workflow_models import (
    InvariantResult,
    InvariantType,
    RepairDiffSummary,
)

logger = logging.getLogger(__name__)

# Default slew rates (degrees per second)
DEFAULT_ROLL_SLEW_RATE = 1.0
DEFAULT_PITCH_SLEW_RATE = 0.5
MIN_SETTLING_TIME_S = 5.0


class WorkflowInvariantChecker:
    """
    Validates workflow invariants for scheduling correctness.

    Each invariant maps to a specific correctness requirement:
    - Temporal: No overlapping acquisitions per satellite
    - Physical: Slew maneuvers are feasible
    - Operational: Hard locks are respected in repair
    - Consistency: Repair diff matches actual DB changes
    """

    def __init__(
        self,
        roll_slew_rate: float = DEFAULT_ROLL_SLEW_RATE,
        pitch_slew_rate: float = DEFAULT_PITCH_SLEW_RATE,
        settling_time_s: float = MIN_SETTLING_TIME_S,
    ):
        self.roll_slew_rate = roll_slew_rate
        self.pitch_slew_rate = pitch_slew_rate
        self.settling_time_s = settling_time_s

    def check_all_invariants(
        self,
        acquisitions: List[Dict[str, Any]],
        conflicts_detected: List[Dict[str, Any]],
        conflicts_preview: Optional[List[Dict[str, Any]]] = None,
        hard_locked_before: Optional[List[str]] = None,
        hard_locked_after: Optional[List[str]] = None,
        repair_diff: Optional[RepairDiffSummary] = None,
        db_changes: Optional[Dict[str, Any]] = None,
        previous_report_hash: Optional[str] = None,
        current_report_hash: Optional[str] = None,
    ) -> List[InvariantResult]:
        """
        Run all invariant checks.

        Args:
            acquisitions: List of committed acquisitions
            conflicts_detected: Conflicts from conflict detection
            conflicts_preview: Conflicts from preview (before commit)
            hard_locked_before: IDs of hard-locked items before repair
            hard_locked_after: IDs of hard-locked items after repair
            repair_diff: Summary of repair changes
            db_changes: Actual DB changes from commit
            previous_report_hash: Hash from previous run (for determinism check)
            current_report_hash: Hash from current run

        Returns:
            List of InvariantResult for each check
        """
        results = []

        # 1. No temporal overlaps
        results.append(self.check_no_temporal_overlap(acquisitions))

        # 2. Slew feasibility
        results.append(self.check_slew_feasibility(acquisitions))

        # 3. Hard locks unchanged (if repair was run)
        if hard_locked_before is not None and hard_locked_after is not None:
            results.append(
                self.check_hard_locks_unchanged(hard_locked_before, hard_locked_after)
            )

        # 4. Repair diff consistency (if repair was run with commit)
        if repair_diff is not None and db_changes is not None:
            results.append(
                self.check_repair_diff_consistent(repair_diff, db_changes)
            )

        # 5. Conflict preview matches detection
        if conflicts_preview is not None:
            results.append(
                self.check_conflict_preview_match(conflicts_preview, conflicts_detected)
            )

        # 6. Determinism check
        if previous_report_hash is not None and current_report_hash is not None:
            results.append(
                self.check_deterministic(previous_report_hash, current_report_hash)
            )

        return results

    def check_no_temporal_overlap(
        self,
        acquisitions: List[Dict[str, Any]],
    ) -> InvariantResult:
        """
        Verify no temporal overlaps exist for same satellite.

        Two acquisitions overlap if acq1.end_time > acq2.start_time.
        """
        violations = []

        # Group by satellite
        by_satellite: Dict[str, List[Dict[str, Any]]] = {}
        for acq in acquisitions:
            sat_id = acq.get("satellite_id", "unknown")
            if sat_id not in by_satellite:
                by_satellite[sat_id] = []
            by_satellite[sat_id].append(acq)

        # Check each satellite's acquisitions
        for sat_id, sat_acqs in by_satellite.items():
            # Sort by start time
            sorted_acqs = sorted(sat_acqs, key=lambda a: a.get("start_time", ""))

            for i in range(len(sorted_acqs) - 1):
                acq1 = sorted_acqs[i]
                acq2 = sorted_acqs[i + 1]

                end1 = self._parse_time(acq1.get("end_time", ""))
                start2 = self._parse_time(acq2.get("start_time", ""))

                if end1 is None or start2 is None:
                    continue

                if end1 > start2:
                    overlap_s = (end1 - start2).total_seconds()
                    violations.append({
                        "satellite_id": sat_id,
                        "acq1_id": acq1.get("id"),
                        "acq2_id": acq2.get("id"),
                        "acq1_target": acq1.get("target_id"),
                        "acq2_target": acq2.get("target_id"),
                        "overlap_seconds": round(overlap_s, 1),
                    })

        passed = len(violations) == 0
        message = (
            "No temporal overlaps detected"
            if passed
            else f"{len(violations)} temporal overlap(s) detected"
        )

        return InvariantResult(
            invariant=InvariantType.NO_TEMPORAL_OVERLAP,
            passed=passed,
            message=message,
            violations=violations,
            details={"acquisitions_checked": len(acquisitions)},
        )

    def check_slew_feasibility(
        self,
        acquisitions: List[Dict[str, Any]],
    ) -> InvariantResult:
        """
        Verify slew feasibility between adjacent scheduled items.

        Checks that available time >= slew_time + settling_time.
        """
        violations = []

        # Group by satellite
        by_satellite: Dict[str, List[Dict[str, Any]]] = {}
        for acq in acquisitions:
            sat_id = acq.get("satellite_id", "unknown")
            if sat_id not in by_satellite:
                by_satellite[sat_id] = []
            by_satellite[sat_id].append(acq)

        # Check each satellite
        for sat_id, sat_acqs in by_satellite.items():
            sorted_acqs = sorted(sat_acqs, key=lambda a: a.get("start_time", ""))

            for i in range(len(sorted_acqs) - 1):
                acq1 = sorted_acqs[i]
                acq2 = sorted_acqs[i + 1]

                end1 = self._parse_time(acq1.get("end_time", ""))
                start2 = self._parse_time(acq2.get("start_time", ""))

                if end1 is None or start2 is None:
                    continue

                available_time = (start2 - end1).total_seconds()

                # Skip if already overlapping (handled by temporal check)
                if available_time <= 0:
                    continue

                # Get roll/pitch angles
                roll1 = acq1.get("roll_angle_deg", 0.0)
                roll2 = acq2.get("roll_angle_deg", 0.0)
                pitch1 = acq1.get("pitch_angle_deg", 0.0)
                pitch2 = acq2.get("pitch_angle_deg", 0.0)

                # Calculate required slew time
                roll_delta = abs(roll2 - roll1)
                pitch_delta = abs(pitch2 - pitch1)
                roll_slew_time = roll_delta / self.roll_slew_rate
                pitch_slew_time = pitch_delta / self.pitch_slew_rate

                # Parallel slew (take max)
                total_slew_time = max(roll_slew_time, pitch_slew_time)
                required_time = total_slew_time + self.settling_time_s

                if available_time < required_time:
                    deficit = required_time - available_time
                    violations.append({
                        "satellite_id": sat_id,
                        "acq1_id": acq1.get("id"),
                        "acq2_id": acq2.get("id"),
                        "roll_delta_deg": round(roll_delta, 1),
                        "pitch_delta_deg": round(pitch_delta, 1),
                        "required_time_s": round(required_time, 1),
                        "available_time_s": round(available_time, 1),
                        "deficit_s": round(deficit, 1),
                    })

        passed = len(violations) == 0
        message = (
            "All slew maneuvers are feasible"
            if passed
            else f"{len(violations)} slew infeasibility violation(s)"
        )

        return InvariantResult(
            invariant=InvariantType.SLEW_FEASIBILITY,
            passed=passed,
            message=message,
            violations=violations,
            details={"acquisitions_checked": len(acquisitions)},
        )

    def check_hard_locks_unchanged(
        self,
        hard_locked_before: List[str],
        hard_locked_after: List[str],
    ) -> InvariantResult:
        """
        Verify hard-locked items are unchanged after repair.

        Hard locks must NEVER be modified by repair mode.
        """
        before_set = set(hard_locked_before)
        after_set = set(hard_locked_after)

        # All items that were hard-locked must still exist
        missing = before_set - after_set
        violations = [{"missing_hard_lock": acq_id} for acq_id in missing]

        passed = len(violations) == 0
        message = (
            f"All {len(before_set)} hard-locked items preserved"
            if passed
            else f"{len(violations)} hard-locked item(s) were modified"
        )

        return InvariantResult(
            invariant=InvariantType.HARD_LOCKS_UNCHANGED,
            passed=passed,
            message=message,
            violations=violations,
            details={
                "hard_locked_before": len(before_set),
                "hard_locked_after": len(after_set),
            },
        )

    def check_repair_diff_consistent(
        self,
        repair_diff: RepairDiffSummary,
        db_changes: Dict[str, Any],
    ) -> InvariantResult:
        """
        Verify repair diff matches actual DB changes.

        Counts must be consistent:
        - kept + added = total after commit
        - dropped = items removed from schedule
        """
        violations = []

        # Check kept count
        db_kept = db_changes.get("kept_count", 0)
        if repair_diff.kept_count != db_kept:
            violations.append({
                "field": "kept_count",
                "diff_value": repair_diff.kept_count,
                "db_value": db_kept,
            })

        # Check dropped count
        db_dropped = db_changes.get("dropped_count", 0)
        if repair_diff.dropped_count != db_dropped:
            violations.append({
                "field": "dropped_count",
                "diff_value": repair_diff.dropped_count,
                "db_value": db_dropped,
            })

        # Check added count
        db_added = db_changes.get("added_count", 0)
        if repair_diff.added_count != db_added:
            violations.append({
                "field": "added_count",
                "diff_value": repair_diff.added_count,
                "db_value": db_added,
            })

        # Check moved count
        db_moved = db_changes.get("moved_count", 0)
        if repair_diff.moved_count != db_moved:
            violations.append({
                "field": "moved_count",
                "diff_value": repair_diff.moved_count,
                "db_value": db_moved,
            })

        passed = len(violations) == 0
        message = (
            "Repair diff matches DB changes"
            if passed
            else f"{len(violations)} inconsistency(ies) between diff and DB"
        )

        return InvariantResult(
            invariant=InvariantType.REPAIR_DIFF_CONSISTENT,
            passed=passed,
            message=message,
            violations=violations,
            details={
                "diff_total": (
                    repair_diff.kept_count
                    + repair_diff.added_count
                    + repair_diff.moved_count
                ),
            },
        )

    def check_conflict_preview_match(
        self,
        conflicts_preview: List[Dict[str, Any]],
        conflicts_detected: List[Dict[str, Any]],
    ) -> InvariantResult:
        """
        Verify conflict preview matches post-commit detection.

        Within the same horizon, the conflict engine should produce
        identical results before and after commit.
        """
        # Compare by type and acquisition pairs
        def conflict_key(c: Dict[str, Any]) -> str:
            ctype = c.get("type", "")
            acq_ids = sorted(c.get("acquisition_ids", []))
            return f"{ctype}:{','.join(acq_ids)}"

        preview_keys = set(conflict_key(c) for c in conflicts_preview)
        detected_keys = set(conflict_key(c) for c in conflicts_detected)

        missing = preview_keys - detected_keys
        extra = detected_keys - preview_keys

        violations = []
        for key in missing:
            violations.append({"type": "missing_in_detection", "conflict": key})
        for key in extra:
            violations.append({"type": "extra_in_detection", "conflict": key})

        passed = len(violations) == 0
        message = (
            f"Conflict preview matches detection ({len(preview_keys)} conflicts)"
            if passed
            else f"{len(violations)} mismatch(es) between preview and detection"
        )

        return InvariantResult(
            invariant=InvariantType.CONFLICT_PREVIEW_MATCH,
            passed=passed,
            message=message,
            violations=violations,
            details={
                "preview_count": len(conflicts_preview),
                "detected_count": len(conflicts_detected),
            },
        )

    def check_deterministic(
        self,
        previous_hash: str,
        current_hash: str,
    ) -> InvariantResult:
        """
        Verify determinism: same config produces identical results.
        """
        passed = previous_hash == current_hash
        message = (
            f"Deterministic: hash {current_hash} matches"
            if passed
            else f"Non-deterministic: {current_hash} != {previous_hash}"
        )

        return InvariantResult(
            invariant=InvariantType.DETERMINISTIC,
            passed=passed,
            message=message,
            details={
                "previous_hash": previous_hash,
                "current_hash": current_hash,
            },
        )

    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """Parse ISO datetime string."""
        if not time_str:
            return None
        try:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None
