/**
 * groundtrackSlicing
 *
 * Utility for temporally slicing a CZML ground-track entity's sampled positions
 * into a static Cartesian3 array covering only the schedule visible window
 * [tStartIso, tEndIso].
 *
 * The CZML generator writes ground-track positions at 2-minute intervals with
 * altitude = 0 (ellipsoid surface).  We sample the entity's SampledPositionProperty
 * at the same cadence so the sliced polyline matches the original arc exactly.
 *
 * PR-UI-034 additions:
 *  - Module-level position cache keyed by (entityId, tStartIso, tEndIso, sampleStep).
 *  - Point-count cap (GROUNDTRACK_MAX_POINTS_PER_SAT) with auto-step-increase.
 *  - Sample-step options constant and GroundtrackSampleStep union type.
 *  - invalidateGroundtrackCache() for datasource-swap invalidation.
 *  - _devGroundtrackStats mutable object read by ScheduleSatelliteLayers overlay (DEV only).
 */

import { JulianDate, Cartesian3, defined } from 'cesium'
import type { Entity } from 'cesium'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Default sampling cadence in seconds — must match backend czml_generator time_step (2 min). */
export const GROUNDTRACK_SAMPLE_STEP_SECONDS = 120

/** Valid sample-step values (seconds) exposed in the dev sample-step selector. */
export const GROUNDTRACK_SAMPLE_STEP_OPTIONS = [60, 120, 300] as const
export type GroundtrackSampleStep = (typeof GROUNDTRACK_SAMPLE_STEP_OPTIONS)[number]

/** Minimum debounce delay (ms) before rebuilding sliced polylines after a window change. */
export const SLICE_DEBOUNCE_MS = 300

/**
 * Maximum Cartesian3 points per satellite per rebuild.
 * When the requested step would exceed this limit the effective step is
 * automatically increased and a dev note is logged to _devGroundtrackStats.
 */
export const GROUNDTRACK_MAX_POINTS_PER_SAT = 2000

// ---------------------------------------------------------------------------
// Module-level position cache
// ---------------------------------------------------------------------------

interface CacheEntry {
  positions: Cartesian3[]
  effectiveStep: number
}

const _sliceCache = new Map<string, CacheEntry>()

/** Upper bound on cache entries before a full eviction sweep. */
const _MAX_CACHE_ENTRIES = 500

/**
 * Invalidate the entire position-slice cache.
 * Must be called whenever the CZML datasource is replaced so that stale
 * SampledPositionProperty references are not reused.
 */
export function invalidateGroundtrackCache(): void {
  _sliceCache.clear()
}

// ---------------------------------------------------------------------------
// Dev-only diagnostics
// ---------------------------------------------------------------------------

/**
 * Mutable diagnostics object written by the hook and read by the
 * ScheduleSatelliteLayers overlay (DEV builds only).
 *
 * Values are updated at the end of each Effect-2 timer callback.
 * The overlay reads them on its next render — no Zustand churn required.
 */
export const _devGroundtrackStats = {
  /** Running session totals across all rebuilds. */
  totalHits: 0,
  totalMisses: 0,
  /** Per-rebuild stats (reset at the start of each Effect-2 callback). */
  lastHits: 0,
  lastMisses: 0,
  /** Effective sampling step used in the most recent rebuild (may be auto-increased). */
  effectiveStep: GROUNDTRACK_SAMPLE_STEP_SECONDS as number,
  /** True when the point cap forced the step to be increased in the last rebuild. */
  capTriggered: false,
  capNote: null as string | null,
}

// ---------------------------------------------------------------------------
// Result type
// ---------------------------------------------------------------------------

export interface SliceResult {
  positions: Cartesian3[]
  /** Actual sampling interval used (may exceed the requested step when cap fires). */
  effectiveStep: number
  /** True when the point cap forced the step to be increased. */
  capTriggered: boolean
  /** True when positions were served from the module-level cache (no resampling done). */
  cacheHit: boolean
}

// ---------------------------------------------------------------------------
// Core utility
// ---------------------------------------------------------------------------

/**
 * Sample Cartesian3 positions from a ground-track entity's SampledPositionProperty
 * within the given [tStartIso, tEndIso] window.
 *
 * Results are cached by (entityId, tStartIso, tEndIso, sampleStep).
 * Call {@link invalidateGroundtrackCache} when the datasource is replaced.
 *
 * If the requested sampleStep would produce more than GROUNDTRACK_MAX_POINTS_PER_SAT
 * points, the effective step is automatically increased to stay within the cap.
 *
 * @param entity      - CZML entity whose `.position` is a SampledPositionProperty.
 * @param tStartIso   - Window start as ISO-8601 string.
 * @param tEndIso     - Window end as ISO-8601 string.
 * @param sampleStep  - Desired sampling interval in seconds (default 120 s).
 * @returns {@link SliceResult} with ≥ 2 positions, or `null` when sampling fails
 *          (no position property, invalid dates, or fewer than 2 valid samples).
 */
export function sliceGroundtrackPositions(
  entity: Entity,
  tStartIso: string,
  tEndIso: string,
  sampleStep: number = GROUNDTRACK_SAMPLE_STEP_SECONDS,
): SliceResult | null {
  if (!entity.position) return null

  const entityId = entity.id ?? ''
  const cacheKey = `${entityId}|${tStartIso}|${tEndIso}|${sampleStep}`

  // ── Cache hit ────────────────────────────────────────────────────────────
  const cached = _sliceCache.get(cacheKey)
  if (cached) {
    if (import.meta.env.DEV) {
      _devGroundtrackStats.totalHits++
    }
    return {
      positions: cached.positions,
      effectiveStep: cached.effectiveStep,
      // Re-derive: if the cached step differs from what was requested, the cap
      // was triggered when this entry was first computed.
      capTriggered: cached.effectiveStep !== sampleStep,
      cacheHit: true,
    }
  }

  // ── Cache miss — compute ─────────────────────────────────────────────────
  if (import.meta.env.DEV) {
    _devGroundtrackStats.totalMisses++
  }

  let start: JulianDate
  let end: JulianDate
  try {
    start = JulianDate.fromIso8601(tStartIso)
    end = JulianDate.fromIso8601(tEndIso)
  } catch {
    return null
  }

  const totalSeconds = JulianDate.secondsDifference(end, start)
  if (totalSeconds <= 0) return null

  // ── Cap: auto-increase step if estimated point count exceeds the maximum ──
  const estimatedPoints = Math.ceil(totalSeconds / sampleStep) + 1
  let effectiveStep = sampleStep
  let capTriggered = false

  if (estimatedPoints > GROUNDTRACK_MAX_POINTS_PER_SAT) {
    effectiveStep = Math.ceil(totalSeconds / (GROUNDTRACK_MAX_POINTS_PER_SAT - 1))
    capTriggered = true
  }

  // ── Sample positions ─────────────────────────────────────────────────────
  const positions: Cartesian3[] = []
  const t = new JulianDate()
  const scratch = new Cartesian3()

  // Walk from start → end in effectiveStep increments.
  // Cap each offset at totalSeconds so we don't overshoot the window end.
  for (let s = 0; s <= totalSeconds; s += effectiveStep) {
    JulianDate.addSeconds(start, Math.min(s, totalSeconds), t)
    const pos = entity.position.getValue(t, scratch)
    if (defined(pos)) {
      positions.push(Cartesian3.clone(pos))
    }
  }

  // Always include the exact window-end sample when totalSeconds is not a
  // whole multiple of effectiveStep.
  if (totalSeconds % effectiveStep !== 0) {
    const pos = entity.position.getValue(end, scratch)
    if (defined(pos)) {
      positions.push(Cartesian3.clone(pos))
    }
  }

  if (positions.length < 2) return null

  // ── Store in cache (with overflow guard) ─────────────────────────────────
  if (_sliceCache.size >= _MAX_CACHE_ENTRIES) {
    _sliceCache.clear()
  }
  _sliceCache.set(cacheKey, { positions, effectiveStep })

  return { positions, effectiveStep, capTriggered, cacheHit: false }
}
