/**
 * Lock Mode Store — PR-UI-003
 *
 * Zustand store for Lock Mode toggle on the map.
 * When lock mode is active, map clicks on lockable entities
 * (SAR swath acquisitions) toggle their lock state via lockStore.
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";

interface LockModeState {
  /** Whether lock mode is currently active on the map */
  isLockMode: boolean;
}

interface LockModeActions {
  enableLockMode: () => void;
  disableLockMode: () => void;
  toggleLockMode: () => void;
}

export const useLockModeStore = create<LockModeState & LockModeActions>()(
  devtools(
    (set, get) => ({
      isLockMode: false,

      enableLockMode: () => {
        set({ isLockMode: true });
      },

      disableLockMode: () => {
        set({ isLockMode: false });
      },

      toggleLockMode: () => {
        set({ isLockMode: !get().isLockMode });
      },
    }),
    { name: "LockModeStore", enabled: import.meta.env?.DEV ?? false },
  ),
);
