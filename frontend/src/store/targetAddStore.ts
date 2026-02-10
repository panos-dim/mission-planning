/**
 * Zustand store for managing target add mode state
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";

interface PendingTarget {
  id: string;
  latitude: number;
  longitude: number;
  name?: string;
  description?: string;
}

interface TargetAddState {
  // Target add mode
  isAddMode: boolean;
  pendingTarget: PendingTarget | null;
  isDetailsSheetOpen: boolean;

  // Actions
  enableAddMode: () => void;
  disableAddMode: () => void;
  toggleAddMode: () => void;
  setPendingTarget: (target: PendingTarget | null) => void;
  openDetailsSheet: () => void;
  closeDetailsSheet: () => void;
  clearPendingTarget: () => void;
}

export const useTargetAddStore = create<TargetAddState>()(
  devtools(
    (set, get) => ({
      // Initial state
      isAddMode: false,
      pendingTarget: null,
      isDetailsSheetOpen: false,

      // Actions
      enableAddMode: () => {
        set({ isAddMode: true });
      },

      disableAddMode: () => {
        // Clear pending target when exiting add mode
        set({
          isAddMode: false,
          pendingTarget: null,
          isDetailsSheetOpen: false,
        });
      },

      toggleAddMode: () => {
        const { isAddMode, disableAddMode, enableAddMode } = get();
        if (isAddMode) {
          disableAddMode();
        } else {
          enableAddMode();
        }
      },

      setPendingTarget: (target: PendingTarget | null) => {
        set({ pendingTarget: target });
      },

      openDetailsSheet: () => {
        set({ isDetailsSheetOpen: true });
      },

      closeDetailsSheet: () => {
        set({ isDetailsSheetOpen: false });
      },

      clearPendingTarget: () => {
        set({
          pendingTarget: null,
          isDetailsSheetOpen: false,
        });
      },
    }),
    { name: "TargetAddStore", enabled: import.meta.env?.DEV ?? false },
  ),
);
