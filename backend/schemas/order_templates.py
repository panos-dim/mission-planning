"""Schemas for recurring order templates."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.time_windows import DailyTimeWindow, get_time_zone, parse_hhmm_time

_VALID_WEEKDAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


def _validate_iso_date(value: Optional[str]) -> Optional[str]:
    """Validate YYYY-MM-DD dates while keeping string payloads stable."""
    if value is None:
        return value
    date.fromisoformat(value)
    return value


def _normalize_days_of_week(value: Optional[List[str]]) -> Optional[List[str]]:
    """Normalize weekday tokens to lowercase unique abbreviations."""
    if value is None:
        return value

    normalized: List[str] = []
    seen = set()
    for day in value:
        normalized_day = day.strip().lower()
        if normalized_day not in _VALID_WEEKDAYS:
            raise ValueError(
                f"Invalid weekday: {day}. Must be one of {sorted(_VALID_WEEKDAYS)}"
            )
        if normalized_day not in seen:
            normalized.append(normalized_day)
            seen.add(normalized_day)
    return normalized


class OrderTemplateFields(BaseModel):
    """Normalized recurring-template payload.

    Architectural rule from the recurring-orders audit:
    - order_templates = recurring business intent
    - orders = actionable dated instances
    - order_id = dated instance identity
    - template_id = recurring template identity
    - planner_target_id = unique scheduler-facing identity for each instance
    - canonical_target_id = physical target identity used for grouping/operator meaning
    """

    name: str = Field(..., min_length=1, max_length=200)
    status: Literal["active", "paused", "ended"] = "active"
    canonical_target_id: str = Field(..., min_length=1, max_length=200)
    target_lat: float
    target_lon: float
    priority: int = Field(default=5, ge=1, le=5)
    constraints: Optional[Dict[str, Any]] = None
    requested_satellite_group: Optional[str] = None
    recurrence_type: Literal["daily", "weekly"]
    interval: int = Field(default=1, ge=1)
    days_of_week: Optional[List[str]] = None
    window_start_hhmm: str = Field(..., description="Window start in HH:MM local time")
    window_end_hhmm: str = Field(..., description="Window end in HH:MM local time")
    timezone_name: str = Field(..., description="IANA timezone name")
    effective_start_date: str = Field(..., description="First active local date")
    effective_end_date: Optional[str] = Field(
        default=None, description="Last active local date, if bounded"
    )
    notes: Optional[str] = None
    external_ref: Optional[str] = None

    @field_validator("window_start_hhmm", "window_end_hhmm")
    @classmethod
    def validate_hhmm(cls, value: str) -> str:
        parse_hhmm_time(value)
        return value

    @field_validator("timezone_name")
    @classmethod
    def validate_timezone_name(cls, value: str) -> str:
        get_time_zone(value)
        return value

    @field_validator("effective_start_date", "effective_end_date")
    @classmethod
    def validate_dates(cls, value: Optional[str]) -> Optional[str]:
        return _validate_iso_date(value)

    @field_validator("days_of_week")
    @classmethod
    def validate_days_of_week(
        cls, value: Optional[List[str]]
    ) -> Optional[List[str]]:
        return _normalize_days_of_week(value)

    @model_validator(mode="after")
    def validate_template(self) -> "OrderTemplateFields":
        DailyTimeWindow.from_strings(
            start_time=self.window_start_hhmm,
            end_time=self.window_end_hhmm,
            timezone_name=self.timezone_name,
        )

        start_date = date.fromisoformat(self.effective_start_date)
        if self.effective_end_date is not None:
            end_date = date.fromisoformat(self.effective_end_date)
            if end_date < start_date:
                raise ValueError(
                    "effective_end_date must be on or after effective_start_date"
                )

        if self.recurrence_type == "weekly":
            if not self.days_of_week:
                raise ValueError(
                    "days_of_week is required when recurrence_type is 'weekly'"
                )
        else:
            self.days_of_week = None

        return self


class CreateOrderTemplateRequest(OrderTemplateFields):
    """Request to create a recurring order template."""

    workspace_id: str = Field(..., min_length=1, description="Owning workspace ID")


class UpdateOrderTemplateRequest(BaseModel):
    """PATCH payload for recurring order templates."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    status: Optional[Literal["active", "paused", "ended"]] = None
    canonical_target_id: Optional[str] = Field(default=None, min_length=1, max_length=200)
    target_lat: Optional[float] = None
    target_lon: Optional[float] = None
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    constraints: Optional[Dict[str, Any]] = None
    requested_satellite_group: Optional[str] = None
    recurrence_type: Optional[Literal["daily", "weekly"]] = None
    interval: Optional[int] = Field(default=None, ge=1)
    days_of_week: Optional[List[str]] = None
    window_start_hhmm: Optional[str] = None
    window_end_hhmm: Optional[str] = None
    timezone_name: Optional[str] = None
    effective_start_date: Optional[str] = None
    effective_end_date: Optional[str] = None
    notes: Optional[str] = None
    external_ref: Optional[str] = None

    @field_validator("window_start_hhmm", "window_end_hhmm")
    @classmethod
    def validate_optional_hhmm(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        parse_hhmm_time(value)
        return value

    @field_validator("timezone_name")
    @classmethod
    def validate_optional_timezone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        get_time_zone(value)
        return value

    @field_validator("effective_start_date", "effective_end_date")
    @classmethod
    def validate_optional_dates(cls, value: Optional[str]) -> Optional[str]:
        return _validate_iso_date(value)

    @field_validator("days_of_week")
    @classmethod
    def validate_optional_days(
        cls, value: Optional[List[str]]
    ) -> Optional[List[str]]:
        return _normalize_days_of_week(value)


class OrderTemplateResponse(OrderTemplateFields):
    """Recurring order template read model."""

    id: str
    workspace_id: str
    created_at: str
    updated_at: str


class OrderTemplateCreateResponse(BaseModel):
    """Single-template create/get/patch response."""

    success: bool
    template: OrderTemplateResponse


class OrderTemplateListResponse(BaseModel):
    """List response for recurring order templates."""

    success: bool
    templates: List[OrderTemplateResponse]
    total: int


class OrderTemplateDeleteResponse(BaseModel):
    """Delete response for recurring order templates."""

    success: bool
    message: str
    template_deleted: bool
