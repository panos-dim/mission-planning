"""
Tests for audit module.

Tests cover:
- InvariantCheck dataclass
- AlgorithmMetrics dataclass
- AuditReport dataclass
- Invariant checking functions
- Scenario generation
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from mission_planner.audit.planning_audit import (
    InvariantCheck,
    AlgorithmMetrics,
    AuditReport,
    check_no_overlap,
    check_roll_within_limits,
)
from mission_planner.audit.scenarios import (
    SatelliteConfig,
    Scenario,
    ICEYE_X44_TLE,
)
from mission_planner.scheduler import ScheduledOpportunity
from mission_planner.targets import GroundTarget


class TestInvariantCheck:
    """Tests for InvariantCheck dataclass."""

    def test_basic_creation_ok(self) -> None:
        check = InvariantCheck(
            name="test_check",
            ok=True,
        )

        assert check.name == "test_check"
        assert check.ok is True
        assert check.details is None
        assert check.affected_items == []

    def test_creation_with_failure(self) -> None:
        check = InvariantCheck(
            name="overlap_check",
            ok=False,
            details="Task A overlaps with Task B",
            affected_items=["task_a", "task_b"],
        )

        assert check.ok is False
        assert "overlaps" in check.details
        assert len(check.affected_items) == 2


class TestAlgorithmMetrics:
    """Tests for AlgorithmMetrics dataclass."""

    def test_default_values(self) -> None:
        metrics = AlgorithmMetrics()

        assert metrics.accepted == 0
        assert metrics.rejected == 0
        assert metrics.total_value == 0.0
        assert metrics.total_pitch_used_deg == 0.0

    def test_custom_values(self) -> None:
        metrics = AlgorithmMetrics(
            accepted=10,
            rejected=2,
            total_opportunities=12,
            total_value=8.5,
            mean_value=0.85,
            mean_incidence_deg=25.0,
            total_roll_used_deg=150.0,
            max_roll_deg=35.0,
            total_pitch_used_deg=60.0,
            max_pitch_deg=20.0,
            opps_using_pitch=4,
            runtime_ms=125.5,
        )

        assert metrics.accepted == 10
        assert metrics.total_pitch_used_deg == 60.0
        assert metrics.opps_using_pitch == 4

    def test_quality_metrics(self) -> None:
        metrics = AlgorithmMetrics(
            quality_degradation=0.15,
            avg_quality_score=0.85,
        )

        assert metrics.quality_degradation == 0.15
        assert metrics.avg_quality_score == 0.85


class TestAuditReport:
    """Tests for AuditReport dataclass."""

    def test_basic_creation(self) -> None:
        metrics = AlgorithmMetrics(accepted=5, rejected=1)
        invariants = [
            InvariantCheck(name="check1", ok=True),
            InvariantCheck(name="check2", ok=True),
        ]

        report = AuditReport(
            algorithm_name="first_fit",
            status="ok",
            metrics=metrics,
            invariants=invariants,
            schedule=[],
        )

        assert report.algorithm_name == "first_fit"
        assert report.status == "ok"
        assert len(report.invariants) == 2
        assert report.warnings == []
        assert report.errors == []

    def test_report_with_warnings(self) -> None:
        metrics = AlgorithmMetrics()

        report = AuditReport(
            algorithm_name="best_fit",
            status="warnings",
            metrics=metrics,
            invariants=[],
            schedule=[],
            warnings=["Low coverage detected", "High maneuver time"],
        )

        assert report.status == "warnings"
        assert len(report.warnings) == 2

    def test_report_with_errors(self) -> None:
        metrics = AlgorithmMetrics()

        report = AuditReport(
            algorithm_name="roll_pitch_first_fit",
            status="failed",
            metrics=metrics,
            invariants=[],
            schedule=[],
            errors=["Overlap detected", "Roll limit exceeded"],
        )

        assert report.status == "failed"
        assert len(report.errors) == 2


class TestCheckNoOverlap:
    """Tests for check_no_overlap function."""

    def test_no_tasks(self) -> None:
        result = check_no_overlap([], ["sat1"])

        assert result.ok is True
        assert result.name == "no_overlap"

    def test_single_task(self) -> None:
        task = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 5, 0),
            delta_roll=10.0,
        )

        result = check_no_overlap([task], ["sat1"])

        assert result.ok is True

    def test_non_overlapping_tasks(self) -> None:
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

        result = check_no_overlap([task1, task2], ["sat1"])

        assert result.ok is True

    def test_overlapping_tasks(self) -> None:
        task1 = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
            delta_roll=10.0,
        )
        task2 = ScheduledOpportunity(
            opportunity_id="opp2",
            satellite_id="sat1",
            target_id="target2",
            start_time=datetime(2025, 1, 1, 12, 5, 0),  # Overlaps
            end_time=datetime(2025, 1, 1, 12, 15, 0),
            delta_roll=15.0,
        )

        result = check_no_overlap([task1, task2], ["sat1"])

        assert result.ok is False
        assert "overlaps" in result.details

    def test_different_satellites_no_conflict(self) -> None:
        task1 = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 10, 0),
            delta_roll=10.0,
        )
        task2 = ScheduledOpportunity(
            opportunity_id="opp2",
            satellite_id="sat2",  # Different satellite
            target_id="target2",
            start_time=datetime(2025, 1, 1, 12, 5, 0),
            end_time=datetime(2025, 1, 1, 12, 15, 0),
            delta_roll=15.0,
        )

        result = check_no_overlap([task1, task2], ["sat1", "sat2"])

        assert result.ok is True


class TestCheckRollWithinLimits:
    """Tests for check_roll_within_limits function."""

    def test_within_limits(self) -> None:
        task = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 5, 0),
            delta_roll=20.0,
            roll_angle=30.0,
        )

        result = check_roll_within_limits([task], max_roll_deg=45.0)

        assert result.ok is True

    def test_exceeds_limits(self) -> None:
        task = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 5, 0),
            delta_roll=30.0,
            roll_angle=50.0,  # Exceeds 45° limit
        )

        result = check_roll_within_limits([task], max_roll_deg=45.0)

        assert result.ok is False
        assert "exceeds limit" in result.details

    def test_negative_roll_within_limits(self) -> None:
        task = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 5, 0),
            delta_roll=-25.0,
            roll_angle=-35.0,  # Left of track, within limits
        )

        result = check_roll_within_limits([task], max_roll_deg=45.0)

        assert result.ok is True

    def test_negative_roll_exceeds_limits(self) -> None:
        task = ScheduledOpportunity(
            opportunity_id="opp1",
            satellite_id="sat1",
            target_id="target1",
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            end_time=datetime(2025, 1, 1, 12, 5, 0),
            delta_roll=-30.0,
            roll_angle=-50.0,  # Exceeds magnitude limit
        )

        result = check_roll_within_limits([task], max_roll_deg=45.0)

        assert result.ok is False


class TestSatelliteConfig:
    """Tests for SatelliteConfig dataclass."""

    def test_basic_creation(self) -> None:
        config = SatelliteConfig(
            id="test-sat",
            tle_line1="1 00000U 00000A   00000.00000000  .00000000  00000-0  00000-0 0  0000",
            tle_line2="2 00000  00.0000 000.0000 0000000 000.0000 000.0000 15.00000000 00000",
        )

        assert config.id == "test-sat"
        assert config.name == ""

    def test_with_name(self) -> None:
        config = SatelliteConfig(
            id="iceye-x44",
            tle_line1="line1",
            tle_line2="line2",
            name="ICEYE-X44",
        )

        assert config.name == "ICEYE-X44"


class TestScenario:
    """Tests for Scenario dataclass."""

    def test_basic_creation(self) -> None:
        scenario = Scenario(
            scenario_id="test_scenario",
            description="Test scenario for unit tests",
            satellites=[ICEYE_X44_TLE],
            targets=[
                GroundTarget(name="T1", latitude=40.0, longitude=20.0),
            ],
            time_window_start=datetime(2025, 1, 1, 0, 0, 0),
            time_window_end=datetime(2025, 1, 1, 12, 0, 0),
        )

        assert scenario.scenario_id == "test_scenario"
        assert len(scenario.satellites) == 1
        assert len(scenario.targets) == 1
        assert scenario.mission_mode == "OPTICAL"

    def test_with_expectations(self) -> None:
        scenario = Scenario(
            scenario_id="expected_scenario",
            description="Scenario with expected behavior",
            satellites=[ICEYE_X44_TLE],
            targets=[
                GroundTarget(name="T1", latitude=40.0, longitude=20.0),
                GroundTarget(name="T2", latitude=41.0, longitude=21.0),
            ],
            time_window_start=datetime(2025, 1, 1, 0, 0, 0),
            time_window_end=datetime(2025, 1, 2, 0, 0, 0),
            expected_min_shots=4,
            expected_behavior="Both algorithms should find similar results",
        )

        assert scenario.expected_min_shots == 4
        assert "Both algorithms" in scenario.expected_behavior

    def test_with_tags(self) -> None:
        scenario = Scenario(
            scenario_id="tagged_scenario",
            description="Tagged scenario",
            satellites=[],
            targets=[],
            time_window_start=datetime(2025, 1, 1, 0, 0, 0),
            time_window_end=datetime(2025, 1, 1, 12, 0, 0),
            tags=["stress_test", "edge_case", "constellation"],
        )

        assert "stress_test" in scenario.tags
        assert len(scenario.tags) == 3

    def test_sar_mission_mode(self) -> None:
        scenario = Scenario(
            scenario_id="sar_scenario",
            description="SAR mission scenario",
            satellites=[ICEYE_X44_TLE],
            targets=[],
            time_window_start=datetime(2025, 1, 1, 0, 0, 0),
            time_window_end=datetime(2025, 1, 1, 12, 0, 0),
            mission_mode="SAR",
        )

        assert scenario.mission_mode == "SAR"


class TestICEYE_X44_TLE:
    """Tests for the standard ICEYE-X44 TLE constant."""

    def test_tle_exists(self) -> None:
        assert ICEYE_X44_TLE is not None
        assert ICEYE_X44_TLE.id == "ICEYE-X44"

    def test_tle_has_valid_lines(self) -> None:
        assert ICEYE_X44_TLE.tle_line1.startswith("1 ")
        assert ICEYE_X44_TLE.tle_line2.startswith("2 ")

    def test_tle_name(self) -> None:
        assert ICEYE_X44_TLE.name == "ICEYE-X44"
