# PR-UI-022 Checklist — Target Colors, Planning States, Feasibility Results Redesign

## Scope

### A) Target Color Policy (Global)

| Item | Status | Details |
|------|--------|---------|
| Remove `TARGET_COLORS` array from `TargetInput.tsx` | ✅ Done | Replaced with `BRAND_BLUE = '#3B82F6'` |
| Remove color picker UI from `TargetInput.tsx` | ✅ Done | Removed hover dropdown, randomize button, color dots |
| Remove color picker from `TargetConfirmPanel.tsx` | ✅ Done | Removed `Palette` import, `TARGET_COLORS`, color picker grid |
| Remove color picker from `TargetDetailsSheet.tsx` | ✅ Done | Removed `Palette` import, `TARGET_COLORS`, color picker grid |
| Default color = brand blue in `targetAddStore.ts` | ✅ Done | `pendingColor: '#3B82F6'` everywhere |
| Default color = brand blue in `GlobeViewport.tsx` preview | ✅ Done | Fallback changed from `#EF4444` → `#3B82F6` |
| Default color = brand blue in backend `czml_generator.py` | ✅ Done | Fallback changed from `#EF4444` → `#3B82F6` |
| Target icon in target list uses brand blue | ✅ Done | `style={{ color: BRAND_BLUE }}` |
| Gulf sample targets all brand blue | ✅ Done | `OrdersPanel.tsx` `GULF_SAMPLE_TARGETS` — was mixed colors |
| `OrderTargetRow` icon always blue | ✅ Done | `text-blue-500` class, no longer reads `target.color` |
| `InlineTargetAdd` default color blue | ✅ Done | `color: '#3B82F6'` |
| File upload targets default blue | ✅ Done | `OrdersPanel.tsx` upload handler |

### B) Planning Map — Three-State Color Logic

| Item | Status | Details |
|------|--------|---------|
| No scheduler run: targets = **gray** | ✅ Done | `#6B7280` (gray-500) — neutral until scheduler runs |
| After scheduling: acquired targets = **blue** | ✅ Done | `#3B82F6` (blue-500) |
| After scheduling: unscheduled targets = **red** | ✅ Done | `#EF4444` (red-500) |
| Schedule-mode: acquired = blue, not-acquired = red | ✅ Done | Was green/red, now blue/red |
| No green target coloring anywhere | ✅ Done | All green target references replaced with blue |

### C) Remove Opportunities from Planning Left Pane

| Item | Status | Details |
|------|--------|---------|
| Remove "No Opportunities Available" guidance block | ✅ Done | Removed from `MissionPlanning.tsx` |
| Keep status bar (compact one-liner) | ✅ Done | "Run Feasibility Analysis first to enable scheduling." |
| Rename "opportunities" → "acquisitions" in schedule table header | ✅ Done | `Schedule ({n} acquisition{s})` |
| Keep `useOpportunities` hook (internal scheduler dependency) | ✅ Done | Not exposed in UI |

### D) Feasibility Results Panel Redesign

| Item | Status | Details |
|------|--------|---------|
| Remove Opportunities section entirely | ✅ Done | Removed ~280 lines of per-target opportunity cards, SAR filters, target expansion |
| Remove collapsible `SectionHeader` wrapper | ✅ Done | Timeline is now a fixed header — always visible, no expand/collapse |
| Fixed header with Clock icon + coverage badge + satellite name | ✅ Done | Static `bg-gray-800/95` header bar |
| Mission time range in header | ✅ Done | Start/End displayed inline |
| Click-to-filter UX for target pills | ✅ Done | Click target → exclusive select; click more → additive; all deselected → show all |
| "Show all" reset button | ✅ Done | Appears when any filter is active |
| Lane labels clickable (same filter logic) | ✅ Done | Target names in timeline lanes trigger filter |
| Target pills: blue ring for selected, gray for visible, dimmed for filtered | ✅ Done | Three visual states + disabled for 0-opp targets |
| Coverage badge slightly larger | ✅ Done | `text-xs font-semibold px-2` |
| Timeline lane border green → blue | ✅ Done | `border-blue-500` |
| MapPin icon color: gray → blue | ✅ Done | `text-blue-400` |
| Cleaned up unused imports/state | ✅ Done | Removed `Calendar`, `Target`, `ChevronDown/Right`, `SectionHeader`, `useVisStore`, `useSwathStore`, SAR filter state, target expansion state, `getOpportunityColor`, `opportunityHoverTitle` |
| Empty state steps: green/purple badges → all blue | ✅ Done | Consistent brand blue |

### E) Additional Green → Blue Consistency

| Item | Status | Details |
|------|--------|---------|
| `OpportunityMetricsCard.tsx` target label: green → blue | ✅ Done | Satellite→target label now both blue |

### F) Pre-Existing Type Fixes

| Item | Status | Details |
|------|--------|---------|
| `GlobeViewport.tsx` `loadedDataSource` typed as `any` | ✅ Fixed | `DataSource \| null` from cesium |
| `GlobeViewport.tsx` billboard image `as any` casts (lines 503-506) | ✅ Fixed | Proper `Property` and `{ valueOf: () => unknown }` types |

## Rule Definition: Target Color States

| View | No Results | Acquired | Not Acquired |
|------|-----------|----------|--------------|
| **General map / Feasibility** | Brand blue | Brand blue | Brand blue |
| **Planning map (no scheduler run)** | Gray | — | — |
| **Planning map (after scheduling)** | — | Blue | Red |
| **Schedule map (committed orders)** | — | Blue | Red |

## Files Changed

### Frontend

- `frontend/src/components/TargetInput.tsx` — Removed `TARGET_COLORS`, color picker, randomize button; default blue
- `frontend/src/components/Targets/TargetConfirmPanel.tsx` — Removed color picker UI; default blue
- `frontend/src/components/Targets/TargetDetailsSheet.tsx` — Removed color picker UI; default blue
- `frontend/src/store/targetAddStore.ts` — Default `pendingColor` → `#3B82F6`
- `frontend/src/components/Map/GlobeViewport.tsx` — Preview default blue; planning-mode gray/blue/red tri-state; schedule-mode blue/red; fixed pre-existing `any` type warnings (`DataSource`, `Property` imports)
- `frontend/src/components/MissionPlanning.tsx` — Removed No Opportunities block; renamed header
- `frontend/src/components/MissionResultsPanel.tsx` — Full redesign: removed Opportunities section, removed collapsible wrapper, fixed header with coverage badge, click-to-filter target pills, beautified timeline, cleaned ~15 unused imports/state variables
- `frontend/src/components/OpportunityMetricsCard.tsx` — Target label green → blue
- `frontend/src/components/OrdersPanel.tsx` — Gulf sample targets all brand blue; `OrderTargetRow` icon always blue; `InlineTargetAdd` default blue; file upload default blue
- `frontend/src/components/__tests__/defaultPriority.test.ts` — Test sample color updated

### Backend

- `backend/czml_generator.py` — Default target color `#EF4444` → `#3B82F6`

## Build Verification

| Check | Status |
|-------|--------|
| `tsc --noEmit` | ✅ Pass (exit 0) |
| `eslint` (all edited files) | ✅ Pass (exit 0) |
| `vite build` | ✅ Pass (exit 0, ~10s) |

## Manual Verification Steps

1. **Load Gulf sample targets** → confirm all dots in left pane and map pins are brand blue (no mixed colors)
2. **Feasibility Results panel** → confirm fixed "Timeline" header (no expand/collapse), coverage badge visible
3. **Click target pills** → confirm click-to-filter: first click = exclusive, second target = additive, deselect all = show all
4. **Planning map (no scheduler run)** → confirm all targets are gray
5. **Planning map (after scheduling)** → confirm blue for scheduled targets, red for unscheduled
6. **Confirm no green target coloring** exists anywhere in the app
7. **Target input forms** have no color picker (TargetConfirmPanel, TargetDetailsSheet, TargetInput)

## Constraints Honored

- Did NOT change opportunity bar colors (already brand-blue aligned in UI-020)
- Did NOT change hover/tooltip content (already updated in UI-021)
- Did NOT change schedule logic, apply behavior, or conflict handling
- Did NOT introduce target shape changes (separate design task)
