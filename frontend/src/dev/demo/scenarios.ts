/**
 * Scalability scenario generator for the Demo Runner.
 *
 * Uses a seeded PRNG (mulberry32) so runs are deterministic and comparable.
 * Generates 1000 targets on a global grid with default priority 5.
 */

// ---------------------------------------------------------------------------
// Seeded PRNG — mulberry32
// ---------------------------------------------------------------------------

function mulberry32(seed: number): () => number {
  return () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// ---------------------------------------------------------------------------
// Target type
// ---------------------------------------------------------------------------

export interface ScaleTarget {
  name: string
  latitude: number
  longitude: number
  priority: number
}

// ---------------------------------------------------------------------------
// Global grid generator
// ---------------------------------------------------------------------------

/**
 * Generate `count` targets on a deterministic global grid.
 *
 * Strategy: evenly space rows of latitude between -60° and +60° (avoiding
 * poles where satellite passes are nearly polar and degenerate). Within each
 * row, distribute longitude points uniformly. A small seeded jitter is added
 * so targets don't sit on exact grid intersections.
 *
 * @param count   Number of targets (default 1000)
 * @param seed    PRNG seed (default 42)
 */
export function generateScalabilityTargets(count = 1000, seed = 42): ScaleTarget[] {
  const rng = mulberry32(seed)

  // Compute grid dimensions: roughly sqrt(count) rows
  const rows = Math.ceil(Math.sqrt(count))
  const cols = Math.ceil(count / rows)

  const latMin = -60
  const latMax = 60
  const lonMin = -180
  const lonMax = 180

  const latStep = (latMax - latMin) / (rows + 1)
  const lonStep = (lonMax - lonMin) / (cols + 1)

  const targets: ScaleTarget[] = []

  for (let r = 0; r < rows && targets.length < count; r++) {
    const baseLat = latMin + (r + 1) * latStep
    for (let c = 0; c < cols && targets.length < count; c++) {
      const baseLon = lonMin + (c + 1) * lonStep

      // Small jitter: ±0.5° lat, ±0.5° lon
      const jitterLat = (rng() - 0.5) * 1.0
      const jitterLon = (rng() - 0.5) * 1.0

      const lat = Math.round((baseLat + jitterLat) * 1e4) / 1e4
      const lon = Math.round((baseLon + jitterLon) * 1e4) / 1e4

      const idx = targets.length + 1
      targets.push({
        name: `SCALE_T${String(idx).padStart(4, '0')}`,
        latitude: Math.max(-90, Math.min(90, lat)),
        longitude: Math.max(-180, Math.min(180, lon)),
        priority: 5,
      })
    }
  }

  return targets
}

// ---------------------------------------------------------------------------
// Preset config
// ---------------------------------------------------------------------------

export const SCALABILITY_PRESET = {
  label: 'Scalability (1000 targets / 14 days / 50 sats)',
  targetCount: 1000,
  durationDays: 14,
  maxSatellites: 50,
  seed: 42,
} as const

// ---------------------------------------------------------------------------
// Satellite count presets (for quick switching in dev runner)
// ---------------------------------------------------------------------------

export const SAT_COUNT_OPTIONS = [10, 20, 50] as const
export type SatCountOption = (typeof SAT_COUNT_OPTIONS)[number]

// ---------------------------------------------------------------------------
// Dev thresholds config — PASS / WARN / FAIL gates
// ---------------------------------------------------------------------------

export interface DevThresholds {
  /** Wall time budget in seconds */
  maxWallTimeSec: number
  /** Response size: warn threshold in bytes */
  responseSizeWarnBytes: number
  /** Response size: fail threshold in bytes */
  responseSizeFailBytes: number
  /** Backend RSS: warn threshold in MB */
  rssWarnMb: number
  /** Backend RSS: fail threshold in MB (hard budget) */
  rssFailMb: number
  /** Risk score threshold — targets * sats * days above this triggers warning */
  riskScoreWarn: number
}

export const DEV_THRESHOLDS: DevThresholds = {
  maxWallTimeSec: 600,
  responseSizeWarnBytes: 100 * 1024 * 1024, // 100 MB
  responseSizeFailBytes: 250 * 1024 * 1024, // 250 MB
  rssWarnMb: 4096, // 4 GB
  rssFailMb: 6144, // 6 GB
  riskScoreWarn: 200_000, // targets * sats * days
}

// ---------------------------------------------------------------------------
// Risk estimation helpers
// ---------------------------------------------------------------------------

export function computeRiskScore(targets: number, sats: number, days: number): number {
  return targets * sats * days
}

export type ThresholdVerdict = 'PASS' | 'WARN' | 'FAIL'

export interface ThresholdResult {
  metric: string
  value: string
  threshold: string
  verdict: ThresholdVerdict
}

export function evaluateThresholds(
  wallTimeSec: number,
  responseBytes: number | null,
  rssMbAfter: number | null,
): ThresholdResult[] {
  const results: ThresholdResult[] = []

  // Wall time
  const wallVerdict: ThresholdVerdict =
    wallTimeSec > DEV_THRESHOLDS.maxWallTimeSec ? 'FAIL' : 'PASS'
  results.push({
    metric: 'Wall time',
    value: `${wallTimeSec.toFixed(1)}s`,
    threshold: `< ${DEV_THRESHOLDS.maxWallTimeSec}s`,
    verdict: wallVerdict,
  })

  // Response size
  if (responseBytes != null) {
    const mb = responseBytes / (1024 * 1024)
    let respVerdict: ThresholdVerdict = 'PASS'
    if (responseBytes >= DEV_THRESHOLDS.responseSizeFailBytes) respVerdict = 'FAIL'
    else if (responseBytes >= DEV_THRESHOLDS.responseSizeWarnBytes) respVerdict = 'WARN'
    results.push({
      metric: 'Response size',
      value: `${mb.toFixed(1)} MB`,
      threshold: `< ${(DEV_THRESHOLDS.responseSizeWarnBytes / (1024 * 1024)).toFixed(0)} MB warn / ${(DEV_THRESHOLDS.responseSizeFailBytes / (1024 * 1024)).toFixed(0)} MB fail`,
      verdict: respVerdict,
    })
  }

  // RSS
  if (rssMbAfter != null) {
    let rssVerdict: ThresholdVerdict = 'PASS'
    if (rssMbAfter >= DEV_THRESHOLDS.rssFailMb) rssVerdict = 'FAIL'
    else if (rssMbAfter >= DEV_THRESHOLDS.rssWarnMb) rssVerdict = 'WARN'
    results.push({
      metric: 'Backend RSS',
      value: `${rssMbAfter.toFixed(1)} MB`,
      threshold: `< ${DEV_THRESHOLDS.rssWarnMb} MB warn / ${DEV_THRESHOLDS.rssFailMb} MB fail`,
      verdict: rssVerdict,
    })
  }

  return results
}
