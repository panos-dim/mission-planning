"""
Extended tests for audit module.

Tests cover:
- Invariant checking functions
- Metrics computation
- Scenario generation
- Preset scenarios
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

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
from mission_planner.audit.scenarios import (
    ICEYE_X44_TLE,
    PRESET_SCENARIOS,
    SatelliteConfig,
    Scenario,
    generate_random_scenario,
    generate_scenario,
    get_preset_scenario,
)
from mission_planner.scheduler import Opportunity, ScheduledOpportunity, SchedulerConfig
from mission_planner.targets import GroundTarget


class TestCheckPitchWithinLimits:
    """Tests for check_pitch_within_limits function."""

    def test_within_limits(self) -> None:
        task = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 5, 0),
            delta_roll=10.0,
            pitch_angle=15.0,
        )

        result = check_pitch_within_limits([task], max_pitch_deg=30.0)

        assert result.ok is True
        assert result.name == "pitch_within_limits"

    def test_exceeds_limits(self) -> None:
        task = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 5, 0),
            delta_roll=10.0,
            pitch_angle=35.0,  # Exceeds 30° limit
        )

        result = check_pitch_within_limits([task], max_pitch_deg=30.0)

        assert result.ok is False
        assert "exceeds limit" in result.details

    def test_negative_pitch_within_limits(self) -> None:
        task = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 5, 0),
            delta_roll=10.0,
            pitch_angle=-20.0,  # Backward looking
        )

        result = check_pitch_within_limits([task], max_pitch_deg=30.0)

        assert result.ok is True

    def test_empty_schedule(self) -> None:
        result = check_pitch_within_limits([], max_pitch_deg=30.0)

        assert result.ok is True


class TestCheckSlackNonNegative:
    """Tests for check_slack_non_negative function."""

    def test_positive_slack(self) -> None:
        task = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 5, 0),
            delta_roll=10.0,
            slack_time=30.0,
        )

        result = check_slack_non_negative([task])

        assert result.ok is True
        assert result.name == "slack_non_negative"

    def test_zero_slack(self) -> None:
        task = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 5, 0),
            delta_roll=10.0,
            slack_time=0.0,
        )

        result = check_slack_non_negative([task])

        assert result.ok is True

    def test_negative_slack(self) -> None:
        task = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 5, 0),
            delta_roll=10.0,
            slack_time=-5.0,  # Negative slack
        )

        result = check_slack_non_negative([task])

        assert result.ok is False
        assert "negative" in result.details

    def test_empty_schedule(self) -> None:
        result = check_slack_non_negative([])

        assert result.ok is True


class TestCheckTimeMonotonic:
    """Tests for check_time_monotonic function."""

    def test_monotonic_schedule(self) -> None:
        task1 = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 5, 0),
            delta_roll=10.0,
        )
        task2 = ScheduledOpportunity(
            opportunity_id="opp2",
            satellite_id="sat1",
            target_id="target2",
            start_time=datetime(2025, 1, 1, 12, 10, 0),
            end_time=datetime(2025, 1, 1, 12, 15, 0),
            delta_roll=15.0,
        )

        result = check_time_monotonic([task1, task2], ["sat1"])

        assert result.ok is True
        assert result.name == "time_monotonic"

    def test_non_monotonic_schedule(self) -> None:
        task1 = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 10, 0),  # Later
            end_time=datetime(2025, 1, 1, 12, 15, 0),
            delta_roll=10.0,
        )
        task2 = ScheduledOpportunity(
            opportunity_id="opp2",
            satellite_id="sat1",
            target_id="target2",
            start_time=datetime(2025, 1, 1, 12, 0, 0),  # Earlier
            end_time=datetime(2025, 1, 1, 12, 5, 0),
            delta_roll=15.0,
        )

        result = check_time_monotonic([task1, task2], ["sat1"])

        assert result.ok is False
        assert "starts after" in result.details

    def test_different_satellites(self) -> None:
        """Different satellites can have independent schedules."""
        task1 = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 10, 0),
            end_time=datetime(2025, 1, 1, 12, 15, 0),
            delta_roll=10.0,
        )
        task2 = ScheduledOpportunity(
            opportunity_id="opp2",
            satellite_id="sat2",  # Different satellite
            target_id="target2",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 5, 0),
            delta_roll=15.0,
        )

        result = check_time_monotonic([task1, task2], ["sat1", "sat2"])

        assert result.ok is True


class TestCheckQualityConsistency:
    """Tests for check_quality_consistency function."""

    def test_quality_model_off(self) -> None:
        result = check_quality_consistency([], [], quality_model="off")

        assert result.ok is True
        assert "disabled" in result.details

    def test_empty_schedule(self) -> None:
        result = check_quality_consistency([], [], quality_model="linear")

        assert result.ok is True

    def test_no_rejected_opportunities(self) -> None:
        task = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 5, 0),
            delta_roll=10.0,
            incidence_angle=20.0,
            value=0.9,
        )

        result = check_quality_consistency([task], [], quality_model="linear")

        assert result.ok is True


class TestComputeMetrics:
    """Tests for compute_metrics function."""

    @pytest.fixture
    def config(self):
        return SchedulerConfig()

    def test_empty_schedule(self, config) -> None:
        metrics = compute_metrics([], [], config, runtime_s=0.1)

        assert metrics.accepted == 0
        assert metrics.rejected == 0
        assert metrics.runtime_ms == pytest.approx(100.0)

    def test_single_task(self, config) -> None:
        task = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 5, 0),
            delta_roll=20.0,
            roll_angle=20.0,
            pitch_angle=10.0,
            maneuver_time=15.0,
            slack_time=30.0,
            value=0.85,
            incidence_angle=25.0,
        )
        opp = Opportunity(
            id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 5, 0),
        )

        metrics = compute_metrics([task], [opp], config, runtime_s=0.05)

        assert metrics.accepted == 1
        assert metrics.total_value == pytest.approx(0.85)
        assert metrics.mean_incidence_deg == 25.0
        assert metrics.max_roll_deg == 20.0

    def test_multiple_tasks(self, config) -> None:
        tasks = [
            ScheduledOpportunity(
                opportunity_id=f"opp{i}",
                satellite_id="sat1",
                target_id=f"target{i}",
                start_time=datetime(2025, 1, 1, 12, i * 10, 0),
                end_time=datetime(2025, 1, 1, 12, i * 10 + 5, 0),
                delta_roll=10.0 + i * 5,
                roll_angle=10.0 + i * 5,
                pitch_angle=5.0 * i,
                maneuver_time=10.0,
                slack_time=20.0,
                value=0.8,
                incidence_angle=20.0 + i * 5,
            )
            for i in range(3)
        ]
        opps = [
            Opportunity(
                id=f"opp{i}",
                satellite_id="sat1",
                target_id=f"target{i}",
                start_time=datetime(2025, 1, 1, 12, i * 10, 0),
                end_time=datetime(2025, 1, 1, 12, i * 10 + 5, 0),
            )
            for i in range(5)  # 5 opportunities, 3 accepted
        ]

        metrics = compute_metrics(tasks, opps, config, runtime_s=0.1)

        assert metrics.accepted == 3
        assert metrics.rejected == 2
        assert metrics.total_opportunities == 5

    def test_pitch_usage_tracking(self, config) -> None:
        tasks = [
            ScheduledOpportunity(
                opportunity_id="opp1",
                satellite_id="sat1",
                target_id="target1",
                start_time=datetime(2025, 1, 1, 12, 0, 0),
                end_time=datetime(2025, 1, 1, 12, 5, 0),
                delta_roll=10.0,
                roll_angle=10.0,
                pitch_angle=15.0,  # Using pitch
                maneuver_time=10.0,
                slack_time=20.0,
                value=0.8,
                incidence_angle=20.0,
            ),
            ScheduledOpportunity(
                opportunity_id="opp2",
                satellite_id="sat1",
                target_id="target2",
                start_time=datetime(2025, 1, 1, 12, 10, 0),
                end_time=datetime(2025, 1, 1, 12, 15, 0),
                delta_roll=10.0,
                roll_angle=10.0,
                pitch_angle=0.0,  # Not using pitch
                maneuver_time=10.0,
                slack_time=20.0,
                value=0.8,
                incidence_angle=20.0,
            ),
        ]

        metrics = compute_metrics(tasks, [], config, runtime_s=0.1)

        assert metrics.opps_using_pitch == 1
        assert metrics.max_pitch_deg == 15.0


class TestPresetScenarios:
    """Tests for preset scenario functions."""

    def test_preset_scenarios_exist(self) -> None:
        assert len(PRESET_SCENARIOS) >= 5

    def test_simple_two_targets(self) -> None:
        scenario = get_preset_scenario("simple_two_targets")

        assert scenario.scenario_id == "simple_two_targets"
        assert len(scenario.targets) == 2
        assert len(scenario.satellites) == 1

    def test_tight_timing_three_targets(self) -> None:
        scenario = get_preset_scenario("tight_timing_three_targets")

        assert scenario.scenario_id == "tight_timing_three_targets"
        assert len(scenario.targets) == 3

    def test_long_day_many_targets(self) -> None:
        scenario = get_preset_scenario("long_day_many_targets")

        assert scenario.scenario_id == "long_day_many_targets"
        assert len(scenario.targets) == 15

    def test_cross_hemisphere(self) -> None:
        scenario = get_preset_scenario("cross_hemisphere")

        assert scenario.scenario_id == "cross_hemisphere"
        assert any(t.latitude > 0 for t in scenario.targets)
        assert any(t.latitude < 0 for t in scenario.targets)

    def test_dense_cluster(self) -> None:
        scenario = get_preset_scenario("dense_cluster")

        assert scenario.scenario_id == "dense_cluster"
        assert len(scenario.targets) == 8

    def test_unknown_preset(self) -> None:
        with pytest.raises(ValueError, match="Unknown preset"):
            get_preset_scenario("nonexistent_preset")


class TestGenerateRandomScenario:
    """Tests for generate_random_scenario function."""

    def test_basic_generation(self) -> None:
        scenario = generate_random_scenario(
            num_targets=5,
            time_span_hours=12,
        )

        assert len(scenario.targets) == 5
        assert "random" in scenario.tags

    def test_with_seed_reproducibility(self) -> None:
        scenario1 = generate_random_scenario(
            num_targets=5,
            time_span_hours=12,
            seed=42,
        )
        scenario2 = generate_random_scenario(
            num_targets=5,
            time_span_hours=12,
            seed=42,
        )

        # Same seed should produce same targets
        assert scenario1.targets[0].latitude == scenario2.targets[0].latitude

    def test_lat_lon_bounds(self) -> None:
        scenario = generate_random_scenario(
            num_targets=10,
            time_span_hours=12,
            lat_min=30.0,
            lat_max=50.0,
            lon_min=-10.0,
            lon_max=30.0,
        )

        for target in scenario.targets:
            assert 30.0 <= target.latitude <= 50.0
            assert -10.0 <= target.longitude <= 30.0

    def test_mission_mode(self) -> None:
        scenario = generate_random_scenario(
            num_targets=3,
            time_span_hours=6,
            mission_mode="SAR",
        )

        assert scenario.mission_mode == "SAR"


class TestGenerateScenario:
    """Tests for generate_scenario function."""

    def test_preset_type(self) -> None:
        scenario = generate_scenario(
            scenario_type="preset",
            preset_id="simple_two_targets",
        )

        assert scenario.scenario_id == "simple_two_targets"

    def test_preset_type_missing_id(self) -> None:
        with pytest.raises(ValueError, match="preset_id required"):
            generate_scenario(scenario_type="preset")

    def test_random_type(self) -> None:
        scenario = generate_scenario(
            scenario_type="random",
            num_targets=5,
            time_span_hours=6,
        )

        assert len(scenario.targets) == 5

    def test_random_type_defaults(self) -> None:
        scenario = generate_scenario(scenario_type="random")

        # Should use defaults
        assert len(scenario.targets) == 10  # Default num_targets

    def test_unknown_type(self) -> None:
        with pytest.raises(ValueError, match="Unknown scenario_type"):
            generate_scenario(scenario_type="invalid_type")


class TestICEYE_X44_TLE_Config:
    """Tests for ICEYE_X44_TLE constant."""

    def test_exists(self) -> None:
        assert ICEYE_X44_TLE is not None

    def test_has_valid_fields(self) -> None:
        assert ICEYE_X44_TLE.id == "ICEYE-X44"
        assert ICEYE_X44_TLE.name == "ICEYE-X44"
        assert ICEYE_X44_TLE.tle_line1.startswith("1 ")
        assert ICEYE_X44_TLE.tle_line2.startswith("2 ")


class TestScenarioTags:
    """Tests for scenario tagging functionality."""

    def test_preset_has_tags(self) -> None:
        scenario = get_preset_scenario("simple_two_targets")

        assert "simple" in scenario.tags
        assert "deterministic" in scenario.tags

    def test_random_has_tags(self) -> None:
        scenario = generate_random_scenario(
            num_targets=5,
            time_span_hours=12,
        )

        assert "random" in scenario.tags
        assert "n5" in scenario.tags
        assert "t12h" in scenario.tags


class TestScenarioTimeWindow:
    """Tests for scenario time window handling."""

    def test_time_window_duration(self) -> None:
        scenario = get_preset_scenario("simple_two_targets")

        duration = scenario.time_window_end - scenario.time_window_start
        assert duration.total_seconds() > 0

    def test_random_scenario_time_window(self) -> None:
        scenario = generate_random_scenario(
            num_targets=3,
            time_span_hours=24,
        )

        duration = scenario.time_window_end - scenario.time_window_start
        assert duration.total_seconds() == 24 * 3600
