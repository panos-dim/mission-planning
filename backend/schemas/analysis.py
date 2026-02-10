"""STK-like analysis and pass enrichment schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.schemas.tle import TLEData
from backend.schemas.target import TargetData


class PassGeometryResponse(BaseModel):
    """Geometry data at a specific point in a pass."""

    elevation_deg: float = Field(description="Elevation angle from target to satellite")
    azimuth_deg: float = Field(description="Azimuth angle from target to satellite")
    range_km: float = Field(description="Slant range from target to satellite")
    incidence_angle_deg: float = Field(description="Off-nadir/look angle")
    ground_sample_distance_m: Optional[float] = Field(
        default=None, description="Ground sample distance (if sensor GSD provided)"
    )


class PassLightingResponse(BaseModel):
    """Lighting conditions during a pass."""

    target_sunlit: bool = Field(description="Whether target is illuminated by sun")
    satellite_sunlit: bool = Field(description="Whether satellite is in sunlight")
    sun_elevation_deg: float = Field(description="Sun elevation at target location")
    local_solar_time: Optional[str] = Field(
        default=None, description="Local solar time at target (HH:MM)"
    )


class PassQualityResponse(BaseModel):
    """Quality metrics for a pass."""

    quality_score: float = Field(description="Overall quality score (0-100)")
    imaging_feasible: bool = Field(description="Whether imaging is feasible")
    feasibility_reason: Optional[str] = Field(
        default=None, description="Reason if imaging is not feasible"
    )


class PassManeuverResponse(BaseModel):
    """Maneuver requirements for a pass."""

    roll_angle_deg: float = Field(description="Required roll angle (signed)")
    pitch_angle_deg: float = Field(description="Required pitch angle")
    slew_angle_deg: float = Field(description="Total slew from nadir")
    slew_time_s: Optional[float] = Field(
        default=None, description="Estimated slew time in seconds"
    )


class EnrichedPassResponse(BaseModel):
    """Complete STK-like pass data."""

    # Core identification
    target: str
    satellite_name: str
    satellite_id: str
    pass_index: int

    # Timing
    start_time: str
    end_time: str
    max_elevation_time: str
    duration_s: float

    # Basic geometry
    max_elevation: float
    start_azimuth: float
    end_azimuth: float
    pass_type: str

    # STK-like enhanced data
    geometry_aos: Optional[PassGeometryResponse] = None
    geometry_tca: Optional[PassGeometryResponse] = None
    geometry_los: Optional[PassGeometryResponse] = None
    lighting: Optional[PassLightingResponse] = None
    quality: Optional[PassQualityResponse] = None
    maneuver: Optional[PassManeuverResponse] = None


class GeometryAnalysisRequest(BaseModel):
    """Request for point-in-time geometry analysis."""

    satellite_tle: TLEData
    target: TargetData
    timestamp: str = Field(description="ISO format timestamp for analysis")
    sensor_gsd_base_m: Optional[float] = Field(
        default=None, description="Base GSD at nadir for GSD calculation"
    )


class LightingAnalysisRequest(BaseModel):
    """Request for lighting analysis at a location."""

    latitude: float
    longitude: float
    timestamp: str = Field(description="ISO format timestamp")


class PassEnrichmentRequest(BaseModel):
    """Request to enrich pass data with STK-like metrics."""

    satellite_tle: TLEData
    target: TargetData
    start_time: str
    end_time: str
    max_elevation_time: str
    max_elevation: float
    max_roll_rate_dps: float = Field(
        default=1.0, description="Max roll rate for slew calc"
    )


class BatchPassEnrichmentRequest(BaseModel):
    """Request to enrich multiple passes."""

    satellite_tle: TLEData
    targets: List[TargetData]
    passes: List[Dict[str, Any]] = Field(description="List of pass data to enrich")
    max_roll_rate_dps: float = Field(default=1.0)
