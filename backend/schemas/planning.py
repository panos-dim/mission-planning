"""Mission planning/scheduling schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PlanningRequest(BaseModel):
    """Request for mission planning/scheduling."""

    # Planning mode (NEW for persistence)
    mode: str = Field(
        default="from_scratch",
        description="Planning mode: from_scratch (ignore history) | incremental (respect committed)",
    )
    workspace_id: Optional[str] = Field(
        default=None,
        description="Workspace ID for incremental mode (loads committed acquisitions)",
    )

    # Agility parameters
    imaging_time_s: float = Field(default=5.0, description="Time on target (tau)")
    max_roll_rate_dps: float = Field(default=1.0, description="Max roll rate (deg/s)")
    max_roll_accel_dps2: float = Field(
        default=10000.0,
        description="Max roll acceleration (deg/s²) - high value simulates instant acceleration",
    )
    # NOTE: max_pitch_deg removed - pitch limit comes from mission analysis (max_spacecraft_pitch_deg)
    max_pitch_rate_dps: float = Field(default=1.0, description="Max pitch rate (deg/s)")
    max_pitch_accel_dps2: float = Field(
        default=10000.0, description="Max pitch acceleration (deg/s²)"
    )

    # Algorithm selection
    algorithms: List[str] = Field(
        default=["first_fit"],
        description="Algorithms to run: first_fit, best_fit, roll_pitch_first_fit, roll_pitch_best_fit",
    )

    # Value source
    value_source: str = Field(
        default="uniform",
        description="Value source: uniform | target_priority | custom",
    )
    custom_values: Optional[Dict[str, float]] = Field(
        default=None, description="Custom opportunity_id -> value mapping"
    )

    # Algorithm parameters
    look_window_s: float = Field(
        default=600.0, description="Candidate window for Best-Fit/Value-Density"
    )

    # Quality model for geometry scoring
    quality_model: str = Field(
        default="monotonic", description="Quality model: off | monotonic | band"
    )
    ideal_incidence_deg: float = Field(
        default=35.0, description="Ideal off-nadir angle for SAR Band model (degrees)"
    )
    band_width_deg: float = Field(
        default=7.5, description="Band width for Band model (degrees)"
    )

    # Multi-criteria weights
    weight_priority: float = Field(
        default=40.0, ge=0.0, description="Weight for target priority"
    )
    weight_geometry: float = Field(
        default=40.0, ge=0.0, description="Weight for imaging geometry quality"
    )
    weight_timing: float = Field(
        default=20.0, ge=0.0, description="Weight for chronological preference"
    )
    weight_preset: Optional[str] = Field(
        default=None,
        description="Use preset: balanced | priority_first | quality_first | urgent | archival",
    )


class PlanningAuditMetadata(BaseModel):
    """Audit metadata for planning responses (instrumentation for persistent scheduling)."""

    plan_input_hash: str = Field(
        description="SHA256 hash of planning inputs for reproducibility"
    )
    run_id: str = Field(description="Unique identifier for this planning run")
    candidate_plan_id: str = Field(
        description="In-memory plan ID (for future persistence)"
    )
    opportunities_considered: List[str] = Field(
        description="List of opportunity IDs that were evaluated"
    )


class PlanningResponse(BaseModel):
    """Response from mission planning."""

    success: bool
    message: str
    results: Optional[Dict[str, Any]] = None
    audit: Optional[PlanningAuditMetadata] = Field(
        default=None, description="Audit metadata for debugging and future persistence"
    )
