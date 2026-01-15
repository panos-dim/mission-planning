/**
 * Satellite Color Palette - Single Source of Truth
 * 
 * Professional aerospace colorblind-safe palette based on:
 * - Okabe-Ito universal design principles
 * - NASA Astro UXDS dark theme optimization
 * - WCAG AA contrast compliance for dark backgrounds
 * 
 * For constellations with 10+ satellites, colors are generated
 * algorithmically using HSL color space to ensure distinction.
 */

// Base palette - 8 hand-picked colorblind-safe colors
export const SATELLITE_COLOR_PALETTE = [
  '#56B4E9',  // Sky Blue (primary) - Space42 brand aligned
  '#E69F00',  // Orange - high contrast, colorblind safe
  '#CC79A7',  // Rose/Pink - distinct from red, colorblind safe
  '#009E73',  // Teal/Green - colorblind safe green alternative
  '#F5C242',  // Amber/Gold - warm accent, high visibility
  '#0072B2',  // Deep Blue - professional aerospace
  '#D55E00',  // Vermillion - warm, distinct from orange
  '#999999',  // Gray - neutral fallback
] as const;

// RGBA versions for Cesium/CZML (matching hex values above)
export const SATELLITE_COLOR_PALETTE_RGBA = [
  [86, 180, 233, 255],   // Sky Blue
  [230, 159, 0, 255],    // Orange
  [204, 121, 167, 255],  // Rose/Pink
  [0, 158, 115, 255],    // Teal/Green
  [245, 194, 66, 255],   // Amber/Gold
  [0, 114, 178, 255],    // Deep Blue
  [213, 94, 0, 255],     // Vermillion
  [153, 153, 153, 255],  // Gray
] as const;

/**
 * Convert HSL to Hex color
 */
function hslToHex(h: number, s: number, l: number): string {
  s /= 100;
  l /= 100;
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color).toString(16).padStart(2, '0');
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

/**
 * Convert HSL to RGBA array
 */
function hslToRgba(h: number, s: number, l: number): [number, number, number, number] {
  s /= 100;
  l /= 100;
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    return Math.round(255 * (l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1)));
  };
  return [f(0), f(8), f(4), 255];
}

/**
 * Generate additional colors for large constellations (9+ satellites)
 * Uses golden angle distribution in HSL space for maximum distinction
 */
function generateExtendedColor(index: number): string {
  // Golden angle in degrees for optimal color distribution
  const goldenAngle = 137.508;
  // Start from a hue that doesn't conflict with base palette
  const baseHue = 200; // Starting point
  const hue = (baseHue + index * goldenAngle) % 360;
  // Keep saturation and lightness in optimal range for dark backgrounds
  const saturation = 65 + (index % 3) * 10; // 65-85%
  const lightness = 55 + (index % 2) * 10;  // 55-65%
  return hslToHex(hue, saturation, lightness);
}

function generateExtendedColorRgba(index: number): [number, number, number, number] {
  const goldenAngle = 137.508;
  const baseHue = 200;
  const hue = (baseHue + index * goldenAngle) % 360;
  const saturation = 65 + (index % 3) * 10;
  const lightness = 55 + (index % 2) * 10;
  return hslToRgba(hue, saturation, lightness);
}

/**
 * Get satellite color by index - handles any constellation size
 * @param index - Satellite index (0-based)
 * @returns Hex color string
 */
export function getSatelliteColorByIndex(index: number): string {
  if (index < SATELLITE_COLOR_PALETTE.length) {
    return SATELLITE_COLOR_PALETTE[index];
  }
  // Generate color for satellites beyond base palette
  return generateExtendedColor(index - SATELLITE_COLOR_PALETTE.length);
}

/**
 * Get satellite color RGBA by index - handles any constellation size
 * @param index - Satellite index (0-based)
 * @returns RGBA array [r, g, b, a]
 */
export function getSatelliteColorRgbaByIndex(index: number): [number, number, number, number] {
  if (index < SATELLITE_COLOR_PALETTE_RGBA.length) {
    return [...SATELLITE_COLOR_PALETTE_RGBA[index]] as [number, number, number, number];
  }
  return generateExtendedColorRgba(index - SATELLITE_COLOR_PALETTE_RGBA.length);
}

/**
 * Convert hex color to RGBA array
 */
export function hexToRgba(hex: string, alpha: number = 255): [number, number, number, number] {
  const cleanHex = hex.replace('#', '');
  return [
    parseInt(cleanHex.substring(0, 2), 16),
    parseInt(cleanHex.substring(2, 4), 16),
    parseInt(cleanHex.substring(4, 6), 16),
    alpha
  ];
}

/**
 * Get color with modified alpha
 */
export function withAlpha(rgba: [number, number, number, number], alpha: number): [number, number, number, number] {
  return [rgba[0], rgba[1], rgba[2], alpha];
}
