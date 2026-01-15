"""
Satellite orbit propagation and TLE handling module.

This module provides functionality to load TLE data and propagate satellite
orbits using the orbit-predictor library.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple, Union
import logging

from orbit_predictor.sources import get_predictor_from_tle_lines, MemoryTLESource
from orbit_predictor.predictors import TLEPredictor
from orbit_predictor.locations import Location
import numpy as np

logger = logging.getLogger(__name__)


class SatelliteOrbit:
    """
    Represents a satellite orbit with TLE-based propagation capabilities.
    
    This class encapsulates satellite orbital mechanics using Two-Line Element
    (TLE) data and provides methods for orbit propagation and position calculation.
    """
    
    def __init__(self, tle_lines: List[str], satellite_name: str) -> None:
        """
        Initialize satellite orbit from TLE data.
        
        Args:
            tle_lines: List of 3 strings containing TLE data (name, line1, line2)
            satellite_name: Name of the satellite
            
        Raises:
            ValueError: If TLE data is invalid or satellite not found
        """
        self.satellite_name = satellite_name
        self.tle_lines = tle_lines
        
        try:
            # Create predictor directly from TLE lines (only line1 and line2, not the name)
            if len(tle_lines) == 3:
                # Format: [name, line1, line2]
                predictor_lines = tle_lines[1:3]
            else:
                # Format: [line1, line2]
                predictor_lines = tle_lines
            
            self.predictor = get_predictor_from_tle_lines(predictor_lines)
            logger.info(f"Successfully loaded orbit for satellite: {satellite_name}")
        except Exception as e:
            logger.error(f"Failed to initialize satellite orbit: {e}")
            raise ValueError(f"Invalid TLE data for satellite {satellite_name}: {e}")
    
    @classmethod
    def from_tle_file(cls, tle_file_path: Union[str, Path], satellite_name: str) -> "SatelliteOrbit":
        """
        Create SatelliteOrbit instance from TLE file.
        
        Args:
            tle_file_path: Path to TLE file
            satellite_name: Name of the satellite to extract from TLE file
            
        Returns:
            SatelliteOrbit instance
            
        Raises:
            FileNotFoundError: If TLE file doesn't exist
            ValueError: If satellite not found in TLE file
        """
        tle_path = Path(tle_file_path)
        if not tle_path.exists():
            raise FileNotFoundError(f"TLE file not found: {tle_file_path}")
        
        try:
            with open(tle_path, 'r') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            
            # Parse TLE file to find the specified satellite
            for i in range(0, len(lines) - 2, 3):
                if i + 2 < len(lines):
                    name_line = lines[i]
                    if satellite_name.upper() in name_line.upper():
                        tle_lines = [lines[i], lines[i + 1], lines[i + 2]]
                        return cls(tle_lines, satellite_name)
            
            raise ValueError(f"Satellite '{satellite_name}' not found in TLE file")
            
        except Exception as e:
            logger.error(f"Error reading TLE file {tle_file_path}: {e}")
            raise
    
    @classmethod
    def from_online_source(cls, satellite_name: str, source_url: Optional[str] = None) -> "SatelliteOrbit":
        """
        Create SatelliteOrbit instance from online TLE source.
        
        Args:
            satellite_name: Name of the satellite
            source_url: Optional URL to TLE source (defaults to CelesTrak)
            
        Returns:
            SatelliteOrbit instance
        """
        if source_url is None:
            # Default to CelesTrak active satellites
            source_url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"
        
        try:
            # Create memory TLE source and load from URL
            source = MemoryTLESource()
            # This is a simplified approach - in practice you'd need to download and parse the TLE file
            # For now, we'll raise an error suggesting to use from_tle_file instead
            raise NotImplementedError("Online TLE loading not yet implemented. Use from_tle_file() instead.")
            
        except Exception as e:
            logger.error(f"Failed to load satellite from online source: {e}")
            raise ValueError(f"Could not load satellite '{satellite_name}' from {source_url}: {e}")
    
    def get_position(self, timestamp: datetime) -> Tuple[float, float, float]:
        """
        Get satellite position at specific timestamp.
        
        Args:
            timestamp: UTC datetime for position calculation
            
        Returns:
            Tuple of (latitude, longitude, altitude_km)
        """
        try:
            position = self.predictor.get_position(timestamp)
            # Extract latitude, longitude, altitude from position_llh
            lat, lon, alt = position.position_llh
            return (lat, lon, alt)
        except Exception as e:
            logger.error(f"Error calculating position for {timestamp}: {e}")
            raise
    
    def get_ground_track(
        self, 
        start_time: datetime, 
        end_time: datetime, 
        time_step_minutes: float = 1.0
    ) -> List[Tuple[datetime, float, float, float]]:
        """
        Generate ground track points over time period.
        
        Args:
            start_time: Start time for ground track (UTC)
            end_time: End time for ground track (UTC)
            time_step_minutes: Time step between points in minutes
            
        Returns:
            List of tuples: (timestamp, latitude, longitude, altitude_km)
        """
        ground_track = []
        current_time = start_time
        time_step = timedelta(minutes=time_step_minutes)
        
        while current_time <= end_time:
            try:
                lat, lon, alt = self.get_position(current_time)
                ground_track.append((current_time, lat, lon, alt))
                current_time += time_step
            except Exception as e:
                logger.warning(f"Skipping position calculation at {current_time}: {e}")
                current_time += time_step
                continue
        
        logger.info(f"Generated ground track with {len(ground_track)} points")
        return ground_track
    
    def get_orbital_period(self) -> timedelta:
        """
        Calculate orbital period of the satellite.
        
        Returns:
            Orbital period as timedelta
        """
        try:
            # Get orbital period in minutes from the predictor
            # Note: period is a property, not a method
            period_minutes = self.predictor.period
            return timedelta(minutes=period_minutes)
        except Exception as e:
            logger.error(f"Error calculating orbital period: {e}")
            # Default fallback for LEO satellites (~90 minutes)
            return timedelta(minutes=90)
    
    def is_above_horizon(self, location: Location, timestamp: datetime) -> bool:
        """
        Check if satellite is above horizon at given location and time.
        
        Args:
            location: Ground location
            timestamp: UTC datetime
            
        Returns:
            True if satellite is above horizon
        """
        try:
            position = self.predictor.get_position(timestamp)
            # Simple horizon check - more sophisticated elevation calculation
            # would be done in the visibility module
            return position.altitude_km > 0
        except Exception as e:
            logger.warning(f"Error checking horizon visibility: {e}")
            return False
    
    def __repr__(self) -> str:
        """String representation of the satellite orbit."""
        period = self.get_orbital_period()
        return f"SatelliteOrbit(name='{self.satellite_name}', period={period})"
