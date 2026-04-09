import type { MissionAnalyzeRunOrder } from '../api/mission'
import type { PreFeasibilityOrder } from '../store/preFeasibilityOrdersStore'
import type { MissionRunOrder } from '../types'
import { getOrderRecurrence } from './recurrence'

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

export function toMissionAnalyzeRunOrder(
  runOrder: MissionRunOrder,
): MissionAnalyzeRunOrder {
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
