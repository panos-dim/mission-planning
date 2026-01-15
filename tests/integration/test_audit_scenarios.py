"""
Tests for scenario generation and preset scenarios.

Tests cover:
- Preset scenario creation
- Random scenario generation with seeds
- Scenario validation
"""

import pytest
from datetime import datetime
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mission_planner.audit.scenarios import (
    get_preset_scenario,
    generate_random_scenario,
    generate_scenario,
    PRESET_SCENARIOS,
)


class TestPresetScenarios:
    """Test preset scenario generation."""
    
    def test_list_all_presets(self):
        """Test that all preset scenarios are available."""
        assert len(PRESET_SCENARIOS) >= 5
        assert "simple_two_targets" in PRESET_SCENARIOS
        assert "tight_timing_three_targets" in PRESET_SCENARIOS
        assert "long_day_many_targets" in PRESET_SCENARIOS
        assert "cross_hemisphere" in PRESET_SCENARIOS
        assert "dense_cluster" in PRESET_SCENARIOS
    
    def test_simple_two_targets(self):
        """Test simple_two_targets preset."""
        scenario = get_preset_scenario("simple_two_targets")
        
        assert scenario.scenario_id == "simple_two_targets"
        assert len(scenario.targets) == 2
        assert len(scenario.satellites) == 1
        assert scenario.mission_mode == "OPTICAL"
        assert "simple" in scenario.tags
        assert "deterministic" in scenario.tags
    
    def test_tight_timing_three_targets(self):
        """Test tight_timing_three_targets preset."""
        scenario = get_preset_scenario("tight_timing_three_targets")
        
        assert scenario.scenario_id == "tight_timing_three_targets"
        assert len(scenario.targets) == 3
        assert "tight_timing" in scenario.tags
        assert "roll_pitch_advantage" in scenario.tags
        assert scenario.expected_behavior is not None
    
    def test_long_day_many_targets(self):
        """Test long_day_many_targets stress test."""
        scenario = get_preset_scenario("long_day_many_targets")
        
        assert scenario.scenario_id == "long_day_many_targets"
        assert len(scenario.targets) == 15
        assert "stress_test" in scenario.tags
        assert "many_targets" in scenario.tags
        
        # Check time window is 24 hours
        duration = scenario.time_window_end - scenario.time_window_start
        assert duration.total_seconds() == 24 * 3600
    
    def test_cross_hemisphere(self):
        """Test cross_hemisphere preset."""
        scenario = get_preset_scenario("cross_hemisphere")
        
        assert scenario.scenario_id == "cross_hemisphere"
        assert len(scenario.targets) == 5
        assert "cross_hemisphere" in scenario.tags
        
        # Check targets span hemispheres
        latitudes = [t.latitude for t in scenario.targets]
        assert any(lat > 50 for lat in latitudes)  # Northern
        assert any(lat < -50 for lat in latitudes)  # Southern
    
    def test_dense_cluster(self):
        """Test dense_cluster preset."""
        scenario = get_preset_scenario("dense_cluster")
        
        assert scenario.scenario_id == "dense_cluster"
        assert len(scenario.targets) == 8
        assert "clustered" in scenario.tags
        
        # Check targets are clustered (within ~2 degrees)
        lats = [t.latitude for t in scenario.targets]
        lons = [t.longitude for t in scenario.targets]
        assert max(lats) - min(lats) < 2.0
        assert max(lons) - min(lons) < 2.0
    
    def test_invalid_preset(self):
        """Test that invalid preset raises error."""
        with pytest.raises(ValueError, match="Unknown preset"):
            get_preset_scenario("nonexistent_scenario")


class TestRandomScenarios:
    """Test random scenario generation."""
    
    def test_random_scenario_basic(self):
        """Test basic random scenario generation."""
        scenario = generate_random_scenario(
            num_targets=5,
            time_span_hours=12,
            seed=42,
        )
        
        assert len(scenario.targets) == 5
        assert len(scenario.satellites) == 1
        assert "random" in scenario.tags
        
        # Check time window
        duration = scenario.time_window_end - scenario.time_window_start
        assert duration.total_seconds() == 12 * 3600
    
    def test_random_scenario_reproducible(self):
        """Test that same seed produces same scenario."""
        scenario1 = generate_random_scenario(
            num_targets=10,
            time_span_hours=6,
            seed=123,
        )
        
        scenario2 = generate_random_scenario(
            num_targets=10,
            time_span_hours=6,
            seed=123,
        )
        
        # Should be identical
        assert len(scenario1.targets) == len(scenario2.targets)
        for t1, t2 in zip(scenario1.targets, scenario2.targets):
            assert t1.latitude == pytest.approx(t2.latitude)
            assert t1.longitude == pytest.approx(t2.longitude)
            assert t1.priority == pytest.approx(t2.priority)
    
    def test_random_scenario_different_seeds(self):
        """Test that different seeds produce different scenarios."""
        scenario1 = generate_random_scenario(
            num_targets=10,
            time_span_hours=6,
            seed=1,
        )
        
        scenario2 = generate_random_scenario(
            num_targets=10,
            time_span_hours=6,
            seed=2,
        )
        
        # Should be different
        lat_diffs = [
            abs(t1.latitude - t2.latitude)
            for t1, t2 in zip(scenario1.targets, scenario2.targets)
        ]
        assert any(diff > 1.0 for diff in lat_diffs)
    
    def test_random_scenario_custom_bounds(self):
        """Test random scenario with custom geographic bounds."""
        scenario = generate_random_scenario(
            num_targets=20,
            time_span_hours=24,
            seed=999,
            lat_min=30.0,
            lat_max=60.0,
            lon_min=-10.0,
            lon_max=40.0,
        )
        
        # Check all targets are within bounds
        for target in scenario.targets:
            assert 30.0 <= target.latitude <= 60.0
            assert -10.0 <= target.longitude <= 40.0
    
    def test_random_scenario_sar_mode(self):
        """Test random scenario with SAR mission mode."""
        scenario = generate_random_scenario(
            num_targets=8,
            time_span_hours=12,
            seed=456,
            mission_mode="SAR",
        )
        
        assert scenario.mission_mode == "SAR"


class TestScenarioGenerator:
    """Test the general scenario generator interface."""
    
    def test_generate_preset_scenario(self):
        """Test generating preset scenario via general interface."""
        scenario = generate_scenario(
            scenario_type="preset",
            preset_id="simple_two_targets",
        )
        
        assert scenario.scenario_id == "simple_two_targets"
        assert len(scenario.targets) == 2
    
    def test_generate_random_scenario(self):
        """Test generating random scenario via general interface."""
        scenario = generate_scenario(
            scenario_type="random",
            num_targets=7,
            time_span_hours=8,
            seed=789,
        )
        
        assert len(scenario.targets) == 7
        duration = scenario.time_window_end - scenario.time_window_start
        assert duration.total_seconds() == 8 * 3600
    
    def test_generate_scenario_invalid_type(self):
        """Test that invalid scenario type raises error."""
        with pytest.raises(ValueError, match="Unknown scenario_type"):
            generate_scenario(scenario_type="invalid")
    
    def test_generate_preset_without_id(self):
        """Test that preset scenario requires preset_id."""
        with pytest.raises(ValueError, match="preset_id required"):
            generate_scenario(scenario_type="preset")


class TestScenarioValidation:
    """Test scenario structure and validation."""
    
    def test_scenario_has_required_fields(self):
        """Test that scenarios have all required fields."""
        scenario = get_preset_scenario("simple_two_targets")
        
        assert hasattr(scenario, "scenario_id")
        assert hasattr(scenario, "description")
        assert hasattr(scenario, "satellites")
        assert hasattr(scenario, "targets")
        assert hasattr(scenario, "time_window_start")
        assert hasattr(scenario, "time_window_end")
        assert hasattr(scenario, "mission_mode")
        assert hasattr(scenario, "tags")
    
    def test_satellite_config_structure(self):
        """Test satellite configuration structure."""
        scenario = get_preset_scenario("simple_two_targets")
        
        assert len(scenario.satellites) > 0
        sat = scenario.satellites[0]
        assert hasattr(sat, "id")
        assert hasattr(sat, "name")
        assert hasattr(sat, "tle_line1")
        assert hasattr(sat, "tle_line2")
        assert sat.tle_line1.startswith("1 ")
        assert sat.tle_line2.startswith("2 ")
    
    def test_target_structure(self):
        """Test target structure."""
        scenario = get_preset_scenario("simple_two_targets")
        
        for target in scenario.targets:
            assert hasattr(target, "name")
            assert hasattr(target, "latitude")
            assert hasattr(target, "longitude")
            assert hasattr(target, "priority")
            assert -90 <= target.latitude <= 90
            assert -180 <= target.longitude <= 180
            assert 1 <= target.priority <= 5
    
    def test_time_window_valid(self):
        """Test that time windows are valid."""
        scenario = get_preset_scenario("simple_two_targets")
        
        assert isinstance(scenario.time_window_start, datetime)
        assert isinstance(scenario.time_window_end, datetime)
        assert scenario.time_window_end > scenario.time_window_start


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
