"""
Conflict Detection Engine for Mission Planning.

Detects scheduling conflicts within a workspace + time horizon:
- temporal_overlap: Two acquisitions for the same satellite overlap in time
- slew_infeasible: Insufficient time to slew between consecutive acquisitions (roll + pitch)

This module computes conflicts but does NOT reshuffle - that's for a future PR.
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.schedule_persistence import Acquisition, Conflict, ScheduleDB

logger = logging.getLogger(__name__)

# Default slew rates (degrees per second) for roll and pitch maneuvers
DEFAULT_ROLL_SLEW_RATE_DEG_PER_SEC = 1.0
DEFAULT_PITCH_SLEW_RATE_DEG_PER_SEC = 1.0

# Minimum settling time after slew (seconds)
MIN_SETTLING_TIME_S = 5.0


@dataclass
class ConflictDetectionConfig:
    """Configuration for conflict detection."""

    roll_slew_rate_deg_per_sec: float = DEFAULT_ROLL_SLEW_RATE_DEG_PER_SEC
    pitch_slew_rate_deg_per_sec: float = DEFAULT_PITCH_SLEW_RATE_DEG_PER_SEC
    settling_time_s: float = MIN_SETTLING_TIME_S
    overlap_threshold_s: float = 0.0  # Minimum overlap to flag (0 = any overlap)
    # If True, roll and pitch slews happen in parallel (max of both times)
    # If False, they happen sequentially (sum of both times)
    parallel_slew: bool = True


@dataclass
class DetectedConflict:
    """A detected conflict before persistence."""

    type: str  # temporal_overlap | slew_infeasible
    severity: str  # error | warning | info
    description: str
    acquisition_ids: List[str]
    details: Dict[str, Any]


class ConflictDetector:
    """
    Conflict detection engine.

    Analyzes acquisitions within a workspace/horizon to detect:
    1. Temporal overlaps (same satellite, overlapping times)
    2. Slew infeasibility (insufficient maneuver time between consecutive acquisitions)
    """

    def __init__(
        self,
        db: ScheduleDB,
        config: Optional[ConflictDetectionConfig] = None,
    ):
        """
        Initialize conflict detector.

        Args:
            db: Schedule database instance
            config: Detection configuration (uses defaults if not provided)
        """
        self.db = db
        self.config = config or ConflictDetectionConfig()

    def detect_conflicts(
        self,
        workspace_id: str,
        start_time: str,
        end_time: str,
        satellite_id: Optional[str] = None,
    ) -> List[DetectedConflict]:
        """
        Detect all conflicts within the specified horizon.

        Args:
            workspace_id: Workspace to analyze
            start_time: Horizon start (ISO datetime)
            end_time: Horizon end (ISO datetime)
            satellite_id: Optional filter to single satellite

        Returns:
            List of detected conflicts
        """
        conflicts: List[DetectedConflict] = []

        # Get acquisitions in horizon
        acquisitions = self.db.get_acquisitions_in_horizon(
            start_time=start_time,
            end_time=end_time,
            workspace_id=workspace_id,
            include_tentative=True,
        )

        if not acquisitions:
            logger.info(
                f"[ConflictDetector] No acquisitions in horizon for workspace {workspace_id}"
            )
            return conflicts

        # Filter by satellite if specified
        if satellite_id:
            acquisitions = [a for a in acquisitions if a.satellite_id == satellite_id]

        # Group acquisitions by satellite
        by_satellite: Dict[str, List[Acquisition]] = {}
        for acq in acquisitions:
            if acq.satellite_id not in by_satellite:
                by_satellite[acq.satellite_id] = []
            by_satellite[acq.satellite_id].append(acq)

        # Detect conflicts per satellite
        for sat_id, sat_acqs in by_satellite.items():
            # Sort by start time
            sat_acqs.sort(key=lambda a: a.start_time)

            # Detect temporal overlaps
            overlap_conflicts = self._detect_temporal_overlaps(sat_acqs, sat_id)
            conflicts.extend(overlap_conflicts)

            # Detect slew infeasibility
            slew_conflicts = self._detect_slew_infeasible(sat_acqs, sat_id)
            conflicts.extend(slew_conflicts)

        logger.info(
            f"[ConflictDetector] Detected {len(conflicts)} conflicts "
            f"for workspace {workspace_id} ({len(acquisitions)} acquisitions)"
        )

        return conflicts

    def _detect_temporal_overlaps(
        self,
        acquisitions: List[Acquisition],
        satellite_id: str,
    ) -> List[DetectedConflict]:
        """
        Detect temporal overlaps for a single satellite's acquisitions.

        Two acquisitions overlap if acq1.end_time > acq2.start_time
        (assuming sorted by start_time).
        """
        conflicts: List[DetectedConflict] = []

        for i in range(len(acquisitions) - 1):
            acq1 = acquisitions[i]
            acq2 = acquisitions[i + 1]

            # Parse times
            end1 = self._parse_time(acq1.end_time)
            start2 = self._parse_time(acq2.start_time)

            if end1 is None or start2 is None:
                continue

            # Check for overlap
            overlap_seconds = (end1 - start2).total_seconds()

            if overlap_seconds > self.config.overlap_threshold_s:
                conflict = DetectedConflict(
                    type="temporal_overlap",
                    severity="error",
                    description=(
                        f"Satellite {satellite_id}: acquisitions overlap by "
                        f"{overlap_seconds:.1f}s. {acq1.target_id} ends at "
                        f"{acq1.end_time}, {acq2.target_id} starts at {acq2.start_time}"
                    ),
                    acquisition_ids=[acq1.id, acq2.id],
                    details={
                        "satellite_id": satellite_id,
                        "overlap_seconds": overlap_seconds,
                        "acq1_target": acq1.target_id,
                        "acq2_target": acq2.target_id,
                        "acq1_end": acq1.end_time,
                        "acq2_start": acq2.start_time,
                    },
                )
                conflicts.append(conflict)

        return conflicts

    def _detect_slew_infeasible(
        self,
        acquisitions: List[Acquisition],
        satellite_id: str,
    ) -> List[DetectedConflict]:
        """
        Detect slew infeasibility between consecutive acquisitions.

        Considers both roll and pitch angle changes.
        Slew is infeasible if available_time < required_slew_time + settling_time.

        By default, roll and pitch slews happen in parallel (max of both times).
        Can be configured for sequential slews (sum of both times).
        """
        conflicts: List[DetectedConflict] = []

        for i in range(len(acquisitions) - 1):
            acq1 = acquisitions[i]
            acq2 = acquisitions[i + 1]

            # Skip if these already have a temporal overlap (handled separately)
            end1 = self._parse_time(acq1.end_time)
            start2 = self._parse_time(acq2.start_time)

            if end1 is None or start2 is None:
                continue

            # Available time between acquisitions
            available_time_s = (start2 - end1).total_seconds()

            # If already overlapping, skip slew check (overlap is the bigger problem)
            if available_time_s <= 0:
                continue

            # Calculate required slew time for roll
            roll_delta = abs(acq2.roll_angle_deg - acq1.roll_angle_deg)
            roll_slew_time_s = roll_delta / self.config.roll_slew_rate_deg_per_sec

            # Calculate required slew time for pitch
            pitch1 = acq1.pitch_angle_deg if acq1.pitch_angle_deg is not None else 0.0
            pitch2 = acq2.pitch_angle_deg if acq2.pitch_angle_deg is not None else 0.0
            pitch_delta = abs(pitch2 - pitch1)
            pitch_slew_time_s = pitch_delta / self.config.pitch_slew_rate_deg_per_sec

            # Total slew time depends on parallel vs sequential mode
            if self.config.parallel_slew:
                # Roll and pitch happen simultaneously - take the max
                total_slew_time_s = max(roll_slew_time_s, pitch_slew_time_s)
            else:
                # Roll and pitch happen sequentially - sum them
                total_slew_time_s = roll_slew_time_s + pitch_slew_time_s

            total_required_s = total_slew_time_s + self.config.settling_time_s

            # Check if feasible
            if available_time_s < total_required_s:
                deficit_s = total_required_s - available_time_s

                # Determine severity based on deficit
                if deficit_s > 10:
                    severity = "error"
                elif deficit_s >= 5:
                    severity = "warning"
                else:
                    severity = "info"

                # Build description
                slew_desc = f"roll {roll_delta:.1f}°"
                if pitch_delta > 0.01:
                    slew_desc += f" + pitch {pitch_delta:.1f}°"

                conflict = DetectedConflict(
                    type="slew_infeasible",
                    severity=severity,
                    description=(
                        f"Satellite {satellite_id}: insufficient slew time. "
                        f"Need {total_required_s:.1f}s to slew ({slew_desc}) "
                        f"but only {available_time_s:.1f}s available "
                        f"(deficit: {deficit_s:.1f}s)"
                    ),
                    acquisition_ids=[acq1.id, acq2.id],
                    details={
                        "satellite_id": satellite_id,
                        "roll_delta_deg": roll_delta,
                        "pitch_delta_deg": pitch_delta,
                        "roll_slew_time_s": roll_slew_time_s,
                        "pitch_slew_time_s": pitch_slew_time_s,
                        "required_time_s": total_required_s,
                        "available_time_s": available_time_s,
                        "deficit_s": deficit_s,
                        "acq1_roll": acq1.roll_angle_deg,
                        "acq2_roll": acq2.roll_angle_deg,
                        "acq1_pitch": pitch1,
                        "acq2_pitch": pitch2,
                        "acq1_target": acq1.target_id,
                        "acq2_target": acq2.target_id,
                        "parallel_slew": self.config.parallel_slew,
                    },
                )
                conflicts.append(conflict)

        return conflicts

    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """Parse ISO datetime string."""
        try:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            logger.warning(f"Failed to parse time: {time_str}")
            return None

    def persist_conflicts(
        self,
        conflicts: List[DetectedConflict],
        workspace_id: str,
        clear_existing: bool = True,
    ) -> List[str]:
        """
        Persist detected conflicts to the database.

        Args:
            conflicts: List of detected conflicts
            workspace_id: Workspace ID
            clear_existing: If True, clear existing unresolved conflicts first

        Returns:
            List of created conflict IDs
        """
        if clear_existing:
            # Clear existing unresolved conflicts for this workspace
            self.db.clear_unresolved_conflicts(workspace_id)

        conflict_ids: List[str] = []

        for detected in conflicts:
            conflict = self.db.create_conflict(
                conflict_type=detected.type,
                severity=detected.severity,
                description=detected.description,
                acquisition_ids=detected.acquisition_ids,
                workspace_id=workspace_id,
            )
            conflict_ids.append(conflict.id)

        logger.info(
            f"[ConflictDetector] Persisted {len(conflict_ids)} conflicts "
            f"for workspace {workspace_id}"
        )

        return conflict_ids


def detect_and_persist_conflicts(
    db: ScheduleDB,
    workspace_id: str,
    start_time: str,
    end_time: str,
    satellite_id: Optional[str] = None,
    config: Optional[ConflictDetectionConfig] = None,
) -> Tuple[List[DetectedConflict], List[str]]:
    """
    Convenience function to detect and persist conflicts in one call.

    Args:
        db: Schedule database instance
        workspace_id: Workspace to analyze
        start_time: Horizon start
        end_time: Horizon end
        satellite_id: Optional satellite filter
        config: Detection configuration

    Returns:
        Tuple of (detected conflicts, persisted conflict IDs)
    """
    detector = ConflictDetector(db, config)

    # Detect conflicts
    conflicts = detector.detect_conflicts(
        workspace_id=workspace_id,
        start_time=start_time,
        end_time=end_time,
        satellite_id=satellite_id,
    )

    # Persist to database
    conflict_ids = detector.persist_conflicts(conflicts, workspace_id)

    return conflicts, conflict_ids


def check_commit_conflicts(
    db: ScheduleDB,
    workspace_id: str,
    acquisition_ids: List[str],
) -> List[Conflict]:
    """
    Check if committing would introduce severity=error conflicts.

    This is used as a guardrail before commit operations.

    Args:
        db: Schedule database instance
        workspace_id: Workspace
        acquisition_ids: IDs of acquisitions being committed

    Returns:
        List of error-severity conflicts involving the given acquisitions
    """
    # Get all unresolved conflicts for the workspace
    conflicts = db.list_conflicts(
        workspace_id=workspace_id,
        resolved=False,
    )

    # Filter to error severity and involving the given acquisitions
    error_conflicts = []
    acq_id_set = set(acquisition_ids)

    for conflict in conflicts:
        if conflict.severity != "error":
            continue

        # Parse acquisition IDs from JSON
        try:
            conflict_acq_ids = json.loads(conflict.acquisition_ids_json)
        except json.JSONDecodeError:
            continue

        # Check if any of our acquisitions are involved
        if any(aid in acq_id_set for aid in conflict_acq_ids):
            error_conflicts.append(conflict)

    return error_conflicts
