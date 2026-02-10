"""TLE (Two-Line Element) schemas."""

from pydantic import BaseModel, field_validator


class TLEData(BaseModel):
    name: str
    line1: str
    line2: str

    @field_validator("line1")
    @classmethod
    def validate_line1(cls, v: str) -> str:
        if not v.strip().startswith("1 "):
            raise ValueError('TLE line1 must start with "1 "')
        if len(v.strip()) < 69:
            raise ValueError("TLE line1 must be at least 69 characters")
        return v.strip()

    @field_validator("line2")
    @classmethod
    def validate_line2(cls, v: str) -> str:
        if not v.strip().startswith("2 "):
            raise ValueError('TLE line2 must start with "2 "')
        if len(v.strip()) < 69:
            raise ValueError("TLE line2 must be at least 69 characters")
        return v.strip()
