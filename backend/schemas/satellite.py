"""Satellite management schemas."""

from typing import Optional

from pydantic import BaseModel


class SatelliteCreateRequest(BaseModel):
    name: str
    line1: str
    line2: str
    imaging_type: str = "optical"
    sensor_fov_half_angle_deg: float = 1.0  # Default for optical
    satellite_agility: float = 1.0
    sar_mode: str = "stripmap"
    description: str = ""
    active: bool = True


class SatelliteUpdateRequest(BaseModel):
    name: Optional[str] = None
    line1: Optional[str] = None
    line2: Optional[str] = None
    imaging_type: Optional[str] = None
    sensor_fov_half_angle_deg: Optional[float] = None
    satellite_agility: Optional[float] = None
    sar_mode: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None
