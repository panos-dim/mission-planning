/**
 * Pre-Feasibility Order Store
 *
 * Zustand store for managing the single run-level order BEFORE feasibility analysis.
 * The order contains many targets. When feasibility is run, that order's targets
 * are sent to the backend.
 *
 * This is distinct from the post-planning ordersStore (AcceptedOrder).
 */

import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import type {
  OrderRecurrenceSettings,
  OrderTemplateStatus,
  OrderType,
  TargetData,
} from '../types'
import {
  DEFAULT_ORDER_RECURRENCE,
  getOrderRecurrence,
  getRecurrenceValidationIssues,
} from '../utils/recurrence'

// =============================================================================
// Types
// =============================================================================

export interface PreFeasibilityOrder {
  /** Stable client-side ID (uuid-like) */
  id: string
  /** User-editable order name (compulsory, non-empty) */
  name: string
  /** Targets belonging to this order */
  targets: TargetData[]
  /** ISO timestamp */
  createdAt: string
  /** One-time orders follow the legacy local flow; recurring orders sync templates */
  orderType?: OrderType
  /** Compact recurrence authoring state for template-backed orders */
  recurrence?: OrderRecurrenceSettings
  /** Backend template IDs aligned with target order when recurrence is saved */
  templateIds?: string[]
  /** Shared status for hydrated backend templates */
  templateStatus?: OrderTemplateStatus | null
}

interface PreFeasibilityOrderState {
  /** Single run-level order authored in Feasibility Analysis */
  order: PreFeasibilityOrder | null
  /** Which order receives map-click / file-upload targets */
  activeOrderId: string | null
}

interface PreFeasibilityOrdersActions {
  /** Create the single run-level order if missing; returns its ID */
  createOrder: () => string
  /** Remove an order by ID */
  removeOrder: (orderId: string) => void
  /** Update order name */
  renameOrder: (orderId: string, name: string) => void
  /** Toggle between one-time and recurring authoring */
  setOrderType: (orderId: string, orderType: OrderType) => void
  /** Update recurrence settings for a recurring order */
  updateOrderRecurrence: (orderId: string, updates: Partial<OrderRecurrenceSettings>) => void
  /** Update backend template bindings for a recurring order */
  setOrderTemplateState: (
    orderId: string,
    updates: { templateIds?: string[]; templateStatus?: OrderTemplateStatus | null },
  ) => void
  /** Add a target to a specific order */
  addTarget: (orderId: string, target: TargetData) => void
  /** Remove a target from an order by index */
  removeTarget: (orderId: string, targetIndex: number) => void
  /** Update a target within an order */
  updateTarget: (orderId: string, targetIndex: number, updates: Partial<TargetData>) => void
  /** Replace all targets in the order (e.g. from file upload or samples) */
  setOrderTargets: (orderId: string, targets: TargetData[]) => void
  /** Get all targets from the single run-level order */
  getAllTargets: () => TargetData[]
  /** Clear the run-level order */
  clearAll: () => void
  /** Replace the run-level order, typically after hydrating recurring templates */
  replaceOrder: (order: PreFeasibilityOrder | null) => void
  /** Set which order is active for receiving targets (map-click, upload) */
  setActiveOrder: (orderId: string | null) => void
  /** Append multiple targets to an order (e.g. from file upload or samples) */
  addTargets: (orderId: string, targets: TargetData[]) => void
  /** Validation: returns list of issues (empty = valid) */
  validate: () => string[]
}

// =============================================================================
// Helpers
// =============================================================================

function generateId(): string {
  return `order_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

function createDefaultOrder(): PreFeasibilityOrder {
  return {
    id: generateId(),
    name: 'Order 1',
    targets: [],
    createdAt: new Date().toISOString(),
    orderType: 'one_time',
    recurrence: { ...DEFAULT_ORDER_RECURRENCE },
    templateIds: [],
    templateStatus: null,
  }
}

function normalizeOrder(order: PreFeasibilityOrder): PreFeasibilityOrder {
  return {
    ...order,
    orderType: order.orderType ?? 'one_time',
    recurrence: getOrderRecurrence(order.recurrence),
    templateIds: [...(order.templateIds ?? [])],
    templateStatus: order.templateStatus ?? null,
    targets: [...order.targets],
  }
}

export function mergePreFeasibilityOrders(
  orders: Array<PreFeasibilityOrder | null | undefined>,
): PreFeasibilityOrder | null {
  const normalizedOrders = orders
    .filter((order): order is PreFeasibilityOrder => Boolean(order))
    .map((order) => normalizeOrder(order))

  if (normalizedOrders.length === 0) {
    return null
  }

  const recurringSource =
    normalizedOrders.find(
      (candidate) =>
        candidate.orderType === 'repeats' || (candidate.templateIds?.length ?? 0) > 0,
    ) ?? null
  const primaryOrder = recurringSource ?? normalizedOrders[0]
  const earliestCreatedAt = normalizedOrders
    .map((candidate) => candidate.createdAt)
    .sort()[0]

  return {
    ...primaryOrder,
    name:
      normalizedOrders.find((candidate) => candidate.name.trim())?.name ??
      primaryOrder.name ??
      'Order 1',
    createdAt: earliestCreatedAt ?? primaryOrder.createdAt,
    targets: normalizedOrders.flatMap((candidate) => candidate.targets),
    templateIds: normalizedOrders.flatMap((candidate) => candidate.templateIds ?? []),
    orderType: recurringSource?.orderType ?? primaryOrder.orderType ?? 'one_time',
    recurrence: getOrderRecurrence(recurringSource?.recurrence ?? primaryOrder.recurrence),
    templateStatus: recurringSource?.templateStatus ?? primaryOrder.templateStatus ?? null,
  }
}

function updateOrderById(
  currentOrder: PreFeasibilityOrder | null,
  orderId: string,
  updater: (order: PreFeasibilityOrder) => PreFeasibilityOrder,
): PreFeasibilityOrder | null {
  if (!currentOrder || currentOrder.id !== orderId) {
    return currentOrder
  }

  return updater(currentOrder)
}

// =============================================================================
// Store
// =============================================================================

export const usePreFeasibilityOrdersStore = create<
  PreFeasibilityOrderState & PreFeasibilityOrdersActions
>()(
  devtools(
    (set, get) => ({
      order: null,
      activeOrderId: null,

      createOrder: () => {
        const existingOrder = get().order
        if (existingOrder) {
          set({ activeOrderId: existingOrder.id })
          return existingOrder.id
        }

        const order = createDefaultOrder()
        set({ order, activeOrderId: order.id })
        return order.id
      },

      removeOrder: (orderId) =>
        set((state) => ({
          order:
            state.order && state.order.id === orderId
              ? null
              : state.order,
          activeOrderId:
            state.activeOrderId === orderId ? null : state.activeOrderId,
        })),

      renameOrder: (orderId, name) =>
        set((state) => ({
          order: updateOrderById(state.order, orderId, (order) => ({ ...order, name })),
        })),

      setOrderType: (orderId, orderType) =>
        set((state) => ({
          order: updateOrderById(state.order, orderId, (order) => ({ ...order, orderType })),
        })),

      updateOrderRecurrence: (orderId, updates) =>
        set((state) => ({
          order: updateOrderById(state.order, orderId, (order) => ({
            ...order,
            recurrence: {
              ...getOrderRecurrence(order.recurrence),
              ...updates,
              daysOfWeek: updates.daysOfWeek ?? order.recurrence?.daysOfWeek ?? [],
            },
          })),
        })),

      setOrderTemplateState: (orderId, updates) =>
        set((state) => ({
          order: updateOrderById(state.order, orderId, (order) => ({
            ...order,
            templateIds: updates.templateIds ?? order.templateIds ?? [],
            templateStatus:
              updates.templateStatus === undefined
                ? order.templateStatus ?? null
                : updates.templateStatus,
          })),
        })),

      addTarget: (orderId, target) =>
        set((state) => ({
          order: updateOrderById(state.order, orderId, (order) => ({
            ...order,
            targets: [...order.targets, target],
          })),
        })),

      removeTarget: (orderId, targetIndex) =>
        set((state) => ({
          order: updateOrderById(state.order, orderId, (order) => ({
            ...order,
            targets: order.targets.filter((_, i) => i !== targetIndex),
            templateIds: (order.templateIds ?? []).filter((_, i) => i !== targetIndex),
          })),
        })),

      updateTarget: (orderId, targetIndex, updates) =>
        set((state) => ({
          order: updateOrderById(state.order, orderId, (order) => ({
            ...order,
            targets: order.targets.map((target, index) =>
              index === targetIndex ? { ...target, ...updates } : target,
            ),
          })),
        })),

      setOrderTargets: (orderId, targets) =>
        set((state) => ({
          order: updateOrderById(state.order, orderId, (order) => ({
            ...order,
            targets,
            templateIds: (order.templateIds ?? []).slice(0, targets.length),
          })),
        })),

      setActiveOrder: (orderId) =>
        set((state) => ({
          activeOrderId:
            orderId === null
              ? null
              : state.order?.id === orderId
                ? orderId
                : state.order?.id ?? null,
        })),

      addTargets: (orderId, targets) =>
        set((state) => ({
          order: updateOrderById(state.order, orderId, (order) => ({
            ...order,
            targets: [...order.targets, ...targets],
          })),
        })),

      getAllTargets: () => get().order?.targets ?? [],

      clearAll: () => set({ order: null, activeOrderId: null }),

      replaceOrder: (order) =>
        set({
          order: order ? normalizeOrder(order) : null,
          activeOrderId: order?.id ?? null,
        }),

      validate: () => {
        const issues: string[] = []
        const order = get().order

        if (!order) {
          issues.push('At least one order is required')
          return issues
        }

        if (!order.name || !order.name.trim()) {
          issues.push(`Order "${order.id}" has no name`)
        }
        if (order.targets.length === 0) {
          issues.push(`Order "${order.name || order.id}" has no targets`)
        }
        const recurrenceIssues = getRecurrenceValidationIssues(order.orderType, order.recurrence)
        for (const recurrenceIssue of recurrenceIssues) {
          issues.push(`Order "${order.name || order.id}": ${recurrenceIssue}`)
        }
        for (const target of order.targets) {
          if (!target.name || !target.name.trim()) {
            issues.push(`A target in order "${order.name || order.id}" has no name`)
          }
        }

        return issues
      },
    }),
    {
      name: 'PreFeasibilityOrdersStore',
      enabled: import.meta.env?.DEV ?? false,
    },
  ),
)
