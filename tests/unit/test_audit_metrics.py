"""
Tests for audit/planning_audit.py metrics computation.

Tests cover:
- compute_metrics function
- AlgorithmMetrics dataclass
- Invariant checks
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from mission_planner.audit.planning_audit import (
    AlgorithmMetrics,
    InvariantCheck,
    check_quality_consistency,
    compute_metrics,
)
from mission_planner.scheduler import Opportunity, ScheduledOpportunity, SchedulerConfig


def create_test_opportunity(target_id, offset_min=0, value=0.8, incidence=30.0):
    """Create a test Opportunity."""
    base = datetime(2025, 1, 15, 12, 0, 0)
    start = base + timedelta(minutes=offset_min)
    end = start + timedelta(minutes=10)

    return Opportunity(
        id=f"opp_{target_id}_{offset_min}",
        target_id=target_id,
        satellite_id="SAT1",
        start_time=start,
        end_time=end,
        max_elevation=60.0,
        incidence_angle=incidence,
        value=value,
    )


def create_scheduled_opportunity(
    target_id, offset_min=0, value=0.8, incidence=30.0, roll=10.0, pitch=5.0
):
    """Create a test ScheduledOpportunity."""
    base = datetime(2025, 1, 15, 12, 0, 0)
    start = base + timedelta(minutes=offset_min)
    end = start + timedelta(minutes=10)

    return ScheduledOpportunity(
        opportunity_id=f"sched_{target_id}_{offset_min}",
        target_id=target_id,
        satellite_id="SAT1",
        start_time=start,
        end_time=end,
        delta_roll=roll,
        delta_pitch=pitch,
        roll_angle=roll,
        pitch_angle=pitch,
        incidence_angle=incidence,
        value=value,
        maneuver_time=5.0,
        slack_time=2.0,
    )


class TestComputeMetricsEmpty:
    """Tests for compute_metrics with empty inputs."""

    def test_empty_schedule(self) -> None:
        config = SchedulerConfig()
        opps = [create_test_opportunity("T1")]

        metrics = compute_metrics([], opps, config, runtime_s=0.1)

        assert metrics.accepted == 0
        assert metrics.rejected == 1
        assert metrics.runtime_ms == pytest.approx(100.0)

    def test_empty_both(self) -> None:
        config = SchedulerConfig()

        metrics = compute_metrics([], [], config, runtime_s=0.05)

        assert metrics.accepted == 0
        assert metrics.total_opportunities == 0


class TestComputeMetricsBasic:
    """Tests for compute_metrics with basic inputs."""

    def test_single_scheduled(self) -> None:
        config = SchedulerConfig()
        opps = [create_test_opportunity("T1")]
        schedule = [create_scheduled_opportunity("T1")]

        metrics = compute_metrics(schedule, opps, config, runtime_s=0.1)

        assert metrics.accepted == 1
        assert metrics.total_opportunities == 1
        assert metrics.rejected == 0

    def test_multiple_scheduled(self) -> None:
        config = SchedulerConfig()
        opps = [
            create_test_opportunity("T1", 0),
            create_test_opportunity("T1", 30),
            create_test_opportunity("T2", 60),
        ]
        schedule = [
            create_scheduled_opportunity("T1", 0),
            create_scheduled_opportunity("T2", 60),
        ]

        metrics = compute_metrics(schedule, opps, config, runtime_s=0.2)

        assert metrics.accepted == 2
        assert metrics.rejected == 1


class TestComputeMetricsValues:
    """Tests for compute_metrics value calculations."""

    def test_total_value(self) -> None:
        config = SchedulerConfig()
        opps = [create_test_opportunity("T1")]
        schedule = [
            create_scheduled_opportunity("T1", 0, value=0.9),
            create_scheduled_opportunity("T2", 30, value=0.7),
        ]

        metrics = compute_metrics(schedule, opps, config, runtime_s=0.1)

        assert metrics.total_value == pytest.approx(1.6)
        assert metrics.mean_value == pytest.approx(0.8)


class TestComputeMetricsGeometry:
    """Tests for compute_metrics geometry calculations."""

    def test_incidence_angles(self) -> None:
        config = SchedulerConfig()
        opps = [create_test_opportunity("T1")]
        schedule = [
            create_scheduled_opportunity("T1", 0, incidence=20.0),
            create_scheduled_opportunity("T2", 30, incidence=40.0),
        ]

        metrics = compute_metrics(schedule, opps, config, runtime_s=0.1)

        assert metrics.min_incidence_deg == 20.0
        assert metrics.max_incidence_deg == 40.0
        assert metrics.mean_incidence_deg == pytest.approx(30.0)

    def test_roll_angles(self) -> None:
        config = SchedulerConfig()
        opps = [create_test_opportunity("T1")]
        schedule = [
            create_scheduled_opportunity("T1", 0, roll=15.0),
            create_scheduled_opportunity("T2", 30, roll=-25.0),
        ]

        metrics = compute_metrics(schedule, opps, config, runtime_s=0.1)

        # Roll uses absolute values
        assert metrics.max_roll_deg == 25.0
        assert metrics.total_roll_used_deg == 40.0

    def test_pitch_angles(self) -> None:
        config = SchedulerConfig()
        opps = [create_test_opportunity("T1")]
        schedule = [
            create_scheduled_opportunity("T1", 0, pitch=5.0),
            create_scheduled_opportunity("T2", 30, pitch=-10.0),
        ]

        metrics = compute_metrics(schedule, opps, config, runtime_s=0.1)

        assert metrics.max_pitch_deg == 10.0
        assert metrics.opps_using_pitch == 2


class TestComputeMetricsTiming:
    """Tests for compute_metrics timing calculations."""

    def test_maneuver_time(self) -> None:
        config = SchedulerConfig()
        opps = [create_test_opportunity("T1")]
        sched1 = create_scheduled_opportunity("T1", 0)
        sched2 = create_scheduled_opportunity("T2", 30)

        metrics = compute_metrics([sched1, sched2], opps, config, runtime_s=0.1)

        # Each scheduled opp has maneuver_time=5.0
        assert metrics.total_maneuver_time_s == 10.0

    def test_slack_time(self) -> None:
        config = SchedulerConfig()
        opps = [create_test_opportunity("T1")]
        sched1 = create_scheduled_opportunity("T1", 0)
        sched2 = create_scheduled_opportunity("T2", 30)

        metrics = compute_metrics([sched1, sched2], opps, config, runtime_s=0.1)

        # Each scheduled opp has slack_time=2.0
        assert metrics.total_slack_time_s == 4.0


class TestAlgorithmMetricsDefaults:
    """Tests for AlgorithmMetrics default values."""

    def test_default_values(self) -> None:
        metrics = AlgorithmMetrics()

        assert metrics.accepted == 0
        assert metrics.rejected == 0
        assert metrics.total_value == 0.0
        assert metrics.runtime_ms == 0.0


class TestInvariantCheck:
    """Tests for InvariantCheck dataclass."""

    def test_ok_check(self) -> None:
        check = InvariantCheck(name="test", ok=True)

        assert check.ok is True
        assert check.details is None

    def test_failed_check(self) -> None:
        check = InvariantCheck(name="test", ok=False, details="Something went wrong")

        assert check.ok is False
        assert check.details == "Something went wrong"

    def test_with_affected_items(self) -> None:
        check = InvariantCheck(
            name="test",
            ok=False,
            details="Issues found",
            affected_items=["item1", "item2"],
        )

        assert len(check.affected_items) == 2


class TestCheckQualityConsistency:
    """Tests for check_quality_consistency function."""

    def test_empty_inputs(self) -> None:
        result = check_quality_consistency([], [], "off")

        assert result.ok is True
        assert result.name == "quality_consistency"

    def test_no_rejected(self) -> None:
        schedule = [create_scheduled_opportunity("T1")]

        result = check_quality_consistency(schedule, [], "off")

        assert result.ok is True

    def test_consistent_quality(self) -> None:
        # Schedule has better quality than rejected
        schedule = [
            create_scheduled_opportunity("T1", 0, value=0.9, incidence=20.0),
        ]
        rejected = [
            create_test_opportunity("T1", 30, value=0.5, incidence=40.0),
        ]

        result = check_quality_consistency(schedule, rejected, "off")

        assert result.ok is True
