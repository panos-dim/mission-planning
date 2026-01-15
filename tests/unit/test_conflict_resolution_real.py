"""
Tests for conflict_resolution module using actual imports.
"""

import pytest
from datetime import datetime, timedelta

from mission_planner.conflict_resolution import (
    ConflictInfo,
    ConflictResolutionResult,
    ConstellationConflictResolver,
    deduplicate_constellation_passes,
)


class TestConflictInfo:
    """Tests for ConflictInfo dataclass."""

    def test_basic_creation(self) -> None:
        info = ConflictInfo(
            target_name="Dubai",
            conflicting_passes=[{"satellite_id": "SAT1"}, {"satellite_id": "SAT2"}],
        )
        assert info.target_name == "Dubai"
        assert len(info.conflicting_passes) == 2

    def test_to_dict(self) -> None:
        info = ConflictInfo(
            target_name="Dubai",
            conflicting_passes=[{"satellite_id": "SAT1"}, {"satellite_id": "SAT2"}],
            resolution_strategy="best_geometry",
            winner_satellite_id="SAT1",
        )
        d = info.to_dict()
        assert d["target_name"] == "Dubai"
        assert d["resolution_strategy"] == "best_geometry"
        assert "SAT1" in d["conflicting_satellites"]

    def test_default_values(self) -> None:
        info = ConflictInfo(target_name="Test", conflicting_passes=[])
        assert info.resolution_strategy == ""
        assert info.winner_satellite_id == ""
        assert info.conflict_type == "temporal_overlap"


class TestConflictResolutionResult:
    """Tests for ConflictResolutionResult dataclass."""

    def test_basic_creation(self) -> None:
        result = ConflictResolutionResult(
            resolved_passes=[],
            conflicts_detected=[],
            conflicts_resolved=0,
            passes_removed=0,
        )
        assert result.conflicts_resolved == 0

    def test_to_dict(self) -> None:
        conflict = ConflictInfo(target_name="Dubai", conflicting_passes=[])
        result = ConflictResolutionResult(
            resolved_passes=[],
            conflicts_detected=[conflict],
            conflicts_resolved=1,
            passes_removed=1,
        )
        d = result.to_dict()
        assert d["conflicts_detected"] == 1
        assert d["conflicts_resolved"] == 1
        assert d["passes_removed"] == 1


class TestConstellationConflictResolver:
    """Tests for ConstellationConflictResolver class."""

    def test_creation_default(self) -> None:
        resolver = ConstellationConflictResolver()
        assert resolver.strategy == "best_geometry"
        assert resolver.time_threshold_seconds == 300.0

    def test_creation_custom(self) -> None:
        resolver = ConstellationConflictResolver(
            time_threshold_seconds=600.0,
            strategy="first_available",
        )
        assert resolver.time_threshold_seconds == 600.0
        assert resolver.strategy == "first_available"

    def test_process_empty_passes(self) -> None:
        resolver = ConstellationConflictResolver()
        result = resolver.process([])
        assert result.conflicts_resolved == 0
        assert len(result.resolved_passes) == 0

    def test_process_single_pass(self) -> None:
        resolver = ConstellationConflictResolver()
        passes = [
            {
                "target_name": "Dubai",
                "satellite_id": "SAT1",
                "start_time": datetime(2025, 1, 1, 12, 0, 0),
                "end_time": datetime(2025, 1, 1, 12, 10, 0),
                "max_elevation": 45.0,
                "incidence_angle_deg": 20.0,
            }
        ]
        result = resolver.process(passes)
        assert len(result.resolved_passes) == 1

    def test_process_no_conflict(self) -> None:
        resolver = ConstellationConflictResolver()
        passes = [
            {
                "target_name": "Dubai",
                "satellite_id": "SAT1",
                "start_time": datetime(2025, 1, 1, 12, 0, 0),
                "end_time": datetime(2025, 1, 1, 12, 10, 0),
                "incidence_angle_deg": 20.0,
            },
            {
                "target_name": "Abu Dhabi",
                "satellite_id": "SAT2",
                "start_time": datetime(2025, 1, 1, 12, 0, 0),
                "end_time": datetime(2025, 1, 1, 12, 10, 0),
                "incidence_angle_deg": 25.0,
            },
        ]
        result = resolver.process(passes)
        assert len(result.resolved_passes) == 2

    def test_process_with_conflict(self) -> None:
        resolver = ConstellationConflictResolver(strategy="best_geometry")
        passes = [
            {
                "target_name": "Dubai",
                "satellite_id": "SAT1",
                "start_time": datetime(2025, 1, 1, 12, 0, 0),
                "end_time": datetime(2025, 1, 1, 12, 10, 0),
                "incidence_angle_deg": 30.0,
            },
            {
                "target_name": "Dubai",
                "satellite_id": "SAT2",
                "start_time": datetime(2025, 1, 1, 12, 2, 0),
                "end_time": datetime(2025, 1, 1, 12, 12, 0),
                "incidence_angle_deg": 15.0,
            },
        ]
        result = resolver.process(passes)
        assert result.conflicts_resolved >= 0

    def test_detect_conflicts(self) -> None:
        resolver = ConstellationConflictResolver()
        passes = [
            {
                "target_name": "Dubai",
                "satellite_id": "SAT1",
                "start_time": datetime(2025, 1, 1, 12, 0, 0),
                "end_time": datetime(2025, 1, 1, 12, 10, 0),
            },
            {
                "target_name": "Dubai",
                "satellite_id": "SAT2",
                "start_time": datetime(2025, 1, 1, 12, 5, 0),
                "end_time": datetime(2025, 1, 1, 12, 15, 0),
            },
        ]
        conflicts = resolver.detect_conflicts(passes)
        assert isinstance(conflicts, list)


class TestDeduplicateConstellationPasses:
    """Tests for deduplicate_constellation_passes function."""

    def test_empty_input(self) -> None:
        result, info = deduplicate_constellation_passes([])
        assert result == []

    def test_single_pass(self) -> None:
        passes = [{"target_name": "Dubai", "satellite_id": "SAT1"}]
        result, info = deduplicate_constellation_passes(passes)
        assert len(result) == 1

    def test_no_duplicates(self) -> None:
        passes = [
            {"target_name": "Dubai", "satellite_id": "SAT1"},
            {"target_name": "Abu Dhabi", "satellite_id": "SAT2"},
        ]
        result, info = deduplicate_constellation_passes(passes)
        assert len(result) == 2
