"""
Pytest configuration and shared fixtures.

This file is automatically loaded by pytest and provides:
- Custom markers for test categorization
- Shared fixtures for common test setup
- Collection hooks to skip problematic modules
"""

import socket
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Tuple

import pytest
from _pytest.config import Config
from _pytest.python import Function

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# =============================================================================
# COLLECTION HOOKS - Prevent hanging on module-level code
# =============================================================================


def _is_server_running(host: str = "localhost", port: int = 8000) -> bool:
    """Quick check if the backend server is reachable."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


# Cache the result once per session so we don't probe the port for every test
_server_available: bool | None = None


def pytest_collection_modifyitems(config: Config, items: List[Function]) -> None:
    """Mark tests that require server and skip them when server is not running."""
    global _server_available
    if _server_available is None:
        _server_available = _is_server_running()

    skip_server = pytest.mark.skip(
        reason="Backend server not running on localhost:8000"
    )

    for item in items:
        # Auto-mark integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Auto-mark e2e tests as requiring server
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.requires_server)

        # Skip requires_server tests when server is not available
        if not _server_available and item.get_closest_marker("requires_server"):
            item.add_marker(skip_server)


def pytest_configure(config: Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "requires_server: marks tests that need backend server running"
    )
    config.addinivalue_line("markers", "integration: marks integration tests")


# =============================================================================
# FIXTURES - Common test setup
# =============================================================================


@pytest.fixture
def sample_tle_lines() -> Tuple[str, str]:
    """Sample TLE data for ICEYE-X44."""
    return (
        "1 62707U 25009DC  25306.22031033  .00004207  00000+0  39848-3 0  9995",
        "2 62707  97.7269  23.9854 0002193 135.9671 224.1724 14.94137357 66022",
    )


@pytest.fixture
def sample_satellite(sample_tle_lines: Tuple[str, str], tmp_path: Path) -> Any:
    """Create a sample SatelliteOrbit for testing."""
    from mission_planner.orbit import SatelliteOrbit

    tle_file = tmp_path / "test.tle"
    tle_file.write_text(f"ICEYE-X44\n{sample_tle_lines[0]}\n{sample_tle_lines[1]}\n")

    return SatelliteOrbit.from_tle_file(str(tle_file), satellite_name="ICEYE-X44")


@pytest.fixture
def sample_target() -> Any:
    """Create a sample GroundTarget for testing."""
    from mission_planner.targets import GroundTarget

    return GroundTarget(
        name="Dubai",
        latitude=25.2048,
        longitude=55.2708,
        elevation_mask=10.0,
        priority=5,
    )


@pytest.fixture
def sample_targets() -> Any:
    """Create multiple sample targets for testing."""
    from mission_planner.targets import GroundTarget

    return [
        GroundTarget(name="Dubai", latitude=25.2048, longitude=55.2708, priority=5),
        GroundTarget(name="Abu_Dhabi", latitude=24.4539, longitude=54.3773, priority=4),
        GroundTarget(name="Doha", latitude=25.2854, longitude=51.5310, priority=3),
    ]


@pytest.fixture
def base_datetime() -> datetime:
    """Standard base datetime for tests."""
    return datetime(2025, 11, 8, 0, 0, 0)


@pytest.fixture
def time_range(base_datetime: datetime) -> Tuple[datetime, datetime]:
    """Standard 24-hour time range for tests."""
    return base_datetime, base_datetime + timedelta(hours=24)


@pytest.fixture
def scheduler_config() -> Any:
    """Default scheduler configuration."""
    from mission_planner.scheduler import SchedulerConfig

    return SchedulerConfig(
        max_spacecraft_roll_deg=45.0,
        max_spacecraft_pitch_deg=30.0,
        max_roll_rate_dps=1.0,
        max_pitch_rate_dps=1.0,
    )


# =============================================================================
# SERVER FIXTURES - For integration tests
# =============================================================================


@pytest.fixture
def server_url() -> str:
    """Backend server URL."""
    return "http://localhost:8000"


@pytest.fixture
def skip_without_server(server_url: str) -> None:
    """Skip test if backend server is not running."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("localhost", 8000))
        sock.close()
        if result != 0:
            pytest.skip("Backend server not running on localhost:8000")
    except Exception:
        pytest.skip("Backend server not running on localhost:8000")


# =============================================================================
# ASYNC FIXTURES - For FastAPI testing
# =============================================================================


@pytest.fixture
def test_client() -> Any:
    """FastAPI TestClient for API testing without running server."""
    try:
        from fastapi.testclient import TestClient

        from backend.main import app

        return TestClient(app)
    except ImportError:
        pytest.skip("FastAPI or backend not available")
