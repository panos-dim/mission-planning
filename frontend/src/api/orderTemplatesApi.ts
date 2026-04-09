import { apiClient } from './client'
import { API_ENDPOINTS } from './config'
import type {
  OrderTemplateRecord,
  OrderTemplateStatus,
  RecurrenceType,
  RecurrenceWeekday,
} from '../types'

function buildQuery(params: Record<string, string | number | undefined>): string {
  const searchParams = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.set(key, String(value))
    }
  }

  const queryString = searchParams.toString()
  return queryString ? `?${queryString}` : ''
}

export interface OrderTemplateCreatePayload {
  workspace_id: string
  name: string
  status?: OrderTemplateStatus
  canonical_target_id: string
  target_lat: number
  target_lon: number
  priority?: number
  constraints?: Record<string, unknown> | null
  requested_satellite_group?: string | null
  recurrence_type: RecurrenceType
  interval?: number
  days_of_week?: RecurrenceWeekday[] | null
  window_start_hhmm: string
  window_end_hhmm: string
  timezone_name: string
  effective_start_date: string
  effective_end_date?: string | null
  notes?: string | null
  external_ref?: string | null
}

export interface OrderTemplateUpdatePayload {
  name?: string
  status?: OrderTemplateStatus
  canonical_target_id?: string
  target_lat?: number
  target_lon?: number
  priority?: number
  constraints?: Record<string, unknown> | null
  requested_satellite_group?: string | null
  recurrence_type?: RecurrenceType
  interval?: number
  days_of_week?: RecurrenceWeekday[] | null
  window_start_hhmm?: string
  window_end_hhmm?: string
  timezone_name?: string
  effective_start_date?: string
  effective_end_date?: string | null
  notes?: string | null
  external_ref?: string | null
}

export interface OrderTemplateResponse {
  success: boolean
  template: OrderTemplateRecord
}

export interface OrderTemplateListResponse {
  success: boolean
  templates: OrderTemplateRecord[]
  total: number
}

export interface OrderTemplateDeleteResponse {
  success: boolean
  message: string
  template_deleted: boolean
}

export async function createOrderTemplate(
  payload: OrderTemplateCreatePayload,
): Promise<OrderTemplateResponse> {
  return apiClient.post<OrderTemplateResponse>(API_ENDPOINTS.ORDER_TEMPLATES, payload, {
    retries: 0,
  })
}

export async function listOrderTemplates(params?: {
  workspace_id?: string
  status?: OrderTemplateStatus
  limit?: number
  offset?: number
}): Promise<OrderTemplateListResponse> {
  const query = buildQuery({
    workspace_id: params?.workspace_id,
    status: params?.status,
    limit: params?.limit,
    offset: params?.offset,
  })

  return apiClient.get<OrderTemplateListResponse>(`${API_ENDPOINTS.ORDER_TEMPLATES}${query}`)
}

export async function getOrderTemplate(templateId: string): Promise<OrderTemplateResponse> {
  return apiClient.get<OrderTemplateResponse>(API_ENDPOINTS.ORDER_TEMPLATE_BY_ID(templateId))
}

export async function updateOrderTemplate(
  templateId: string,
  payload: OrderTemplateUpdatePayload,
): Promise<OrderTemplateResponse> {
  return apiClient.patch<OrderTemplateResponse>(
    API_ENDPOINTS.ORDER_TEMPLATE_BY_ID(templateId),
    payload,
    {
      retries: 0,
    },
  )
}

export async function deleteOrderTemplate(
  templateId: string,
): Promise<OrderTemplateDeleteResponse> {
  return apiClient.delete<OrderTemplateDeleteResponse>(API_ENDPOINTS.ORDER_TEMPLATE_BY_ID(templateId), {
    retries: 0,
  })
}
