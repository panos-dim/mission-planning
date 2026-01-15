# View Modes & Split View

## Overview

The Mission Planning application now supports multiple visualization modes with synchronized state across viewports. The system defaults to 2D view for better initial performance and provides options for 3D view or split-screen 2D/3D visualization.

## Features

### View Modes

1. **2D View (Default)**
   - Flat map projection optimized for mission planning
   - Constrained zoom levels for optimal performance
   - Rotation disabled for stable viewing
   - All CZML entities rendered in 2D space
   - Better performance for overview analysis

2. **3D View**
   - Full globe visualization with free rotation
   - Camera tilt and zoom controls enabled
   - Perspective view of orbital mechanics
   - Better for detailed trajectory analysis

3. **Split View (2D | 3D)**
   - Side-by-side synchronized viewports
   - Left panel: Configurable (2D or 3D)
   - Right panel: Configurable (2D or 3D)  
   - Synchronized clock and timeline
   - Shared layer visibility states
   - Expand/collapse individual panels

### State Synchronization

When using Split View, the following elements are synchronized:
- **Clock Time**: Both viewports follow the same mission time
- **Timeline Window**: Zoom and range synchronized
- **Layer Visibility**: Toggle affects both viewports
- **Selected Objects**: Selection highlights in both views
- **Camera Focus**: Opportunity clicks center both views

### Performance Optimizations

- **Single CZML Load**: Data loaded once and shared between viewports
- **Cached Data**: CZML cached in memory to prevent reloading
- **Lazy Rendering**: Secondary viewport only renders when visible
- **Request Idle**: Non-critical updates use requestIdleCallback
- **Scene Mode Morphing**: Instant transitions between 2D/3D

## Usage

### Switching View Modes

1. Click the **View Mode** dropdown in the header
2. Select from:
   - **2D View**: Single 2D viewport
   - **3D View**: Single 3D viewport  
   - **Split 2D | 3D**: Side-by-side viewports

### Split View Configuration

When in Split View mode:
1. The dropdown shows configuration options
2. **Left Panel**: Toggle between 2D/3D
3. **Right Panel**: Toggle between 2D/3D
4. Use expand/collapse buttons on each viewport for focus

### Layer Controls

Layer visibility is synchronized across all viewports:
- Open the **Layers** panel in the right sidebar
- Toggle any layer on/off
- Changes apply to all active viewports immediately

### Timeline Controls

- Primary viewport shows timeline and animation widgets
- Secondary viewport follows primary's time
- Scrubbing timeline affects both viewports
- Play/pause controls both animations

## Technical Implementation

### Architecture

```
App.tsx
├── Header
│   └── ViewModeToggle (View mode selector)
├── MultiViewContainer
│   ├── GlobeViewport (Primary)
│   └── GlobeViewport (Secondary, if split)
└── RightSidebar (Layer controls)
```

### State Management

- **visStore** (Zustand): Centralized visualization state
  - Scene modes (2D/3D for each viewport)
  - View mode (single/split)
  - Clock synchronization
  - Layer visibility
  - Camera positions

### Data Flow

1. Mission data loaded via MissionContext
2. CZML cached in useCzmlShared hook
3. Shared data passed to viewports
4. Layer/clock changes propagate via visStore
5. Viewports react to store updates

## Performance Targets

- **Single View**: ≥ 45 FPS on typical laptop
- **Split View**: ≥ 30 FPS with both viewports active
- **Mode Switch**: < 100ms transition time
- **Memory**: No growth after 50+ mode toggles

## Troubleshooting

### Performance Issues

If experiencing low FPS in split view:
1. Use the expand button to focus one viewport
2. Disable unnecessary layers
3. Reduce timeline playback speed
4. Consider using 2D mode for overview

### Synchronization Issues

If viewports become desynchronized:
1. Switch to single view and back to split
2. Use "Reset Timeline" button
3. Refresh the page if issues persist

## API Compatibility

No changes to backend API or CZML schema. All view modes consume the same data format and use existing endpoints without modification.
