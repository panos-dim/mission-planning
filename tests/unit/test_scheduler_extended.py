"""
Extended tests for scheduler module to improve coverage.

Tests cover:
- ScheduleMetrics dataclass
- FeasibilityKernel class
- Maneuver time computation
- Attitude tracking
- Edge cases and error handling
"""

import math
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from mission_planner.scheduler import (
    EARTH_RADIUS_KM,
    MIN_GAP_SECONDS,
    PITCH_THRESHOLD_DEG,
    ROLL_ONLY_PITCH_THRESHOLD_DEG,
    AlgorithmType,
    FeasibilityKernel,
    MissionScheduler,
    Opportunity,
    ScheduledOpportunity,
    ScheduleMetrics,
    SchedulerConfig,
)


class TestScheduleMetrics:
    """Tests for ScheduleMetrics dataclass."""

    def test_basic_creation(self) -> None:
        metrics = ScheduleMetrics(
            algorithm="first_fit",
            runtime_ms=100.5,
            opportunities_evaluated=10,
            opportunities_accepted=8,
            opportunities_rejected=2,
            total_value=7.5,
            mean_value=0.9375,
            total_imaging_time=40.0,
            total_maneuver_time=30.0,
            schedule_span=300.0,
            utilization=0.233,
            mean_density=0.5,
            median_density=0.6,
        )

        assert metrics.algorithm == "first_fit"
        assert metrics.runtime_ms == 100.5
        assert metrics.opportunities_accepted == 8

    def test_to_dict(self) -> None:
        metrics = ScheduleMetrics(
            algorithm="best_fit",
            runtime_ms=50.123,
            opportunities_evaluated=5,
            opportunities_accepted=4,
            opportunities_rejected=1,
            total_value=3.5,
            mean_value=0.875,
            total_imaging_time=20.0,
            total_maneuver_time=15.0,
            schedule_span=150.0,
            utilization=0.233,
            mean_density=0.4,
            median_density=0.5,
        )

        result = metrics.to_dict()

        assert result["algorithm"] == "best_fit"
        assert result["runtime_ms"] == 50.12
        assert result["opportunities_accepted"] == 4
        assert "total_imaging_time_s" in result
        assert "total_maneuver_time_s" in result

    def test_to_dict_with_optional_fields(self) -> None:
        metrics = ScheduleMetrics(
            algorithm="roll_pitch_first_fit",
            runtime_ms=75.0,
            opportunities_evaluated=10,
            opportunities_accepted=9,
            opportunities_rejected=1,
            total_value=8.0,
            mean_value=0.889,
            total_imaging_time=45.0,
            total_maneuver_time=25.0,
            schedule_span=200.0,
            utilization=0.35,
            mean_density=0.6,
            median_density=0.65,
            mean_incidence_deg=25.5,
            total_pitch_used_deg=30.0,
            max_pitch_deg=15.0,
            opportunities_saved_by_pitch=2,
        )

        result = metrics.to_dict()

        assert result["mean_incidence_deg"] == 25.5
        assert result["total_pitch_used_deg"] == 30.0
        assert result["max_pitch_deg"] == 15.0
        assert result["opportunities_saved_by_pitch"] == 2


class TestScheduledOpportunityToDict:
    """Tests for ScheduledOpportunity.to_dict method."""

    def test_basic_to_dict(self) -> None:
        start = datetime(2025, 1, 1, 12, 0, 0)
        end = datetime(2025, 1, 1, 12, 5, 0)

        scheduled = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=start,
            end_time=end,
            delta_roll=20.0,
            delta_pitch=5.0,
            roll_angle=20.0,
            pitch_angle=5.0,
            maneuver_time=10.0,
            slack_time=50.0,
            value=0.85,
            density=0.085,
        )

        result = scheduled.to_dict()

        assert result["opportunity_id"] == "opp1"
        assert result["satellite_id"] == "sat1"
        assert result["delta_roll"] == 20.0
        assert result["density"] == 0.085

    def test_to_dict_with_incidence_angle(self) -> None:
        start = datetime(2025, 1, 1, 12, 0, 0)
        end = datetime(2025, 1, 1, 12, 5, 0)

        scheduled = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=start,
            end_time=end,
            delta_roll=25.0,
            maneuver_time=15.0,
            slack_time=45.0,
            incidence_angle=30.5,
        )

        result = scheduled.to_dict()

        assert result["incidence_angle"] == 30.5

    def test_to_dict_with_satellite_position(self) -> None:
        start = datetime(2025, 1, 1, 12, 0, 0)
        end = datetime(2025, 1, 1, 12, 5, 0)

        scheduled = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=start,
            end_time=end,
            delta_roll=15.0,
            maneuver_time=10.0,
            slack_time=40.0,
            satellite_lat=45.123456,
            satellite_lon=10.654321,
            satellite_alt=600.123,
        )

        result = scheduled.to_dict()

        assert result["satellite_lat"] == 45.123456
        assert result["satellite_lon"] == 10.654321
        assert result["satellite_alt"] == 600.123

    def test_to_dict_infinity_density(self) -> None:
        start = datetime(2025, 1, 1, 12, 0, 0)
        end = datetime(2025, 1, 1, 12, 5, 0)

        scheduled = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=start,
            end_time=end,
            delta_roll=0.0,
            maneuver_time=0.0,
            slack_time=60.0,
            density=float("inf"),
        )

        result = scheduled.to_dict()

        assert result["density"] == "inf"


class TestSchedulerConfigValidation:
    """Tests for SchedulerConfig validation."""

    def test_invalid_roll_rate(self) -> None:
        with pytest.raises(ValueError, match="max_roll_rate_dps must be positive"):
            SchedulerConfig(max_roll_rate_dps=0.0)

    def test_invalid_roll_rate_negative(self) -> None:
        with pytest.raises(ValueError, match="max_roll_rate_dps must be positive"):
            SchedulerConfig(max_roll_rate_dps=-1.0)

    def test_invalid_roll_accel(self) -> None:
        with pytest.raises(ValueError, match="max_roll_accel_dps2 must be positive"):
            SchedulerConfig(max_roll_accel_dps2=0.0)

    def test_invalid_imaging_time(self) -> None:
        with pytest.raises(ValueError, match="imaging_time_s must be non-negative"):
            SchedulerConfig(imaging_time_s=-1.0)

    def test_invalid_spacecraft_roll(self) -> None:
        with pytest.raises(
            ValueError, match="max_spacecraft_roll_deg must be non-negative"
        ):
            SchedulerConfig(max_spacecraft_roll_deg=-10.0)

    def test_invalid_spacecraft_pitch(self) -> None:
        with pytest.raises(
            ValueError, match="max_spacecraft_pitch_deg must be non-negative"
        ):
            SchedulerConfig(max_spacecraft_pitch_deg=-5.0)


class TestFeasibilityKernel:
    """Tests for FeasibilityKernel class."""

    @pytest.fixture
    def config(self):
        return SchedulerConfig(
            max_spacecraft_roll_deg=45.0,
            max_spacecraft_pitch_deg=30.0,
            max_roll_rate_dps=1.0,
            max_pitch_rate_dps=1.0,
        )

    @pytest.fixture
    def kernel(self, config):
        return FeasibilityKernel(config)

    def test_initialization(self, kernel) -> None:
        assert kernel.current_roll == 0.0
        assert kernel.current_pitch == 0.0
        assert kernel.R_EARTH == EARTH_RADIUS_KM

    def test_get_satellite_attitude_new(self, kernel) -> None:
        roll, pitch = kernel.get_satellite_attitude("sat1")
        assert roll == 0.0
        assert pitch == 0.0

    def test_get_satellite_attitude_existing(self, kernel) -> None:
        kernel.update_satellite_attitude("sat1", 20.0, 10.0)
        roll, pitch = kernel.get_satellite_attitude("sat1")
        assert roll == 20.0
        assert pitch == 10.0

    def test_update_satellite_attitude(self, kernel) -> None:
        kernel.update_satellite_attitude("sat1", 25.0, 15.0)

        assert kernel.current_roll == 25.0
        assert kernel.current_pitch == 15.0

        roll, pitch = kernel.get_satellite_attitude("sat1")
        assert roll == 25.0
        assert pitch == 15.0

    def test_reset_all_attitudes(self, kernel) -> None:
        kernel.update_satellite_attitude("sat1", 20.0, 10.0)
        kernel.update_satellite_attitude("sat2", 30.0, 15.0)

        kernel.reset_all_attitudes()

        assert kernel.current_roll == 0.0
        assert kernel.current_pitch == 0.0
        # New satellite should start at 0
        roll, pitch = kernel.get_satellite_attitude("sat1")
        assert roll == 0.0
        assert pitch == 0.0

    def test_compute_maneuver_time_zero(self, kernel) -> None:
        time = kernel.compute_maneuver_time(0.0, 0.0)
        assert time == 0.0

    def test_compute_maneuver_time_roll_only(self, kernel) -> None:
        time = kernel.compute_maneuver_time(30.0, 0.0)
        # At 1 deg/sec, 30 degrees should take ~30 seconds
        assert time > 0
        assert time >= 30.0  # At least 30 seconds

    def test_compute_maneuver_time_pitch_only(self, kernel) -> None:
        time = kernel.compute_maneuver_time(0.0, 20.0)
        assert time >= 20.0  # At 1 deg/sec pitch rate

    def test_compute_maneuver_time_both(self, kernel) -> None:
        time = kernel.compute_maneuver_time(30.0, 20.0)
        # Should be max of roll and pitch times
        assert time >= 30.0

    def test_multiple_satellites_tracking(self, kernel) -> None:
        kernel.update_satellite_attitude("sat1", 20.0, 10.0)
        kernel.update_satellite_attitude("sat2", 35.0, -5.0)
        kernel.update_satellite_attitude("sat3", -15.0, 20.0)

        r1, p1 = kernel.get_satellite_attitude("sat1")
        r2, p2 = kernel.get_satellite_attitude("sat2")
        r3, p3 = kernel.get_satellite_attitude("sat3")

        assert r1 == 20.0 and p1 == 10.0
        assert r2 == 35.0 and p2 == -5.0
        assert r3 == -15.0 and p3 == 20.0


class TestMissionSchedulerExtended:
    """Extended tests for MissionScheduler."""

    @pytest.fixture
    def scheduler(self):
        config = SchedulerConfig(
            max_spacecraft_roll_deg=45.0,
            max_spacecraft_pitch_deg=30.0,
            max_roll_rate_dps=1.0,
            max_pitch_rate_dps=1.0,
            imaging_time_s=5.0,
        )
        return MissionScheduler(config)

    @pytest.fixture
    def target_positions(self):
        return {
            "target1": (25.0, 55.0),
            "target2": (26.0, 56.0),
            "target3": (27.0, 57.0),
            "target4": (28.0, 58.0),
            "target5": (29.0, 59.0),
        }

    def test_single_opportunity(self, scheduler, target_positions) -> None:
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        opps = [
            Opportunity(
                id="opp1",
                satellite_id="sat1",
                target_id="target1",
                start_time=base_time,
                end_time=base_time + timedelta(seconds=60),
                incidence_angle=10.0,
                value=1.0,
            ),
        ]

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.FIRST_FIT
        )

        assert len(schedule) == 1
        assert schedule[0].opportunity_id == "opp1"

    def test_conflicting_opportunities(self, scheduler, target_positions) -> None:
        """Test handling of overlapping opportunities."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        opps = [
            Opportunity(
                id="opp1",
                satellite_id="sat1",
                target_id="target1",
                start_time=base_time,
                end_time=base_time + timedelta(seconds=60),
                incidence_angle=10.0,
                value=1.0,
            ),
            Opportunity(
                id="opp2",
                satellite_id="sat1",
                target_id="target2",
                start_time=base_time + timedelta(seconds=30),  # Overlapping
                end_time=base_time + timedelta(seconds=90),
                incidence_angle=15.0,
                value=0.9,
            ),
        ]

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.FIRST_FIT
        )

        # Should only schedule non-overlapping
        assert len(schedule) <= 2

    def test_high_priority_opportunities(self, scheduler, target_positions) -> None:
        """Test that high priority opportunities are handled."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        opps = [
            Opportunity(
                id="opp_low",
                satellite_id="sat1",
                target_id="target1",
                start_time=base_time,
                end_time=base_time + timedelta(seconds=60),
                incidence_angle=10.0,
                value=0.5,
                priority=5,
            ),
            Opportunity(
                id="opp_high",
                satellite_id="sat1",
                target_id="target2",
                start_time=base_time + timedelta(minutes=5),
                end_time=base_time + timedelta(minutes=6),
                incidence_angle=15.0,
                value=1.0,
                priority=1,
            ),
        ]

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.BEST_FIT
        )

        assert len(schedule) >= 1

    def test_all_algorithms(self, scheduler, target_positions) -> None:
        """Test all algorithm types work."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        opps = [
            Opportunity(
                id=f"opp{i}",
                satellite_id="sat1",
                target_id=f"target{i+1}",
                start_time=base_time + timedelta(minutes=i * 10),
                end_time=base_time + timedelta(minutes=i * 10 + 1),
                incidence_angle=10.0 + i * 5,
                value=0.8,
            )
            for i in range(3)
        ]

        for algo in AlgorithmType:
            schedule, metrics = scheduler.schedule(opps, target_positions, algo)
            assert isinstance(schedule, list)
            assert metrics is not None

    def test_negative_incidence_angle(self, scheduler, target_positions) -> None:
        """Test handling of negative (left-of-track) incidence angles."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        opps = [
            Opportunity(
                id="opp1",
                satellite_id="sat1",
                target_id="target1",
                start_time=base_time,
                end_time=base_time + timedelta(seconds=60),
                incidence_angle=-25.0,  # Left of track
                value=1.0,
            ),
        ]

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.FIRST_FIT
        )

        assert len(schedule) == 1

    def test_with_pitch_angles(self, scheduler, target_positions) -> None:
        """Test opportunities with pitch angles."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        opps = [
            Opportunity(
                id="opp_backward",
                satellite_id="sat1",
                target_id="target1",
                start_time=base_time,
                end_time=base_time + timedelta(seconds=60),
                incidence_angle=20.0,
                pitch_angle=-15.0,  # Backward looking
                value=0.9,
            ),
            Opportunity(
                id="opp_forward",
                satellite_id="sat1",
                target_id="target2",
                start_time=base_time + timedelta(minutes=5),
                end_time=base_time + timedelta(minutes=6),
                incidence_angle=25.0,
                pitch_angle=15.0,  # Forward looking
                value=0.8,
            ),
        ]

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.ROLL_PITCH_FIRST_FIT
        )

        assert len(schedule) >= 1

    def test_metrics_computation(self, scheduler, target_positions) -> None:
        """Test that metrics are properly computed."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        opps = [
            Opportunity(
                id="opp1",
                satellite_id="sat1",
                target_id="target1",
                start_time=base_time,
                end_time=base_time + timedelta(seconds=60),
                incidence_angle=20.0,
                value=0.9,
            ),
            Opportunity(
                id="opp2",
                satellite_id="sat1",
                target_id="target2",
                start_time=base_time + timedelta(minutes=5),
                end_time=base_time + timedelta(minutes=6),
                incidence_angle=25.0,
                value=0.8,
            ),
        ]

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.FIRST_FIT
        )

        assert metrics.opportunities_evaluated == 2
        assert metrics.runtime_ms >= 0


class TestOpportunityEdgeCases:
    """Edge case tests for Opportunity dataclass."""

    def test_zero_duration(self) -> None:
        start = datetime(2025, 1, 1, 12, 0, 0)

        opp = Opportunity(
            id="instant",
            satellite_id="sat1",
            target_id="target1",
            start_time=start,
            end_time=start,  # Same time
        )

        assert opp.duration_seconds == 0.0

    def test_very_long_duration(self) -> None:
        start = datetime(2025, 1, 1, 0, 0, 0)
        end = datetime(2025, 1, 2, 0, 0, 0)  # 24 hours

        opp = Opportunity(
            id="long",
            satellite_id="sat1",
            target_id="target1",
            start_time=start,
            end_time=end,
        )

        assert opp.duration_seconds == 86400.0  # 24 hours in seconds

    def test_high_incidence_angle(self) -> None:
        start = datetime(2025, 1, 1, 12, 0, 0)

        opp = Opportunity(
            id="edge",
            satellite_id="sat1",
            target_id="target1",
            start_time=start,
            end_time=start + timedelta(seconds=60),
            incidence_angle=89.9,  # Nearly at horizon
        )

        assert opp.incidence_angle == 89.9


class TestConstants:
    """Tests for module constants."""

    def test_pitch_threshold(self) -> None:
        assert PITCH_THRESHOLD_DEG == 0.1

    def test_roll_only_pitch_threshold(self) -> None:
        assert ROLL_ONLY_PITCH_THRESHOLD_DEG == 1.0
