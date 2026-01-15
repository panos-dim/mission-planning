"""
Ground target definitions and management.

This module provides classes for defining and managing ground targets
for satellite visibility calculations.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class GroundTarget:
    """
    Represents a ground target for satellite visibility analysis.
    
    A ground target is a specific location on Earth's surface with
    associated parameters for visibility calculations.
    
    MIGRATION NOTE:
    - OLD: pointing_angle (DEPRECATED - conflated sensor FOV with spacecraft limit)
    - NEW: sensor_fov_half_angle_deg (sensor payload FOV half-angle)
    - Spacecraft agility limits are now in SpacecraftConfig (see mission_config.py)
    """
    
    name: str
    latitude: float  # degrees, -90 to +90
    longitude: float  # degrees, -180 to +180
    elevation_mask: float = 10.0  # minimum elevation angle in degrees
    altitude: float = 0.0  # altitude above sea level in meters
    mission_type: str = 'imaging'  # 'communication' or 'imaging'
    
    # Sensor FOV (for visualization/imaging)
    sensor_fov_half_angle_deg: Optional[float] = None  # Sensor FOV half-angle (degrees)
    
    # Spacecraft agility limit (for visibility analysis)
    max_spacecraft_roll: Optional[float] = None  # Max spacecraft roll angle (degrees)
    
    description: Optional[str] = None
    priority: int = 1  # Target priority (1-5) for scheduling
    color: Optional[str] = None  # Marker color (hex format, e.g., '#EF4444')
    
    def __post_init__(self) -> None:
        """Validate target parameters after initialization."""
        self._validate_coordinates()
        self._validate_elevation_mask()
        self._validate_mission_type()
        self._handle_deprecated_fields()
        self._validate_sensor_fov()
    
    def _handle_deprecated_fields(self) -> None:
        """Handle defaults for sensor FOV and spacecraft roll."""
        # Set sensor FOV default if not specified
        if self.sensor_fov_half_angle_deg is None:
            if self.mission_type == 'imaging':
                # Default based on imaging type: optical=1° (high-res), SAR=30° (wide-swath)
                imaging_type = getattr(self, 'imaging_type', 'optical')
                if imaging_type == 'optical':
                    self.sensor_fov_half_angle_deg = 1.0  # Realistic for WorldView-3/4, SkySat
                else:
                    self.sensor_fov_half_angle_deg = 30.0  # SAR default
                logger.info(
                    f"GroundTarget '{self.name}': No sensor_fov_half_angle_deg specified. "
                    f"Using default {self.sensor_fov_half_angle_deg}° for {imaging_type} {self.mission_type} mission."
                )
        
        # Set max_spacecraft_roll default if not specified
        if self.max_spacecraft_roll is None:
            if self.mission_type == 'imaging':
                self.max_spacecraft_roll = 45.0  # Standard agile satellite
                logger.info(
                    f"GroundTarget '{self.name}': No max_spacecraft_roll specified. "
                    f"Using default {self.max_spacecraft_roll}° for visibility analysis."
                )
    
    def _validate_sensor_fov(self) -> None:
        """Validate sensor FOV value."""
        if self.sensor_fov_half_angle_deg is not None:
            if not 0 < self.sensor_fov_half_angle_deg <= 90:
                raise ValueError(
                    f"Invalid sensor_fov_half_angle_deg: {self.sensor_fov_half_angle_deg}. "
                    f"Must be between 0 and 90 degrees."
                )
    
    def _validate_coordinates(self) -> None:
        """Validate latitude and longitude values."""
        if not -90 <= self.latitude <= 90:
            raise ValueError(f"Invalid latitude: {self.latitude}. Must be between -90 and 90 degrees.")
        
        if not -180 <= self.longitude <= 180:
            raise ValueError(f"Invalid longitude: {self.longitude}. Must be between -180 and 180 degrees.")
    
    def _validate_elevation_mask(self) -> None:
        """Validate elevation mask value."""
        if not 0 <= self.elevation_mask <= 90:
            raise ValueError(f"Invalid elevation mask: {self.elevation_mask}. Must be between 0 and 90 degrees.")
    
    def _validate_mission_type(self) -> None:
        """Validate mission type value."""
        valid_types = ['communication', 'imaging']
        if self.mission_type not in valid_types:
            raise ValueError(f"Invalid mission type: {self.mission_type}. Must be one of {valid_types}.")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert target to dictionary representation."""
        result = {
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation_mask": self.elevation_mask,
            "altitude": self.altitude,
            "mission_type": self.mission_type,
            "sensor_fov_half_angle_deg": self.sensor_fov_half_angle_deg,
            "description": self.description,
            "max_spacecraft_roll": self.max_spacecraft_roll
        }
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GroundTarget":
        """Create GroundTarget from dictionary."""
        return cls(**data)
    
    def distance_to(self, other: "GroundTarget") -> float:
        """
        Calculate great circle distance to another target.
        
        Args:
            other: Another GroundTarget
            
        Returns:
            Distance in kilometers
        """
        # Convert to radians
        lat1, lon1 = np.radians(self.latitude), np.radians(self.longitude)
        lat2, lon2 = np.radians(other.latitude), np.radians(other.longitude)
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        
        # Earth's radius in km
        earth_radius = 6371.0
        return earth_radius * c
    
    def __str__(self) -> str:
        """String representation of the target."""
        return f"{self.name} ({self.latitude:.4f}°, {self.longitude:.4f}°)"
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"GroundTarget(name='{self.name}', "
                f"lat={self.latitude:.4f}, lon={self.longitude:.4f}, "
                f"elevation_mask={self.elevation_mask}°)")


class TargetManager:
    """
    Manages collections of ground targets.
    
    Provides functionality to load, save, and manage multiple ground targets
    for mission planning operations.
    """
    
    def __init__(self, targets: Optional[List[GroundTarget]] = None) -> None:
        """
        Initialize target manager.
        
        Args:
            targets: Optional list of initial targets
        """
        self.targets: List[GroundTarget] = targets or []
        logger.info(f"Initialized TargetManager with {len(self.targets)} targets")
    
    def add_target(self, target: GroundTarget) -> None:
        """
        Add a target to the collection.
        
        Args:
            target: GroundTarget to add
        """
        if not isinstance(target, GroundTarget):
            raise TypeError("Target must be a GroundTarget instance")
        
        # Check for duplicate names
        existing_names = [t.name for t in self.targets]
        if target.name in existing_names:
            logger.warning(f"Target with name '{target.name}' already exists. Adding anyway.")
        
        self.targets.append(target)
        logger.info(f"Added target: {target}")
    
    def remove_target(self, name: str) -> bool:
        """
        Remove a target by name.
        
        Args:
            name: Name of target to remove
            
        Returns:
            True if target was removed, False if not found
        """
        for i, target in enumerate(self.targets):
            if target.name == name:
                removed_target = self.targets.pop(i)
                logger.info(f"Removed target: {removed_target}")
                return True
        
        logger.warning(f"Target '{name}' not found for removal")
        return False
    
    def get_target(self, name: str) -> Optional[GroundTarget]:
        """
        Get a target by name.
        
        Args:
            name: Name of target to retrieve
            
        Returns:
            GroundTarget if found, None otherwise
        """
        for target in self.targets:
            if target.name == name:
                return target
        return None
    
    def get_targets_in_region(
        self, 
        center_lat: float, 
        center_lon: float, 
        radius_km: float
    ) -> List[GroundTarget]:
        """
        Get all targets within a specified radius of a center point.
        
        Args:
            center_lat: Center latitude in degrees
            center_lon: Center longitude in degrees
            radius_km: Radius in kilometers
            
        Returns:
            List of targets within the specified region
        """
        center_target = GroundTarget("center", center_lat, center_lon)
        nearby_targets = []
        
        for target in self.targets:
            distance = target.distance_to(center_target)
            if distance <= radius_km:
                nearby_targets.append(target)
        
        logger.info(f"Found {len(nearby_targets)} targets within {radius_km}km of "
                   f"({center_lat:.4f}, {center_lon:.4f})")
        return nearby_targets
    
    def save_to_file(self, file_path: str) -> None:
        """
        Save targets to JSON file.
        
        Args:
            file_path: Path to save file
        """
        try:
            targets_data = [target.to_dict() for target in self.targets]
            
            with open(file_path, 'w') as f:
                json.dump({
                    "targets": targets_data,
                    "count": len(targets_data)
                }, f, indent=2)
            
            logger.info(f"Saved {len(self.targets)} targets to {file_path}")
            
        except Exception as e:
            logger.error(f"Error saving targets to {file_path}: {e}")
            raise
    
    @classmethod
    def load_from_file(cls, file_path: str) -> "TargetManager":
        """
        Load targets from JSON file.
        
        Args:
            file_path: Path to load file
            
        Returns:
            TargetManager instance with loaded targets
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            targets = [GroundTarget.from_dict(target_data) 
                      for target_data in data.get("targets", [])]
            
            logger.info(f"Loaded {len(targets)} targets from {file_path}")
            return cls(targets)
            
        except Exception as e:
            logger.error(f"Error loading targets from {file_path}: {e}")
            raise
    
    def create_predefined_targets(self) -> None:
        """Add some common predefined targets for testing and examples."""
        predefined = [
            GroundTarget(
                name="Houston Mission Control",
                latitude=29.5586,
                longitude=-95.0964,
                elevation_mask=10.0,
                description="NASA Johnson Space Center"
            ),
            GroundTarget(
                name="Moscow Mission Control",
                latitude=55.9286,
                longitude=38.1420,
                elevation_mask=10.0,
                description="Roscosmos Mission Control Center"
            ),
            GroundTarget(
                name="ESA Darmstadt",
                latitude=49.8728,
                longitude=8.6512,
                elevation_mask=10.0,
                description="European Space Operations Centre"
            ),
            GroundTarget(
                name="Tokyo",
                latitude=35.6762,
                longitude=139.6503,
                elevation_mask=15.0,
                description="Tokyo, Japan"
            ),
            GroundTarget(
                name="Sydney",
                latitude=-33.8688,
                longitude=151.2093,
                elevation_mask=10.0,
                description="Sydney, Australia"
            )
        ]
        
        for target in predefined:
            self.add_target(target)
        
        logger.info("Added predefined targets")
    
    def __len__(self) -> int:
        """Return number of targets."""
        return len(self.targets)
    
    def __iter__(self):
        """Make the manager iterable."""
        return iter(self.targets)
    
    def __repr__(self) -> str:
        """String representation of the target manager."""
        return f"TargetManager({len(self.targets)} targets)"
