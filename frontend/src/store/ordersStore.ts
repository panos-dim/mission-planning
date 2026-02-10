/**
 * Orders Store
 *
 * Zustand store for sharing accepted orders across components.
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";
import type { AcceptedOrder } from "../types";

interface OrdersState {
  orders: AcceptedOrder[];
  setOrders: (orders: AcceptedOrder[]) => void;
  addOrder: (order: AcceptedOrder) => void;
  removeOrder: (orderId: string) => void;
  clearOrders: () => void;
  getOrderById: (orderId: string) => AcceptedOrder | undefined;
}

export const useOrdersStore = create<OrdersState>()(
  devtools(
    (set, get) => ({
      orders: [],

      setOrders: (orders) => set({ orders }),

      addOrder: (order) =>
        set((state) => ({
          orders: [...state.orders, order],
        })),

      removeOrder: (orderId) =>
        set((state) => ({
          orders: state.orders.filter((o) => o.order_id !== orderId),
        })),

      clearOrders: () => set({ orders: [] }),

      getOrderById: (orderId) => {
        return get().orders.find((o) => o.order_id === orderId);
      },
    }),
    { name: "OrdersStore", enabled: import.meta.env?.DEV ?? false },
  ),
);
