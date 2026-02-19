"""Regression tests for spherical-Earth ground arc distance calculation.

The flat-Earth formula ``h * tan(θ)`` underestimates the ground footprint
radius at large off-nadir angles (≈5 % at 45°).  The fix uses the law-of-sines
formula on the satellite–Earth-center–ground triangle:

    α = arcsin((R+h)/R · sin(θ)) − θ
    ground_distance = R · α

These tests lock in the correct values and verify that the old flat-Earth
formula is no longer used.
"""

import math

import pytest

from backend.czml_generator import CZMLGenerator


# ── Helper: flat-Earth baseline for comparison ──────────────────────────
def _flat_earth_m(alt_km: float, angle_deg: float) -> float:
    return alt_km * 1000.0 * math.tan(math.radians(angle_deg))


# ── Parametrised known-good values ──────────────────────────────────────
# (alt_km, angle_deg, expected_m, tolerance_m)
# Expected values computed analytically:
#   α = arcsin((R+h)/R * sin(θ)) - θ ;  d = R * α * 1000
KNOWN_CASES = [
    # Small angle – almost identical to flat-Earth
    (570, 10, 100_651, 100),
    # Medium angle
    (570, 30, 334_306, 200),
    # Large angle – the bug scenario (45° off-nadir at ICEYE altitude)
    (570, 45, 599_023, 300),
    # Very small angle (sensor FOV ≈ 1°)
    (570, 1, 9_950, 50),
    # Higher orbit (800 km, 45°)
    (800, 45, 860_660, 500),
]


@pytest.mark.parametrize("alt_km,angle_deg,expected_m,tol_m", KNOWN_CASES)
def test_ground_arc_distance_known_values(
    alt_km: float, angle_deg: float, expected_m: float, tol_m: float
) -> None:
    result = CZMLGenerator._ground_arc_distance_m(alt_km, angle_deg)
    assert abs(result - expected_m) < tol_m, (
        f"Expected ≈{expected_m:.0f} m, got {result:.0f} m "
        f"(alt={alt_km} km, angle={angle_deg}°)"
    )


def test_spherical_larger_than_flat_earth_at_45deg() -> None:
    """At 45° off-nadir, the spherical result must be larger than the flat-Earth one."""
    alt_km = 570
    angle_deg = 45
    spherical = CZMLGenerator._ground_arc_distance_m(alt_km, angle_deg)
    flat = _flat_earth_m(alt_km, angle_deg)
    assert (
        spherical > flat
    ), f"Spherical ({spherical:.0f} m) should be > flat-Earth ({flat:.0f} m)"
    # The difference should be approximately 5 %
    pct = (spherical - flat) / flat * 100
    assert 3.0 < pct < 8.0, f"Expected ~5 % difference, got {pct:.1f} %"


def test_nadir_gives_zero() -> None:
    """At nadir (0° off-nadir), ground distance must be zero."""
    result = CZMLGenerator._ground_arc_distance_m(570, 0.0)
    assert result == pytest.approx(0.0, abs=0.01)


def test_horizon_cap() -> None:
    """An angle beyond horizon should be capped, not raise."""
    # At 570 km, horizon angle is arcsin(R/(R+h)) ≈ 66.5°
    # Requesting 80° should return the horizon arc, not error
    result = CZMLGenerator._ground_arc_distance_m(570, 80)
    assert result > 0
    # Should be less than quarter of Earth circumference
    assert result < 10_000_000
