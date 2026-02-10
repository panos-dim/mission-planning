# Cesium Entity ID Contract

This document defines the canonical entity ID patterns used for Cesium map entities in the mission planner. All layers that render Cesium entities MUST follow these patterns to ensure reliable highlighting, selection, and cross-component communication.

## Entity ID Patterns

### Targets

```
target:{targetId}
```

- **Example**: `target:T1`, `target:my-target-123`
- **Entity Types**: Billboard, Label, Point
- **Used By**: Target markers on the map

### Opportunities

```
opp:{opportunityId}
```

- **Example**: `opp:550e8400-e29b-41d4-a716-446655440000`
- **Entity Types**: Polygon (footprint), Point
- **Used By**: Opportunity footprints, planning results

### Acquisitions

```
acq:{acquisitionId}
```

- **Example**: `acq:acq-2024-01-15-001`
- **Entity Types**: Polygon, Point
- **Used By**: Scheduled acquisitions in commit mode

### SAR Swaths

```
swath:{opportunityId}
```

- **Example**: `swath:550e8400-e29b-41d4-a716-446655440000`
- **Entity Types**: Polygon (SAR imaging swath)
- **Notes**: Legacy prefix `sar_swath_{id}` is also supported for backward compatibility

### Ghost Entities (Moved Items Preview)

```
ghost:acq:{acquisitionId}
```

- **Example**: `ghost:acq:acq-2024-01-15-001`
- **Entity Types**: Polygon (faded style showing previous position)
- **Used By**: Repair mode diff preview for moved items

## Legacy Patterns (Backward Compatible)

The following patterns are supported for backward compatibility but new code should use the canonical patterns above:

| Legacy Pattern | Canonical Pattern |
|---------------|------------------|
| `sar_swath_{id}` | `swath:{id}` |
| `target_{id}` | `target:{id}` |
| `opp_{id}` | `opp:{id}` |
| `acq_{id}` | `acq:{id}` |
| `ghost_{id}` | `ghost:acq:{id}` |
| `ghost_swath_{id}` | `ghost:acq:{id}` |

## Entity Resolution Rules

The highlight adapter resolves logical IDs to Cesium entity IDs using these rules:

1. **Direct Match**: Entity ID equals the pattern exactly
2. **Prefix Match**: Entity ID starts with the pattern
3. **Contains Match**: Entity ID contains the pattern (fallback)
4. **Property Match**: Entity has `opportunity_id`, `target_id`, or `acquisition_id` property matching the logical ID

## Highlight Modes

| Mode | Description | Colors |
|------|-------------|--------|
| `conflict` | Scheduling conflict highlighting | Orange fill, red outline |
| `repair` | Repair diff highlighting | Per-type colors (see below) |
| `selection` | Normal selection highlighting | Blue fill, cyan outline |

### Repair Diff Type Colors

| Type | Fill Color | Outline Color |
|------|-----------|---------------|
| `kept` | Green (60% alpha) | Green |
| `dropped` | Red (60% alpha) | Red |
| `added` | Cyan (60% alpha) | Cyan |
| `moved` | Yellow (70% alpha) | Orange |
| `ghost` | White (15% alpha) | White (40% alpha) |

## Implementation

The unified highlight adapter is located at:

```
frontend/src/adapters/highlightAdapter.ts
```

### Key Exports

```typescript
// Entity ID builders
buildEntityId(type: EntityIdType, id: string): string
buildGhostEntityId(id: string): string

// Entity resolution
resolveEntityIds(viewer: Viewer, logicalIds: string[]): Entity[]

// Highlighting
applyHighlight(entities: Entity[], mode: HighlightMode, diffType?: RepairDiffType): void
clearHighlights(entities: Entity[]): void

// Ghost entity management
createGhostClone(viewer: Viewer, sourceEntity: Entity, ghostId: string): Entity | null
removeGhostClone(viewer: Viewer, ghostId: string): void
```

## Best Practices

1. **Always use canonical patterns** when creating new entities
2. **Register entities** with the highlight store when creating them dynamically
3. **Clear highlights** before applying new ones to avoid stale state
4. **Use the adapter** instead of direct entity manipulation for highlighting
5. **Test with both legacy and canonical IDs** to ensure backward compatibility

## Related Documentation

- `docs/PR_CONFLICT_UX_02_CHECKLIST.md` - Conflict highlighting implementation
- `docs/PR_REPAIR_UX_01_CHECKLIST.md` - Repair diff highlighting implementation
- `docs/PR_MAP_HIGHLIGHT_01_CHECKLIST.md` - Unified highlighting test checklist
