# Changelog

All notable changes to the Mission Planning Tool.

## [Unreleased]

### Added

- Documentation reorganization with clear folder structure

---

## [2025.12] - December 2025

### Added

- **Live Slew Visualization**: Animated visualization of satellite slew maneuvers
- **Map Click Targets**: Click-to-add targets on Cesium globe
- **2D/3D View Modes**: Switchable visualization modes with split view
- **Resizable Sidebars**: Draggable resize handles for left/right panels
- **Celestrak Integration**: Real-time satellite catalog search

### Changed

- Frontend refactored to use Zustand for state management
- API layer consolidated with TanStack Query
- Mission Planning component split into focused sub-components

### Fixed

- Best-Fit algorithm geometry optimization
- Signed roll angle calculations
- Timeline synchronization with CZML data
- Coverage circle altitude calculations

---

## [2025.11] - November 2025

### Added

- **Roll+Pitch Algorithm**: 2D spacecraft slew scheduling
- **Forward/Backward Looking**: Pitch-based imaging opportunities
- **Quality Scoring Models**: Monotonic, band, and custom quality models
- **Audit System**: Algorithm behavior logging and analysis

### Changed

- Scheduler refactored for multi-axis slew support
- Opportunity creation expanded to early/max/late per pass

### Fixed

- Incidence angle calculations at imaging time
- Delta roll computation from previous attitude

---

## [2025.10] - October 2025

### Added

- **Adaptive Time-Stepping**: 20-30x faster visibility calculations
- **HPC Mode**: High-performance computing optimizations
- **Parallel Processing**: Multi-target visibility computation

### Changed

- Visibility calculator optimized with event-function abstraction
- Benchmark suite expanded for performance validation

---

## [2025.09] - September 2025

### Added

- **Sunlight Constraint**: Optical imaging daylight filtering
- **Day/Night Visualization**: Cesium lighting for optical missions
- **Pointing Cone Visualization**: Sensor FOV display on globe

### Fixed

- Elevation calculation coordinate system
- Coverage circle formula corrections

---

## [2025.08] - August 2025

### Added

- **STK Validation**: Ground truth comparison with AGI STK
- **Communication Pass Detection**: 10° elevation mask filtering

### Validated

- 100% pass count accuracy vs STK
- Timing accuracy within 7.2 seconds average

---

## Format

This changelog follows [Keep a Changelog](https://keepachangelog.com/) principles.

Categories:
- **Added**: New features
- **Changed**: Changes to existing functionality
- **Deprecated**: Features to be removed
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security improvements
