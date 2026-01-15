"""
Mission Settings Manager
Handles global mission configuration settings for mission planning and analysis
"""

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


@dataclass
class PassDurationSettings:
    """Pass duration constraints for different mission types"""

    min_seconds: int
    preferred_seconds: int
    max_seconds: int


@dataclass
class ElevationConstraints:
    """Elevation mask constraints for ground station visibility"""

    default_mask_deg: int
    optimal_min_deg: int
    max_useful_deg: int


@dataclass
class PlanningConstraints:
    """Mission planning constraints and limits"""

    planning_horizon_days: int
    max_passes_per_satellite: int
    min_pass_gap_minutes: int
    tle_max_age_days: int
    weather: Dict[str, Any]


@dataclass
class ResourceAllocation:
    """Resource allocation limits and constraints"""

    max_concurrent_imaging: int
    max_concurrent_communication: int
    max_concurrent_tracking: int
    max_daily_data_volume: int
    max_station_utilization: int


@dataclass
class AnalysisSettings:
    """Settings for mission analysis calculations"""

    time_step_seconds: int
    ground_sample_distance_m: int
    target_buffer_km: int
    conflict_resolution_strategy: str


@dataclass
class OutputSettings:
    """Output and visualization settings"""

    export_formats: list
    visualization: Dict[str, Any]
    reports: Dict[str, bool]


@dataclass
class PerformanceSettings:
    """System performance and optimization settings"""

    parallel_processing: bool
    max_worker_threads: int
    max_memory_usage_mb: int
    enable_calculation_cache: bool
    cache_expiry_hours: int


class MissionSettingsManager:
    """Manages global mission settings configuration"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.pass_duration: Dict[str, PassDurationSettings] = {}
        self.elevation_constraints: Dict[str, ElevationConstraints] = {}
        self.planning_constraints: Optional[PlanningConstraints] = None
        self.resource_allocation: Optional[ResourceAllocation] = None
        self.mission_priorities: Dict[str, int] = {}
        self.analysis_settings: Optional[AnalysisSettings] = None
        self.output_settings: Optional[OutputSettings] = None
        self.performance: Optional[PerformanceSettings] = None
        self.defaults: Dict[str, Any] = {}
        self._raw_config: Dict = {}

        # Load configuration on initialization
        self.load_config()

    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        backend_dir = Path(__file__).parent
        config_path = backend_dir.parent / "config" / "mission_settings.yaml"
        return str(config_path)

    def load_config(self) -> bool:
        """Load mission settings from YAML file"""
        try:
            config_path = Path(self.config_path)

            if not config_path.exists():
                logger.warning(f"Mission settings file not found: {config_path}")
                self._create_default_config()
                return False

            with open(config_path, "r", encoding="utf-8") as file:
                self._raw_config = yaml.safe_load(file) or {}

            # Parse pass duration settings
            self.pass_duration = {}
            for mission_type, settings in self._raw_config.get(
                "pass_duration", {}
            ).items():
                self.pass_duration[mission_type] = PassDurationSettings(**settings)

            # Parse elevation constraints
            self.elevation_constraints = {}
            for mission_type, settings in self._raw_config.get(
                "elevation_constraints", {}
            ).items():
                self.elevation_constraints[mission_type] = ElevationConstraints(
                    **settings
                )

            # Parse other settings
            planning_data = self._raw_config.get("planning_constraints", {})
            if planning_data:
                self.planning_constraints = PlanningConstraints(**planning_data)

            resource_data = self._raw_config.get("resource_allocation", {})
            if resource_data:
                self.resource_allocation = ResourceAllocation(**resource_data)

            analysis_data = self._raw_config.get("analysis_settings", {})
            if analysis_data:
                self.analysis_settings = AnalysisSettings(**analysis_data)

            output_data = self._raw_config.get("output_settings", {})
            if output_data:
                self.output_settings = OutputSettings(**output_data)

            performance_data = self._raw_config.get("performance", {})
            if performance_data:
                self.performance = PerformanceSettings(**performance_data)

            # Parse simple dictionaries
            self.mission_priorities = self._raw_config.get("mission_priorities", {})
            self.defaults = self._raw_config.get("defaults", {})

            logger.info(f"Loaded mission settings from {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"Error loading mission settings: {str(e)}")
            return False

    def save_config(self) -> bool:
        """Save current mission settings to YAML file"""
        try:
            config_data = {
                "pass_duration": {
                    mission_type: asdict(settings)
                    for mission_type, settings in self.pass_duration.items()
                },
                "elevation_constraints": {
                    mission_type: asdict(settings)
                    for mission_type, settings in self.elevation_constraints.items()
                },
                "mission_priorities": self.mission_priorities,
                "defaults": self.defaults,
            }

            # Add complex objects if they exist
            if self.planning_constraints:
                config_data["planning_constraints"] = asdict(self.planning_constraints)
            if self.resource_allocation:
                config_data["resource_allocation"] = asdict(self.resource_allocation)
            if self.analysis_settings:
                config_data["analysis_settings"] = asdict(self.analysis_settings)
            if self.output_settings:
                config_data["output_settings"] = asdict(self.output_settings)
            if self.performance:
                config_data["performance"] = asdict(self.performance)

            config_path = Path(self.config_path)
            config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(config_path, "w", encoding="utf-8") as file:
                yaml.dump(
                    config_data, file, default_flow_style=False, allow_unicode=True
                )

            logger.info(f"Saved mission settings to {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving mission settings: {str(e)}")
            return False

    def _create_default_config(self) -> None:
        """Create default mission settings if file doesn't exist"""
        # Set up basic defaults
        self.pass_duration = {
            "imaging": PassDurationSettings(30, 60, 300),
            "communication": PassDurationSettings(60, 120, 600),
            "tracking": PassDurationSettings(120, 180, 900),
        }

        self.elevation_constraints = {
            "imaging": ElevationConstraints(10, 20, 85),
            "communication": ElevationConstraints(10, 15, 90),
            "tracking": ElevationConstraints(5, 10, 90),
        }

        self.mission_priorities = {
            "emergency_response": 1,
            "commercial_imaging": 2,
            "scientific_research": 3,
            "routine_monitoring": 4,
            "calibration": 5,
        }

        self.defaults = {
            "mission_duration_days": 7,
            "target_revisit_hours": 24,
            "data_latency_requirements": "near_real_time",
            "mission_criticality": "routine",
        }

        self.save_config()

    def get_pass_duration(self, mission_type: str) -> Optional[PassDurationSettings]:
        """Get pass duration settings for a mission type"""
        return self.pass_duration.get(mission_type)

    def get_elevation_constraints(
        self, mission_type: str
    ) -> Optional[ElevationConstraints]:
        """Get elevation constraints for a mission type"""
        return self.elevation_constraints.get(mission_type)

    def get_mission_priority(self, mission_type: str) -> int:
        """Get priority level for a mission type (lower number = higher priority)"""
        return self.mission_priorities.get(mission_type, 99)

    def update_setting(self, section: str, key: str, value: Any) -> bool:
        """Update a specific setting in the configuration

        Args:
            section: The configuration section
            key: The setting key within the section
            value: The new value for the setting

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Handle updates to settings
            if section == "pass_duration" and key in self.pass_duration:
                if isinstance(value, dict):
                    self.pass_duration[key] = PassDurationSettings(**value)
                    return self.save_config()
            elif (
                section == "elevation_constraints" and key in self.elevation_constraints
            ):
                if isinstance(value, dict):
                    self.elevation_constraints[key] = ElevationConstraints(**value)
                    return self.save_config()
            elif section == "mission_priorities":
                self.mission_priorities[key] = value
                return self.save_config()
            elif section == "defaults":
                self.defaults[key] = value
                return self.save_config()
            elif section == "planning_constraints":
                if (
                    not hasattr(self, "planning_constraints")
                    or self.planning_constraints is None
                ):
                    self.planning_constraints = PlanningConstraints(
                        planning_horizon_days=7,
                        max_passes_per_satellite=100,
                        min_pass_gap_minutes=5,
                        tle_max_age_days=14,
                        weather={},
                    )
                setattr(self.planning_constraints, key, value)
                return self.save_config()
            elif section == "output_settings":
                if not hasattr(self, "output_settings") or self.output_settings is None:
                    self.output_settings = OutputSettings(
                        export_formats=["json", "csv"],
                        visualization={"enabled": True},
                        reports={"summary": True, "detailed": False},
                    )
                # Handle nested dict values (like reports)
                if isinstance(value, dict) and hasattr(self.output_settings, key):
                    # For nested objects, update the attribute directly
                    setattr(self.output_settings, key, value)
                else:
                    # For simple values, use setattr
                    setattr(self.output_settings, key, value)
                return self.save_config()
            elif section == "resource_allocation":
                if (
                    not hasattr(self, "resource_allocation")
                    or self.resource_allocation is None
                ):
                    self.resource_allocation = ResourceAllocation(
                        max_concurrent_imaging=5,
                        max_concurrent_communication=10,
                        max_concurrent_tracking=3,
                        max_daily_data_volume=1000,
                        max_station_utilization=90,
                    )
                self.resource_allocation.__dict__[key] = value
                return self.save_config()

            return False
        except Exception as e:
            logger.error(f"Error updating setting {section}.{key}: {str(e)}")
            return False

    def get_config_dict(self) -> Dict[str, Any]:
        """Get full configuration as dictionary"""
        config = {
            "pass_duration": {
                mission_type: asdict(settings)
                for mission_type, settings in self.pass_duration.items()
            },
            "elevation_constraints": {
                mission_type: asdict(settings)
                for mission_type, settings in self.elevation_constraints.items()
            },
            "mission_priorities": self.mission_priorities,
            "defaults": self.defaults,
        }

        # Add complex objects if they exist
        if self.planning_constraints:
            config["planning_constraints"] = asdict(self.planning_constraints)
        if self.resource_allocation:
            config["resource_allocation"] = asdict(self.resource_allocation)
        if self.analysis_settings:
            config["analysis_settings"] = asdict(self.analysis_settings)
        if self.output_settings:
            config["output_settings"] = asdict(self.output_settings)
        if self.performance:
            config["performance"] = asdict(self.performance)

        return config
