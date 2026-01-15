"""
Mission Planning Audit and Debug Module

This module provides deep audit capabilities for mission planning algorithms,
including invariant checking, metrics computation, and scenario benchmarking.
"""

from .planning_audit import (
    AuditReport,
    AlgorithmMetrics,
    InvariantCheck,
    run_algorithm_audit,
    compare_roll_vs_pitch,
    check_no_overlap,
    check_roll_within_limits,
    check_pitch_within_limits,
    check_slack_non_negative,
    check_time_monotonic,
    check_quality_consistency,
    compute_metrics,
)
from .scenarios import (
    Scenario,
    generate_scenario,
    get_preset_scenario,
    PRESET_SCENARIOS,
)

__all__ = [
    "AuditReport",
    "AlgorithmMetrics",
    "InvariantCheck",
    "run_algorithm_audit",
    "compare_roll_vs_pitch",
    "check_no_overlap",
    "check_roll_within_limits",
    "check_pitch_within_limits",
    "check_slack_non_negative",
    "check_time_monotonic",
    "check_quality_consistency",
    "compute_metrics",
    "Scenario",
    "generate_scenario",
    "get_preset_scenario",
    "PRESET_SCENARIOS",
]
