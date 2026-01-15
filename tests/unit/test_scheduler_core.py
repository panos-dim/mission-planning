"""
Core tests for scheduler.py module.

Tests cover:
- MissionScheduler initialization
- SchedulerConfig defaults
- ScheduleMetrics dataclass
- Algorithm execution
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from mission_planner.scheduler import (
    AlgorithmType,
    FeasibilityKernel,
    MissionScheduler,
    Opportunity,
    ScheduledOpportunity,
    ScheduleMetrics,
    SchedulerConfig,
)


def create_mock_satellite():
    """Create a mock satellite for testing."""
    sat = MagicMock()
    sat.satellite_name = "TEST-SAT"
    sat.get_position = MagicMock(return_value=(45.0, 10.0, 600.0))
    return sat


def create_test_opportunity(target_id, offset_min=0, elevation=45.0):
    """Create a test opportunity."""
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
        incidence_angle=30.0,
        value=0.8,
    )


class TestSchedulerConfigDefaults:
    """Tests for SchedulerConfig defaults."""

    def test_default_imaging_time(self) -> None:
        config = SchedulerConfig()
        assert config.imaging_time_s > 0

    def test_default_roll_limit(self) -> None:
        config = SchedulerConfig()
        assert config.max_spacecraft_roll_deg > 0

    def test_default_roll_rate(self) -> None:
        config = SchedulerConfig()
        assert config.max_roll_rate_dps > 0

    def test_custom_values(self) -> None:
        config = SchedulerConfig(max_spacecraft_roll_deg=30.0, max_roll_rate_dps=2.0)
        assert config.max_spacecraft_roll_deg == 30.0
        assert config.max_roll_rate_dps == 2.0


class TestMissionSchedulerInit:
    """Tests for MissionScheduler initialization."""

    def test_init_with_config(self) -> None:
        config = SchedulerConfig()
        scheduler = MissionScheduler(config)
        assert scheduler.config == config

    def test_init_with_satellite(self) -> None:
        config = SchedulerConfig()
        sat = create_mock_satellite()
        scheduler = MissionScheduler(config, satellite=sat)
        assert scheduler.satellite == sat

    def test_init_creates_kernel(self) -> None:
        config = SchedulerConfig()
        scheduler = MissionScheduler(config)
        assert scheduler.kernel is not None


class TestFeasibilityKernelInit:
    """Tests for FeasibilityKernel initialization."""

    def test_init_with_config(self) -> None:
        config = SchedulerConfig()
        kernel = FeasibilityKernel(config)
        assert kernel.config == config

    def test_init_with_satellite(self) -> None:
        config = SchedulerConfig()
        sat = create_mock_satellite()
        kernel = FeasibilityKernel(config, sat)
        assert kernel.satellite == sat


class TestFeasibilityKernelManeuverTime:
    """Tests for compute_maneuver_time method."""

    @pytest.fixture
    def kernel(self):
        config = SchedulerConfig(max_roll_rate_dps=1.0)
        return FeasibilityKernel(config)

    def test_zero_angle(self, kernel) -> None:
        time = kernel.compute_maneuver_time(0.0)
        assert time == 0.0

    def test_positive_angle(self, kernel) -> None:
        time = kernel.compute_maneuver_time(10.0)
        assert time > 0

    def test_larger_angle_takes_longer(self, kernel) -> None:
        time_small = kernel.compute_maneuver_time(10.0)
        time_large = kernel.compute_maneuver_time(30.0)
        assert time_large > time_small


class TestScheduleMethod:
    """Tests for schedule method."""

    @pytest.fixture
    def scheduler(self):
        config = SchedulerConfig()
        return MissionScheduler(config)

    def test_empty_opportunities(self, scheduler) -> None:
        schedule, metrics = scheduler.schedule([], {}, AlgorithmType.FIRST_FIT)
        assert len(schedule) == 0
        assert metrics.opportunities_evaluated == 0

    def test_returns_tuple(self, scheduler) -> None:
        opps = [create_test_opportunity("T1", 0)]
        result = scheduler.schedule(opps, {"T1": (45.0, 10.0)}, AlgorithmType.FIRST_FIT)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_first_fit_algorithm(self, scheduler) -> None:
        opps = [create_test_opportunity("T1", 0)]
        schedule, metrics = scheduler.schedule(
            opps, {"T1": (45.0, 10.0)}, AlgorithmType.FIRST_FIT
        )
        assert metrics.algorithm == "first_fit"

    def test_best_fit_algorithm(self, scheduler) -> None:
        opps = [create_test_opportunity("T1", 0)]
        schedule, metrics = scheduler.schedule(
            opps, {"T1": (45.0, 10.0)}, AlgorithmType.BEST_FIT
        )
        assert metrics.algorithm == "best_fit"


class TestScheduleMetricsDataclass:
    """Tests for ScheduleMetrics dataclass."""

    def test_create_metrics(self) -> None:
        metrics = ScheduleMetrics(
            algorithm="first_fit",
            runtime_ms=10.5,
            opportunities_evaluated=10,
            opportunities_accepted=5,
            opportunities_rejected=5,
            total_value=4.0,
            mean_value=0.8,
            total_imaging_time=300.0,
            total_maneuver_time=60.0,
            schedule_span=600.0,
            utilization=0.6,
            mean_density=0.5,
            median_density=0.4,
        )
        assert metrics.algorithm == "first_fit"
        assert metrics.opportunities_evaluated == 10

    def test_metrics_fields(self) -> None:
        metrics = ScheduleMetrics(
            algorithm="best_fit",
            runtime_ms=5.0,
            opportunities_evaluated=5,
            opportunities_accepted=3,
            opportunities_rejected=2,
            total_value=2.4,
            mean_value=0.8,
            total_imaging_time=180.0,
            total_maneuver_time=30.0,
            schedule_span=400.0,
            utilization=0.525,
            mean_density=0.6,
            median_density=0.5,
        )
        assert metrics.opportunities_accepted == 3
        assert metrics.opportunities_rejected == 2


class TestAlgorithmTypeEnum:
    """Tests for AlgorithmType enum."""

    def test_first_fit_value(self) -> None:
        assert AlgorithmType.FIRST_FIT.value == "first_fit"

    def test_best_fit_value(self) -> None:
        assert AlgorithmType.BEST_FIT.value == "best_fit"

    def test_roll_pitch_first_fit_value(self) -> None:
        assert AlgorithmType.ROLL_PITCH_FIRST_FIT.value == "roll_pitch_first_fit"

    def test_roll_pitch_best_fit_value(self) -> None:
        assert AlgorithmType.ROLL_PITCH_BEST_FIT.value == "roll_pitch_best_fit"


class TestOpportunityDataclass:
    """Tests for Opportunity dataclass."""

    def test_create_opportunity(self) -> None:
        opp = create_test_opportunity("T1", 0, 60.0)
        assert opp.target_id == "T1"
        assert opp.max_elevation == 60.0

    def test_opportunity_fields(self) -> None:
        opp = create_test_opportunity("T2", 30)
        assert hasattr(opp, "id")
        assert hasattr(opp, "target_id")
        assert hasattr(opp, "satellite_id")
        assert hasattr(opp, "start_time")
        assert hasattr(opp, "end_time")
        assert hasattr(opp, "value")


class TestSchedulerWithMultipleOpportunities:
    """Tests for scheduler with multiple opportunities."""

    @pytest.fixture
    def scheduler(self):
        config = SchedulerConfig()
        return MissionScheduler(config)

    def test_multiple_targets(self, scheduler) -> None:
        opps = [
            create_test_opportunity("T1", 0),
            create_test_opportunity("T2", 30),
        ]
        target_positions = {"T1": (45.0, 10.0), "T2": (46.0, 11.0)}

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.FIRST_FIT
        )

        assert metrics.opportunities_evaluated == 2

    def test_same_target_multiple_passes(self, scheduler) -> None:
        opps = [
            create_test_opportunity("T1", 0, 60.0),
            create_test_opportunity("T1", 100, 45.0),
        ]
        target_positions = {"T1": (45.0, 10.0)}

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.BEST_FIT
        )

        assert metrics.opportunities_evaluated == 2
