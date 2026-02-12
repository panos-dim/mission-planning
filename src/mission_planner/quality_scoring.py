"""
Quality scoring models for mission planning.

This module provides quality scoring functions that convert incidence angles
into quality scores for opportunity valuation. Different imaging modalities
(optical vs SAR) have different optimal geometries.

Supports multi-criteria weighted scoring with configurable weights for:
- Priority: Target importance (1-5)
- Geometry: Imaging quality from incidence angle
- Timing: Preference for earlier opportunities (optional)
"""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class MultiCriteriaWeights:
    """
    Multi-criteria weight configuration for opportunity scoring.

    All weights are automatically normalized to sum to 1.0.
    Use raw values (any scale) - normalization is handled internally.
    """

    priority: float = 40.0  # Weight for target priority (1-5 scale)
    geometry: float = 40.0  # Weight for incidence angle quality (0-1 scale)
    timing: float = 20.0  # Weight for chronological preference (0-1 scale)

    # Derived normalized weights (computed in __post_init__)
    _normalized: Dict[str, float] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        """Normalize weights to sum to 1.0."""
        self._normalize()

    def _normalize(self):
        """Compute normalized weights."""
        total = self.priority + self.geometry + self.timing
        if total <= 0:
            # Equal weights if all zero
            self._normalized = {"priority": 1 / 3, "geometry": 1 / 3, "timing": 1 / 3}
        else:
            self._normalized = {
                "priority": self.priority / total,
                "geometry": self.geometry / total,
                "timing": self.timing / total,
            }

    @property
    def norm_priority(self) -> float:
        return self._normalized.get("priority", 0.33)

    @property
    def norm_geometry(self) -> float:
        return self._normalized.get("geometry", 0.33)

    @property
    def norm_timing(self) -> float:
        return self._normalized.get("timing", 0.33)

    def to_dict(self) -> Dict[str, float]:
        """Return raw weights as dictionary."""
        return {
            "priority": self.priority,
            "geometry": self.geometry,
            "timing": self.timing,
        }

    def normalized_dict(self) -> Dict[str, float]:
        """Return normalized weights as dictionary."""
        return self._normalized.copy()

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "MultiCriteriaWeights":
        """Create from dictionary."""
        return cls(
            priority=d.get("priority", 40.0),
            geometry=d.get("geometry", 40.0),
            timing=d.get("timing", 20.0),
        )


# Preset weight profiles for common scenarios
WEIGHT_PRESETS: Dict[str, MultiCriteriaWeights] = {
    "balanced": MultiCriteriaWeights(priority=40, geometry=40, timing=20),
    "priority_first": MultiCriteriaWeights(priority=70, geometry=20, timing=10),
    "quality_first": MultiCriteriaWeights(priority=20, geometry=70, timing=10),
    "urgent": MultiCriteriaWeights(priority=60, geometry=10, timing=30),
    "archival": MultiCriteriaWeights(priority=10, geometry=80, timing=10),
}


class QualityModel(Enum):
    """Available quality scoring models."""

    OFF = "off"  # No quality adjustment (quality_score = 1.0)
    MONOTONIC = "monotonic"  # Lower incidence = higher quality (optical default)
    BAND = "band"  # Peaked at ideal incidence (SAR default)


def compute_quality_score(
    incidence_angle_deg: Optional[float],
    mode: str,
    quality_model: QualityModel = QualityModel.MONOTONIC,
    ideal_incidence_deg: float = 35.0,
    band_width_deg: float = 7.5,
) -> float:
    """
    Compute quality score from incidence angle.

    Args:
        incidence_angle_deg: Off-nadir incidence angle in degrees (0=nadir, 90=horizon)
        mode: Imaging mode ('OPTICAL' or 'SAR')
        quality_model: Quality model to use
        ideal_incidence_deg: Ideal incidence angle for Band model (degrees)
        band_width_deg: Band width for Band model (degrees)

    Returns:
        Quality score in [0, 1] where 1.0 is highest quality
    """
    # Handle missing incidence angle
    if incidence_angle_deg is None:
        logger.warning("Missing incidence_angle_deg, returning neutral quality score")
        return 1.0

    # Quality model: OFF
    if quality_model == QualityModel.OFF:
        return 1.0

    # Quality model: MONOTONIC (optical default)
    if quality_model == QualityModel.MONOTONIC:
        return _monotonic_quality(incidence_angle_deg)

    # Quality model: BAND (SAR default)
    if quality_model == QualityModel.BAND:
        return _band_quality(incidence_angle_deg, ideal_incidence_deg, band_width_deg)

    # Fallback
    logger.warning(f"Unknown quality model: {quality_model}, using monotonic")
    return _monotonic_quality(incidence_angle_deg)


def _monotonic_quality(incidence_angle_deg: float) -> float:
    """
    Monotonic decreasing quality function.

    Lower incidence angle = higher quality (better for optical imaging).
    Uses exponential decay to ensure strict preference for nadir.

    Quality progression:
    - 0° (nadir): 1.00
    - 15°: 0.78
    - 30°: 0.61
    - 45°: 0.47
    - 60°: 0.37

    Args:
        incidence_angle_deg: Off-nadir angle in degrees (can be signed, absolute value used)

    Returns:
        Quality score in [0, 1]
    """
    # IMPORTANT: Use absolute value - incidence angles can be signed (left/right of ground track)
    # The sign indicates direction, not quality difference
    abs_angle = abs(incidence_angle_deg)

    # Exponential decay: q = exp(-0.02 * angle)
    # This gives a smooth, strictly decreasing function
    quality = math.exp(-0.02 * abs_angle)

    # Clamp to [0, 1]
    return max(0.0, min(1.0, quality))


def _band_quality(
    incidence_angle_deg: float, ideal_incidence_deg: float, band_width_deg: float
) -> float:
    """
    Band quality function with peak at ideal incidence.

    Quality peaks at ideal incidence and decays with Gaussian-like profile.
    Better for SAR imaging which prefers specific incidence angles (e.g., 35°±7.5°).

    Args:
        incidence_angle_deg: Off-nadir angle in degrees
        ideal_incidence_deg: Peak quality angle (e.g., 35° for SAR)
        band_width_deg: Width of quality band (e.g., 7.5°)

    Returns:
        Quality score in [0, 1]
    """
    # Distance from ideal
    delta = abs(incidence_angle_deg - ideal_incidence_deg)

    # Gaussian-like decay: q = exp(-(delta / width)^2)
    # This creates a smooth peak at ideal_incidence_deg
    quality = math.exp(-((delta / band_width_deg) ** 2))

    # Clamp to [0, 1]
    return max(0.0, min(1.0, quality))


def compute_composite_value(
    priority: float,
    quality_score: float,
    timing_score: float,
    weights: MultiCriteriaWeights,
) -> float:
    """
    Compute composite opportunity value using multi-criteria weights.

    Formula: value = P×priority + G×geometry + T×timing

    Where P, G, T are normalized weights (sum to 1.0) and all scores are in [0, 1].

    Args:
        priority: Target priority (1-5 scale, normalized internally to 0-1)
        quality_score: Geometry quality from off-nadir angle (0-1, higher = better)
        timing_score: Chronological preference (0-1, earlier = higher)
        weights: Multi-criteria weight configuration

    Returns:
        Composite value score in range [0, 1] where 1 = highest value
    """
    # Normalize priority from 1-5 scale to 0-1 (1=best→1.0, 5=lowest→0.0)
    norm_priority = (5.0 - priority) / 4.0  # Maps 1→1, 5→0
    norm_priority = max(0.0, min(1.0, norm_priority))

    # Quality score already in 0-1
    norm_quality = max(0.0, min(1.0, quality_score))

    # Timing score already in 0-1
    norm_timing = max(0.0, min(1.0, timing_score))

    # Compute weighted sum using normalized weights
    # Result is in range [0, 1] where 1 = highest value
    value = (
        weights.norm_priority * norm_priority
        + weights.norm_geometry * norm_quality
        + weights.norm_timing * norm_timing
    )

    return value


def compute_timing_score(opportunity_index: int, total_opportunities: int) -> float:
    """
    Compute timing score based on chronological position.

    Earlier opportunities get higher scores.

    Args:
        opportunity_index: 0-based index in chronological order
        total_opportunities: Total number of opportunities

    Returns:
        Timing score in [0, 1] where 1.0 = earliest
    """
    if total_opportunities <= 1:
        return 1.0

    # Linear decay: first = 1.0, last = 0.0
    return 1.0 - (opportunity_index / (total_opportunities - 1))


def select_default_model(mode: str) -> QualityModel:
    """
    Select default quality model based on imaging mode.

    Args:
        mode: Imaging mode ('OPTICAL' or 'SAR')

    Returns:
        Recommended quality model
    """
    mode_upper = mode.upper() if mode else "OPTICAL"

    if mode_upper == "SAR":
        return QualityModel.BAND
    else:
        return QualityModel.MONOTONIC
