# State Management Documentation

## Overview

The application uses Zustand with a slice pattern for modular, type-safe state management. All state is centralized in a unified store (`useAppStore`) with specialized selector hooks for common access patterns.

## Architecture

```plaintext
src/store/
├── appStore.ts           # Unified store combining all slices
├── slices/
│   ├── missionSlice.ts   # Mission data, CZML, scene objects
│   ├── visSlice.ts       # View modes, clock, layers, camera
│   ├── targetAddSlice.ts # Target add mode
│   ├── previewTargetsSlice.ts
│   └── slewVisSlice.ts   # Slew visualization
└── index.ts              # Barrel export
```

## Usage

### Direct Store Access

```typescript
import { useAppStore } from '@/store'

// Single value
const clockTime = useAppStore((state) => state.clockTime)

// Multiple values (creates new object each render - use sparingly)
const { isLoading, error } = useAppStore((state) => ({
  isLoading: state.isLoading,
  error: state.error,
}))

// Action
const setClockTime = useAppStore((state) => state.setClockTime)
```

### Selector Hooks (Recommended)

Selector hooks provide optimized subscriptions for common patterns:

```typescript
import { 
  useMissionState,
  useLayerState,
  useClockState,
  useViewModeState,
  useTargetAddState,
} from '@/store'

// Mission data
const { isLoading, missionData, czmlData, error } = useMissionState()

// Layer visibility
const { activeLayers, toggleLayer, setLayerVisibility } = useLayerState()

// Clock synchronization
const { clockTime, setClockTime, setClockState } = useClockState()

// View modes
const { viewMode, setViewMode, sceneModePrimary } = useViewModeState()

// Target add mode
const { isAddMode, enableAddMode, disableAddMode } = useTargetAddState()
```

## Store Slices

### Mission Slice

Manages mission analysis data and scene objects.

**State:**

| Field | Type | Description |
|-------|------|-------------|
| `isLoading` | `boolean` | Loading state |
| `missionData` | `MissionData \| null` | Current mission data |
| `czmlData` | `CZMLPacket[]` | CZML visualization data |
| `error` | `string \| null` | Error message |
| `validationResult` | `ValidationResponse \| null` | TLE validation result |
| `sceneObjects` | `SceneObject[]` | Scene objects |
| `selectedObjectId` | `string \| null` | Selected object ID |
| `workspaces` | `Workspace[]` | Saved workspaces |

**Actions:**

```typescript
setLoading(loading: boolean)
setMissionData(data: { missionData, czmlData })
setError(error: string | null)
clearMission()
addSceneObject(object: SceneObject)
updateSceneObject(id: string, updates: Partial<SceneObject>)
removeSceneObject(id: string)
setSelectedObject(id: string | null)
saveWorkspace(workspace: Workspace)
loadWorkspace(workspace: Workspace)
deleteWorkspace(id: string)
```

### Visualization Slice

Manages view configuration, clock, and layers.

**State:**

| Field | Type | Description |
|-------|------|-------------|
| `sceneModePrimary` | `'2D' \| '3D'` | Primary viewport mode |
| `sceneModeSecondary` | `'2D' \| '3D'` | Secondary viewport mode |
| `viewMode` | `'single' \| 'split'` | View layout |
| `leftSidebarOpen` | `boolean` | Left sidebar visibility |
| `rightSidebarOpen` | `boolean` | Right sidebar visibility |
| `leftSidebarWidth` | `number` | Left sidebar width (432-864px) |
| `rightSidebarWidth` | `number` | Right sidebar width |
| `clockTime` | `JulianDate \| null` | Current clock time |
| `clockShouldAnimate` | `boolean` | Animation state |
| `clockMultiplier` | `number` | Playback speed |
| `activeLayers` | `LayerVisibility` | Layer visibility flags |

**Layer Visibility:**

```typescript
interface LayerVisibility {
  orbitLine: boolean       // Satellite path
  groundTrack: boolean     // Ground track
  targets: boolean         // Target markers
  footprints: boolean      // Coverage footprints
  labels: boolean          // Entity labels
  coverageAreas: boolean   // Coverage circles
  pointingCone: boolean    // Sensor cone
  dayNightLighting: boolean // Day/night terminator
}
```

**Actions:**

```typescript
setSceneModePrimary(mode: SceneMode)
setSceneModeSecondary(mode: SceneMode)
setViewMode(mode: ViewMode)
setClockTime(time: JulianDate | null)
setClockState(time, shouldAnimate, multiplier)
toggleLayer(layer: keyof LayerVisibility)
setLayerVisibility(layer, visible)
```

### Target Add Slice

Manages the target add mode for map click interactions.

**State:**

| Field | Type | Description |
|-------|------|-------------|
| `isAddMode` | `boolean` | Add mode active |
| `pendingTarget` | `PendingTarget \| null` | Target being added |
| `isDetailsSheetOpen` | `boolean` | Details sheet visible |

**Actions:**

```typescript
enableAddMode()
disableAddMode()
toggleAddMode()
setPendingTarget(target: PendingTarget | null)
openDetailsSheet()
closeDetailsSheet()
clearPendingTarget()
```

### Preview Targets Slice

Manages preview targets displayed before mission analysis.

**State:**

| Field | Type | Description |
|-------|------|-------------|
| `previewTargets` | `TargetData[]` | Preview targets |
| `hidePreview` | `boolean` | Hide preview flag |

**Actions:**

```typescript
setPreviewTargets(targets: TargetData[])
clearPreviewTargets()
setHidePreview(hide: boolean)
```

### Slew Visualization Slice

Manages slew visualization settings.

**State:**

| Field | Type | Description |
|-------|------|-------------|
| `slewEnabled` | `boolean` | Slew visualization enabled |
| `activeSchedule` | `AlgorithmResult \| null` | Active schedule |
| `showFootprints` | `boolean` | Show footprints |
| `showSlewArcs` | `boolean` | Show slew arcs |
| `colorBy` | `'quality' \| 'density' \| 'none'` | Color mode |
| `filterMode` | `'accepted' \| 'rejected_feasible' \| 'all'` | Filter mode |

**Actions:**

```typescript
setSlewEnabled(enabled: boolean)
setActiveSchedule(schedule: AlgorithmResult | null)
setShowFootprints(show: boolean)
setShowSlewArcs(show: boolean)
setColorBy(mode: ColorByMode)
setFilterMode(mode: FilterMode)
resetSlewVis()
```

## State Persistence

The following state is automatically persisted to localStorage:

```typescript
{
  workspaces: state.workspaces,
  leftSidebarWidth: state.leftSidebarWidth,
  rightSidebarWidth: state.rightSidebarWidth,
  activeLayers: state.activeLayers,
  viewMode: state.viewMode,
}
```

## DevTools Integration

Redux DevTools integration is enabled in development:

1. Install Redux DevTools browser extension
2. Open DevTools and select "Redux" tab
3. View state tree and action history

## Best Practices

### 1. Use Selector Hooks

```typescript
// ✅ Recommended - optimized subscription
const { isLoading, error } = useMissionState()

// ❌ Avoid - creates new object each render
const state = useAppStore((s) => ({ isLoading: s.isLoading, error: s.error }))
```

### 2. Select Minimal State

```typescript
// ✅ Good - only subscribes to clockTime
const clockTime = useAppStore((s) => s.clockTime)

// ❌ Bad - subscribes to entire store
const state = useAppStore()
```

### 3. Memoize Complex Selectors

```typescript
import { useCallback } from 'react'

// For derived state
const filteredObjects = useAppStore(
  useCallback((state) => 
    state.sceneObjects.filter(obj => obj.visible), [])
)
```

### 4. Colocate Related Actions

```typescript
// ✅ Good - get related state and actions together
const { 
  activeLayers, 
  toggleLayer, 
  setLayerVisibility 
} = useLayerState()
```
