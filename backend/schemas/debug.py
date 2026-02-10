"""Debug and benchmark scenario schemas."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TimeWindow(BaseModel):
    """Time window for scenario."""

    start: str
    end: str


class PlanningParams(BaseModel):
    """Planning parameters for debug scenarios."""

    imaging_time_s: float = 1.0
    max_roll_rate_dps: float = 3.0
    max_roll_accel_dps2: float = 1.0
    max_spacecraft_roll_deg: float = 45.0
    max_pitch_rate_dps: float = 0.5
    max_pitch_accel_dps2: float = 0.25
    max_spacecraft_pitch_deg: float = 10.0
    quality_weight: float = 0.6
    quality_model: str = "off"


class DebugSatellite(BaseModel):
    """Satellite configuration for debug scenario."""

    id: str
    name: str
    tle_line1: str
    tle_line2: str


class DebugTarget(BaseModel):
    """Target configuration for debug scenario."""

    name: str
    latitude: float
    longitude: float
    priority: int = 1
    id: Optional[str] = None  # Optional for backwards compatibility


class RunScenarioRequest(BaseModel):
    """Request to run a single debug scenario."""

    scenario_id: Optional[str] = None
    satellites: List[DebugSatellite]
    targets: List[DebugTarget]
    time_window: TimeWindow
    mission_mode: str = "OPTICAL"
    algorithms: List[str] = [
        "first_fit",
        "best_fit",
        "roll_pitch_first_fit",
    ]  # "optimal" disabled
    planning_params: PlanningParams = Field(default_factory=PlanningParams)


class BenchmarkRequest(BaseModel):
    """Request to run benchmark across multiple scenarios."""

    presets: List[str] = Field(default_factory=list)
    num_random_scenarios: int = 0
    mission_mode: str = "OPTICAL"
    algorithms: List[str] = ["first_fit", "roll_pitch_first_fit"]  # "optimal" disabled
    vary_params: Optional[Dict[str, List[float]]] = None
