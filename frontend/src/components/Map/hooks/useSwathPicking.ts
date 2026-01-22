/**
 * useSwathPicking Hook
 *
 * Handles deterministic picking of SAR swath polygons in Cesium.
 * Ensures clicking a swath:
 * - Selects the correct opportunity in results table
 * - Opens inspector for that opportunity
 * - Highlights only that swath + its target marker
 */

import { useCallback, useRef, useEffect } from "react";
import {
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  defined,
  Entity,
  Cartesian2,
} from "cesium";
import { useSwathStore, SwathProperties } from "../../../store/swathStore";
import { useVisStore } from "../../../store/visStore";
import { useExplorerStore } from "../../../store/explorerStore";

// Cesium Viewer type (from resium)
interface CesiumViewerRef {
  cesiumElement: {
    scene: {
      pick: (position: Cartesian2) => { id?: Entity } | undefined;
      canvas: HTMLCanvasElement;
    };
  } | null;
}

interface UseSwathPickingOptions {
  viewerRef: React.RefObject<CesiumViewerRef | null>;
  enabled?: boolean;
  onSwathSelect?: (opportunityId: string, properties: SwathProperties) => void;
  onSwathHover?: (
    opportunityId: string | null,
    properties: SwathProperties | null
  ) => void;
}

interface PickResult {
  isSwath: boolean;
  entityId: string | null;
  opportunityId: string | null;
  properties: SwathProperties | null;
}

/**
 * Extract swath properties from a Cesium entity
 */
function extractSwathProperties(entity: Entity): SwathProperties | null {
  if (!entity.properties) return null;

  try {
    // Check if this is a SAR swath entity
    const entityType = entity.properties.entity_type?.getValue(null);
    if (entityType !== "sar_swath") return null;

    return {
      opportunity_id: entity.properties.opportunity_id?.getValue(null) ?? "",
      run_id: entity.properties.run_id?.getValue(null) ?? "analysis",
      target_id: entity.properties.target_id?.getValue(null) ?? "",
      pass_index: entity.properties.pass_index?.getValue(null) ?? 0,
      look_side: entity.properties.look_side?.getValue(null) ?? "LEFT",
      pass_direction:
        entity.properties.pass_direction?.getValue(null) ?? "ASCENDING",
      incidence_deg: entity.properties.incidence_deg?.getValue(null) ?? 0,
      swath_width_km: entity.properties.swath_width_km?.getValue(null) ?? 0,
      imaging_time: entity.properties.imaging_time?.getValue(null) ?? "",
      entity_type: entityType,
    };
  } catch {
    return null;
  }
}

/**
 * Check if an entity is a SAR swath
 */
function isSarSwathEntity(entity: Entity): boolean {
  if (!entity.id || typeof entity.id !== "string") return false;

  // Check by ID prefix
  if (entity.id.startsWith("sar_swath_")) return true;

  // Check by properties
  try {
    const entityType = entity.properties?.entity_type?.getValue(null);
    return entityType === "sar_swath";
  } catch {
    return false;
  }
}

export function useSwathPicking({
  viewerRef,
  enabled = true,
  onSwathSelect,
  onSwathHover,
}: UseSwathPickingOptions) {
  const eventHandlerRef = useRef<ScreenSpaceEventHandler | null>(null);
  const lastHoveredRef = useRef<string | null>(null);

  // Store actions
  const { selectSwath, setHoveredSwath, updateDebugInfo } = useSwathStore();
  const { setSelectedOpportunity } = useVisStore();
  const { selectNode } = useExplorerStore();

  /**
   * Pick and analyze clicked position
   */
  const pickSwath = useCallback(
    (position: Cartesian2): PickResult => {
      const viewer = viewerRef.current?.cesiumElement;
      if (!viewer?.scene) {
        return {
          isSwath: false,
          entityId: null,
          opportunityId: null,
          properties: null,
        };
      }

      const pickedObject = viewer.scene.pick(position);

      if (!defined(pickedObject) || !(pickedObject.id instanceof Entity)) {
        return {
          isSwath: false,
          entityId: null,
          opportunityId: null,
          properties: null,
        };
      }

      const entity = pickedObject.id;

      if (!isSarSwathEntity(entity)) {
        return {
          isSwath: false,
          entityId: entity.id,
          opportunityId: null,
          properties: null,
        };
      }

      const properties = extractSwathProperties(entity);
      const opportunityId = properties?.opportunity_id ?? null;

      return {
        isSwath: true,
        entityId: entity.id,
        opportunityId,
        properties,
      };
    },
    [viewerRef]
  );

  /**
   * Handle swath click - select opportunity
   */
  const handleSwathClick = useCallback(
    (click: { position: Cartesian2 }) => {
      if (!enabled) return;

      const result = pickSwath(click.position);

      // Update debug info
      updateDebugInfo({
        pickingHitType: result.isSwath
          ? "sar_swath"
          : result.entityId
          ? "other_entity"
          : "empty",
        lastPickTime: Date.now(),
      });

      if (result.isSwath && result.opportunityId && result.properties) {
        // Select the swath
        selectSwath(result.entityId, result.opportunityId);

        // Sync with visStore for cross-panel sync
        setSelectedOpportunity(result.opportunityId);

        // Try to select corresponding node in explorer
        // Format: opportunity__{target}_{timestamp}_{index}
        const explorerNodeId = `opportunity__${result.opportunityId}`;
        selectNode(explorerNodeId, "opportunity");

        // Call external handler if provided
        onSwathSelect?.(result.opportunityId, result.properties);

        console.log(
          `[SwathPicking] Selected swath: ${result.opportunityId}`,
          result.properties
        );
      } else if (!result.isSwath) {
        // Clicked on non-swath or empty space - clear swath selection
        selectSwath(null, null);
      }
    },
    [
      enabled,
      pickSwath,
      selectSwath,
      setSelectedOpportunity,
      selectNode,
      updateDebugInfo,
      onSwathSelect,
    ]
  );

  /**
   * Handle mouse move - hover highlighting
   */
  const handleMouseMove = useCallback(
    (movement: { endPosition: Cartesian2 }) => {
      if (!enabled) return;

      const result = pickSwath(movement.endPosition);
      const currentHovered = result.isSwath ? result.opportunityId : null;

      // Only update if changed (debounce)
      if (currentHovered !== lastHoveredRef.current) {
        lastHoveredRef.current = currentHovered;

        setHoveredSwath(
          result.isSwath ? result.entityId : null,
          currentHovered
        );

        onSwathHover?.(currentHovered, result.properties);
      }
    },
    [enabled, pickSwath, setHoveredSwath, onSwathHover]
  );

  /**
   * Setup event handlers
   */
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer?.scene?.canvas) return;

    // Cleanup existing handler
    if (eventHandlerRef.current && !eventHandlerRef.current.isDestroyed()) {
      eventHandlerRef.current.destroy();
    }

    // Create new handler
    eventHandlerRef.current = new ScreenSpaceEventHandler(viewer.scene.canvas);

    // Register click handler
    eventHandlerRef.current.setInputAction(
      handleSwathClick,
      ScreenSpaceEventType.LEFT_CLICK
    );

    // Register hover handler (throttled by the handler itself)
    eventHandlerRef.current.setInputAction(
      handleMouseMove,
      ScreenSpaceEventType.MOUSE_MOVE
    );

    return () => {
      if (eventHandlerRef.current && !eventHandlerRef.current.isDestroyed()) {
        eventHandlerRef.current.destroy();
        eventHandlerRef.current = null;
      }
    };
  }, [viewerRef, handleSwathClick, handleMouseMove]);

  return {
    pickSwath,
    handleSwathClick,
    handleMouseMove,
  };
}

export default useSwathPicking;
