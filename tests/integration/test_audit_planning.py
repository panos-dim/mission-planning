"""
Tests for mission planning audit functionality.

Tests cover:
- Invariant checks (overlap, limits, slack, monotonicity)
- Metrics computation (coverage, value, geometry, time)
- Roll vs pitch comparison logic
- Scenario generation
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mission_planner.audit import (
    run_algorithm_audit,
    compare_roll_vs_pitch,
    check_no_overlap,
    check_roll_within_limits,
    check_pitch_within_limits,
    check_slack_non_negative,
    check_time_monotonic,
    compute_metrics,
    AlgorithmMetrics,
    AuditReport,
    InvariantCheck,
)
from mission_planner.scheduler import (
    Opportunity,
    ScheduledOpportunity,
    SchedulerConfig,
)


@pytest.fixture
def sample_opportunities():
    """Create sample opportunities for testing."""
    base_time = datetime(2025, 10, 13, 10, 0, 0)
    
    return [
        Opportunity(
            id="sat1_target1_0",
            satellite_id="sat1",
            target_id="target1",
            start_time=base_time,
            end_time=base_time + timedelta(seconds=60),
            incidence_angle=20.0,
            pitch_angle=0.0,
        ),
        Opportunity(
            id="sat1_target2_0",
            satellite_id="sat1",
            target_id="target2",
            start_time=base_time + timedelta(minutes=10),
            end_time=base_time + timedelta(minutes=10, seconds=60),
            incidence_angle=30.0,
            pitch_angle=0.0,
        ),
        Opportunity(
            id="sat1_target3_0",
            satellite_id="sat1",
            target_id="target3",
            start_time=base_time + timedelta(minutes=20),
            end_time=base_time + timedelta(minutes=20, seconds=60),
            incidence_angle=25.0,
            pitch_angle=0.0,
        ),
    ]


@pytest.fixture
def sample_schedule():
    """Create sample scheduled tasks for testing."""
    base_time = datetime(2025, 10, 13, 10, 0, 0)
    
    return [
        ScheduledOpportunity(
            opportunity_id="sat1_target1_0",
            satellite_id="sat1",
            target_id="target1",
            start_time=base_time,
            end_time=base_time + timedelta(seconds=30),
            delta_roll=20.0,  # Required field
            delta_pitch=0.0,
            roll_angle=20.0,
            pitch_angle=0.0,
            maneuver_time=5.0,
            slack_time=24.0,  # Was "slack"
            value=1.0,
            incidence_angle=20.0,
        ),
        ScheduledOpportunity(
            opportunity_id="sat1_target2_0",
            satellite_id="sat1",
            target_id="target2",
            start_time=base_time + timedelta(minutes=10),
            end_time=base_time + timedelta(minutes=10, seconds=40),
            delta_roll=10.0,  # Required field
            delta_pitch=0.0,
            roll_angle=30.0,
            pitch_angle=0.0,
            maneuver_time=10.0,
            slack_time=29.0,  # Was "slack"
            value=0.9,
            incidence_angle=30.0,
        ),
    ]


@pytest.fixture
def default_constraints():
    """Default planning constraints."""
    return SchedulerConfig(
        imaging_time_s=1.0,
        max_roll_rate_dps=3.0,
        max_roll_accel_dps2=1.0,
        max_spacecraft_roll_deg=45.0,
        max_pitch_rate_dps=0.5,
        max_pitch_accel_dps2=0.25,
        max_spacecraft_pitch_deg=10.0,
    )


class TestInvariantChecks:
    """Test individual invariant checking functions."""
    
    def test_no_overlap_pass(self, sample_schedule):
        """Test no_overlap check with non-overlapping schedule."""
        result = check_no_overlap(sample_schedule, ["sat1"])
        assert result.ok
        assert result.details is None
    
    def test_no_overlap_fail(self):
        """Test no_overlap check with overlapping tasks."""
        base_time = datetime(2025, 10, 13, 10, 0, 0)
        
        overlapping_schedule = [
            ScheduledOpportunity(
                opportunity_id="task1",
                satellite_id="sat1",
                target_id="target1",
                start_time=base_time,
                end_time=base_time + timedelta(seconds=60),
                incidence_angle=20.0,
                roll_angle=20.0,
                pitch_angle=0.0,
                maneuver_time=5.0,
                delta_roll=20.0,
                slack_time=54.0,
                value=1.0,
            ),
            ScheduledOpportunity(
                opportunity_id="task2",
                satellite_id="sat1",
                target_id="target2",
                start_time=base_time + timedelta(seconds=30),  # Overlaps!
                end_time=base_time + timedelta(seconds=90),
                incidence_angle=30.0,
                roll_angle=30.0,
                pitch_angle=0.0,
                maneuver_time=5.0,
                delta_roll=20.0,
                slack_time=54.0,
                value=1.0,
            ),
        ]
        
        result = check_no_overlap(overlapping_schedule, ["sat1"])
        assert not result.ok
        assert "task1" in result.details
        assert "task2" in result.details
    
    def test_roll_within_limits_pass(self, sample_schedule):
        """Test roll limits check with valid angles."""
        result = check_roll_within_limits(sample_schedule, 45.0)
        assert result.ok
    
    def test_roll_within_limits_fail(self, sample_schedule):
        """Test roll limits check with excessive angle."""
        result = check_roll_within_limits(sample_schedule, 25.0)  # Lower limit
        assert not result.ok
        assert "sat1_target2_0" in result.details  # Has 30° roll
    
    def test_pitch_within_limits_pass(self, sample_schedule):
        """Test pitch limits check with valid angles."""
        result = check_pitch_within_limits(sample_schedule, 10.0)
        assert result.ok
    
    def test_pitch_within_limits_fail(self):
        """Test pitch limits check with excessive angle."""
        base_time = datetime(2025, 10, 13, 10, 0, 0)
        
        schedule_with_pitch = [
            ScheduledOpportunity(
                opportunity_id="task1",
                satellite_id="sat1",
                target_id="target1",
                start_time=base_time,
                end_time=base_time + timedelta(seconds=30),
                incidence_angle=20.0,
                roll_angle=20.0,
                pitch_angle=15.0,  # Exceeds limit
                maneuver_time=5.0,
                delta_roll=20.0,
                slack_time=24.0,
                value=1.0,
            ),
        ]
        
        result = check_pitch_within_limits(schedule_with_pitch, 10.0)
        assert not result.ok
        assert "task1" in result.details
    
    def test_slack_non_negative_pass(self, sample_schedule):
        """Test slack check with non-negative values."""
        result = check_slack_non_negative(sample_schedule)
        assert result.ok
    
    def test_slack_non_negative_fail(self):
        """Test slack check with negative slack."""
        base_time = datetime(2025, 10, 13, 10, 0, 0)
        
        schedule_negative_slack = [
            ScheduledOpportunity(
                opportunity_id="task1",
                satellite_id="sat1",
                target_id="target1",
                start_time=base_time,
                end_time=base_time + timedelta(seconds=30),
                incidence_angle=20.0,
                roll_angle=20.0,
                pitch_angle=0.0,
                maneuver_time=5.0,
                delta_roll=20.0,
                slack_time=-5.0,  # Negative!
                value=1.0,
            ),
        ]
        
        result = check_slack_non_negative(schedule_negative_slack)
        assert not result.ok
        assert "task1" in result.details
    
    def test_time_monotonic_pass(self, sample_schedule):
        """Test monotonicity check with properly ordered schedule."""
        result = check_time_monotonic(sample_schedule, ["sat1"])
        assert result.ok
    
    def test_time_monotonic_fail(self):
        """Test monotonicity check with out-of-order schedule."""
        base_time = datetime(2025, 10, 13, 10, 0, 0)
        
        unordered_schedule = [
            ScheduledOpportunity(
                opportunity_id="task2",
                satellite_id="sat1",
                target_id="target2",
                start_time=base_time + timedelta(minutes=10),
                end_time=base_time + timedelta(minutes=10, seconds=30),
                incidence_angle=30.0,
                roll_angle=30.0,
                pitch_angle=0.0,
                maneuver_time=5.0,
                delta_roll=30.0,
                slack_time=24.0,
                value=1.0,
            ),
            ScheduledOpportunity(
                opportunity_id="task1",
                satellite_id="sat1",
                target_id="target1",
                start_time=base_time,  # Earlier!
                end_time=base_time + timedelta(seconds=30),
                incidence_angle=20.0,
                roll_angle=20.0,
                pitch_angle=0.0,
                maneuver_time=5.0,
                delta_roll=20.0,
                slack_time=24.0,
                value=1.0,
            ),
        ]
        
        result = check_time_monotonic(unordered_schedule, ["sat1"])
        assert not result.ok


class TestMetricsComputation:
    """Test metrics computation."""
    
    def test_compute_metrics_basic(self, sample_schedule, sample_opportunities, default_constraints):
        """Test basic metrics computation."""
        metrics = compute_metrics(
            schedule=sample_schedule,
            all_opportunities=sample_opportunities,
            constraints=default_constraints,
            runtime_s=0.042,
            quality_model="off",
        )
        
        assert metrics.accepted == 2
        assert metrics.rejected == 1
        assert metrics.total_opportunities == 3
        assert metrics.total_value == pytest.approx(1.9)
        assert metrics.mean_value == pytest.approx(0.95)
        assert metrics.mean_incidence_deg == pytest.approx(25.0)
        assert metrics.max_roll_deg == pytest.approx(30.0)
        assert metrics.runtime_ms == pytest.approx(42.0)
    
    def test_compute_metrics_empty_schedule(self, sample_opportunities, default_constraints):
        """Test metrics with empty schedule."""
        metrics = compute_metrics(
            schedule=[],
            all_opportunities=sample_opportunities,
            constraints=default_constraints,
            runtime_s=0.001,
        )
        
        assert metrics.accepted == 0
        assert metrics.rejected == 3
        assert metrics.total_value == 0.0
    
    def test_compute_metrics_pitch_usage(self, sample_opportunities, default_constraints):
        """Test pitch-related metrics."""
        base_time = datetime(2025, 10, 13, 10, 0, 0)
        
        schedule_with_pitch = [
            ScheduledOpportunity(
                opportunity_id="task1",
                satellite_id="sat1",
                target_id="target1",
                start_time=base_time,
                end_time=base_time + timedelta(seconds=30),
                incidence_angle=20.0,
                roll_angle=20.0,
                pitch_angle=5.0,
                maneuver_time=5.0,
                delta_roll=20.0,
                slack_time=24.0,
                value=1.0,
            ),
            ScheduledOpportunity(
                opportunity_id="task2",
                satellite_id="sat1",
                target_id="target2",
                start_time=base_time + timedelta(minutes=10),
                end_time=base_time + timedelta(minutes=10, seconds=30),
                incidence_angle=30.0,
                roll_angle=30.0,
                pitch_angle=8.0,
                maneuver_time=10.0,
                delta_roll=30.0,
                slack_time=19.0,
                value=0.9,
            ),
        ]
        
        metrics = compute_metrics(
            schedule=schedule_with_pitch,
            all_opportunities=sample_opportunities,
            constraints=default_constraints,
            runtime_s=0.050,
        )
        
        assert metrics.opps_using_pitch == 2
        assert metrics.max_pitch_deg == pytest.approx(8.0)
        assert metrics.total_pitch_used_deg == pytest.approx(13.0)


class TestAuditReport:
    """Test full audit report generation."""
    
    def test_run_algorithm_audit_first_fit(self, sample_opportunities, default_constraints):
        """Test audit for first_fit algorithm."""
        report = run_algorithm_audit(
            algorithm_name="first_fit",
            opportunities=sample_opportunities,
            constraints=default_constraints,
            satellite_ids=["sat1"],
            quality_model="off",
            quality_weight=0.5,
        )
        
        assert report.algorithm_name == "first_fit"
        assert report.status in ["ok", "warnings"]
        assert report.metrics.total_opportunities == 3
        assert len(report.invariants) >= 5  # At least 5 invariant checks
        assert isinstance(report.schedule, list)
    
    def test_run_algorithm_audit_invalid_algorithm(self, sample_opportunities, default_constraints):
        """Test audit with invalid algorithm name."""
        report = run_algorithm_audit(
            algorithm_name="invalid_algorithm",
            opportunities=sample_opportunities,
            constraints=default_constraints,
            satellite_ids=["sat1"],
        )
        
        assert report.status == "failed"
        assert len(report.errors) > 0


class TestRollVsPitchComparison:
    """Test roll-only vs roll+pitch comparison."""
    
    def test_comparison_improvement(self):
        """Test comparison showing pitch improvement."""
        roll_only = AuditReport(
            algorithm_name="first_fit",
            status="ok",
            metrics=AlgorithmMetrics(
                accepted=7,
                rejected=3,
                total_opportunities=10,
                total_value=7.0,
                utilization=0.35,
            ),
            invariants=[],
            schedule=[],
        )
        
        roll_pitch = AuditReport(
            algorithm_name="first_fit_roll_pitch",
            status="ok",
            metrics=AlgorithmMetrics(
                accepted=9,
                rejected=1,
                total_opportunities=10,
                total_value=9.0,
                utilization=0.45,
                opps_using_pitch=2,
                max_pitch_deg=8.0,
            ),
            invariants=[],
            schedule=[],
        )
        
        comparison = compare_roll_vs_pitch(roll_only, roll_pitch)
        
        assert comparison["delta_accepted"] == 2
        assert comparison["delta_value"] == pytest.approx(2.0)
        assert len(comparison["improvements"]) > 0
        assert any("additional_coverage" in imp["type"] for imp in comparison["improvements"])
    
    def test_comparison_regression_explained(self):
        """Test comparison with explainable regression (pitch limits)."""
        roll_only = AuditReport(
            algorithm_name="first_fit",
            status="ok",
            metrics=AlgorithmMetrics(accepted=8, rejected=2, total_opportunities=10),
            invariants=[],
            schedule=[],
        )
        
        roll_pitch = AuditReport(
            algorithm_name="first_fit_roll_pitch",
            status="warnings",
            metrics=AlgorithmMetrics(accepted=6, rejected=4, total_opportunities=10),
            invariants=[
                InvariantCheck(name="pitch_within_limits", ok=False, details="2 violations")
            ],
            schedule=[],
        )
        
        comparison = compare_roll_vs_pitch(roll_only, roll_pitch)
        
        assert comparison["delta_accepted"] == -2
        assert len(comparison["regressions"]) > 0
        assert any(reg["ok"] for reg in comparison["regressions"])  # Explained regression
    
    def test_comparison_unexplained_regression(self):
        """Test comparison with unexplained regression (potential bug)."""
        roll_only = AuditReport(
            algorithm_name="first_fit",
            status="ok",
            metrics=AlgorithmMetrics(accepted=8, rejected=2, total_opportunities=10),
            invariants=[],
            schedule=[],
        )
        
        roll_pitch = AuditReport(
            algorithm_name="first_fit_roll_pitch",
            status="ok",
            metrics=AlgorithmMetrics(accepted=6, rejected=4, total_opportunities=10),
            invariants=[
                InvariantCheck(name="pitch_within_limits", ok=True)  # No violations!
            ],
            schedule=[],
        )
        
        comparison = compare_roll_vs_pitch(roll_only, roll_pitch)
        
        assert comparison["delta_accepted"] == -2
        assert len(comparison["regressions"]) > 0
        assert any(not reg["ok"] for reg in comparison["regressions"])  # Unexplained!


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
