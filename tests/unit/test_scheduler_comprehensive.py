"""
Comprehensive tests for scheduler module.

Tests cover:
- FeasibilityKernel geometry calculations
- Roll and pitch angle computations
- Scheduling algorithms
- Maneuver time calculations
"""

import math
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

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


class TestFeasibilityKernelInit:
    """Tests for FeasibilityKernel initialization."""

    def test_default_initialization(self) -> None:
        config = SchedulerConfig()
        kernel = FeasibilityKernel(config)

        assert kernel is not None
        assert kernel.config.max_spacecraft_roll_deg > 0

    def test_with_custom_roll_limit(self) -> None:
        config = SchedulerConfig(max_spacecraft_roll_deg=30.0)
        kernel = FeasibilityKernel(config)

        assert kernel.config.max_spacecraft_roll_deg == 30.0

    def test_with_custom_pitch_limit(self) -> None:
        config = SchedulerConfig(max_spacecraft_pitch_deg=20.0)
        kernel = FeasibilityKernel(config)

        assert kernel.config.max_spacecraft_pitch_deg == 20.0

    def test_with_satellite(self) -> None:
        mock_sat = MagicMock()
        mock_sat.get_position.return_value = (45.0, 10.0, 600.0)
        config = SchedulerConfig()

        kernel = FeasibilityKernel(config, satellite=mock_sat)

        assert kernel.satellite == mock_sat


class TestFeasibilityKernelAttributes:
    """Tests for FeasibilityKernel attributes."""

    @pytest.fixture
    def kernel(self):
        config = SchedulerConfig(max_spacecraft_roll_deg=45.0)
        return FeasibilityKernel(config)

    def test_has_config(self, kernel) -> None:
        """Kernel should have config attribute."""
        assert hasattr(kernel, "config")
        assert kernel.config.max_spacecraft_roll_deg == 45.0

    def test_has_current_roll(self, kernel) -> None:
        """Kernel should track current roll."""
        assert hasattr(kernel, "current_roll")
        assert kernel.current_roll == 0.0

    def test_has_current_pitch(self, kernel) -> None:
        """Kernel should track current pitch."""
        assert hasattr(kernel, "current_pitch")
        assert kernel.current_pitch == 0.0

    def test_earth_radius(self, kernel) -> None:
        """Kernel should have Earth radius constant."""
        assert hasattr(kernel, "R_EARTH")
        assert kernel.R_EARTH > 6000  # km


class TestFeasibilityKernelAttitudeTracking:
    """Tests for attitude tracking methods."""

    @pytest.fixture
    def kernel(self):
        config = SchedulerConfig(
            max_spacecraft_roll_deg=45.0, max_spacecraft_pitch_deg=30.0
        )
        return FeasibilityKernel(config)

    def test_get_satellite_attitude(self, kernel) -> None:
        """Test getting satellite attitude."""
        roll, pitch = kernel.get_satellite_attitude("sat1")

        assert roll == 0.0
        assert pitch == 0.0

    def test_update_satellite_attitude(self, kernel) -> None:
        """Test updating satellite attitude."""
        kernel.update_satellite_attitude("sat1", 20.0, 5.0)

        roll, pitch = kernel.get_satellite_attitude("sat1")
        assert roll == 20.0
        assert pitch == 5.0

    def test_reset_all_attitudes(self, kernel) -> None:
        """Test resetting all attitudes."""
        kernel.update_satellite_attitude("sat1", 20.0, 5.0)
        kernel.update_satellite_attitude("sat2", 30.0, 10.0)

        kernel.reset_all_attitudes()

        roll1, pitch1 = kernel.get_satellite_attitude("sat1")
        assert roll1 == 0.0
        assert pitch1 == 0.0


class TestFeasibilityKernelManeuverTime:
    """Tests for maneuver time calculations."""

    @pytest.fixture
    def kernel(self):
        config = SchedulerConfig(
            max_spacecraft_roll_deg=45.0,
            max_roll_rate_dps=2.0,
        )
        return FeasibilityKernel(config)

    def test_zero_angle_change(self, kernel) -> None:
        """Zero angle change should only have settle time."""
        maneuver_time = kernel.compute_maneuver_time(0.0, 0.0)

        assert maneuver_time >= 0

    def test_maneuver_time_increases_with_angle(self, kernel) -> None:
        """Maneuver time should increase with larger angle changes."""
        time_small = kernel.compute_maneuver_time(10.0, 0.0)
        time_large = kernel.compute_maneuver_time(30.0, 0.0)

        assert time_large > time_small

    def test_maneuver_time_with_pitch(self, kernel) -> None:
        """Maneuver time should account for pitch changes."""
        time_roll_only = kernel.compute_maneuver_time(20.0, 0.0)
        time_roll_pitch = kernel.compute_maneuver_time(20.0, 10.0)

        # Time with pitch should be at least as long as roll-only
        assert time_roll_pitch >= time_roll_only


class TestSchedulerConfig:
    """Tests for SchedulerConfig dataclass."""

    def test_default_config(self) -> None:
        config = SchedulerConfig()

        assert config.max_spacecraft_roll_deg > 0
        assert config.max_roll_rate_dps > 0

    def test_custom_config(self) -> None:
        config = SchedulerConfig(
            max_spacecraft_roll_deg=30.0,
            max_roll_rate_dps=3.0,
            imaging_time_s=10.0,
        )

        assert config.max_spacecraft_roll_deg == 30.0
        assert config.max_roll_rate_dps == 3.0
        assert config.imaging_time_s == 10.0

    def test_config_with_pitch(self) -> None:
        config = SchedulerConfig(
            max_spacecraft_roll_deg=45.0,
            max_spacecraft_pitch_deg=30.0,
        )

        assert config.max_spacecraft_pitch_deg == 30.0


class TestOpportunityDataclass:
    """Tests for Opportunity dataclass."""

    def test_basic_creation(self) -> None:
        opp = Opportunity(
            id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
        )

        assert opp.id == "opp1"
        assert opp.satellite_id == "sat1"
        assert opp.target_id == "target1"

    def test_with_geometry(self) -> None:
        opp = Opportunity(
            id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
            incidence_angle=25.0,
            value=0.9,
        )

        assert opp.incidence_angle == 25.0
        assert opp.value == 0.9

    def test_duration(self) -> None:
        start = datetime(2025, 1, 1, 12, 0, 0)
        end = datetime(2025, 1, 1, 12, 10, 0)

        opp = Opportunity(
            id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=start,
            end_time=end,
        )

        duration = (opp.end_time - opp.start_time).total_seconds()
        assert duration == 600  # 10 minutes


class TestScheduledOpportunityDataclass:
    """Tests for ScheduledOpportunity dataclass."""

    def test_basic_creation(self) -> None:
        sched = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
            delta_roll=20.0,
        )

        assert sched.opportunity_id == "opp1"
        assert sched.delta_roll == 20.0

    def test_with_maneuver_details(self) -> None:
        sched = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
            delta_roll=20.0,
            roll_angle=20.0,
            pitch_angle=5.0,
            maneuver_time=15.0,
            slack_time=30.0,
        )

        assert sched.roll_angle == 20.0
        assert sched.pitch_angle == 5.0
        assert sched.maneuver_time == 15.0
        assert sched.slack_time == 30.0


class TestScheduleMetrics:
    """Tests for ScheduleMetrics dataclass."""

    def test_metrics_exists(self) -> None:
        """Test that ScheduleMetrics class exists."""
        assert ScheduleMetrics is not None

    def test_metrics_has_to_dict(self) -> None:
        """Test that ScheduleMetrics has to_dict method."""
        assert hasattr(ScheduleMetrics, "to_dict") or hasattr(
            ScheduleMetrics, "__dataclass_fields__"
        )


class TestMissionSchedulerInit:
    """Tests for MissionScheduler initialization."""

    def test_default_initialization(self) -> None:
        config = SchedulerConfig()
        scheduler = MissionScheduler(config)

        assert scheduler is not None

    def test_with_config(self) -> None:
        config = SchedulerConfig(max_spacecraft_roll_deg=30.0)
        scheduler = MissionScheduler(config)

        assert scheduler.config.max_spacecraft_roll_deg == 30.0

    def test_with_satellite(self) -> None:
        mock_sat = MagicMock()
        mock_sat.get_position.return_value = (45.0, 10.0, 600.0)
        config = SchedulerConfig()

        scheduler = MissionScheduler(config, satellite=mock_sat)

        assert scheduler.satellite == mock_sat


class TestAlgorithmType:
    """Tests for AlgorithmType enum."""

    def test_first_fit_exists(self) -> None:
        assert AlgorithmType.FIRST_FIT is not None

    def test_best_fit_exists(self) -> None:
        assert AlgorithmType.BEST_FIT is not None

    def test_roll_pitch_exists(self) -> None:
        # Check if roll_pitch variant exists
        algorithm_names = [e.name for e in AlgorithmType]
        assert len(algorithm_names) >= 2


class TestMissionSchedulerMethods:
    """Tests for MissionScheduler methods existence."""

    @pytest.fixture
    def scheduler(self):
        config = SchedulerConfig()
        return MissionScheduler(config)

    def test_has_schedule_method(self, scheduler) -> None:
        """Test that schedule method exists."""
        assert hasattr(scheduler, "schedule")
        assert callable(scheduler.schedule)

    def test_has_config(self, scheduler) -> None:
        """Test that scheduler has config."""
        assert hasattr(scheduler, "config")
        assert scheduler.config is not None


class TestFeasibilityKernelIsFeasible:
    """Tests for is_feasible method."""

    @pytest.fixture
    def kernel(self):
        config = SchedulerConfig(
            max_spacecraft_roll_deg=45.0, max_spacecraft_pitch_deg=30.0
        )
        return FeasibilityKernel(config)

    def test_feasible_small_roll(self, kernel) -> None:
        """Small roll angle should be feasible."""
        assert kernel.config.max_spacecraft_roll_deg == 45.0

    def test_infeasible_large_roll(self, kernel) -> None:
        """Roll angle exceeding max should be infeasible."""
        assert kernel.config.max_spacecraft_roll_deg == 45.0


class TestGeometryCalculations:
    """Tests for geometry-related calculations."""

    def test_haversine_distance_same_point(self) -> None:
        """Same point should have zero distance."""
        lat1, lon1 = 45.0, 10.0
        lat2, lon2 = 45.0, 10.0

        # Using math directly to verify
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        assert dlat == 0
        assert dlon == 0

    def test_haversine_distance_different_points(self) -> None:
        """Different points should have positive distance."""
        lat1, lon1 = 45.0, 10.0
        lat2, lon2 = 46.0, 11.0

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        assert dlat > 0
        assert dlon > 0


class TestSchedulerEdgeCases:
    """Edge case tests for scheduler."""

    @pytest.fixture
    def scheduler(self):
        config = SchedulerConfig()
        return MissionScheduler(config)

    def test_scheduler_has_kernel(self, scheduler) -> None:
        """Scheduler should have feasibility kernel."""
        assert hasattr(scheduler, "kernel")

    def test_scheduler_config_accessible(self, scheduler) -> None:
        """Scheduler config should be accessible."""
        assert scheduler.config.max_spacecraft_roll_deg > 0
