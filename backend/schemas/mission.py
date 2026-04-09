"""Mission request/response schemas."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.time_windows import (
    DailyTimeWindow,
    OFF_NADIR_TIME_REFERENCE,
    get_time_zone,
    parse_hhmm_time,
)

from backend.schemas.tle import TLEData
from backend.schemas.target import TargetData


class SARInputParams(BaseModel):
    """SAR mission parameters aligned with ICEYE tasking concepts."""

    imaging_mode: str = Field(
        default="strip",
        description="SAR imaging mode: spot, strip, scan, or dwell",
    )
    incidence_min_deg: Optional[float] = Field(
        default=None,
        description="Minimum incidence angle in degrees (uses mode default if not specified)",
    )
    incidence_max_deg: Optional[float] = Field(
        default=None,
        description="Maximum incidence angle in degrees (uses mode default if not specified)",
    )
    look_side: str = Field(
        default="ANY",
        description="SAR look side: LEFT, RIGHT, or ANY",
    )
    pass_direction: str = Field(
        default="ANY",
        description="Pass direction filter: ASCENDING, DESCENDING, or ANY",
    )

    @field_validator("imaging_mode")
    @classmethod
    def validate_imaging_mode(cls, v: str) -> str:
        valid_modes = ["spot", "strip", "scan", "dwell"]
        if v.lower() not in valid_modes:
            raise ValueError(f"Invalid SAR mode: {v}. Must be one of {valid_modes}")
        return v.lower()

    @field_validator("look_side")
    @classmethod
    def validate_look_side(cls, v: str) -> str:
        valid_sides = ["LEFT", "RIGHT", "ANY"]
        if v.upper() not in valid_sides:
            raise ValueError(f"Invalid look side: {v}. Must be one of {valid_sides}")
        return v.upper()

    @field_validator("pass_direction")
    @classmethod
    def validate_pass_direction(cls, v: str) -> str:
        valid_dirs = ["ASCENDING", "DESCENDING", "ANY"]
        if v.upper() not in valid_dirs:
            raise ValueError(
                f"Invalid pass direction: {v}. Must be one of {valid_dirs}"
            )
        return v.upper()


class AcquisitionTimeWindowRequest(BaseModel):
    """Recurring daily acquisition time window filter."""

    enabled: bool = Field(
        default=False,
        description="Whether to restrict feasibility to a recurring daily time window",
    )
    start_time: Optional[str] = Field(
        default=None,
        description="Window start in HH:MM local time",
    )
    end_time: Optional[str] = Field(
        default=None,
        description="Window end in HH:MM local time",
    )
    timezone: str = Field(
        default="UTC",
        description="IANA timezone used for daily time-of-day comparison",
    )
    reference: str = Field(
        default=OFF_NADIR_TIME_REFERENCE,
        description="Timestamp reference for time window filtering",
    )

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        parse_hhmm_time(v)
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        get_time_zone(v)
        return v

    @field_validator("reference")
    @classmethod
    def validate_reference(cls, v: str) -> str:
        if v != OFF_NADIR_TIME_REFERENCE:
            raise ValueError(
                f"Unsupported acquisition time window reference: {v}"
            )
        return v

    @model_validator(mode="after")
    def validate_enabled_window(self) -> "AcquisitionTimeWindowRequest":
        if not self.enabled:
            return self

        if not self.start_time or not self.end_time:
            raise ValueError(
                "Acquisition time window start_time and end_time are required when enabled"
            )

        DailyTimeWindow.from_strings(
            start_time=self.start_time,
            end_time=self.end_time,
            timezone_name=self.timezone,
            reference=self.reference,
        )
        return self


RunOrderType = Literal["one_time", "repeats"]
RunOrderRecurrenceType = Literal["daily", "weekly"]
RunOrderWeekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
PlanningDemandType = Literal["one_time", "recurring_instance"]
PlanningDemandFeasibilityStatus = Literal["feasible", "no_opportunity"]


class RunOrderTargetBinding(BaseModel):
    """Lineage metadata for one target inside the run-level order."""

    canonical_target_id: str = Field(..., min_length=1)
    display_target_name: Optional[str] = Field(default=None, min_length=1)
    template_id: Optional[str] = Field(default=None, min_length=1)

    @field_validator("canonical_target_id", "display_target_name", "template_id")
    @classmethod
    def validate_non_empty_strings(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value must not be empty")
        return stripped


class RunOrderRecurrenceRequest(BaseModel):
    """Recurring cadence authored on the single run-level order."""

    recurrence_type: RunOrderRecurrenceType
    interval: int = Field(default=1, ge=1)
    days_of_week: Optional[List[RunOrderWeekday]] = Field(default=None)
    window_start_hhmm: str = Field(..., min_length=1)
    window_end_hhmm: str = Field(..., min_length=1)
    timezone_name: str = Field(default="UTC", min_length=1)
    effective_start_date: str = Field(..., min_length=1)
    effective_end_date: Optional[str] = Field(default=None, min_length=1)

    @field_validator("window_start_hhmm", "window_end_hhmm")
    @classmethod
    def validate_window_time_format(cls, value: str) -> str:
        parse_hhmm_time(value)
        return value

    @field_validator("timezone_name")
    @classmethod
    def validate_recurrence_timezone(cls, value: str) -> str:
        get_time_zone(value)
        return value

    @model_validator(mode="after")
    def validate_weekly_configuration(self) -> "RunOrderRecurrenceRequest":
        if self.recurrence_type == "weekly" and not self.days_of_week:
            raise ValueError(
                "days_of_week is required when recurrence_type is 'weekly'"
            )
        return self


class RunOrderRequest(BaseModel):
    """Single run-level order container sent with feasibility analysis."""

    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    order_type: RunOrderType = Field(default="one_time")
    targets: List[RunOrderTargetBinding] = Field(default_factory=list)
    recurrence: Optional[RunOrderRecurrenceRequest] = Field(default=None)

    @field_validator("id", "name")
    @classmethod
    def validate_run_order_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value must not be empty")
        return stripped

    @model_validator(mode="after")
    def validate_recurrence_for_order_type(self) -> "RunOrderRequest":
        if self.order_type == "repeats" and self.recurrence is None:
            raise ValueError("recurrence is required when order_type is 'repeats'")
        return self


class MissionRequest(BaseModel):
    # Legacy single satellite (optional for backward compatibility)
    tle: Optional[TLEData] = Field(
        default=None,
        description="Single satellite TLE (deprecated - use 'satellites' for constellation)",
    )

    # NEW: Constellation support - multiple satellites
    satellites: Optional[List[TLEData]] = Field(
        default=None, description="List of satellite TLEs for constellation mission"
    )
    workspace_id: Optional[str] = Field(
        default=None,
        description="Optional workspace scope for mission analysis state",
    )
    run_order: Optional[RunOrderRequest] = Field(
        default=None,
        description="Optional single run-level order contract for demand-aware feasibility",
    )

    targets: List[TargetData]
    start_time: str  # ISO format
    end_time: Optional[str] = Field(
        default=None,
        description="Mission end time (ISO format) - takes precedence over duration_hours",
    )
    duration_hours: Optional[float] = Field(
        default=None, description="Deprecated - for backward compatibility only"
    )
    mission_type: str = Field(
        default="imaging", description="Mission type: imaging or communication"
    )
    imaging_type: Optional[str] = Field(
        default="optical",
        description="Imaging sensor type: optical or sar (for imaging missions)",
    )
    sar_mode: Optional[str] = Field(
        default=None,
        description="SAR imaging mode: spotlight, stripmap, or scan (used when imaging_type='sar')",
    )
    elevation_mask: Optional[float] = Field(
        default=None,
        description="Minimum elevation angle in degrees (optional, will use config defaults)",
    )
    max_spacecraft_roll_deg: Optional[float] = Field(
        default=None,
        description="Maximum spacecraft roll angle limit in degrees (satellite agility)",
    )
    max_spacecraft_pitch_deg: Optional[float] = Field(
        default=None,
        description="Maximum spacecraft pitch angle limit in degrees (2D slew capability)",
    )
    sensor_fov_half_angle_deg: Optional[float] = Field(
        default=None,
        description="Sensor FOV half-angle in degrees (camera field of view)",
    )
    ground_station_name: Optional[str] = Field(
        default=None,
        description="Deprecated and ignored; ground stations are not used by mission analysis",
    )
    use_parallel: Optional[bool] = Field(
        default=None,
        description="Enable HPC mode with parallel processing (auto-detect if None)",
    )
    max_workers: Optional[int] = Field(
        default=None, description="Maximum parallel workers (None = auto-detect)"
    )
    use_adaptive: Optional[bool] = Field(
        default=True,
        description="Use adaptive time-stepping algorithm (recommended for performance)",
    )
    # SAR-specific parameters (ICEYE-parity)
    sar: Optional[SARInputParams] = Field(
        default=None,
        description="SAR-specific parameters (only used when imaging_type='sar')",
    )
    acquisition_time_window: Optional[AcquisitionTimeWindowRequest] = Field(
        default=None,
        description=(
            "Optional recurring daily time-of-day window filter applied to "
            "off-nadir time across the planning horizon"
        ),
    )

    @model_validator(mode="after")
    def validate_satellite_input(self) -> "MissionRequest":
        """Ensure either tle or satellites is provided."""
        has_tle = self.tle is not None
        has_satellites = self.satellites is not None and len(self.satellites) > 0

        if not has_tle and not has_satellites:
            raise ValueError("Either 'tle' or 'satellites' must be provided")
        if self.run_order and self.run_order.targets:
            if len(self.run_order.targets) != len(self.targets):
                raise ValueError(
                    "run_order.targets must align 1:1 with request.targets"
                )
        return self

    def get_satellite_list(self) -> List[TLEData]:
        """Get normalized list of satellites (handles both legacy and new format)."""
        if self.satellites and len(self.satellites) > 0:
            return self.satellites
        elif self.tle:
            return [self.tle]
        return []

    def is_constellation(self) -> bool:
        """Check if this is a multi-satellite constellation mission."""
        return len(self.get_satellite_list()) > 1


class MissionResponse(BaseModel):
    success: bool
    message: str
    data: Optional["MissionAnalyzeResponseData"] = None


class SatelliteInfoResponse(BaseModel):
    """Satellite summary returned by feasibility analysis."""

    id: str
    name: str
    color: Optional[str] = None


class RunOrderRecurrenceResponse(BaseModel):
    """Normalized recurring cadence returned with mission results."""

    recurrence_type: RunOrderRecurrenceType
    interval: int = Field(default=1, ge=1)
    days_of_week: Optional[List[RunOrderWeekday]] = None
    window_start_hhmm: str
    window_end_hhmm: str
    timezone_name: str
    effective_start_date: str
    effective_end_date: Optional[str] = None


class RunOrderSummary(BaseModel):
    """Single run-level order summary attached to mission results."""

    id: str
    name: str
    order_type: RunOrderType
    target_count: int = Field(ge=0)
    planning_demand_count: int = Field(ge=0)
    recurrence: Optional[RunOrderRecurrenceResponse] = None


class PlanningDemandSummary(BaseModel):
    """Demand-aware feasibility summary for one actionable planning unit."""

    run_order_id: str
    demand_id: str
    canonical_target_id: str
    display_target_name: str
    demand_type: PlanningDemandType
    template_id: Optional[str] = None
    instance_key: Optional[str] = None
    requested_window_start: Optional[str] = None
    requested_window_end: Optional[str] = None
    local_date: Optional[str] = None
    priority: int = Field(ge=1, le=5)
    feasibility_status: PlanningDemandFeasibilityStatus
    has_feasible_pass: bool
    matching_pass_count: int = Field(ge=0)
    matching_pass_indexes: List[int] = Field(default_factory=list)
    first_pass_start: Optional[str] = None
    last_pass_end: Optional[str] = None
    best_pass_index: Optional[int] = None
    best_pass_start: Optional[str] = None
    best_pass_end: Optional[str] = None
    best_max_elevation: Optional[float] = None


class PlanningDemandAggregateSummary(BaseModel):
    """Roll-up counts for the demand-aware feasibility response."""

    run_order_id: str
    total_demands: int = Field(ge=0)
    feasible_demands: int = Field(ge=0)
    infeasible_demands: int = Field(ge=0)
    one_time_demands: int = Field(ge=0)
    recurring_instance_demands: int = Field(ge=0)


class MissionDataResponse(BaseModel):
    """Typed mission analysis payload with additive demand-aware fields."""

    model_config = ConfigDict(extra="allow")

    satellite_name: Optional[str] = None
    satellites: List[SatelliteInfoResponse] = Field(default_factory=list)
    is_constellation: bool = False
    mission_type: str
    imaging_type: Optional[str] = None
    start_time: str
    end_time: str
    elevation_mask: float
    sensor_fov_half_angle_deg: Optional[float] = None
    max_spacecraft_roll_deg: Optional[float] = None
    max_spacecraft_pitch_deg: Optional[float] = None
    satellite_agility: Optional[float] = None
    acquisition_time_window: Optional[AcquisitionTimeWindowRequest] = None
    total_passes: int = Field(ge=0)
    targets: List[TargetData]
    passes: List[Dict[str, Any]] = Field(default_factory=list)
    coverage_percentage: Optional[float] = None
    pass_statistics: Optional[Dict[str, int]] = None
    sar: Optional[Dict[str, Any]] = None
    run_order: Optional[RunOrderSummary] = None
    planning_demands: List[PlanningDemandSummary] = Field(default_factory=list)
    planning_demand_summary: Optional[PlanningDemandAggregateSummary] = None


class MissionAnalyzeResponseData(BaseModel):
    """Nested response payload for mission feasibility analysis."""

    mission_data: MissionDataResponse
    czml_data: List[Dict[str, Any]]


MissionResponse.model_rebuild()
