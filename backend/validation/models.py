"""
Data models for SAR validation scenarios, reports, and assertions.

These models define the structure for:
- Scenario configuration and inputs
- Validation reports with metrics
- Assertion results with failure details
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AssertionStatus(Enum):
    """Status of a validation assertion."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"  # Assertion not applicable to scenario


@dataclass
class AssertionResult:
    """Result of a single semantic assertion."""

    assertion_name: str
    status: AssertionStatus
    count_checked: int = 0
    count_failed: int = 0
    example_failures: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0  # 0.0 to 1.0
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assertion_name": self.assertion_name,
            "status": self.status.value,
            "count_checked": self.count_checked,
            "count_failed": self.count_failed,
            "example_failures": self.example_failures[:5],  # Limit to 5 examples
            "confidence": round(self.confidence, 3),
            "message": self.message,
        }


@dataclass
class RuntimeMetrics:
    """Timing metrics for scenario execution."""

    total_runtime_s: float = 0.0
    analysis_runtime_s: float = 0.0
    planning_runtime_s: float = 0.0
    czml_derivation_s: float = 0.0
    assertions_runtime_s: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_runtime_s": round(self.total_runtime_s, 3),
            "analysis_runtime_s": round(self.analysis_runtime_s, 3),
            "planning_runtime_s": round(self.planning_runtime_s, 3),
            "czml_derivation_s": round(self.czml_derivation_s, 3),
            "assertions_runtime_s": round(self.assertions_runtime_s, 3),
        }


@dataclass
class OpportunityMetrics:
    """Metrics about SAR opportunities found."""

    total_opportunities: int = 0
    by_target: Dict[str, int] = field(default_factory=dict)
    by_satellite: Dict[str, int] = field(default_factory=dict)
    by_look_side: Dict[str, int] = field(default_factory=dict)  # LEFT/RIGHT counts
    by_pass_direction: Dict[str, int] = field(default_factory=dict)  # ASC/DESC counts
    incidence_stats: Dict[str, float] = field(default_factory=dict)  # mean/min/max

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_opportunities": self.total_opportunities,
            "by_target": self.by_target,
            "by_satellite": self.by_satellite,
            "by_look_side": self.by_look_side,
            "by_pass_direction": self.by_pass_direction,
            "incidence_stats": {
                k: round(v, 2) for k, v in self.incidence_stats.items()
            },
        }


@dataclass
class PlanningMetrics:
    """Metrics for planning algorithm results."""

    algorithm: str = ""
    accepted_count: int = 0
    rejected_count: int = 0
    total_value: float = 0.0
    total_slew_time_s: float = 0.0
    coverage_percent: float = 0.0
    targets_covered: int = 0
    targets_total: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "total_value": round(self.total_value, 2),
            "total_slew_time_s": round(self.total_slew_time_s, 2),
            "coverage_percent": round(self.coverage_percent, 1),
            "targets_covered": self.targets_covered,
            "targets_total": self.targets_total,
        }


@dataclass
class SwathSummary:
    """Summary of CZML swath data for verification."""

    swath_id: str
    target_name: str
    look_side: str
    pass_direction: str
    incidence_center_deg: float
    swath_width_km: float
    scene_length_km: float
    corner_coords: List[List[float]] = field(default_factory=list)  # [[lat, lon], ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "swath_id": self.swath_id,
            "target_name": self.target_name,
            "look_side": self.look_side,
            "pass_direction": self.pass_direction,
            "incidence_center_deg": round(self.incidence_center_deg, 2),
            "swath_width_km": round(self.swath_width_km, 2),
            "scene_length_km": round(self.scene_length_km, 2),
            "corner_coords": [
                [round(c, 4) for c in coord] for coord in self.corner_coords
            ],
        }


@dataclass
class ScenarioConfig:
    """Configuration for a validation scenario."""

    # Time window
    start_time: str  # ISO format
    end_time: str  # ISO format

    # SAR parameters
    imaging_mode: str = "strip"
    look_side: str = "ANY"
    pass_direction: str = "ANY"
    incidence_min_deg: Optional[float] = None
    incidence_max_deg: Optional[float] = None

    # Planning parameters
    max_spacecraft_roll_deg: float = 45.0
    max_roll_rate_dps: float = 1.0
    quality_weight: float = 0.5
    quality_model: str = "band"

    # Execution options
    run_planning: bool = True
    algorithms: List[str] = field(default_factory=lambda: ["first_fit", "best_fit"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "imaging_mode": self.imaging_mode,
            "look_side": self.look_side,
            "pass_direction": self.pass_direction,
            "incidence_min_deg": self.incidence_min_deg,
            "incidence_max_deg": self.incidence_max_deg,
            "max_spacecraft_roll_deg": self.max_spacecraft_roll_deg,
            "max_roll_rate_dps": self.max_roll_rate_dps,
            "quality_weight": self.quality_weight,
            "quality_model": self.quality_model,
            "run_planning": self.run_planning,
            "algorithms": self.algorithms,
        }


@dataclass
class SatelliteInput:
    """Satellite TLE input for scenarios."""

    name: str
    tle_line1: str
    tle_line2: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "tle_line1": self.tle_line1,
            "tle_line2": self.tle_line2,
        }


@dataclass
class TargetInput:
    """Target input for scenarios."""

    name: str
    latitude: float
    longitude: float
    priority: int = 1
    import_source: str = "manual"  # Provenance tracking

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "priority": self.priority,
            "import_source": self.import_source,
        }


@dataclass
class ExpectedInvariants:
    """Expected invariants for scenario validation.

    These are semantic expectations, not exact values.
    """

    # Look side expectations
    expect_left_opportunities: Optional[bool] = None
    expect_right_opportunities: Optional[bool] = None
    expect_single_look_side: Optional[str] = None  # "LEFT" or "RIGHT" if constrained

    # Pass direction expectations
    expect_ascending_passes: Optional[bool] = None
    expect_descending_passes: Optional[bool] = None
    expect_single_pass_direction: Optional[str] = None

    # Incidence expectations
    incidence_must_be_in_range: bool = True

    # Opportunity count expectations (ranges, not exact)
    min_opportunities: Optional[int] = None
    max_opportunities: Optional[int] = None

    # Planning expectations
    expect_all_targets_covered: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "expect_left_opportunities": self.expect_left_opportunities,
            "expect_right_opportunities": self.expect_right_opportunities,
            "expect_single_look_side": self.expect_single_look_side,
            "expect_ascending_passes": self.expect_ascending_passes,
            "expect_descending_passes": self.expect_descending_passes,
            "expect_single_pass_direction": self.expect_single_pass_direction,
            "incidence_must_be_in_range": self.incidence_must_be_in_range,
            "min_opportunities": self.min_opportunities,
            "max_opportunities": self.max_opportunities,
            "expect_all_targets_covered": self.expect_all_targets_covered,
        }


@dataclass
class SARScenario:
    """Complete SAR validation scenario definition."""

    id: str
    name: str
    description: str
    satellites: List[SatelliteInput]
    targets: List[TargetInput]
    config: ScenarioConfig
    expected: ExpectedInvariants = field(default_factory=ExpectedInvariants)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "satellites": [s.to_dict() for s in self.satellites],
            "targets": [t.to_dict() for t in self.targets],
            "config": self.config.to_dict(),
            "expected": self.expected.to_dict(),
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SARScenario":
        """Create scenario from dictionary."""
        satellites = [SatelliteInput(**s) for s in data.get("satellites", [])]
        targets = [TargetInput(**t) for t in data.get("targets", [])]
        config = ScenarioConfig(**data.get("config", {}))
        expected = ExpectedInvariants(**data.get("expected", {}))

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            satellites=satellites,
            targets=targets,
            config=config,
            expected=expected,
            tags=data.get("tags", []),
        )


@dataclass
class ValidationReport:
    """Complete validation report for a scenario run."""

    report_id: str
    scenario_id: str
    scenario_name: str
    timestamp: str  # ISO format

    # Overall status
    passed: bool
    total_assertions: int
    passed_assertions: int
    failed_assertions: int

    # Detailed results
    assertions: List[AssertionResult] = field(default_factory=list)
    opportunity_metrics: Optional[OpportunityMetrics] = None
    planning_metrics: List[PlanningMetrics] = field(default_factory=list)
    swath_summaries: List[SwathSummary] = field(default_factory=list)
    runtime: RuntimeMetrics = field(default_factory=RuntimeMetrics)

    # Raw data for debugging (optional)
    opportunities_data: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "timestamp": self.timestamp,
            "passed": self.passed,
            "total_assertions": self.total_assertions,
            "passed_assertions": self.passed_assertions,
            "failed_assertions": self.failed_assertions,
            "assertions": [a.to_dict() for a in self.assertions],
            "opportunity_metrics": (
                self.opportunity_metrics.to_dict() if self.opportunity_metrics else None
            ),
            "planning_metrics": [p.to_dict() for p in self.planning_metrics],
            "swath_summaries": [s.to_dict() for s in self.swath_summaries],
            "runtime": self.runtime.to_dict(),
            "opportunities_data": self.opportunities_data,
            "errors": self.errors,
        }

    def summary(self) -> str:
        """Generate a human-readable summary."""
        status = "✅ PASSED" if self.passed else "❌ FAILED"
        lines = [
            f"Validation Report: {self.scenario_name}",
            f"Status: {status}",
            f"Assertions: {self.passed_assertions}/{self.total_assertions} passed",
            f"Runtime: {self.runtime.total_runtime_s:.2f}s",
        ]

        if self.opportunity_metrics:
            lines.append(
                f"Opportunities: {self.opportunity_metrics.total_opportunities}"
            )

        if self.failed_assertions > 0:
            lines.append("\nFailed Assertions:")
            for a in self.assertions:
                if a.status == AssertionStatus.FAIL:
                    lines.append(f"  - {a.assertion_name}: {a.message}")

        return "\n".join(lines)
