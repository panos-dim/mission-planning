"""
Advanced tests for scheduler module.

Tests cover:
- MissionScheduler initialization
- Algorithm dispatching
- Satellite lookup methods
- Scheduling algorithms
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
    SchedulerConfig,
)


def create_mock_satellite(name="TEST-SAT"):
    """Create a mock satellite."""
    sat = MagicMock()
    sat.satellite_name = name
    sat.get_position = MagicMock(return_value=(45.0, 10.0, 600.0))
    return sat


def create_opportunity(
    target_id, start_offset_min=0, elevation=45.0, satellite_id="SAT1"
):
    """Create a test opportunity."""
    base_time = datetime(2025, 1, 15, 12, 0, 0)
    start = base_time + timedelta(minutes=start_offset_min)
    end = start + timedelta(minutes=10)

    return Opportunity(
        id=f"opp_{target_id}_{start_offset_min}",
        target_id=target_id,
        satellite_id=satellite_id,
        start_time=start,
        end_time=end,
        max_elevation=elevation,
        incidence_angle=30.0,
        value=0.8,
    )


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

    def test_init_with_satellites_dict(self) -> None:
        config = SchedulerConfig()
        satellites = {
            "SAT1": create_mock_satellite("SAT1"),
            "SAT2": create_mock_satellite("SAT2"),
        }

        scheduler = MissionScheduler(config, satellites=satellites)

        assert len(scheduler.satellites) == 2

    def test_kernel_created(self) -> None:
        config = SchedulerConfig()

        scheduler = MissionScheduler(config)

        assert scheduler.kernel is not None
        assert isinstance(scheduler.kernel, FeasibilityKernel)


class TestGetSatelliteForOpportunity:
    """Tests for _get_satellite_for_opportunity method."""

    @pytest.fixture
    def scheduler_with_satellites(self):
        config = SchedulerConfig()
        satellites = {
            "SAT1": create_mock_satellite("SAT1"),
            "sat_SAT2": create_mock_satellite("SAT2"),
        }
        return MissionScheduler(config, satellites=satellites)

    def test_exact_match(self, scheduler_with_satellites) -> None:
        sat = scheduler_with_satellites._get_satellite_for_opportunity("SAT1")

        assert sat is not None
        assert sat.satellite_name == "SAT1"

    def test_prefixed_match(self, scheduler_with_satellites) -> None:
        # Looking for "SAT2" should find "sat_SAT2"
        sat = scheduler_with_satellites._get_satellite_for_opportunity("SAT2")

        assert sat is not None

    def test_fallback_to_legacy(self) -> None:
        config = SchedulerConfig()
        legacy_sat = create_mock_satellite("LEGACY")
        scheduler = MissionScheduler(config, satellite=legacy_sat, satellites={})

        sat = scheduler._get_satellite_for_opportunity("UNKNOWN")

        assert sat == legacy_sat


class TestScheduleMethodDispatching:
    """Tests for schedule method algorithm dispatching."""

    @pytest.fixture
    def scheduler(self):
        config = SchedulerConfig()
        return MissionScheduler(config)

    def test_first_fit_algorithm(self, scheduler) -> None:
        opps = [create_opportunity("T1", 0)]
        target_positions = {"T1": (45.0, 10.0)}

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.FIRST_FIT
        )

        assert metrics.algorithm == "first_fit"

    def test_best_fit_algorithm(self, scheduler) -> None:
        opps = [create_opportunity("T1", 0)]
        target_positions = {"T1": (45.0, 10.0)}

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.BEST_FIT
        )

        assert metrics.algorithm == "best_fit"

    def test_roll_pitch_first_fit_algorithm(self, scheduler) -> None:
        opps = [create_opportunity("T1", 0)]
        target_positions = {"T1": (45.0, 10.0)}

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.ROLL_PITCH_FIRST_FIT
        )

        assert metrics.algorithm == "roll_pitch_first_fit"

    def test_roll_pitch_best_fit_algorithm(self, scheduler) -> None:
        opps = [create_opportunity("T1", 0)]
        target_positions = {"T1": (45.0, 10.0)}

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.ROLL_PITCH_BEST_FIT
        )

        assert metrics.algorithm == "roll_pitch_best_fit"


class TestScheduleMetrics:
    """Tests for schedule metrics computation."""

    @pytest.fixture
    def scheduler(self):
        config = SchedulerConfig()
        return MissionScheduler(config)

    def test_empty_schedule_metrics(self, scheduler) -> None:
        schedule, metrics = scheduler.schedule([], {}, AlgorithmType.FIRST_FIT)

        assert metrics.opportunities_evaluated == 0
        assert metrics.opportunities_accepted == 0

    def test_metrics_have_runtime(self, scheduler) -> None:
        opps = [create_opportunity("T1", 0)]
        target_positions = {"T1": (45.0, 10.0)}

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.FIRST_FIT
        )

        assert metrics.runtime_ms >= 0


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
        config = SchedulerConfig(max_roll_rate_dps=1.0, max_roll_accel_dps2=0.5)
        return FeasibilityKernel(config)

    def test_zero_angle_zero_time(self, kernel) -> None:
        time = kernel.compute_maneuver_time(0.0)

        assert time == 0.0

    def test_small_angle_maneuver(self, kernel) -> None:
        time = kernel.compute_maneuver_time(5.0)

        assert time > 0

    def test_larger_angle_takes_longer(self, kernel) -> None:
        time_small = kernel.compute_maneuver_time(10.0)
        time_large = kernel.compute_maneuver_time(30.0)

        assert time_large > time_small

    def test_with_pitch_component(self, kernel) -> None:
        time_roll_only = kernel.compute_maneuver_time(20.0, 0.0)
        time_with_pitch = kernel.compute_maneuver_time(20.0, 10.0)

        # With pitch should take at least as long
        assert time_with_pitch >= time_roll_only


class TestAlgorithmType:
    """Tests for AlgorithmType enum."""

    def test_first_fit_value(self) -> None:
        assert AlgorithmType.FIRST_FIT.value == "first_fit"

    def test_best_fit_value(self) -> None:
        assert AlgorithmType.BEST_FIT.value == "best_fit"

    def test_roll_pitch_first_fit_value(self) -> None:
        assert AlgorithmType.ROLL_PITCH_FIRST_FIT.value == "roll_pitch_first_fit"

    def test_roll_pitch_best_fit_value(self) -> None:
        assert AlgorithmType.ROLL_PITCH_BEST_FIT.value == "roll_pitch_best_fit"


class TestSchedulerConfigDefaults:
    """Tests for SchedulerConfig default values."""

    def test_default_imaging_time(self) -> None:
        config = SchedulerConfig()

        assert config.imaging_time_s > 0

    def test_default_roll_limit(self) -> None:
        config = SchedulerConfig()

        assert config.max_spacecraft_roll_deg > 0

    def test_default_pitch_limit(self) -> None:
        config = SchedulerConfig()

        assert config.max_spacecraft_pitch_deg >= 0

    def test_custom_roll_limit(self) -> None:
        config = SchedulerConfig(max_spacecraft_roll_deg=30.0)

        assert config.max_spacecraft_roll_deg == 30.0


class TestOpportunityDataclass:
    """Tests for Opportunity dataclass."""

    def test_create_opportunity(self) -> None:
        opp = create_opportunity("T1", 0, 60.0)

        assert opp.target_id == "T1"
        assert opp.max_elevation == 60.0

    def test_opportunity_has_required_fields(self) -> None:
        opp = create_opportunity("T1", 0)

        assert hasattr(opp, "id")
        assert hasattr(opp, "target_id")
        assert hasattr(opp, "satellite_id")
        assert hasattr(opp, "start_time")
        assert hasattr(opp, "end_time")
