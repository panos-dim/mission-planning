"""
Tests for scheduler.py algorithm methods.

Tests cover:
- FeasibilityKernel roll/pitch calculations
- Algorithm dispatch
- Schedule optimization
"""

import math
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from mission_planner.scheduler import (
    AlgorithmType,
    FeasibilityKernel,
    MissionScheduler,
    Opportunity,
    ScheduledOpportunity,
    SchedulerConfig,
)


def create_test_opportunity(
    target_id, offset_min=0, value=0.8, incidence=30.0, elevation=60.0
):
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
        max_elevation=elevation,
        incidence_angle=incidence,
        value=value,
    )


def create_mock_satellite():
    """Create a mock satellite."""
    sat = MagicMock()
    sat.satellite_name = "TEST-SAT"
    sat.get_position = MagicMock(return_value=(45.0, 10.0, 600.0))
    return sat


class TestFeasibilityKernelRollCalculation:
    """Tests for FeasibilityKernel roll angle calculation."""

    @pytest.fixture
    def kernel(self):
        config = SchedulerConfig(max_roll_rate_dps=1.0)
        return FeasibilityKernel(config)

    def test_nadir_roll_near_zero(self, kernel) -> None:
        # Target directly below satellite
        roll = kernel.compute_roll_angle_from_satellite(
            target_position=(45.0, 10.0), satellite_position=(45.0, 10.0, 600.0)
        )

        assert roll == pytest.approx(0.0, abs=1.0)

    def test_off_nadir_positive_roll(self, kernel) -> None:
        roll = kernel.compute_roll_angle_from_satellite(
            target_position=(46.0, 10.0), satellite_position=(45.0, 10.0, 600.0)
        )

        assert roll > 0

    def test_roll_increases_with_distance(self, kernel) -> None:
        roll_close = kernel.compute_roll_angle_from_satellite(
            target_position=(45.5, 10.0), satellite_position=(45.0, 10.0, 600.0)
        )
        roll_far = kernel.compute_roll_angle_from_satellite(
            target_position=(47.0, 10.0), satellite_position=(45.0, 10.0, 600.0)
        )

        assert roll_far > roll_close


class TestFeasibilityKernelManeuverTime:
    """Tests for FeasibilityKernel maneuver time calculation."""

    @pytest.fixture
    def kernel(self):
        config = SchedulerConfig(max_roll_rate_dps=2.0)
        return FeasibilityKernel(config)

    def test_zero_angle_zero_time(self, kernel) -> None:
        time = kernel.compute_maneuver_time(0.0)

        assert time == 0.0

    def test_maneuver_time_proportional(self, kernel) -> None:
        time_small = kernel.compute_maneuver_time(10.0)
        time_large = kernel.compute_maneuver_time(30.0)

        # Time should scale with angle
        assert time_large > time_small

    def test_negative_angle_same_as_positive(self, kernel) -> None:
        time_pos = kernel.compute_maneuver_time(20.0)
        time_neg = kernel.compute_maneuver_time(-20.0)

        assert time_pos == time_neg


class TestSchedulerAlgorithmDispatch:
    """Tests for scheduler algorithm dispatch."""

    @pytest.fixture
    def scheduler(self):
        config = SchedulerConfig()
        return MissionScheduler(config)

    def test_first_fit_dispatch(self, scheduler) -> None:
        opps = [create_test_opportunity("T1")]
        target_positions = {"T1": (45.0, 10.0)}

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.FIRST_FIT
        )

        assert metrics.algorithm == "first_fit"

    def test_best_fit_dispatch(self, scheduler) -> None:
        opps = [create_test_opportunity("T1")]
        target_positions = {"T1": (45.0, 10.0)}

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.BEST_FIT
        )

        assert metrics.algorithm == "best_fit"

    def test_roll_pitch_first_fit_dispatch(self, scheduler) -> None:
        opps = [create_test_opportunity("T1")]
        target_positions = {"T1": (45.0, 10.0)}

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.ROLL_PITCH_FIRST_FIT
        )

        assert metrics.algorithm == "roll_pitch_first_fit"

    def test_roll_pitch_best_fit_dispatch(self, scheduler) -> None:
        opps = [create_test_opportunity("T1")]
        target_positions = {"T1": (45.0, 10.0)}

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.ROLL_PITCH_BEST_FIT
        )

        assert metrics.algorithm == "roll_pitch_best_fit"


class TestSchedulerWithSatellite:
    """Tests for scheduler with satellite object."""

    def test_scheduler_with_satellite(self) -> None:
        config = SchedulerConfig()
        sat = create_mock_satellite()
        scheduler = MissionScheduler(config, satellite=sat)

        assert scheduler.satellite == sat

    def test_kernel_with_satellite(self) -> None:
        config = SchedulerConfig()
        sat = create_mock_satellite()
        kernel = FeasibilityKernel(config, sat)

        assert kernel.satellite == sat


class TestSchedulerConfigOptions:
    """Tests for SchedulerConfig options."""

    def test_default_imaging_time(self) -> None:
        config = SchedulerConfig()

        assert config.imaging_time_s > 0

    def test_custom_imaging_time(self) -> None:
        config = SchedulerConfig(imaging_time_s=5.0)

        assert config.imaging_time_s == 5.0

    def test_default_roll_limit(self) -> None:
        config = SchedulerConfig()

        assert config.max_spacecraft_roll_deg > 0

    def test_custom_roll_limit(self) -> None:
        config = SchedulerConfig(max_spacecraft_roll_deg=30.0)

        assert config.max_spacecraft_roll_deg == 30.0

    def test_default_pitch_limit(self) -> None:
        config = SchedulerConfig()

        assert hasattr(config, "max_spacecraft_pitch_deg")


class TestSchedulerMultipleOpportunities:
    """Tests for scheduler with multiple opportunities."""

    @pytest.fixture
    def scheduler(self):
        config = SchedulerConfig()
        return MissionScheduler(config)

    def test_multiple_targets(self, scheduler) -> None:
        opps = [
            create_test_opportunity("T1", 0, value=0.9),
            create_test_opportunity("T2", 20, value=0.8),
            create_test_opportunity("T3", 40, value=0.7),
        ]
        target_positions = {
            "T1": (45.0, 10.0),
            "T2": (46.0, 11.0),
            "T3": (47.0, 12.0),
        }

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.FIRST_FIT
        )

        assert metrics.opportunities_evaluated == 3

    def test_overlapping_opportunities(self, scheduler) -> None:
        # Create overlapping opportunities
        opps = [
            create_test_opportunity("T1", 0, value=0.9),
            create_test_opportunity("T2", 5, value=0.8),  # Overlaps with T1
        ]
        target_positions = {
            "T1": (45.0, 10.0),
            "T2": (46.0, 11.0),
        }

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.FIRST_FIT
        )

        # Some may be rejected due to overlap
        assert metrics.opportunities_evaluated == 2


class TestOpportunityDataclass:
    """Tests for Opportunity dataclass."""

    def test_create_opportunity(self) -> None:
        opp = create_test_opportunity("T1", 0, 0.9, 25.0)

        assert opp.target_id == "T1"
        assert opp.value == 0.9
        assert opp.incidence_angle == 25.0

    def test_opportunity_time_window(self) -> None:
        opp = create_test_opportunity("T1", 0)

        assert opp.end_time > opp.start_time

    def test_opportunity_duration(self) -> None:
        opp = create_test_opportunity("T1", 0)

        duration = (opp.end_time - opp.start_time).total_seconds()
        assert duration == 600  # 10 minutes


class TestScheduledOpportunityDataclass:
    """Tests for ScheduledOpportunity dataclass."""

    def test_create_scheduled_opportunity(self) -> None:
        base = datetime(2025, 1, 15, 12, 0, 0)
        sched = ScheduledOpportunity(
            opportunity_id="opp_1",
            target_id="T1",
            satellite_id="SAT1",
            start_time=base,
            end_time=base + timedelta(minutes=10),
            delta_roll=15.0,
            delta_pitch=5.0,
            roll_angle=15.0,
            pitch_angle=5.0,
            maneuver_time=10.0,
            slack_time=5.0,
            value=0.9,
        )

        assert sched.target_id == "T1"
        assert sched.roll_angle == 15.0

    def test_scheduled_opportunity_to_dict(self) -> None:
        base = datetime(2025, 1, 15, 12, 0, 0)
        sched = ScheduledOpportunity(
            opportunity_id="opp_1",
            target_id="T1",
            satellite_id="SAT1",
            start_time=base,
            end_time=base + timedelta(minutes=10),
            delta_roll=15.0,
        )

        result = sched.to_dict()

        assert isinstance(result, dict)
        assert "opportunity_id" in result
        assert result["target_id"] == "T1"
