"""
Satellite Configuration Manager
Handles CRUD operations for managed satellites with persistent storage
"""

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests  # type: ignore[import-untyped]
import yaml  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


@dataclass
class Satellite:
    """Satellite configuration with TLE data and imaging parameters"""

    id: str
    name: str
    line1: str
    line2: str
    imaging_type: str = "optical"
    sensor_fov_half_angle_deg: float = 1.0  # Sensor field of view half-angle
    satellite_agility: float = 1.0
    sar_mode: str = "stripmap"
    description: str = ""
    active: bool = True
    created_at: str = ""
    tle_updated_at: str = ""
    capabilities: Optional[List[str]] = None
    orbital_characteristics: Optional[Dict[str, Any]] = None
    imaging_parameters: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.capabilities is None:
            self.capabilities = ["imaging"]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat() + "Z"
        if not self.tle_updated_at:
            self.tle_updated_at = datetime.now(timezone.utc).isoformat() + "Z"

    def to_dict(self) -> Dict:
        return asdict(self)


class SatelliteManager:
    """Manages satellite configuration with YAML persistence"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.satellites: List[Satellite] = []
        self.defaults: Dict[str, Any] = {}
        self.satellite_settings: Dict[str, Any] = {}
        self._raw_config: Dict = {}

        # Load configuration on initialization
        self.load_config()

    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        # Try relative to backend directory first
        backend_dir = Path(__file__).parent
        config_path = backend_dir.parent / "config" / "satellites.yaml"

        if not config_path.exists():
            # Try relative to project root
            project_root = backend_dir.parent
            config_path = project_root / "config" / "satellites.yaml"

        return str(config_path)

    def load_config(self) -> bool:
        """Load satellite configuration from YAML file"""
        try:
            config_path = Path(self.config_path)

            if not config_path.exists():
                logger.warning(f"Satellite config file not found: {config_path}")
                self._create_default_config()
                return False

            with open(config_path, "r", encoding="utf-8") as file:
                self._raw_config = yaml.safe_load(file) or {}

            # Parse satellites
            self.satellites = []
            for sat_data in self._raw_config.get("satellites", []):
                satellite = Satellite(**sat_data)
                if satellite.active:
                    self.satellites.append(satellite)

            # Parse defaults and satellite settings
            self.defaults = self._raw_config.get("defaults", {})
            self.satellite_settings = self._raw_config.get("satellite_settings", {})
            self.mission_settings = self._raw_config.get("mission_settings", {})

            logger.info(
                f"Loaded {len(self.satellites)} active satellites from {self.config_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Error loading satellite configuration: {str(e)}")
            return False

    def save_config(self) -> bool:
        """Save current satellite configuration to YAML file"""
        try:
            config_data = {
                "defaults": self.defaults,
                "satellite_settings": self.satellite_settings,
                "satellites": [sat.to_dict() for sat in self.satellites],
            }

            config_path = Path(self.config_path)
            config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(config_path, "w", encoding="utf-8") as file:
                yaml.dump(
                    config_data, file, default_flow_style=False, allow_unicode=True
                )

            logger.info(
                f"Saved {len(self.satellites)} satellites to {self.config_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Error saving satellite configuration: {str(e)}")
            return False

    def _create_default_config(self) -> None:
        """Create default satellite configuration if file doesn't exist"""
        self.defaults = {
            "imaging_type": "optical",
            "satellite_agility": 1.0,
            "sar_mode": "stripmap",
            "active": True,
            "capabilities": ["imaging"],
        }

        self.satellite_settings = {
            "optical": {
                "default_agility_deg_per_sec": 1.0,
                "max_slew_angle": 45,
                "settling_time_seconds": 5,
                "min_sun_elevation": 30,
                "max_cloud_cover": 20,
            },
            "sar": {
                "default_agility_deg_per_sec": 2.5,
                "max_slew_angle": 60,
                "settling_time_seconds": 3,
                "default_mode": "stripmap",
                "polarizations": ["VV", "VH", "HH", "HV"],
                "resolution_modes": ["stripmap", "spotlight", "scan"],
                "incidence_angle_range": [20, 50],
            },
        }

        self.satellites = []
        self.save_config()

    def get_satellites(self) -> List[Satellite]:
        """Get all active satellites"""
        return [sat for sat in self.satellites if sat.active]

    def get_satellite_by_id(self, satellite_id: str) -> Optional[Satellite]:
        """Get satellite by ID"""
        for sat in self.satellites:
            if sat.id == satellite_id:
                return sat
        return None

    def add_satellite(self, satellite_data: Dict[str, Any]) -> Satellite:
        """Add new satellite to configuration"""
        # Apply defaults for missing fields
        for key, default_value in self.defaults.items():
            if key not in satellite_data:
                satellite_data[key] = default_value

        # Ensure required fields
        if "id" not in satellite_data:
            satellite_data["id"] = (
                f"{satellite_data['name']}-{int(datetime.now(timezone.utc).timestamp())}"
            )

        satellite = Satellite(**satellite_data)
        self.satellites.append(satellite)
        self.save_config()

        logger.info(f"Added satellite: {satellite.name} ({satellite.id})")
        return satellite

    def update_satellite(
        self, satellite_id: str, updates: Dict[str, Any]
    ) -> Optional[Satellite]:
        """Update existing satellite"""
        for i, sat in enumerate(self.satellites):
            if sat.id == satellite_id:
                # Update satellite data
                updated_data = sat.to_dict()
                updated_data.update(updates)
                updated_satellite = Satellite(**updated_data)

                self.satellites[i] = updated_satellite
                self.save_config()

                logger.info(
                    f"Updated satellite: {updated_satellite.name} ({satellite_id})"
                )
                return updated_satellite

        return None

    def remove_satellite(self, satellite_id: str) -> bool:
        """Remove satellite from configuration"""
        for i, sat in enumerate(self.satellites):
            if sat.id == satellite_id:
                removed_satellite = self.satellites.pop(i)
                self.save_config()

                logger.info(
                    f"Removed satellite: {removed_satellite.name} ({satellite_id})"
                )
                return True

        return False

    def get_config_dict(self) -> Dict[str, Any]:
        """Get full configuration as dictionary"""
        return {
            "satellites": [sat.to_dict() for sat in self.satellites],
            "defaults": self.defaults,
            "satellite_settings": self.satellite_settings,
        }

    def refresh_satellite_tle(
        self, satellite_id: str, source_url: Optional[str] = None
    ) -> Optional[Satellite]:
        """Refresh TLE data for a specific satellite from Celestrak or other sources"""
        satellite = self.get_satellite_by_id(satellite_id)
        if not satellite:
            logger.error(f"Satellite not found: {satellite_id}")
            return None

        try:
            # If no source URL provided, try to find TLE by satellite name from common sources
            if not source_url:
                tle_data = self._fetch_tle_by_name(satellite.name)
            else:
                tle_data = self._fetch_tle_from_url(source_url, satellite.name)

            if tle_data:
                # Update satellite with new TLE data
                updates = {
                    "line1": tle_data["line1"],
                    "line2": tle_data["line2"],
                    "tle_updated_at": datetime.now(timezone.utc).isoformat() + "Z",
                }
                return self.update_satellite(satellite_id, updates)
            else:
                logger.warning(
                    f"Could not fetch updated TLE for satellite: {satellite.name}"
                )
                return None

        except Exception as e:
            logger.error(
                f"Error refreshing TLE for satellite {satellite.name}: {str(e)}"
            )
            return None

    def _fetch_tle_by_name(self, satellite_name: str) -> Optional[Dict[str, str]]:
        """Fetch TLE data by satellite name - uses fast direct name search first"""
        import time

        logger.info(f"🔍 Fetching TLE for: {satellite_name}")
        start_time = time.time()

        # Method 1: Direct name search (FASTEST - single small request)
        # Celestrak GP API supports direct name queries
        encoded_name = satellite_name.replace(" ", "%20")
        direct_url = f"https://celestrak.org/NORAD/elements/gp.php?NAME={encoded_name}&FORMAT=tle"

        try:
            response = requests.get(direct_url, timeout=10)
            if (
                response.ok
                and response.text.strip()
                and "No GP data found" not in response.text
            ):
                lines = response.text.strip().split("\n")
                if len(lines) >= 3:
                    elapsed = time.time() - start_time
                    logger.info(
                        f"✅ Found TLE via direct name search in {elapsed:.1f}s"
                    )
                    return {
                        "name": lines[0].strip(),
                        "line1": lines[1].strip(),
                        "line2": lines[2].strip(),
                    }
        except Exception as e:
            logger.debug(f"Direct name search failed: {e}")

        # Method 2: Fallback to catalog search (slower but more comprehensive)
        logger.info(f"  Direct search failed, trying catalog search...")
        from concurrent.futures import ThreadPoolExecutor, as_completed

        celestrak_sources = [
            "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle",
            "https://celestrak.org/NORAD/elements/gp.php?GROUP=resource&FORMAT=tle",
            "https://celestrak.org/NORAD/elements/gp.php?GROUP=planet&FORMAT=tle",
        ]

        def fetch_from_source(src_url: str) -> tuple[Optional[Dict[str, str]], str]:
            try:
                return self._fetch_tle_from_url(src_url, satellite_name), src_url
            except Exception:
                return None, src_url

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(fetch_from_source, url): url
                for url in celestrak_sources
            }

            for future in as_completed(futures):
                tle_data, source_url = future.result()
                if tle_data:
                    elapsed = time.time() - start_time
                    source_name = source_url.split("GROUP=")[1].split("&")[0]
                    logger.info(f"✅ Found TLE in '{source_name}' after {elapsed:.1f}s")
                    return tle_data

        elapsed = time.time() - start_time
        logger.warning(f"❌ TLE not found for {satellite_name} ({elapsed:.1f}s)")
        return None

    def _fetch_tle_from_url(
        self, url: str, satellite_name: str
    ) -> Optional[Dict[str, str]]:
        """Fetch TLE data from a specific URL"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            lines = response.text.strip().split("\n")

            # Parse TLE format (3 lines per satellite: name, line1, line2)
            for i in range(0, len(lines) - 2, 3):
                if i + 2 < len(lines):
                    name_line = lines[i].strip()
                    line1 = lines[i + 1].strip()
                    line2 = lines[i + 2].strip()

                    # Check if this is the satellite we're looking for
                    if satellite_name.upper() in name_line.upper():
                        return {"name": name_line, "line1": line1, "line2": line2}

            return None

        except Exception as e:
            logger.error(f"Error fetching TLE from {url}: {str(e)}")
            return None

    def get_tle_age_days(self, satellite_id: str) -> Optional[int]:
        """Get the age of TLE data in days"""
        satellite = self.get_satellite_by_id(satellite_id)
        if not satellite or not satellite.tle_updated_at:
            return None

        try:
            tle_date = datetime.fromisoformat(
                satellite.tle_updated_at.replace("Z", "+00:00")
            )
            current_date = datetime.now(timezone.utc).replace(tzinfo=tle_date.tzinfo)
            age = (current_date - tle_date).days
            return age
        except Exception as e:
            logger.error(
                f"Error calculating TLE age for satellite {satellite_id}: {str(e)}"
            )
            return None
