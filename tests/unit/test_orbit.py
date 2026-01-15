"""
Tests for the orbit module.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mission_planner.orbit import SatelliteOrbit
from mission_planner.utils import create_sample_tle_file


class TestSatelliteOrbit:
    """Test cases for SatelliteOrbit class."""
    
    @pytest.fixture
    def sample_tle_file(self):
        """Create a temporary TLE file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tle', delete=False) as f:
            create_sample_tle_file(f.name)
            return f.name
    
    @pytest.fixture
    def sample_satellite(self, sample_tle_file):
        """Create a sample satellite for testing."""
        return SatelliteOrbit.from_tle_file(sample_tle_file, "ISS (ZARYA)")
    
    def test_satellite_initialization(self, sample_satellite) -> None:
        """Test satellite initialization from TLE."""
        assert sample_satellite.satellite_name == "ISS (ZARYA)"
        assert len(sample_satellite.tle_lines) == 3
        assert sample_satellite.predictor is not None
    
    def test_invalid_satellite_name(self, sample_tle_file) -> None:
        """Test error handling for invalid satellite name."""
        with pytest.raises(ValueError):
            SatelliteOrbit.from_tle_file(sample_tle_file, "NONEXISTENT SATELLITE")
    
    def test_invalid_tle_file(self) -> None:
        """Test error handling for nonexistent TLE file."""
        with pytest.raises(FileNotFoundError):
            SatelliteOrbit.from_tle_file("nonexistent.tle", "ISS (ZARYA)")
    
    def test_get_position(self, sample_satellite) -> None:
        """Test position calculation."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        lat, lon, alt = sample_satellite.get_position(timestamp)
        
        # Basic sanity checks
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180
        assert alt > 0  # Should be above Earth's surface
    
    def test_get_ground_track(self, sample_satellite) -> None:
        """Test ground track generation."""
        start_time = datetime(2024, 1, 1, 12, 0, 0)
        end_time = start_time + timedelta(hours=1)
        
        ground_track = sample_satellite.get_ground_track(start_time, end_time, 5.0)
        
        assert len(ground_track) > 0
        assert len(ground_track) == 13  # 60 minutes / 5 minute steps + 1
        
        # Check data structure
        for point in ground_track:
            timestamp, lat, lon, alt = point
            assert isinstance(timestamp, datetime)
            assert -90 <= lat <= 90
            assert -180 <= lon <= 180
            assert alt > 0
    
    def test_orbital_period(self, sample_satellite) -> None:
        """Test orbital period calculation."""
        period = sample_satellite.get_orbital_period()
        
        # ISS orbital period should be around 90-95 minutes
        assert 80 <= period.total_seconds() / 60 <= 100
    
    def test_string_representation(self, sample_satellite) -> None:
        """Test string representation."""
        repr_str = repr(sample_satellite)
        assert "ISS (ZARYA)" in repr_str
        assert "SatelliteOrbit" in repr_str
