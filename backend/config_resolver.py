"""
Config Resolver - Single source of truth for mission configuration.

Loads satellites.yaml, sar_modes.yaml, ground_stations.yaml, mission_settings.yaml
and produces a ResolvedConfig for each mission run.

Enforces parameter governance rules:
- Bus limits/rates/settling time → Admin only (reject if sent via mission input)
- SAR mode + look side + pass direction + optional incidence override → Mission input
- Optical pointing angle override allowed but must be ≤ max_spacecraft_roll_deg
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent / "config"


# =============================================================================
# Data Classes for Resolved Configuration
# =============================================================================


@dataclass
class SpacecraftBusConfig:
    """Spacecraft bus limits - Admin only, cannot be overridden by mission input."""

    max_spacecraft_roll_deg: float = 45.0
    max_roll_rate_dps: float = 1.0
    max_roll_accel_dps2: float = 1.0
    max_spacecraft_pitch_deg: float = 0.0
    max_pitch_rate_dps: float = 0.0
    max_pitch_accel_dps2: float = 0.0
    settling_time_s: float = 5.0
    satellite_agility: float = 1.0


@dataclass
class SensorConfig:
    """Sensor/payload configuration - Admin only."""

    sensor_fov_half_angle_deg: float = 1.0
    imaging_type: str = "optical"  # "optical" or "sar"
    min_sun_elevation_deg: float = 0.0
    max_cloud_cover_percent: float = 100.0


@dataclass
class SARModeConfig:
    """SAR mode configuration from sar_modes.yaml - Admin only."""

    display_name: str = ""
    description: str = ""
    incidence_recommended_min: float = 15.0
    incidence_recommended_max: float = 45.0
    incidence_absolute_min: float = 10.0
    incidence_absolute_max: float = 55.0
    scene_width_km: float = 30.0
    scene_length_km: float = 50.0
    collection_duration_s: Optional[float] = None
    optimal_incidence_deg: float = 30.0
    quality_model: str = "band"


@dataclass
class SARMissionInput:
    """SAR-specific mission input parameters - User configurable per run."""

    imaging_mode: str = "strip"  # spot, strip, scan, dwell
    look_side: str = "ANY"  # LEFT, RIGHT, ANY
    pass_direction: str = "ANY"  # ASC, DESC, ANY
    incidence_min_deg: Optional[float] = None  # Override within mode bounds
    incidence_max_deg: Optional[float] = None  # Override within mode bounds


@dataclass
class OpticalMissionInput:
    """Optical-specific mission input parameters - User configurable per run."""

    pointing_angle: float = 45.0  # Must be ≤ max_spacecraft_roll_deg
    illumination_filter: bool = True  # Filter for daylight passes


@dataclass
class ResolvedSatelliteConfig:
    """Fully resolved satellite configuration for a mission run."""

    id: str
    name: str
    tle_line1: str
    tle_line2: str
    imaging_type: str
    bus: SpacecraftBusConfig
    sensor: SensorConfig
    supported_sar_modes: List[str] = field(default_factory=list)


@dataclass
class ResolvedSARConfig:
    """Resolved SAR configuration combining mode defaults and mission overrides."""

    mode: SARModeConfig
    mission_input: SARMissionInput
    # Effective incidence bounds after applying overrides + clamping
    effective_incidence_min: float = 15.0
    effective_incidence_max: float = 45.0


@dataclass
class ResolvedConfig:
    """Complete resolved configuration for a mission run."""

    # Metadata
    config_hash: str = ""
    resolved_at: str = ""

    # Mission parameters (from user input)
    start_time: str = ""
    end_time: str = ""
    targets: List[Dict[str, Any]] = field(default_factory=list)

    # Satellite configurations (from YAML + defaults)
    satellites: List[ResolvedSatelliteConfig] = field(default_factory=list)

    # SAR configuration (if SAR mission)
    sar_config: Optional[ResolvedSARConfig] = None

    # Optical configuration (if optical mission)
    optical_config: Optional[OpticalMissionInput] = None

    # Validation warnings that were applied
    warnings: List[str] = field(default_factory=list)
    clamped_values: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: Dict[str, Any] = {
            "config_hash": self.config_hash,
            "resolved_at": self.resolved_at,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "targets": self.targets,
            "satellites": [],
            "warnings": self.warnings,
            "clamped_values": self.clamped_values,
        }

        for sat in self.satellites:
            result["satellites"].append(
                {
                    "id": sat.id,
                    "name": sat.name,
                    "imaging_type": sat.imaging_type,
                    "bus": {
                        "max_spacecraft_roll_deg": sat.bus.max_spacecraft_roll_deg,
                        "max_roll_rate_dps": sat.bus.max_roll_rate_dps,
                        "max_roll_accel_dps2": sat.bus.max_roll_accel_dps2,
                        "max_spacecraft_pitch_deg": sat.bus.max_spacecraft_pitch_deg,
                        "max_pitch_rate_dps": sat.bus.max_pitch_rate_dps,
                        "max_pitch_accel_dps2": sat.bus.max_pitch_accel_dps2,
                        "settling_time_s": sat.bus.settling_time_s,
                        "satellite_agility": sat.bus.satellite_agility,
                    },
                    "sensor": {
                        "sensor_fov_half_angle_deg": sat.sensor.sensor_fov_half_angle_deg,
                        "imaging_type": sat.sensor.imaging_type,
                        "min_sun_elevation_deg": sat.sensor.min_sun_elevation_deg,
                        "max_cloud_cover_percent": sat.sensor.max_cloud_cover_percent,
                    },
                    "supported_sar_modes": sat.supported_sar_modes,
                }
            )

        if self.sar_config:
            result["sar_config"] = {
                "mode_name": self.sar_config.mission_input.imaging_mode,
                "mode": {
                    "display_name": self.sar_config.mode.display_name,
                    "incidence_absolute_min": self.sar_config.mode.incidence_absolute_min,
                    "incidence_absolute_max": self.sar_config.mode.incidence_absolute_max,
                    "optimal_incidence_deg": self.sar_config.mode.optimal_incidence_deg,
                },
                "mission_input": {
                    "imaging_mode": self.sar_config.mission_input.imaging_mode,
                    "look_side": self.sar_config.mission_input.look_side,
                    "pass_direction": self.sar_config.mission_input.pass_direction,
                    "incidence_min_deg": self.sar_config.mission_input.incidence_min_deg,
                    "incidence_max_deg": self.sar_config.mission_input.incidence_max_deg,
                },
                "effective_incidence_min": self.sar_config.effective_incidence_min,
                "effective_incidence_max": self.sar_config.effective_incidence_max,
            }

        if self.optical_config:
            result["optical_config"] = {
                "pointing_angle": self.optical_config.pointing_angle,
                "illumination_filter": self.optical_config.illumination_filter,
            }

        return result


@dataclass
class GovernanceViolation:
    """A governance rule violation."""

    field: str
    message: str
    severity: str = "error"  # "error" (reject) or "warning" (clamp/warn)
    clamped_to: Optional[Any] = None


@dataclass
class ResolveResult:
    """Result of config resolution."""

    success: bool
    config: Optional[ResolvedConfig] = None
    violations: List[GovernanceViolation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "config": self.config.to_dict() if self.config else None,
            "violations": [
                {
                    "field": v.field,
                    "message": v.message,
                    "severity": v.severity,
                    "clamped_to": v.clamped_to,
                }
                for v in self.violations
            ],
        }


# =============================================================================
# Config Resolver Class
# =============================================================================


class ConfigResolver:
    """
    Resolves mission configuration by combining:
    - Platform truth (YAML configs managed by Admin)
    - Mission inputs (per-run decisions by mission planner)

    Enforces parameter governance rules as defined in PARAMETER_GOVERNANCE_MATRIX.md
    """

    # Parameters that are ADMIN ONLY - reject if sent via mission input
    ADMIN_ONLY_PARAMS = frozenset(
        [
            "max_roll_rate_dps",
            "max_roll_accel_dps2",
            "max_pitch_rate_dps",
            "max_pitch_accel_dps2",
            "settling_time_s",
            "sensor_fov_half_angle_deg",
            "max_spacecraft_roll_deg",
            "max_spacecraft_pitch_deg",
            "satellite_agility",
            "min_sun_elevation_deg",
            "max_cloud_cover_percent",
        ]
    )

    def __init__(self) -> None:
        self._satellites_config: Dict[str, Any] = {}
        self._sar_modes_config: Dict[str, Any] = {}
        self._ground_stations_config: Dict[str, Any] = {}
        self._mission_settings_config: Dict[str, Any] = {}
        self._config_hash: str = ""
        self._loaded = False

    def load_configs(self, force_reload: bool = False) -> None:
        """Load all YAML configuration files."""
        if self._loaded and not force_reload:
            return

        try:
            # Load satellites.yaml
            satellites_path = CONFIG_DIR / "satellites.yaml"
            if satellites_path.exists():
                with open(satellites_path, "r") as f:
                    self._satellites_config = yaml.safe_load(f) or {}

            # Load sar_modes.yaml
            sar_modes_path = CONFIG_DIR / "sar_modes.yaml"
            if sar_modes_path.exists():
                with open(sar_modes_path, "r") as f:
                    self._sar_modes_config = yaml.safe_load(f) or {}

            # Load ground_stations.yaml
            gs_path = CONFIG_DIR / "ground_stations.yaml"
            if gs_path.exists():
                with open(gs_path, "r") as f:
                    self._ground_stations_config = yaml.safe_load(f) or {}

            # Load mission_settings.yaml
            ms_path = CONFIG_DIR / "mission_settings.yaml"
            if ms_path.exists():
                with open(ms_path, "r") as f:
                    self._mission_settings_config = yaml.safe_load(f) or {}

            # Calculate config hash
            self._config_hash = self._calculate_hash()
            self._loaded = True

            logger.info(f"ConfigResolver loaded configs. Hash: {self._config_hash}")

        except Exception as e:
            logger.error(f"Error loading configs: {e}")
            raise

    def _calculate_hash(self) -> str:
        """Calculate SHA256 hash of all config files."""
        combined = ""
        for filename in [
            "satellites.yaml",
            "sar_modes.yaml",
            "ground_stations.yaml",
            "mission_settings.yaml",
        ]:
            filepath = CONFIG_DIR / filename
            if filepath.exists():
                combined += filepath.read_text()
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def get_config_hash(self) -> str:
        """Get current config hash."""
        self.load_configs()
        return self._config_hash

    def get_config_snapshot(self) -> Dict[str, Any]:
        """Get snapshot of current config for workspace storage."""
        self.load_configs()
        return {
            "config_hash": self._config_hash,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "satellites": self._satellites_config.get("satellites", []),
            "satellite_settings": self._satellites_config.get("satellite_settings", {}),
            "sar_modes": self._sar_modes_config.get("modes", {}),
            "ground_stations": self._ground_stations_config.get("ground_stations", []),
        }

    def resolve(
        self,
        mission_input: Dict[str, Any],
        satellite_ids: List[str],
        clamp_on_warning: bool = True,
    ) -> ResolveResult:
        """
        Resolve configuration for a mission run.

        Args:
            mission_input: Mission parameters from frontend
            satellite_ids: List of satellite IDs to use
            clamp_on_warning: If True, clamp out-of-bounds values with warning.
                            If False, reject out-of-bounds values as error.

        Returns:
            ResolveResult with resolved config or violations
        """
        self.load_configs()

        violations: List[GovernanceViolation] = []
        warnings: List[str] = []
        clamped_values: Dict[str, Any] = {}

        # Step 1: Check for admin-only parameter overrides
        admin_violations = self._check_admin_only_overrides(mission_input)
        violations.extend(admin_violations)

        # If there are admin-only violations, fail immediately
        if any(v.severity == "error" for v in violations):
            return ResolveResult(success=False, violations=violations)

        # Step 2: Resolve satellite configurations
        resolved_satellites, sat_violations = self._resolve_satellites(satellite_ids)
        violations.extend(sat_violations)

        if any(v.severity == "error" for v in sat_violations):
            return ResolveResult(success=False, violations=violations)

        # Step 3: Resolve imaging type and type-specific config
        imaging_type = mission_input.get("imagingType", "optical")
        sar_config = None
        optical_config = None

        if imaging_type == "sar":
            sar_config, sar_violations = self._resolve_sar_config(
                mission_input, resolved_satellites, clamp_on_warning
            )
            violations.extend(sar_violations)

            # Collect warnings and clamped values
            for v in sar_violations:
                if v.severity == "warning":
                    warnings.append(v.message)
                    if v.clamped_to is not None:
                        clamped_values[v.field] = v.clamped_to
        else:
            optical_config, optical_violations = self._resolve_optical_config(
                mission_input, resolved_satellites, clamp_on_warning
            )
            violations.extend(optical_violations)

            for v in optical_violations:
                if v.severity == "warning":
                    warnings.append(v.message)
                    if v.clamped_to is not None:
                        clamped_values[v.field] = v.clamped_to

        # Check for errors
        if any(v.severity == "error" for v in violations):
            return ResolveResult(success=False, violations=violations)

        # Step 4: Build resolved config
        resolved_config = ResolvedConfig(
            config_hash=self._config_hash,
            resolved_at=datetime.utcnow().isoformat() + "Z",
            start_time=mission_input.get("startTime", ""),
            end_time=mission_input.get("endTime", ""),
            targets=mission_input.get("targets", []),
            satellites=resolved_satellites,
            sar_config=sar_config,
            optical_config=optical_config,
            warnings=warnings,
            clamped_values=clamped_values,
        )

        return ResolveResult(
            success=True, config=resolved_config, violations=violations
        )

    def _check_admin_only_overrides(
        self, mission_input: Dict[str, Any]
    ) -> List[GovernanceViolation]:
        """Check for forbidden admin-only parameter overrides."""
        violations = []

        # Check top-level params
        for param in self.ADMIN_ONLY_PARAMS:
            if param in mission_input:
                # Allow if explicit override flag is set (for advanced users)
                if not mission_input.get("allow_bus_override", False):
                    violations.append(
                        GovernanceViolation(
                            field=param,
                            message=f"Parameter '{param}' is admin-only and cannot be set via mission input. "
                            f"Configure this in Admin Panel → Satellites or Settings.",
                            severity="error",
                        )
                    )

        return violations

    def _resolve_satellites(
        self, satellite_ids: List[str]
    ) -> Tuple[List[ResolvedSatelliteConfig], List[GovernanceViolation]]:
        """Resolve satellite configurations from YAML."""
        violations = []
        resolved = []

        satellites_list = self._satellites_config.get("satellites", [])
        satellite_settings = self._satellites_config.get("satellite_settings", {})

        # Index satellites by ID
        sat_by_id = {
            sat.get("id", sat.get("name", "").lower().replace(" ", "-")): sat
            for sat in satellites_list
        }

        for sat_id in satellite_ids:
            sat_data = sat_by_id.get(sat_id)
            if not sat_data:
                violations.append(
                    GovernanceViolation(
                        field="satellites",
                        message=f"Satellite '{sat_id}' not found in configuration.",
                        severity="error",
                    )
                )
                continue

            # Get imaging type and corresponding defaults
            imaging_type = sat_data.get("imaging_type", "optical")
            type_settings = satellite_settings.get(imaging_type, {})
            spacecraft_defaults = type_settings.get("spacecraft", {})
            sensor_defaults = type_settings.get("sensor", {})

            # Build bus config from satellite data + defaults
            bus = SpacecraftBusConfig(
                max_spacecraft_roll_deg=sat_data.get(
                    "max_spacecraft_roll_deg",
                    spacecraft_defaults.get("max_spacecraft_roll_deg", 45.0),
                ),
                max_roll_rate_dps=sat_data.get(
                    "max_roll_rate_dps",
                    spacecraft_defaults.get("max_roll_rate_dps", 1.0),
                ),
                max_roll_accel_dps2=sat_data.get(
                    "max_roll_accel_dps2",
                    spacecraft_defaults.get("max_roll_accel_dps2", 1.0),
                ),
                max_spacecraft_pitch_deg=sat_data.get(
                    "max_spacecraft_pitch_deg",
                    spacecraft_defaults.get("max_spacecraft_pitch_deg", 0.0),
                ),
                max_pitch_rate_dps=sat_data.get(
                    "max_pitch_rate_dps",
                    spacecraft_defaults.get("max_pitch_rate_dps", 0.0),
                ),
                max_pitch_accel_dps2=sat_data.get(
                    "max_pitch_accel_dps2",
                    spacecraft_defaults.get("max_pitch_accel_dps2", 0.0),
                ),
                settling_time_s=sat_data.get(
                    "settling_time_s", spacecraft_defaults.get("settling_time_s", 5.0)
                ),
                satellite_agility=sat_data.get(
                    "satellite_agility",
                    type_settings.get("default_agility_deg_per_sec", 1.0),
                ),
            )

            # Build sensor config
            sensor = SensorConfig(
                sensor_fov_half_angle_deg=sat_data.get(
                    "sensor_fov_half_angle_deg",
                    sensor_defaults.get(
                        "sensor_fov_half_angle_deg",
                        1.0 if imaging_type == "optical" else 30.0,
                    ),
                ),
                imaging_type=imaging_type,
                min_sun_elevation_deg=sensor_defaults.get("min_sun_elevation_deg", 0.0),
                max_cloud_cover_percent=sensor_defaults.get(
                    "max_cloud_cover_percent", 100.0
                ),
            )

            # Determine supported SAR modes
            supported_sar_modes = []
            if imaging_type == "sar" or "sar" in sat_data.get("capabilities", []):
                # All SAR satellites support all modes by default
                supported_sar_modes = list(
                    self._sar_modes_config.get("modes", {}).keys()
                )

            resolved.append(
                ResolvedSatelliteConfig(
                    id=sat_id,
                    name=sat_data.get("name", sat_id),
                    tle_line1=sat_data.get("line1", ""),
                    tle_line2=sat_data.get("line2", ""),
                    imaging_type=imaging_type,
                    bus=bus,
                    sensor=sensor,
                    supported_sar_modes=supported_sar_modes,
                )
            )

        return resolved, violations

    def _resolve_sar_config(
        self,
        mission_input: Dict[str, Any],
        satellites: List[ResolvedSatelliteConfig],
        clamp_on_warning: bool,
    ) -> Tuple[Optional[ResolvedSARConfig], List[GovernanceViolation]]:
        """Resolve SAR-specific configuration."""
        violations = []
        sar_input = mission_input.get("sar", {})

        # Get SAR mission input
        imaging_mode = sar_input.get("imaging_mode", "strip")
        look_side = sar_input.get("look_side", "ANY")
        pass_direction = sar_input.get("pass_direction", "ANY")
        user_inc_min = sar_input.get("incidence_min_deg")
        user_inc_max = sar_input.get("incidence_max_deg")

        # Validate imaging mode exists
        modes = self._sar_modes_config.get("modes", {})
        if imaging_mode not in modes:
            violations.append(
                GovernanceViolation(
                    field="sar.imaging_mode",
                    message=f"SAR mode '{imaging_mode}' not found. Valid modes: {list(modes.keys())}",
                    severity="error",
                )
            )
            return None, violations

        mode_data = modes[imaging_mode]
        incidence = mode_data.get("incidence_angle", {})

        # Build mode config
        mode_config = SARModeConfig(
            display_name=mode_data.get("display_name", imaging_mode),
            description=mode_data.get("description", ""),
            incidence_recommended_min=incidence.get("recommended_min", 15.0),
            incidence_recommended_max=incidence.get("recommended_max", 45.0),
            incidence_absolute_min=incidence.get("absolute_min", 10.0),
            incidence_absolute_max=incidence.get("absolute_max", 55.0),
            scene_width_km=mode_data.get("scene", {}).get("width_km", 30.0),
            scene_length_km=mode_data.get("scene", {}).get("length_km", 50.0),
            collection_duration_s=mode_data.get("collection", {}).get("duration_s"),
            optimal_incidence_deg=mode_data.get("quality", {}).get(
                "optimal_incidence_deg", 30.0
            ),
            quality_model=mode_data.get("quality", {}).get("quality_model", "band"),
        )

        # Check mode supported by satellites
        for sat in satellites:
            if sat.imaging_type != "sar" and "sar" not in sat.supported_sar_modes:
                violations.append(
                    GovernanceViolation(
                        field="satellites",
                        message=f"Satellite '{sat.name}' is not a SAR satellite. SAR configuration will be ignored.",
                        severity="warning",
                    )
                )

        # Validate and clamp incidence overrides
        effective_min = mode_config.incidence_recommended_min
        effective_max = mode_config.incidence_recommended_max

        if user_inc_min is not None:
            if user_inc_min < mode_config.incidence_absolute_min:
                if clamp_on_warning:
                    violations.append(
                        GovernanceViolation(
                            field="sar.incidence_min_deg",
                            message=f"Incidence min {user_inc_min}° below absolute min {mode_config.incidence_absolute_min}°. Clamped.",
                            severity="warning",
                            clamped_to=mode_config.incidence_absolute_min,
                        )
                    )
                    effective_min = mode_config.incidence_absolute_min
                else:
                    violations.append(
                        GovernanceViolation(
                            field="sar.incidence_min_deg",
                            message=f"Incidence min {user_inc_min}° below absolute min {mode_config.incidence_absolute_min}°.",
                            severity="error",
                        )
                    )
            elif user_inc_min < mode_config.incidence_recommended_min:
                violations.append(
                    GovernanceViolation(
                        field="sar.incidence_min_deg",
                        message=f"Incidence min {user_inc_min}° below recommended min {mode_config.incidence_recommended_min}°. Quality may be degraded.",
                        severity="warning",
                    )
                )
                effective_min = user_inc_min
            else:
                effective_min = user_inc_min

        if user_inc_max is not None:
            if user_inc_max > mode_config.incidence_absolute_max:
                if clamp_on_warning:
                    violations.append(
                        GovernanceViolation(
                            field="sar.incidence_max_deg",
                            message=f"Incidence max {user_inc_max}° above absolute max {mode_config.incidence_absolute_max}°. Clamped.",
                            severity="warning",
                            clamped_to=mode_config.incidence_absolute_max,
                        )
                    )
                    effective_max = mode_config.incidence_absolute_max
                else:
                    violations.append(
                        GovernanceViolation(
                            field="sar.incidence_max_deg",
                            message=f"Incidence max {user_inc_max}° above absolute max {mode_config.incidence_absolute_max}°.",
                            severity="error",
                        )
                    )
            elif user_inc_max > mode_config.incidence_recommended_max:
                violations.append(
                    GovernanceViolation(
                        field="sar.incidence_max_deg",
                        message=f"Incidence max {user_inc_max}° above recommended max {mode_config.incidence_recommended_max}°. Quality may be degraded.",
                        severity="warning",
                    )
                )
                effective_max = user_inc_max
            else:
                effective_max = user_inc_max

        # Validate min < max
        if effective_min >= effective_max:
            violations.append(
                GovernanceViolation(
                    field="sar.incidence_range",
                    message=f"Incidence min ({effective_min}°) must be less than max ({effective_max}°).",
                    severity="error",
                )
            )

        # Validate look_side and pass_direction
        valid_look_sides = self._sar_modes_config.get("look_side", {}).get(
            "options", ["LEFT", "RIGHT", "ANY"]
        )
        if look_side not in valid_look_sides:
            violations.append(
                GovernanceViolation(
                    field="sar.look_side",
                    message=f"Invalid look side '{look_side}'. Valid options: {valid_look_sides}",
                    severity="error",
                )
            )

        valid_pass_dirs = self._sar_modes_config.get("pass_direction", {}).get(
            "options", ["ASCENDING", "DESCENDING", "ANY"]
        )
        # Normalize to uppercase
        pass_direction = pass_direction.upper()
        # Handle shorthand
        if pass_direction == "ASC":
            pass_direction = "ASCENDING"
        elif pass_direction == "DESC":
            pass_direction = "DESCENDING"

        if pass_direction not in valid_pass_dirs:
            violations.append(
                GovernanceViolation(
                    field="sar.pass_direction",
                    message=f"Invalid pass direction '{pass_direction}'. Valid options: {valid_pass_dirs}",
                    severity="error",
                )
            )

        mission_sar_input = SARMissionInput(
            imaging_mode=imaging_mode,
            look_side=look_side,
            pass_direction=pass_direction,
            incidence_min_deg=user_inc_min,
            incidence_max_deg=user_inc_max,
        )

        sar_config = ResolvedSARConfig(
            mode=mode_config,
            mission_input=mission_sar_input,
            effective_incidence_min=effective_min,
            effective_incidence_max=effective_max,
        )

        return sar_config, violations

    def _resolve_optical_config(
        self,
        mission_input: Dict[str, Any],
        satellites: List[ResolvedSatelliteConfig],
        clamp_on_warning: bool,
    ) -> Tuple[Optional[OpticalMissionInput], List[GovernanceViolation]]:
        """Resolve optical-specific configuration."""
        violations = []

        pointing_angle = mission_input.get("pointingAngle", 45.0)
        illumination_filter = mission_input.get("illumination_filter", True)

        # Validate pointing angle against satellite bus limits
        effective_pointing = pointing_angle
        for sat in satellites:
            max_roll = sat.bus.max_spacecraft_roll_deg
            if pointing_angle > max_roll:
                if clamp_on_warning:
                    violations.append(
                        GovernanceViolation(
                            field="pointingAngle",
                            message=f"Pointing angle {pointing_angle}° exceeds satellite '{sat.name}' max roll {max_roll}°. Clamped.",
                            severity="warning",
                            clamped_to=max_roll,
                        )
                    )
                    effective_pointing = min(effective_pointing, max_roll)
                else:
                    violations.append(
                        GovernanceViolation(
                            field="pointingAngle",
                            message=f"Pointing angle {pointing_angle}° exceeds satellite '{sat.name}' max roll {max_roll}°.",
                            severity="error",
                        )
                    )

        optical_config = OpticalMissionInput(
            pointing_angle=effective_pointing,
            illumination_filter=illumination_filter,
        )

        return optical_config, violations

    def get_sar_modes(self) -> Dict[str, Any]:
        """Get available SAR modes."""
        self.load_configs()
        modes = self._sar_modes_config.get("modes", {})
        return dict(modes) if modes else {}

    def get_satellite_info(self, satellite_id: str) -> Optional[Dict[str, Any]]:
        """Get satellite information including bus and sensor specs."""
        self.load_configs()
        satellites_list = self._satellites_config.get("satellites", [])
        for sat in satellites_list:
            if sat.get("id") == satellite_id:
                return dict(sat)
        return None


# =============================================================================
# Module-level singleton
# =============================================================================

_resolver: Optional[ConfigResolver] = None


def get_config_resolver() -> ConfigResolver:
    """Get or create the config resolver singleton."""
    global _resolver
    if _resolver is None:
        _resolver = ConfigResolver()
    return _resolver


def resolve_mission_config(
    mission_input: Dict[str, Any],
    satellite_ids: List[str],
    clamp_on_warning: bool = True,
) -> ResolveResult:
    """
    Resolve mission configuration.

    This is the main entry point for config resolution.
    """
    resolver = get_config_resolver()
    return resolver.resolve(mission_input, satellite_ids, clamp_on_warning)


def get_config_hash() -> str:
    """Get current config hash."""
    return get_config_resolver().get_config_hash()


def get_config_snapshot() -> Dict[str, Any]:
    """Get config snapshot for workspace storage."""
    return get_config_resolver().get_config_snapshot()


def reload_config() -> None:
    """Reload configuration from YAML files."""
    get_config_resolver().load_configs(force_reload=True)
