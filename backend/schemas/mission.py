"""Mission request/response schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

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
        default=None, description="Use specific ground station configuration"
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

    @model_validator(mode="after")
    def validate_satellite_input(self) -> "MissionRequest":
        """Ensure either tle or satellites is provided."""
        has_tle = self.tle is not None
        has_satellites = self.satellites is not None and len(self.satellites) > 0

        if not has_tle and not has_satellites:
            raise ValueError("Either 'tle' or 'satellites' must be provided")
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
    data: Optional[Dict[str, Any]] = None
