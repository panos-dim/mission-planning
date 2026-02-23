# PR-UI-026: Cesium Satellite Color Registry & Groundtrack Object Parity

## Summary

Introduces a deterministic `SatelliteColorRegistry` as the single source of truth for
satellite → color mapping across the Cesium viewer. Satellite entities (point, orbit path,
ground track) now use per-satellite colors from the colorblind-safe Okabe-Ito palette.
Targets and opportunities are **not affected**.

---

## Mapping Rule

**Method:** Index-based palette assignment, preserving backend CZML ordering.

When CZML loads, satellite entity IDs (pattern `sat_<name>`) are collected in document
order and registered with the `SatelliteColorRegistry`. Each satellite receives a palette
index matching the backend's `CZMLGenerator` enumeration order.

For ad-hoc lookups on unregistered IDs, a deterministic djb2 hash is used as fallback.

### Color Palette (Okabe-Ito inspired, colorblind-safe)

| Index | Color Name   | Hex       | Example Satellite      |
|-------|-------------|-----------|------------------------|
| 0     | Sky Blue    | `#56B4E9` | 1st satellite in CZML  |
| 1     | Orange      | `#E69F00` | 2nd satellite          |
| 2     | Rose/Pink   | `#CC79A7` | 3rd satellite          |
| 3     | Teal/Green  | `#009E73` | 4th satellite          |
| 4     | Amber/Gold  | `#F5C242` | 5th satellite          |
| 5     | Deep Blue   | `#0072B2` | 6th satellite          |
| 6     | Vermillion  | `#D55E00` | 7th satellite          |
| 7     | Gray        | `#999999` | 8th satellite          |
| 8+    | Generated   | HSL algo  | Golden-angle distribution |

### Satellite ID → Color Example

```
sat_ICEYE-X7       → #56B4E9 (Sky Blue)
sat_ICEYE-X44      → #E69F00 (Orange)
sat_ICEYE-X44_ground_track → same orange (α=0.4)
```

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/utils/satelliteColors.ts` | **NEW** — `SatelliteColorRegistry` module |
| `frontend/src/components/Map/GlobeViewport.tsx` | Replaced PR-UI-013 brand-blue neutralization with per-satellite coloring from registry |
| `frontend/src/components/Map/SatelliteColorLegend.tsx` | **NEW** — Minimal collapsible legend widget |
| `frontend/src/components/Map/SelectionIndicator.tsx` | Selection ring color adapts to satellite color when a satellite entity is selected |
| `frontend/src/constants/colors.ts` | No changes (palette already existed) |

---

## What Gets Satellite Colors

- ✅ Satellite point marker (entity.point)
- ✅ Satellite orbit path trail (entity.path)
- ✅ Ground track polyline/path (entity with `_ground_track` suffix)
- ✅ Selection indicator ring (when satellite is selected)
- ✅ Legend widget (bottom-right of Cesium viewer)

## What Does NOT Get Satellite Colors (Regression Guard)

- ❌ Target pins — remain blue (default), gray/red/green (planning/schedule mode)
- ❌ Opportunity bars / timeline windows — remain brand blue
- ❌ Schedule acquired status colors — unchanged
- ❌ Pointing cone / agility envelope ellipses — remain brand blue
- ❌ SAR swath polygons — unchanged (separate coloring in `sar_czml.py`)

---

## Regression Check Notes

### Target Coloring (VERIFIED UNCHANGED)

- **Default state:** Blue pins (`#3B82F6`) from backend CZML
- **Planning mode (no scheduler run):** Gray pins (`#6B7280`)
- **Planning mode (post-scheduler):** Blue = acquired, Red = not acquired
- **Schedule mode:** Green = upcoming, Gray = past, Red = not scheduled

All target coloring logic resides in separate `useEffect` blocks in `GlobeViewport.tsx`
that only operate on entities matching `target_` or `preview_target_` ID prefixes.
These blocks were not modified.

### Opportunity Coloring (VERIFIED UNCHANGED)

No satellite coloring is applied to opportunity entities, swath entities, or
timeline/schedule UI. The `onLoad` callback only applies satellite colors to
entities matching `sat_*` and `*_ground_track` patterns.

---

## Manual Verification Steps

1. **Load scenario with ≥3 satellites** → Verify distinct colors per satellite groundtrack
2. **Confirm satellite icon/label** uses the same color as its groundtrack
3. **Switch scenarios / reload** → Colors remain consistent for same satellite IDs
4. **Confirm targets/opportunities** colors unchanged (no satellite coloring leaks)
5. **Build passes** → `npx tsc --noEmit` ✅, `npx vite build` ✅, ESLint 0 errors ✅
6. **Selection highlight** → Click on satellite: ring pulses in satellite color; click on target: ring is default blue
7. **Legend widget** → Bottom-right of viewer shows satellite name + color swatch; collapsible

---

## Screenshot Placeholder

> **TODO:** Add screenshot of Cesium viewer showing multiple colored groundtracks + satellites
> after manual verification with a multi-satellite scenario.
