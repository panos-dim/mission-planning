"""
Constellation Conflict Resolution Module.

Detects and resolves scheduling conflicts when multiple satellites in a
constellation can observe the same target at overlapping times.

Resolution Strategies:
- best_geometry: Select satellite with lowest incidence angle (best image quality)
- first_available: Select satellite with earliest imaging opportunity
- load_balance: Distribute targets across satellites evenly

2025 Best Practice: Implements clean separation of detection and resolution.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ConflictInfo:
    """Information about a scheduling conflict between satellites."""

    target_name: str
    conflicting_passes: List[Dict]  # List of pass dictionaries
    resolution_strategy: str = ""
    winner_satellite_id: str = ""
    winner_pass_index: int = -1
    conflict_type: str = "temporal_overlap"  # temporal_overlap, same_orbit

    def to_dict(self) -> Dict:
        """Convert to dictionary for API response."""
        return {
            "target_name": self.target_name,
            "conflicting_satellites": [
                p.get("satellite_id", "") for p in self.conflicting_passes
            ],
            "resolution_strategy": self.resolution_strategy,
            "winner_satellite_id": self.winner_satellite_id,
            "conflict_type": self.conflict_type,
        }


@dataclass
class ConflictResolutionResult:
    """Result of conflict resolution process."""

    resolved_passes: List[Dict]  # Passes after conflict resolution
    conflicts_detected: List[ConflictInfo]
    conflicts_resolved: int
    passes_removed: int

    def to_dict(self) -> Dict:
        """Convert to dictionary for API response."""
        return {
            "conflicts_detected": len(self.conflicts_detected),
            "conflicts_resolved": self.conflicts_resolved,
            "passes_removed": self.passes_removed,
            "conflict_details": [c.to_dict() for c in self.conflicts_detected],
        }


class ConstellationConflictResolver:
    """
    Detects and resolves conflicts between satellites observing the same target.

    A conflict occurs when:
    1. Multiple satellites can see the same target
    2. The observation windows overlap or are within a threshold time

    Resolution selects the optimal satellite based on the chosen strategy.
    """

    def __init__(
        self,
        time_threshold_seconds: float = 300.0,  # 5 minutes default
        strategy: str = "best_geometry",
    ):
        """
        Initialize conflict resolver.

        Args:
            time_threshold_seconds: Maximum time between passes to consider conflicting
            strategy: Resolution strategy ('best_geometry', 'first_available', 'load_balance')
        """
        self.time_threshold_seconds = time_threshold_seconds
        self.strategy = strategy

        # Track satellite load for load balancing
        self._satellite_loads: Dict[str, int] = defaultdict(int)

    def detect_conflicts(self, passes: List[Dict]) -> List[ConflictInfo]:
        """
        Detect conflicts among passes from multiple satellites.

        Args:
            passes: List of pass dictionaries with satellite_id and target fields

        Returns:
            List of detected conflicts
        """
        conflicts = []

        # Group passes by target
        passes_by_target: Dict[str, List[Tuple[int, Dict]]] = defaultdict(list)
        for idx, p in enumerate(passes):
            target = p.get("target", "")
            passes_by_target[target].append((idx, p))

        # Check each target for conflicts
        for target, target_passes in passes_by_target.items():
            if len(target_passes) < 2:
                continue  # No conflict possible with single pass

            # Check all pairs for temporal overlap
            checked_pairs = set()
            conflict_group = []

            for i, (idx1, p1) in enumerate(target_passes):
                for idx2, p2 in target_passes[i + 1 :]:
                    sat1 = p1.get("satellite_id", "")
                    sat2 = p2.get("satellite_id", "")

                    # Skip if same satellite (not a conflict)
                    if sat1 == sat2:
                        continue

                    # Check temporal overlap
                    if self._passes_overlap(p1, p2):
                        pair_key = tuple(sorted([idx1, idx2]))
                        if pair_key not in checked_pairs:
                            checked_pairs.add(pair_key)
                            if not conflict_group:
                                conflict_group = [p1]
                            if p2 not in conflict_group:
                                conflict_group.append(p2)

            if conflict_group:
                conflicts.append(
                    ConflictInfo(
                        target_name=target,
                        conflicting_passes=conflict_group,
                        conflict_type="temporal_overlap",
                    )
                )

        logger.info(f"Detected {len(conflicts)} conflicts across {len(passes)} passes")
        return conflicts

    def _passes_overlap(self, p1: Dict, p2: Dict) -> bool:
        """Check if two passes overlap or are within threshold."""
        try:
            # Parse times
            start1 = self._parse_time(p1.get("start_time", ""))
            end1 = self._parse_time(p1.get("end_time", ""))
            start2 = self._parse_time(p2.get("start_time", ""))
            end2 = self._parse_time(p2.get("end_time", ""))

            if not all([start1, end1, start2, end2]):
                return False

            # Check overlap with threshold
            threshold = timedelta(seconds=self.time_threshold_seconds)

            # Extend windows by threshold
            start1_ext = start1 - threshold
            end1_ext = end1 + threshold

            # Check if pass2 overlaps extended pass1
            return not (end2 < start1_ext or start2 > end1_ext)

        except Exception as e:
            logger.warning(f"Error checking pass overlap: {e}")
            return False

    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """Parse ISO time string to datetime."""
        if not time_str:
            return None
        try:
            # Handle both with and without Z suffix
            time_str = time_str.replace("Z", "+00:00")
            if "+" in time_str:
                time_str = time_str.split("+")[0]
            return datetime.fromisoformat(time_str)
        except (ValueError, TypeError):
            return None

    def resolve_conflicts(
        self, passes: List[Dict], conflicts: List[ConflictInfo]
    ) -> ConflictResolutionResult:
        """
        Resolve detected conflicts by selecting winning satellite for each.

        Args:
            passes: Original list of passes
            conflicts: Detected conflicts

        Returns:
            Resolution result with filtered passes
        """
        if not conflicts:
            return ConflictResolutionResult(
                resolved_passes=passes,
                conflicts_detected=[],
                conflicts_resolved=0,
                passes_removed=0,
            )

        # Track which passes to remove
        passes_to_remove = set()
        resolved_conflicts = []

        for conflict in conflicts:
            winner = self._select_winner(conflict)

            if winner:
                conflict.resolution_strategy = self.strategy
                conflict.winner_satellite_id = winner.get("satellite_id", "")

                # Mark losing passes for removal
                for p in conflict.conflicting_passes:
                    if p.get("satellite_id") != conflict.winner_satellite_id:
                        # Find and mark this pass
                        pass_key = self._get_pass_key(p)
                        passes_to_remove.add(pass_key)

                resolved_conflicts.append(conflict)

                # Update load tracking
                self._satellite_loads[conflict.winner_satellite_id] += 1

        # Filter out removed passes
        resolved_passes = [
            p for p in passes if self._get_pass_key(p) not in passes_to_remove
        ]

        passes_removed = len(passes) - len(resolved_passes)

        logger.info(
            f"Resolved {len(resolved_conflicts)} conflicts, "
            f"removed {passes_removed} duplicate passes"
        )

        return ConflictResolutionResult(
            resolved_passes=resolved_passes,
            conflicts_detected=resolved_conflicts,
            conflicts_resolved=len(resolved_conflicts),
            passes_removed=passes_removed,
        )

    def _get_pass_key(self, p: Dict) -> str:
        """Generate unique key for a pass."""
        return f"{p.get('satellite_id', '')}_{p.get('target', '')}_{p.get('start_time', '')}"

    def _select_winner(self, conflict: ConflictInfo) -> Optional[Dict]:
        """Select winning pass based on resolution strategy."""
        passes = conflict.conflicting_passes

        if not passes:
            return None

        if self.strategy == "best_geometry":
            # Select pass with lowest incidence angle (best image quality)
            return min(
                passes, key=lambda p: abs(p.get("incidence_angle_deg", 90) or 90)
            )

        elif self.strategy == "first_available":
            # Select pass with earliest start time
            return min(passes, key=lambda p: p.get("start_time", "9999"))

        elif self.strategy == "load_balance":
            # Select satellite with lowest current load
            return min(
                passes,
                key=lambda p: self._satellite_loads.get(p.get("satellite_id", ""), 0),
            )

        else:
            # Default: first pass
            return passes[0]

    def process(self, passes: List[Dict]) -> ConflictResolutionResult:
        """
        Full conflict detection and resolution pipeline.

        Args:
            passes: List of passes from all satellites

        Returns:
            Resolution result with deduplicated passes
        """
        # Reset load tracking
        self._satellite_loads.clear()

        # Detect conflicts
        conflicts = self.detect_conflicts(passes)

        # Resolve conflicts
        result = self.resolve_conflicts(passes, conflicts)

        return result


def deduplicate_constellation_passes(
    passes: List[Dict],
    strategy: str = "best_geometry",
    time_threshold_seconds: float = 300.0,
) -> Tuple[List[Dict], Dict]:
    """
    Convenience function to deduplicate passes from a constellation.

    Args:
        passes: List of pass dictionaries from all satellites
        strategy: Resolution strategy
        time_threshold_seconds: Overlap threshold

    Returns:
        Tuple of (deduplicated_passes, conflict_summary)
    """
    resolver = ConstellationConflictResolver(
        time_threshold_seconds=time_threshold_seconds, strategy=strategy
    )

    result = resolver.process(passes)

    return result.resolved_passes, result.to_dict()
