/**
 * useSwathVisibility Hook
 *
 * Manages SAR swath visibility in Cesium based on:
 * - Visibility mode (off | selected_plan | filtered | all)
 * - Active filters (target_id, run_id)
 * - LOD settings (max swaths, zoom level)
 * - Selection state (highlight selected/hovered)
 */

import { useEffect, useRef, useCallback } from "react";
import { Entity, Color, ConstantProperty } from "cesium";
import { useShallow } from "zustand/react/shallow";
import { useSwathStore, SwathVisibilityMode } from "../../../store/swathStore";
import { usePlanningStore } from "../../../store/planningStore";

// Swath styling constants
const SWATH_STYLES = {
  // Default (unselected) swath colors by look side
  default: {
    LEFT: {
      fill: Color.fromBytes(255, 100, 100, 60),
      outline: Color.fromBytes(255, 50, 50, 200),
    },
    RIGHT: {
      fill: Color.fromBytes(100, 100, 255, 60),
      outline: Color.fromBytes(50, 50, 255, 200),
    },
  },
  // Selected swath (brighter)
  selected: {
    LEFT: {
      fill: Color.fromBytes(255, 100, 100, 150),
      outline: Color.fromBytes(255, 50, 50, 255),
    },
    RIGHT: {
      fill: Color.fromBytes(100, 100, 255, 150),
      outline: Color.fromBytes(50, 50, 255, 255),
    },
  },
  // Hovered swath
  hovered: {
    LEFT: {
      fill: Color.fromBytes(255, 150, 150, 100),
      outline: Color.fromBytes(255, 100, 100, 255),
    },
    RIGHT: {
      fill: Color.fromBytes(150, 150, 255, 100),
      outline: Color.fromBytes(100, 100, 255, 255),
    },
  },
  // Dimmed (when not matching filter)
  dimmed: {
    fill: Color.fromBytes(128, 128, 128, 30),
    outline: Color.fromBytes(128, 128, 128, 80),
  },
};

interface CesiumViewerRef {
  cesiumElement: {
    dataSources: {
      length: number;
      get: (index: number) => {
        entities: {
          values: Entity[];
        };
      };
    };
  } | null;
}

interface UseSwathVisibilityOptions {
  viewerRef: React.RefObject<CesiumViewerRef | null>;
  enabled?: boolean;
}

/**
 * Get swath entity properties
 */
function getSwathProperties(entity: Entity): {
  opportunityId: string | null;
  targetId: string | null;
  runId: string | null;
  lookSide: "LEFT" | "RIGHT" | null;
} {
  try {
    return {
      opportunityId: entity.properties?.opportunity_id?.getValue(null) ?? null,
      targetId: entity.properties?.target_id?.getValue(null) ?? null,
      runId: entity.properties?.run_id?.getValue(null) ?? null,
      lookSide: entity.properties?.look_side?.getValue(null) ?? null,
    };
  } catch {
    return { opportunityId: null, targetId: null, runId: null, lookSide: null };
  }
}

/**
 * Check if entity is a SAR swath
 */
function isSarSwath(entity: Entity): boolean {
  if (!entity.id || typeof entity.id !== "string") return false;
  return entity.id.startsWith("sar_swath_");
}

/**
 * Apply styling to a swath entity
 */
function applySwathStyle(
  entity: Entity,
  style: "default" | "selected" | "hovered" | "dimmed",
  lookSide: "LEFT" | "RIGHT" | null,
) {
  if (!entity.polygon) return;

  const side = lookSide ?? "LEFT";
  let colors: { fill: Color; outline: Color };

  if (style === "dimmed") {
    colors = SWATH_STYLES.dimmed;
  } else {
    colors = SWATH_STYLES[style][side];
  }

  // Update polygon material color
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const material = entity.polygon.material as any;
  if (material?.color) {
    material.color = new ConstantProperty(colors.fill);
  }

  // Update outline color
  if (entity.polygon.outlineColor) {
    entity.polygon.outlineColor = new ConstantProperty(colors.outline);
  }
}

export function useSwathVisibility({
  viewerRef,
  enabled = true,
}: UseSwathVisibilityOptions) {
  const updateTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastUpdateRef = useRef<string>("");

  // Store state
  const {
    visibilityMode,
    selectedOpportunityId,
    hoveredOpportunityId,
    filteredTargetId,
    activeRunId,
    lodConfig,
    setRenderedSwaths,
    updateDebugInfo,
  } = useSwathStore(
    useShallow((s) => ({
      visibilityMode: s.visibilityMode,
      selectedOpportunityId: s.selectedOpportunityId,
      hoveredOpportunityId: s.hoveredOpportunityId,
      filteredTargetId: s.filteredTargetId,
      activeRunId: s.activeRunId,
      lodConfig: s.lodConfig,
      setRenderedSwaths: s.setRenderedSwaths,
      updateDebugInfo: s.updateDebugInfo,
    })),
  );

  // Planning store for selected plan's opportunities
  const { activeAlgorithm, results } = usePlanningStore(
    useShallow((s) => ({
      activeAlgorithm: s.activeAlgorithm,
      results: s.results,
    })),
  );

  /**
   * Get all swath entities from viewer
   */
  const getSwathEntities = useCallback((): Entity[] => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer?.dataSources) return [];

    const swathEntities: Entity[] = [];

    for (let i = 0; i < viewer.dataSources.length; i++) {
      const dataSource = viewer.dataSources.get(i);
      if (dataSource?.entities?.values) {
        dataSource.entities.values.forEach((entity) => {
          if (isSarSwath(entity)) {
            swathEntities.push(entity);
          }
        });
      }
    }

    return swathEntities;
  }, [viewerRef]);

  /**
   * Get scheduled opportunity IDs from selected plan
   */
  const getSelectedPlanOpportunityIds = useCallback((): Set<string> => {
    if (!activeAlgorithm || !results?.[activeAlgorithm]?.schedule) {
      return new Set();
    }

    const schedule = results[activeAlgorithm].schedule;
    return new Set(schedule.map((item) => item.opportunity_id));
  }, [activeAlgorithm, results]);

  /**
   * Determine if a swath should be visible based on mode and filters
   */
  const shouldShowSwath = useCallback(
    (
      opportunityId: string | null,
      targetId: string | null,
      runId: string | null,
      mode: SwathVisibilityMode,
      planOpportunities: Set<string>,
    ): boolean => {
      if (mode === "off") return false;

      if (mode === "selected_plan") {
        return opportunityId !== null && planOpportunities.has(opportunityId);
      }

      if (mode === "filtered") {
        // Show if matches filter criteria
        if (filteredTargetId && targetId !== filteredTargetId) return false;
        if (activeRunId && runId !== activeRunId) return false;
        return true;
      }

      // mode === "all"
      return true;
    },
    [filteredTargetId, activeRunId],
  );

  /**
   * Update swath visibility and styling
   */
  const updateSwathVisibility = useCallback(() => {
    if (!enabled) return;

    const swathEntities = getSwathEntities();
    const planOpportunities = getSelectedPlanOpportunityIds();
    const renderedIds: string[] = [];

    // Apply LOD cap for "all" mode
    let visibleCount = 0;
    const maxVisible =
      visibilityMode === "all" ? lodConfig.maxAllSwaths : Infinity;

    swathEntities.forEach((entity) => {
      const props = getSwathProperties(entity);
      const { opportunityId, targetId, runId, lookSide } = props;

      // Determine visibility
      const shouldShow = shouldShowSwath(
        opportunityId,
        targetId,
        runId,
        visibilityMode,
        planOpportunities,
      );

      // Apply LOD cap
      const withinCap = visibleCount < maxVisible;
      const finalVisible = shouldShow && withinCap;

      entity.show = finalVisible;

      if (finalVisible && opportunityId) {
        visibleCount++;
        renderedIds.push(opportunityId);

        // Determine style
        let style: "default" | "selected" | "hovered" | "dimmed" = "default";

        if (opportunityId === selectedOpportunityId) {
          style = "selected";
        } else if (opportunityId === hoveredOpportunityId) {
          style = "hovered";
        } else if (
          visibilityMode === "filtered" &&
          filteredTargetId &&
          targetId !== filteredTargetId
        ) {
          style = "dimmed";
        }

        applySwathStyle(entity, style, lookSide);
      }
    });

    // Update store with rendered swaths
    setRenderedSwaths(renderedIds);

    // Update debug info
    updateDebugInfo({
      renderedSwathCount: visibleCount,
      lodLevel:
        visibilityMode === "all" && visibleCount >= lodConfig.maxAllSwaths
          ? "simplified"
          : "full",
    });
  }, [
    enabled,
    getSwathEntities,
    getSelectedPlanOpportunityIds,
    shouldShowSwath,
    visibilityMode,
    selectedOpportunityId,
    hoveredOpportunityId,
    filteredTargetId,
    lodConfig.maxAllSwaths,
    setRenderedSwaths,
    updateDebugInfo,
  ]);

  /**
   * Debounced update for filter changes
   */
  const scheduleUpdate = useCallback(() => {
    // Create a cache key for the current state
    const cacheKey = `${visibilityMode}_${selectedOpportunityId}_${hoveredOpportunityId}_${filteredTargetId}_${activeRunId}`;

    // Skip if nothing changed
    if (cacheKey === lastUpdateRef.current) return;
    lastUpdateRef.current = cacheKey;

    // Clear pending update
    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current);
    }

    // Immediate update for selection changes, debounced for filter changes
    const isSelectionChange =
      cacheKey.includes(selectedOpportunityId || "") ||
      cacheKey.includes(hoveredOpportunityId || "");

    if (isSelectionChange) {
      updateSwathVisibility();
    } else {
      updateTimeoutRef.current = setTimeout(
        updateSwathVisibility,
        lodConfig.filterDebounceMs,
      );
    }
  }, [
    visibilityMode,
    selectedOpportunityId,
    hoveredOpportunityId,
    filteredTargetId,
    activeRunId,
    lodConfig.filterDebounceMs,
    updateSwathVisibility,
  ]);

  // Effect to update visibility when dependencies change
  useEffect(() => {
    scheduleUpdate();

    return () => {
      if (updateTimeoutRef.current) {
        clearTimeout(updateTimeoutRef.current);
      }
    };
  }, [scheduleUpdate]);

  return {
    updateSwathVisibility,
    getSwathEntities,
  };
}

export default useSwathVisibility;
