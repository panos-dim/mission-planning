"""
Advanced tests for conflict_resolution module.

Tests cover:
- Pass overlap detection
- Time parsing
- Winner selection strategies
- Full conflict resolution pipeline
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from mission_planner.conflict_resolution import (
    ConflictInfo,
    ConflictResolutionResult,
    ConstellationConflictResolver,
)


class TestPassesOverlap:
    """Tests for _passes_overlap method."""

    @pytest.fixture
    def resolver(self):
        return ConstellationConflictResolver(time_threshold_seconds=300)

    def test_overlapping_passes(self, resolver) -> None:
        """Passes with overlapping times should be detected."""
        p1 = {
            "start_time": "2025-01-01T12:00:00",
            "end_time": "2025-01-01T12:10:00",
        }
        p2 = {
            "start_time": "2025-01-01T12:05:00",
            "end_time": "2025-01-01T12:15:00",
        }

        result = resolver._passes_overlap(p1, p2)

        assert result is True

    def test_non_overlapping_passes(self, resolver) -> None:
        """Passes without overlap should not be detected."""
        p1 = {
            "start_time": "2025-01-01T12:00:00",
            "end_time": "2025-01-01T12:10:00",
        }
        p2 = {
            "start_time": "2025-01-01T13:00:00",
            "end_time": "2025-01-01T13:10:00",
        }

        result = resolver._passes_overlap(p1, p2)

        assert result is False

    def test_adjacent_passes_within_threshold(self, resolver) -> None:
        """Passes within threshold should be considered overlapping."""
        p1 = {
            "start_time": "2025-01-01T12:00:00",
            "end_time": "2025-01-01T12:10:00",
        }
        # Starts 2 minutes after p1 ends (within 5 min threshold)
        p2 = {
            "start_time": "2025-01-01T12:12:00",
            "end_time": "2025-01-01T12:22:00",
        }

        result = resolver._passes_overlap(p1, p2)

        assert result is True

    def test_passes_with_invalid_times(self, resolver) -> None:
        """Invalid times should return False."""
        p1 = {"start_time": "", "end_time": ""}
        p2 = {"start_time": "2025-01-01T12:00:00", "end_time": "2025-01-01T12:10:00"}

        result = resolver._passes_overlap(p1, p2)

        assert result is False


class TestParseTime:
    """Tests for _parse_time method."""

    @pytest.fixture
    def resolver(self):
        return ConstellationConflictResolver()

    def test_parse_iso_format(self, resolver) -> None:
        """ISO format should be parsed correctly."""
        result = resolver._parse_time("2025-01-15T14:30:00")

        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30

    def test_parse_with_z_suffix(self, resolver) -> None:
        """Z suffix should be handled."""
        result = resolver._parse_time("2025-01-15T14:30:00Z")

        assert result is not None
        assert result.year == 2025

    def test_parse_with_timezone(self, resolver) -> None:
        """Timezone offset should be handled."""
        result = resolver._parse_time("2025-01-15T14:30:00+00:00")

        assert result is not None
        assert result.year == 2025

    def test_parse_empty_string(self, resolver) -> None:
        """Empty string should return None."""
        result = resolver._parse_time("")

        assert result is None

    def test_parse_invalid_format(self, resolver) -> None:
        """Invalid format should return None."""
        result = resolver._parse_time("not-a-date")

        assert result is None


class TestSelectWinner:
    """Tests for _select_winner method."""

    def test_best_geometry_strategy(self) -> None:
        """Best geometry should select lowest incidence angle."""
        resolver = ConstellationConflictResolver(strategy="best_geometry")

        conflict = ConflictInfo(
            target_name="Target1",
            conflicting_passes=[
                {"satellite_id": "sat1", "incidence_angle_deg": 30.0},
                {"satellite_id": "sat2", "incidence_angle_deg": 20.0},
                {"satellite_id": "sat3", "incidence_angle_deg": 25.0},
            ],
            conflict_type="temporal_overlap",
        )

        winner = resolver._select_winner(conflict)

        assert winner["satellite_id"] == "sat2"  # Lowest incidence angle

    def test_first_available_strategy(self) -> None:
        """First available should select earliest start time."""
        resolver = ConstellationConflictResolver(strategy="first_available")

        conflict = ConflictInfo(
            target_name="Target1",
            conflicting_passes=[
                {"satellite_id": "sat1", "start_time": "2025-01-01T12:10:00"},
                {"satellite_id": "sat2", "start_time": "2025-01-01T12:00:00"},
                {"satellite_id": "sat3", "start_time": "2025-01-01T12:05:00"},
            ],
            conflict_type="temporal_overlap",
        )

        winner = resolver._select_winner(conflict)

        assert winner["satellite_id"] == "sat2"  # Earliest start

    def test_load_balance_strategy(self) -> None:
        """Load balance should select satellite with lowest load."""
        resolver = ConstellationConflictResolver(strategy="load_balance")
        resolver._satellite_loads = {"sat1": 5, "sat2": 2, "sat3": 3}

        conflict = ConflictInfo(
            target_name="Target1",
            conflicting_passes=[
                {"satellite_id": "sat1"},
                {"satellite_id": "sat2"},
                {"satellite_id": "sat3"},
            ],
            conflict_type="temporal_overlap",
        )

        winner = resolver._select_winner(conflict)

        assert winner["satellite_id"] == "sat2"  # Lowest load

    def test_empty_passes_returns_none(self) -> None:
        """Empty passes should return None."""
        resolver = ConstellationConflictResolver()

        conflict = ConflictInfo(
            target_name="Target1",
            conflicting_passes=[],
            conflict_type="temporal_overlap",
        )

        winner = resolver._select_winner(conflict)

        assert winner is None


class TestResolveConflicts:
    """Tests for resolve_conflicts method."""

    @pytest.fixture
    def resolver(self):
        return ConstellationConflictResolver(strategy="best_geometry")

    def test_no_conflicts(self, resolver) -> None:
        """No conflicts should return all passes."""
        passes = [
            {
                "satellite_id": "sat1",
                "target": "t1",
                "start_time": "2025-01-01T12:00:00",
            },
            {
                "satellite_id": "sat2",
                "target": "t2",
                "start_time": "2025-01-01T13:00:00",
            },
        ]

        result = resolver.resolve_conflicts(passes, [])

        assert len(result.resolved_passes) == 2
        assert result.conflicts_resolved == 0
        assert result.passes_removed == 0

    def test_single_conflict_resolution(self, resolver) -> None:
        """Single conflict should remove losing pass."""
        passes = [
            {
                "satellite_id": "sat1",
                "target": "t1",
                "start_time": "2025-01-01T12:00:00",
                "incidence_angle_deg": 30,
            },
            {
                "satellite_id": "sat2",
                "target": "t1",
                "start_time": "2025-01-01T12:05:00",
                "incidence_angle_deg": 20,
            },
        ]

        conflict = ConflictInfo(
            target_name="t1",
            conflicting_passes=passes,
            conflict_type="temporal_overlap",
        )

        result = resolver.resolve_conflicts(passes, [conflict])

        assert result.conflicts_resolved == 1


class TestGetPassKey:
    """Tests for _get_pass_key method."""

    @pytest.fixture
    def resolver(self):
        return ConstellationConflictResolver()

    def test_generates_unique_key(self, resolver) -> None:
        """Should generate unique key from pass data."""
        p = {
            "satellite_id": "sat1",
            "target": "target1",
            "start_time": "2025-01-01T12:00:00",
        }

        key = resolver._get_pass_key(p)

        assert "sat1" in key
        assert "target1" in key
        assert "2025-01-01T12:00:00" in key

    def test_different_passes_different_keys(self, resolver) -> None:
        """Different passes should have different keys."""
        p1 = {
            "satellite_id": "sat1",
            "target": "target1",
            "start_time": "2025-01-01T12:00:00",
        }
        p2 = {
            "satellite_id": "sat2",
            "target": "target1",
            "start_time": "2025-01-01T12:00:00",
        }

        key1 = resolver._get_pass_key(p1)
        key2 = resolver._get_pass_key(p2)

        assert key1 != key2


class TestConflictInfoDataclass:
    """Tests for ConflictInfo dataclass."""

    def test_basic_creation(self) -> None:
        conflict = ConflictInfo(
            target_name="Target1",
            conflicting_passes=[{"sat": "sat1"}, {"sat": "sat2"}],
            conflict_type="temporal_overlap",
        )

        assert conflict.target_name == "Target1"
        assert len(conflict.conflicting_passes) == 2
        assert conflict.conflict_type == "temporal_overlap"

    def test_with_resolution(self) -> None:
        conflict = ConflictInfo(
            target_name="Target1",
            conflicting_passes=[{"sat": "sat1"}],
            conflict_type="temporal_overlap",
            resolution_strategy="best_geometry",
            winner_satellite_id="sat1",
        )

        assert conflict.resolution_strategy == "best_geometry"
        assert conflict.winner_satellite_id == "sat1"

    def test_to_dict(self) -> None:
        conflict = ConflictInfo(
            target_name="Target1",
            conflicting_passes=[{"satellite_id": "sat1"}, {"satellite_id": "sat2"}],
            conflict_type="temporal_overlap",
        )

        result = conflict.to_dict()

        assert result["target_name"] == "Target1"
        assert "conflicting_satellites" in result


class TestConflictResolutionResultDataclass:
    """Tests for ConflictResolutionResult dataclass."""

    def test_basic_creation(self) -> None:
        result = ConflictResolutionResult(
            resolved_passes=[{"pass": 1}],
            conflicts_detected=[],
            conflicts_resolved=0,
            passes_removed=0,
        )

        assert len(result.resolved_passes) == 1
        assert result.conflicts_resolved == 0

    def test_with_conflicts(self) -> None:
        conflict = ConflictInfo(
            target_name="T1", conflicting_passes=[], conflict_type="overlap"
        )

        result = ConflictResolutionResult(
            resolved_passes=[],
            conflicts_detected=[conflict],
            conflicts_resolved=1,
            passes_removed=1,
        )

        assert len(result.conflicts_detected) == 1
        assert result.passes_removed == 1

    def test_to_dict(self) -> None:
        result = ConflictResolutionResult(
            resolved_passes=[{"pass": 1}],
            conflicts_detected=[],
            conflicts_resolved=0,
            passes_removed=0,
        )

        d = result.to_dict()

        assert "resolved_passes" in d or "conflicts_resolved" in d


class TestConstellationConflictResolverInit:
    """Tests for ConstellationConflictResolver initialization."""

    def test_default_initialization(self) -> None:
        resolver = ConstellationConflictResolver()

        assert resolver is not None
        assert resolver.time_threshold_seconds > 0

    def test_custom_threshold(self) -> None:
        resolver = ConstellationConflictResolver(time_threshold_seconds=600)

        assert resolver.time_threshold_seconds == 600

    def test_custom_strategy(self) -> None:
        resolver = ConstellationConflictResolver(strategy="load_balance")

        assert resolver.strategy == "load_balance"

    def test_satellite_loads_initialized(self) -> None:
        resolver = ConstellationConflictResolver()

        assert hasattr(resolver, "_satellite_loads")
        assert isinstance(resolver._satellite_loads, dict)
