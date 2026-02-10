/**
 * Conflict Store
 *
 * Manages conflict state for the UI:
 * - List of detected conflicts
 * - Selected conflict for highlighting
 * - Conflict statistics
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { Conflict } from "../api/scheduleApi";

interface ConflictState {
  conflicts: Conflict[];
  selectedConflictId: string | null;
  highlightedAcquisitionIds: string[];
  isLoading: boolean;
  error: string | null;
  summary: {
    total: number;
    errorCount: number;
    warningCount: number;
  };
}

interface ConflictActions {
  setConflicts: (conflicts: Conflict[]) => void;
  selectConflict: (conflictId: string | null) => void;
  clearSelection: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  getConflictsForAcquisition: (acquisitionId: string) => Conflict[];
}

export const useConflictStore = create<ConflictState & ConflictActions>()(
  devtools(
    (set, get) => ({
      conflicts: [],
      selectedConflictId: null,
      highlightedAcquisitionIds: [],
      isLoading: false,
      error: null,
      summary: {
        total: 0,
        errorCount: 0,
        warningCount: 0,
      },

      setConflicts: (conflicts) => {
        const errorCount = conflicts.filter(
          (c) => c.severity === "error",
        ).length;
        const warningCount = conflicts.filter(
          (c) => c.severity === "warning",
        ).length;

        set({
          conflicts,
          summary: {
            total: conflicts.length,
            errorCount,
            warningCount,
          },
          error: null,
        });
      },

      selectConflict: (conflictId) => {
        const { conflicts } = get();
        const conflict = conflicts.find((c) => c.id === conflictId);
        const highlightedAcquisitionIds = conflict
          ? conflict.acquisition_ids
          : [];

        set({
          selectedConflictId: conflictId,
          highlightedAcquisitionIds,
        });
      },

      clearSelection: () => {
        set({
          selectedConflictId: null,
          highlightedAcquisitionIds: [],
        });
      },

      setLoading: (isLoading) => set({ isLoading }),

      setError: (error) => set({ error, isLoading: false }),

      getConflictsForAcquisition: (acquisitionId) => {
        const { conflicts } = get();
        return conflicts.filter((c) =>
          c.acquisition_ids.includes(acquisitionId),
        );
      },
    }),
    { name: "ConflictStore", enabled: import.meta.env?.DEV ?? false },
  ),
);
