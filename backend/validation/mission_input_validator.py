"""
Mission Input Validator - Enforces parameter governance rules.

Validates mission inputs against:
- Satellite bus limits (max roll, rates)
- SAR mode bounds (incidence angles)
- Parameter ownership rules (Admin vs Mission Input)
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


@dataclass
class ValidationError:
    """A validation error with details."""

    field: str
    message: str
    severity: str = "error"  # "error" or "warning"
    suggested_value: Optional[Any] = None


@dataclass
class ValidationResult:
    """Result of mission input validation."""

    valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    clamped_values: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [
                {"field": e.field, "message": e.message, "severity": e.severity}
                for e in self.errors
            ],
            "warnings": [
                {
                    "field": w.field,
                    "message": w.message,
                    "severity": w.severity,
                    "suggested_value": w.suggested_value,
                }
                for w in self.warnings
            ],
            "clamped_values": self.clamped_values,
        }


class MissionInputValidator:
    """Validates mission inputs against platform configuration."""

    def __init__(self) -> None:
        self.sar_modes: Dict[str, Any] = {}
        self.satellites: Dict[str, Any] = {}
        self.satellite_settings: Dict[str, Any] = {}
        self._load_configs()

    def _load_configs(self) -> None:
        """Load configuration files."""
        try:
            # Load SAR modes
            sar_modes_path = CONFIG_DIR / "sar_modes.yaml"
            if sar_modes_path.exists():
                with open(sar_modes_path, "r") as f:
                    config = yaml.safe_load(f) or {}
                    self.sar_modes = config.get("modes", {})

            # Load satellites
            satellites_path = CONFIG_DIR / "satellites.yaml"
            if satellites_path.exists():
                with open(satellites_path, "r") as f:
                    config = yaml.safe_load(f) or {}
                    self.satellite_settings = config.get("satellite_settings", {})
                    # Index satellites by ID
                    for sat in config.get("satellites", []):
                        self.satellites[sat.get("id", sat.get("name"))] = sat

        except Exception as e:
            logger.error(f"Error loading validation configs: {e}")

    def reload_configs(self) -> None:
        """Reload configuration files."""
        self._load_configs()

    def validate_mission_input(
        self,
        mission_input: Dict[str, Any],
        satellite_ids: List[str],
        clamp_on_warning: bool = True,
    ) -> ValidationResult:
        """
        Validate mission input against platform constraints.

        Args:
            mission_input: The mission input parameters
            satellite_ids: List of satellite IDs being used
            clamp_on_warning: If True, clamp values that exceed bounds (warning)
                            If False, reject values that exceed bounds (error)

        Returns:
            ValidationResult with errors, warnings, and clamped values
        """
        result = ValidationResult(valid=True)

        # Get imaging type
        imaging_type = mission_input.get("imagingType", "optical")

        # Validate based on imaging type
        if imaging_type == "sar":
            self._validate_sar_inputs(
                mission_input, satellite_ids, result, clamp_on_warning
            )
        else:
            self._validate_optical_inputs(
                mission_input, satellite_ids, result, clamp_on_warning
            )

        # Validate time window
        self._validate_time_window(mission_input, result)

        # Check for forbidden direct bus limit changes
        self._check_bus_limit_overrides(mission_input, result)

        # Set valid = False if there are errors
        result.valid = len(result.errors) == 0

        return result

    def _validate_sar_inputs(
        self,
        mission_input: Dict[str, Any],
        satellite_ids: List[str],
        result: ValidationResult,
        clamp_on_warning: bool,
    ) -> None:
        """Validate SAR-specific inputs."""
        sar_params = mission_input.get("sar", {})
        if not sar_params:
            return

        imaging_mode = sar_params.get("imaging_mode", "strip")

        # Check if SAR mode is supported
        if imaging_mode not in self.sar_modes:
            result.errors.append(
                ValidationError(
                    field="sar.imaging_mode",
                    message=f"Unsupported SAR mode: '{imaging_mode}'. Valid modes: {list(self.sar_modes.keys())}",
                )
            )
            return

        mode_config = self.sar_modes[imaging_mode]
        incidence = mode_config.get("incidence_angle", {})

        # Get user-specified incidence range
        user_inc_min = sar_params.get("incidence_min_deg")
        user_inc_max = sar_params.get("incidence_max_deg")

        # Get absolute bounds from mode config
        abs_min = incidence.get("absolute_min", 10)
        abs_max = incidence.get("absolute_max", 55)
        rec_min = incidence.get("recommended_min", 15)
        rec_max = incidence.get("recommended_max", 45)

        # Validate incidence_min_deg
        if user_inc_min is not None:
            if user_inc_min < abs_min:
                if clamp_on_warning:
                    result.warnings.append(
                        ValidationError(
                            field="sar.incidence_min_deg",
                            message=f"Incidence min {user_inc_min}° below mode absolute min {abs_min}°. Clamped.",
                            severity="warning",
                            suggested_value=abs_min,
                        )
                    )
                    result.clamped_values["sar.incidence_min_deg"] = abs_min
                else:
                    result.errors.append(
                        ValidationError(
                            field="sar.incidence_min_deg",
                            message=f"Incidence min {user_inc_min}° below mode absolute min {abs_min}°.",
                        )
                    )
            elif user_inc_min < rec_min:
                result.warnings.append(
                    ValidationError(
                        field="sar.incidence_min_deg",
                        message=f"Incidence min {user_inc_min}° below recommended min {rec_min}°. Quality may be degraded.",
                        severity="warning",
                    )
                )

        # Validate incidence_max_deg
        if user_inc_max is not None:
            if user_inc_max > abs_max:
                if clamp_on_warning:
                    result.warnings.append(
                        ValidationError(
                            field="sar.incidence_max_deg",
                            message=f"Incidence max {user_inc_max}° above mode absolute max {abs_max}°. Clamped.",
                            severity="warning",
                            suggested_value=abs_max,
                        )
                    )
                    result.clamped_values["sar.incidence_max_deg"] = abs_max
                else:
                    result.errors.append(
                        ValidationError(
                            field="sar.incidence_max_deg",
                            message=f"Incidence max {user_inc_max}° above mode absolute max {abs_max}°.",
                        )
                    )
            elif user_inc_max > rec_max:
                result.warnings.append(
                    ValidationError(
                        field="sar.incidence_max_deg",
                        message=f"Incidence max {user_inc_max}° above recommended max {rec_max}°. Quality may be degraded.",
                        severity="warning",
                    )
                )

        # Validate min < max
        if user_inc_min is not None and user_inc_max is not None:
            # Use clamped values if available
            actual_min = result.clamped_values.get(
                "sar.incidence_min_deg", user_inc_min
            )
            actual_max = result.clamped_values.get(
                "sar.incidence_max_deg", user_inc_max
            )
            if actual_min >= actual_max:
                result.errors.append(
                    ValidationError(
                        field="sar.incidence_range",
                        message=f"Incidence min ({actual_min}°) must be less than max ({actual_max}°).",
                    )
                )

        # Check SAR mode supported by selected satellites
        for sat_id in satellite_ids:
            satellite = self.satellites.get(sat_id)
            if satellite and satellite.get("imaging_type") != "sar":
                result.warnings.append(
                    ValidationError(
                        field="satellites",
                        message=f"Satellite '{sat_id}' is not a SAR satellite. SAR parameters will be ignored for this satellite.",
                        severity="warning",
                    )
                )

    def _validate_optical_inputs(
        self,
        mission_input: Dict[str, Any],
        satellite_ids: List[str],
        result: ValidationResult,
        clamp_on_warning: bool,
    ) -> None:
        """Validate optical-specific inputs."""
        pointing_angle = mission_input.get("pointingAngle")
        if pointing_angle is None:
            return

        # Get max roll limits from selected satellites
        for sat_id in satellite_ids:
            satellite = self.satellites.get(sat_id)
            if not satellite:
                continue

            # Get satellite's max roll
            sat_max_roll = satellite.get("max_spacecraft_roll_deg")
            if sat_max_roll is None:
                # Get from defaults based on imaging type
                imaging_type = satellite.get("imaging_type", "optical")
                settings = self.satellite_settings.get(imaging_type, {})
                spacecraft = settings.get("spacecraft", {})
                sat_max_roll = spacecraft.get("max_spacecraft_roll_deg", 45)

            if pointing_angle > sat_max_roll:
                if clamp_on_warning:
                    result.warnings.append(
                        ValidationError(
                            field="pointingAngle",
                            message=f"Pointing angle {pointing_angle}° exceeds satellite '{sat_id}' max roll {sat_max_roll}°. Clamped.",
                            severity="warning",
                            suggested_value=sat_max_roll,
                        )
                    )
                    result.clamped_values["pointingAngle"] = min(
                        result.clamped_values.get("pointingAngle", pointing_angle),
                        sat_max_roll,
                    )
                else:
                    result.errors.append(
                        ValidationError(
                            field="pointingAngle",
                            message=f"Pointing angle {pointing_angle}° exceeds satellite '{sat_id}' max roll {sat_max_roll}°.",
                        )
                    )

    def _validate_time_window(
        self, mission_input: Dict[str, Any], result: ValidationResult
    ) -> None:
        """Validate time window parameters."""
        from datetime import datetime, timedelta

        start_time_str = mission_input.get("startTime")
        end_time_str = mission_input.get("endTime")

        if not start_time_str or not end_time_str:
            result.errors.append(
                ValidationError(
                    field="timeWindow",
                    message="Start time and end time are required.",
                )
            )
            return

        try:
            # Parse times (handle both Z and +00:00 suffixes)
            start_time_str = start_time_str.replace("Z", "+00:00")
            end_time_str = end_time_str.replace("Z", "+00:00")
            start_time = datetime.fromisoformat(start_time_str)
            end_time = datetime.fromisoformat(end_time_str)

            if end_time <= start_time:
                result.errors.append(
                    ValidationError(
                        field="endTime",
                        message="End time must be after start time.",
                    )
                )

            # Check duration doesn't exceed 30 days
            max_duration = timedelta(days=30)
            if (end_time - start_time) > max_duration:
                result.errors.append(
                    ValidationError(
                        field="timeWindow",
                        message="Time window cannot exceed 30 days.",
                    )
                )

        except ValueError as e:
            result.errors.append(
                ValidationError(
                    field="timeWindow",
                    message=f"Invalid time format: {e}",
                )
            )

    def _check_bus_limit_overrides(
        self, mission_input: Dict[str, Any], result: ValidationResult
    ) -> None:
        """
        Check for forbidden direct bus limit changes.

        These parameters should only be set via Admin panel, not per-mission.
        """
        forbidden_overrides = [
            "max_roll_rate_dps",
            "max_roll_accel_dps2",
            "max_pitch_rate_dps",
            "max_pitch_accel_dps2",
            "settling_time_s",
            "sensor_fov_half_angle_deg",
        ]

        for param in forbidden_overrides:
            if param in mission_input:
                override_allowed = mission_input.get("allow_bus_override", False)
                if not override_allowed:
                    result.errors.append(
                        ValidationError(
                            field=param,
                            message=f"Direct override of '{param}' is not allowed. "
                            f"This parameter is managed in Admin panel. "
                            f"Set 'allow_bus_override=true' to force (advanced).",
                        )
                    )


# Singleton instance
_validator: Optional[MissionInputValidator] = None


def get_validator() -> MissionInputValidator:
    """Get or create the mission input validator instance."""
    global _validator
    if _validator is None:
        _validator = MissionInputValidator()
    return _validator


def validate_mission_input(
    mission_input: Dict[str, Any],
    satellite_ids: List[str],
    clamp_on_warning: bool = True,
) -> ValidationResult:
    """
    Validate mission input parameters.

    This is the main entry point for mission validation.

    Args:
        mission_input: Mission parameters from the frontend
        satellite_ids: List of satellite IDs being used
        clamp_on_warning: If True, clamp out-of-bounds values (default)
                         If False, reject out-of-bounds values

    Returns:
        ValidationResult with errors, warnings, and clamped values
    """
    validator = get_validator()
    return validator.validate_mission_input(
        mission_input, satellite_ids, clamp_on_warning
    )


def reload_validation_config() -> None:
    """Reload validation configuration from files."""
    validator = get_validator()
    validator.reload_configs()
