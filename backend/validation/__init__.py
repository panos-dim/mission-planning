"""
SAR Validation Harness Module.

Provides scenario-based validation for SAR mission analysis and planning,
with semantic assertions aligned with ICEYE parity requirements.

Components:
- ScenarioRunner: Execute scenarios and generate validation reports
- AssertionChecker: Verify semantic correctness of SAR computations
- ValidationReport: Structured results with metrics and pass/fail status
- ScenarioStorage: Persistence for scenarios and reports
"""

from .assertions import SARAssertionChecker
from .models import (
    AssertionResult,
    AssertionStatus,
    PlanningMetrics,
    RuntimeMetrics,
    SARScenario,
    ScenarioConfig,
    SwathSummary,
    ValidationReport,
)
from .scenario_runner import ScenarioRunner
from .storage import ScenarioStorage

__all__ = [
    # Models
    "SARScenario",
    "ScenarioConfig",
    "ValidationReport",
    "AssertionResult",
    "AssertionStatus",
    "RuntimeMetrics",
    "PlanningMetrics",
    "SwathSummary",
    # Core classes
    "ScenarioRunner",
    "SARAssertionChecker",
    "ScenarioStorage",
]
