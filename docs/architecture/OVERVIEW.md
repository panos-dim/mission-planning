# System Architecture Overview

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        COSMOS42 Frontend                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   React     │  │   Zustand   │  │        Cesium           │  │
│  │ Components  │──│    Store    │──│   3D Visualization      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│         │                │                      │                │
│         └────────────────┼──────────────────────┘                │
│                          │                                       │
│                   TanStack Query                                 │
│                   (Data Fetching)                                │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/REST
┌──────────────────────────┴──────────────────────────────────────┐
│                        FastAPI Backend                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Routers   │  │   Mission   │  │        CZML             │  │
│  │  (API)      │──│   Planner   │──│      Generator          │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│         │                │                      │                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Config     │  │  Scheduler  │  │    Orbit Predictor      │  │
│  │  Manager    │  │  Algorithms │  │    (SGP4/SDP4)          │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                        Data Layer                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   TLE       │  │   Ground    │  │      Mission            │  │
│  │   Files     │  │   Stations  │  │      Settings           │  │
│  │   (.tle)    │  │   (.yaml)   │  │      (.yaml)            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Component Breakdown

### Frontend Layer

| Component | Location | Purpose |
|-----------|----------|---------|
| App Shell | `App.tsx` | Layout, routing, global providers |
| Sidebars | `LeftSidebar.tsx`, `RightSidebar.tsx` | Navigation, controls, results |
| Map View | `MultiViewContainer.tsx` | 2D/3D Cesium visualization |
| UI Library | `components/ui/` | Reusable UI primitives |
| Feature Components | `components/features/` | Domain-specific components |
| State Store | `store/appStore.ts` | Unified Zustand store |
| API Layer | `api/` | HTTP client with retry logic |

### Backend Layer

| Component | Location | Purpose |
|-----------|----------|---------|
| Main App | `main.py` | FastAPI app, core endpoints |
| TLE Router | `routers/tle.py` | TLE validation, satellite data |
| Config Router | `routers/config.py` | Ground stations, satellites, settings |
| Planning Router | `routers/planning.py` | Scheduling algorithms |
| Mission Planner | `mission_planner/` | Core orbit/visibility logic |
| CZML Generator | `czml_generator.py` | Cesium visualization data |

### Data Layer

| File | Format | Purpose |
|------|--------|---------|
| `data/active_satellites.tle` | TLE | Satellite orbital elements |
| `config/ground_stations.yaml` | YAML | Ground station definitions |
| `config/satellites.yaml` | YAML | Managed satellite configs |
| `config/mission_settings.yaml` | YAML | Default mission parameters |

---

## Data Flow

### Mission Analysis Flow

```
1. User Input (Frontend)
   └── Target coordinates, satellite selection, time window
        │
2. API Request
   └── POST /api/mission/analyze
        │
3. Mission Planner (Backend)
   ├── Load TLE → Create SatelliteOrbit
   ├── Create GroundTarget objects
   └── Compute visibility passes
        │
4. CZML Generation
   └── Convert passes to time-dynamic CZML entities
        │
5. Response
   └── { mission_data, czml, opportunities }
        │
6. Visualization (Frontend)
   ├── Load CZML into Cesium viewer
   ├── Update mission state
   └── Display results in sidebar
```

### Planning Flow

```
1. Load Opportunities
   └── GET /api/planning/opportunities
        │
2. Configure Parameters
   └── Weights, quality model, agility constraints
        │
3. Run Algorithms
   └── POST /api/planning/schedule
        │
4. Compare Results
   └── Display metrics, coverage, schedule table
        │
5. Accept Plan
   └── Promote to orders for execution
```

---

## Key Design Decisions

### 1. Single Zustand Store
All frontend state consolidated into `appStore.ts` with slices for:
- Mission data and CZML
- Visualization settings (layers, view mode)
- UI state (sidebars, panels)
- Planning state (opportunities, results)

### 2. CZML for Visualization
Time-dynamic visualization using CZML format:
- Satellite position and path
- Target markers with coverage circles
- Sensor pointing cone
- Day/night lighting

### 3. Modular Backend Routers
API organized by domain:
- `/api/tle/*` - TLE operations
- `/api/mission/*` - Mission analysis
- `/api/planning/*` - Scheduling
- `/api/config/*` - Configuration

### 4. Physics-Based Algorithms
All calculations use validated orbital mechanics:
- SGP4/SDP4 propagation via orbit-predictor
- Spherical geometry for visibility
- Sun position for optical constraints

---

## Performance Considerations

### Frontend
- **Lazy Loading**: Split view renders secondary viewport only when visible
- **Memoization**: React.memo for pure child components
- **CZML Caching**: Single load shared between viewports
- **Debounced Updates**: Timeline scrubbing batched

### Backend
- **Parallel Processing**: Multi-target analysis uses thread pool
- **Adaptive Stepping**: Variable time step based on orbital geometry
- **Caching**: Satellite objects reused across analyses
- **Streaming**: Large responses chunked
