/**
 * Highlight Adapter
 *
 * Unified adapter for applying Cesium entity highlighting across all selection modes:
 * - Conflict highlighting (orange)
 * - Repair diff highlighting (kept/dropped/added/moved with per-type colors)
 * - Normal selection highlighting (blue)
 *
 * Implements the Cesium Entity ID Contract (docs/CESIUM_ENTITY_ID_CONTRACT.md)
 *
 * Part of PR-MAP-HIGHLIGHT-01
 */

import {
  Color,
  Entity,
  ColorMaterialProperty,
  ConstantProperty,
  Property,
  JulianDate,
} from "cesium";

const isDev = import.meta.env?.DEV ?? false;

// =============================================================================
// Types
// =============================================================================

export type EntityIdType = "target" | "opp" | "acq" | "swath" | "ghost";
export type HighlightMode = "conflict" | "repair" | "selection";
export type RepairDiffType = "kept" | "dropped" | "added" | "moved";

export interface HighlightRequest {
  mode: HighlightMode;
  ids: string[];
  diffType?: RepairDiffType;
  ghostIds?: string[];
}

export interface OriginalEntityStyle {
  polygonMaterial?: Property | undefined;
  polygonOutlineColor?: Property | undefined;
  polygonOutlineWidth?: Property | undefined;
  polygonOutline?: Property | undefined;
  pointColor?: Property | undefined;
  pointOutlineColor?: Property | undefined;
  pointOutlineWidth?: Property | undefined;
  pointPixelSize?: Property | undefined;
  billboardColor?: Property | undefined;
  billboardScale?: Property | undefined;
}

// Storage key for original style on entity
const ORIGINAL_STYLE_KEY = "__highlightOriginalStyle";
const GHOST_CLONE_KEY = "__isGhostClone";

// =============================================================================
// Color Definitions
// =============================================================================

const HIGHLIGHT_COLORS = {
  conflict: {
    fill: Color.ORANGE.withAlpha(0.9),
    outline: Color.RED,
    glow: Color.ORANGE.withAlpha(0.5),
  },
  selection: {
    fill: Color.DODGERBLUE.withAlpha(0.7),
    outline: Color.CYAN,
    glow: Color.DODGERBLUE.withAlpha(0.5),
  },
  repair: {
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
  },
  ghost: {
    fill: Color.WHITE.withAlpha(0.15),
    outline: Color.WHITE.withAlpha(0.4),
    glow: Color.WHITE.withAlpha(0.2),
  },
};

// =============================================================================
// Entity ID Builders (Canonical Format)
// =============================================================================

export function buildEntityId(type: EntityIdType, id: string): string {
  return `${type}:${id}`;
}

export function buildGhostEntityId(id: string): string {
  return `ghost:acq:${id}`;
}

// =============================================================================
// Entity ID Pattern Matching
// =============================================================================

const LEGACY_PATTERNS: Record<string, string[]> = {
  target: ["target:", "target_"],
  opp: ["opp:", "opp_"],
  acq: ["acq:", "acq_"],
  swath: ["swath:", "swath_", "sar_swath_"],
  ghost: ["ghost:", "ghost_", "ghost_swath_"],
};

function buildPatternSet(logicalIds: string[]): Set<string> {
  const patterns = new Set<string>();

  for (const id of logicalIds) {
    // Add the raw ID
    patterns.add(id);

    // Add all canonical and legacy patterns
    for (const type of Object.keys(LEGACY_PATTERNS)) {
      for (const prefix of LEGACY_PATTERNS[type]) {
        patterns.add(`${prefix}${id}`);
      }
    }
  }

  return patterns;
}

function entityMatchesPatterns(
  entity: Entity,
  logicalIds: string[],
  patterns: Set<string>,
): boolean {
  const entityId = entity.id;
  if (!entityId) return false;

  // Direct pattern match
  if (patterns.has(entityId)) return true;

  // Check if entity ID starts with or contains any pattern
  for (const pattern of patterns) {
    if (entityId === pattern) return true;
    if (entityId.startsWith(pattern)) return true;
    // Only use contains for specific ID formats to avoid false positives
    if (pattern.includes(":") && entityId.includes(pattern)) return true;
  }

  // Check entity properties for matching IDs
  if (entity.properties) {
    try {
      const opportunityId = entity.properties.opportunity_id?.getValue(null);
      if (opportunityId && logicalIds.includes(opportunityId)) {
        return true;
      }

      const acquisitionId = entity.properties.acquisition_id?.getValue(null);
      if (acquisitionId && logicalIds.includes(acquisitionId)) {
        return true;
      }

      const targetId = entity.properties.target_id?.getValue(null);
      if (targetId && logicalIds.includes(targetId)) {
        return true;
      }
    } catch {
      // Property access failed, continue
    }
  }

  return false;
}

// =============================================================================
// Entity Resolution (O(k) with caching)
// =============================================================================

// Cache for entity lookups - invalidated when viewer entities change
let entityCache: Map<string, Entity> | null = null;
let lastCacheSize = 0;

function buildEntityCache(viewer: any): Map<string, Entity> {
  const cache = new Map<string, Entity>();

  // Collect from regular entities
  if (viewer.entities?.values) {
    for (const entity of viewer.entities.values) {
      if (entity.id) {
        cache.set(entity.id, entity);
      }
    }
  }

  // Collect from data sources
  if (viewer.dataSources) {
    for (let i = 0; i < viewer.dataSources.length; i++) {
      const dataSource = viewer.dataSources.get(i);
      if (dataSource?.entities?.values) {
        for (const entity of dataSource.entities.values) {
          if (entity.id) {
            cache.set(entity.id, entity);
          }
        }
      }
    }
  }

  return cache;
}

function getEntityCache(viewer: any): Map<string, Entity> {
  // Simple cache invalidation: if entity count changed, rebuild
  let currentSize = 0;
  if (viewer.entities?.values) {
    currentSize += viewer.entities.values.length;
  }
  if (viewer.dataSources) {
    for (let i = 0; i < viewer.dataSources.length; i++) {
      const dataSource = viewer.dataSources.get(i);
      if (dataSource?.entities?.values) {
        currentSize += dataSource.entities.values.length;
      }
    }
  }

  if (!entityCache || currentSize !== lastCacheSize) {
    entityCache = buildEntityCache(viewer);
    lastCacheSize = currentSize;
    if (isDev) {
      console.log(
        `[HighlightAdapter] Rebuilt entity cache: ${entityCache.size} entities`,
      );
    }
  }

  return entityCache;
}

export function invalidateEntityCache(): void {
  entityCache = null;
  lastCacheSize = 0;
}

export function resolveEntityIds(viewer: any, logicalIds: string[]): Entity[] {
  if (!viewer || !logicalIds.length) return [];

  const cache = getEntityCache(viewer);
  const patterns = buildPatternSet(logicalIds);
  const matchedEntities: Entity[] = [];
  const matchedIds = new Set<string>();

  // O(k) lookup using patterns against cache
  for (const pattern of patterns) {
    const entity = cache.get(pattern);
    if (entity && !matchedIds.has(entity.id)) {
      matchedEntities.push(entity);
      matchedIds.add(entity.id);
    }
  }

  // Fallback: scan cache for property matches (only if direct lookup missed some)
  if (matchedEntities.length < logicalIds.length) {
    for (const entity of cache.values()) {
      if (matchedIds.has(entity.id)) continue;
      if (entityMatchesPatterns(entity, logicalIds, patterns)) {
        matchedEntities.push(entity);
        matchedIds.add(entity.id);
      }
    }
  }

  return matchedEntities;
}

// =============================================================================
// Style Management
// =============================================================================

function storeOriginalStyle(entity: Entity): void {
  if ((entity as any)[ORIGINAL_STYLE_KEY]) return; // Already stored

  const original: OriginalEntityStyle = {};

  if (entity.polygon) {
    original.polygonMaterial = entity.polygon.material;
    original.polygonOutlineColor = entity.polygon.outlineColor;
    original.polygonOutlineWidth = entity.polygon.outlineWidth;
    original.polygonOutline = entity.polygon.outline;
  }

  if (entity.point) {
    original.pointColor = entity.point.color;
    original.pointOutlineColor = entity.point.outlineColor;
    original.pointOutlineWidth = entity.point.outlineWidth;
    original.pointPixelSize = entity.point.pixelSize;
  }

  if (entity.billboard) {
    original.billboardColor = entity.billboard.color;
    original.billboardScale = entity.billboard.scale;
  }

  (entity as any)[ORIGINAL_STYLE_KEY] = original;
}

function restoreOriginalStyle(entity: Entity): void {
  const original = (entity as any)[ORIGINAL_STYLE_KEY] as
    | OriginalEntityStyle
    | undefined;
  if (!original) return;

  if (entity.polygon) {
    if (original.polygonMaterial !== undefined) {
      (entity.polygon as any).material = original.polygonMaterial;
    }
    if (original.polygonOutlineColor !== undefined) {
      (entity.polygon as any).outlineColor = original.polygonOutlineColor;
    }
    if (original.polygonOutlineWidth !== undefined) {
      entity.polygon.outlineWidth = original.polygonOutlineWidth;
    }
    if (original.polygonOutline !== undefined) {
      entity.polygon.outline = original.polygonOutline;
    }
  }

  if (entity.point) {
    if (original.pointColor !== undefined) {
      entity.point.color = original.pointColor;
    }
    if (original.pointOutlineColor !== undefined) {
      entity.point.outlineColor = original.pointOutlineColor;
    }
    if (original.pointOutlineWidth !== undefined) {
      entity.point.outlineWidth = original.pointOutlineWidth;
    }
    if (original.pointPixelSize !== undefined) {
      entity.point.pixelSize = original.pointPixelSize;
    }
  }

  if (entity.billboard) {
    if (original.billboardColor !== undefined) {
      entity.billboard.color = original.billboardColor;
    }
    if (original.billboardScale !== undefined) {
      entity.billboard.scale = original.billboardScale;
    }
  }

  delete (entity as any)[ORIGINAL_STYLE_KEY];
}

function getColorsForMode(
  mode: HighlightMode,
  diffType?: RepairDiffType,
): { fill: Color; outline: Color; glow: Color } {
  if (mode === "repair" && diffType) {
    return HIGHLIGHT_COLORS.repair[diffType];
  }
  if (mode === "conflict") {
    return HIGHLIGHT_COLORS.conflict;
  }
  return HIGHLIGHT_COLORS.selection;
}

function applyStyleToEntity(
  entity: Entity,
  colors: { fill: Color; outline: Color; glow: Color },
): void {
  storeOriginalStyle(entity);

  // Highlight polygons (SAR swaths, footprints)
  if (entity.polygon) {
    (entity.polygon as any).material = new ColorMaterialProperty(colors.fill);
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
}

function applyGhostStyleToEntity(entity: Entity): void {
  storeOriginalStyle(entity);
  const colors = HIGHLIGHT_COLORS.ghost;

  if (entity.polygon) {
    (entity.polygon as any).material = new ColorMaterialProperty(colors.fill);
    entity.polygon.outlineColor = new ConstantProperty(colors.outline);
    entity.polygon.outlineWidth = new ConstantProperty(2);
    entity.polygon.outline = new ConstantProperty(true);
  }

  if (entity.point) {
    entity.point.color = new ConstantProperty(colors.fill);
    entity.point.outlineColor = new ConstantProperty(colors.outline);
    entity.point.outlineWidth = new ConstantProperty(2);
    entity.point.pixelSize = new ConstantProperty(10);
  }

  if (entity.billboard) {
    entity.billboard.color = new ConstantProperty(colors.glow);
    entity.billboard.scale = new ConstantProperty(1.2);
  }
}

// =============================================================================
// Public API: Highlighting
// =============================================================================

export function applyHighlight(
  entities: Entity[],
  mode: HighlightMode,
  diffType?: RepairDiffType,
): void {
  const colors = getColorsForMode(mode, diffType);

  for (const entity of entities) {
    applyStyleToEntity(entity, colors);
  }

  if (isDev) {
    console.log(
      `[HighlightAdapter] Applied ${mode}${diffType ? `:${diffType}` : ""} highlight to ${entities.length} entities`,
    );
  }
}

export function applyGhostHighlight(entities: Entity[]): void {
  for (const entity of entities) {
    applyGhostStyleToEntity(entity);
  }

  if (isDev) {
    console.log(
      `[HighlightAdapter] Applied ghost highlight to ${entities.length} entities`,
    );
  }
}

export function clearHighlights(entities: Entity[]): void {
  for (const entity of entities) {
    restoreOriginalStyle(entity);
  }

  if (isDev && entities.length > 0) {
    console.log(
      `[HighlightAdapter] Cleared highlights from ${entities.length} entities`,
    );
  }
}

// =============================================================================
// Ghost Entity Clone Management
// =============================================================================

// Track created ghost clones for cleanup
const createdGhostClones = new Set<string>();

export function createGhostClone(
  viewer: any,
  sourceEntity: Entity,
  ghostId: string,
): Entity | null {
  if (!viewer || !sourceEntity) return null;

  // Check if ghost entity already exists
  const existingGhost = viewer.entities.getById(ghostId);
  if (existingGhost) {
    if (isDev) {
      console.log(`[HighlightAdapter] Ghost entity already exists: ${ghostId}`);
    }
    return existingGhost;
  }

  try {
    // Create a lightweight clone with the same geometry
    const cloneOptions: any = {
      id: ghostId,
      name: `Ghost: ${sourceEntity.name || sourceEntity.id}`,
    };

    // Clone polygon if present
    if (sourceEntity.polygon) {
      const hierarchy = sourceEntity.polygon.hierarchy?.getValue(
        JulianDate.now(),
      );
      if (hierarchy) {
        cloneOptions.polygon = {
          hierarchy: hierarchy,
          material: new ColorMaterialProperty(HIGHLIGHT_COLORS.ghost.fill),
          outline: true,
          outlineColor: HIGHLIGHT_COLORS.ghost.outline,
          outlineWidth: 2,
          height: 0,
          heightReference: sourceEntity.polygon.heightReference?.getValue(
            JulianDate.now(),
          ),
        };
      }
    }

    // Clone point if present
    if (sourceEntity.point) {
      const position = sourceEntity.position?.getValue(JulianDate.now());
      if (position) {
        cloneOptions.position = position;
        cloneOptions.point = {
          color: HIGHLIGHT_COLORS.ghost.fill,
          outlineColor: HIGHLIGHT_COLORS.ghost.outline,
          outlineWidth: 2,
          pixelSize: 10,
        };
      }
    }

    // Clone billboard if present (for target markers)
    if (sourceEntity.billboard && sourceEntity.position) {
      const position = sourceEntity.position.getValue(JulianDate.now());
      if (position) {
        cloneOptions.position = position;
        cloneOptions.billboard = {
          image: sourceEntity.billboard.image?.getValue(JulianDate.now()),
          color: HIGHLIGHT_COLORS.ghost.glow,
          scale: 1.0,
          verticalOrigin: sourceEntity.billboard.verticalOrigin?.getValue(
            JulianDate.now(),
          ),
          horizontalOrigin: sourceEntity.billboard.horizontalOrigin?.getValue(
            JulianDate.now(),
          ),
        };
      }
    }

    // Only create if we have something to clone
    if (
      !cloneOptions.polygon &&
      !cloneOptions.point &&
      !cloneOptions.billboard
    ) {
      if (isDev) {
        console.log(
          `[HighlightAdapter] Cannot create ghost clone - no clonable geometry for ${sourceEntity.id}`,
        );
      }
      return null;
    }

    const ghostEntity = viewer.entities.add(cloneOptions);
    (ghostEntity as any)[GHOST_CLONE_KEY] = true;
    createdGhostClones.add(ghostId);

    if (isDev) {
      console.log(`[HighlightAdapter] Created ghost clone: ${ghostId}`);
    }

    return ghostEntity;
  } catch (error) {
    console.error(`[HighlightAdapter] Failed to create ghost clone:`, error);
    return null;
  }
}

export function removeGhostClone(viewer: any, ghostId: string): void {
  if (!viewer) return;

  const entity = viewer.entities.getById(ghostId);
  if (entity && (entity as any)[GHOST_CLONE_KEY]) {
    viewer.entities.remove(entity);
    createdGhostClones.delete(ghostId);

    if (isDev) {
      console.log(`[HighlightAdapter] Removed ghost clone: ${ghostId}`);
    }
  }
}

export function removeAllGhostClones(viewer: any): void {
  if (!viewer) return;

  for (const ghostId of createdGhostClones) {
    const entity = viewer.entities.getById(ghostId);
    if (entity) {
      viewer.entities.remove(entity);
    }
  }

  const count = createdGhostClones.size;
  createdGhostClones.clear();

  if (isDev && count > 0) {
    console.log(`[HighlightAdapter] Removed ${count} ghost clones`);
  }
}

export function getCreatedGhostCloneIds(): string[] {
  return Array.from(createdGhostClones);
}

// =============================================================================
// Unified Highlight Controller
// =============================================================================

export interface HighlightController {
  highlightedEntityIds: Set<string>;
  ghostEntityIds: Set<string>;

  applyHighlights: (request: HighlightRequest) => void;
  clearAll: () => void;
}

export function createHighlightController(
  viewerRef: React.RefObject<any>,
): HighlightController {
  const highlightedEntityIds = new Set<string>();
  const ghostEntityIds = new Set<string>();

  const getViewer = () => viewerRef.current?.cesiumElement;

  return {
    highlightedEntityIds,
    ghostEntityIds,

    applyHighlights(request: HighlightRequest) {
      const viewer = getViewer();
      if (!viewer) return;

      // Clear previous highlights first
      this.clearAll();

      // Resolve and highlight primary entities
      const primaryIds = request.ids.filter((id) => !id.startsWith("ghost"));
      const primaryEntities = resolveEntityIds(viewer, primaryIds);

      applyHighlight(primaryEntities, request.mode, request.diffType);

      for (const entity of primaryEntities) {
        if (entity.id) {
          highlightedEntityIds.add(entity.id);
        }
      }

      // Handle ghost entities for moved items
      if (request.ghostIds && request.ghostIds.length > 0) {
        const ghostEntities = resolveEntityIds(viewer, request.ghostIds);

        // If ghost entities don't exist, try to create clones
        if (ghostEntities.length === 0 && primaryEntities.length > 0) {
          for (let i = 0; i < request.ghostIds.length; i++) {
            const ghostId = request.ghostIds[i];
            const sourceEntity = primaryEntities[i % primaryEntities.length];
            const clone = createGhostClone(viewer, sourceEntity, ghostId);
            if (clone) {
              ghostEntities.push(clone);
            }
          }
        }

        applyGhostHighlight(ghostEntities);

        for (const entity of ghostEntities) {
          if (entity.id) {
            ghostEntityIds.add(entity.id);
          }
        }
      }

      // Request render update
      if (viewer.scene) {
        viewer.scene.requestRender();
      }
    },

    clearAll() {
      const viewer = getViewer();
      if (!viewer) return;

      // Restore highlighted entities
      if (highlightedEntityIds.size > 0 || ghostEntityIds.size > 0) {
        const allIds = [
          ...Array.from(highlightedEntityIds),
          ...Array.from(ghostEntityIds),
        ];
        const entities = resolveEntityIds(viewer, allIds);
        clearHighlights(entities);
      }

      // Remove any created ghost clones
      removeAllGhostClones(viewer);

      highlightedEntityIds.clear();
      ghostEntityIds.clear();

      // Request render update
      if (viewer.scene) {
        viewer.scene.requestRender();
      }
    },
  };
}

// =============================================================================
// Exports for Stores
// =============================================================================

export { HIGHLIGHT_COLORS };
