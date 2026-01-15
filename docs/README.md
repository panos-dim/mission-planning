# COSMOS42 Mission Planning Documentation

> Satellite Mission Planning & Scheduling System

## Quick Navigation

| Section | Description |
|---------|-------------|
| [Getting Started](./getting-started/) | Installation and first mission |
| [Architecture](./architecture/) | System design overview |
| [Guides](./guides/) | Usage guides and configuration |
| [Frontend](./frontend/) | React/Cesium UI documentation |
| [Backend](./backend/) | FastAPI and mission planning logic |
| [Algorithms](./algorithms/) | Scheduling algorithms reference |
| [API Reference](./api/) | REST API documentation |
| [Features](./features/) | Feature-specific documentation |
| [Development](./development/) | Contributing and changelog |

---

## Documentation Structure

```text
docs/
├── README.md                        # This file
├── getting-started/
│   └── QUICK_START.md               # Installation & first mission
├── architecture/
│   └── OVERVIEW.md                  # System architecture
├── guides/
│   ├── USAGE.md                     # CLI and webapp usage
│   ├── MISSION_TYPES.md             # Imaging vs communication
│   └── CONFIGURATION.md             # Config files reference
├── frontend/
│   ├── ARCHITECTURE.md              # React component structure
│   ├── UI_COMPONENTS.md             # Shared UI library
│   ├── STATE_MANAGEMENT.md          # Zustand patterns
│   ├── API_LAYER.md                 # API client usage
│   └── BEST_PRACTICES_2025.md       # Modern React patterns
├── backend/
│   └── ROUTERS.md                   # API router organization
├── api/
│   └── API_REFERENCE.md             # Full API documentation
├── algorithms/
│   ├── OVERVIEW.md                  # Algorithm comparison
│   ├── ADAPTIVE_TIME_STEPPING.md    # Performance optimization
│   └── ROLL_PITCH.md                # 2D slew scheduling
├── features/
│   ├── LIVE_SLEW.md                 # Slew visualization
│   ├── VIEW_MODES.md                # 2D/3D view modes
│   └── MAP_CLICK_TARGETS.md         # Click-to-add targets
├── development/
│   ├── CONTRIBUTING.md              # Contribution guide
│   └── CHANGELOG.md                 # Version history
├── validation/
│   └── VERIFICATION_GUIDE.md        # Testing & validation
└── reference/
    └── TERMINOLOGY.md               # Domain terminology
```

---

## Technology Stack

### Frontend

| Tech | Version | Purpose |
|------|---------|---------|
| React | 18.2.0 | UI Framework |
| TypeScript | 5.2.0 | Type Safety |
| Vite | 7.2.6 | Build Tool |
| Zustand | 5.0.8 | State Management |
| TanStack Query | 5.x | Data Fetching |
| Cesium | 1.111.0 | 3D Globe |
| Tailwind CSS | 3.3.0 | Styling |

### Backend

| Tech | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Runtime |
| FastAPI | 0.104+ | REST API |
| Pydantic | 2.x | Validation |
| orbit-predictor | 1.15+ | Orbit Propagation |
| NumPy | Latest | Data Processing |

---

## Quick Start

```bash
# Clone and setup
git clone <repo>
cd mission-planning

# Backend
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Frontend
cd frontend
npm install

# Run development
./run_dev.sh
```

See [Getting Started Guide](./getting-started/QUICK_START.md) for details.

---

## Key Concepts

### Mission Types

- **Imaging**: Optical/SAR imaging with pointing constraints
- **Communication**: Ground station passes for data downlink

### Scheduling Algorithms

- **First-Fit**: Greedy chronological selection
- **Best-Fit**: Geometry optimization
- **Roll+Pitch**: 2D spacecraft slew capability

### Visualization

- **2D/3D Globe**: Cesium-based time animation
- **CZML**: Time-dynamic entity visualization
- **Layers**: Configurable orbit, targets, coverage

---

## Contributing

See [CONTRIBUTING.md](./development/CONTRIBUTING.md) for guidelines.

---

Last updated: December 2025
