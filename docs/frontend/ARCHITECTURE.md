# Frontend Architecture

## Overview

The COSMOS42 frontend is a modern React application built with TypeScript, featuring a sophisticated satellite mission planning visualization powered by CesiumJS.

## Technology Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 18.2.0 | UI Framework |
| TypeScript | 5.2.0 | Type Safety |
| Vite | 7.2.6 | Build Tool |
| Zustand | 5.0.8 | State Management |
| TanStack Query | 5.x | Data Fetching |
| Cesium | 1.111.0 | 3D Globe Rendering |
| Resium | 1.17.0 | React-Cesium Bindings |
| Tailwind CSS | 3.3.0 | Styling |
| Zod | 3.x | Runtime Validation |

## Directory Structure

```plaintext
frontend/src/
├── api/                    # API layer
│   ├── client.ts          # HTTP client with retry/timeout
│   ├── config.ts          # API configuration
│   ├── configApi.ts       # Config endpoints
│   ├── errors.ts          # Custom error classes
│   ├── mission.ts         # Mission endpoints
│   ├── tle.ts             # TLE endpoints
│   ├── validate.ts        # Runtime validation
│   ├── schemas/           # Zod validation schemas
│   └── index.ts           # Barrel export
│
├── components/
│   ├── Map/               # Cesium map components
│   │   ├── GlobeViewport.tsx
│   │   ├── MultiViewContainer.tsx
│   │   └── hooks/         # Map-specific hooks
│   │       ├── useClockSync.ts
│   │       ├── useEntitySelection.ts
│   │       ├── useImageryFallback.ts
│   │       ├── useLayerVisibility.ts
│   │       ├── useSceneMode.ts
│   │       └── useCzmlShared.ts
│   ├── skeletons/         # Loading placeholders
│   └── lazy.ts            # Lazy-loaded components
│
├── constants/             # Centralized constants
│   ├── ui.ts             # UI constants
│   ├── cesium.ts         # Cesium constants
│   └── index.ts
│
├── context/
│   └── MissionContext.tsx # Mission data context
│
├── hooks/
│   └── queries/           # TanStack Query hooks
│       ├── useConfigQueries.ts
│       ├── useMissionQueries.ts
│       ├── useTLEQueries.ts
│       └── index.ts
│
├── lib/
│   └── queryClient.ts     # Query client configuration
│
├── store/                 # Zustand state management
│   ├── appStore.ts        # Unified store
│   ├── slices/            # Store slices
│   │   ├── missionSlice.ts
│   │   ├── visSlice.ts
│   │   ├── targetAddSlice.ts
│   │   ├── previewTargetsSlice.ts
│   │   └── slewVisSlice.ts
│   └── index.ts           # Barrel export
│
├── types/
│   └── index.ts           # TypeScript type definitions
│
└── utils/
    └── debug.ts           # Debug logging utility
```

## Key Architectural Patterns

### 1. API Layer

The API layer provides centralized HTTP communication with automatic retry, timeout handling, and runtime validation.

```typescript
// Usage
import { missionApi, tleApi, configApi } from '@/api'

const result = await missionApi.analyze(request)
```

**Features:**
- Automatic retry with exponential backoff
- Request timeout handling
- AbortController support for cancellation
- Zod schema validation of responses
- Centralized error handling

### 2. State Management

Uses Zustand with a slice pattern for modular state management.

```typescript
// Direct store access
const clockTime = useAppStore((state) => state.clockTime)

// Selector hooks (preferred)
const { isLoading, missionData } = useMissionState()
const { activeLayers, toggleLayer } = useLayerState()
```

**Slices:**
- `missionSlice` - Mission data, CZML, scene objects
- `visSlice` - View modes, clock, layers, camera
- `targetAddSlice` - Target add mode
- `previewTargetsSlice` - Preview targets
- `slewVisSlice` - Slew visualization

### 3. Data Fetching

TanStack Query provides intelligent caching and data synchronization.

```typescript
// Query hooks
const { data: sources } = useTLESources()
const { mutate: analyze, isLoading } = useMissionAnalysis()
```

**Features:**
- Automatic caching (5-minute stale time)
- Request deduplication
- Background refetching
- Optimistic updates
- DevTools integration

### 4. Component Hooks

Complex component logic is extracted into focused hooks:

| Hook | Purpose |
|------|---------|
| `useClockSync` | Synchronize clock between viewports |
| `useLayerVisibility` | Manage entity visibility |
| `useImageryFallback` | Handle Ion failures |
| `useSceneMode` | Manage 2D/3D transitions |
| `useEntitySelection` | Handle entity clicks |

## State Persistence

The following state is persisted to localStorage:
- Workspaces
- Sidebar widths
- Layer visibility preferences
- View mode preference

## Performance Optimizations

1. **Memoization** - useCallback for expensive functions
2. **Code Splitting** - Lazy loading for heavy components
3. **Query Caching** - 5-minute stale time reduces API calls
4. **AbortController** - Cancel in-flight requests on unmount
5. **Loading Skeletons** - Better perceived performance

## Error Handling

Errors are handled at multiple levels:

1. **API Layer** - Custom error classes (ApiError, NetworkError, TimeoutError)
2. **Validation** - Zod schema validation with warnings in dev
3. **Components** - ErrorBoundary components
4. **Debug Utility** - Configurable logging levels
