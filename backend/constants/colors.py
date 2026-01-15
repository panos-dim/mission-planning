"""
Satellite Color Palette - Single Source of Truth

Professional aerospace colorblind-safe palette based on:
- Okabe-Ito universal design principles
- NASA Astro UXDS dark theme optimization
- WCAG AA contrast compliance for dark backgrounds

For constellations with 10+ satellites, colors are generated
algorithmically using HSL color space to ensure distinction.
"""

import math
from typing import List, Tuple

# Base palette - 8 hand-picked colorblind-safe colors (hex format)
SATELLITE_COLOR_PALETTE = [
    "#56B4E9",  # Sky Blue (primary) - Space42 brand aligned
    "#E69F00",  # Orange - high contrast, colorblind safe
    "#CC79A7",  # Rose/Pink - distinct from red, colorblind safe
    "#009E73",  # Teal/Green - colorblind safe green alternative
    "#F5C242",  # Amber/Gold - warm accent, high visibility
    "#0072B2",  # Deep Blue - professional aerospace
    "#D55E00",  # Vermillion - warm, distinct from orange
    "#999999",  # Gray - neutral fallback
]

# RGBA versions for CZML (matching hex values above)
SATELLITE_COLOR_PALETTE_RGBA: List[List[int]] = [
    [86, 180, 233, 255],   # Sky Blue
    [230, 159, 0, 255],    # Orange
    [204, 121, 167, 255],  # Rose/Pink
    [0, 158, 115, 255],    # Teal/Green
    [245, 194, 66, 255],   # Amber/Gold
    [0, 114, 178, 255],    # Deep Blue
    [213, 94, 0, 255],     # Vermillion
    [153, 153, 153, 255],  # Gray
]


def _hsl_to_rgb(h: float, s: float, l: float) -> Tuple[int, int, int]:
    """Convert HSL to RGB values."""
    s /= 100
    l /= 100
    a = s * min(l, 1 - l)
    
    def f(n: int) -> int:
        k = (n + h / 30) % 12
        color = l - a * max(min(k - 3, 9 - k, 1), -1)
        return round(255 * color)
    
    return (f(0), f(8), f(4))


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    """Convert HSL to hex color string."""
    r, g, b = _hsl_to_rgb(h, s, l)
    return f"#{r:02x}{g:02x}{b:02x}".upper()


def _hsl_to_rgba(h: float, s: float, l: float, alpha: int = 255) -> List[int]:
    """Convert HSL to RGBA list."""
    r, g, b = _hsl_to_rgb(h, s, l)
    return [r, g, b, alpha]


def _generate_extended_color_hex(index: int) -> str:
    """
    Generate additional colors for large constellations (9+ satellites).
    Uses golden angle distribution in HSL space for maximum distinction.
    """
    golden_angle = 137.508  # degrees
    base_hue = 200  # Starting point that doesn't conflict with base palette
    hue = (base_hue + index * golden_angle) % 360
    saturation = 65 + (index % 3) * 10  # 65-85%
    lightness = 55 + (index % 2) * 10   # 55-65%
    return _hsl_to_hex(hue, saturation, lightness)


def _generate_extended_color_rgba(index: int) -> List[int]:
    """Generate RGBA color for satellites beyond base palette."""
    golden_angle = 137.508
    base_hue = 200
    hue = (base_hue + index * golden_angle) % 360
    saturation = 65 + (index % 3) * 10
    lightness = 55 + (index % 2) * 10
    return _hsl_to_rgba(hue, saturation, lightness)


def get_satellite_color_by_index(index: int) -> str:
    """
    Get satellite color by index - handles any constellation size.
    
    Args:
        index: Satellite index (0-based)
        
    Returns:
        Hex color string (e.g., "#56B4E9")
    """
    if index < len(SATELLITE_COLOR_PALETTE):
        return SATELLITE_COLOR_PALETTE[index]
    return _generate_extended_color_hex(index - len(SATELLITE_COLOR_PALETTE))


def get_satellite_color_rgba_by_index(index: int) -> List[int]:
    """
    Get satellite color RGBA by index - handles any constellation size.
    
    Args:
        index: Satellite index (0-based)
        
    Returns:
        RGBA list [r, g, b, a]
    """
    if index < len(SATELLITE_COLOR_PALETTE_RGBA):
        return list(SATELLITE_COLOR_PALETTE_RGBA[index])
    return _generate_extended_color_rgba(index - len(SATELLITE_COLOR_PALETTE_RGBA))


def hex_to_rgba(hex_color: str, alpha: int = 255) -> List[int]:
    """Convert hex color to RGBA list."""
    hex_color = hex_color.lstrip('#')
    return [
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
        alpha
    ]


def with_alpha(rgba: List[int], alpha: int) -> List[int]:
    """Get color with modified alpha."""
    return [rgba[0], rgba[1], rgba[2], alpha]
