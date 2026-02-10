"""
Backend Pydantic schemas for API request/response models.

All schemas are re-exported here for convenient imports:
    from backend.schemas import TLEData, TargetData, MissionRequest
"""

from backend.schemas.analysis import (
    BatchPassEnrichmentRequest,
    EnrichedPassResponse,
    GeometryAnalysisRequest,
    LightingAnalysisRequest,
    PassEnrichmentRequest,
    PassGeometryResponse,
    PassLightingResponse,
    PassManeuverResponse,
    PassQualityResponse,
)
from backend.schemas.debug import (
    BenchmarkRequest,
    DebugSatellite,
    DebugTarget,
    PlanningParams,
    RunScenarioRequest,
    TimeWindow,
)
from backend.schemas.mission import MissionRequest, MissionResponse, SARInputParams
from backend.schemas.planning import (
    PlanningAuditMetadata,
    PlanningRequest,
    PlanningResponse,
)
from backend.schemas.satellite import SatelliteCreateRequest, SatelliteUpdateRequest
from backend.schemas.target import CoordinateInput, ParsedTarget, TargetData
from backend.schemas.tle import TLEData

__all__ = [
    # TLE
    "TLEData",
    # Target
    "TargetData",
    "CoordinateInput",
    "ParsedTarget",
    # Mission
    "SARInputParams",
    "MissionRequest",
    "MissionResponse",
    # Analysis
    "PassGeometryResponse",
    "PassLightingResponse",
    "PassQualityResponse",
    "PassManeuverResponse",
    "EnrichedPassResponse",
    "GeometryAnalysisRequest",
    "LightingAnalysisRequest",
    "PassEnrichmentRequest",
    "BatchPassEnrichmentRequest",
    # Debug
    "TimeWindow",
    "PlanningParams",
    "DebugSatellite",
    "DebugTarget",
    "RunScenarioRequest",
    "BenchmarkRequest",
    # Satellite
    "SatelliteCreateRequest",
    "SatelliteUpdateRequest",
    # Planning
    "PlanningRequest",
    "PlanningAuditMetadata",
    "PlanningResponse",
]
