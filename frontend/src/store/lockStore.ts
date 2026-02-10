/**
 * Lock Store — PR-LOCK-OPS-01
 *
 * Zustand store for optimistic lock-level management.
 * Tracks acquisition lock levels, provides toggle/bulk actions,
 * calls backend API, and rolls back on failure.
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";
import type { LockLevel } from "../api/scheduleApi";
import { updateAcquisitionLock, bulkUpdateLocks } from "../api/scheduleApi";

// =============================================================================
// Types
// =============================================================================

export interface LockToastMessage {
  id: string;
  type: "success" | "error" | "info";
  message: string;
  timestamp: number;
}

interface LockState {
  /** acquisitionId → LockLevel overrides (only entries that differ from default) */
  levels: Map<string, LockLevel>;
  /** In-flight lock operations (acquisition IDs currently being updated) */
  pending: Set<string>;
  /** Toast messages for user feedback */
  toasts: LockToastMessage[];
}

interface LockActions {
  /** Get effective lock level for an acquisition (defaults to "none") */
  getLockLevel: (acquisitionId: string) => LockLevel;

  /** Toggle lock: none→hard, hard→none. Optimistic + API call + rollback. */
  toggleLock: (acquisitionId: string) => Promise<void>;

  /** Set lock level for a single acquisition. Optimistic + API. */
  setLockLevel: (acquisitionId: string, level: LockLevel) => Promise<void>;

  /** Bulk lock: set level for multiple acquisition IDs. */
  bulkSetLockLevel: (
    acquisitionIds: string[],
    level: LockLevel,
  ) => Promise<void>;

  /** Seed lock levels from external data (e.g., fetched acquisitions) */
  seedLevels: (entries: Array<{ id: string; lock_level: LockLevel }>) => void;

  /** Dismiss a toast by ID */
  dismissToast: (id: string) => void;

  /** Clear all toasts */
  clearToasts: () => void;
}

// =============================================================================
// Helpers
// =============================================================================

let toastCounter = 0;

function makeToast(
  type: LockToastMessage["type"],
  message: string,
): LockToastMessage {
  return {
    id: `lock-toast-${++toastCounter}`,
    type,
    message,
    timestamp: Date.now(),
  };
}

// =============================================================================
// Store
// =============================================================================

export const useLockStore = create<LockState & LockActions>()(
  devtools(
    (set, get) => ({
      levels: new Map(),
      pending: new Set(),
      toasts: [],

      getLockLevel: (acquisitionId) => {
        return get().levels.get(acquisitionId) ?? "none";
      },

      toggleLock: async (acquisitionId) => {
        const current = get().getLockLevel(acquisitionId);
        const next: LockLevel = current === "hard" ? "none" : "hard";
        await get().setLockLevel(acquisitionId, next);
      },

      setLockLevel: async (acquisitionId, level) => {
        const { levels, pending } = get();

        // Guard: already in-flight
        if (pending.has(acquisitionId)) return;

        const previous = levels.get(acquisitionId) ?? "none";
        if (previous === level) return; // no-op

        // Optimistic update
        const newLevels = new Map(levels);
        newLevels.set(acquisitionId, level);
        const newPending = new Set(pending);
        newPending.add(acquisitionId);

        set({ levels: newLevels, pending: newPending });

        try {
          await updateAcquisitionLock(acquisitionId, level);

          // Success: clear pending, add toast
          const finalPending = new Set(get().pending);
          finalPending.delete(acquisitionId);
          set({
            pending: finalPending,
            toasts: [
              ...get().toasts,
              makeToast(
                "success",
                level === "hard"
                  ? "Acquisition locked"
                  : "Acquisition unlocked",
              ),
            ],
          });
        } catch (err) {
          // Rollback
          const rollbackLevels = new Map(get().levels);
          rollbackLevels.set(acquisitionId, previous);
          const rollbackPending = new Set(get().pending);
          rollbackPending.delete(acquisitionId);

          const errorMsg =
            err instanceof Error ? err.message : "Lock update failed";

          // Check for specific error messages
          let userMessage = "Lock update failed, please retry";
          if (errorMsg.includes("Cannot unlock")) {
            userMessage = "Cannot unlock executed acquisition";
          } else if (errorMsg.includes("not found")) {
            userMessage = "Acquisition not found";
          }

          set({
            levels: rollbackLevels,
            pending: rollbackPending,
            toasts: [...get().toasts, makeToast("error", userMessage)],
          });
        }
      },

      bulkSetLockLevel: async (acquisitionIds, level) => {
        if (acquisitionIds.length === 0) return;

        const { levels, pending } = get();

        // Filter out already-pending and already-at-level
        const toUpdate = acquisitionIds.filter(
          (id) => !pending.has(id) && (levels.get(id) ?? "none") !== level,
        );

        if (toUpdate.length === 0) return;

        // Save previous state for rollback
        const previousLevels = new Map<string, LockLevel>();
        for (const id of toUpdate) {
          previousLevels.set(id, levels.get(id) ?? "none");
        }

        // Optimistic update
        const newLevels = new Map(levels);
        const newPending = new Set(pending);
        for (const id of toUpdate) {
          newLevels.set(id, level);
          newPending.add(id);
        }
        set({ levels: newLevels, pending: newPending });

        try {
          const result = await bulkUpdateLocks({
            acquisition_ids: toUpdate,
            lock_level: level,
          });

          // Clear pending for all
          const finalPending = new Set(get().pending);
          for (const id of toUpdate) {
            finalPending.delete(id);
          }

          // Rollback any that failed
          const finalLevels = new Map(get().levels);
          for (const failedId of result.failed || []) {
            const prev = previousLevels.get(failedId);
            if (prev !== undefined) {
              finalLevels.set(failedId, prev);
            }
          }

          const successCount = result.updated;
          const failCount = (result.failed || []).length;

          const toasts = [...get().toasts];
          if (successCount > 0) {
            toasts.push(
              makeToast(
                "success",
                `${successCount} acquisition${successCount !== 1 ? "s" : ""} ${level === "hard" ? "locked" : "unlocked"}`,
              ),
            );
          }
          if (failCount > 0) {
            toasts.push(
              makeToast(
                "error",
                `${failCount} acquisition${failCount !== 1 ? "s" : ""} failed to update`,
              ),
            );
          }

          set({ levels: finalLevels, pending: finalPending, toasts });
        } catch (err) {
          // Full rollback
          const rollbackLevels = new Map(get().levels);
          const rollbackPending = new Set(get().pending);
          for (const id of toUpdate) {
            const prev = previousLevels.get(id);
            if (prev !== undefined) {
              rollbackLevels.set(id, prev);
            }
            rollbackPending.delete(id);
          }

          set({
            levels: rollbackLevels,
            pending: rollbackPending,
            toasts: [
              ...get().toasts,
              makeToast("error", "Bulk lock update failed, please retry"),
            ],
          });
        }
      },

      seedLevels: (entries) => {
        const newLevels = new Map(get().levels);
        for (const entry of entries) {
          newLevels.set(entry.id, entry.lock_level);
        }
        set({ levels: newLevels });
      },

      dismissToast: (id) => {
        set({ toasts: get().toasts.filter((t) => t.id !== id) });
      },

      clearToasts: () => {
        set({ toasts: [] });
      },
    }),
    { name: "LockStore", enabled: import.meta.env?.DEV ?? false },
  ),
);

// =============================================================================
// Selector hooks
// =============================================================================

/** Hook: is a specific acquisition currently pending a lock update? */
export const useIsLockPending = (acquisitionId: string): boolean =>
  useLockStore((s) => s.pending.has(acquisitionId));

/** Hook: get effective lock level for an acquisition */
export const useAcquisitionLockLevel = (acquisitionId: string): LockLevel =>
  useLockStore((s) => s.levels.get(acquisitionId) ?? "none");
