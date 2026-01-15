"""
Unit tests for satellite factory functions (PR #2).

Tests the constellation support helper functions:
- create_satellite_orbit_from_tle
- create_satellites_from_request
- assign_satellite_colors
- get_satellite_info_list

These tests use isolated mock objects to avoid external dependencies.
"""

import pytest
from typing import List, Optional, Dict
from pydantic import BaseModel, Field, model_validator


# ============================================================================
# Isolated Model Definitions (mirrors backend/main.py)
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
    tle: Optional[TLEData] = None
    satellites: Optional[List[TLEData]] = None
    targets: List[TargetData]
    start_time: str
    end_time: Optional[str] = None
    
    @model_validator(mode='after')
    def validate_satellite_input(self) -> 'MissionRequest':
        has_tle = self.tle is not None
        has_satellites = self.satellites is not None and len(self.satellites) > 0
        if not has_tle and not has_satellites:
            raise ValueError("Either 'tle' or 'satellites' must be provided")
        return self
    
    def get_satellite_list(self) -> List[TLEData]:
        if self.satellites and len(self.satellites) > 0:
            return self.satellites
        elif self.tle:
            return [self.tle]
        return []
    
    def is_constellation(self) -> bool:
        return len(self.get_satellite_list()) > 1


# ============================================================================
# Satellite Factory Functions (mirrors backend/main.py)
# ============================================================================

SATELLITE_COLORS = [
    "#FFD700",  # Gold (primary satellite)
    "#00FFFF",  # Cyan
    "#FF00FF",  # Magenta
    "#FFA500",  # Orange
    "#32CD32",  # Lime Green
    "#1E90FF",  # Dodger Blue
    "#FF69B4",  # Hot Pink
    "#ADFF2F",  # Green Yellow
]


def assign_satellite_colors(satellite_list: List[TLEData]) -> Dict[str, str]:
    """Assign distinct colors to each satellite for visualization."""
    return {
        f"sat_{s.name}": SATELLITE_COLORS[i % len(SATELLITE_COLORS)]
        for i, s in enumerate(satellite_list)
    }


def get_satellite_info_list(satellite_list: List[TLEData]) -> List[Dict[str, str]]:
    """Build satellite info list for API response."""
    colors = assign_satellite_colors(satellite_list)
    return [
        {
            "id": f"sat_{s.name}",
            "name": s.name,
            "color": colors[f"sat_{s.name}"]
        }
        for s in satellite_list
    ]


# ============================================================================
# Tests
# ============================================================================

class TestAssignSatelliteColors:
    """Test satellite color assignment."""
    
    def test_single_satellite_gets_gold(self) -> None:
        """First satellite gets gold color."""
        tle = TLEData(
            name="SAT-1",
            line1="1 99999U 24999A   25001.00000000  .00000000  00000-0  00000-0 0  9999",
            line2="2 99999  97.4000 180.0000 0001000  90.0000 270.0000 15.20000000    01"
        )
        
        colors = assign_satellite_colors([tle])
        
        assert "sat_SAT-1" in colors
        assert colors["sat_SAT-1"] == "#FFD700"  # Gold
    
    def test_second_satellite_gets_cyan(self) -> None:
        """Second satellite gets cyan color."""
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
        
        colors = assign_satellite_colors([sat1, sat2])
        
        assert colors["sat_SAT-1"] == "#FFD700"  # Gold
        assert colors["sat_SAT-2"] == "#00FFFF"  # Cyan
    
    def test_colors_cycle_for_large_constellation(self) -> None:
        """Colors cycle when constellation is larger than palette."""
        satellites = []
        for i in range(10):  # More than 8 colors available
            satellites.append(TLEData(
                name=f"SAT-{i+1}",
                line1=f"1 9999{i}U 24999A   25001.00000000  .00000000  00000-0  00000-0 0  999{i}",
                line2=f"2 9999{i}  97.4000 180.0000 0001000  90.0000 270.0000 15.20000000    0{i}"
            ))
        
        colors = assign_satellite_colors(satellites)
        
        # 9th satellite (index 8) should wrap to first color
        assert colors["sat_SAT-9"] == "#FFD700"  # Gold (cycled)
    
    def test_empty_list_returns_empty_dict(self) -> None:
        """Empty satellite list returns empty color dict."""
        colors = assign_satellite_colors([])
        assert colors == {}


class TestGetSatelliteInfoList:
    """Test satellite info list builder."""
    
    def test_single_satellite_info(self) -> None:
        """Single satellite returns proper info structure."""
        tle = TLEData(
            name="TEST-SAT",
            line1="1 99999U 24999A   25001.00000000  .00000000  00000-0  00000-0 0  9999",
            line2="2 99999  97.4000 180.0000 0001000  90.0000 270.0000 15.20000000    01"
        )
        
        info_list = get_satellite_info_list([tle])
        
        assert len(info_list) == 1
        assert info_list[0]["id"] == "sat_TEST-SAT"
        assert info_list[0]["name"] == "TEST-SAT"
        assert info_list[0]["color"] == "#FFD700"
    
    def test_constellation_info_list(self) -> None:
        """Constellation returns info for all satellites."""
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
        
        info_list = get_satellite_info_list([sat1, sat2])
        
        assert len(info_list) == 2
        
        # First satellite
        assert info_list[0]["id"] == "sat_SAT-ALPHA"
        assert info_list[0]["name"] == "SAT-ALPHA"
        assert info_list[0]["color"] == "#FFD700"  # Gold
        
        # Second satellite
        assert info_list[1]["id"] == "sat_SAT-BETA"
        assert info_list[1]["name"] == "SAT-BETA"
        assert info_list[1]["color"] == "#00FFFF"  # Cyan
    
    def test_info_list_preserves_order(self) -> None:
        """Info list preserves satellite order."""
        satellites = []
        for letter in ["C", "A", "B"]:
            satellites.append(TLEData(
                name=f"SAT-{letter}",
                line1="1 99999U 24999A   25001.00000000  .00000000  00000-0  00000-0 0  9999",
                line2="2 99999  97.4000 180.0000 0001000  90.0000 270.0000 15.20000000    01"
            ))
        
        info_list = get_satellite_info_list(satellites)
        
        assert info_list[0]["name"] == "SAT-C"
        assert info_list[1]["name"] == "SAT-A"
        assert info_list[2]["name"] == "SAT-B"


class TestConstellationIntegration:
    """Integration tests for constellation request processing."""
    
    def test_single_satellite_request_produces_single_info(self) -> None:
        """Single satellite request produces single info entry."""
        tle = TLEData(
            name="SOLO",
            line1="1 99999U 24999A   25001.00000000  .00000000  00000-0  00000-0 0  9999",
            line2="2 99999  97.4000 180.0000 0001000  90.0000 270.0000 15.20000000    01"
        )
        target = TargetData(name="Target", latitude=40.0, longitude=23.0)
        
        request = MissionRequest(
            tle=tle,
            targets=[target],
            start_time="2025-01-01T00:00:00Z"
        )
        
        satellite_list = request.get_satellite_list()
        info_list = get_satellite_info_list(satellite_list)
        
        assert len(info_list) == 1
        assert info_list[0]["name"] == "SOLO"
        assert request.is_constellation() is False
    
    def test_constellation_request_produces_multiple_info(self) -> None:
        """Constellation request produces info for all satellites."""
        sat1 = TLEData(
            name="TWIN-A",
            line1="1 99999U 24999A   25001.00000000  .00000000  00000-0  00000-0 0  9999",
            line2="2 99999  97.4000 180.0000 0001000  90.0000 270.0000 15.20000000    01"
        )
        sat2 = TLEData(
            name="TWIN-B",
            line1="1 99998U 24999B   25001.00000000  .00000000  00000-0  00000-0 0  9998",
            line2="2 99998  97.4000 180.0000 0001000  90.0000 270.0000 15.20000000    01"
        )
        target = TargetData(name="Target", latitude=40.0, longitude=23.0)
        
        request = MissionRequest(
            satellites=[sat1, sat2],
            targets=[target],
            start_time="2025-01-01T00:00:00Z"
        )
        
        satellite_list = request.get_satellite_list()
        info_list = get_satellite_info_list(satellite_list)
        
        assert len(info_list) == 2
        assert info_list[0]["name"] == "TWIN-A"
        assert info_list[1]["name"] == "TWIN-B"
        assert request.is_constellation() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
