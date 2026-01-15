"""
Scenario generator for mission planning audit and benchmarking.

Provides both deterministic fixtures and randomized scenarios for testing
algorithm behavior across different conditions.
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from ..targets import GroundTarget

logger = logging.getLogger(__name__)


@dataclass
class SatelliteConfig:
    """Satellite configuration for a scenario."""
    
    id: str
    tle_line1: str
    tle_line2: str
    name: str = ""


@dataclass
class Scenario:
    """Complete scenario definition for audit/benchmark."""
    
    scenario_id: str
    description: str
    satellites: List[SatelliteConfig]
    targets: List[GroundTarget]
    time_window_start: datetime
    time_window_end: datetime
    mission_mode: str = "OPTICAL"  # or "SAR"
    
    # Expected behavior (for validation)
    expected_min_shots: Optional[int] = None
    expected_behavior: Optional[str] = None
    
    # Tags for filtering
    tags: List[str] = field(default_factory=list)


# Standard ICEYE-X44 TLE (used in most tests)
ICEYE_X44_TLE = SatelliteConfig(
    id="ICEYE-X44",
    name="ICEYE-X44",
    tle_line1="1 48915U 21059L   25226.50000000  .00001234  00000-0  12345-3 0  9990",
    tle_line2="2 48915  97.6900 234.5678 0001234  89.0123 271.1234 15.19012345123456",
)


def _create_simple_two_targets() -> Scenario:
    """
    Simple scenario with 2 targets.
    Easy to reason about, good for manual verification.
    """
    return Scenario(
        scenario_id="simple_two_targets",
        description="Two targets with clear visibility, easy to verify manually",
        satellites=[ICEYE_X44_TLE],
        targets=[
            GroundTarget(
                name="Target 1",
                latitude=40.0,
                longitude=20.0,
                priority=1,
            ),
            GroundTarget(
                name="Target 2",
                latitude=41.0,
                longitude=21.0,
                priority=1,
            ),
        ],
        time_window_start=datetime(2025, 10, 13, 0, 0, 0),
        time_window_end=datetime(2025, 10, 13, 12, 0, 0),
        mission_mode="OPTICAL",
        expected_min_shots=2,
        expected_behavior="Both roll-only and roll+pitch should accept similar number of shots",
        tags=["simple", "deterministic", "manual_verification"],
    )


def _create_tight_timing_three_targets() -> Scenario:
    """
    Three targets with tight timing constraints.
    Designed to show where roll+pitch can recover shots that roll-only cannot.
    """
    return Scenario(
        scenario_id="tight_timing_three_targets",
        description="Three targets with tight spacing - roll+pitch should recover additional shots",
        satellites=[ICEYE_X44_TLE],
        targets=[
            GroundTarget(
                name="Target A",
                latitude=35.0,
                longitude=10.0,
                priority=1,
            ),
            GroundTarget(
                name="Target B",
                latitude=35.5,
                longitude=11.0,
                priority=1,
            ),
            GroundTarget(
                name="Target C",
                latitude=36.0,
                longitude=12.0,
                priority=1,
            ),
        ],
        time_window_start=datetime(2025, 10, 13, 6, 0, 0),
        time_window_end=datetime(2025, 10, 13, 18, 0, 0),
        mission_mode="OPTICAL",
        expected_min_shots=3,
        expected_behavior="Roll+pitch should accept >=3 shots, roll-only may miss some due to maneuver constraints",
        tags=["tight_timing", "roll_pitch_advantage", "deterministic"],
    )


def _create_long_day_many_targets() -> Scenario:
    """
    Stress test with many targets over a full day.
    Tests algorithm scalability and complex scheduling.
    """
    targets = []
    for i in range(15):
        # Distribute targets across different latitudes
        lat = 20.0 + (i * 3.0)  # 20° to 62°
        lon = -10.0 + (i * 5.0)  # -10° to 60°
        targets.append(
            GroundTarget(
                name=f"Target {i:02d}",
                latitude=lat,
                longitude=lon,
                priority=max(1, 5 - (i // 3)),  # Decreasing priority (5 to 1)
            )
        )
    
    return Scenario(
        scenario_id="long_day_many_targets",
        description="15 targets over 24 hours - stress test for algorithm scalability",
        satellites=[ICEYE_X44_TLE],
        targets=targets,
        time_window_start=datetime(2025, 10, 13, 0, 0, 0),
        time_window_end=datetime(2025, 10, 14, 0, 0, 0),
        mission_mode="OPTICAL",
        expected_min_shots=10,
        expected_behavior="Should accept majority of targets; roll+pitch may gain 1-3 additional shots",
        tags=["stress_test", "many_targets", "long_duration"],
    )


def _create_cross_hemisphere() -> Scenario:
    """
    Targets in both northern and southern hemispheres.
    Tests global coverage and orbit dynamics.
    """
    return Scenario(
        scenario_id="cross_hemisphere",
        description="Targets spanning northern and southern hemispheres",
        satellites=[ICEYE_X44_TLE],
        targets=[
            GroundTarget(name="North 1", latitude=60.0, longitude=25.0, priority=1),
            GroundTarget(name="North 2", latitude=55.0, longitude=30.0, priority=1),
            GroundTarget(name="Equator", latitude=0.0, longitude=20.0, priority=1),
            GroundTarget(name="South 1", latitude=-55.0, longitude=25.0, priority=1),
            GroundTarget(name="South 2", latitude=-60.0, longitude=30.0, priority=1),
        ],
        time_window_start=datetime(2025, 10, 13, 0, 0, 0),
        time_window_end=datetime(2025, 10, 13, 12, 0, 0),
        mission_mode="OPTICAL",
        expected_min_shots=4,
        expected_behavior="Polar orbit should cover both hemispheres well",
        tags=["global", "cross_hemisphere", "polar_orbit"],
    )


def _create_dense_cluster() -> Scenario:
    """
    Cluster of targets in small geographic area.
    Tests handling of nearby targets and potential overlaps.
    """
    base_lat = 40.0
    base_lon = 20.0
    targets = []
    
    for i in range(8):
        # Create cluster within ~100km radius
        offset_lat = (random.random() - 0.5) * 1.0  # ±0.5° (~55km)
        offset_lon = (random.random() - 0.5) * 1.0
        
        targets.append(
            GroundTarget(
                name=f"Cluster {i}",
                latitude=base_lat + offset_lat,
                longitude=base_lon + offset_lon,
                priority=1,
            )
        )
    
    return Scenario(
        scenario_id="dense_cluster",
        description="Dense cluster of 8 targets in small area",
        satellites=[ICEYE_X44_TLE],
        targets=targets,
        time_window_start=datetime(2025, 10, 13, 0, 0, 0),
        time_window_end=datetime(2025, 10, 13, 12, 0, 0),
        mission_mode="OPTICAL",
        expected_min_shots=5,
        expected_behavior="Multiple targets may be imageable in single pass; tests within-pass scheduling",
        tags=["clustered", "high_density", "single_pass_multiple"],
    )


# Registry of preset scenarios
PRESET_SCENARIOS = {
    "simple_two_targets": _create_simple_two_targets,
    "tight_timing_three_targets": _create_tight_timing_three_targets,
    "long_day_many_targets": _create_long_day_many_targets,
    "cross_hemisphere": _create_cross_hemisphere,
    "dense_cluster": _create_dense_cluster,
}


def get_preset_scenario(preset_id: str) -> Scenario:
    """
    Get a preset scenario by ID.
    
    Args:
        preset_id: ID of preset scenario
        
    Returns:
        Scenario object
        
    Raises:
        ValueError: If preset_id not found
    """
    if preset_id not in PRESET_SCENARIOS:
        available = ", ".join(PRESET_SCENARIOS.keys())
        raise ValueError(f"Unknown preset '{preset_id}'. Available: {available}")
    
    return PRESET_SCENARIOS[preset_id]()


def generate_random_scenario(
    num_targets: int,
    time_span_hours: int,
    seed: Optional[int] = None,
    lat_min: float = -60.0,
    lat_max: float = 60.0,
    lon_min: float = -180.0,
    lon_max: float = 180.0,
    mission_mode: str = "OPTICAL",
) -> Scenario:
    """
    Generate a random scenario with specified parameters.
    
    Args:
        num_targets: Number of targets to generate
        time_span_hours: Duration of mission window in hours
        seed: Random seed for reproducibility (optional)
        lat_min: Minimum latitude for target distribution
        lat_max: Maximum latitude for target distribution
        lon_min: Minimum longitude for target distribution
        lon_max: Maximum longitude for target distribution
        mission_mode: "OPTICAL" or "SAR"
        
    Returns:
        Randomly generated Scenario
    """
    if seed is not None:
        random.seed(seed)
    
    scenario_id = f"random_{num_targets}tgt_{time_span_hours}h_seed{seed}" if seed else f"random_{num_targets}tgt_{time_span_hours}h"
    
    # Generate random targets
    targets = []
    for i in range(num_targets):
        targets.append(
            GroundTarget(
                name=f"Random Target {i:03d}",
                latitude=random.uniform(lat_min, lat_max),
                longitude=random.uniform(lon_min, lon_max),
                priority=random.randint(1, 5),
            )
        )
    
    # Random start time in October 2025
    start_day = random.randint(1, 20)
    start_hour = random.randint(0, 23)
    time_window_start = datetime(2025, 10, start_day, start_hour, 0, 0)
    time_window_end = time_window_start + timedelta(hours=time_span_hours)
    
    return Scenario(
        scenario_id=scenario_id,
        description=f"Random scenario: {num_targets} targets over {time_span_hours}h (seed={seed})",
        satellites=[ICEYE_X44_TLE],
        targets=targets,
        time_window_start=time_window_start,
        time_window_end=time_window_end,
        mission_mode=mission_mode,
        tags=["random", f"n{num_targets}", f"t{time_span_hours}h"],
    )


def generate_scenario(
    scenario_type: str,
    **kwargs,
) -> Scenario:
    """
    Generate a scenario by type.
    
    Args:
        scenario_type: "preset" or "random"
        **kwargs: Additional parameters (preset_id for preset, or random params)
        
    Returns:
        Generated Scenario
    """
    if scenario_type == "preset":
        preset_id = kwargs.get("preset_id")
        if not preset_id:
            raise ValueError("preset_id required for preset scenarios")
        return get_preset_scenario(preset_id)
    
    elif scenario_type == "random":
        return generate_random_scenario(
            num_targets=kwargs.get("num_targets", 10),
            time_span_hours=kwargs.get("time_span_hours", 12),
            seed=kwargs.get("seed"),
            lat_min=kwargs.get("lat_min", -60.0),
            lat_max=kwargs.get("lat_max", 60.0),
            lon_min=kwargs.get("lon_min", -180.0),
            lon_max=kwargs.get("lon_max", 180.0),
            mission_mode=kwargs.get("mission_mode", "OPTICAL"),
        )
    
    else:
        raise ValueError(f"Unknown scenario_type: {scenario_type}")
