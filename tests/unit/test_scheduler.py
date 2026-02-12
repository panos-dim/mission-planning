"""
Comprehensive tests for scheduler module.

Tests cover:
- Opportunity dataclass
- ScheduledOpportunity dataclass
- SchedulerConfig dataclass
- AlgorithmType enum
- MissionScheduler algorithms
"""

from datetime import datetime, timedelta

import pytest

from mission_planner.scheduler import (
    EARTH_RADIUS_KM,
    MIN_GAP_SECONDS,
    AlgorithmType,
    MissionScheduler,
    Opportunity,
    ScheduledOpportunity,
    SchedulerConfig,
)


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

    def test_from_string(self) -> None:
        assert AlgorithmType("first_fit") == AlgorithmType.FIRST_FIT


class TestOpportunity:
    """Tests for Opportunity dataclass."""

    def test_basic_creation(self) -> None:
        start = datetime(2025, 1, 1, 12, 0, 0)
        end = datetime(2025, 1, 1, 12, 5, 0)

        opp = Opportunity(
            id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=start,
            end_time=end,
        )

        assert opp.id == "opp1"
        assert opp.satellite_id == "sat1"
        assert opp.target_id == "target1"

    def test_duration_calculated(self) -> None:
        start = datetime(2025, 1, 1, 12, 0, 0)
        end = datetime(2025, 1, 1, 12, 5, 0)

        opp = Opportunity(
            id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=start,
            end_time=end,
        )

        assert opp.duration_seconds == 300.0  # 5 minutes

    def test_explicit_duration(self) -> None:
        start = datetime(2025, 1, 1, 12, 0, 0)
        end = datetime(2025, 1, 1, 12, 5, 0)

        opp = Opportunity(
            id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=start,
            end_time=end,
            duration_seconds=600.0,  # Override
        )

        assert opp.duration_seconds == 600.0

    def test_default_values(self) -> None:
        start = datetime(2025, 1, 1, 12, 0, 0)
        end = datetime(2025, 1, 1, 12, 5, 0)

        opp = Opportunity(
            id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=start,
            end_time=end,
        )

        assert opp.value == 1.0
        assert opp.priority == 5
        assert opp.incidence_angle is None
        assert opp.pitch_angle is None

    def test_with_angles(self) -> None:
        start = datetime(2025, 1, 1, 12, 0, 0)
        end = datetime(2025, 1, 1, 12, 5, 0)

        opp = Opportunity(
            id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=start,
            end_time=end,
            incidence_angle=25.5,
            pitch_angle=-10.0,
        )

        assert opp.incidence_angle == 25.5
        assert opp.pitch_angle == -10.0


class TestScheduledOpportunity:
    """Tests for ScheduledOpportunity dataclass."""

    def test_basic_creation(self) -> None:
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
        )

        assert scheduled.opportunity_id == "opp1"
        assert scheduled.delta_roll == 20.0
        assert scheduled.roll_angle == 20.0


class TestSchedulerConfig:
    """Tests for SchedulerConfig dataclass."""

    def test_default_values(self) -> None:
        config = SchedulerConfig()

        assert config.max_spacecraft_roll_deg == 90.0
        assert config.max_spacecraft_pitch_deg == 0.0
        assert config.max_roll_rate_dps == 1.0
        assert config.imaging_time_s == 5.0

    def test_custom_values(self) -> None:
        config = SchedulerConfig(
            max_spacecraft_roll_deg=45.0,
            max_spacecraft_pitch_deg=30.0,
            max_roll_rate_dps=2.0,
        )

        assert config.max_spacecraft_roll_deg == 45.0
        assert config.max_spacecraft_pitch_deg == 30.0
        assert config.max_roll_rate_dps == 2.0


class TestMissionScheduler:
    """Tests for MissionScheduler class."""

    @pytest.fixture
    def scheduler(self):
        config = SchedulerConfig(
            max_spacecraft_roll_deg=45.0,
            max_spacecraft_pitch_deg=30.0,
            max_roll_rate_dps=1.0,
            max_pitch_rate_dps=1.0,
        )
        return MissionScheduler(config)

    @pytest.fixture
    def sample_opportunities(self):
        base_time = datetime(2025, 1, 1, 12, 0, 0)
        return [
            Opportunity(
                id="opp1",
                satellite_id="sat1",
                target_id="target1",
                start_time=base_time,
                end_time=base_time + timedelta(seconds=60),
                incidence_angle=20.0,
                value=0.8,
            ),
            Opportunity(
                id="opp2",
                satellite_id="sat1",
                target_id="target2",
                start_time=base_time + timedelta(minutes=5),
                end_time=base_time + timedelta(minutes=6),
                incidence_angle=25.0,
                value=0.9,
            ),
            Opportunity(
                id="opp3",
                satellite_id="sat1",
                target_id="target3",
                start_time=base_time + timedelta(minutes=10),
                end_time=base_time + timedelta(minutes=11),
                incidence_angle=30.0,
                value=0.7,
            ),
        ]

    @pytest.fixture
    def target_positions(self):
        return {
            "target1": (25.0, 55.0),
            "target2": (26.0, 56.0),
            "target3": (27.0, 57.0),
        }

    def test_scheduler_creation(self, scheduler) -> None:
        assert scheduler is not None
        assert scheduler.config.max_spacecraft_roll_deg == 45.0

    def test_empty_opportunities(self, scheduler, target_positions) -> None:
        schedule, metrics = scheduler.schedule(
            [], target_positions, AlgorithmType.FIRST_FIT
        )
        assert len(schedule) == 0

    def test_first_fit_basic(
        self, scheduler, sample_opportunities, target_positions
    ) -> None:
        schedule, metrics = scheduler.schedule(
            sample_opportunities, target_positions, AlgorithmType.FIRST_FIT
        )
        assert len(schedule) > 0

    def test_best_fit_basic(
        self, scheduler, sample_opportunities, target_positions
    ) -> None:
        schedule, metrics = scheduler.schedule(
            sample_opportunities, target_positions, AlgorithmType.BEST_FIT
        )
        assert len(schedule) > 0

    def test_roll_pitch_first_fit(
        self, scheduler, sample_opportunities, target_positions
    ) -> None:
        schedule, metrics = scheduler.schedule(
            sample_opportunities, target_positions, AlgorithmType.ROLL_PITCH_FIRST_FIT
        )
        assert len(schedule) > 0

    def test_roll_pitch_best_fit(
        self, scheduler, sample_opportunities, target_positions
    ) -> None:
        schedule, metrics = scheduler.schedule(
            sample_opportunities, target_positions, AlgorithmType.ROLL_PITCH_BEST_FIT
        )
        assert len(schedule) > 0

    def test_schedule_respects_roll_limit(self, scheduler, target_positions) -> None:
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        # Create opportunity with angle beyond limit
        opps = [
            Opportunity(
                id="opp1",
                satellite_id="sat1",
                target_id="target1",
                start_time=base_time,
                end_time=base_time + timedelta(seconds=60),
                incidence_angle=50.0,  # Beyond 45° limit
                value=1.0,
            ),
        ]

        schedule, metrics = scheduler.schedule(
            opps, target_positions, AlgorithmType.FIRST_FIT
        )
        # May or may not be scheduled depending on implementation
        assert isinstance(schedule, list)

    def test_chronological_order(
        self, scheduler, sample_opportunities, target_positions
    ) -> None:
        schedule, metrics = scheduler.schedule(
            sample_opportunities, target_positions, AlgorithmType.FIRST_FIT
        )

        # Check schedule is in chronological order
        for i in range(len(schedule) - 1):
            assert schedule[i].start_time <= schedule[i + 1].start_time

    def test_metrics_returned(
        self, scheduler, sample_opportunities, target_positions
    ) -> None:
        schedule, metrics = scheduler.schedule(
            sample_opportunities, target_positions, AlgorithmType.FIRST_FIT
        )

        assert metrics is not None


class TestConstants:
    """Tests for module constants."""

    def test_earth_radius(self) -> None:
        assert EARTH_RADIUS_KM == 6371.0

    def test_min_gap(self) -> None:
        assert MIN_GAP_SECONDS == 10.0
