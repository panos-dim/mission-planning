import type { MissionAnalyzeRunOrder } from '../api/mission'
import type { PreFeasibilityOrder } from '../store/preFeasibilityOrdersStore'
import type {
  MissionRunOrder,
  MissionRunOrderSummary,
  PlanningDemandAggregateSummary,
  PlanningDemandSummary,
} from '../types'
import { formatDateDDMMYYYY, formatDateTimeShort, normalizeTimestamp } from './date'
import { formatRecurrenceSummary, getOrderRecurrence } from './recurrence'

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

function formatUtcTime(iso: string): string {
  const normalized = normalizeTimestamp(iso) ?? iso.replace('+00:00', 'Z')
  const date = new Date(normalized)
  const hours = String(date.getUTCHours()).padStart(2, '0')
  const minutes = String(date.getUTCMinutes()).padStart(2, '0')
  return `${hours}:${minutes}`
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
  const start = demand.requested_window_start
  const end = demand.requested_window_end

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

  return 'Requested window unavailable'
}

export function getPlanningDemandPrimaryPassIndex(demand: PlanningDemandSummary): number | null {
  if (typeof demand.best_pass_index === 'number') {
    return demand.best_pass_index
  }

  return demand.matching_pass_indexes[0] ?? null
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
