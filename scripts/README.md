# Scripts

Development and utility scripts for the Mission Planning Tool.

## Directory Structure

```text
scripts/
├── benchmarks/      # Performance benchmarks
├── tests/           # Test and validation scripts
├── utilities/       # Helper utilities
├── demo/            # Demo scripts
└── validation/      # Validation scripts
```

## Quick Reference

### Run Development Servers

```bash
# Best option - uses run_dev.sh
make dev

# Or directly
./run_dev.sh
```

### Run Benchmarks

```bash
# Adaptive time-stepping benchmark
.venv/bin/python scripts/benchmarks/benchmark_adaptive.py

# Heavy load benchmark
.venv/bin/python scripts/benchmarks/benchmark_heavy.py

# All benchmarks via make
make benchmark
```

### Run Validation

```bash
# Adaptive stepping validation
.venv/bin/python scripts/tests/validate_adaptive_stepping.py

# Via make
make validate
```

### Auditing

```bash
# Algorithm audit
.venv/bin/python scripts/audit_algorithms.py

# Planning audit
.venv/bin/python scripts/run_planning_audit.py

# Frontend audit
.venv/bin/python scripts/run_frontend_audit.py
```

## Script Categories

### benchmarks/

Performance testing scripts:

- `benchmark_adaptive.py` - Adaptive time-stepping performance
- `benchmark_heavy.py` - Heavy workload testing
- `benchmark_parallel.py` - Parallel processing benchmarks
- `benchmark_vectorized.py` - Vectorization benchmarks
- `benchmark_caching.py` - Cache performance
- `final_benchmark.py` - Comprehensive benchmark suite

### tests/

Test and validation scripts:

- `validate_adaptive_stepping.py` - Validate adaptive algorithm
- `test_adaptive_basic.py` - Basic adaptive tests
- `test_quality_planning.py` - Quality model tests
- `test_e2e_quality_planning.py` - End-to-end tests
- `test_multi_criteria.py` - Multi-criteria optimization tests
- `test_value_weights.py` - Value weighting tests

### utilities/

Helper utilities:

- `compare_schedules.py` - Compare two schedules
- `compare_counts.py` - Compare pass counts
- `compare_with_api.py` - Compare with API results
- `profile_mission.py` - Profile mission performance
- `verify_kml_mission.py` - Verify KML mission data
- `visualize_continuous_pitch.py` - Pitch visualization

### demo/

Demonstration scripts:

- `demo_full_pass_sampling.py` - Pass sampling demo
- `demo_incidence_angle_problem.py` - Incidence angle demo

## Running Scripts

Always use the virtual environment:

```bash
# Activate venv
source .venv/bin/activate

# Or run directly with venv Python
.venv/bin/python scripts/<script>.py
```

## Adding New Scripts

1. Place in appropriate subdirectory
2. Add shebang: `#!/usr/bin/env python3`
3. Include docstring with purpose
4. Use `if __name__ == "__main__":` guard
