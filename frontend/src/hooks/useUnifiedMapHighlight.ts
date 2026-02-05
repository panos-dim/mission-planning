/**
 * useUnifiedMapHighlight Hook
 *
 * Unified hook for applying Cesium entity highlighting across all modes:
 * - Conflict highlighting
 * - Repair diff highlighting
 * - Normal selection highlighting
 *
 * Uses the highlight adapter for consistent entity resolution and styling.
 * Implements ghost entity fallback cloning for moved items.
 * Implements timeline focus reliability guard.
 *
 * Part of PR-MAP-HIGHLIGHT-01
 */

import { useEffect, useRef, useCallback, useMemo } from "react";
import { JulianDate } from "cesium";
import {
  useUnifiedHighlightStore,
  useShouldFocusTimeline,
  useHighlightTimeRange,
} from "../store/unifiedHighlightStore";
import { useVisStore } from "../store/visStore";
import {
  resolveEntityIds,
  applyHighlight,
  applyGhostHighlight,
  clearHighlights,
  createGhostClone,
  removeAllGhostClones,
  buildGhostEntityId,
  invalidateEntityCache,
  type HighlightMode,
  type RepairDiffType,
} from "../adapters/highlightAdapter";

const isDev = import.meta.env?.DEV ?? false;

// =============================================================================
// Hook Implementation
// =============================================================================

export function useUnifiedMapHighlight(viewerRef: React.RefObject<any>) {
  // Track previously highlighted entities for cleanup
  const highlightedEntitiesRef = useRef<Set<string>>(new Set());
  const ghostEntitiesRef = useRef<Set<string>>(new Set());
  const lastHighlightKeyRef = useRef<string | null>(null);

  // Store state
  const activeMode = useUnifiedHighlightStore((s) => s.activeMode);
  const highlightedIds = useUnifiedHighlightStore((s) => s.highlightedIds);
  const ghostIds = useUnifiedHighlightStore((s) => s.ghostIds);
  const repairDiffType = useUnifiedHighlightStore((s) => s.repairDiffType);
  const clearTimelineFocus = useUnifiedHighlightStore(
    (s) => s.clearTimelineFocus,
  );
  const setTimelineVisible = useUnifiedHighlightStore(
    (s) => s.setTimelineVisible,
  );

  // Timeline focus state
  const shouldFocusTimeline = useShouldFocusTimeline();
  const timeRange = useHighlightTimeRange();
  const setClockTime = useVisStore((s) => s.setClockTime);

  // Create a stable highlight key for dependency tracking
  const highlightKey = useMemo(() => {
    if (!activeMode || highlightedIds.length === 0) return null;
    return `${activeMode}:${repairDiffType || ""}:${highlightedIds.join(",")}:${ghostIds.join(",")}`;
  }, [activeMode, repairDiffType, highlightedIds, ghostIds]);

  /**
   * Clear all highlights from the map
   */
  const clearAllHighlights = useCallback(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer) return;

    const toRestore = new Set([
      ...highlightedEntitiesRef.current,
      ...ghostEntitiesRef.current,
    ]);

    if (toRestore.size === 0) return;

    if (isDev) {
      console.log(
        `[UnifiedMapHighlight] Clearing ${toRestore.size} highlighted entities`,
      );
    }

    // Resolve and clear highlights
    const entities = resolveEntityIds(viewer, Array.from(toRestore));
    clearHighlights(entities);

    // Remove any created ghost clones
    removeAllGhostClones(viewer);

    highlightedEntitiesRef.current.clear();
    ghostEntitiesRef.current.clear();

    // Request render update
    if (viewer.scene) {
      viewer.scene.requestRender();
    }
  }, [viewerRef]);

  /**
   * Apply highlights based on current store state
   */
  const applyHighlightsFromStore = useCallback(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer) return;

    // Clear previous highlights first
    clearAllHighlights();

    // If no active highlight, we're done
    if (!activeMode || highlightedIds.length === 0) {
      if (isDev) {
        console.log(
          "[UnifiedMapHighlight] No active highlight mode or no IDs to highlight",
        );
      }
      return;
    }

    if (isDev) {
      console.log(
        `[UnifiedMapHighlight] Applying ${activeMode} highlights to ${highlightedIds.length} IDs`,
      );
    }

    // Resolve primary entities
    const primaryEntities = resolveEntityIds(viewer, highlightedIds);

    if (isDev) {
      console.log(
        `[UnifiedMapHighlight] Resolved ${primaryEntities.length} primary entities`,
      );
    }

    // Apply highlight styling
    applyHighlight(
      primaryEntities,
      activeMode as HighlightMode,
      repairDiffType as RepairDiffType | undefined,
    );

    // Track highlighted entity IDs
    for (const entity of primaryEntities) {
      if (entity.id) {
        highlightedEntitiesRef.current.add(entity.id);
      }
    }

    // Handle ghost entities for moved items
    if (
      activeMode === "repair" &&
      repairDiffType === "moved" &&
      ghostIds.length > 0
    ) {
      // First try to find existing ghost entities
      const ghostEntities = resolveEntityIds(viewer, ghostIds);

      // If no ghost entities found, create clones from primary entities
      if (ghostEntities.length === 0 && primaryEntities.length > 0) {
        if (isDev) {
          console.log(
            `[UnifiedMapHighlight] No ghost entities found, creating ${ghostIds.length} clones`,
          );
        }

        for (let i = 0; i < ghostIds.length; i++) {
          const ghostId = ghostIds[i];
          // Use the first primary entity as the source for cloning
          const sourceEntity = primaryEntities[0];
          const canonicalGhostId = buildGhostEntityId(
            ghostId.replace(/^ghost[:_]/, ""),
          );
          const clone = createGhostClone(
            viewer,
            sourceEntity,
            canonicalGhostId,
          );
          if (clone) {
            ghostEntities.push(clone);
          }
        }
      }

      // Apply ghost styling
      applyGhostHighlight(ghostEntities);

      // Track ghost entity IDs
      for (const entity of ghostEntities) {
        if (entity.id) {
          ghostEntitiesRef.current.add(entity.id);
        }
      }

      if (isDev) {
        console.log(
          `[UnifiedMapHighlight] Applied ghost highlight to ${ghostEntities.length} entities`,
        );
      }
    }

    // Request render update
    if (viewer.scene) {
      viewer.scene.requestRender();
    }
  }, [
    viewerRef,
    activeMode,
    highlightedIds,
    ghostIds,
    repairDiffType,
    clearAllHighlights,
  ]);

  // Effect: Apply highlighting when store state changes
  useEffect(() => {
    // Skip if highlight key hasn't changed
    if (highlightKey === lastHighlightKeyRef.current) {
      return;
    }
    lastHighlightKeyRef.current = highlightKey;

    applyHighlightsFromStore();
  }, [highlightKey, applyHighlightsFromStore]);

  // Effect: Monitor timeline visibility
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer) return;

    // Check initial visibility
    const checkVisibility = () => {
      const isVisible =
        viewer.timeline !== undefined && viewer.timeline !== null;
      setTimelineVisible(isVisible);
    };

    // Check immediately
    checkVisibility();

    // Re-check periodically (timeline might be hidden/shown dynamically)
    const interval = setInterval(checkVisibility, 1000);

    return () => clearInterval(interval);
  }, [viewerRef, setTimelineVisible]);

  // Effect: Focus timeline when time range changes
  useEffect(() => {
    if (!shouldFocusTimeline || !timeRange) return;

    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer) return;

    // Check if timeline is available
    if (!viewer.timeline || !viewer.clock) {
      if (isDev) {
        console.log(
          "[UnifiedMapHighlight] Timeline not available, focus will be applied when visible",
        );
      }
      return;
    }

    try {
      // Parse times and add padding
      const paddingMs = timeRange.padding * 60 * 1000;
      const startTime = new Date(
        new Date(timeRange.start).getTime() - paddingMs,
      );
      const endTime = new Date(new Date(timeRange.end).getTime() + paddingMs);

      const startJulian = JulianDate.fromDate(startTime);
      const endJulian = JulianDate.fromDate(endTime);

      // Focus timeline on time window
      viewer.timeline.zoomTo(startJulian, endJulian);

      // Jump clock to start of time range
      const rangeStart = JulianDate.fromIso8601(timeRange.start);
      viewer.clock.currentTime = rangeStart;
      setClockTime(rangeStart);

      if (isDev) {
        console.log(
          `[UnifiedMapHighlight] Focused timeline: ${timeRange.start} - ${timeRange.end}`,
        );
      }

      // Clear the focus flag
      clearTimelineFocus();
    } catch (error) {
      console.error("[UnifiedMapHighlight] Failed to focus timeline:", error);
    }
  }, [
    viewerRef,
    timeRange,
    shouldFocusTimeline,
    setClockTime,
    clearTimelineFocus,
  ]);

  // Effect: Invalidate entity cache when viewer entities change
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer) return;

    // Listen for entity collection changes
    const handleChange = () => {
      invalidateEntityCache();
    };

    // Subscribe to entity changes
    if (viewer.entities?.collectionChanged) {
      viewer.entities.collectionChanged.addEventListener(handleChange);
    }

    return () => {
      if (viewer.entities?.collectionChanged) {
        viewer.entities.collectionChanged.removeEventListener(handleChange);
      }
    };
  }, [viewerRef]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearAllHighlights();
    };
  }, [clearAllHighlights]);

  return {
    clearAllHighlights,
    highlightedCount: highlightedEntitiesRef.current.size,
    ghostCount: ghostEntitiesRef.current.size,
  };
}

export default useUnifiedMapHighlight;
