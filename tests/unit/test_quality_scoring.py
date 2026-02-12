"""
Comprehensive tests for quality_scoring module.

Tests cover:
- MultiCriteriaWeights normalization
- Quality models (monotonic, band, off)
- Composite value computation
- Timing score computation
- Edge cases and boundary conditions
"""

import math

import pytest

from mission_planner.quality_scoring import (
    WEIGHT_PRESETS,
    MultiCriteriaWeights,
    QualityModel,
    _band_quality,
    _monotonic_quality,
    compute_composite_value,
    compute_quality_score,
    compute_timing_score,
    select_default_model,
)


class TestMultiCriteriaWeights:
    """Tests for MultiCriteriaWeights dataclass."""

    def test_default_weights(self) -> None:
        """Test default weight initialization."""
        weights = MultiCriteriaWeights()
        assert weights.priority == 40.0
        assert weights.geometry == 40.0
        assert weights.timing == 20.0

    def test_normalization_default(self) -> None:
        """Test that default weights normalize correctly."""
        weights = MultiCriteriaWeights()
        # 40 + 40 + 20 = 100
        assert abs(weights.norm_priority - 0.4) < 0.001
        assert abs(weights.norm_geometry - 0.4) < 0.001
        assert abs(weights.norm_timing - 0.2) < 0.001

    def test_normalization_custom(self) -> None:
        """Test normalization with custom weights."""
        weights = MultiCriteriaWeights(priority=10, geometry=20, timing=70)
        assert abs(weights.norm_priority - 0.1) < 0.001
        assert abs(weights.norm_geometry - 0.2) < 0.001
        assert abs(weights.norm_timing - 0.7) < 0.001

    def test_normalization_sum_to_one(self) -> None:
        """Test that normalized weights always sum to 1.0."""
        for _ in range(10):
            import random

            p = random.uniform(0, 100)
            g = random.uniform(0, 100)
            t = random.uniform(0, 100)
            weights = MultiCriteriaWeights(priority=p, geometry=g, timing=t)
            total = weights.norm_priority + weights.norm_geometry + weights.norm_timing
            assert abs(total - 1.0) < 0.001

    def test_zero_weights(self) -> None:
        """Test handling of all-zero weights."""
        weights = MultiCriteriaWeights(priority=0, geometry=0, timing=0)
        # Should default to equal weights
        assert abs(weights.norm_priority - 1 / 3) < 0.001
        assert abs(weights.norm_geometry - 1 / 3) < 0.001
        assert abs(weights.norm_timing - 1 / 3) < 0.001

    def test_to_dict(self) -> None:
        """Test to_dict method."""
        weights = MultiCriteriaWeights(priority=10, geometry=20, timing=30)
        d = weights.to_dict()
        assert d == {"priority": 10, "geometry": 20, "timing": 30}

    def test_normalized_dict(self) -> None:
        """Test normalized_dict method."""
        weights = MultiCriteriaWeights(priority=25, geometry=25, timing=50)
        d = weights.normalized_dict()
        assert abs(d["priority"] - 0.25) < 0.001
        assert abs(d["geometry"] - 0.25) < 0.001
        assert abs(d["timing"] - 0.50) < 0.001

    def test_from_dict(self) -> None:
        """Test from_dict class method."""
        d = {"priority": 50, "geometry": 30, "timing": 20}
        weights = MultiCriteriaWeights.from_dict(d)
        assert weights.priority == 50
        assert weights.geometry == 30
        assert weights.timing == 20

    def test_from_dict_missing_keys(self) -> None:
        """Test from_dict with missing keys uses defaults."""
        d = {"priority": 50}
        weights = MultiCriteriaWeights.from_dict(d)
        assert weights.priority == 50
        assert weights.geometry == 40.0  # default
        assert weights.timing == 20.0  # default


class TestWeightPresets:
    """Tests for weight presets."""

    def test_balanced_preset(self) -> None:
        """Test balanced preset."""
        w = WEIGHT_PRESETS["balanced"]
        assert w.priority == 40
        assert w.geometry == 40
        assert w.timing == 20

    def test_priority_first_preset(self) -> None:
        """Test priority_first preset."""
        w = WEIGHT_PRESETS["priority_first"]
        assert w.priority > w.geometry
        assert w.priority > w.timing

    def test_quality_first_preset(self) -> None:
        """Test quality_first preset."""
        w = WEIGHT_PRESETS["quality_first"]
        assert w.geometry > w.priority
        assert w.geometry > w.timing

    def test_all_presets_exist(self) -> None:
        """Test all expected presets exist."""
        expected = ["balanced", "priority_first", "quality_first", "urgent", "archival"]
        for name in expected:
            assert name in WEIGHT_PRESETS


class TestMonotonicQuality:
    """Tests for monotonic quality function."""

    def test_nadir_quality(self) -> None:
        """Test quality at nadir (0°) is maximum."""
        assert abs(_monotonic_quality(0.0) - 1.0) < 0.001

    def test_decreasing_quality(self) -> None:
        """Test quality decreases with increasing angle."""
        q_15 = _monotonic_quality(15.0)
        q_30 = _monotonic_quality(30.0)
        q_45 = _monotonic_quality(45.0)

        assert q_15 > q_30 > q_45

    def test_signed_angles_equivalent(self) -> None:
        """Test that signed angles give same quality (only magnitude matters)."""
        assert _monotonic_quality(20.0) == _monotonic_quality(-20.0)
        assert _monotonic_quality(35.0) == _monotonic_quality(-35.0)

    def test_quality_bounds(self) -> None:
        """Test quality stays in [0, 1]."""
        for angle in [0, 15, 30, 45, 60, 75, 90]:
            q = _monotonic_quality(angle)
            assert 0.0 <= q <= 1.0

    def test_quality_at_45_degrees(self) -> None:
        """Test expected quality at 45°."""
        q = _monotonic_quality(45.0)
        # exp(-0.02 * 45) ≈ 0.407
        assert abs(q - math.exp(-0.02 * 45)) < 0.001


class TestBandQuality:
    """Tests for band quality function."""

    def test_peak_at_ideal(self) -> None:
        """Test quality peaks at ideal incidence."""
        ideal = 35.0
        q = _band_quality(ideal, ideal, 7.5)
        assert abs(q - 1.0) < 0.001

    def test_symmetric_decay(self) -> None:
        """Test quality decays symmetrically from ideal."""
        ideal = 35.0
        band = 7.5

        q_low = _band_quality(ideal - 10, ideal, band)
        q_high = _band_quality(ideal + 10, ideal, band)

        assert abs(q_low - q_high) < 0.001

    def test_width_affects_decay(self) -> None:
        """Test that band width affects decay rate."""
        ideal = 35.0
        delta = 10.0

        q_narrow = _band_quality(ideal + delta, ideal, 5.0)
        q_wide = _band_quality(ideal + delta, ideal, 15.0)

        assert q_wide > q_narrow  # Wider band = less decay

    def test_quality_bounds(self) -> None:
        """Test quality stays in [0, 1]."""
        for angle in [0, 15, 30, 35, 40, 45, 60]:
            q = _band_quality(angle, 35.0, 7.5)
            assert 0.0 <= q <= 1.0


class TestComputeQualityScore:
    """Tests for compute_quality_score function."""

    def test_off_model(self) -> None:
        """Test OFF model returns 1.0."""
        q = compute_quality_score(45.0, "OPTICAL", QualityModel.OFF)
        assert q == 1.0

    def test_monotonic_model(self) -> None:
        """Test MONOTONIC model."""
        q = compute_quality_score(30.0, "OPTICAL", QualityModel.MONOTONIC)
        expected = _monotonic_quality(30.0)
        assert abs(q - expected) < 0.001

    def test_band_model(self) -> None:
        """Test BAND model."""
        q = compute_quality_score(
            35.0, "SAR", QualityModel.BAND, ideal_incidence_deg=35.0, band_width_deg=7.5
        )
        assert abs(q - 1.0) < 0.001  # At ideal angle

    def test_none_incidence(self) -> None:
        """Test None incidence returns 1.0 (neutral)."""
        q = compute_quality_score(None, "OPTICAL", QualityModel.MONOTONIC)
        assert q == 1.0


class TestComputeCompositeValue:
    """Tests for compute_composite_value function."""

    def test_balanced_weights(self) -> None:
        """Test with balanced weights."""
        weights = MultiCriteriaWeights(priority=33.33, geometry=33.33, timing=33.34)

        # Max values: priority=1 (→1.0, best), quality=1.0, timing=1.0
        value = compute_composite_value(1, 1.0, 1.0, weights)
        assert abs(value - 1.0) < 0.01

    def test_min_values(self) -> None:
        """Test with minimum values (priority=5 is lowest → 0.0)."""
        weights = MultiCriteriaWeights()
        value = compute_composite_value(5, 0.0, 0.0, weights)
        assert value >= 0.0
        assert value < 0.01  # All components at minimum

    def test_priority_dominance(self) -> None:
        """Test priority-dominant weights (1=best scores higher than 5=lowest)."""
        weights = MultiCriteriaWeights(priority=100, geometry=0, timing=0)

        high_priority = compute_composite_value(1, 0.0, 0.0, weights)  # 1=best
        low_priority = compute_composite_value(5, 0.0, 0.0, weights)  # 5=lowest

        assert high_priority > low_priority

    def test_priority_normalization_mapping(self) -> None:
        """Test exact normalization: 1→1.0, 3→0.5, 5→0.0."""
        weights = MultiCriteriaWeights(priority=100, geometry=0, timing=0)

        val_p1 = compute_composite_value(1, 0.0, 0.0, weights)
        val_p3 = compute_composite_value(3, 0.0, 0.0, weights)
        val_p5 = compute_composite_value(5, 0.0, 0.0, weights)

        assert abs(val_p1 - 1.0) < 0.01  # 1 → 1.0
        assert abs(val_p3 - 0.5) < 0.01  # 3 → 0.5
        assert abs(val_p5 - 0.0) < 0.01  # 5 → 0.0

    def test_geometry_dominance(self) -> None:
        """Test geometry-dominant weights."""
        weights = MultiCriteriaWeights(priority=0, geometry=100, timing=0)

        high_quality = compute_composite_value(1, 1.0, 0.0, weights)
        low_quality = compute_composite_value(1, 0.0, 0.0, weights)

        assert high_quality > low_quality


class TestComputeTimingScore:
    """Tests for compute_timing_score function."""

    def test_first_is_highest(self) -> None:
        """Test first opportunity has highest score."""
        assert compute_timing_score(0, 10) == 1.0

    def test_last_is_lowest(self) -> None:
        """Test last opportunity has lowest score."""
        assert compute_timing_score(9, 10) == 0.0

    def test_single_opportunity(self) -> None:
        """Test single opportunity gets 1.0."""
        assert compute_timing_score(0, 1) == 1.0

    def test_linear_decay(self) -> None:
        """Test linear decay."""
        scores = [compute_timing_score(i, 5) for i in range(5)]
        # Should be [1.0, 0.75, 0.5, 0.25, 0.0]
        assert abs(scores[0] - 1.0) < 0.001
        assert abs(scores[2] - 0.5) < 0.001
        assert abs(scores[4] - 0.0) < 0.001


class TestSelectDefaultModel:
    """Tests for select_default_model function."""

    def test_optical_default(self) -> None:
        """Test optical mode uses monotonic."""
        assert select_default_model("OPTICAL") == QualityModel.MONOTONIC
        assert select_default_model("optical") == QualityModel.MONOTONIC

    def test_sar_default(self) -> None:
        """Test SAR mode uses band."""
        assert select_default_model("SAR") == QualityModel.BAND
        assert select_default_model("sar") == QualityModel.BAND

    def test_empty_string(self) -> None:
        """Test empty string defaults to monotonic."""
        assert select_default_model("") == QualityModel.MONOTONIC

    def test_none_input(self) -> None:
        """Test None input defaults to monotonic."""
        assert select_default_model(None) == QualityModel.MONOTONIC
