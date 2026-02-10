"""Target and coordinate schemas."""

from typing import Optional

from pydantic import BaseModel, field_validator


class TargetData(BaseModel):
    name: str
    latitude: float
    longitude: float
    description: Optional[str] = ""
    priority: Optional[int] = 1  # Target priority (1-5)
    color: Optional[str] = "#EF4444"  # Marker color (hex format)

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90 degrees")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180 degrees")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 1 <= v <= 5:
            raise ValueError("Priority must be between 1 and 5")
        return v


class CoordinateInput(BaseModel):
    """Input model for coordinate parsing."""

    coordinate_string: str


class ParsedTarget(BaseModel):
    """Parsed target response."""

    name: str
    latitude: float
    longitude: float
    description: str = ""
    source: str = "manual"  # manual, file, parsed
