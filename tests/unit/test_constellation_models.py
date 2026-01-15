"""
Unit tests for constellation data models (PR #1).

Tests the MissionRequest model validation for both legacy single-satellite
and new multi-satellite constellation formats.

This test uses isolated Pydantic models to avoid importing the full backend
which has external dependencies (orbit_predictor, etc.).
"""

import pytest
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator, ValidationError


# ============================================================================
# Isolated Model Definitions (mirrors backend/main.py)
# This allows testing without importing the full backend with its dependencies
# ============================================================================

class TLEData(BaseModel):
    """TLE data for a satellite."""
    name: str
    line1: str
    line2: str
    sensor_fov_half_angle_deg: Optional[float] = None
    imaging_type: Optional[str] = None


class TargetData(BaseModel):
    """Target data for mission planning."""
    name: str
    latitude: float
    longitude: float
    description: Optional[str] = None
    priority: Optional[int] = None


class MissionRequest(BaseModel):
    """Mission request model with constellation support."""
    # Legacy single satellite (optional for backward compatibility)
    tle: Optional[TLEData] = Field(
        default=None, 
        description="Single satellite TLE (deprecated - use 'satellites' for constellation)"
    )
    
    # NEW: Constellation support - multiple satellites
    satellites: Optional[List[TLEData]] = Field(
        default=None,
        description="List of satellite TLEs for constellation mission"
    )
    
    targets: List[TargetData]
    start_time: str
    end_time: Optional[str] = None
    duration_hours: Optional[float] = None
    mission_type: str = "imaging"
    
    @model_validator(mode='after')
    def validate_satellite_input(self) -> 'MissionRequest':
        """Ensure either tle or satellites is provided."""
        has_tle = self.tle is not None
        has_satellites = self.satellites is not None and len(self.satellites) > 0
        
        if not has_tle and not has_satellites:
            raise ValueError("Either 'tle' or 'satellites' must be provided")
        return self
    
    def get_satellite_list(self) -> List[TLEData]:
        """Get normalized list of satellites (handles both legacy and new format)."""
        if self.satellites and len(self.satellites) > 0:
            return self.satellites
        elif self.tle:
            return [self.tle]
        return []
    
    def is_constellation(self) -> bool:
        """Check if this is a multi-satellite constellation mission."""
        return len(self.get_satellite_list()) > 1


# ============================================================================
# Tests
# ============================================================================


class TestMissionRequestValidation:
    """Test MissionRequest model validation for constellation support."""
    
    @pytest.fixture
    def sample_tle(self) -> TLEData:
        """Create a sample TLE for testing."""
        return TLEData(
            name="TEST-SAT-1",
            line1="1 99999U 24999A   25001.00000000  .00000000  00000-0  00000-0 0  9999",
            line2="2 99999  97.4000 180.0000 0001000  90.0000 270.0000 15.20000000    01"
        )
    
    @pytest.fixture
    def sample_tle_2(self) -> TLEData:
        """Create a second sample TLE for constellation testing."""
        return TLEData(
            name="TEST-SAT-2",
            line1="1 99998U 24999B   25001.00000000  .00000000  00000-0  00000-0 0  9998",
            line2="2 99998  45.0000 100.0000 0001000  90.0000 270.0000 15.50000000    01"
        )
    
    @pytest.fixture
    def sample_target(self) -> TargetData:
        """Create a sample target for testing."""
        return TargetData(
            name="Test Target",
            latitude=40.0,
            longitude=23.0
        )
    
    def test_legacy_single_tle_valid(self, sample_tle: TLEData, sample_target: TargetData) -> None:
        """Test that legacy single-TLE request still works (backward compatibility)."""
        request = MissionRequest(
            tle=sample_tle,
            targets=[sample_target],
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-02T00:00:00Z"
        )
        
        assert request.tle is not None
        assert request.tle.name == "TEST-SAT-1"
        assert request.satellites is None
        
        # get_satellite_list should return single satellite as list
        satellites = request.get_satellite_list()
        assert len(satellites) == 1
        assert satellites[0].name == "TEST-SAT-1"
        
        # is_constellation should be False for single satellite
        assert request.is_constellation() is False
    
    def test_constellation_multiple_satellites(
        self, 
        sample_tle: TLEData, 
        sample_tle_2: TLEData, 
        sample_target: TargetData
    ) -> None:
        """Test constellation with multiple satellites."""
        request = MissionRequest(
            satellites=[sample_tle, sample_tle_2],
            targets=[sample_target],
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-02T00:00:00Z"
        )
        
        assert request.tle is None
        assert request.satellites is not None
        assert len(request.satellites) == 2
        
        # get_satellite_list should return all satellites
        satellites = request.get_satellite_list()
        assert len(satellites) == 2
        assert satellites[0].name == "TEST-SAT-1"
        assert satellites[1].name == "TEST-SAT-2"
        
        # is_constellation should be True for multiple satellites
        assert request.is_constellation() is True
    
    def test_no_satellite_provided_raises_error(self, sample_target: TargetData) -> None:
        """Test that request without any satellite raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            MissionRequest(
                targets=[sample_target],
                start_time="2025-01-01T00:00:00Z",
                end_time="2025-01-02T00:00:00Z"
            )
        
        # Check error message mentions the validation requirement
        error_str = str(exc_info.value)
        assert "tle" in error_str.lower() or "satellites" in error_str.lower()
    
    def test_empty_satellites_list_raises_error(self, sample_target: TargetData) -> None:
        """Test that empty satellites list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            MissionRequest(
                satellites=[],
                targets=[sample_target],
                start_time="2025-01-01T00:00:00Z",
                end_time="2025-01-02T00:00:00Z"
            )
        
        # Should fail validation since neither tle nor satellites has content
        assert exc_info.value is not None
    
    def test_both_tle_and_satellites_uses_satellites(
        self, 
        sample_tle: TLEData, 
        sample_tle_2: TLEData, 
        sample_target: TargetData
    ) -> None:
        """Test that when both are provided, satellites takes precedence."""
        request = MissionRequest(
            tle=sample_tle,  # Legacy field
            satellites=[sample_tle_2],  # New constellation field
            targets=[sample_target],
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-02T00:00:00Z"
        )
        
        # satellites should take precedence in get_satellite_list
        satellites = request.get_satellite_list()
        assert len(satellites) == 1
        assert satellites[0].name == "TEST-SAT-2"  # From satellites, not tle
    
    def test_single_satellite_in_satellites_list(
        self, 
        sample_tle: TLEData, 
        sample_target: TargetData
    ) -> None:
        """Test single satellite provided via satellites array (not legacy tle)."""
        request = MissionRequest(
            satellites=[sample_tle],
            targets=[sample_target],
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-02T00:00:00Z"
        )
        
        assert request.tle is None
        assert len(request.satellites) == 1
        
        # Single satellite via satellites array is NOT a constellation
        assert request.is_constellation() is False


class TestSatelliteListNormalization:
    """Test get_satellite_list() normalization behavior."""
    
    def test_single_tle_returns_list(self) -> None:
        """Single TLE is normalized to list."""
        tle = TLEData(
            name="SAT-1",
            line1="1 99999U 24999A   25001.00000000  .00000000  00000-0  00000-0 0  9999",
            line2="2 99999  97.4000 180.0000 0001000  90.0000 270.0000 15.20000000    01"
        )
        target = TargetData(name="T1", latitude=40.0, longitude=23.0)
        
        request = MissionRequest(
            tle=tle,
            targets=[target],
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-02T00:00:00Z"
        )
        
        result = request.get_satellite_list()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].name == "SAT-1"
    
    def test_multiple_satellites_preserves_order(self) -> None:
        """Multiple satellites preserve order in list."""
        sat1 = TLEData(
            name="SAT-ALPHA",
            line1="1 99999U 24999A   25001.00000000  .00000000  00000-0  00000-0 0  9999",
            line2="2 99999  97.4000 180.0000 0001000  90.0000 270.0000 15.20000000    01"
        )
        sat2 = TLEData(
            name="SAT-BETA",
            line1="1 99998U 24999B   25001.00000000  .00000000  00000-0  00000-0 0  9998",
            line2="2 99998  45.0000 100.0000 0001000  90.0000 270.0000 15.50000000    01"
        )
        sat3 = TLEData(
            name="SAT-GAMMA",
            line1="1 99997U 24999C   25001.00000000  .00000000  00000-0  00000-0 0  9997",
            line2="2 99997  55.0000 120.0000 0001000  90.0000 270.0000 15.30000000    01"
        )
        target = TargetData(name="T1", latitude=40.0, longitude=23.0)
        
        request = MissionRequest(
            satellites=[sat1, sat2, sat3],
            targets=[target],
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-02T00:00:00Z"
        )
        
        result = request.get_satellite_list()
        assert len(result) == 3
        assert result[0].name == "SAT-ALPHA"
        assert result[1].name == "SAT-BETA"
        assert result[2].name == "SAT-GAMMA"


class TestIsConstellation:
    """Test is_constellation() method."""
    
    def test_single_satellite_via_tle_not_constellation(self) -> None:
        """Single satellite via tle field is not a constellation."""
        tle = TLEData(
            name="SOLO-SAT",
            line1="1 99999U 24999A   25001.00000000  .00000000  00000-0  00000-0 0  9999",
            line2="2 99999  97.4000 180.0000 0001000  90.0000 270.0000 15.20000000    01"
        )
        target = TargetData(name="T1", latitude=40.0, longitude=23.0)
        
        request = MissionRequest(
            tle=tle,
            targets=[target],
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-02T00:00:00Z"
        )
        
        assert request.is_constellation() is False
    
    def test_single_satellite_via_satellites_not_constellation(self) -> None:
        """Single satellite via satellites field is not a constellation."""
        tle = TLEData(
            name="SOLO-SAT",
            line1="1 99999U 24999A   25001.00000000  .00000000  00000-0  00000-0 0  9999",
            line2="2 99999  97.4000 180.0000 0001000  90.0000 270.0000 15.20000000    01"
        )
        target = TargetData(name="T1", latitude=40.0, longitude=23.0)
        
        request = MissionRequest(
            satellites=[tle],
            targets=[target],
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-02T00:00:00Z"
        )
        
        assert request.is_constellation() is False
    
    def test_two_satellites_is_constellation(self) -> None:
        """Two satellites is a constellation."""
        sat1 = TLEData(
            name="SAT-1",
            line1="1 99999U 24999A   25001.00000000  .00000000  00000-0  00000-0 0  9999",
            line2="2 99999  97.4000 180.0000 0001000  90.0000 270.0000 15.20000000    01"
        )
        sat2 = TLEData(
            name="SAT-2",
            line1="1 99998U 24999B   25001.00000000  .00000000  00000-0  00000-0 0  9998",
            line2="2 99998  45.0000 100.0000 0001000  90.0000 270.0000 15.50000000    01"
        )
        target = TargetData(name="T1", latitude=40.0, longitude=23.0)
        
        request = MissionRequest(
            satellites=[sat1, sat2],
            targets=[target],
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-02T00:00:00Z"
        )
        
        assert request.is_constellation() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
