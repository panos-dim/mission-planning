"""
Incremental Planning Module.

Provides functionality for planning around existing scheduled acquisitions.
This implements the "industry" behavior where planners know what's already
scheduled and plan around it, only suggesting changes when explicitly asked.

Key concepts:
- Planning Mode: from_scratch vs incremental
- Blocked Intervals: Time windows occupied by committed/locked acquisitions
- Lock Policy: Which acquisition states to respect (hard only vs hard+soft)
- Adjacency Feasibility: Slew feasibility relative to neighboring blocked items
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from backend.schedule_persistence import Acquisition, ScheduleDB

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Types
# =============================================================================


class PlanningMode(str, Enum):
    """Planning mode determines how the planner treats existing acquisitions."""

    FROM_SCRATCH = "from_scratch"  # Ignore existing schedule, plan fresh
    INCREMENTAL = "incremental"  # Plan around existing committed/locked acquisitions
    REPAIR = "repair"  # Repair existing schedule: keep hard locks, optionally move/replace soft


class LockPolicy(str, Enum):
    """Lock policy determines which acquisition states are treated as blocked."""

    RESPECT_HARD_ONLY = "respect_hard_only"  # Only hard-locked items block planning
    RESPECT_HARD_AND_SOFT = "respect_hard_and_soft"  # Both hard and soft locks block


class RepairScope(str, Enum):
    """Scope of repair operation."""

    WORKSPACE_HORIZON = "workspace_horizon"  # Repair entire workspace within horizon
    SATELLITE_SUBSET = "satellite_subset"  # Repair only specified satellites
    TARGET_SUBSET = "target_subset"  # Repair only specified targets


class RepairObjective(str, Enum):
    """Optimization objective for repair mode."""

    MAXIMIZE_SCORE = "maximize_score"  # Maximize total schedule value
    MAXIMIZE_PRIORITY = "maximize_priority"  # Prioritize high-priority targets
    MINIMIZE_CHANGES = "minimize_changes"  # Make fewest changes to existing schedule


class RepairReasonCode(str, Enum):
    """Deterministic reason codes for repair changes."""

    HARD_LOCK_CONSTRAINT = "HARD_LOCK_CONSTRAINT"
    CONFLICT_RESOLUTION = "CONFLICT_RESOLUTION"
    PRIORITY_UPGRADE = "PRIORITY_UPGRADE"
    QUALITY_SCORE_UPGRADE = "QUALITY_SCORE_UPGRADE"
    SLEW_CHAIN_FEASIBILITY = "SLEW_CHAIN_FEASIBILITY"
    HORIZON_LIMIT = "HORIZON_LIMIT"
    RESOURCE_LIMIT = "RESOURCE_LIMIT"
    KEPT_UNCHANGED = "KEPT_UNCHANGED"
    ADDED_NEW = "ADDED_NEW"


@dataclass
class BlockedInterval:
    """
    Represents a time interval blocked by an existing acquisition.

    Used by incremental planner to avoid scheduling conflicts.
    """

    acquisition_id: str
    satellite_id: str
    target_id: str
    start_time: datetime
    end_time: datetime
    roll_angle_deg: float
    pitch_angle_deg: float = 0.0
    state: str = "committed"
    lock_level: str = "none"

    @property
    def duration_s(self) -> float:
        """Duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()


@dataclass
class IncrementalPlanningContext:
    """
    Context for incremental planning containing blocked intervals and config.

    This is passed to the planner to provide awareness of existing schedule.
    """

    mode: PlanningMode = PlanningMode.FROM_SCRATCH
    lock_policy: LockPolicy = LockPolicy.RESPECT_HARD_ONLY
    horizon_start: Optional[datetime] = None
    horizon_end: Optional[datetime] = None
    workspace_id: Optional[str] = None
    include_tentative: bool = False

    # Blocked intervals per satellite
    blocked_intervals: Dict[str, List[BlockedInterval]] = field(default_factory=dict)

    # Summary statistics
    loaded_acquisitions_count: int = 0
    loaded_acquisitions_by_state: Dict[str, int] = field(default_factory=dict)

    def get_blocked_for_satellite(self, satellite_id: str) -> List[BlockedInterval]:
        """Get blocked intervals for a specific satellite, sorted by start time."""
        intervals = self.blocked_intervals.get(satellite_id, [])
        return sorted(intervals, key=lambda x: x.start_time)

    def is_time_blocked(
        self,
        satellite_id: str,
        start_time: datetime,
        end_time: datetime,
        margin_s: float = 0.0,
    ) -> Tuple[bool, Optional[BlockedInterval]]:
        """
        Check if a time window overlaps with any blocked interval.

        Args:
            satellite_id: Satellite ID to check
            start_time: Candidate start time
            end_time: Candidate end time
            margin_s: Optional safety margin in seconds

        Returns:
            Tuple of (is_blocked, blocking_interval or None)
        """
        # Normalize candidate times to naive UTC for comparison
        _start = start_time.replace(tzinfo=None) if start_time.tzinfo else start_time
        _end = end_time.replace(tzinfo=None) if end_time.tzinfo else end_time

        for interval in self.get_blocked_for_satellite(satellite_id):
            # Apply margin and normalize to naive UTC
            i_start = (
                interval.start_time.replace(tzinfo=None)
                if interval.start_time.tzinfo
                else interval.start_time
            )
            i_end = (
                interval.end_time.replace(tzinfo=None)
                if interval.end_time.tzinfo
                else interval.end_time
            )
            interval_start = i_start - timedelta(seconds=margin_s)
            interval_end = i_end + timedelta(seconds=margin_s)

            # Check for overlap: candidate.start < interval.end AND candidate.end > interval.start
            if _start < interval_end and _end > interval_start:
                return True, interval

        return False, None

    def get_neighbors(
        self,
        satellite_id: str,
        candidate_start: datetime,
        candidate_end: datetime,
    ) -> Tuple[Optional[BlockedInterval], Optional[BlockedInterval]]:
        """
        Find the previous and next blocked intervals relative to a candidate.

        Used for adjacency feasibility checks (slew feasibility with neighbors).

        Args:
            satellite_id: Satellite ID
            candidate_start: Candidate acquisition start time
            candidate_end: Candidate acquisition end time

        Returns:
            Tuple of (previous_interval, next_interval) - either can be None
        """
        intervals = self.get_blocked_for_satellite(satellite_id)

        previous: Optional[BlockedInterval] = None
        next_interval: Optional[BlockedInterval] = None

        # Normalize candidate times to naive UTC
        _start = (
            candidate_start.replace(tzinfo=None)
            if candidate_start.tzinfo
            else candidate_start
        )
        _end = (
            candidate_end.replace(tzinfo=None)
            if candidate_end.tzinfo
            else candidate_end
        )

        for interval in intervals:
            i_end = (
                interval.end_time.replace(tzinfo=None)
                if interval.end_time.tzinfo
                else interval.end_time
            )
            i_start = (
                interval.start_time.replace(tzinfo=None)
                if interval.start_time.tzinfo
                else interval.start_time
            )
            if i_end <= _start:
                # This interval ends before candidate starts - potential previous
                if previous is None or i_end > (
                    previous.end_time.replace(tzinfo=None)
                    if previous.end_time.tzinfo
                    else previous.end_time
                ):
                    previous = interval
            elif i_start >= _end:
                # This interval starts after candidate ends - potential next
                if next_interval is None or i_start < (
                    next_interval.start_time.replace(tzinfo=None)
                    if next_interval.start_time.tzinfo
                    else next_interval.start_time
                ):
                    next_interval = interval

        return previous, next_interval


@dataclass
class FlexibleAcquisition:
    """
    Represents an acquisition that can be modified during repair.

    Tracks original state and any proposed changes.
    """

    acquisition_id: str
    satellite_id: str
    target_id: str
    original_start: datetime
    original_end: datetime
    roll_angle_deg: float
    pitch_angle_deg: float = 0.0
    value: float = 1.0
    lock_level: str = "none"
    # Proposed changes (None = keep original)
    proposed_start: Optional[datetime] = None
    proposed_end: Optional[datetime] = None
    proposed_roll_deg: Optional[float] = None
    proposed_pitch_deg: Optional[float] = None
    # Status
    action: str = "keep"  # keep | drop | shift | replace

    @property
    def is_modified(self) -> bool:
        """Check if this acquisition has been modified."""
        return self.action != "keep"

    def to_blocked_interval(self) -> BlockedInterval:
        """Convert to BlockedInterval using effective (proposed or original) values."""
        return BlockedInterval(
            acquisition_id=self.acquisition_id,
            satellite_id=self.satellite_id,
            target_id=self.target_id,
            start_time=self.proposed_start or self.original_start,
            end_time=self.proposed_end or self.original_end,
            roll_angle_deg=self.proposed_roll_deg or self.roll_angle_deg,
            pitch_angle_deg=self.proposed_pitch_deg or self.pitch_angle_deg,
            lock_level=self.lock_level,
        )


@dataclass
class RepairPlanningContext:
    """
    Context for repair planning with fixed and flexible acquisition sets.

    Extends IncrementalPlanningContext with repair-specific partitioning.
    """

    mode: PlanningMode = PlanningMode.REPAIR
    repair_scope: RepairScope = RepairScope.WORKSPACE_HORIZON
    objective: RepairObjective = RepairObjective.MAXIMIZE_SCORE
    max_changes: int = 100  # Cap on how disruptive repair can be

    horizon_start: Optional[datetime] = None
    horizon_end: Optional[datetime] = None
    workspace_id: Optional[str] = None

    # Scope filters
    satellite_subset: List[str] = field(default_factory=list)
    target_subset: List[str] = field(default_factory=list)

    # Partitioned acquisition sets
    fixed_set: List[BlockedInterval] = field(
        default_factory=list
    )  # Hard locks - immutable
    flex_set: List[FlexibleAcquisition] = field(
        default_factory=list
    )  # Soft - can modify

    # Summary statistics
    original_acquisition_count: int = 0
    original_score: float = 0.0
    original_conflict_count: int = 0

    def get_fixed_for_satellite(self, satellite_id: str) -> List[BlockedInterval]:
        """Get fixed (immutable) intervals for a satellite."""
        return sorted(
            [b for b in self.fixed_set if b.satellite_id == satellite_id],
            key=lambda x: x.start_time,
        )

    def get_flex_for_satellite(self, satellite_id: str) -> List[FlexibleAcquisition]:
        """Get flexible acquisitions for a satellite."""
        return sorted(
            [f for f in self.flex_set if f.satellite_id == satellite_id],
            key=lambda x: x.original_start,
        )

    def get_all_blocked_intervals(self) -> Dict[str, List[BlockedInterval]]:
        """Build blocked intervals from fixed set + kept flex items."""
        result: Dict[str, List[BlockedInterval]] = {}

        # Add all fixed items
        for interval in self.fixed_set:
            if interval.satellite_id not in result:
                result[interval.satellite_id] = []
            result[interval.satellite_id].append(interval)

        # Add kept/shifted flex items (but not dropped ones)
        for flex in self.flex_set:
            if flex.action in ("keep", "shift"):
                if flex.satellite_id not in result:
                    result[flex.satellite_id] = []
                result[flex.satellite_id].append(flex.to_blocked_interval())

        # Sort each satellite's intervals
        for sat_id in result:
            result[sat_id] = sorted(result[sat_id], key=lambda x: x.start_time)

        return result


# =============================================================================
# Pydantic Models for API
# =============================================================================


class IncrementalPlanningParams(BaseModel):
    """Parameters for incremental planning request."""

    planning_mode: str = Field(
        default="from_scratch",
        description="Planning mode: 'from_scratch' or 'incremental'",
    )
    horizon_from: Optional[str] = Field(
        default=None,
        description="Horizon start time (ISO format). Default: now",
    )
    horizon_to: Optional[str] = Field(
        default=None,
        description="Horizon end time (ISO format). Default: +7 days",
    )
    workspace_id: Optional[str] = Field(
        default=None,
        description="Workspace ID to load existing acquisitions from",
    )
    include_tentative: bool = Field(
        default=False,
        description="Include tentative acquisitions as blocked intervals",
    )
    lock_policy: str = Field(
        default="respect_hard_only",
        description="Lock policy: 'respect_hard_only' or 'respect_hard_and_soft'",
    )


class ExistingAcquisitionsSummary(BaseModel):
    """Summary of existing acquisitions loaded for incremental planning."""

    count: int = 0
    by_state: Dict[str, int] = Field(default_factory=dict)
    by_satellite: Dict[str, int] = Field(default_factory=dict)
    acquisition_ids: List[str] = Field(default_factory=list)
    horizon_start: Optional[str] = None
    horizon_end: Optional[str] = None


class PlanItemPreview(BaseModel):
    """Preview of a planned item."""

    opportunity_id: str
    satellite_id: str
    target_id: str
    start_time: str
    end_time: str
    roll_angle_deg: float
    pitch_angle_deg: float = 0.0
    value: Optional[float] = None
    quality_score: Optional[float] = None


class CommitPreview(BaseModel):
    """Preview of what will happen on commit."""

    will_create: int = 0
    will_conflict_with: int = 0
    conflict_details: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class IncrementalPlanResponse(BaseModel):
    """Response from incremental planning endpoint."""

    success: bool
    message: str
    planning_mode: str
    existing_acquisitions: ExistingAcquisitionsSummary
    new_plan_items: List[PlanItemPreview] = Field(default_factory=list)
    conflicts_if_committed: List[Dict[str, Any]] = Field(default_factory=list)
    commit_preview: CommitPreview
    algorithm_metrics: Dict[str, Any] = Field(default_factory=dict)
    plan_id: Optional[str] = None


# =============================================================================
# Repair Mode Pydantic Models
# =============================================================================


class RepairPlanRequest(BaseModel):
    """Request for repair planning."""

    # Planning mode (must be 'repair')
    planning_mode: str = Field(
        default="repair",
        description="Planning mode: must be 'repair'",
    )

    # Horizon parameters
    horizon_from: Optional[str] = Field(
        default=None,
        description="Horizon start time (ISO format). Default: now",
    )
    horizon_to: Optional[str] = Field(
        default=None,
        description="Horizon end time (ISO format). Default: +7 days",
    )

    # Workspace and filtering
    workspace_id: Optional[str] = Field(
        default=None,
        description="Workspace ID to load existing acquisitions from",
    )
    include_tentative: bool = Field(
        default=True,
        description="Include tentative acquisitions in repair scope",
    )

    # Repair-specific parameters
    repair_scope: str = Field(
        default="workspace_horizon",
        description="Repair scope: 'workspace_horizon', 'satellite_subset', or 'target_subset'",
    )
    max_changes: int = Field(
        default=100,
        description="Maximum number of changes allowed (cap disruption)",
        ge=0,
    )
    objective: str = Field(
        default="maximize_score",
        description="Optimization objective: 'maximize_score', 'maximize_priority', or 'minimize_changes'",
    )

    # Scope filters (used when repair_scope is satellite_subset or target_subset)
    satellite_subset: List[str] = Field(
        default_factory=list,
        description="Satellites to include in repair (empty = all)",
    )
    target_subset: List[str] = Field(
        default_factory=list,
        description="Targets to include in repair (empty = all)",
    )

    # Planning parameters (forwarded to mission planner)
    imaging_time_s: float = Field(
        default=1.0, description="Imaging duration per target"
    )
    max_roll_rate_dps: float = Field(default=1.0, description="Max roll rate deg/s")
    max_roll_accel_dps2: float = Field(
        default=10000.0, description="Max roll acceleration"
    )
    max_pitch_rate_dps: float = Field(default=1.0, description="Max pitch rate deg/s")
    max_pitch_accel_dps2: float = Field(
        default=10000.0, description="Max pitch acceleration"
    )
    look_window_s: float = Field(default=600.0, description="Look-ahead window seconds")
    value_source: str = Field(
        default="target_priority", description="Value source for scoring"
    )


class MovedAcquisitionInfo(BaseModel):
    """Info about an acquisition that was moved during repair."""

    id: str
    from_start: str
    from_end: str
    to_start: str
    to_end: str
    from_roll_deg: Optional[float] = None
    to_roll_deg: Optional[float] = None


class DropReasonInfo(BaseModel):
    """Reason why an acquisition was dropped during repair."""

    id: str
    reason: str


class MoveReasonInfo(BaseModel):
    """Reason why an acquisition was moved during repair."""

    id: str
    reason: str


# ---- PR-OPS-REPAIR-REPORT-01: Structured change log entries ----


class DroppedEntry(BaseModel):
    """Structured entry for a dropped acquisition."""

    acquisition_id: str
    satellite_id: str
    target_id: str
    start: str
    end: str
    reason_code: str  # RepairReasonCode value
    reason_text: str
    replaced_by: List[str] = Field(default_factory=list)


class AddedEntry(BaseModel):
    """Structured entry for a newly added acquisition."""

    acquisition_id: str
    satellite_id: str
    target_id: str
    start: str
    end: str
    reason_code: str  # RepairReasonCode value
    reason_text: str
    replaces: List[str] = Field(default_factory=list)
    value: Optional[float] = None


class MovedEntry(BaseModel):
    """Structured entry for a moved acquisition."""

    acquisition_id: str
    satellite_id: str
    target_id: str
    from_start: str
    from_end: str
    to_start: str
    to_end: str
    reason_code: str  # RepairReasonCode value
    reason_text: str


class ChangeScore(BaseModel):
    """Summary of changes made during repair."""

    num_changes: int = 0
    percent_changed: float = 0.0


class RepairDiff(BaseModel):
    """Diff object showing what changed during repair."""

    kept: List[str] = Field(
        default_factory=list, description="Acquisition IDs that were kept unchanged"
    )
    dropped: List[str] = Field(
        default_factory=list, description="Acquisition IDs that were dropped"
    )
    added: List[str] = Field(
        default_factory=list, description="New opportunity IDs that were added"
    )
    moved: List[MovedAcquisitionInfo] = Field(
        default_factory=list, description="Acquisitions that were moved"
    )
    reason_summary: Dict[str, List[Dict[str, str]]] = Field(
        default_factory=dict,
        description="Reasons for drops and moves",
    )
    change_score: ChangeScore = Field(default_factory=ChangeScore)
    hard_lock_warnings: List[str] = Field(
        default_factory=list,
        description="Warnings about hard-locked acquisitions that could not be resolved",
    )
    # PR-OPS-REPAIR-REPORT-01: Structured change log
    change_log: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured change log with dropped/added/moved entries and reason_codes",
    )


class MetricsComparison(BaseModel):
    """Before vs after metrics comparison."""

    score_before: float = 0.0
    score_after: float = 0.0
    score_delta: float = 0.0
    mean_incidence_before: Optional[float] = None
    mean_incidence_after: Optional[float] = None
    conflicts_before: int = 0
    conflicts_after: int = 0
    acquisition_count_before: int = 0
    acquisition_count_after: int = 0


class RepairPlanResponse(BaseModel):
    """Response from repair planning endpoint."""

    success: bool
    message: str
    planning_mode: str = "repair"

    # Schedule context
    existing_acquisitions: ExistingAcquisitionsSummary
    fixed_count: int = Field(
        default=0, description="Number of hard-locked (immutable) acquisitions"
    )
    flex_count: int = Field(
        default=0, description="Number of soft-locked (flexible) acquisitions"
    )

    # Proposed schedule
    new_plan_items: List[PlanItemPreview] = Field(default_factory=list)

    # Repair diff (critical)
    repair_diff: RepairDiff = Field(default_factory=RepairDiff)

    # Metrics comparison
    metrics_before: Dict[str, Any] = Field(default_factory=dict)
    metrics_after: Dict[str, Any] = Field(default_factory=dict)
    metrics_comparison: MetricsComparison = Field(default_factory=MetricsComparison)

    # Conflict prediction
    conflicts_if_committed: List[Dict[str, Any]] = Field(default_factory=list)

    # Commit preview
    commit_preview: CommitPreview = Field(default_factory=CommitPreview)

    # Algorithm metrics
    algorithm_metrics: Dict[str, Any] = Field(default_factory=dict)
    plan_id: Optional[str] = None
    schedule_context: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Horizon Loading and Blocked Intervals Builder
# =============================================================================


def load_blocked_intervals(
    db: ScheduleDB,
    workspace_id: str,
    horizon_start: datetime,
    horizon_end: datetime,
    lock_policy: LockPolicy = LockPolicy.RESPECT_HARD_ONLY,
    include_tentative: bool = False,
) -> IncrementalPlanningContext:
    """
    Load existing acquisitions and build blocked intervals for incremental planning.

    This is the key function that queries the schedule database and builds
    the context that the planner uses to avoid conflicts.

    Args:
        db: Schedule database instance
        workspace_id: Workspace to query
        horizon_start: Start of planning horizon
        horizon_end: End of planning horizon
        lock_policy: Which lock levels to respect
        include_tentative: Include tentative acquisitions as blocked

    Returns:
        IncrementalPlanningContext with blocked intervals
    """
    context = IncrementalPlanningContext(
        mode=PlanningMode.INCREMENTAL,
        lock_policy=lock_policy,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        workspace_id=workspace_id,
        include_tentative=include_tentative,
    )

    # Build query filters based on lock policy
    start_str = horizon_start.isoformat() + "Z"
    end_str = horizon_end.isoformat() + "Z"

    # Get all acquisitions in horizon
    acquisitions = db.get_acquisitions_in_horizon(
        start_time=start_str,
        end_time=end_str,
        workspace_id=workspace_id,
        include_tentative=include_tentative,
    )

    logger.info(
        f"[IncrementalPlanning] Loaded {len(acquisitions)} acquisitions from horizon "
        f"{horizon_start.isoformat()} to {horizon_end.isoformat()}"
    )

    # Filter based on state and lock policy
    blocked_acquisitions: List[Acquisition] = []

    for acq in acquisitions:
        should_block = False

        # Always block committed, locked, and executing states
        if acq.state in ("committed", "locked", "executing"):
            should_block = True

        # Check lock level based on policy
        if lock_policy == LockPolicy.RESPECT_HARD_ONLY:
            # Only hard locks are respected as absolute blocks
            if acq.lock_level == "hard":
                should_block = True
            elif acq.state in ("committed", "locked", "executing"):
                # Still block committed states even without hard lock
                should_block = True
        else:
            # Respect hard locks only (soft locks no longer exist)
            if acq.lock_level == "hard":
                should_block = True

        # Optionally include tentative
        if include_tentative and acq.state == "tentative":
            should_block = True

        if should_block:
            blocked_acquisitions.append(acq)

    logger.info(
        f"[IncrementalPlanning] {len(blocked_acquisitions)} acquisitions will block planning "
        f"(policy: {lock_policy.value}, include_tentative: {include_tentative})"
    )

    # Build blocked intervals per satellite
    state_counts: Dict[str, int] = {}

    for acq in blocked_acquisitions:
        # Parse times
        try:
            start_dt = datetime.fromisoformat(acq.start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(acq.end_time.replace("Z", "+00:00"))
        except ValueError:
            logger.warning(f"Failed to parse times for acquisition {acq.id}")
            continue

        # Create blocked interval
        interval = BlockedInterval(
            acquisition_id=acq.id,
            satellite_id=acq.satellite_id,
            target_id=acq.target_id,
            start_time=start_dt,
            end_time=end_dt,
            roll_angle_deg=acq.roll_angle_deg,
            pitch_angle_deg=acq.pitch_angle_deg or 0.0,
            state=acq.state,
            lock_level=acq.lock_level,
        )

        # Add to satellite's blocked list
        if acq.satellite_id not in context.blocked_intervals:
            context.blocked_intervals[acq.satellite_id] = []
        context.blocked_intervals[acq.satellite_id].append(interval)

        # Track state counts
        state_counts[acq.state] = state_counts.get(acq.state, 0) + 1

    context.loaded_acquisitions_count = len(blocked_acquisitions)
    context.loaded_acquisitions_by_state = state_counts

    return context


# =============================================================================
# Feasibility Checks with Blocked Intervals
# =============================================================================


@dataclass
class SlewConfig:
    """Configuration for slew feasibility calculations."""

    roll_slew_rate_deg_per_sec: float = 1.0
    pitch_slew_rate_deg_per_sec: float = 1.0
    settling_time_s: float = 5.0
    parallel_slew: bool = True  # Roll and pitch slew simultaneously


def check_adjacency_feasibility(
    context: IncrementalPlanningContext,
    satellite_id: str,
    candidate_start: datetime,
    candidate_end: datetime,
    candidate_roll_deg: float,
    candidate_pitch_deg: float = 0.0,
    slew_config: Optional[SlewConfig] = None,
) -> Tuple[bool, List[str]]:
    """
    Check if a candidate acquisition is feasible relative to its blocked neighbors.

    This ensures:
    1. The candidate doesn't overlap with any blocked interval
    2. There's enough time to slew from the previous blocked item (if any)
    3. There's enough time to slew to the next blocked item (if any)

    Args:
        context: Incremental planning context with blocked intervals
        satellite_id: Satellite ID
        candidate_start: Candidate start time
        candidate_end: Candidate end time
        candidate_roll_deg: Candidate roll angle
        candidate_pitch_deg: Candidate pitch angle
        slew_config: Slew configuration (uses defaults if None)

    Returns:
        Tuple of (is_feasible, list of rejection reasons)
    """
    if slew_config is None:
        slew_config = SlewConfig()

    reasons: List[str] = []

    # Check 1: No overlap with blocked intervals
    is_blocked, blocking_interval = context.is_time_blocked(
        satellite_id, candidate_start, candidate_end
    )

    if is_blocked and blocking_interval:
        reasons.append(
            f"Overlaps with blocked acquisition {blocking_interval.acquisition_id} "
            f"({blocking_interval.target_id}: {blocking_interval.start_time.isoformat()} - "
            f"{blocking_interval.end_time.isoformat()})"
        )
        return False, reasons

    # Check 2: Slew feasibility with neighbors
    previous, next_interval = context.get_neighbors(
        satellite_id, candidate_start, candidate_end
    )

    # Normalize candidate times to naive UTC for arithmetic
    _cand_start = (
        candidate_start.replace(tzinfo=None)
        if candidate_start.tzinfo
        else candidate_start
    )
    _cand_end = (
        candidate_end.replace(tzinfo=None) if candidate_end.tzinfo else candidate_end
    )

    # Check slew from previous
    if previous is not None:
        _prev_end = (
            previous.end_time.replace(tzinfo=None)
            if previous.end_time.tzinfo
            else previous.end_time
        )
        available_time_s = (_cand_start - _prev_end).total_seconds()

        # Calculate required slew time
        roll_delta = abs(candidate_roll_deg - previous.roll_angle_deg)
        pitch_delta = abs(candidate_pitch_deg - previous.pitch_angle_deg)

        roll_time = roll_delta / slew_config.roll_slew_rate_deg_per_sec
        pitch_time = pitch_delta / slew_config.pitch_slew_rate_deg_per_sec

        if slew_config.parallel_slew:
            total_slew_time = max(roll_time, pitch_time)
        else:
            total_slew_time = roll_time + pitch_time

        required_time = total_slew_time + slew_config.settling_time_s

        if available_time_s < required_time:
            deficit = required_time - available_time_s
            reasons.append(
                f"Insufficient slew time from previous acquisition {previous.acquisition_id}: "
                f"need {required_time:.1f}s but only {available_time_s:.1f}s available "
                f"(deficit: {deficit:.1f}s)"
            )

    # Check slew to next
    if next_interval is not None:
        _next_start = (
            next_interval.start_time.replace(tzinfo=None)
            if next_interval.start_time.tzinfo
            else next_interval.start_time
        )
        available_time_s = (_next_start - _cand_end).total_seconds()

        # Calculate required slew time
        roll_delta = abs(next_interval.roll_angle_deg - candidate_roll_deg)
        pitch_delta = abs(next_interval.pitch_angle_deg - candidate_pitch_deg)

        roll_time = roll_delta / slew_config.roll_slew_rate_deg_per_sec
        pitch_time = pitch_delta / slew_config.pitch_slew_rate_deg_per_sec

        if slew_config.parallel_slew:
            total_slew_time = max(roll_time, pitch_time)
        else:
            total_slew_time = roll_time + pitch_time

        required_time = total_slew_time + slew_config.settling_time_s

        if available_time_s < required_time:
            deficit = required_time - available_time_s
            reasons.append(
                f"Insufficient slew time to next acquisition {next_interval.acquisition_id}: "
                f"need {required_time:.1f}s but only {available_time_s:.1f}s available "
                f"(deficit: {deficit:.1f}s)"
            )

    is_feasible = len(reasons) == 0
    return is_feasible, reasons


def filter_opportunities_incremental(
    opportunities: List[Dict[str, Any]],
    context: IncrementalPlanningContext,
    slew_config: Optional[SlewConfig] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Filter opportunities based on blocked intervals.

    Args:
        opportunities: List of candidate opportunities (dicts with timing/geometry)
        context: Incremental planning context
        slew_config: Slew configuration

    Returns:
        Tuple of (feasible_opportunities, rejected_opportunities_with_reasons)
    """
    if context.mode == PlanningMode.FROM_SCRATCH:
        # No filtering in from_scratch mode
        return opportunities, []

    feasible = []
    rejected = []

    for opp in opportunities:
        try:
            # Parse opportunity data
            satellite_id = opp.get("satellite_id", "unknown")
            start_str = opp.get("start_time", "")
            end_str = opp.get("end_time", "")
            roll_deg = opp.get("roll_angle_deg", opp.get("roll_angle", 0.0))
            pitch_deg = opp.get("pitch_angle_deg", opp.get("pitch_angle", 0.0))

            # Parse times and remove timezone info for comparison
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

            # Convert to naive UTC for comparison with blocked intervals
            if start_dt.tzinfo is not None:
                start_dt = start_dt.replace(tzinfo=None)
            if end_dt.tzinfo is not None:
                end_dt = end_dt.replace(tzinfo=None)

            # Check feasibility
            is_feasible, reasons = check_adjacency_feasibility(
                context=context,
                satellite_id=satellite_id,
                candidate_start=start_dt,
                candidate_end=end_dt,
                candidate_roll_deg=roll_deg,
                candidate_pitch_deg=pitch_deg,
                slew_config=slew_config,
            )

            if is_feasible:
                feasible.append(opp)
            else:
                rejected.append(
                    {
                        **opp,
                        "rejection_reasons": reasons,
                    }
                )

        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to process opportunity: {e}")
            rejected.append(
                {
                    **opp,
                    "rejection_reasons": [f"Parse error: {str(e)}"],
                }
            )

    logger.info(
        f"[IncrementalPlanning] Filtered opportunities: "
        f"{len(feasible)} feasible, {len(rejected)} rejected"
    )
    for r in rejected:
        logger.info(
            f"[IncrementalPlanning]   REJECTED: {r.get('satellite_id')}→{r.get('target_id')} "
            f"at {r.get('start_time', '?')[:19]} — {'; '.join(r.get('rejection_reasons', ['unknown']))}"
        )

    return feasible, rejected


# =============================================================================
# Pre-Commit Conflict Prediction
# =============================================================================


def predict_commit_conflicts(
    db: ScheduleDB,
    workspace_id: str,
    new_items: List[Dict[str, Any]],
    horizon_start: datetime,
    horizon_end: datetime,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Predict conflicts that would occur if new items were committed.

    This runs the conflict detection logic on the combined set of
    existing acquisitions + new items to predict conflicts before commit.

    Args:
        db: Schedule database
        workspace_id: Workspace ID
        new_items: New plan items to be committed
        horizon_start: Horizon start
        horizon_end: Horizon end

    Returns:
        Tuple of (predicted conflicts, conflict count)
    """
    from backend.conflict_detection import ConflictDetectionConfig, ConflictDetector

    # Create a temporary detector
    detector = ConflictDetector(db)

    # Get existing acquisitions
    start_str = horizon_start.isoformat() + "Z"
    end_str = horizon_end.isoformat() + "Z"

    existing = db.get_acquisitions_in_horizon(
        start_time=start_str,
        end_time=end_str,
        workspace_id=workspace_id,
        include_tentative=False,
    )

    # Create pseudo-acquisitions from new items for conflict checking
    from backend.schedule_persistence import Acquisition

    pseudo_acquisitions = []
    for idx, item in enumerate(new_items):
        pseudo = Acquisition(
            id=f"pseudo_{idx}",
            created_at=datetime.now(timezone.utc).isoformat() + "Z",
            updated_at=datetime.now(timezone.utc).isoformat() + "Z",
            satellite_id=item.get("satellite_id", "unknown"),
            target_id=item.get("target_id", "unknown"),
            start_time=item.get("start_time", ""),
            end_time=item.get("end_time", ""),
            mode="OPTICAL",
            roll_angle_deg=item.get("roll_angle_deg", 0.0),
            pitch_angle_deg=item.get("pitch_angle_deg", 0.0),
            incidence_angle_deg=None,
            look_side=None,
            pass_direction=None,
            sar_mode=None,
            swath_width_km=None,
            scene_length_km=None,
            state="tentative",
            lock_level="none",
            source="preview",
            order_id=None,
            plan_id=None,
            opportunity_id=None,
            quality_score=None,
            maneuver_time_s=None,
            slack_time_s=None,
            workspace_id=workspace_id,
        )
        pseudo_acquisitions.append(pseudo)

    # Combine and detect conflicts
    all_acquisitions = list(existing) + pseudo_acquisitions

    # Group by satellite
    by_satellite: Dict[str, List[Acquisition]] = {}
    for acq in all_acquisitions:
        if acq.satellite_id not in by_satellite:
            by_satellite[acq.satellite_id] = []
        by_satellite[acq.satellite_id].append(acq)

    # Detect conflicts using the detector's internal methods
    predicted_conflicts: List[Dict[str, Any]] = []

    for satellite_id, sat_acqs in by_satellite.items():
        # Sort by start time
        sat_acqs_sorted = sorted(sat_acqs, key=lambda x: x.start_time)

        # Check temporal overlaps
        overlaps = detector._detect_temporal_overlaps(sat_acqs_sorted, satellite_id)
        for conflict in overlaps:
            predicted_conflicts.append(
                {
                    "type": conflict.type,
                    "severity": conflict.severity,
                    "description": conflict.description,
                    "acquisition_ids": conflict.acquisition_ids,
                    "involves_new_item": any(
                        aid.startswith("pseudo_") for aid in conflict.acquisition_ids
                    ),
                }
            )

        # Check slew feasibility
        slew_issues = detector._detect_slew_infeasible(sat_acqs_sorted, satellite_id)
        for conflict in slew_issues:
            predicted_conflicts.append(
                {
                    "type": conflict.type,
                    "severity": conflict.severity,
                    "description": conflict.description,
                    "acquisition_ids": conflict.acquisition_ids,
                    "involves_new_item": any(
                        aid.startswith("pseudo_") for aid in conflict.acquisition_ids
                    ),
                }
            )

    return predicted_conflicts, len(predicted_conflicts)


# =============================================================================
# Repair Mode Functions
# =============================================================================


def load_repair_context(
    db: ScheduleDB,
    workspace_id: str,
    horizon_start: datetime,
    horizon_end: datetime,
    repair_scope: RepairScope = RepairScope.WORKSPACE_HORIZON,
    satellite_subset: Optional[List[str]] = None,
    target_subset: Optional[List[str]] = None,
    include_tentative: bool = True,
) -> RepairPlanningContext:
    """
    Load existing acquisitions and partition into fixed/flex sets for repair.

    Stage A of repair: Build the "fixed backbone" and identify flex items.

    Args:
        db: Schedule database instance
        workspace_id: Workspace to query
        horizon_start: Start of planning horizon
        horizon_end: End of planning horizon
        repair_scope: Scope of repair operation
        satellite_subset: If repair_scope is satellite_subset, which satellites to include
        target_subset: If repair_scope is target_subset, which targets to include
        include_tentative: Include tentative acquisitions in repair scope

    Returns:
        RepairPlanningContext with fixed and flex sets partitioned
    """
    context = RepairPlanningContext(
        mode=PlanningMode.REPAIR,
        repair_scope=repair_scope,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        workspace_id=workspace_id,
        satellite_subset=satellite_subset or [],
        target_subset=target_subset or [],
    )

    # Query acquisitions in horizon
    start_str = horizon_start.isoformat() + "Z"
    end_str = horizon_end.isoformat() + "Z"

    acquisitions = db.get_acquisitions_in_horizon(
        start_time=start_str,
        end_time=end_str,
        workspace_id=workspace_id,
        include_tentative=include_tentative,
    )

    logger.info(
        f"[RepairPlanning] Loaded {len(acquisitions)} acquisitions from horizon "
        f"{horizon_start.isoformat()} to {horizon_end.isoformat()}"
    )

    # Apply scope filters
    filtered_acquisitions = acquisitions
    if repair_scope == RepairScope.SATELLITE_SUBSET and satellite_subset:
        filtered_acquisitions = [
            a for a in acquisitions if a.satellite_id in satellite_subset
        ]
    elif repair_scope == RepairScope.TARGET_SUBSET and target_subset:
        filtered_acquisitions = [
            a for a in acquisitions if a.target_id in target_subset
        ]

    # Partition into fixed (hard-locked) and flex (unlocked) sets
    total_score = 0.0

    for acq in filtered_acquisitions:
        # Parse times
        try:
            start_dt = datetime.fromisoformat(acq.start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(acq.end_time.replace("Z", "+00:00"))
            # Remove timezone for consistency
            if start_dt.tzinfo is not None:
                start_dt = start_dt.replace(tzinfo=None)
            if end_dt.tzinfo is not None:
                end_dt = end_dt.replace(tzinfo=None)
        except ValueError:
            logger.warning(f"Failed to parse times for acquisition {acq.id}")
            continue

        # Get value: prefer quality_score, fall back to value field
        value = acq.quality_score or getattr(acq, "value", None) or 1.0
        total_score += value

        # Determine if fixed or flex based on lock level and policy
        is_hard_locked = acq.lock_level == "hard"
        is_executing = acq.state in ("executing", "locked")

        # Hard locks and executing acquisitions are always fixed
        if is_hard_locked or is_executing:
            interval = BlockedInterval(
                acquisition_id=acq.id,
                satellite_id=acq.satellite_id,
                target_id=acq.target_id,
                start_time=start_dt,
                end_time=end_dt,
                roll_angle_deg=acq.roll_angle_deg,
                pitch_angle_deg=acq.pitch_angle_deg or 0.0,
                state=acq.state,
                lock_level=acq.lock_level,
            )
            context.fixed_set.append(interval)
        else:
            # Non-hard-locked items go to flex set
            flex = FlexibleAcquisition(
                acquisition_id=acq.id,
                satellite_id=acq.satellite_id,
                target_id=acq.target_id,
                original_start=start_dt,
                original_end=end_dt,
                roll_angle_deg=acq.roll_angle_deg,
                pitch_angle_deg=acq.pitch_angle_deg or 0.0,
                value=value,
                lock_level=acq.lock_level,
            )
            context.flex_set.append(flex)

    context.original_acquisition_count = len(filtered_acquisitions)
    context.original_score = total_score

    logger.info(
        f"[RepairPlanning] Partitioned: {len(context.fixed_set)} fixed (immutable), "
        f"{len(context.flex_set)} flex (modifiable)"
    )

    return context


def execute_repair_planning(
    repair_context: RepairPlanningContext,
    opportunities: List[Dict[str, Any]],
    max_changes: int = 100,
    objective: RepairObjective = RepairObjective.MAXIMIZE_SCORE,
    slew_config: Optional[SlewConfig] = None,
    target_priorities: Optional[Dict[str, int]] = None,
) -> Tuple[List[Dict[str, Any]], RepairDiff, Dict[str, Any]]:
    """
    Execute repair planning: decide what to keep/drop/add/move.

    Stage B & C of repair:
    - Decide what to do with flex_set based on policy and max_changes
    - Fill gaps with new opportunities using existing planner logic

    Args:
        repair_context: RepairPlanningContext with fixed/flex sets
        opportunities: Available opportunities to fill gaps
        max_changes: Maximum number of changes allowed
        objective: Optimization objective
        slew_config: Slew configuration for feasibility checks
        target_priorities: Optional map of target_name → priority (1=highest, 5=lowest)

    Returns:
        Tuple of (proposed_schedule, repair_diff, metrics)
    """
    if slew_config is None:
        slew_config = SlewConfig()

    # Track changes for diff
    kept_ids: List[str] = []
    dropped_ids: List[str] = []
    added_ids: List[str] = []
    moved_items: List[MovedAcquisitionInfo] = []
    drop_reasons: List[Dict[str, str]] = []
    move_reasons: List[Dict[str, str]] = []
    hard_lock_warnings: List[str] = []

    # All hard-locked items are kept by definition
    for interval in repair_context.fixed_set:
        kept_ids.append(interval.acquisition_id)

    # Stage B: Decide what to do with flex set
    changes_made = 0
    flex_to_keep: List[FlexibleAcquisition] = []
    flex_to_drop: List[FlexibleAcquisition] = []

    # Sort flex items by value (highest first for MAXIMIZE_SCORE)
    sorted_flex = sorted(
        repair_context.flex_set,
        key=lambda f: f.value,
        reverse=(objective != RepairObjective.MINIMIZE_CHANGES),
    )

    # Build blocked intervals from fixed set for conflict checking
    fixed_blocked = IncrementalPlanningContext(
        mode=PlanningMode.INCREMENTAL,
        blocked_intervals={},
    )
    for interval in repair_context.fixed_set:
        if interval.satellite_id not in fixed_blocked.blocked_intervals:
            fixed_blocked.blocked_intervals[interval.satellite_id] = []
        fixed_blocked.blocked_intervals[interval.satellite_id].append(interval)

    # Check each flex item for conflicts with fixed set
    for flex in sorted_flex:
        # Check if this flex item conflicts with any fixed item
        is_blocked, blocking = fixed_blocked.is_time_blocked(
            flex.satellite_id,
            flex.original_start,
            flex.original_end,
        )

        if is_blocked and blocking:
            # Flex item conflicts with a hard lock - must drop
            flex.action = "drop"
            flex_to_drop.append(flex)
            dropped_ids.append(flex.acquisition_id)
            drop_reasons.append(
                {
                    "id": flex.acquisition_id,
                    "reason": f"Conflicts with hard-locked acquisition {blocking.acquisition_id}",
                }
            )
            # Add warning about hard lock conflict
            hard_lock_warnings.append(
                f"Cannot resolve conflict: acquisition {flex.acquisition_id} ({flex.target_id}) "
                f"conflicts with hard-locked {blocking.acquisition_id} ({blocking.target_id}). "
                f"The soft-locked acquisition will be dropped."
            )
            changes_made += 1
        elif changes_made >= max_changes:
            # Hit max changes limit - keep remaining items
            flex.action = "keep"
            flex_to_keep.append(flex)
            kept_ids.append(flex.acquisition_id)
        else:
            # Keep this item (may be dropped later if better opportunities exist)
            flex.action = "keep"
            flex_to_keep.append(flex)
            kept_ids.append(flex.acquisition_id)

    # Build complete blocked intervals (fixed + kept flex)
    all_blocked = IncrementalPlanningContext(
        mode=PlanningMode.INCREMENTAL,
        blocked_intervals=repair_context.get_all_blocked_intervals(),
    )

    # Stage C: Fill gaps with new opportunities
    # Filter opportunities against the current blocked set
    feasible_opps, rejected_opps = filter_opportunities_incremental(
        opportunities=opportunities,
        context=all_blocked,
        slew_config=slew_config,
    )

    # If objective is MAXIMIZE_SCORE and we have room for changes,
    # consider replacing low-value flex items with high-value opportunities
    if objective == RepairObjective.MAXIMIZE_SCORE and changes_made < max_changes:
        # Sort opportunities by value (highest first)
        sorted_opps = sorted(
            feasible_opps,
            key=lambda o: o.get("value", 1.0),
            reverse=True,
        )

        # Sort kept flex by value (lowest first) for potential replacement
        sorted_kept_flex = sorted(flex_to_keep, key=lambda f: f.value)

        # Try to replace low-value flex with high-value opportunities
        # IMPORTANT: Only same-target replacement is allowed (quality upgrade).
        # Cross-target replacement would drop existing coverage, violating user intent.
        for opp in sorted_opps:
            if changes_made >= max_changes:
                break

            opp_value = opp.get("value", 1.0)
            opp_sat_id = opp.get("satellite_id", "")
            opp_target = opp.get("target_id", "")

            # Find lowest-value flex item on same satellite AND same target
            for flex in sorted_kept_flex:
                if flex.action == "drop":
                    continue
                if flex.satellite_id != opp_sat_id:
                    continue
                if flex.target_id != opp_target:
                    continue  # Only same-target replacement allowed
                if flex.value >= opp_value:
                    continue  # No value improvement

                # Check if opp would fit if we drop this flex
                test_blocked = IncrementalPlanningContext(
                    mode=PlanningMode.INCREMENTAL,
                    blocked_intervals={},
                )
                # Copy all blocked except this flex
                for sat_id, intervals in all_blocked.blocked_intervals.items():
                    test_blocked.blocked_intervals[sat_id] = [
                        i for i in intervals if i.acquisition_id != flex.acquisition_id
                    ]

                try:
                    opp_start = datetime.fromisoformat(
                        opp.get("start_time", "").replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    opp_end = datetime.fromisoformat(
                        opp.get("end_time", "").replace("Z", "+00:00")
                    ).replace(tzinfo=None)

                    is_feasible, _ = check_adjacency_feasibility(
                        context=test_blocked,
                        satellite_id=opp_sat_id,
                        candidate_start=opp_start,
                        candidate_end=opp_end,
                        candidate_roll_deg=opp.get("roll_angle_deg", 0.0),
                        candidate_pitch_deg=opp.get("pitch_angle_deg", 0.0),
                        slew_config=slew_config,
                    )

                    if is_feasible:
                        # Replace flex with better opportunity for same target
                        flex.action = "drop"
                        if flex.acquisition_id in kept_ids:
                            kept_ids.remove(flex.acquisition_id)
                        dropped_ids.append(flex.acquisition_id)
                        drop_reasons.append(
                            {
                                "id": flex.acquisition_id,
                                "reason": f"Replaced by higher-value opportunity (value: {opp_value:.2f} vs {flex.value:.2f})",
                            }
                        )
                        added_ids.append(opp.get("id", opp.get("opportunity_id", "")))
                        changes_made += 1
                        break
                except (ValueError, KeyError):
                    continue

    # Stage D: Fill remaining gaps with feasible opportunities not yet added
    # This handles the case where schedule is empty (nothing to replace) or
    # there are more feasible opportunities than flex items to replace.
    #
    # Per-target dedup: only add the best opportunity per target that doesn't
    # already have an acquisition in the schedule (fixed + kept flex).
    already_added = set(added_ids)

    # Build set of targets already covered by the current schedule
    targets_covered: set[str] = set()
    for interval in repair_context.fixed_set:
        targets_covered.add(interval.target_id)
    for flex in repair_context.flex_set:
        if flex.action == "keep":
            targets_covered.add(flex.target_id)
    # Also track targets added during Stage C (replacement)
    for opp_id in added_ids:
        for opp in opportunities:
            if opp.get("id", opp.get("opportunity_id", "")) == opp_id:
                targets_covered.add(opp.get("target_id", ""))
                break

    for opp in sorted(feasible_opps, key=lambda o: o.get("value", 1.0), reverse=True):
        if changes_made >= max_changes:
            break
        opp_id = opp.get("id", opp.get("opportunity_id", ""))
        if opp_id in already_added:
            continue  # Already added via replacement

        # Per-target dedup: skip if this target already has an acquisition
        opp_target = opp.get("target_id", "")
        if opp_target and opp_target in targets_covered:
            continue

        # Verify this opportunity doesn't conflict with anything already scheduled
        # (fixed items + kept flex + already-added opportunities)
        try:
            opp_start = datetime.fromisoformat(
                opp.get("start_time", "").replace("Z", "+00:00")
            ).replace(tzinfo=None)
            opp_end = datetime.fromisoformat(
                opp.get("end_time", "").replace("Z", "+00:00")
            ).replace(tzinfo=None)
            opp_sat = opp.get("satellite_id", "")

            is_blocked, _ = all_blocked.is_time_blocked(opp_sat, opp_start, opp_end)
            if is_blocked:
                continue

            is_feasible, _ = check_adjacency_feasibility(
                context=all_blocked,
                satellite_id=opp_sat,
                candidate_start=opp_start,
                candidate_end=opp_end,
                candidate_roll_deg=opp.get("roll_angle_deg", 0.0),
                candidate_pitch_deg=opp.get("pitch_angle_deg", 0.0),
                slew_config=slew_config,
            )
            if not is_feasible:
                continue

            added_ids.append(opp_id)
            already_added.add(opp_id)
            changes_made += 1
            targets_covered.add(opp_target)

            # Also add to blocked intervals so subsequent opportunities check against it
            new_interval = BlockedInterval(
                acquisition_id=opp_id,
                satellite_id=opp_sat,
                target_id=opp.get("target_id", ""),
                start_time=opp_start,
                end_time=opp_end,
                roll_angle_deg=opp.get("roll_angle_deg", 0.0),
                pitch_angle_deg=opp.get("pitch_angle_deg", 0.0),
            )
            if opp_sat not in all_blocked.blocked_intervals:
                all_blocked.blocked_intervals[opp_sat] = []
            all_blocked.blocked_intervals[opp_sat].append(new_interval)
            all_blocked.blocked_intervals[opp_sat].sort(key=lambda x: x.start_time)
        except (ValueError, KeyError):
            continue

    # Stage E: Coverage improvement — cross-target swaps for uncovered targets.
    # When a target has opportunities but can't fit around kept acquisitions,
    # try dropping a kept flex item on the same satellite IF the dropped target
    # can be re-covered on a different satellite.  Net result: +1 coverage.
    all_request_targets = set(
        opp.get("target_id", "") for opp in opportunities if opp.get("target_id")
    )
    uncovered_targets = all_request_targets - targets_covered

    if uncovered_targets and changes_made < max_changes:
        logger.info(
            f"[RepairPlanning] Stage E: {len(uncovered_targets)} uncovered target(s), "
            f"attempting cross-target coverage swaps"
        )

        for uncovered_target in sorted(uncovered_targets):
            if changes_made >= max_changes:
                break

            # All opportunities for this uncovered target, best first
            target_opps = sorted(
                [o for o in opportunities if o.get("target_id") == uncovered_target],
                key=lambda o: o.get("value", 1.0),
                reverse=True,
            )

            swap_done = False
            for opp in target_opps:
                if swap_done or changes_made >= max_changes:
                    break

                opp_id = opp.get("id", opp.get("opportunity_id", ""))
                if opp_id in already_added:
                    continue

                try:
                    opp_start = datetime.fromisoformat(
                        opp.get("start_time", "").replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    opp_end = datetime.fromisoformat(
                        opp.get("end_time", "").replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    opp_sat = opp.get("satellite_id", "")
                except (ValueError, KeyError):
                    continue

                # Flex items on the same satellite, lowest value first
                same_sat_flex = sorted(
                    [
                        f
                        for f in flex_to_keep
                        if f.action == "keep" and f.satellite_id == opp_sat
                    ],
                    key=lambda f: f.value,
                )

                for flex_candidate in same_sat_flex:
                    if changes_made >= max_changes:
                        break

                    # Build test context without this flex item
                    test_blocked = IncrementalPlanningContext(
                        mode=PlanningMode.INCREMENTAL,
                        blocked_intervals={},
                    )
                    for sat_id, intervals in all_blocked.blocked_intervals.items():
                        test_blocked.blocked_intervals[sat_id] = [
                            i
                            for i in intervals
                            if i.acquisition_id != flex_candidate.acquisition_id
                        ]

                    # Check if uncovered target's opportunity fits without the flex item
                    is_feasible, _ = check_adjacency_feasibility(
                        context=test_blocked,
                        satellite_id=opp_sat,
                        candidate_start=opp_start,
                        candidate_end=opp_end,
                        candidate_roll_deg=opp.get("roll_angle_deg", 0.0),
                        candidate_pitch_deg=opp.get("pitch_angle_deg", 0.0),
                        slew_config=slew_config,
                    )
                    if not is_feasible:
                        continue

                    # Add new opp to test context before checking alt coverage
                    new_bi = BlockedInterval(
                        acquisition_id=opp_id,
                        satellite_id=opp_sat,
                        target_id=uncovered_target,
                        start_time=opp_start,
                        end_time=opp_end,
                        roll_angle_deg=opp.get("roll_angle_deg", 0.0),
                        pitch_angle_deg=opp.get("pitch_angle_deg", 0.0),
                    )
                    if opp_sat not in test_blocked.blocked_intervals:
                        test_blocked.blocked_intervals[opp_sat] = []
                    test_blocked.blocked_intervals[opp_sat].append(new_bi)
                    test_blocked.blocked_intervals[opp_sat].sort(
                        key=lambda x: x.start_time
                    )

                    # Can the dropped target be re-covered on a DIFFERENT satellite?
                    dropped_target = flex_candidate.target_id
                    alt_opps = sorted(
                        [
                            o
                            for o in opportunities
                            if o.get("target_id") == dropped_target
                            and o.get("satellite_id") != opp_sat
                            and o.get("id", o.get("opportunity_id", ""))
                            not in already_added
                        ],
                        key=lambda o: o.get("value", 1.0),
                        reverse=True,
                    )

                    alt_opp_match = None
                    for ao in alt_opps:
                        try:
                            ao_start = datetime.fromisoformat(
                                ao.get("start_time", "").replace("Z", "+00:00")
                            ).replace(tzinfo=None)
                            ao_end = datetime.fromisoformat(
                                ao.get("end_time", "").replace("Z", "+00:00")
                            ).replace(tzinfo=None)
                            ao_sat = ao.get("satellite_id", "")

                            ao_feasible, _ = check_adjacency_feasibility(
                                context=test_blocked,
                                satellite_id=ao_sat,
                                candidate_start=ao_start,
                                candidate_end=ao_end,
                                candidate_roll_deg=ao.get("roll_angle_deg", 0.0),
                                candidate_pitch_deg=ao.get("pitch_angle_deg", 0.0),
                                slew_config=slew_config,
                            )
                            if ao_feasible:
                                alt_opp_match = ao
                                break
                        except (ValueError, KeyError):
                            continue

                    if alt_opp_match is None:
                        logger.debug(
                            f"[RepairPlanning] Stage E: Cannot swap {dropped_target} "
                            f"for {uncovered_target} on {opp_sat} — no re-coverage "
                            f"available for {dropped_target}"
                        )
                        continue

                    # ── Execute the coverage swap ──
                    # 1. Drop the flex item
                    flex_candidate.action = "drop"
                    if flex_candidate.acquisition_id in kept_ids:
                        kept_ids.remove(flex_candidate.acquisition_id)
                    dropped_ids.append(flex_candidate.acquisition_id)
                    drop_reasons.append(
                        {
                            "id": flex_candidate.acquisition_id,
                            "reason": (
                                f"Swapped to improve coverage: "
                                f"re-covered {dropped_target} on another satellite "
                                f"to add uncovered target {uncovered_target}"
                            ),
                        }
                    )
                    changes_made += 1

                    # 2. Add uncovered target's opportunity
                    added_ids.append(opp_id)
                    already_added.add(opp_id)
                    targets_covered.add(uncovered_target)
                    changes_made += 1

                    # 3. Add alternative coverage for the dropped target
                    alt_opp_id = alt_opp_match.get(
                        "id", alt_opp_match.get("opportunity_id", "")
                    )
                    added_ids.append(alt_opp_id)
                    already_added.add(alt_opp_id)
                    # dropped_target stays in targets_covered
                    changes_made += 1

                    # Update blocked intervals to reflect the swap
                    all_blocked.blocked_intervals = {
                        sid: list(ivs)
                        for sid, ivs in test_blocked.blocked_intervals.items()
                    }
                    # Add alt opportunity to blocked
                    ao_sat = alt_opp_match.get("satellite_id", "")
                    ao_start = datetime.fromisoformat(
                        alt_opp_match.get("start_time", "").replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    ao_end = datetime.fromisoformat(
                        alt_opp_match.get("end_time", "").replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    alt_bi = BlockedInterval(
                        acquisition_id=alt_opp_id,
                        satellite_id=ao_sat,
                        target_id=dropped_target,
                        start_time=ao_start,
                        end_time=ao_end,
                        roll_angle_deg=alt_opp_match.get("roll_angle_deg", 0.0),
                        pitch_angle_deg=alt_opp_match.get("pitch_angle_deg", 0.0),
                    )
                    if ao_sat not in all_blocked.blocked_intervals:
                        all_blocked.blocked_intervals[ao_sat] = []
                    all_blocked.blocked_intervals[ao_sat].append(alt_bi)
                    all_blocked.blocked_intervals[ao_sat].sort(
                        key=lambda x: x.start_time
                    )

                    logger.info(
                        f"[RepairPlanning] Stage E coverage swap: "
                        f"dropped {dropped_target} on {opp_sat}, "
                        f"added {uncovered_target} on {opp_sat}, "
                        f"re-covered {dropped_target} on {ao_sat}"
                    )
                    swap_done = True
                    break

        remaining_uncovered = all_request_targets - targets_covered
        if remaining_uncovered:
            logger.info(
                f"[RepairPlanning] Stage E complete. Still uncovered: "
                f"{sorted(remaining_uncovered)}"
            )
        else:
            logger.info("[RepairPlanning] Stage E: All targets now covered")

    # Stage F: Priority-driven eviction — when an uncovered target has HIGHER
    # priority than a covered flex item, drop the lower-priority item to make
    # room, even if the dropped target cannot be re-covered elsewhere.
    # This trades coverage count for schedule value (high-priority coverage).
    remaining_uncovered = all_request_targets - targets_covered
    if remaining_uncovered and target_priorities and changes_made < max_changes:
        logger.info(
            f"[RepairPlanning] Stage F: {len(remaining_uncovered)} uncovered target(s), "
            f"attempting priority-driven eviction"
        )

        # Sort uncovered targets by priority (highest first = lowest number)
        uncovered_by_priority = sorted(
            remaining_uncovered,
            key=lambda t: target_priorities.get(t, 5),
        )

        for uncovered_target in uncovered_by_priority:
            if changes_made >= max_changes:
                break

            uncovered_priority = target_priorities.get(uncovered_target, 5)

            # Best opportunities for this uncovered target
            target_opps = sorted(
                [o for o in opportunities if o.get("target_id") == uncovered_target],
                key=lambda o: o.get("value", 1.0),
                reverse=True,
            )

            eviction_done = False
            for opp in target_opps:
                if eviction_done or changes_made >= max_changes:
                    break

                opp_id = opp.get("id", opp.get("opportunity_id", ""))
                if opp_id in already_added:
                    continue

                try:
                    opp_start = datetime.fromisoformat(
                        opp.get("start_time", "").replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    opp_end = datetime.fromisoformat(
                        opp.get("end_time", "").replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    opp_sat = opp.get("satellite_id", "")
                except (ValueError, KeyError):
                    continue

                # Find flex items on the same satellite with LOWER priority (higher number)
                same_sat_flex = sorted(
                    [
                        f
                        for f in flex_to_keep
                        if f.action == "keep" and f.satellite_id == opp_sat
                    ],
                    key=lambda f: -(target_priorities.get(f.target_id, 5)),
                )

                for flex_candidate in same_sat_flex:
                    if changes_made >= max_changes:
                        break

                    candidate_priority = target_priorities.get(
                        flex_candidate.target_id, 5
                    )
                    # Only evict if uncovered target has strictly higher priority
                    if uncovered_priority >= candidate_priority:
                        continue

                    # Build test context without this flex item
                    test_blocked = IncrementalPlanningContext(
                        mode=PlanningMode.INCREMENTAL,
                        blocked_intervals={},
                    )
                    for sat_id, intervals in all_blocked.blocked_intervals.items():
                        test_blocked.blocked_intervals[sat_id] = [
                            i
                            for i in intervals
                            if i.acquisition_id != flex_candidate.acquisition_id
                        ]

                    # Check if uncovered target's opportunity fits without the flex item
                    is_feasible, _ = check_adjacency_feasibility(
                        context=test_blocked,
                        satellite_id=opp_sat,
                        candidate_start=opp_start,
                        candidate_end=opp_end,
                        candidate_roll_deg=opp.get("roll_angle_deg", 0.0),
                        candidate_pitch_deg=opp.get("pitch_angle_deg", 0.0),
                        slew_config=slew_config,
                    )
                    if not is_feasible:
                        continue

                    # ── Execute priority eviction ──
                    dropped_target = flex_candidate.target_id

                    # 1. Drop the lower-priority flex item
                    flex_candidate.action = "drop"
                    if flex_candidate.acquisition_id in kept_ids:
                        kept_ids.remove(flex_candidate.acquisition_id)
                    dropped_ids.append(flex_candidate.acquisition_id)
                    drop_reasons.append(
                        {
                            "id": flex_candidate.acquisition_id,
                            "reason": (
                                f"Priority eviction: dropped {dropped_target} (priority {candidate_priority}) "
                                f"to schedule higher-priority {uncovered_target} (priority {uncovered_priority})"
                            ),
                        }
                    )
                    targets_covered.discard(dropped_target)
                    changes_made += 1

                    # 2. Add the higher-priority uncovered target's opportunity
                    added_ids.append(opp_id)
                    already_added.add(opp_id)
                    targets_covered.add(uncovered_target)
                    changes_made += 1

                    # Update blocked intervals
                    all_blocked.blocked_intervals = {
                        sid: list(ivs)
                        for sid, ivs in test_blocked.blocked_intervals.items()
                    }
                    new_bi = BlockedInterval(
                        acquisition_id=opp_id,
                        satellite_id=opp_sat,
                        target_id=uncovered_target,
                        start_time=opp_start,
                        end_time=opp_end,
                        roll_angle_deg=opp.get("roll_angle_deg", 0.0),
                        pitch_angle_deg=opp.get("pitch_angle_deg", 0.0),
                    )
                    if opp_sat not in all_blocked.blocked_intervals:
                        all_blocked.blocked_intervals[opp_sat] = []
                    all_blocked.blocked_intervals[opp_sat].append(new_bi)
                    all_blocked.blocked_intervals[opp_sat].sort(
                        key=lambda x: x.start_time
                    )

                    logger.info(
                        f"[RepairPlanning] Stage F priority eviction: "
                        f"dropped {dropped_target} (P{candidate_priority}) on {opp_sat}, "
                        f"added {uncovered_target} (P{uncovered_priority}) on {opp_sat}"
                    )
                    eviction_done = True
                    break

        final_uncovered = all_request_targets - targets_covered
        if final_uncovered:
            logger.info(
                f"[RepairPlanning] Stage F complete. Still uncovered: "
                f"{sorted(final_uncovered)}"
            )
        else:
            logger.info("[RepairPlanning] Stage F: All targets now covered")

    # Build final proposed schedule
    proposed_schedule: List[Dict[str, Any]] = []

    # Add all fixed items
    for interval in repair_context.fixed_set:
        proposed_schedule.append(
            {
                "acquisition_id": interval.acquisition_id,
                "satellite_id": interval.satellite_id,
                "target_id": interval.target_id,
                "start_time": interval.start_time.isoformat() + "Z",
                "end_time": interval.end_time.isoformat() + "Z",
                "roll_angle_deg": interval.roll_angle_deg,
                "pitch_angle_deg": interval.pitch_angle_deg,
                "value": getattr(interval, "value", 1.0) or 1.0,
                "is_fixed": True,
                "action": "kept",
            }
        )

    # Add kept flex items
    for flex in repair_context.flex_set:
        if flex.action == "keep":
            proposed_schedule.append(
                {
                    "acquisition_id": flex.acquisition_id,
                    "satellite_id": flex.satellite_id,
                    "target_id": flex.target_id,
                    "start_time": flex.original_start.isoformat() + "Z",
                    "end_time": flex.original_end.isoformat() + "Z",
                    "roll_angle_deg": flex.roll_angle_deg,
                    "pitch_angle_deg": flex.pitch_angle_deg,
                    "value": flex.value or 1.0,
                    "is_fixed": False,
                    "action": "kept",
                }
            )

    # Add new opportunities (that don't conflict with kept items)
    for opp_id in added_ids:
        # Find the opportunity
        for opp in opportunities:
            if opp.get("id", opp.get("opportunity_id", "")) == opp_id:
                proposed_schedule.append(
                    {
                        "opportunity_id": opp_id,
                        "satellite_id": opp.get("satellite_id", ""),
                        "target_id": opp.get("target_id", ""),
                        "start_time": opp.get("start_time", ""),
                        "end_time": opp.get("end_time", ""),
                        "roll_angle_deg": opp.get("roll_angle_deg", 0.0),
                        "pitch_angle_deg": opp.get("pitch_angle_deg", 0.0),
                        "is_fixed": False,
                        "action": "added",
                        "value": opp.get("value", 1.0),
                    }
                )
                break

    # Sort by start time
    proposed_schedule.sort(key=lambda x: x.get("start_time", ""))

    # Calculate metrics
    total_proposed = len(proposed_schedule)
    total_original = repair_context.original_acquisition_count
    percent_changed = (
        (changes_made / total_original * 100) if total_original > 0 else 0.0
    )

    # PR-OPS-REPAIR-REPORT-01: Build structured change log
    # Derive reason codes from existing drop_reasons / move_reasons
    def _derive_reason_code(reason_text: str) -> str:
        """Derive a RepairReasonCode from free-text reason."""
        reason_lower = reason_text.lower()
        if "hard-lock" in reason_lower or "hard_lock" in reason_lower:
            return RepairReasonCode.HARD_LOCK_CONSTRAINT.value
        if "higher-value" in reason_lower or "replaced by" in reason_lower:
            return RepairReasonCode.PRIORITY_UPGRADE.value
        if "quality" in reason_lower or "score" in reason_lower:
            return RepairReasonCode.QUALITY_SCORE_UPGRADE.value
        if "coverage" in reason_lower or "uncovered" in reason_lower:
            return RepairReasonCode.CONFLICT_RESOLUTION.value
        if "slew" in reason_lower or "feasib" in reason_lower:
            return RepairReasonCode.SLEW_CHAIN_FEASIBILITY.value
        if "horizon" in reason_lower or "boundary" in reason_lower:
            return RepairReasonCode.HORIZON_LIMIT.value
        if "resource" in reason_lower or "capacity" in reason_lower:
            return RepairReasonCode.RESOURCE_LIMIT.value
        if "conflict" in reason_lower:
            return RepairReasonCode.CONFLICT_RESOLUTION.value
        return RepairReasonCode.CONFLICT_RESOLUTION.value

    # Build lookup for flex items and opportunities by ID
    flex_lookup: Dict[str, FlexibleAcquisition] = {
        f.acquisition_id: f for f in repair_context.flex_set
    }
    fixed_lookup: Dict[str, BlockedInterval] = {
        b.acquisition_id: b for b in repair_context.fixed_set
    }
    opp_lookup: Dict[str, Dict[str, Any]] = {}
    for opp in opportunities:
        oid = opp.get("id", opp.get("opportunity_id", ""))
        if oid:
            opp_lookup[oid] = opp

    # Build drop reason lookup
    drop_reason_lookup: Dict[str, str] = {dr["id"]: dr["reason"] for dr in drop_reasons}

    # Build dropped entries
    dropped_entries = []
    for did in dropped_ids:
        flex_item = flex_lookup.get(did)
        reason_text = drop_reason_lookup.get(did, "Dropped during repair optimization")
        reason_code = _derive_reason_code(reason_text)
        # Check if this was replaced by an added item (same satellite)
        replaced_by_ids = []
        if flex_item:
            for aid in added_ids:
                opp = opp_lookup.get(aid, {})
                if opp.get("satellite_id") == flex_item.satellite_id:
                    replaced_by_ids.append(aid)
        dropped_entries.append(
            DroppedEntry(
                acquisition_id=did,
                satellite_id=flex_item.satellite_id if flex_item else "",
                target_id=flex_item.target_id if flex_item else "",
                start=flex_item.original_start.isoformat() + "Z" if flex_item else "",
                end=flex_item.original_end.isoformat() + "Z" if flex_item else "",
                reason_code=reason_code,
                reason_text=reason_text,
                replaced_by=replaced_by_ids,
            ).model_dump()
        )

    # Build added entries
    added_entries = []
    for aid in added_ids:
        opp = opp_lookup.get(aid, {})
        # Check if this replaces a dropped item (same satellite)
        replaces_ids = []
        opp_sat = opp.get("satellite_id", "")
        for did in dropped_ids:
            flex_item = flex_lookup.get(did)
            if flex_item and flex_item.satellite_id == opp_sat:
                replaces_ids.append(did)
        reason_code = (
            RepairReasonCode.PRIORITY_UPGRADE.value
            if replaces_ids
            else RepairReasonCode.ADDED_NEW.value
        )
        reason_text = (
            f"Replaced lower-value acquisition(s) on {opp_sat}"
            if replaces_ids
            else "Added to fill schedule gap"
        )
        added_entries.append(
            AddedEntry(
                acquisition_id=aid,
                satellite_id=opp_sat,
                target_id=opp.get("target_id", ""),
                start=opp.get("start_time", ""),
                end=opp.get("end_time", ""),
                reason_code=reason_code,
                reason_text=reason_text,
                replaces=replaces_ids,
                value=opp.get("value"),
            ).model_dump()
        )

    # Build moved entries (currently empty since repair doesn't move, but structure is ready)
    moved_entries = []
    for m in moved_items:
        flex_item = flex_lookup.get(m.id)
        move_reason_lookup = {mr["id"]: mr["reason"] for mr in move_reasons}
        reason_text = move_reason_lookup.get(m.id, "Rescheduled to a better time slot")
        reason_code = _derive_reason_code(reason_text)
        moved_entries.append(
            MovedEntry(
                acquisition_id=m.id,
                satellite_id=flex_item.satellite_id if flex_item else "",
                target_id=flex_item.target_id if flex_item else "",
                from_start=m.from_start,
                from_end=m.from_end,
                to_start=m.to_start,
                to_end=m.to_end,
                reason_code=reason_code,
                reason_text=reason_text,
            ).model_dump()
        )

    change_log = {
        "dropped": dropped_entries,
        "added": added_entries,
        "moved": moved_entries,
        "kept_count": len(kept_ids),
    }

    # Build diff
    repair_diff = RepairDiff(
        kept=kept_ids,
        dropped=dropped_ids,
        added=added_ids,
        moved=moved_items,
        reason_summary={
            "dropped": drop_reasons,
            "moved": move_reasons,
        },
        change_score=ChangeScore(
            num_changes=changes_made,
            percent_changed=round(percent_changed, 2),
        ),
        hard_lock_warnings=hard_lock_warnings,
        change_log=change_log,
    )

    metrics = {
        "total_original": total_original,
        "total_proposed": total_proposed,
        "fixed_count": len(repair_context.fixed_set),
        "flex_count": len(repair_context.flex_set),
        "kept_count": len(kept_ids),
        "dropped_count": len(dropped_ids),
        "added_count": len(added_ids),
        "moved_count": len(moved_items),
        "changes_made": changes_made,
        "max_changes": max_changes,
    }

    logger.info(
        f"[RepairPlanning] Repair complete: {len(kept_ids)} kept, "
        f"{len(dropped_ids)} dropped, {len(added_ids)} added, "
        f"{len(moved_items)} moved. Changes: {changes_made}/{max_changes}"
    )

    return proposed_schedule, repair_diff, metrics
