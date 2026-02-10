/**
 * useRepairMapHighlight Hook
 *
 * Applies visual highlighting to Cesium entities for repair diff items.
 * Supports different styles for kept, dropped, added, and moved items.
 * For moved items, shows ghost (previous) and solid (new) footprints.
 *
 * Part of PR-REPAIR-UX-01
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
import {
  useRepairHighlightStore,
  useRepairTimeRangeValue,
  useRepairShouldFocusTimeline,
  type RepairDiffType,
} from "../store/repairHighlightStore";
import { useVisStore } from "../store/visStore";

// Dev mode check
const isDev = import.meta.env?.DEV ?? false;

// =============================================================================
// Highlight Colors by Repair Diff Type
// =============================================================================

const REPAIR_COLORS: Record<
  RepairDiffType,
  { fill: Color; outline: Color; glow: Color }
> = {
  kept: {
    fill: Color.GREEN.withAlpha(0.6),
    outline: Color.GREEN,
    glow: Color.GREEN.withAlpha(0.4),
  },
  dropped: {
    fill: Color.RED.withAlpha(0.6),
    outline: Color.RED,
    glow: Color.RED.withAlpha(0.4),
  },
  added: {
    fill: Color.CYAN.withAlpha(0.6),
    outline: Color.CYAN,
    glow: Color.CYAN.withAlpha(0.4),
  },
  moved: {
    fill: Color.YELLOW.withAlpha(0.7),
    outline: Color.ORANGE,
    glow: Color.YELLOW.withAlpha(0.5),
  },
};

// Ghost style for moved items (shows previous position)
const GHOST_COLOR = {
  fill: Color.WHITE.withAlpha(0.15),
  outline: Color.WHITE.withAlpha(0.4),
  dashed: true,
};

// Original style storage key on entity
const ORIGINAL_STYLE_KEY = "__repairOriginalStyle";

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

// =============================================================================
// Hook Implementation
// =============================================================================

/**
 * Hook to apply repair diff highlighting to Cesium entities
 * @param viewerRef - Ref to the Cesium viewer
 */
export function useRepairMapHighlight(viewerRef: React.RefObject<any>) {
  // Track previously highlighted entities for cleanup
  const highlightedEntitiesRef = useRef<Set<string>>(new Set());
  const ghostEntitiesRef = useRef<Set<string>>(new Set());
  const cleanupTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Repair highlight store state
  const selectedDiffItem = useRepairHighlightStore((s) => s.selectedDiffItem);
  const highlightedEntityIds = useRepairHighlightStore(
    (s) => s.highlightedEntityIds,
  );
  const ghostEntityIds = useRepairHighlightStore((s) => s.ghostEntityIds);
  const clearSelection = useRepairHighlightStore((s) => s.clearSelection);

  // Timeline focus
  const timeRange = useRepairTimeRangeValue();
  const shouldFocus = useRepairShouldFocusTimeline();
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
   * Apply repair highlight styling to an entity based on diff type
   */
  const applyHighlightStyle = useCallback(
    (entity: Entity, diffType: RepairDiffType): void => {
      storeOriginalStyle(entity);

      const colors = REPAIR_COLORS[diffType];

      // Highlight polygons (SAR swaths, footprints)
      if (entity.polygon) {
        (entity.polygon as any).material = new ColorMaterialProperty(
          colors.fill,
        );
        entity.polygon.outlineColor = new ConstantProperty(colors.outline);
        entity.polygon.outlineWidth = new ConstantProperty(3);
        entity.polygon.outline = new ConstantProperty(true);
      }

      // Highlight points (targets)
      if (entity.point) {
        entity.point.color = new ConstantProperty(colors.fill);
        entity.point.outlineColor = new ConstantProperty(colors.outline);
        entity.point.outlineWidth = new ConstantProperty(3);
        entity.point.pixelSize = new ConstantProperty(15);
      }

      // Highlight billboards (target markers)
      if (entity.billboard) {
        entity.billboard.color = new ConstantProperty(colors.glow);
        entity.billboard.scale = new ConstantProperty(1.5);
      }

      if (isDev) {
        console.log(
          `[RepairHighlight] Applied ${diffType} highlight to entity: ${entity.id}`,
        );
      }
    },
    [storeOriginalStyle],
  );

  /**
   * Apply ghost styling for moved items (previous position)
   */
  const applyGhostStyle = useCallback(
    (entity: Entity): void => {
      storeOriginalStyle(entity);

      if (entity.polygon) {
        (entity.polygon as any).material = new ColorMaterialProperty(
          GHOST_COLOR.fill,
        );
        entity.polygon.outlineColor = new ConstantProperty(GHOST_COLOR.outline);
        entity.polygon.outlineWidth = new ConstantProperty(2);
        entity.polygon.outline = new ConstantProperty(true);
      }

      if (entity.point) {
        entity.point.color = new ConstantProperty(GHOST_COLOR.fill);
        entity.point.outlineColor = new ConstantProperty(GHOST_COLOR.outline);
        entity.point.outlineWidth = new ConstantProperty(2);
        entity.point.pixelSize = new ConstantProperty(10);
      }

      if (isDev) {
        console.log(
          `[RepairHighlight] Applied ghost style to entity: ${entity.id}`,
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
        `[RepairHighlight] Restored original style for entity: ${entity.id}`,
      );
    }
  }, []);

  /**
   * Find entities matching IDs
   */
  const findEntitiesForIds = useCallback(
    (viewer: any, itemIds: string[]): Entity[] => {
      const matchedEntities: Entity[] = [];
      if (!viewer || !itemIds.length) return matchedEntities;

      // Build a set of patterns to match
      const patterns = new Set<string>();
      for (const itemId of itemIds) {
        patterns.add(itemId);
        patterns.add(`sar_swath_${itemId}`);
        patterns.add(`swath_${itemId}`);
        patterns.add(`opp_${itemId}`);
        patterns.add(`target_${itemId}`);
        patterns.add(`acq_${itemId}`);
        patterns.add(`ghost_${itemId}`);
        patterns.add(`ghost_swath_${itemId}`);
      }

      const matchesPattern = (entity: Entity): boolean => {
        const entityId = entity.id;
        if (!entityId) return false;

        if (patterns.has(entityId)) return true;

        for (const pattern of patterns) {
          if (entityId.startsWith(pattern) || entityId.includes(pattern)) {
            return true;
          }
        }

        // Check entity properties
        if (entity.properties) {
          try {
            const opportunityId = entity.properties.opportunity_id?.getValue(
              null,
            );
            if (opportunityId && itemIds.includes(opportunityId)) {
              return true;
            }
          } catch {
            // Property access failed
          }
        }

        return false;
      };

      // Search in regular entities
      if (viewer.entities?.values) {
        for (const entity of viewer.entities.values) {
          if (matchesPattern(entity)) {
            matchedEntities.push(entity);
          }
        }
      }

      // Search in data sources
      if (viewer.dataSources) {
        for (let i = 0; i < viewer.dataSources.length; i++) {
          const dataSource = viewer.dataSources.get(i);
          if (dataSource?.entities?.values) {
            for (const entity of dataSource.entities.values) {
              if (matchesPattern(entity)) {
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
   * Clear all highlights
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
        `[RepairHighlight] Clearing ${toRestore.size} highlighted entities`,
      );
    }

    // Collect all entities
    const allEntities: Entity[] = [];

    if (viewer.entities?.values) {
      allEntities.push(...viewer.entities.values);
    }

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
    ghostEntitiesRef.current.clear();

    // Request render update
    if (viewer.scene) {
      viewer.scene.requestRender();
    }
  }, [viewerRef, restoreOriginalStyle]);

  // Effect: Apply highlighting when repair diff selection changes
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer) return;

    // Clear previous highlights
    clearAllHighlights();

    // If no item selected, we're done
    if (!selectedDiffItem || highlightedEntityIds.length === 0) {
      if (isDev) {
        console.log(
          "[RepairHighlight] No repair item selected or no entities to highlight",
        );
      }
      return;
    }

    if (isDev) {
      console.log(
        `[RepairHighlight] Highlighting ${highlightedEntityIds.length} entities for ${selectedDiffItem.type} item ${selectedDiffItem.id}`,
      );
    }

    // Find and highlight primary entities (solid style)
    const primaryIds = highlightedEntityIds.filter(
      (id) => !id.startsWith("ghost_"),
    );
    const primaryEntities = findEntitiesForIds(viewer, primaryIds);

    for (const entity of primaryEntities) {
      applyHighlightStyle(entity, selectedDiffItem.type);
      if (entity.id) {
        highlightedEntitiesRef.current.add(entity.id);
      }
    }

    // For moved items, also apply ghost style
    if (selectedDiffItem.type === "moved" && ghostEntityIds.length > 0) {
      const ghostEntities = findEntitiesForIds(viewer, ghostEntityIds);

      for (const entity of ghostEntities) {
        applyGhostStyle(entity);
        if (entity.id) {
          ghostEntitiesRef.current.add(entity.id);
        }
      }

      if (isDev) {
        console.log(
          `[RepairHighlight] Applied ghost style to ${ghostEntities.length} entities`,
        );
      }
    }

    // Request render update
    if (viewer.scene) {
      viewer.scene.requestRender();
    }

    if (isDev) {
      console.log(
        `[RepairHighlight] Highlighted ${primaryEntities.length} primary entities`,
      );
    }
  }, [
    viewerRef,
    highlightedEntityIds,
    ghostEntityIds,
    selectedDiffItem,
    clearAllHighlights,
    findEntitiesForIds,
    applyHighlightStyle,
    applyGhostStyle,
  ]);

  // Effect: Focus timeline when repair time range changes
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

      // Focus timeline on repair item window
      viewer.timeline.zoomTo(startJulian, endJulian);

      // Jump clock to start of the time range
      const itemStart = JulianDate.fromIso8601(timeRange.start);
      viewer.clock.currentTime = itemStart;
      setClockTime(itemStart);

      if (isDev) {
        console.log(
          `[RepairHighlight] Focused timeline: ${timeRange.start} - ${timeRange.end}`,
        );
      }
    } catch (error) {
      console.error("[RepairHighlight] Failed to focus timeline:", error);
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
      clearSelection();
    };
  }, [clearAllHighlights, clearSelection]);

  return {
    clearAllHighlights,
    highlightedCount: highlightedEntitiesRef.current.size,
    ghostCount: ghostEntitiesRef.current.size,
  };
}

export default useRepairMapHighlight;
