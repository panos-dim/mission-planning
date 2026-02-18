/**
 * Pre-Feasibility Orders Store
 *
 * Zustand store for managing orders BEFORE feasibility analysis.
 * Each order has a name and a list of targets. When feasibility is run,
 * ALL targets from ALL orders are collected and sent to the backend.
 *
 * This is distinct from the post-planning ordersStore (AcceptedOrder).
 */

import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import type { TargetData } from '../types'

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
}

interface PreFeasibilityOrdersState {
  orders: PreFeasibilityOrder[]
  /** Counter for auto-suggesting "Order N" names */
  nextOrderNumber: number
  /** Which order receives map-click / file-upload targets */
  activeOrderId: string | null
}

interface PreFeasibilityOrdersActions {
  /** Create a new empty order with auto-suggested name */
  createOrder: () => string
  /** Remove an order by ID */
  removeOrder: (orderId: string) => void
  /** Update order name */
  renameOrder: (orderId: string, name: string) => void
  /** Add a target to a specific order */
  addTarget: (orderId: string, target: TargetData) => void
  /** Remove a target from an order by index */
  removeTarget: (orderId: string, targetIndex: number) => void
  /** Update a target within an order */
  updateTarget: (orderId: string, targetIndex: number, updates: Partial<TargetData>) => void
  /** Replace all targets in an order (e.g. from file upload or samples) */
  setOrderTargets: (orderId: string, targets: TargetData[]) => void
  /** Get all targets from all orders (flattened) */
  getAllTargets: () => TargetData[]
  /** Clear all orders */
  clearAll: () => void
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

// =============================================================================
// Store
// =============================================================================

export const usePreFeasibilityOrdersStore = create<
  PreFeasibilityOrdersState & PreFeasibilityOrdersActions
>()(
  devtools(
    (set, get) => ({
      orders: [],
      nextOrderNumber: 1,
      activeOrderId: null,

      createOrder: () => {
        const num = get().nextOrderNumber
        const id = generateId()
        const order: PreFeasibilityOrder = {
          id,
          name: `Order ${num}`,
          targets: [],
          createdAt: new Date().toISOString(),
        }
        set((state) => ({
          orders: [...state.orders, order],
          nextOrderNumber: state.nextOrderNumber + 1,
        }))
        return id
      },

      removeOrder: (orderId) =>
        set((state) => ({
          orders: state.orders.filter((o) => o.id !== orderId),
        })),

      renameOrder: (orderId, name) =>
        set((state) => ({
          orders: state.orders.map((o) => (o.id === orderId ? { ...o, name } : o)),
        })),

      addTarget: (orderId, target) =>
        set((state) => ({
          orders: state.orders.map((o) =>
            o.id === orderId ? { ...o, targets: [...o.targets, target] } : o,
          ),
        })),

      removeTarget: (orderId, targetIndex) =>
        set((state) => ({
          orders: state.orders.map((o) =>
            o.id === orderId ? { ...o, targets: o.targets.filter((_, i) => i !== targetIndex) } : o,
          ),
        })),

      updateTarget: (orderId, targetIndex, updates) =>
        set((state) => ({
          orders: state.orders.map((o) =>
            o.id === orderId
              ? {
                  ...o,
                  targets: o.targets.map((t, i) => (i === targetIndex ? { ...t, ...updates } : t)),
                }
              : o,
          ),
        })),

      setOrderTargets: (orderId, targets) =>
        set((state) => ({
          orders: state.orders.map((o) => (o.id === orderId ? { ...o, targets } : o)),
        })),

      setActiveOrder: (orderId) => set({ activeOrderId: orderId }),

      addTargets: (orderId, targets) =>
        set((state) => ({
          orders: state.orders.map((o) =>
            o.id === orderId ? { ...o, targets: [...o.targets, ...targets] } : o,
          ),
        })),

      getAllTargets: () => {
        return get().orders.flatMap((o) => o.targets)
      },

      clearAll: () => set({ orders: [], nextOrderNumber: 1 }),

      validate: () => {
        const issues: string[] = []
        const orders = get().orders

        if (orders.length === 0) {
          issues.push('At least one order is required')
          return issues
        }

        for (const order of orders) {
          if (!order.name || !order.name.trim()) {
            issues.push(`Order "${order.id}" has no name`)
          }
          if (order.targets.length === 0) {
            issues.push(`Order "${order.name || order.id}" has no targets`)
          }
          for (const target of order.targets) {
            if (!target.name || !target.name.trim()) {
              issues.push(`A target in order "${order.name || order.id}" has no name`)
            }
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
