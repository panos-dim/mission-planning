/**
 * useConflictMapHighlight Hook
 *
 * Applies visual highlighting to Cesium entities when a conflict is selected.
 * Reacts to selectionStore.highlightedAcquisitionIds and applies emphasis styling.
 *
 * Part of PR-CONFLICT-UX-02
 * Updated for PR-MAP-HIGHLIGHT-01 to use unified highlight adapter
 */

import { useEffect, useRef, useCallback } from "react";
import {
  Color,
  Entity,
  ColorMaterialProperty,
  ConstantProperty,
  JulianDate,
  Property,
} from "cesium";
import { useSelectionStore } from "../store/selectionStore";
import {
  useConflictHighlightStore,
  useConflictTimeRangeValue,
  useShouldFocusTimeline,
} from "../store/conflictHighlightStore";
import { useVisStore } from "../store/visStore";
// Note: Unified highlight store integration available via useUnifiedMapHighlight hook
// This hook is maintained for backward compatibility (PR-CONFLICT-UX-02)

// Dev mode check
const isDev = import.meta.env?.DEV ?? false;

// Highlight colors for conflict entities
const CONFLICT_HIGHLIGHT_COLOR = Color.ORANGE.withAlpha(0.9);
const CONFLICT_OUTLINE_COLOR = Color.RED;
const CONFLICT_GLOW_COLOR = Color.ORANGE.withAlpha(0.5);

// Original style storage key on entity
const ORIGINAL_STYLE_KEY = "__conflictOriginalStyle";

interface OriginalEntityStyle {
  polygonMaterial?: Property | undefined;
  polygonOutlineColor?: Property | undefined;
  polygonOutlineWidth?: Property | undefined;
  pointColor?: Property | undefined;
  pointOutlineColor?: Property | undefined;
  pointPixelSize?: Property | undefined;
  billboardColor?: Property | undefined;
  billboardScale?: Property | undefined;
}

/**
 * Hook to apply conflict highlighting to Cesium entities
 * @param viewerRef - Ref to the Cesium viewer
 */
export function useConflictMapHighlight(viewerRef: React.RefObject<any>) {
  // Track previously highlighted entities for cleanup
  const highlightedEntitiesRef = useRef<Set<string>>(new Set());
  const cleanupTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Selection store for highlighted acquisition IDs
  const highlightedAcquisitionIds = useSelectionStore(
    (s) => s.highlightedAcquisitionIds,
  );
  const selectedConflictId = useSelectionStore((s) => s.selectedConflictId);

  // Conflict highlight store for additional highlight management
  // Use individual selectors to get actions (stable references)
  const setHighlightedAcquisitions = useConflictHighlightStore(
    (s) => s.setHighlightedAcquisitions,
  );
  const clearHighlights = useConflictHighlightStore((s) => s.clearHighlights);

  // Timeline focus - use individual selectors to avoid infinite loops
  const timeRange = useConflictTimeRangeValue();
  const shouldFocus = useShouldFocusTimeline();
  const setClockTime = useVisStore((s) => s.setClockTime);

  /**
   * Store original style before applying highlight
   */
  const storeOriginalStyle = useCallback((entity: Entity): void => {
    if ((entity as any)[ORIGINAL_STYLE_KEY]) return; // Already stored

    const original: OriginalEntityStyle = {};

    if (entity.polygon) {
      original.polygonMaterial = entity.polygon.material;
      original.polygonOutlineColor = entity.polygon.outlineColor;
      original.polygonOutlineWidth = entity.polygon.outlineWidth;
    }

    if (entity.point) {
      original.pointColor = entity.point.color;
      original.pointOutlineColor = entity.point.outlineColor;
      original.pointPixelSize = entity.point.pixelSize;
    }

    if (entity.billboard) {
      original.billboardColor = entity.billboard.color;
      original.billboardScale = entity.billboard.scale;
    }

    (entity as any)[ORIGINAL_STYLE_KEY] = original;
  }, []);

  /**
   * Apply conflict highlight styling to an entity
   */
  const applyHighlightStyle = useCallback(
    (entity: Entity): void => {
      storeOriginalStyle(entity);

      // Highlight polygons (SAR swaths, footprints)
      if (entity.polygon) {
        // Use type assertion to work around Cesium's complex MaterialProperty types
        (entity.polygon as any).material = new ColorMaterialProperty(
          CONFLICT_HIGHLIGHT_COLOR,
        );
        entity.polygon.outlineColor = new ConstantProperty(
          CONFLICT_OUTLINE_COLOR,
        );
        entity.polygon.outlineWidth = new ConstantProperty(3);
        entity.polygon.outline = new ConstantProperty(true);
      }

      // Highlight points (targets)
      if (entity.point) {
        entity.point.color = new ConstantProperty(CONFLICT_HIGHLIGHT_COLOR);
        entity.point.outlineColor = new ConstantProperty(
          CONFLICT_OUTLINE_COLOR,
        );
        entity.point.outlineWidth = new ConstantProperty(3);
        entity.point.pixelSize = new ConstantProperty(15);
      }

      // Highlight billboards (target markers)
      if (entity.billboard) {
        entity.billboard.color = new ConstantProperty(CONFLICT_GLOW_COLOR);
        entity.billboard.scale = new ConstantProperty(1.5);
      }

      if (isDev) {
        console.log(
          `[ConflictHighlight] Applied highlight to entity: ${entity.id}`,
        );
      }
    },
    [storeOriginalStyle],
  );

  /**
   * Restore original style to an entity
   */
  const restoreOriginalStyle = useCallback((entity: Entity): void => {
    const original = (entity as any)[ORIGINAL_STYLE_KEY] as
      | OriginalEntityStyle
      | undefined;
    if (!original) return;

    if (entity.polygon) {
      if (original.polygonMaterial) {
        (entity.polygon as any).material = original.polygonMaterial;
      }
      if (original.polygonOutlineColor) {
        (entity.polygon as any).outlineColor = original.polygonOutlineColor;
      }
      if (original.polygonOutlineWidth) {
        entity.polygon.outlineWidth = original.polygonOutlineWidth;
      }
    }

    if (entity.point) {
      if (original.pointColor) {
        entity.point.color = original.pointColor;
      }
      if (original.pointOutlineColor) {
        entity.point.outlineColor = original.pointOutlineColor;
      }
      if (original.pointPixelSize) {
        entity.point.pixelSize = original.pointPixelSize;
      }
    }

    if (entity.billboard) {
      if (original.billboardColor) {
        entity.billboard.color = original.billboardColor;
      }
      if (original.billboardScale) {
        entity.billboard.scale = original.billboardScale;
      }
    }

    delete (entity as any)[ORIGINAL_STYLE_KEY];

    if (isDev) {
      console.log(
        `[ConflictHighlight] Restored original style for entity: ${entity.id}`,
      );
    }
  }, []);

  /**
   * Find entities matching acquisition IDs
   */
  const findEntitiesForAcquisitions = useCallback(
    (viewer: any, acquisitionIds: string[]): Entity[] => {
      const matchedEntities: Entity[] = [];
      if (!viewer || !acquisitionIds.length) return matchedEntities;

      // Build a set of patterns to match
      const patterns = new Set<string>();
      for (const acqId of acquisitionIds) {
        patterns.add(acqId);
        patterns.add(`sar_swath_${acqId}`);
        patterns.add(`swath_${acqId}`);
        patterns.add(`opp_${acqId}`);
        patterns.add(`target_${acqId}`);
        // Also match by opportunity_id in entity properties
      }

      // Search in regular entities
      if (viewer.entities?.values) {
        for (const entity of viewer.entities.values) {
          if (matchesAcquisition(entity, acquisitionIds, patterns)) {
            matchedEntities.push(entity);
          }
        }
      }

      // Search in data sources (CZML entities)
      if (viewer.dataSources) {
        for (let i = 0; i < viewer.dataSources.length; i++) {
          const dataSource = viewer.dataSources.get(i);
          if (dataSource?.entities?.values) {
            for (const entity of dataSource.entities.values) {
              if (matchesAcquisition(entity, acquisitionIds, patterns)) {
                matchedEntities.push(entity);
              }
            }
          }
        }
      }

      return matchedEntities;
    },
    [],
  );

  /**
   * Check if an entity matches any acquisition ID
   */
  const matchesAcquisition = (
    entity: Entity,
    acquisitionIds: string[],
    patterns: Set<string>,
  ): boolean => {
    const entityId = entity.id;
    if (!entityId) return false;

    // Direct pattern match
    if (patterns.has(entityId)) return true;

    // Check if entity ID starts with any pattern
    for (const pattern of patterns) {
      if (entityId.startsWith(pattern) || entityId.includes(pattern)) {
        return true;
      }
    }

    // Check entity properties for opportunity_id match
    if (entity.properties) {
      try {
        const opportunityId = entity.properties.opportunity_id?.getValue(null);
        if (opportunityId && acquisitionIds.includes(opportunityId)) {
          return true;
        }

        // Also check target_id for target markers
        const targetId = entity.properties.target_id?.getValue(null);
        if (targetId) {
          // Check if any acquisition targets this target
          // This requires knowledge of acquisition→target mapping
        }
      } catch {
        // Property access failed, continue
      }
    }

    return false;
  };

  /**
   * Clear all highlights
   */
  const clearAllHighlights = useCallback(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer) return;

    const toRestore = highlightedEntitiesRef.current;
    if (toRestore.size === 0) return;

    if (isDev) {
      console.log(
        `[ConflictHighlight] Clearing ${toRestore.size} highlighted entities`,
      );
    }

    // Restore all highlighted entities
    const allEntities: Entity[] = [];

    // Collect from regular entities
    if (viewer.entities?.values) {
      allEntities.push(...viewer.entities.values);
    }

    // Collect from data sources
    if (viewer.dataSources) {
      for (let i = 0; i < viewer.dataSources.length; i++) {
        const dataSource = viewer.dataSources.get(i);
        if (dataSource?.entities?.values) {
          allEntities.push(...dataSource.entities.values);
        }
      }
    }

    for (const entity of allEntities) {
      if (entity.id && toRestore.has(entity.id)) {
        restoreOriginalStyle(entity);
      }
    }

    highlightedEntitiesRef.current.clear();

    // Request render update
    if (viewer.scene) {
      viewer.scene.requestRender();
    }
  }, [viewerRef, restoreOriginalStyle]);

  // Effect: Apply highlighting when conflict acquisitions change
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer) return;

    // Clear previous highlights
    clearAllHighlights();

    // If no conflict selected or no acquisitions to highlight, we're done
    if (!selectedConflictId || highlightedAcquisitionIds.length === 0) {
      if (isDev) {
        console.log(
          "[ConflictHighlight] No conflict selected or no acquisitions to highlight",
        );
      }
      return;
    }

    if (isDev) {
      console.log(
        `[ConflictHighlight] Highlighting ${highlightedAcquisitionIds.length} acquisitions for conflict ${selectedConflictId}`,
      );
    }

    // Find and highlight matching entities
    const entities = findEntitiesForAcquisitions(
      viewer,
      highlightedAcquisitionIds,
    );

    if (isDev) {
      console.log(
        `[ConflictHighlight] Found ${entities.length} entities to highlight`,
      );
    }

    for (const entity of entities) {
      applyHighlightStyle(entity);
      if (entity.id) {
        highlightedEntitiesRef.current.add(entity.id);
      }
    }

    // Request render update
    if (viewer.scene) {
      viewer.scene.requestRender();
    }

    // Update conflict highlight store with resolved entity IDs
    setHighlightedAcquisitions(highlightedAcquisitionIds);
  }, [
    viewerRef,
    highlightedAcquisitionIds,
    selectedConflictId,
    clearAllHighlights,
    findEntitiesForAcquisitions,
    applyHighlightStyle,
    setHighlightedAcquisitions,
  ]);

  // Effect: Focus timeline when conflict time range changes
  useEffect(() => {
    if (!shouldFocus || !timeRange) return;

    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer?.timeline || !viewer?.clock) return;

    try {
      // Parse times and add padding
      const paddingMs = timeRange.padding * 60 * 1000;
      const startTime = new Date(
        new Date(timeRange.start).getTime() - paddingMs,
      );
      const endTime = new Date(new Date(timeRange.end).getTime() + paddingMs);

      const startJulian = JulianDate.fromDate(startTime);
      const endJulian = JulianDate.fromDate(endTime);

      // Focus timeline on conflict window
      viewer.timeline.zoomTo(startJulian, endJulian);

      // Jump clock to start of conflict
      const conflictStart = JulianDate.fromIso8601(timeRange.start);
      viewer.clock.currentTime = conflictStart;
      setClockTime(conflictStart);

      if (isDev) {
        console.log(
          `[ConflictHighlight] Focused timeline on conflict: ${timeRange.start} - ${timeRange.end}`,
        );
      }
    } catch (error) {
      console.error("[ConflictHighlight] Failed to focus timeline:", error);
    }
  }, [viewerRef, timeRange, shouldFocus, setClockTime]);

  // Cleanup on unmount
  useEffect(() => {
    const timeoutRef = cleanupTimeoutRef.current;
    return () => {
      if (timeoutRef) {
        clearTimeout(timeoutRef);
      }
      clearAllHighlights();
      clearHighlights();
    };
  }, [clearAllHighlights, clearHighlights]);

  return {
    clearAllHighlights,
    highlightedCount: highlightedEntitiesRef.current.size,
  };
}

export default useConflictMapHighlight;
