"""
SAR Validation Harness Module.

Provides scenario-based validation for SAR mission analysis and planning,
with semantic assertions aligned with ICEYE parity requirements.

Components:
- ScenarioRunner: Execute scenarios and generate validation reports
- AssertionChecker: Verify semantic correctness of SAR computations
- ValidationReport: Structured results with metrics and pass/fail status
- ScenarioStorage: Persistence for scenarios and reports

Workflow Validation (PR-VALIDATION-01):
- WorkflowValidationRunner: Deterministic full-workflow validation
- WorkflowScenario: Scenario config for analysis → planning → repair → commit
- WorkflowValidationReport: Report with invariants and stage metrics
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
from .workflow_assertions import WorkflowInvariantChecker
from .workflow_models import (
    InvariantResult,
    InvariantType,
    RepairDiffSummary,
    SatelliteConfig,
    StageMetrics,
    TargetConfig,
    WorkflowCounts,
    WorkflowMetrics,
    WorkflowScenario,
    WorkflowScenarioConfig,
    WorkflowStage,
    WorkflowValidationReport,
)
from .workflow_runner import WorkflowValidationRunner

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
    # Workflow Validation (PR-VALIDATION-01)
    "WorkflowValidationRunner",
    "WorkflowInvariantChecker",
    "WorkflowScenario",
    "WorkflowScenarioConfig",
    "WorkflowValidationReport",
    "WorkflowStage",
    "StageMetrics",
    "InvariantResult",
    "InvariantType",
    "WorkflowCounts",
    "WorkflowMetrics",
    "RepairDiffSummary",
    "SatelliteConfig",
    "TargetConfig",
]
