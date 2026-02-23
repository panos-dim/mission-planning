/**
 * Satellite Color Registry — Single Source of Truth
 *
 * Deterministic satellite_id → color mapping using stable hashing.
 * Colors are consistent across reloads and sessions for the same satellite ID.
 *
 * Uses the colorblind-safe Okabe-Ito-inspired palette from constants/colors.ts.
 * For constellations exceeding the base palette, generates additional colors
 * algorithmically using golden-angle HSL distribution.
 */

import { Color } from 'cesium'
import {
  SATELLITE_COLOR_PALETTE,
  getSatelliteColorByIndex,
  getSatelliteColorRgbaByIndex,
} from '../constants/colors'

// ---------------------------------------------------------------------------
// Deterministic hash: satellite_id → stable integer
// ---------------------------------------------------------------------------

/**
 * djb2 hash — fast, deterministic, good distribution for short strings.
 * Returns a non-negative 32-bit integer.
 */
function djb2Hash(str: string): number {
  let hash = 5381
  for (let i = 0; i < str.length; i++) {
    // hash * 33 + charCode
    hash = ((hash << 5) + hash + str.charCodeAt(i)) | 0
  }
  return Math.abs(hash)
}

// ---------------------------------------------------------------------------
// Registry (module-level singleton)
// ---------------------------------------------------------------------------

/** Cached mappings: satellite_id → palette index */
const idToIndex = new Map<string, number>()

/** Ordered list of registered satellite IDs (insertion order = palette order) */
const registeredIds: string[] = []

/**
 * Ensure a satellite ID is registered and return its palette index.
 *
 * When satellites are registered in bulk via `registerSatellites()`, their
 * indices follow insertion order (matching the backend palette assignment).
 * For ad-hoc lookups on unregistered IDs, a deterministic hash is used.
 */
function ensureIndex(satId: string): number {
  const existing = idToIndex.get(satId)
  if (existing !== undefined) return existing

  // Fallback: deterministic hash into palette space
  const idx = djb2Hash(satId) % Math.max(SATELLITE_COLOR_PALETTE.length, 8)
  idToIndex.set(satId, idx)
  registeredIds.push(satId)
  return idx
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Bulk-register satellite IDs so palette indices match the backend ordering.
 * Call this once when mission data / CZML loads.
 *
 * If the same set is registered again, it's a no-op.
 */
export function registerSatellites(satIds: string[]): void {
  // Only re-register if the set has actually changed
  const alreadyRegistered = satIds.every((id) => idToIndex.has(id))
  if (alreadyRegistered && satIds.length === registeredIds.length) return

  // Clear and re-register in order
  idToIndex.clear()
  registeredIds.length = 0

  satIds.forEach((id, idx) => {
    idToIndex.set(id, idx)
    registeredIds.push(id)
  })
}

/**
 * Get Cesium Color for a satellite ID.
 */
export function getSatColor(satId: string): Color {
  const idx = ensureIndex(satId)
  const [r, g, b, a] = getSatelliteColorRgbaByIndex(idx)
  return new Color(r / 255, g / 255, b / 255, a / 255)
}

/**
 * Get Cesium Color with custom alpha for a satellite ID.
 */
export function getSatColorWithAlpha(satId: string, alpha: number): Color {
  const idx = ensureIndex(satId)
  const [r, g, b] = getSatelliteColorRgbaByIndex(idx)
  return new Color(r / 255, g / 255, b / 255, alpha)
}

/**
 * Get CSS hex color string for a satellite ID.
 */
export function getSatCssColor(satId: string): string {
  const idx = ensureIndex(satId)
  return getSatelliteColorByIndex(idx)
}

/**
 * Get RGBA array [r, g, b, a] (0-255) for a satellite ID.
 */
export function getSatRgba(satId: string): [number, number, number, number] {
  const idx = ensureIndex(satId)
  return getSatelliteColorRgbaByIndex(idx)
}

/**
 * Get all currently registered satellite → color mappings.
 * Useful for legend rendering.
 */
export function getRegisteredSatelliteColors(): Array<{
  satId: string
  cssColor: string
  cesiumColor: Color
}> {
  return registeredIds.map((satId) => ({
    satId,
    cssColor: getSatCssColor(satId),
    cesiumColor: getSatColor(satId),
  }))
}

/**
 * Extract a human-readable satellite name from a satellite entity ID.
 * Handles patterns like "sat_ICEYE-X7" → "ICEYE-X7".
 */
export function satIdToDisplayName(satId: string): string {
  return satId.replace(/^sat_/, '')
}

/**
 * Clear the registry. Call when switching scenarios / clearing mission.
 */
export function clearSatelliteColorRegistry(): void {
  idToIndex.clear()
  registeredIds.length = 0
}
