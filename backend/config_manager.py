"""
Configuration manager for legacy defaults and mission settings.

Ground station support is deprecated and intentionally ignored.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


@dataclass
class GroundStation:
    """Ground station configuration"""

    name: str
    latitude: float
    longitude: float
    altitude_km: float = 0.0
    elevation_mask: int = 10
    active: bool = True
    id: Optional[str] = None
    type: Optional[str] = "Ground Station"
    description: str = ""
    capabilities: Optional[List[str]] = None

    def __post_init__(self) -> None:
        if self.capabilities is None:
            self.capabilities = ["communication"]

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class MissionSettings:
    """Mission-specific configuration settings"""

    min_duration_seconds: int
    # For communication and tracking missions
    default_elevation_mask: Optional[int] = None
    # For imaging missions
    default_pointing_angle: Optional[int] = None
    imaging_types: Optional[Dict[str, Any]] = None
    satellite_config: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary, excluding None values"""
        data = {}
        for key, value in asdict(self).items():
            if value is not None:
                data[key] = value
        return data


class ConfigManager:
    """Manages legacy defaults and mission configuration."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.ground_stations: List[GroundStation] = []
        self.mission_settings: Dict[str, MissionSettings] = {}
        self.defaults: Dict[str, Any] = {}
        self._raw_config: Dict = {}

        # Load configuration on initialization
        self.load_config()

    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        # Try relative to backend directory first
        backend_dir = Path(__file__).parent
        config_path = backend_dir.parent / "config" / "ground_stations.yaml"

        if not config_path.exists():
            # Try relative to project root
            project_root = backend_dir.parent
            config_path = project_root / "config" / "ground_stations.yaml"

        return str(config_path)

    def load_config(self, config_path: Optional[str] = None) -> bool:
        """Load configuration from YAML file"""
        if config_path:
            self.config_path = config_path

        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"Configuration file not found: {self.config_path}")
                self._create_default_config()
                return False

            with open(self.config_path, "r") as f:
                self._raw_config = yaml.safe_load(f)

            # Ground station support is deprecated. Keep an empty list so
            # compatibility endpoints can return a stable shape without
            # affecting planning behavior.
            self.ground_stations = []
            if self._raw_config.get("ground_stations"):
                logger.info("Ground station configuration is deprecated and ignored")

            # Parse defaults
            self.defaults = self._raw_config.get("defaults", {})

            # Parse mission settings
            self.mission_settings = {}
            for mission_type, settings in self._raw_config.get(
                "mission_settings", {}
            ).items():
                # Filter out unknown fields and handle the new structure
                filtered_settings = {}
                for key, value in settings.items():
                    if key in [
                        "min_duration_seconds",
                        "default_elevation_mask",
                        "default_pointing_angle",
                        "imaging_types",
                        "satellite_config",
                    ]:
                        filtered_settings[key] = value

                # Set default min_duration_seconds if not present
                if "min_duration_seconds" not in filtered_settings:
                    filtered_settings["min_duration_seconds"] = (
                        30 if mission_type == "imaging" else 60
                    )

                self.mission_settings[mission_type] = MissionSettings(
                    **filtered_settings
                )

            logger.info("Loaded mission defaults from %s", self.config_path)
            return True

        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            return False

    def _create_default_config(self) -> None:
        """Create default configuration if file doesn't exist"""
        default_config = {
            "defaults": {
                "elevation_mask": 10,
                "altitude_km": 0,
                "active": True,
                "capabilities": ["communication"],
            },
            "mission_settings": {
                "imaging": {"default_elevation_mask": 45, "min_duration_seconds": 30},
                "communication": {
                    "default_elevation_mask": 10,
                    "min_duration_seconds": 60,
                },
            },
        }

        # Create config directory if it doesn't exist
        config_dir = os.path.dirname(self.config_path)
        os.makedirs(config_dir, exist_ok=True)

        # Write default config
        with open(self.config_path, "w") as f:
            yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Created default configuration file: {self.config_path}")
        self.load_config()

    def save_config(self, config_data: Optional[Dict[Any, Any]] = None) -> bool:
        """Save configuration to YAML file"""
        try:
            if config_data:
                self._raw_config = config_data
                # Reload to parse the new data
                with open(self.config_path, "w") as f:
                    yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
                self.load_config()
            else:
                # Save current configuration
                config_dict = self.to_dict()
                with open(self.config_path, "w") as f:
                    yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

            logger.info(f"Configuration saved to {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            return False

    def get_ground_station(self, name: str) -> Optional[GroundStation]:
        """Get ground station by name"""
        for gs in self.ground_stations:
            if gs.name == name:
                return gs
        return None

    def get_ground_stations_list(self) -> List[Dict]:
        """Ground stations are deprecated and intentionally unavailable."""
        return []

    def add_ground_station(self, gs_data: Dict) -> bool:
        """Ground stations are deprecated and cannot be added."""
        logger.warning("Ignoring deprecated add_ground_station request: %s", gs_data)
        return False

    def update_ground_station(self, name: str, gs_data: Dict) -> bool:
        """Ground stations are deprecated and cannot be updated."""
        logger.warning(
            "Ignoring deprecated update_ground_station request for %s: %s",
            name,
            gs_data,
        )
        return False

    def delete_ground_station(self, name: str) -> bool:
        """Ground stations are deprecated and cannot be deleted."""
        logger.warning("Ignoring deprecated delete_ground_station request for %s", name)
        return False

    def get_elevation_mask(
        self, gs_name: str, mission_type: Optional[str] = None
    ) -> int:
        """Get effective elevation mask. Ground station input is ignored."""
        gs_elevation = self.defaults.get("elevation_mask", 10)

        # Check if mission type has a specific elevation mask (for communication/tracking)
        if mission_type and mission_type in self.mission_settings:
            mission_settings = self.mission_settings[mission_type]
            if mission_settings.default_elevation_mask is not None:
                # Use the more restrictive elevation mask
                return max(gs_elevation, mission_settings.default_elevation_mask)

        return gs_elevation

    def get_pointing_angle(self, mission_type: str = "imaging") -> int:
        """Get default pointing angle for imaging missions"""
        if mission_type in self.mission_settings:
            mission_settings = self.mission_settings[mission_type]
            if mission_settings.default_pointing_angle is not None:
                return mission_settings.default_pointing_angle
        return 45  # Default pointing angle

    def _update_raw_config(self) -> None:
        """Update raw configuration dictionary from current state"""
        self._raw_config.pop("ground_stations", None)
        if hasattr(self, "defaults"):
            self._raw_config["defaults"] = self.defaults
        if hasattr(self, "mission_settings"):
            self._raw_config["mission_settings"] = {
                name: settings.to_dict()
                for name, settings in self.mission_settings.items()
            }

    def to_dict(self) -> Dict:
        """Convert configuration to dictionary"""
        return {
            "defaults": self.defaults,
            "mission_settings": {
                name: settings.to_dict()
                for name, settings in self.mission_settings.items()
            },
        }

    def from_dict(self, config_dict: Dict) -> bool:
        """Load configuration from dictionary"""
        try:
            self._raw_config = config_dict
            return self.save_config(config_dict)
        except Exception as e:
            logger.error(f"Error loading configuration from dict: {str(e)}")
            return False


# Global configuration manager instance
config_manager = ConfigManager()


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance"""
    return config_manager


def reload_config(config_path: Optional[str] = None) -> bool:
    """Reload configuration from file"""
    global config_manager
    return config_manager.load_config(config_path)
