"""
Auto Mode Selection for Scheduling Pipeline.

Deterministic rules for choosing planning mode based on workspace/schedule state.
The mission planner UI never sees these modes — they are internal system logic.

Rules (PR_SCHED_001):
  - FROM_SCRATCH: workspace has no existing schedule snapshot OR schedule is empty
  - INCREMENTAL:  existing schedule AND new orders/targets added since last apply
  - REPAIR:       existing schedule AND conflicts/violations requiring repair
                   (or when incremental is not feasible)

All decisions are logged with structured context for audit traceability.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from src.mission_planner.quality_scoring import MultiCriteriaWeights

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level store for last planning run diagnostics (DEV_MODE only)
# ---------------------------------------------------------------------------
_last_planning_run: Dict[str, Any] = {}


def get_last_planning_run() -> Dict[str, Any]:
    """Return diagnostics from the last planning run (dev-only)."""
    return dict(_last_planning_run)


def clear_last_planning_run() -> None:
    """Clear last planning run diagnostics."""
    _last_planning_run.clear()


# ---------------------------------------------------------------------------
# Auto-mode selection result
# ---------------------------------------------------------------------------


@dataclass
class ModeSelectionResult:
    """Result of auto-mode selection with full audit context."""

    mode: str  # "from_scratch" | "incremental" | "repair"
    reason: str  # Human-readable reason
    workspace_id: str
    existing_acquisition_count: int = 0
    new_target_count: int = 0
    removed_scheduled_target_count: int = 0
    conflict_count: int = 0
    previous_plan_count: int = 0
    request_payload_hash: str = ""
    # Detailed context
    existing_target_ids: Set[str] = field(default_factory=set)
    new_target_ids: Set[str] = field(default_factory=set)

    def to_log_dict(self) -> Dict[str, Any]:
        """Structured dict for logging."""
        return {
            "chosen_mode": self.mode,
            "reason": self.reason,
            "workspace_id": self.workspace_id,
            "existing_acquisition_count": self.existing_acquisition_count,
            "new_target_count": self.new_target_count,
            "removed_scheduled_target_count": self.removed_scheduled_target_count,
            "conflict_count": self.conflict_count,
            "previous_plan_count": self.previous_plan_count,
            "request_payload_hash": self.request_payload_hash,
        }


def compute_request_hash(payload: Dict[str, Any]) -> str:
    """Compute a deterministic hash of the request payload for audit."""
    # Sort keys for determinism, exclude volatile fields
    stable = {
        k: v
        for k, v in sorted(payload.items())
        if k not in ("horizon_from", "horizon_to")
    }
    raw = json.dumps(stable, sort_keys=True, default=str)
    return f"sha256:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def select_planning_mode(
    workspace_id: str,
    existing_acquisition_count: int,
    existing_target_ids: Optional[Set[str]],
    current_target_ids: Optional[Set[str]],
    scheduled_target_ids: Optional[Set[str]] = None,
    target_priorities: Optional[Dict[str, int]] = None,
    weight_priority: float = 40.0,
    weight_geometry: float = 40.0,
    weight_timing: float = 20.0,
    conflict_count: int = 0,
    previous_plan_count: int = 0,
    request_payload_hash: str = "",
    force_mode: Optional[str] = None,
) -> ModeSelectionResult:
    """
    Deterministic auto-mode selection based on workspace/schedule state.

    Args:
        workspace_id: Active workspace ID
        existing_acquisition_count: Number of acquisitions already in schedule
        existing_target_ids: Target IDs from the previous planned workspace scope
        current_target_ids: Target IDs in current planning request
        scheduled_target_ids: Target IDs backed by live scheduled acquisitions
        conflict_count: Number of detected conflicts in existing schedule
        previous_plan_count: Number of committed plans for this workspace
        request_payload_hash: Hash of request payload for audit
        force_mode: If set, override auto-selection (for backward compat)

    Returns:
        ModeSelectionResult with chosen mode and audit context
    """
    existing_targets = existing_target_ids or set()
    current_targets = current_target_ids or set()
    scheduled_targets = scheduled_target_ids or set()
    new_targets = current_targets - existing_targets
    removed_scheduled_targets = scheduled_targets - current_targets
    priorities = target_priorities or {}

    result = ModeSelectionResult(
        mode="from_scratch",
        reason="",
        workspace_id=workspace_id,
        existing_acquisition_count=existing_acquisition_count,
        new_target_count=len(new_targets),
        removed_scheduled_target_count=len(removed_scheduled_targets),
        conflict_count=conflict_count,
        previous_plan_count=previous_plan_count,
        request_payload_hash=request_payload_hash,
        existing_target_ids=existing_targets,
        new_target_ids=new_targets,
    )

    # Allow explicit override (backward compat)
    if force_mode and force_mode in ("from_scratch", "incremental", "repair"):
        result.mode = force_mode
        result.reason = f"Explicitly requested mode: {force_mode}"
        _log_mode_selection(result)
        return result

    # Rule 1: FROM_SCRATCH — no existing schedule
    if existing_acquisition_count == 0:
        result.mode = "from_scratch"
        result.reason = (
            "No existing schedule found for workspace. "
            "Building new optimized schedule from all opportunities."
        )
        _log_mode_selection(result)
        return result

    if removed_scheduled_targets:
        result.mode = "repair"
        result.reason = (
            f"{len(removed_scheduled_targets)} scheduled target(s) are no longer in scope "
            f"({', '.join(sorted(removed_scheduled_targets)[:5])}). "
            f"Repairing the current schedule so removed work can be dropped safely."
        )
        _log_mode_selection(result)
        return result

    existing_target_priorities = [
        priorities[target_id]
        for target_id in existing_targets
        if target_id in priorities and isinstance(priorities[target_id], int)
    ]
    new_target_priorities = [
        priorities[target_id]
        for target_id in new_targets
        if target_id in priorities and isinstance(priorities[target_id], int)
    ]
    best_existing_priority = (
        min(existing_target_priorities) if existing_target_priorities else None
    )
    best_new_priority = min(new_target_priorities) if new_target_priorities else None
    weights = MultiCriteriaWeights(
        priority=weight_priority,
        geometry=weight_geometry,
        timing=weight_timing,
    )
    priority_gap = (
        (best_existing_priority - best_new_priority)
        if best_existing_priority is not None and best_new_priority is not None
        else 0
    )
    priority_uplift = weights.norm_priority * max(priority_gap, 0) / 4.0

    # Rule 2: New targets added to existing schedule → INCREMENTAL.
    # Escalate to REPAIR when the newly added work is higher priority than the
    # existing scheduled target set *and* the active scoring weights place
    # enough emphasis on priority to justify reshuffling.
    if len(new_targets) > 0:
        if (
            best_new_priority is not None
            and best_existing_priority is not None
            and best_new_priority < best_existing_priority
            and priority_uplift >= 0.25
        ):
            result.mode = "repair"
            result.reason = (
                f"{len(new_targets)} new target(s) detected "
                f"({', '.join(sorted(new_targets)[:5])}) and they include higher-priority work "
                f"(best new P{best_new_priority} vs existing best P{best_existing_priority}, "
                f"priority weight {weights.norm_priority:.0%}). "
                f"Repairing the current schedule to allow weight-aware reshuffling."
            )
            _log_mode_selection(result)
            return result

        result.mode = "incremental"
        result.reason = (
            f"{len(new_targets)} new target(s) detected "
            f"({', '.join(sorted(new_targets)[:5])}). "
            f"Planning incrementally around "
            f"{existing_acquisition_count} existing acquisition(s)."
        )
        _log_mode_selection(result)
        return result

    # Rule 3: REPAIR — existing schedule, no new targets, conflicts present
    if conflict_count > 0:
        result.mode = "repair"
        result.reason = (
            f"Existing schedule has {conflict_count} conflict(s). "
            f"Repairing while preserving {existing_acquisition_count} locked items."
        )
        _log_mode_selection(result)
        return result

    # Rule 4: REPAIR — existing schedule, no new targets, no conflicts
    # (optimize existing schedule: keep locks, adjust unlocked)
    result.mode = "repair"
    result.reason = (
        f"Found {existing_acquisition_count} existing acquisition(s). "
        f"Locked items preserved, unlocked items may be adjusted."
    )
    _log_mode_selection(result)
    return result


def _log_mode_selection(result: ModeSelectionResult) -> None:
    """Log mode selection with structured context."""
    logger.info(
        f"[Auto Mode Selection] mode={result.mode} | "
        f"workspace={result.workspace_id} | "
        f"existing_acq={result.existing_acquisition_count} | "
        f"new_targets={result.new_target_count} | "
        f"removed_scheduled={result.removed_scheduled_target_count} | "
        f"conflicts={result.conflict_count} | "
        f"reason={result.reason}"
    )


# ---------------------------------------------------------------------------
# Audit breadcrumbs — dev-only instrumentation
# ---------------------------------------------------------------------------


@dataclass
class AuditBreadcrumb:
    """Single breadcrumb in the scheduling pipeline audit trail."""

    stage: str  # e.g. "mode_selection", "feasibility", "plan_generation", "apply"
    timestamp: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "timestamp": self.timestamp,
            "data": self.data,
        }


class PipelineAuditTrail:
    """
    Collects breadcrumbs throughout a single scheduling pipeline run.

    Dev-only: records request hash, chosen mode, schedule revision before/after,
    acquisition IDs before/after, and diff counts.
    """

    def __init__(self, run_id: str, workspace_id: str):
        self.run_id = run_id
        self.workspace_id = workspace_id
        self.breadcrumbs: List[AuditBreadcrumb] = []
        self.started_at = datetime.now(timezone.utc).isoformat() + "Z"

    def add(self, stage: str, **data: Any) -> None:
        """Add a breadcrumb to the trail."""
        crumb = AuditBreadcrumb(
            stage=stage,
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            data=data,
        )
        self.breadcrumbs.append(crumb)
        logger.debug(
            f"[Audit Trail] run={self.run_id} stage={stage} "
            f"data={json.dumps(data, default=str)[:200]}"
        )

    def finalize(self) -> Dict[str, Any]:
        """Finalize and return the full audit trail as a dict."""
        trail = {
            "run_id": self.run_id,
            "workspace_id": self.workspace_id,
            "started_at": self.started_at,
            "completed_at": datetime.now(timezone.utc).isoformat() + "Z",
            "breadcrumb_count": len(self.breadcrumbs),
            "breadcrumbs": [b.to_dict() for b in self.breadcrumbs],
        }
        # Store in module-level last-run for dev endpoint
        _last_planning_run.clear()
        _last_planning_run.update(trail)
        return trail


def record_schedule_diff(
    trail: PipelineAuditTrail,
    acq_ids_before: List[str],
    acq_ids_after: List[str],
) -> Dict[str, Any]:
    """Record acquisition ID diff between schedule revisions."""
    before_set = set(acq_ids_before)
    after_set = set(acq_ids_after)
    diff = {
        "kept": sorted(before_set & after_set),
        "added": sorted(after_set - before_set),
        "removed": sorted(before_set - after_set),
        "kept_count": len(before_set & after_set),
        "added_count": len(after_set - before_set),
        "removed_count": len(before_set - after_set),
    }
    trail.add(
        "schedule_diff",
        acq_ids_before_count=len(acq_ids_before),
        acq_ids_after_count=len(acq_ids_after),
        **{k: v for k, v in diff.items() if k.endswith("_count")},
    )
    return diff
