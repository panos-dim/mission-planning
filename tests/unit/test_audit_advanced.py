"""
Advanced tests for audit/planning_audit module.

Tests cover:
- Invariant checks
- Metrics computation
- Algorithm audit functions
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from mission_planner.audit.planning_audit import (
    AlgorithmMetrics,
    AuditReport,
    InvariantCheck,
    check_no_overlap,
    check_pitch_within_limits,
    check_quality_consistency,
    check_roll_within_limits,
    check_slack_non_negative,
    check_time_monotonic,
    compute_metrics,
)
from mission_planner.scheduler import Opportunity, ScheduledOpportunity, SchedulerConfig


class TestInvariantCheckDataclass:
    """Tests for InvariantCheck dataclass."""

    def test_basic_creation(self) -> None:
        check = InvariantCheck(name="test", ok=True)

        assert check.name == "test"
        assert check.ok is True
        assert check.details is None

    def test_with_details(self) -> None:
        check = InvariantCheck(name="test", ok=False, details="Something failed")

        assert check.ok is False
        assert check.details == "Something failed"

    def test_with_affected_items(self) -> None:
        check = InvariantCheck(
            name="test",
            ok=False,
            details="Items affected",
            affected_items=["item1", "item2"],
        )

        assert len(check.affected_items) == 2


class TestAlgorithmMetricsDataclass:
    """Tests for AlgorithmMetrics dataclass."""

    def test_default_creation(self) -> None:
        metrics = AlgorithmMetrics()

        assert metrics.accepted == 0
        assert metrics.rejected == 0
        assert metrics.total_value == 0.0

    def test_with_values(self) -> None:
        metrics = AlgorithmMetrics()
        metrics.accepted = 10
        metrics.rejected = 5
        metrics.total_value = 8.5

        assert metrics.accepted == 10
        assert metrics.rejected == 5
        assert metrics.total_value == 8.5

    def test_has_geometry_fields(self) -> None:
        metrics = AlgorithmMetrics()

        assert hasattr(metrics, "mean_incidence_deg")
        assert hasattr(metrics, "min_incidence_deg")
        assert hasattr(metrics, "max_incidence_deg")

    def test_has_roll_fields(self) -> None:
        metrics = AlgorithmMetrics()

        assert hasattr(metrics, "total_roll_used_deg")
        assert hasattr(metrics, "max_roll_deg")
        assert hasattr(metrics, "mean_roll_deg")


class TestAuditReportDataclass:
    """Tests for AuditReport dataclass."""

    def test_basic_creation(self) -> None:
        report = AuditReport(
            algorithm_name="test_algo",
            status="ok",
            metrics=AlgorithmMetrics(),
            invariants=[],
            schedule=[],
        )

        assert report.algorithm_name == "test_algo"
        assert report.status == "ok"

    def test_with_invariants(self) -> None:
        checks = [
            InvariantCheck(name="check1", ok=True),
            InvariantCheck(name="check2", ok=False, details="Failed"),
        ]

        report = AuditReport(
            algorithm_name="test",
            status="failed",
            metrics=AlgorithmMetrics(),
            invariants=checks,
            schedule=[],
        )

        assert len(report.invariants) == 2


def test_check_roll_within_limits_empty_schedule() -> None:
    result = check_roll_within_limits([], 45.0)

    assert result.ok is True


def test_check_roll_within_limits_within_limits() -> None:
    schedule = [
        MagicMock(roll_angle=20.0, opportunity_id="opp1"),
        MagicMock(roll_angle=30.0, opportunity_id="opp2"),
    ]

    result = check_roll_within_limits(schedule, 45.0)

    assert result.ok is True


def test_check_roll_within_limits_exceeds_roll_limit() -> None:
    schedule = [
        MagicMock(roll_angle=50.0, opportunity_id="opp1"),
    ]

    result = check_roll_within_limits(schedule, 45.0)

    assert result.ok is False


def test_check_pitch_within_limits_empty_schedule() -> None:
    result = check_pitch_within_limits([], 30.0)

    assert result.ok is True


def test_check_pitch_within_limits_within_limits() -> None:
    schedule = [
        MagicMock(pitch_angle=10.0, opportunity_id="opp1"),
        MagicMock(pitch_angle=20.0, opportunity_id="opp2"),
    ]

    result = check_pitch_within_limits(schedule, 30.0)

    assert result.ok is True


def test_check_slack_non_negative_empty_schedule() -> None:
    result = check_slack_non_negative([])

    assert result.ok is True


def test_check_slack_non_negative_positive_slack() -> None:
    schedule = [
        MagicMock(slack_time=5.0, opportunity_id="opp1"),
        MagicMock(slack_time=10.0, opportunity_id="opp2"),
    ]

    result = check_slack_non_negative(schedule)

    assert result.ok is True


def test_check_slack_non_negative_negative_slack() -> None:
    schedule = [
        MagicMock(slack_time=-5.0, opportunity_id="opp1"),
    ]

    result = check_slack_non_negative(schedule)

    assert result.ok is False


def test_check_no_overlap_empty_schedule() -> None:
    result = check_no_overlap([], ["sat1"])

    assert result.ok is True


def test_check_no_overlap_no_overlap() -> None:
    base_time = datetime(2025, 1, 1, 12, 0, 0)

    schedule = [
        MagicMock(
            satellite_id="sat1",
            start_time=base_time,
            end_time=base_time + timedelta(minutes=5),
            opportunity_id="opp1",
        ),
        MagicMock(
            satellite_id="sat1",
            start_time=base_time + timedelta(minutes=10),
            end_time=base_time + timedelta(minutes=15),
            opportunity_id="opp2",
        ),
    ]

    result = check_no_overlap(schedule, ["sat1"])

    assert result.ok is True


def test_check_time_monotonic_empty_schedule() -> None:
    result = check_time_monotonic([], ["sat1"])

    assert result.ok is True


def test_check_time_monotonic_monotonic_schedule() -> None:
    base_time = datetime(2025, 1, 1, 12, 0, 0)

    schedule = [
        MagicMock(
            satellite_id="sat1",
            start_time=base_time,
            end_time=base_time + timedelta(minutes=5),
            opportunity_id="opp1",
        ),
        MagicMock(
            satellite_id="sat1",
            start_time=base_time + timedelta(minutes=10),
            end_time=base_time + timedelta(minutes=15),
            opportunity_id="opp2",
        ),
    ]

    result = check_time_monotonic(schedule, ["sat1"])

    assert result.ok is True


def test_check_quality_consistency_model_off() -> None:
    result = check_quality_consistency([], [], "off")

    assert result.ok is True
    assert "disabled" in result.details.lower()


def test_check_quality_consistency_empty_schedule() -> None:
    result = check_quality_consistency([], [], "linear")

    assert result.ok is True


class TestComputeMetrics:
    """Tests for compute_metrics function."""

    def test_empty_schedule(self) -> None:
        config = SchedulerConfig()

        metrics = compute_metrics([], [], config, 0.1)

        assert metrics.accepted == 0
        assert metrics.runtime_ms > 0

    def test_with_schedule(self) -> None:
        config = SchedulerConfig()
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        schedule = [
            MagicMock(
                value=0.8,
                incidence_angle=25.0,
                roll_angle=15.0,
                pitch_angle=2.0,
                maneuver_time=10.0,
                slack_time=5.0,
                start_time=base_time,
                end_time=base_time + timedelta(minutes=5),
            ),
            MagicMock(
                value=0.9,
                incidence_angle=20.0,
                roll_angle=10.0,
                pitch_angle=0.0,
                maneuver_time=8.0,
                slack_time=3.0,
                start_time=base_time + timedelta(minutes=10),
                end_time=base_time + timedelta(minutes=15),
            ),
        ]

        all_opps = [MagicMock() for _ in range(5)]

        metrics = compute_metrics(schedule, all_opps, config, 0.5)

        assert metrics.accepted == 2
        assert metrics.total_opportunities == 5
        assert metrics.rejected == 3
        assert abs(metrics.total_value - 1.7) < 0.01
        assert abs(metrics.mean_value - 0.85) < 0.01

    def test_geometry_metrics(self) -> None:
        config = SchedulerConfig()
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        schedule = [
            MagicMock(
                value=0.8,
                incidence_angle=30.0,
                roll_angle=20.0,
                pitch_angle=5.0,
                maneuver_time=10.0,
                slack_time=5.0,
                start_time=base_time,
                end_time=base_time + timedelta(minutes=5),
            ),
            MagicMock(
                value=0.7,
                incidence_angle=20.0,
                roll_angle=10.0,
                pitch_angle=0.0,
                maneuver_time=8.0,
                slack_time=3.0,
                start_time=base_time + timedelta(minutes=10),
                end_time=base_time + timedelta(minutes=15),
            ),
        ]

        metrics = compute_metrics(schedule, schedule, config, 0.5)

        assert metrics.mean_incidence_deg == 25.0
        assert metrics.min_incidence_deg == 20.0
        assert metrics.max_incidence_deg == 30.0

    def test_roll_metrics(self) -> None:
        config = SchedulerConfig()
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        schedule = [
            MagicMock(
                value=0.8,
                incidence_angle=25.0,
                roll_angle=20.0,
                pitch_angle=0.0,
                maneuver_time=10.0,
                slack_time=5.0,
                start_time=base_time,
                end_time=base_time + timedelta(minutes=5),
            ),
            MagicMock(
                value=0.9,
                incidence_angle=20.0,
                roll_angle=30.0,
                pitch_angle=0.0,
                maneuver_time=8.0,
                slack_time=3.0,
                start_time=base_time + timedelta(minutes=10),
                end_time=base_time + timedelta(minutes=15),
            ),
        ]

        metrics = compute_metrics(schedule, schedule, config, 0.5)

        assert metrics.total_roll_used_deg == 50.0
        assert metrics.max_roll_deg == 30.0
        assert metrics.mean_roll_deg == 25.0


class TestComputeMetricsWithQuality:
    """Tests for compute_metrics with quality model."""

    def test_quality_model_enabled(self) -> None:
        config = SchedulerConfig()
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        task1 = MagicMock(
            value=0.8,
            incidence_angle=25.0,
            roll_angle=15.0,
            pitch_angle=0.0,
            maneuver_time=10.0,
            slack_time=5.0,
            quality_score=0.85,
            start_time=base_time,
            end_time=base_time + timedelta(minutes=5),
        )

        schedule = [task1]

        metrics = compute_metrics(
            schedule, schedule, config, 0.5, quality_model="linear"
        )

        assert metrics.avg_quality_score == 0.85
