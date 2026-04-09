import { queryClient, queryKeys } from '../lib/queryClient'
import type { OrderTemplateStatus } from '../types'
import {
  createOrderTemplate,
  deleteOrderTemplate,
  updateOrderTemplate,
} from '../api/orderTemplatesApi'
import { isApiError } from '../api'
import { getOrderRecurrence } from './recurrence'

export interface RecurringOrderSyncInput {
  id: string
  name: string
  targets: Array<{
    name: string
    latitude: number
    longitude: number
    priority?: number
  }>
  recurrence?: {
    recurrenceType?: 'daily' | 'weekly' | ''
    daysOfWeek?: Array<'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun'>
    windowStart?: string
    windowEnd?: string
    effectiveStartDate?: string
    effectiveEndDate?: string
  } | null
  templateIds?: string[]
  templateStatus?: OrderTemplateStatus | null
}

export function getTemplateMutationErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    const detail =
      typeof error.data === 'object' &&
      error.data !== null &&
      'detail' in error.data &&
      typeof (error.data as { detail?: unknown }).detail === 'string'
        ? ((error.data as { detail?: string }).detail ?? null)
        : null

    return detail || error.message
  }

  return error instanceof Error ? error.message : 'Unexpected recurrence error'
}

export async function retireTemplateIds(templateIds: string[]) {
  for (const templateId of templateIds) {
    try {
      await deleteOrderTemplate(templateId)
    } catch (error) {
      if (isApiError(error) && error.status === 409) {
        await updateOrderTemplate(templateId, { status: 'ended' })
        continue
      }
      throw error
    }
  }
}

export async function syncRecurringTemplatesForOrder(
  order: RecurringOrderSyncInput,
  workspaceId: string,
): Promise<{ templateIds: string[]; templateStatus: OrderTemplateStatus | null }> {
  const recurrence = getOrderRecurrence(order.recurrence)
  const existingTemplateIds = order.templateIds ?? []
  const nextTemplateIds: string[] = []
  let nextStatus: OrderTemplateStatus | null = order.templateStatus ?? 'active'

  for (const [index, target] of order.targets.entries()) {
    const payload = {
      name: order.name.trim(),
      canonical_target_id: target.name.trim(),
      target_lat: target.latitude,
      target_lon: target.longitude,
      priority: target.priority ?? 5,
      recurrence_type: recurrence.recurrenceType as 'daily' | 'weekly',
      interval: 1,
      days_of_week: recurrence.recurrenceType === 'weekly' ? recurrence.daysOfWeek ?? [] : null,
      window_start_hhmm: recurrence.windowStart ?? '',
      window_end_hhmm: recurrence.windowEnd ?? '',
      timezone_name: 'UTC',
      effective_start_date: recurrence.effectiveStartDate ?? '',
      effective_end_date: recurrence.effectiveEndDate ?? '',
    }

    const existingTemplateId = existingTemplateIds[index]
    if (existingTemplateId) {
      const response = await updateOrderTemplate(existingTemplateId, payload)
      nextTemplateIds.push(response.template.id)
      nextStatus = response.template.status
      continue
    }

    const response = await createOrderTemplate({
      workspace_id: workspaceId,
      status: order.templateStatus ?? 'active',
      ...payload,
    })
    nextTemplateIds.push(response.template.id)
    nextStatus = response.template.status
  }

  const retiredTemplateIds = existingTemplateIds.slice(order.targets.length)
  if (retiredTemplateIds.length > 0) {
    await retireTemplateIds(retiredTemplateIds)
  }

  await queryClient.invalidateQueries({
    queryKey: queryKeys.orderTemplates.list(workspaceId),
  })

  return {
    templateIds: nextTemplateIds,
    templateStatus: nextStatus,
  }
}
