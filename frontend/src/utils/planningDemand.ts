import type { MissionAnalyzeRunOrder } from '../api/mission'
import type { PreFeasibilityOrder } from '../store/preFeasibilityOrdersStore'
import type {
  MissionRunOrder,
  MissionRunOrderSummary,
  PassData,
  PlanningDemandAggregateSummary,
  PlanningDemandSummary,
} from '../types'
import { formatDateDDMMYYYY, formatDateTimeShort, normalizeTimestamp } from './date'
import { formatRecurrenceSummary, getOrderRecurrence } from './recurrence'

const MAX_DISTANCE_MS = Number.MAX_SAFE_INTEGER

export interface PlanningDemandAcquisitionLike {
  id?: string
  target_id: string
  start_time: string
  end_time?: string | null
}

export interface PlanningDemandStatusDisplay {
  label: 'Feasible' | 'Limited' | 'No opportunities'
  tone: 'blue' | 'amber' | 'red'
}

export interface PlanningDemandWindowDisplay {
  label: 'Requested Window' | 'Run Window'
  value: string
}

export function buildMissionRunOrder(order: PreFeasibilityOrder): MissionRunOrder {
  const recurrence = getOrderRecurrence(order.recurrence)
  const isRecurring = order.orderType === 'repeats'

  return {
    id: order.id,
    name: order.name.trim(),
    orderType: order.orderType ?? 'one_time',
    targets: order.targets.map((target, index) => ({
      canonicalTargetId: target.name.trim(),
      displayTargetName: target.name.trim(),
      templateId: order.templateIds?.[index] ?? null,
    })),
    recurrence: isRecurring
      ? {
          recurrenceType: recurrence.recurrenceType,
          interval: 1,
          daysOfWeek: recurrence.daysOfWeek ?? [],
          windowStart: recurrence.windowStart,
          windowEnd: recurrence.windowEnd,
          timezone: recurrence.timezone ?? 'UTC',
          effectiveStartDate: recurrence.effectiveStartDate,
          effectiveEndDate: recurrence.effectiveEndDate,
        }
      : null,
  }
}

export function toMissionAnalyzeRunOrder(runOrder: MissionRunOrder): MissionAnalyzeRunOrder {
  return {
    id: runOrder.id,
    name: runOrder.name,
    order_type: runOrder.orderType,
    targets: runOrder.targets.map((target) => ({
      canonical_target_id: target.canonicalTargetId,
      display_target_name: target.displayTargetName,
      template_id: target.templateId ?? null,
    })),
    recurrence:
      runOrder.orderType === 'repeats' && runOrder.recurrence?.recurrenceType
        ? {
            recurrence_type: runOrder.recurrence.recurrenceType,
            interval: runOrder.recurrence.interval ?? 1,
            days_of_week: runOrder.recurrence.daysOfWeek ?? [],
            window_start_hhmm: runOrder.recurrence.windowStart ?? '',
            window_end_hhmm: runOrder.recurrence.windowEnd ?? '',
            timezone_name: runOrder.recurrence.timezone ?? 'UTC',
            effective_start_date: runOrder.recurrence.effectiveStartDate ?? '',
            effective_end_date: runOrder.recurrence.effectiveEndDate ?? null,
          }
        : null,
  }
}

export interface GroupedPlanningDemand {
  id: string
  label: string
  localDate: string | null
  demands: PlanningDemandSummary[]
}

function compareNullableStrings(left?: string | null, right?: string | null): number {
  if (!left && !right) return 0
  if (!left) return 1
  if (!right) return -1
  return left.localeCompare(right)
}

function parseTimestampMs(value?: string | null): number | null {
  const normalized = normalizeTimestamp(value)
  if (!normalized) return null
  const ms = new Date(normalized).getTime()
  return Number.isNaN(ms) ? null : ms
}

function normalizeDemandTarget(value?: string | null): string {
  return value?.trim() ?? ''
}

function isTimestampWithinWindow(
  timeIso?: string | null,
  windowStartIso?: string | null,
  windowEndIso?: string | null,
): boolean {
  const timeMs = parseTimestampMs(timeIso)
  if (timeMs === null) return false

  const startMs = parseTimestampMs(windowStartIso)
  const endMs = parseTimestampMs(windowEndIso)

  if (startMs !== null && timeMs < startMs) return false
  if (endMs !== null && timeMs > endMs) return false

  return startMs !== null || endMs !== null
}

function getWindowDistanceMs(
  timeIso?: string | null,
  windowStartIso?: string | null,
  windowEndIso?: string | null,
): number {
  const timeMs = parseTimestampMs(timeIso)
  if (timeMs === null) return MAX_DISTANCE_MS

  const startMs = parseTimestampMs(windowStartIso)
  const endMs = parseTimestampMs(windowEndIso)

  if (startMs === null && endMs === null) return MAX_DISTANCE_MS
  if (startMs !== null && endMs !== null) {
    if (timeMs >= startMs && timeMs <= endMs) return 0
    return timeMs < startMs ? startMs - timeMs : timeMs - endMs
  }
  if (startMs !== null) return Math.max(0, startMs - timeMs)
  return Math.max(0, timeMs - (endMs ?? timeMs))
}

function getClosestAnchorDistanceMs(
  demand: PlanningDemandSummary,
  timeIso?: string | null,
): number {
  const timeMs = parseTimestampMs(timeIso)
  if (timeMs === null) return MAX_DISTANCE_MS

  const anchorCandidates = [
    demand.best_pass_start,
    demand.best_pass_end,
    demand.first_pass_start,
    demand.last_pass_end,
    demand.requested_window_start,
    demand.requested_window_end,
  ]
    .map((value) => parseTimestampMs(value))
    .filter((value): value is number => value !== null)

  if (anchorCandidates.length === 0) return MAX_DISTANCE_MS

  return anchorCandidates.reduce((best, candidateMs) => {
    const distance = Math.abs(candidateMs - timeMs)
    return distance < best ? distance : best
  }, MAX_DISTANCE_MS)
}

function compareCandidateRanks(
  left: {
    preferred: boolean
    explicitPassMatch: boolean
    insideRequestedWindow: boolean
    insideFeasibleWindow: boolean
    feasible: boolean
    distanceToRequestedWindowMs: number
    distanceToAnchorMs: number
    priority: number
  },
  right: {
    preferred: boolean
    explicitPassMatch: boolean
    insideRequestedWindow: boolean
    insideFeasibleWindow: boolean
    feasible: boolean
    distanceToRequestedWindowMs: number
    distanceToAnchorMs: number
    priority: number
  },
): number {
  if (left.preferred !== right.preferred) return left.preferred ? -1 : 1
  if (left.explicitPassMatch !== right.explicitPassMatch) {
    return left.explicitPassMatch ? -1 : 1
  }
  if (left.insideRequestedWindow !== right.insideRequestedWindow) {
    return left.insideRequestedWindow ? -1 : 1
  }
  if (left.insideFeasibleWindow !== right.insideFeasibleWindow) {
    return left.insideFeasibleWindow ? -1 : 1
  }
  if (left.feasible !== right.feasible) return left.feasible ? -1 : 1
  if (left.distanceToRequestedWindowMs !== right.distanceToRequestedWindowMs) {
    return left.distanceToRequestedWindowMs - right.distanceToRequestedWindowMs
  }
  if (left.distanceToAnchorMs !== right.distanceToAnchorMs) {
    return left.distanceToAnchorMs - right.distanceToAnchorMs
  }
  return left.priority - right.priority
}

function formatUtcTime(iso: string): string {
  const normalized = normalizeTimestamp(iso) ?? iso.replace('+00:00', 'Z')
  const date = new Date(normalized)
  const hours = String(date.getUTCHours()).padStart(2, '0')
  const minutes = String(date.getUTCMinutes()).padStart(2, '0')
  return `${hours}:${minutes}`
}

function formatIsoWindow(
  start?: string | null,
  end?: string | null,
  fallback = 'Requested window unavailable',
): string {
  if (start && end) {
    const normalizedStart = normalizeTimestamp(start) ?? start.replace('+00:00', 'Z')
    const normalizedEnd = normalizeTimestamp(end) ?? end.replace('+00:00', 'Z')
    const startDate = new Date(normalizedStart)
    const endDate = new Date(normalizedEnd)
    const sameUtcDay =
      startDate.getUTCFullYear() === endDate.getUTCFullYear() &&
      startDate.getUTCMonth() === endDate.getUTCMonth() &&
      startDate.getUTCDate() === endDate.getUTCDate()

    if (sameUtcDay) {
      return `${formatDateDDMMYYYY(normalizedStart)} ${formatUtcTime(normalizedStart)}-${formatUtcTime(normalizedEnd)} UTC`
    }

    return `${formatDateTimeShort(normalizedStart)} to ${formatDateTimeShort(normalizedEnd)}`
  }

  if (start) {
    return formatDateTimeShort(start)
  }

  if (end) {
    return formatDateTimeShort(end)
  }

  return fallback
}

export function getPlanningDemandTargetId(demand: PlanningDemandSummary): string {
  return normalizeDemandTarget(demand.canonical_target_id || demand.display_target_name)
}

export function matchesPlanningDemandTarget(
  demand: PlanningDemandSummary,
  targetId?: string | null,
): boolean {
  const normalizedTargetId = normalizeDemandTarget(targetId)
  if (!normalizedTargetId) return false
  return (
    getPlanningDemandTargetId(demand) === normalizedTargetId ||
    normalizeDemandTarget(demand.display_target_name) === normalizedTargetId
  )
}

export function getPlanningDemandStatusDisplay(
  demand: PlanningDemandSummary,
): PlanningDemandStatusDisplay {
  if (
    demand.feasibility_status === 'limited' ||
    (!demand.has_feasible_pass && demand.matching_pass_count > 0)
  ) {
    return { label: 'Limited', tone: 'amber' }
  }

  if (demand.has_feasible_pass || demand.feasibility_status === 'feasible') {
    return { label: 'Feasible', tone: 'blue' }
  }

  return { label: 'No opportunities', tone: 'red' }
}

export function getPlanningDemandInstanceDateLabel(
  demand: PlanningDemandSummary,
): string | null {
  if (demand.local_date?.trim()) {
    return formatDateDDMMYYYY(`${demand.local_date.trim()}T00:00:00Z`)
  }

  const rawInstanceKey = demand.instance_key?.trim()
  if (!rawInstanceKey) return null

  if (/^\d{4}-\d{2}-\d{2}$/.test(rawInstanceKey)) {
    return formatDateDDMMYYYY(`${rawInstanceKey}T00:00:00Z`)
  }

  const normalizedInstance = normalizeTimestamp(rawInstanceKey)
  return normalizedInstance ? formatDateDDMMYYYY(normalizedInstance) : null
}

export function getPlanningDemandWindowDisplay(
  demand: PlanningDemandSummary,
  missionWindow?: {
    start?: string | null
    end?: string | null
  },
): PlanningDemandWindowDisplay {
  if (demand.requested_window_start || demand.requested_window_end) {
    return {
      label: 'Requested Window',
      value: formatPlanningDemandWindow(demand),
    }
  }

  if (demand.demand_type === 'one_time') {
    return {
      label: 'Run Window',
      value: formatIsoWindow(
        missionWindow?.start,
        missionWindow?.end,
        'Run-derived window unavailable',
      ),
    }
  }

  return {
    label: 'Requested Window',
    value: 'Requested window unavailable',
  }
}

export function getPlanningDemandCounts(
  planningDemands: PlanningDemandSummary[],
  summary?: PlanningDemandAggregateSummary | null,
): PlanningDemandAggregateSummary {
  if (summary) {
    return summary
  }

  const feasibleDemands = planningDemands.filter((demand) => demand.has_feasible_pass).length
  const oneTimeDemands = planningDemands.filter(
    (demand) => demand.demand_type === 'one_time',
  ).length
  const recurringInstanceDemands = planningDemands.filter(
    (demand) => demand.demand_type === 'recurring_instance',
  ).length

  return {
    run_order_id: planningDemands[0]?.run_order_id ?? '',
    total_demands: planningDemands.length,
    feasible_demands: feasibleDemands,
    infeasible_demands: planningDemands.length - feasibleDemands,
    one_time_demands: oneTimeDemands,
    recurring_instance_demands: recurringInstanceDemands,
  }
}

export function formatRunOrderRecurrenceSummary(
  runOrder?: MissionRunOrderSummary | null,
): string | null {
  if (!runOrder?.recurrence) {
    return null
  }

  return formatRecurrenceSummary({
    orderType: runOrder.order_type,
    recurrence: {
      recurrenceType: runOrder.recurrence.recurrence_type,
      daysOfWeek: runOrder.recurrence.days_of_week ?? [],
      windowStart: runOrder.recurrence.window_start_hhmm,
      windowEnd: runOrder.recurrence.window_end_hhmm,
      timezone: runOrder.recurrence.timezone_name,
      effectiveStartDate: runOrder.recurrence.effective_start_date,
      effectiveEndDate: runOrder.recurrence.effective_end_date ?? '',
    },
  })
}

export function formatPlanningDemandWindow(demand: PlanningDemandSummary): string {
  return formatIsoWindow(demand.requested_window_start, demand.requested_window_end)
}

export function getPlanningDemandPrimaryPassIndex(demand: PlanningDemandSummary): number | null {
  if (typeof demand.best_pass_index === 'number') {
    return demand.best_pass_index
  }

  return demand.matching_pass_indexes[0] ?? null
}

export function getPlanningDemandBestPass(
  demand: PlanningDemandSummary,
  passes: PassData[],
): { pass: PassData; passIndex: number } | null {
  const passIndex = getPlanningDemandPrimaryPassIndex(demand)
  if (passIndex === null || passIndex < 0 || passIndex >= passes.length) {
    return null
  }

  const pass = passes[passIndex]
  return pass ? { pass, passIndex } : null
}

export function getPassOffNadirAngle(pass?: Pick<PassData, 'off_nadir_deg' | 'max_elevation'> | null): number | null {
  if (!pass) return null
  if (typeof pass.off_nadir_deg === 'number') return pass.off_nadir_deg
  if (typeof pass.max_elevation === 'number') return 90 - pass.max_elevation
  return null
}

export function doesAcquisitionMatchPlanningDemand(
  demand: PlanningDemandSummary,
  acquisition: PlanningDemandAcquisitionLike,
): boolean {
  if (!matchesPlanningDemandTarget(demand, acquisition.target_id)) {
    return false
  }

  if (
    isTimestampWithinWindow(
      acquisition.start_time,
      demand.requested_window_start,
      demand.requested_window_end,
    ) ||
    isTimestampWithinWindow(acquisition.start_time, demand.best_pass_start, demand.best_pass_end) ||
    isTimestampWithinWindow(acquisition.start_time, demand.first_pass_start, demand.last_pass_end)
  ) {
    return true
  }

  return demand.demand_type === 'one_time'
}

export function findPlanningDemandById(
  planningDemands: PlanningDemandSummary[],
  demandId?: string | null,
): PlanningDemandSummary | null {
  if (!demandId) return null
  return planningDemands.find((demand) => demand.demand_id === demandId) ?? null
}

export function findPlanningDemandForPass(params: {
  planningDemands: PlanningDemandSummary[]
  passIndex?: number | null
  targetId?: string | null
  passStartTime?: string | null
  preferredDemandId?: string | null
}): PlanningDemandSummary | null {
  const { planningDemands, passIndex, targetId, passStartTime, preferredDemandId } = params

  const candidates = planningDemands.filter((demand) => matchesPlanningDemandTarget(demand, targetId))
  if (candidates.length === 0) return null
  if (candidates.length === 1) return candidates[0]

  return [...candidates].sort((left, right) => {
    const leftRank = {
      preferred: left.demand_id === preferredDemandId,
      explicitPassMatch:
        typeof passIndex === 'number' &&
        (left.best_pass_index === passIndex || left.matching_pass_indexes.includes(passIndex)),
      insideRequestedWindow: isTimestampWithinWindow(
        passStartTime,
        left.requested_window_start,
        left.requested_window_end,
      ),
      insideFeasibleWindow:
        isTimestampWithinWindow(passStartTime, left.best_pass_start, left.best_pass_end) ||
        isTimestampWithinWindow(passStartTime, left.first_pass_start, left.last_pass_end),
      feasible: left.has_feasible_pass,
      distanceToRequestedWindowMs: getWindowDistanceMs(
        passStartTime,
        left.requested_window_start,
        left.requested_window_end,
      ),
      distanceToAnchorMs: getClosestAnchorDistanceMs(left, passStartTime),
      priority: left.priority,
    }
    const rightRank = {
      preferred: right.demand_id === preferredDemandId,
      explicitPassMatch:
        typeof passIndex === 'number' &&
        (right.best_pass_index === passIndex || right.matching_pass_indexes.includes(passIndex)),
      insideRequestedWindow: isTimestampWithinWindow(
        passStartTime,
        right.requested_window_start,
        right.requested_window_end,
      ),
      insideFeasibleWindow:
        isTimestampWithinWindow(passStartTime, right.best_pass_start, right.best_pass_end) ||
        isTimestampWithinWindow(passStartTime, right.first_pass_start, right.last_pass_end),
      feasible: right.has_feasible_pass,
      distanceToRequestedWindowMs: getWindowDistanceMs(
        passStartTime,
        right.requested_window_start,
        right.requested_window_end,
      ),
      distanceToAnchorMs: getClosestAnchorDistanceMs(right, passStartTime),
      priority: right.priority,
    }

    const rankDelta = compareCandidateRanks(leftRank, rightRank)
    if (rankDelta !== 0) return rankDelta
    return left.display_target_name.localeCompare(right.display_target_name)
  })[0]
}

export function findPlanningDemandForAcquisition(params: {
  planningDemands: PlanningDemandSummary[]
  acquisition?: PlanningDemandAcquisitionLike | null
  preferredDemandId?: string | null
}): PlanningDemandSummary | null {
  const { planningDemands, acquisition, preferredDemandId } = params
  if (!acquisition) return null

  const candidates = planningDemands.filter((demand) =>
    matchesPlanningDemandTarget(demand, acquisition.target_id),
  )
  if (candidates.length === 0) return null
  if (candidates.length === 1) return candidates[0]

  return [...candidates].sort((left, right) => {
    const leftRank = {
      preferred: left.demand_id === preferredDemandId,
      explicitPassMatch: false,
      insideRequestedWindow: isTimestampWithinWindow(
        acquisition.start_time,
        left.requested_window_start,
        left.requested_window_end,
      ),
      insideFeasibleWindow:
        isTimestampWithinWindow(
          acquisition.start_time,
          left.best_pass_start,
          left.best_pass_end,
        ) ||
        isTimestampWithinWindow(acquisition.start_time, left.first_pass_start, left.last_pass_end),
      feasible: left.has_feasible_pass,
      distanceToRequestedWindowMs: getWindowDistanceMs(
        acquisition.start_time,
        left.requested_window_start,
        left.requested_window_end,
      ),
      distanceToAnchorMs: getClosestAnchorDistanceMs(left, acquisition.start_time),
      priority: left.priority,
    }
    const rightRank = {
      preferred: right.demand_id === preferredDemandId,
      explicitPassMatch: false,
      insideRequestedWindow: isTimestampWithinWindow(
        acquisition.start_time,
        right.requested_window_start,
        right.requested_window_end,
      ),
      insideFeasibleWindow:
        isTimestampWithinWindow(
          acquisition.start_time,
          right.best_pass_start,
          right.best_pass_end,
        ) ||
        isTimestampWithinWindow(
          acquisition.start_time,
          right.first_pass_start,
          right.last_pass_end,
        ),
      feasible: right.has_feasible_pass,
      distanceToRequestedWindowMs: getWindowDistanceMs(
        acquisition.start_time,
        right.requested_window_start,
        right.requested_window_end,
      ),
      distanceToAnchorMs: getClosestAnchorDistanceMs(right, acquisition.start_time),
      priority: right.priority,
    }

    const rankDelta = compareCandidateRanks(leftRank, rightRank)
    if (rankDelta !== 0) return rankDelta
    return left.display_target_name.localeCompare(right.display_target_name)
  })[0]
}

export function getPlanningDemandMatchingAcquisitions<T extends PlanningDemandAcquisitionLike>(
  demand: PlanningDemandSummary,
  acquisitions: T[],
): T[] {
  const directMatches = acquisitions.filter((acquisition) =>
    doesAcquisitionMatchPlanningDemand(demand, acquisition),
  )

  if (directMatches.length > 0 || demand.demand_type === 'recurring_instance') {
    return directMatches
  }

  return acquisitions.filter((acquisition) =>
    matchesPlanningDemandTarget(demand, acquisition.target_id),
  )
}

export function groupPlanningDemandsByDate(
  planningDemands: PlanningDemandSummary[],
): GroupedPlanningDemand[] {
  if (planningDemands.length === 0) {
    return []
  }

  const hasOnlyOneTimeDemands = planningDemands.every((demand) => !demand.local_date)
  const groups = new Map<string, PlanningDemandSummary[]>()

  for (const demand of planningDemands) {
    const key = demand.local_date?.trim() || '__current_run__'
    const existing = groups.get(key)
    if (existing) {
      existing.push(demand)
    } else {
      groups.set(key, [demand])
    }
  }

  return Array.from(groups.entries())
    .sort(([left], [right]) => {
      if (left === '__current_run__' && right === '__current_run__') return 0
      if (left === '__current_run__') return -1
      if (right === '__current_run__') return 1
      return left.localeCompare(right)
    })
    .map(([key, demands]) => ({
      id: key,
      label:
        key === '__current_run__'
          ? hasOnlyOneTimeDemands
            ? 'One-time demands'
            : 'Current run'
          : formatDateDDMMYYYY(`${key}T00:00:00Z`),
      localDate: key === '__current_run__' ? null : key,
      demands: [...demands].sort((left, right) => {
        const byWindow = compareNullableStrings(
          left.requested_window_start,
          right.requested_window_start,
        )
        if (byWindow !== 0) return byWindow

        const byName = left.display_target_name.localeCompare(right.display_target_name)
        if (byName !== 0) return byName

        return left.priority - right.priority
      }),
    }))
}
