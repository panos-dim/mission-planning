"""
Core audit engine for mission planning algorithms.

Provides deep analysis of algorithm behavior including:
- Metrics computation (coverage, value, utilization, etc.)
- Invariant checking (overlap, limits, slack, etc.)
- Roll vs Roll+Pitch comparisons
- Machine-readable audit reports
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..scheduler import (
    MissionScheduler,
    Opportunity,
    ScheduledOpportunity,
    SchedulerConfig,
    AlgorithmType,
)
from ..quality_scoring import QualityModel

logger = logging.getLogger(__name__)


@dataclass
class InvariantCheck:
    """Result of a single invariant check."""

    name: str
    ok: bool
    details: Optional[str] = None
    affected_items: List[str] = field(default_factory=list)


@dataclass
class AlgorithmMetrics:
    """Comprehensive metrics for a planning algorithm run."""

    # Coverage metrics
    accepted: int = 0
    rejected: int = 0
    total_opportunities: int = 0

    # Value metrics
    total_value: float = 0.0
    mean_value: float = 0.0

    # Geometry metrics
    mean_incidence_deg: float = 0.0
    min_incidence_deg: float = 0.0
    max_incidence_deg: float = 0.0

    # Roll metrics
    total_roll_used_deg: float = 0.0
    max_roll_deg: float = 0.0
    mean_roll_deg: float = 0.0

    # Pitch metrics (for 2D slew algorithms)
    total_pitch_used_deg: float = 0.0
    max_pitch_deg: float = 0.0
    mean_pitch_deg: float = 0.0
    opps_using_pitch: int = 0

    # Time metrics
    total_maneuver_time_s: float = 0.0
    total_imaging_time_s: float = 0.0
    total_slack_time_s: float = 0.0
    utilization: float = 0.0  # (maneuver + imaging) / total_time

    # Performance
    runtime_ms: float = 0.0

    # Quality model metrics (when enabled)
    quality_degradation: Optional[float] = None
    avg_quality_score: Optional[float] = None


@dataclass
class AuditReport:
    """Complete audit report for a single algorithm run."""

    algorithm_name: str
    status: str  # "ok", "failed", "warnings"
    metrics: AlgorithmMetrics
    invariants: List[InvariantCheck]
    schedule: List[Dict[str, Any]]
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def check_no_overlap(schedule: List[ScheduledOpportunity], satellite_ids: List[str]) -> InvariantCheck:
    """
    Check that no two tasks overlap in time for the same satellite.

    Args:
        schedule: List of scheduled tasks
        satellite_ids: List of satellite IDs to check

    Returns:
        InvariantCheck with result
    """
    overlaps = []

    for sat_id in satellite_ids:
        sat_tasks = [t for t in schedule if t.satellite_id == sat_id]
        sat_tasks.sort(key=lambda t: t.start_time)

        for i in range(len(sat_tasks) - 1):
            current = sat_tasks[i]
            next_task = sat_tasks[i + 1]

            if current.end_time > next_task.start_time:
                overlaps.append(
                    f"{sat_id}: Task {current.opportunity_id} "
                    f"({current.end_time.isoformat()}) overlaps with "
                    f"{next_task.opportunity_id} ({next_task.start_time.isoformat()})"
                )

    return InvariantCheck(
        name="no_overlap",
        ok=len(overlaps) == 0,
        details="; ".join(overlaps) if overlaps else None,
        affected_items=overlaps,
    )


def check_roll_within_limits(
    schedule: List[ScheduledOpportunity],
    max_roll_deg: float,
) -> InvariantCheck:
    """Check that all roll angles are within configured limits."""
    violations = []

    for task in schedule:
        if abs(task.roll_angle) > max_roll_deg + 0.01:  # Small tolerance for float precision
            violations.append(
                f"{task.opportunity_id}: roll={task.roll_angle:.2f}° exceeds limit {max_roll_deg}°"
            )

    return InvariantCheck(
        name="roll_within_limits",
        ok=len(violations) == 0,
        details="; ".join(violations) if violations else None,
        affected_items=violations,
    )


def check_pitch_within_limits(
    schedule: List[ScheduledOpportunity],
    max_pitch_deg: float,
) -> InvariantCheck:
    """Check that all pitch angles are within configured limits."""
    violations = []

    for task in schedule:
        if abs(task.pitch_angle) > max_pitch_deg + 0.01:  # Small tolerance
            violations.append(
                f"{task.opportunity_id}: pitch={task.pitch_angle:.2f}° exceeds limit {max_pitch_deg}°"
            )

    return InvariantCheck(
        name="pitch_within_limits",
        ok=len(violations) == 0,
        details="; ".join(violations) if violations else None,
        affected_items=violations,
    )


def check_slack_non_negative(schedule: List[ScheduledOpportunity]) -> InvariantCheck:
    """Check that all tasks have non-negative slack time."""
    violations = []

    for task in schedule:
        if task.slack_time < -0.01:  # Small tolerance for float precision
            violations.append(
                f"{task.opportunity_id}: slack={task.slack_time:.2f}s is negative"
            )

    return InvariantCheck(
        name="slack_non_negative",
        ok=len(violations) == 0,
        details="; ".join(violations) if violations else None,
        affected_items=violations,
    )


def check_time_monotonic(schedule: List[ScheduledOpportunity], satellite_ids: List[str]) -> InvariantCheck:
    """Check that schedule is sorted by start time for each satellite."""
    violations = []

    for sat_id in satellite_ids:
        sat_tasks = [t for t in schedule if t.satellite_id == sat_id]

        for i in range(len(sat_tasks) - 1):
            if sat_tasks[i].start_time > sat_tasks[i + 1].start_time:
                violations.append(
                    f"{sat_id}: Task {sat_tasks[i].opportunity_id} "
                    f"starts after {sat_tasks[i + 1].opportunity_id}"
                )

    return InvariantCheck(
        name="time_monotonic",
        ok=len(violations) == 0,
        details="; ".join(violations) if violations else None,
        affected_items=violations,
    )


def check_quality_consistency(
    schedule: List[ScheduledOpportunity],
    rejected_opps: List[Opportunity],
    quality_model: str,
) -> InvariantCheck:
    """
    Check for suspicious cases where higher-value opportunities were skipped
    in favor of strictly worse ones when quality model is enabled.

    This is a heuristic check, not a strict proof.
    """
    if quality_model == "off":
        return InvariantCheck(
            name="quality_consistency",
            ok=True,
            details="Quality model disabled, check skipped",
        )

    suspicious = []

    # For each rejected opportunity
    for rejected in rejected_opps:
        # Find accepted opportunities with worse geometry
        worse_accepted = [
            t for t in schedule
            if t.target_id == rejected.target_id
            and t.incidence_angle > rejected.incidence_angle  # Worse geometry
            and t.value < rejected.value  # Lower value
        ]

        if worse_accepted:
            suspicious.append(
                f"Target {rejected.target_id}: Rejected opp with "
                f"incidence={rejected.incidence_angle:.1f}°, value={rejected.value:.2f} "
                f"but accepted worse opportunity"
            )

    return InvariantCheck(
        name="quality_consistency",
        ok=len(suspicious) == 0,
        details="; ".join(suspicious[:5]) if suspicious else None,  # Limit to 5 examples
        affected_items=suspicious,
    )


def compute_metrics(
    schedule: List[ScheduledOpportunity],
    all_opportunities: List[Opportunity],
    constraints: SchedulerConfig,
    runtime_s: float,
    quality_model: str = "off",
) -> AlgorithmMetrics:
    """
    Compute comprehensive metrics for a planning result.

    Args:
        schedule: Accepted tasks
        all_opportunities: All input opportunities
        constraints: Planning constraints
        runtime_s: Algorithm runtime in seconds
        quality_model: Quality model used

    Returns:
        AlgorithmMetrics with all computed values
    """
    metrics = AlgorithmMetrics()

    # Coverage
    metrics.accepted = len(schedule)
    metrics.total_opportunities = len(all_opportunities)
    metrics.rejected = metrics.total_opportunities - metrics.accepted

    if not schedule:
        metrics.runtime_ms = runtime_s * 1000
        return metrics

    # Value
    metrics.total_value = sum(t.value for t in schedule)
    metrics.mean_value = metrics.total_value / len(schedule)

    # Geometry
    incidence_angles = [t.incidence_angle for t in schedule]
    metrics.mean_incidence_deg = sum(incidence_angles) / len(incidence_angles)
    metrics.min_incidence_deg = min(incidence_angles)
    metrics.max_incidence_deg = max(incidence_angles)

    # Roll
    roll_angles = [abs(t.roll_angle) for t in schedule]
    metrics.total_roll_used_deg = sum(roll_angles)
    metrics.max_roll_deg = max(roll_angles)
    metrics.mean_roll_deg = sum(roll_angles) / len(roll_angles)

    # Pitch
    pitch_angles = [abs(t.pitch_angle) for t in schedule]
    metrics.total_pitch_used_deg = sum(pitch_angles)
    metrics.max_pitch_deg = max(pitch_angles) if pitch_angles else 0.0
    metrics.mean_pitch_deg = sum(pitch_angles) / len(pitch_angles) if pitch_angles else 0.0
    metrics.opps_using_pitch = sum(1 for p in pitch_angles if abs(p) > 0.1)

    # Time
    metrics.total_maneuver_time_s = sum(t.maneuver_time for t in schedule)
    metrics.total_imaging_time_s = 0.0  # No imaging_duration field in ScheduledOpportunity
    metrics.total_slack_time_s = sum(t.slack_time for t in schedule)

    # Utilization
    if schedule:
        time_span = (schedule[-1].end_time - schedule[0].start_time).total_seconds()
        if time_span > 0:
            active_time = metrics.total_maneuver_time_s + metrics.total_imaging_time_s
            metrics.utilization = active_time / time_span

    # Performance
    metrics.runtime_ms = runtime_s * 1000

    # Quality model metrics
    if quality_model != "off":
        quality_scores = [t.quality_score for t in schedule if hasattr(t, 'quality_score')]
        if quality_scores:
            metrics.avg_quality_score = sum(quality_scores) / len(quality_scores)
            # Degradation = how much worse than nadir (incidence=0)
            metrics.quality_degradation = 1.0 - metrics.avg_quality_score

    return metrics


def run_algorithm_audit(
    algorithm_name: str,
    opportunities: List[Opportunity],
    constraints: SchedulerConfig,
    satellite_ids: List[str],
    quality_model: str = "off",
    quality_weight: float = 0.5,
) -> AuditReport:
    """
    Run a complete audit of a planning algorithm.

    Args:
        algorithm_name: Name of algorithm to run
        opportunities: Input opportunities
        constraints: Planning constraints
        satellite_ids: List of satellite IDs
        quality_model: Quality model to use
        quality_weight: Weight for quality vs coverage

    Returns:
        Complete AuditReport
    """
    logger.info(f"Running audit for algorithm: {algorithm_name}")

    report = AuditReport(
        algorithm_name=algorithm_name,
        status="ok",
        metrics=AlgorithmMetrics(),
        invariants=[],
        schedule=[],
    )

    try:
        # Create scheduler
        scheduler = MissionScheduler(
            config=constraints,
        )

        # Map algorithm name to AlgorithmType enum
        algorithm_map = {
            "first_fit": AlgorithmType.FIRST_FIT,
            "best_fit": AlgorithmType.BEST_FIT,
            "first_fit_roll_pitch": AlgorithmType.ROLL_PITCH_FIRST_FIT,
            "roll_pitch_first_fit": AlgorithmType.ROLL_PITCH_FIRST_FIT,
            "best_fit_roll_pitch": AlgorithmType.ROLL_PITCH_BEST_FIT,
            "roll_pitch_best_fit": AlgorithmType.ROLL_PITCH_BEST_FIT,
        }

        if algorithm_name not in algorithm_map:
            raise ValueError(f"Unknown algorithm: {algorithm_name}")

        algorithm_type = algorithm_map[algorithm_name]

        # Extract target positions (dummy positions for testing)
        target_positions = {opp.target_id: (0.0, 0.0) for opp in opportunities}

        # Run algorithm with timing
        start_time = time.time()
        schedule, metrics = scheduler.schedule(opportunities, target_positions, algorithm_type)
        runtime_s = time.time() - start_time

        # Compute metrics
        report.metrics = compute_metrics(
            schedule=schedule,
            all_opportunities=opportunities,
            constraints=constraints,
            runtime_s=runtime_s,
            quality_model=quality_model,
        )

        # Run invariant checks
        report.invariants = [
            check_no_overlap(schedule, satellite_ids),
            check_roll_within_limits(schedule, constraints.max_spacecraft_roll_deg),
            check_pitch_within_limits(schedule, constraints.max_spacecraft_pitch_deg),
            check_slack_non_negative(schedule),
            check_time_monotonic(schedule, satellite_ids),
            check_quality_consistency(
                schedule=schedule,
                rejected_opps=[o for o in opportunities if o.id not in {t.opportunity_id for t in schedule}],
                quality_model=quality_model,
            ),
        ]

        # Convert schedule to dict for JSON serialization
        report.schedule = [
            {
                "opportunity_id": t.opportunity_id,
                "satellite_id": t.satellite_id,
                "target_id": t.target_id,
                "start_time": t.start_time.isoformat(),
                "end_time": t.end_time.isoformat(),
                "incidence_angle": t.incidence_angle if t.incidence_angle is not None else 0.0,
                "roll_angle": t.roll_angle,
                "pitch_angle": t.pitch_angle,
                "maneuver_time": t.maneuver_time,
                "slack": t.slack_time,
                "value": t.value,
            }
            for t in schedule
        ]

        # Determine overall status
        failed_invariants = [inv for inv in report.invariants if not inv.ok]
        if failed_invariants:
            report.status = "warnings" if not any("exceeds" in inv.details or "negative" in inv.details for inv in failed_invariants if inv.details) else "failed"
            report.warnings.extend([f"{inv.name}: {inv.details}" for inv in failed_invariants if inv.details])

    except Exception as e:
        logger.error(f"Algorithm {algorithm_name} failed: {e}", exc_info=True)
        report.status = "failed"
        report.errors.append(str(e))

    return report


def compare_roll_vs_pitch(
    roll_only_report: AuditReport,
    roll_pitch_report: AuditReport,
) -> Dict[str, Any]:
    """
    Compare roll-only vs roll+pitch algorithm results.

    Args:
        roll_only_report: Audit report for roll-only algorithm
        roll_pitch_report: Audit report for roll+pitch algorithm

    Returns:
        Comparison dict with deltas and regression analysis
    """
    comparison = {
        "delta_accepted": roll_pitch_report.metrics.accepted - roll_only_report.metrics.accepted,
        "delta_value": roll_pitch_report.metrics.total_value - roll_only_report.metrics.total_value,
        "delta_utilization": roll_pitch_report.metrics.utilization - roll_only_report.metrics.utilization,
        "regressions": [],
        "improvements": [],
    }

    # Check for paradoxical regressions
    if comparison["delta_accepted"] < 0:
        # Roll+pitch accepted fewer - check if explainable
        pitch_violations = [inv for inv in roll_pitch_report.invariants if inv.name == "pitch_within_limits" and not inv.ok]

        if not pitch_violations:
            # Unexplained regression
            comparison["regressions"].append({
                "type": "UNEXPLAINED",
                "details": f"Roll+pitch accepted {-comparison['delta_accepted']} fewer opportunities without pitch limit violations",
                "ok": False,
            })
        else:
            # Explained by pitch limits
            comparison["regressions"].append({
                "type": "pitch_over_limit",
                "details": f"Roll+pitch rejected {-comparison['delta_accepted']} due to pitch constraints",
                "ok": True,
            })

    # Check for improvements
    if comparison["delta_accepted"] > 0:
        comparison["improvements"].append({
            "type": "additional_coverage",
            "details": f"Roll+pitch accepted {comparison['delta_accepted']} additional opportunities",
            "value_gained": comparison["delta_value"],
        })

    # Check pitch usage
    if roll_pitch_report.metrics.opps_using_pitch > 0:
        comparison["improvements"].append({
            "type": "pitch_utilization",
            "details": f"{roll_pitch_report.metrics.opps_using_pitch} opportunities used pitch capability",
            "max_pitch_used": roll_pitch_report.metrics.max_pitch_deg,
        })

    return comparison
