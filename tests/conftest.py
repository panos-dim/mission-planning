"""
Pytest configuration and shared fixtures.

This file is automatically loaded by pytest and provides:
- Custom markers for test categorization
- Shared fixtures for common test setup
- Collection hooks to skip problematic modules
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# =============================================================================
# COLLECTION HOOKS - Prevent hanging on module-level code
# =============================================================================

def pytest_collection_modifyitems(config, items):
    """Mark tests that require server and skip them by default."""
    for item in items:
        # Auto-mark integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Auto-mark e2e tests as requiring server
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.requires_server)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "requires_server: marks tests that need backend server running"
    )
    config.addinivalue_line(
        "markers", "integration: marks integration tests"
    )


# =============================================================================
# FIXTURES - Common test setup
# =============================================================================

@pytest.fixture
def sample_tle_lines():
    """Sample TLE data for ICEYE-X44."""
    return (
        "1 62707U 25009DC  25306.22031033  .00004207  00000+0  39848-3 0  9995",
        "2 62707  97.7269  23.9854 0002193 135.9671 224.1724 14.94137357 66022"
    )


@pytest.fixture
def sample_satellite(sample_tle_lines, tmp_path):
    """Create a sample SatelliteOrbit for testing."""
    from mission_planner.orbit import SatelliteOrbit

    tle_file = tmp_path / "test.tle"
    tle_file.write_text(f"ICEYE-X44\n{sample_tle_lines[0]}\n{sample_tle_lines[1]}\n")

    return SatelliteOrbit.from_tle_file(str(tle_file))


@pytest.fixture
def sample_target():
    """Create a sample GroundTarget for testing."""
    from mission_planner.targets import GroundTarget

    return GroundTarget(
        name="Dubai",
        latitude=25.2048,
        longitude=55.2708,
        elevation_mask=10.0,
        priority=5
    )


@pytest.fixture
def sample_targets():
    """Create multiple sample targets for testing."""
    from mission_planner.targets import GroundTarget

    return [
        GroundTarget(name="Dubai", latitude=25.2048, longitude=55.2708, priority=5),
        GroundTarget(name="Abu_Dhabi", latitude=24.4539, longitude=54.3773, priority=4),
        GroundTarget(name="Doha", latitude=25.2854, longitude=51.5310, priority=3),
    ]


@pytest.fixture
def base_datetime():
    """Standard base datetime for tests."""
    return datetime(2025, 11, 8, 0, 0, 0)


@pytest.fixture
def time_range(base_datetime):
    """Standard 24-hour time range for tests."""
    return base_datetime, base_datetime + timedelta(hours=24)


@pytest.fixture
def scheduler_config():
    """Default scheduler configuration."""
    from mission_planner.scheduler import SchedulerConfig

    return SchedulerConfig(
        max_roll_deg=45.0,
        max_pitch_deg=30.0,
        roll_rate_dps=1.0,
        pitch_rate_dps=1.0,
        settle_time_sec=5.0,
    )


# =============================================================================
# SERVER FIXTURES - For integration tests
# =============================================================================

@pytest.fixture
def server_url():
    """Backend server URL."""
    return "http://localhost:8000"


@pytest.fixture
def skip_without_server(server_url):
    """Skip test if backend server is not running."""
    import socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 8000))
        sock.close()
        if result != 0:
            pytest.skip("Backend server not running on localhost:8000")
    except Exception:
        pytest.skip("Backend server not running on localhost:8000")


# =============================================================================
# ASYNC FIXTURES - For FastAPI testing
# =============================================================================

@pytest.fixture
def test_client():
    """FastAPI TestClient for API testing without running server."""
    try:
        from fastapi.testclient import TestClient
        from backend.main import app
        return TestClient(app)
    except ImportError:
        pytest.skip("FastAPI or backend not available")
