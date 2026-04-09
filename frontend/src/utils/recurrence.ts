import type {
  OrderRecurrenceSettings,
  OrderTemplateRecord,
  OrderTemplateStatus,
  OrderType,
  RecurrenceWeekday,
  TargetData,
} from '../types'

const WEEKDAY_LABELS: Record<RecurrenceWeekday, string> = {
  mon: 'Mon',
  tue: 'Tue',
  wed: 'Wed',
  thu: 'Thu',
  fri: 'Fri',
  sat: 'Sat',
  sun: 'Sun',
}

export const WEEKDAY_OPTIONS: Array<{ value: RecurrenceWeekday; label: string }> = [
  { value: 'mon', label: 'Mon' },
  { value: 'tue', label: 'Tue' },
  { value: 'wed', label: 'Wed' },
  { value: 'thu', label: 'Thu' },
  { value: 'fri', label: 'Fri' },
  { value: 'sat', label: 'Sat' },
  { value: 'sun', label: 'Sun' },
]

export const DEFAULT_ORDER_RECURRENCE: OrderRecurrenceSettings = {
  recurrenceType: '',
  daysOfWeek: [],
  windowStart: '',
  windowEnd: '',
  timezone: 'UTC',
  effectiveStartDate: '',
  effectiveEndDate: '',
}

interface RecurrenceShape {
  orderType?: OrderType
  recurrence?: OrderRecurrenceSettings | null
}

export function getOrderRecurrence(
  recurrence?: OrderRecurrenceSettings | null,
): OrderRecurrenceSettings {
  return {
    ...DEFAULT_ORDER_RECURRENCE,
    ...recurrence,
    daysOfWeek: recurrence?.daysOfWeek ? [...recurrence.daysOfWeek] : [],
  }
}

export function getRecurrenceValidationIssues(
  orderType: OrderType | undefined,
  recurrence?: OrderRecurrenceSettings | null,
): string[] {
  if ((orderType ?? 'one_time') !== 'repeats') {
    return []
  }

  const current = getOrderRecurrence(recurrence)
  const issues: string[] = []

  if (!current.recurrenceType) {
    issues.push('Frequency is required')
  }
  if (!current.windowStart) {
    issues.push('Recurring orders require a time window start')
  }
  if (!current.windowEnd) {
    issues.push('Recurring orders require a time window end')
  }
  if (current.windowStart && current.windowEnd && current.windowStart === current.windowEnd) {
    issues.push('Recurring time window From and To must be different')
  }
  if (!current.effectiveStartDate) {
    issues.push('Recurring orders require an effective start date')
  }
  if (!current.effectiveEndDate) {
    issues.push('Recurring orders require an effective end date')
  }
  if (
    current.effectiveStartDate &&
    current.effectiveEndDate &&
    current.effectiveEndDate < current.effectiveStartDate
  ) {
    issues.push('Effective end date must be on or after the effective start date')
  }
  if (current.recurrenceType === 'weekly' && (!current.daysOfWeek || current.daysOfWeek.length === 0)) {
    issues.push('Weekly recurrence requires at least one weekday')
  }

  return issues
}

export function formatRecurrenceSummary({ orderType, recurrence }: RecurrenceShape): string | null {
  if ((orderType ?? 'one_time') !== 'repeats') {
    return null
  }

  const current = getOrderRecurrence(recurrence)
  if (!current.recurrenceType || !current.windowStart || !current.windowEnd) {
    return null
  }

  const timezoneSuffix =
    current.timezone?.trim() && current.timezone.trim().toUpperCase() !== 'UTC'
      ? ` ${current.timezone.trim()}`
      : ''

  if (current.recurrenceType === 'daily') {
    return `Daily ${current.windowStart}-${current.windowEnd}${timezoneSuffix}`
  }

  const dayLabels =
    current.daysOfWeek && current.daysOfWeek.length > 0
      ? current.daysOfWeek.map((day) => WEEKDAY_LABELS[day]).join('/')
      : 'Weekly'

  return `${dayLabels} ${current.windowStart}-${current.windowEnd}${timezoneSuffix}`
}

export function formatTemplateRecurrenceSummary(template?: OrderTemplateRecord | null): string | null {
  if (!template) {
    return null
  }

  return formatRecurrenceSummary({
    orderType: 'repeats',
    recurrence: {
      recurrenceType: template.recurrence_type,
      daysOfWeek: template.days_of_week ?? [],
      windowStart: template.window_start_hhmm,
      windowEnd: template.window_end_hhmm,
      timezone: template.timezone_name,
      effectiveStartDate: template.effective_start_date,
      effectiveEndDate: template.effective_end_date ?? '',
    },
  })
}

export interface HydratedRecurringOrder {
  id: string
  name: string
  createdAt: string
  targets: TargetData[]
  orderType: OrderType
  recurrence: OrderRecurrenceSettings
  templateIds: string[]
  templateStatus: OrderTemplateStatus | null
}

export function groupTemplatesIntoOrders(templates: OrderTemplateRecord[]): HydratedRecurringOrder[] {
  const activeTemplates = templates
    .filter((template) => template.status !== 'ended')
    .sort((left, right) => {
      const byCreated = left.created_at.localeCompare(right.created_at)
      if (byCreated !== 0) return byCreated
      return left.canonical_target_id.localeCompare(right.canonical_target_id)
    })

  const groups = new Map<string, HydratedRecurringOrder>()

  for (const template of activeTemplates) {
    const groupKey = [
      template.name,
      template.status,
      template.recurrence_type,
      (template.days_of_week ?? []).join(','),
      template.window_start_hhmm,
      template.window_end_hhmm,
      template.timezone_name,
      template.effective_start_date,
      template.effective_end_date ?? '',
    ].join('||')

    const existing = groups.get(groupKey)
    if (existing) {
      existing.targets.push({
        name: template.canonical_target_id,
        latitude: template.target_lat,
        longitude: template.target_lon,
        priority: template.priority,
        color: '#3B82F6',
      })
      existing.templateIds.push(template.id)
      continue
    }

    groups.set(groupKey, {
      id: `template-group-${template.id}`,
      name: template.name,
      createdAt: template.created_at,
      targets: [
        {
          name: template.canonical_target_id,
          latitude: template.target_lat,
          longitude: template.target_lon,
          priority: template.priority,
          color: '#3B82F6',
        },
      ],
      orderType: 'repeats',
      recurrence: {
        recurrenceType: template.recurrence_type,
        daysOfWeek: template.days_of_week ?? [],
        windowStart: template.window_start_hhmm,
        windowEnd: template.window_end_hhmm,
        timezone: template.timezone_name,
        effectiveStartDate: template.effective_start_date,
        effectiveEndDate: template.effective_end_date ?? '',
      },
      templateIds: [template.id],
      templateStatus: template.status,
    })
  }

  return Array.from(groups.values())
}
