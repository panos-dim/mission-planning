/**
 * Planning Results Store
 *
 * Zustand store for sharing mission planning results between components.
 */

import { create } from "zustand";
import { AlgorithmResult } from "../types";

interface PlanningResultsState {
  // Results from mission planning algorithms
  results: Record<string, AlgorithmResult> | null;

  // Currently selected/active algorithm
  activeAlgorithm: string | null;

  // Actions
  setResults: (results: Record<string, AlgorithmResult> | null) => void;
  setActiveAlgorithm: (algorithm: string | null) => void;
  clearResults: () => void;

  // Computed getters
  getScheduledCount: () => number;
  getActiveResult: () => AlgorithmResult | null;
}

export const usePlanningStore = create<PlanningResultsState>((set, get) => ({
  results: null,
  activeAlgorithm: null,

  setResults: (results) => set({ results }),

  setActiveAlgorithm: (algorithm) => set({ activeAlgorithm: algorithm }),

  clearResults: () => set({ results: null, activeAlgorithm: null }),

  getScheduledCount: () => {
    const { results, activeAlgorithm } = get();
    if (!results || !activeAlgorithm) return 0;
    const activeResult = results[activeAlgorithm];
    return activeResult?.schedule?.length || 0;
  },

  getActiveResult: () => {
    const { results, activeAlgorithm } = get();
    if (!results || !activeAlgorithm) return null;
    return results[activeAlgorithm] || null;
  },
}));
