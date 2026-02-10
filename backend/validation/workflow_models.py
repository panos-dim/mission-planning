"""
Workflow Validation Models for Deterministic Scenario Validation.

Defines data structures for:
- Workflow scenarios (analysis → planning → repair → commit)
- Stage-level runtime metrics
- Invariant assertions specific to scheduling workflows
- Deterministic report hashing
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class WorkflowStage(Enum):
    """Stages in the validation workflow."""

    ANALYSIS = "analysis"
    PLANNING = "planning"
    REPAIR = "repair"
    COMMIT_PREVIEW = "commit_preview"
    COMMIT = "commit"
    CONFLICT_RECOMPUTE = "conflict_recompute"


class InvariantType(Enum):
    """Types of workflow invariants."""

    NO_TEMPORAL_OVERLAP = "no_temporal_overlap"
    SLEW_FEASIBILITY = "slew_feasibility"
    HARD_LOCKS_UNCHANGED = "hard_locks_unchanged"
    REPAIR_DIFF_CONSISTENT = "repair_diff_consistent"
    CONFLICT_PREVIEW_MATCH = "conflict_preview_match"
    DETERMINISTIC = "deterministic"


@dataclass
class StageMetrics:
    """Metrics for a single workflow stage."""

    stage: WorkflowStage
    runtime_ms: float = 0.0
    success: bool = True
    error_message: Optional[str] = None
    # Stage-specific counts
    input_count: int = 0
    output_count: int = 0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage.value,
            "runtime_ms": round(self.runtime_ms, 2),
            "success": self.success,
            "error_message": self.error_message,
            "input_count": self.input_count,
            "output_count": self.output_count,
            "details": self.details,
        }


@dataclass
class InvariantResult:
    """Result of an invariant check."""

    invariant: InvariantType
    passed: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    violations: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invariant": self.invariant.value,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
            "violations": self.violations[:10],  # Limit to 10 examples
        }


@dataclass
class RepairDiffSummary:
    """Summary of repair mode changes."""

    kept_count: int = 0
    dropped_count: int = 0
    added_count: int = 0
    moved_count: int = 0
    kept_ids: List[str] = field(default_factory=list)
    dropped_ids: List[str] = field(default_factory=list)
    added_ids: List[str] = field(default_factory=list)
    moved_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kept_count": self.kept_count,
            "dropped_count": self.dropped_count,
            "added_count": self.added_count,
            "moved_count": self.moved_count,
            "kept_ids": self.kept_ids,
            "dropped_ids": self.dropped_ids,
            "added_ids": self.added_ids,
            "moved_ids": self.moved_ids,
        }


@dataclass
class WorkflowCounts:
    """Counts at each stage of the workflow."""

    opportunities: int = 0
    planned: int = 0
    committed: int = 0
    conflicts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunities": self.opportunities,
            "planned": self.planned,
            "committed": self.committed,
            "conflicts": self.conflicts,
        }


@dataclass
class WorkflowMetrics:
    """Overall metrics for the workflow."""

    total_value: float = 0.0
    total_score: float = 0.0
    mean_incidence_deg: Optional[float] = None
    left_swath_count: int = 0
    right_swath_count: int = 0
    ascending_count: int = 0
    descending_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_value": round(self.total_value, 2),
            "total_score": round(self.total_score, 2),
            "mean_incidence_deg": (
                round(self.mean_incidence_deg, 2)
                if self.mean_incidence_deg is not None
                else None
            ),
            "left_swath_count": self.left_swath_count,
            "right_swath_count": self.right_swath_count,
            "ascending_count": self.ascending_count,
            "descending_count": self.descending_count,
        }


@dataclass
class WorkflowScenarioConfig:
    """Configuration for a workflow validation scenario."""

    # Time window
    start_time: str
    end_time: str

    # Mission parameters
    mission_mode: str = "SAR"  # SAR | OPTICAL
    imaging_mode: str = "strip"
    look_side: str = "ANY"
    pass_direction: str = "ANY"

    # Spacecraft constraints
    max_spacecraft_roll_deg: float = 45.0
    max_roll_rate_dps: float = 1.0
    max_pitch_rate_dps: float = 0.5

    # Planning algorithm
    algorithm: str = "first_fit"

    # Repair mode options
    run_repair: bool = False
    max_repair_changes: int = 10

    # Commit options
    dry_run: bool = True  # Default to no DB mutation
    use_temp_workspace: bool = True

    # Determinism
    seed: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "mission_mode": self.mission_mode,
            "imaging_mode": self.imaging_mode,
            "look_side": self.look_side,
            "pass_direction": self.pass_direction,
            "max_spacecraft_roll_deg": self.max_spacecraft_roll_deg,
            "max_roll_rate_dps": self.max_roll_rate_dps,
            "max_pitch_rate_dps": self.max_pitch_rate_dps,
            "algorithm": self.algorithm,
            "run_repair": self.run_repair,
            "max_repair_changes": self.max_repair_changes,
            "dry_run": self.dry_run,
            "use_temp_workspace": self.use_temp_workspace,
            "seed": self.seed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowScenarioConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SatelliteConfig:
    """Satellite configuration for workflow scenarios."""

    id: str
    name: str
    tle_line1: str
    tle_line2: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "tle_line1": self.tle_line1,
            "tle_line2": self.tle_line2,
        }


@dataclass
class TargetConfig:
    """Target configuration for workflow scenarios."""

    id: str
    name: str
    latitude: float
    longitude: float
    priority: int = 1
    lock_level: str = "none"  # none | soft | hard

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "priority": self.priority,
            "lock_level": self.lock_level,
        }


@dataclass
class WorkflowScenario:
    """Complete workflow validation scenario."""

    id: str
    name: str
    description: str
    satellites: List[SatelliteConfig]
    targets: List[TargetConfig]
    config: WorkflowScenarioConfig
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "satellites": [s.to_dict() for s in self.satellites],
            "targets": [t.to_dict() for t in self.targets],
            "config": self.config.to_dict(),
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowScenario":
        satellites = [SatelliteConfig(**s) for s in data.get("satellites", [])]
        targets = [TargetConfig(**t) for t in data.get("targets", [])]
        config = WorkflowScenarioConfig.from_dict(data.get("config", {}))
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            satellites=satellites,
            targets=targets,
            config=config,
            tags=data.get("tags", []),
        )


@dataclass
class WorkflowValidationReport:
    """Complete validation report for a workflow run."""

    report_id: str
    scenario_id: str
    scenario_name: str
    timestamp: str
    config_hash: str

    # Overall status
    passed: bool
    total_invariants: int
    passed_invariants: int
    failed_invariants: int

    # Stage results
    stages: List[StageMetrics] = field(default_factory=list)
    invariants: List[InvariantResult] = field(default_factory=list)

    # Counts and metrics
    counts: WorkflowCounts = field(default_factory=WorkflowCounts)
    metrics: WorkflowMetrics = field(default_factory=WorkflowMetrics)

    # Repair diff (if repair was run)
    repair_diff: Optional[RepairDiffSummary] = None

    # Runtime
    total_runtime_ms: float = 0.0

    # Determinism check
    report_hash: str = ""

    # Errors
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "timestamp": self.timestamp,
            "config_hash": self.config_hash,
            "passed": self.passed,
            "total_invariants": self.total_invariants,
            "passed_invariants": self.passed_invariants,
            "failed_invariants": self.failed_invariants,
            "stages": [s.to_dict() for s in self.stages],
            "invariants": [i.to_dict() for i in self.invariants],
            "counts": self.counts.to_dict(),
            "metrics": self.metrics.to_dict(),
            "repair_diff": self.repair_diff.to_dict() if self.repair_diff else None,
            "total_runtime_ms": round(self.total_runtime_ms, 2),
            "report_hash": self.report_hash,
            "errors": self.errors,
        }

    def compute_report_hash(self) -> str:
        """
        Compute deterministic hash of report results.

        Excludes timing and IDs to ensure same input → same hash.
        """
        # Build deterministic representation
        hashable = {
            "scenario_id": self.scenario_id,
            "config_hash": self.config_hash,
            "passed": self.passed,
            "counts": self.counts.to_dict(),
            "metrics": self.metrics.to_dict(),
            "invariants_passed": [
                i.invariant.value for i in self.invariants if i.passed
            ],
            "invariants_failed": [
                i.invariant.value for i in self.invariants if not i.passed
            ],
        }

        # Sort keys for determinism
        json_str = json.dumps(hashable, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]

    def summary(self) -> str:
        """Generate human-readable summary."""
        status = "✅ PASSED" if self.passed else "❌ FAILED"
        lines = [
            f"Workflow Validation Report: {self.scenario_name}",
            f"Status: {status}",
            f"Invariants: {self.passed_invariants}/{self.total_invariants} passed",
            f"Runtime: {self.total_runtime_ms:.0f}ms",
            f"Report Hash: {self.report_hash}",
            "",
            "Counts:",
            f"  Opportunities: {self.counts.opportunities}",
            f"  Planned: {self.counts.planned}",
            f"  Committed: {self.counts.committed}",
            f"  Conflicts: {self.counts.conflicts}",
        ]

        if self.failed_invariants > 0:
            lines.append("\nFailed Invariants:")
            for inv in self.invariants:
                if not inv.passed:
                    lines.append(f"  - {inv.invariant.value}: {inv.message}")

        if self.errors:
            lines.append("\nErrors:")
            for err in self.errors:
                lines.append(f"  - {err}")

        return "\n".join(lines)


def compute_config_hash(scenario: WorkflowScenario) -> str:
    """Compute hash of scenario configuration for determinism verification."""
    config_dict = scenario.to_dict()
    # Exclude non-deterministic fields
    config_dict.pop("tags", None)
    json_str = json.dumps(config_dict, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]
