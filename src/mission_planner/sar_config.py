"""
SAR Mode Configuration and Management.

This module provides configuration management for SAR imaging modes,
aligned with ICEYE tasking API concepts. It loads mode specifications
from config/sar_modes.yaml and provides programmatic access.

ICEYE-Parity Concepts:
- Imaging modes: Spot, Strip, Scan, Dwell
- Look side: LEFT, RIGHT, ANY
- Pass direction: ASCENDING, DESCENDING, ANY
- Incidence angle constraints per mode
"""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS - SAR-specific types
# =============================================================================


class SARMode(Enum):
    """SAR imaging mode types (ICEYE-aligned)."""

    SPOT = "spot"
    STRIP = "strip"
    SCAN = "scan"
    DWELL = "dwell"

    @classmethod
    def from_string(cls, value: str) -> "SARMode":
        """Create SARMode from string (case-insensitive)."""
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(
                f"Invalid SAR mode: {value}. " f"Valid modes: {[m.value for m in cls]}"
            )


class LookSide(Enum):
    """SAR look side (antenna pointing direction)."""

    LEFT = "LEFT"
    RIGHT = "RIGHT"
    ANY = "ANY"

    @classmethod
    def from_string(cls, value: str) -> "LookSide":
        """Create LookSide from string (case-insensitive)."""
        try:
            return cls(value.upper())
        except ValueError:
            raise ValueError(
                f"Invalid look side: {value}. "
                f"Valid options: {[s.value for s in cls]}"
            )


class PassDirection(Enum):
    """Satellite pass direction over target."""

    ASCENDING = "ASCENDING"
    DESCENDING = "DESCENDING"
    ANY = "ANY"

    @classmethod
    def from_string(cls, value: str) -> "PassDirection":
        """Create PassDirection from string (case-insensitive)."""
        try:
            return cls(value.upper())
        except ValueError:
            raise ValueError(
                f"Invalid pass direction: {value}. "
                f"Valid options: {[d.value for d in cls]}"
            )


# =============================================================================
# DATA CLASSES - SAR configuration structures
# =============================================================================


@dataclass
class IncidenceAngleSpec:
    """Incidence angle constraints for a SAR mode."""

    recommended_min: float
    recommended_max: float
    absolute_min: float
    absolute_max: float

    def is_within_recommended(self, angle_deg: float) -> bool:
        """Check if angle is within recommended range."""
        return self.recommended_min <= angle_deg <= self.recommended_max

    def is_within_absolute(self, angle_deg: float) -> bool:
        """Check if angle is within absolute limits."""
        return self.absolute_min <= angle_deg <= self.absolute_max

    def get_recommended_range(self) -> Tuple[float, float]:
        """Get recommended incidence range as tuple."""
        return (self.recommended_min, self.recommended_max)


@dataclass
class SceneSpec:
    """Scene/swath dimensions for a SAR mode."""

    width_km: float
    length_km: float
    max_length_km: Optional[float] = None


@dataclass
class CollectionSpec:
    """Collection parameters for a SAR mode."""

    duration_s: Optional[float]
    azimuth_resolution_m: float
    range_resolution_m: float


@dataclass
class QualitySpec:
    """Quality scoring parameters for a SAR mode."""

    optimal_incidence_deg: float
    quality_model: str = "band"  # "band" or "monotonic"


@dataclass
class SARModeSpec:
    """Complete specification for a SAR imaging mode."""

    mode: SARMode
    display_name: str
    description: str
    incidence_angle: IncidenceAngleSpec
    scene: SceneSpec
    collection: CollectionSpec
    quality: QualitySpec

    def get_swath_width_km(self) -> float:
        """Get swath width for this mode."""
        return self.scene.width_km

    def get_scene_length_km(self) -> float:
        """Get scene/strip length for this mode."""
        return self.scene.length_km

    def validate_incidence(self, angle_deg: float) -> Tuple[bool, str]:
        """
        Validate an incidence angle against mode constraints.

        Returns:
            Tuple of (is_valid, reason_message)
        """
        if angle_deg < self.incidence_angle.absolute_min:
            return (
                False,
                f"Incidence {angle_deg:.1f}° below minimum "
                f"{self.incidence_angle.absolute_min:.1f}° for {self.display_name}",
            )
        if angle_deg > self.incidence_angle.absolute_max:
            return (
                False,
                f"Incidence {angle_deg:.1f}° exceeds maximum "
                f"{self.incidence_angle.absolute_max:.1f}° for {self.display_name}",
            )
        return (True, "")


@dataclass
class SARSpacecraftSpec:
    """SAR spacecraft/bus configuration."""

    max_roll_deg: float = 60.0
    max_roll_rate_dps: float = 1.0
    max_roll_accel_dps2: float = 1.0
    settling_time_s: float = 3.0
    max_pitch_deg: float = 0.0
    max_pitch_rate_dps: float = 0.0


@dataclass
class SARConstraints:
    """SAR-specific mission constraints."""

    requires_illumination: bool = False  # SAR works day/night
    weather_constraint: str = "none"
    min_elevation_deg: float = 10.0
    max_squint_angle_deg: float = 5.0


@dataclass
class SARInputParams:
    """
    User-provided SAR mission parameters (ICEYE-aligned).

    These are the inputs that users provide when configuring a SAR mission.
    """

    imaging_mode: SARMode = SARMode.STRIP
    incidence_min_deg: Optional[float] = None  # Use mode default if None
    incidence_max_deg: Optional[float] = None  # Use mode default if None
    look_side: LookSide = LookSide.ANY
    pass_direction: PassDirection = PassDirection.ANY

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "imaging_mode": self.imaging_mode.value,
            "incidence_min_deg": self.incidence_min_deg,
            "incidence_max_deg": self.incidence_max_deg,
            "look_side": self.look_side.value,
            "pass_direction": self.pass_direction.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SARInputParams":
        """Create from dictionary."""
        return cls(
            imaging_mode=SARMode.from_string(data.get("imaging_mode", "strip")),
            incidence_min_deg=data.get("incidence_min_deg"),
            incidence_max_deg=data.get("incidence_max_deg"),
            look_side=LookSide.from_string(data.get("look_side", "ANY")),
            pass_direction=PassDirection.from_string(data.get("pass_direction", "ANY")),
        )


# =============================================================================
# SAR OPPORTUNITY DATA
# =============================================================================


@dataclass
class SAROpportunityData:
    """
    SAR-specific data for an imaging opportunity.

    This extends the base opportunity with SAR-specific attributes
    needed for proper swath visualization and mission planning.
    """

    # Core SAR attributes (ICEYE-aligned)
    look_side: LookSide
    pass_direction: PassDirection

    # Incidence angles (near/center/far swath model)
    incidence_center_deg: float
    incidence_near_deg: Optional[float] = None  # Near edge of swath
    incidence_far_deg: Optional[float] = None  # Far edge of swath

    # Swath geometry
    swath_width_km: float = 30.0
    scene_length_km: float = 50.0

    # Imaging mode used
    imaging_mode: SARMode = SARMode.STRIP

    # Quality metrics
    quality_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "look_side": self.look_side.value,
            "pass_direction": self.pass_direction.value,
            "incidence_center_deg": round(self.incidence_center_deg, 2),
            "incidence_near_deg": (
                round(self.incidence_near_deg, 2)
                if self.incidence_near_deg is not None
                else None
            ),
            "incidence_far_deg": (
                round(self.incidence_far_deg, 2)
                if self.incidence_far_deg is not None
                else None
            ),
            "swath_width_km": round(self.swath_width_km, 2),
            "scene_length_km": round(self.scene_length_km, 2),
            "imaging_mode": self.imaging_mode.value,
            "quality_score": round(self.quality_score, 1),
        }


# =============================================================================
# CONFIGURATION MANAGER
# =============================================================================


class SARConfigManager:
    """
    Manages SAR mode configurations loaded from YAML.

    Provides access to mode specifications, validation, and defaults.
    """

    _instance: Optional["SARConfigManager"] = None
    _config: Dict[str, Any] = {}
    _modes: Dict[SARMode, SARModeSpec] = {}

    def __new__(cls) -> "SARConfigManager":
        """Singleton pattern for config manager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        """Load SAR configuration from YAML file."""
        # Find config file
        config_paths = [
            Path(__file__).parent.parent.parent / "config" / "sar_modes.yaml",
            Path("config/sar_modes.yaml"),
            Path(
                "/Users/panagiotis.d/CascadeProjects/mission-planning/config/sar_modes.yaml"
            ),
        ]

        config_file = None
        for path in config_paths:
            if path.exists():
                config_file = path
                break

        if config_file is None:
            logger.warning(
                "SAR config file not found, using built-in defaults. "
                f"Searched: {[str(p) for p in config_paths]}"
            )
            self._use_builtin_defaults()
            return

        try:
            with open(config_file, "r") as f:
                self._config = yaml.safe_load(f)

            logger.info(f"Loaded SAR configuration from {config_file}")
            self._parse_modes()

        except Exception as e:
            logger.error(f"Error loading SAR config: {e}")
            self._use_builtin_defaults()

    def _use_builtin_defaults(self) -> None:
        """Use built-in defaults if config file unavailable."""
        self._modes = {
            SARMode.SPOT: SARModeSpec(
                mode=SARMode.SPOT,
                display_name="Spot",
                description="High-resolution spotlight mode",
                incidence_angle=IncidenceAngleSpec(15.0, 35.0, 10.0, 45.0),
                scene=SceneSpec(5.0, 5.0),
                collection=CollectionSpec(10.0, 0.5, 0.5),
                quality=QualitySpec(25.0, "band"),
            ),
            SARMode.STRIP: SARModeSpec(
                mode=SARMode.STRIP,
                display_name="Strip",
                description="Standard stripmap mode",
                incidence_angle=IncidenceAngleSpec(15.0, 45.0, 10.0, 55.0),
                scene=SceneSpec(30.0, 50.0, 500.0),
                collection=CollectionSpec(None, 3.0, 3.0),
                quality=QualitySpec(30.0, "band"),
            ),
            SARMode.SCAN: SARModeSpec(
                mode=SARMode.SCAN,
                display_name="Scan",
                description="Wide area ScanSAR mode",
                incidence_angle=IncidenceAngleSpec(20.0, 50.0, 15.0, 55.0),
                scene=SceneSpec(100.0, 100.0, 1000.0),
                collection=CollectionSpec(None, 15.0, 15.0),
                quality=QualitySpec(35.0, "band"),
            ),
            SARMode.DWELL: SARModeSpec(
                mode=SARMode.DWELL,
                display_name="Dwell",
                description="Extended dwell mode",
                incidence_angle=IncidenceAngleSpec(20.0, 40.0, 15.0, 50.0),
                scene=SceneSpec(5.0, 5.0),
                collection=CollectionSpec(25.0, 1.0, 1.0),
                quality=QualitySpec(30.0, "band"),
            ),
        }
        logger.info("Using built-in SAR mode defaults")

    def _parse_modes(self) -> None:
        """Parse mode specifications from loaded config."""
        modes_config = self._config.get("modes", {})

        for mode_key, mode_data in modes_config.items():
            try:
                mode_enum = SARMode.from_string(mode_key)
                inc_data = mode_data.get("incidence_angle", {})
                scene_data = mode_data.get("scene", {})
                coll_data = mode_data.get("collection", {})
                qual_data = mode_data.get("quality", {})

                self._modes[mode_enum] = SARModeSpec(
                    mode=mode_enum,
                    display_name=mode_data.get("display_name", mode_key.title()),
                    description=mode_data.get("description", ""),
                    incidence_angle=IncidenceAngleSpec(
                        recommended_min=inc_data.get("recommended_min", 15.0),
                        recommended_max=inc_data.get("recommended_max", 45.0),
                        absolute_min=inc_data.get("absolute_min", 10.0),
                        absolute_max=inc_data.get("absolute_max", 55.0),
                    ),
                    scene=SceneSpec(
                        width_km=scene_data.get("width_km", 30.0),
                        length_km=scene_data.get("length_km", 50.0),
                        max_length_km=scene_data.get("max_length_km"),
                    ),
                    collection=CollectionSpec(
                        duration_s=coll_data.get("duration_s"),
                        azimuth_resolution_m=coll_data.get("azimuth_resolution_m", 3.0),
                        range_resolution_m=coll_data.get("range_resolution_m", 3.0),
                    ),
                    quality=QualitySpec(
                        optimal_incidence_deg=qual_data.get(
                            "optimal_incidence_deg", 30.0
                        ),
                        quality_model=qual_data.get("quality_model", "band"),
                    ),
                )
                logger.debug(f"Loaded SAR mode: {mode_enum.value}")

            except Exception as e:
                logger.warning(f"Error parsing SAR mode {mode_key}: {e}")

    def get_mode_spec(self, mode: SARMode) -> SARModeSpec:
        """Get specification for a SAR mode."""
        if mode not in self._modes:
            raise ValueError(f"Unknown SAR mode: {mode}")
        return self._modes[mode]

    def get_all_modes(self) -> List[SARModeSpec]:
        """Get all available SAR mode specifications."""
        return list(self._modes.values())

    def get_mode_names(self) -> List[str]:
        """Get list of available mode names."""
        return [m.value for m in self._modes.keys()]

    def get_spacecraft_spec(self) -> SARSpacecraftSpec:
        """Get SAR spacecraft specification."""
        sc_config = self._config.get("spacecraft", {})
        return SARSpacecraftSpec(
            max_roll_deg=sc_config.get("max_roll_deg", 60.0),
            max_roll_rate_dps=sc_config.get("max_roll_rate_dps", 1.0),
            max_roll_accel_dps2=sc_config.get("max_roll_accel_dps2", 1.0),
            settling_time_s=sc_config.get("settling_time_s", 3.0),
            max_pitch_deg=sc_config.get("max_pitch_deg", 0.0),
            max_pitch_rate_dps=sc_config.get("max_pitch_rate_dps", 0.0),
        )

    def get_constraints(self) -> SARConstraints:
        """Get SAR-specific constraints."""
        c_config = self._config.get("constraints", {})
        return SARConstraints(
            requires_illumination=c_config.get("requires_illumination", False),
            weather_constraint=c_config.get("weather_constraint", "none"),
            min_elevation_deg=c_config.get("min_elevation_deg", 10.0),
            max_squint_angle_deg=c_config.get("max_squint_angle_deg", 5.0),
        )

    def get_default_incidence_range(self, mode: SARMode) -> Tuple[float, float]:
        """Get default incidence angle range for a mode."""
        spec = self.get_mode_spec(mode)
        return spec.incidence_angle.get_recommended_range()

    def get_swath_width(self, mode: SARMode) -> float:
        """Get swath width for a mode in km."""
        spec = self.get_mode_spec(mode)
        return spec.scene.width_km

    def validate_sar_params(self, params: SARInputParams) -> Tuple[bool, List[str]]:
        """
        Validate SAR input parameters against mode constraints.

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        spec = self.get_mode_spec(params.imaging_mode)

        # Validate incidence range if specified
        if params.incidence_min_deg is not None:
            if params.incidence_min_deg < spec.incidence_angle.absolute_min:
                issues.append(
                    f"Min incidence {params.incidence_min_deg}° below "
                    f"absolute minimum {spec.incidence_angle.absolute_min}° for {spec.display_name}"
                )

        if params.incidence_max_deg is not None:
            if params.incidence_max_deg > spec.incidence_angle.absolute_max:
                issues.append(
                    f"Max incidence {params.incidence_max_deg}° exceeds "
                    f"absolute maximum {spec.incidence_angle.absolute_max}° for {spec.display_name}"
                )

        if (
            params.incidence_min_deg is not None
            and params.incidence_max_deg is not None
            and params.incidence_min_deg > params.incidence_max_deg
        ):
            issues.append(
                f"Min incidence {params.incidence_min_deg}° greater than "
                f"max incidence {params.incidence_max_deg}°"
            )

        return (len(issues) == 0, issues)


# =============================================================================
# MODULE-LEVEL FUNCTIONS
# =============================================================================


def get_sar_config() -> SARConfigManager:
    """Get the SAR configuration manager instance."""
    return SARConfigManager()


def get_mode_spec(mode: str) -> SARModeSpec:
    """Get specification for a SAR mode by name."""
    return get_sar_config().get_mode_spec(SARMode.from_string(mode))


def get_default_sar_params(mode: str = "strip") -> SARInputParams:
    """Get default SAR parameters for a mode."""
    sar_mode = SARMode.from_string(mode)
    config = get_sar_config()
    inc_min, inc_max = config.get_default_incidence_range(sar_mode)

    return SARInputParams(
        imaging_mode=sar_mode,
        incidence_min_deg=inc_min,
        incidence_max_deg=inc_max,
        look_side=LookSide.ANY,
        pass_direction=PassDirection.ANY,
    )
