import type { AcceptedOrder } from '../types'

const LEGACY_ACCEPTED_ORDERS_KEY = 'acceptedOrders'
const ACCEPTED_ORDERS_STORAGE_PREFIX = 'acceptedOrders:'
const DEFAULT_WORKSPACE_STORAGE_KEY = 'default'

const dedupeAcceptedOrders = (orders: AcceptedOrder[]): AcceptedOrder[] => {
  const seen = new Set<string>()
  return orders.filter((order) => {
    if (seen.has(order.order_id)) return false
    seen.add(order.order_id)
    return true
  })
}

const parseAcceptedOrders = (raw: string | null): AcceptedOrder[] => {
  if (!raw) return []

  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? dedupeAcceptedOrders(parsed as AcceptedOrder[]) : []
  } catch {
    return []
  }
}

export const getAcceptedOrdersStorageKey = (workspaceId?: string | null): string =>
  `${ACCEPTED_ORDERS_STORAGE_PREFIX}${workspaceId || DEFAULT_WORKSPACE_STORAGE_KEY}`

export function loadAcceptedOrdersForWorkspace(workspaceId?: string | null): AcceptedOrder[] {
  const workspaceKey = getAcceptedOrdersStorageKey(workspaceId)
  const storedWorkspaceOrders = parseAcceptedOrders(localStorage.getItem(workspaceKey))
  if (storedWorkspaceOrders.length > 0) {
    return storedWorkspaceOrders
  }

  // Legacy `acceptedOrders` was global and therefore ambiguous across workspaces.
  // Only reuse it for the default workspace to avoid cross-workspace leaks.
  if (!workspaceId || workspaceId === DEFAULT_WORKSPACE_STORAGE_KEY) {
    return parseAcceptedOrders(localStorage.getItem(LEGACY_ACCEPTED_ORDERS_KEY))
  }

  return []
}

export function saveAcceptedOrdersForWorkspace(
  workspaceId: string | null | undefined,
  orders: AcceptedOrder[],
): void {
  const serialized = JSON.stringify(dedupeAcceptedOrders(orders))
  localStorage.setItem(getAcceptedOrdersStorageKey(workspaceId), serialized)

  // Keep the legacy key in sync for the default workspace during the migration window.
  if (!workspaceId || workspaceId === DEFAULT_WORKSPACE_STORAGE_KEY) {
    localStorage.setItem(LEGACY_ACCEPTED_ORDERS_KEY, serialized)
  }
}
