"""
Utility functions for the mission planner.

This module provides common utility functions used throughout
the mission planning tool.
"""

import contextvars
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, Optional, Union

import requests

logger = logging.getLogger(__name__)

# Earth mean radius in km (WGS-84 volumetric mean)
EARTH_RADIUS_KM = 6371.0
DEFAULT_NOISY_LOGGERS = {
    "httpcore": "WARNING",
    "urllib3": "WARNING",
    "uvicorn.access": "WARNING",
}
_EMPTY_LOG_CONTEXT: Dict[str, str] = {}
_LOG_CONTEXT: contextvars.ContextVar[Dict[str, str]] = contextvars.ContextVar(
    "mission_planner_log_context",
    default=_EMPTY_LOG_CONTEXT,
)
_LOG_CONTEXT_ALIASES = {
    "request_id": "req",
    "workspace_id": "ws",
    "run_id": "run",
    "plan_id": "plan",
    "order_id": "order",
    "snapshot_id": "snap",
}


def get_log_context() -> Dict[str, str]:
    """Get the current structured log context."""
    return dict(_LOG_CONTEXT.get())


def _normalize_log_context(context: Mapping[str, object]) -> Dict[str, str]:
    """Normalize context values into compact strings."""
    normalized: Dict[str, str] = {}
    for key, value in context.items():
        if value is None:
            continue
        rendered = str(value).strip()
        if rendered:
            normalized[key] = rendered
    return normalized


def set_log_context(**context: object) -> contextvars.Token[Dict[str, str]]:
    """Replace the current log context and return a reset token."""
    return _LOG_CONTEXT.set(_normalize_log_context(context))


def update_log_context(**context: object) -> None:
    """Merge values into the current log context."""
    merged = _LOG_CONTEXT.get()
    if merged is _EMPTY_LOG_CONTEXT:
        merged = {}
        _LOG_CONTEXT.set(merged)
    for key, value in context.items():
        if value is None:
            merged.pop(key, None)
            continue
        rendered = str(value).strip()
        if rendered:
            merged[key] = rendered
        else:
            merged.pop(key, None)


def reset_log_context(token: contextvars.Token[Dict[str, str]]) -> None:
    """Reset the current log context using a token from set_log_context()."""
    _LOG_CONTEXT.reset(token)


def clear_log_context() -> None:
    """Clear the current log context."""
    current = _LOG_CONTEXT.get()
    if current is _EMPTY_LOG_CONTEXT:
        return
    current.clear()


def _format_log_context(context: Mapping[str, str]) -> str:
    """Render structured log context as a compact suffix."""
    if not context:
        return ""

    ordered_keys = list(_LOG_CONTEXT_ALIASES)
    ordered_keys.extend(sorted(key for key in context if key not in _LOG_CONTEXT_ALIASES))

    parts = []
    for key in ordered_keys:
        value = context.get(key)
        if not value:
            continue
        label = _LOG_CONTEXT_ALIASES.get(key, key)
        parts.append(f"{label}={value}")

    return f" [{' '.join(parts)}]" if parts else ""


class _LogContextFilter(logging.Filter):
    """Attach request-scoped context to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        context = get_log_context()
        record.request_id = context.get("request_id", "")
        record.log_context = _format_log_context(context)
        return True


class _RepeatedMessageFilter(logging.Filter):
    """Suppress identical bursts of log messages to reduce noise."""

    def __init__(self, window_seconds: float = 5.0, burst_limit: int = 3) -> None:
        super().__init__()
        self.window_seconds = max(float(window_seconds), 0.0)
        self.burst_limit = max(int(burst_limit), 1)
        self._state: Dict[tuple[str, int, str], Dict[str, float]] = {}

    def filter(self, record: logging.LogRecord) -> bool:
        if self.window_seconds <= 0:
            return True

        message = record.getMessage()
        key = (
            record.name,
            record.levelno,
            message,
            _format_log_context(get_log_context()),
        )
        now = time.monotonic()
        state = self._state.get(key)

        if state is None or now - state["first_seen"] > self.window_seconds:
            suppressed = int(state["suppressed"]) if state is not None else 0
            self._state[key] = {
                "first_seen": now,
                "allowed": 1,
                "suppressed": 0,
            }
            if len(self._state) > 512:
                self._prune(now)
            if suppressed:
                record.msg = "%s [suppressed %d similar messages in %.0fs]"
                record.args = (message, suppressed, self.window_seconds)
            return True

        if state["allowed"] < self.burst_limit:
            state["allowed"] += 1
            return True

        state["suppressed"] += 1
        return False

    def _prune(self, now: float) -> None:
        stale_after = max(self.window_seconds * 5, 30.0)
        self._state = {
            key: value
            for key, value in self._state.items()
            if now - value["first_seen"] <= stale_after
        }


def _coerce_log_level(level: str) -> int:
    """Return a logging level, defaulting invalid values to INFO."""
    return getattr(logging, str(level).upper(), logging.INFO)


def _get_env_float(name: str, default: float) -> float:
    """Read a float environment variable with a safe fallback."""
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _get_env_int(name: str, default: int) -> int:
    """Read an int environment variable with a safe fallback."""
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _build_log_formatter(format_style: str) -> logging.Formatter:
    """Create a compact or verbose formatter."""
    style = format_style.strip().lower()
    if style == "verbose":
        return logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s%(log_context)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    return logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s%(log_context)s",
        datefmt="%H:%M:%S",
    )


def _parse_logger_level_overrides(raw: Optional[str]) -> Dict[str, int]:
    """Parse module-level logger overrides from env."""
    overrides: Dict[str, int] = {}
    if not raw:
        return overrides

    for entry in raw.replace(";", ",").split(","):
        name, separator, level = entry.partition("=")
        if not separator:
            continue
        logger_name = name.strip()
        level_name = level.strip()
        if not logger_name or not level_name:
            continue
        overrides[logger_name] = _coerce_log_level(level_name)

    return overrides


def ground_arc_distance_km(alt_km: float, angle_deg: float) -> float:
    """Compute ground arc distance from sub-satellite point for a given off-nadir angle.

    Uses spherical-Earth geometry (law of sines) instead of the flat-Earth
    approximation ``h * tan(θ)`` which underestimates at large angles
    (≈5 % error at 45°).

    Geometry (triangle: Earth-center C, Satellite S, Ground-point G):
        |CS| = R + h,  |CG| = R,  angle at S = θ (off-nadir)
        By sine rule  →  sin(∠G) = (R+h)/R · sin(θ)
        Earth central angle  α = arcsin((R+h)/R · sin(θ)) − θ
        Ground arc distance  d = R · α

    Args:
        alt_km:   Satellite altitude above Earth surface in km.
        angle_deg: Off-nadir (or incidence) angle in degrees.

    Returns:
        Ground arc distance in **kilometres**.
    """
    import math

    R = EARTH_RADIUS_KM
    theta = math.radians(angle_deg)
    sin_gamma = (R + alt_km) / R * math.sin(theta)

    if sin_gamma >= 1.0:
        # Angle exceeds horizon – return maximum visible arc
        alpha = math.acos(R / (R + alt_km))
        return R * alpha

    alpha = math.asin(sin_gamma) - theta  # Earth central angle (radians)
    return R * alpha


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Set up logging configuration.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path

    Environment Variables:
        MISSION_PLANNER_LOG_LEVEL: Override log level (DEBUG, INFO, WARNING, ERROR)
        MISSION_PLANNER_LOG_FILE: Optional file path override
        MISSION_PLANNER_LOG_FORMAT: "compact" (default) or "verbose"
        MISSION_PLANNER_LOG_DEDUP_WINDOW_SECONDS: Deduplicate identical bursts
        MISSION_PLANNER_LOG_BURST_LIMIT: Number of identical messages to allow
        MISSION_PLANNER_LOG_LEVELS: Comma-separated "logger=LEVEL" overrides
    """
    # Allow environment variable to override
    env_level = os.environ.get("MISSION_PLANNER_LOG_LEVEL")
    if env_level:
        level = env_level
    env_log_file = os.environ.get("MISSION_PLANNER_LOG_FILE")
    if env_log_file and not log_file:
        log_file = env_log_file

    log_level = _coerce_log_level(level)
    format_style = os.environ.get("MISSION_PLANNER_LOG_FORMAT", "compact")
    dedup_window = _get_env_float("MISSION_PLANNER_LOG_DEDUP_WINDOW_SECONDS", 5.0)
    burst_limit = _get_env_int("MISSION_PLANNER_LOG_BURST_LIMIT", 3)
    formatter = _build_log_formatter(format_style)

    logger_overrides = {
        name: _coerce_log_level(value)
        for name, value in DEFAULT_NOISY_LOGGERS.items()
    }
    logger_overrides.update(
        _parse_logger_level_overrides(os.environ.get("MISSION_PLANNER_LOG_LEVELS"))
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    def _attach_handler(handler: logging.Handler) -> None:
        handler.setFormatter(formatter)
        handler.addFilter(_LogContextFilter())
        handler.addFilter(
            _RepeatedMessageFilter(
                window_seconds=dedup_window,
                burst_limit=burst_limit,
            )
        )
        root_logger.addHandler(handler)

    # Add console handler
    _attach_handler(logging.StreamHandler())

    # Add file handler if specified
    if log_file:
        _attach_handler(logging.FileHandler(log_file))

    for logger_name, logger_level in logger_overrides.items():
        logging.getLogger(logger_name).setLevel(logger_level)

    logger.info(
        "Logging configured: level=%s format=%s dedup_window=%.1fs burst_limit=%d",
        logging.getLevelName(log_level),
        format_style,
        dedup_window,
        burst_limit,
    )


def parse_datetime(date_string: str) -> datetime:
    """
    Parse datetime string in various formats.

    Args:
        date_string: Date string to parse

    Returns:
        Parsed datetime object (UTC)

    Raises:
        ValueError: If date string cannot be parsed
    """
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_string, fmt)
            # Ensure UTC timezone
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            continue

    raise ValueError(f"Could not parse datetime string: {date_string}")


def download_tle_file(url: str, output_file: Union[str, Path]) -> bool:
    """
    Download TLE file from URL.

    Args:
        url: URL to download TLE data from
        output_file: Local file path to save TLE data

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Downloading TLE data from {url}")

        response = requests.get(url, timeout=30)
        response.raise_for_status()

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(response.text)

        logger.info(f"TLE data saved to {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error downloading TLE file: {e}")
        return False


def get_common_tle_sources() -> dict:
    """
    Get dictionary of common TLE data sources.

    Returns:
        Dictionary mapping source names to URLs
    """
    tle_sources = {
        "celestrak_active": "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle",
        "celestrak_stations": "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle",
        "celestrak_visual": "https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=tle",
        "celestrak_weather": "https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle",
        "celestrak_noaa": "https://celestrak.org/NORAD/elements/gp.php?GROUP=noaa&FORMAT=tle",
        "celestrak_goes": "https://celestrak.org/NORAD/elements/gp.php?GROUP=goes&FORMAT=tle",
        "celestrak_resource": "https://celestrak.org/NORAD/elements/gp.php?GROUP=resource&FORMAT=tle",
        "celestrak_cubesat": "https://celestrak.org/NORAD/elements/gp.php?GROUP=cubesat&FORMAT=tle",
        "celestrak_other": "https://celestrak.org/NORAD/elements/gp.php?GROUP=other-comm&FORMAT=tle",
    }
    return tle_sources


def validate_coordinates(latitude: float, longitude: float) -> bool:
    """
    Validate latitude and longitude coordinates.

    Args:
        latitude: Latitude in degrees
        longitude: Longitude in degrees

    Returns:
        True if coordinates are valid
    """
    return (-90 <= latitude <= 90) and (-180 <= longitude <= 180)


def degrees_to_dms(degrees: float) -> tuple:
    """
    Convert decimal degrees to degrees, minutes, seconds.

    Args:
        degrees: Decimal degrees

    Returns:
        Tuple of (degrees, minutes, seconds)
    """
    abs_degrees = abs(degrees)
    d = int(abs_degrees)
    m = int((abs_degrees - d) * 60)
    s = ((abs_degrees - d) * 60 - m) * 60

    return (d, m, s)


def format_coordinates(
    latitude: float, longitude: float, format: str = "decimal"
) -> str:
    """
    Format coordinates for display.

    Args:
        latitude: Latitude in degrees
        longitude: Longitude in degrees
        format: Format type ("decimal" or "dms")

    Returns:
        Formatted coordinate string
    """
    if format == "decimal":
        return f"{latitude:.6f}°, {longitude:.6f}°"
    elif format == "dms":
        lat_d, lat_m, lat_s = degrees_to_dms(latitude)
        lon_d, lon_m, lon_s = degrees_to_dms(longitude)

        lat_dir = "N" if latitude >= 0 else "S"
        lon_dir = "E" if longitude >= 0 else "W"

        return (
            f"{lat_d}°{lat_m}'{lat_s:.1f}\"{lat_dir}, "
            f"{lon_d}°{lon_m}'{lon_s:.1f}\"{lon_dir}"
        )
    else:
        raise ValueError(f"Unknown format: {format}")


def calculate_ground_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate great circle distance between two points on Earth.

    Args:
        lat1, lon1: First point coordinates (degrees)
        lat2, lon2: Second point coordinates (degrees)

    Returns:
        Distance in kilometers
    """
    import math

    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    # Earth's radius in km
    earth_radius = 6371.0
    return earth_radius * c


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def create_sample_tle_file(output_file: Union[str, Path]) -> None:
    """
    Create a sample TLE file with common satellites.

    Args:
        output_file: Path to create sample TLE file
    """
    sample_tle_data = """ISS (ZARYA)
1 25544U 98067A   24001.00000000  .00002182  00000-0  40864-4 0  9990
2 25544  51.6461 339.7939 0001220  92.8340 267.3124 15.49309239426382
NOAA 18
1 28654U 05018A   24001.00000000  .00000012  00000-0  28110-4 0  9997
2 28654  99.0581 161.3857 0013414  73.9446 286.3932 14.12501637967188
TERRA
1 25994U 99068A   24001.00000000  .00000023  00000-0  42979-4 0  9991
2 25994  98.2022  10.3559 0001378  83.7123 276.4313 14.57107527260649
AQUA
1 27424U 02022A   24001.00000000  .00000024  00000-0  43856-4 0  9996
2 27424  98.2123  70.8559 0002378  93.7123 266.4313 14.57207527160649
LANDSAT 8
1 39084U 13008A   24001.00000000  .00000012  00000-0  28110-4 0  9993
2 39084  98.2062 348.0319 0001378  83.7123 276.4313 14.57107527560649"""

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        f.write(sample_tle_data)

    logger.info(f"Created sample TLE file: {output_path}")


def get_current_utc() -> datetime:
    """
    Get current UTC datetime.

    Returns:
        Current UTC datetime (timezone-aware, tzinfo=timezone.utc)
    """
    return datetime.now(timezone.utc)


def ensure_directory_exists(directory: Union[str, Path]) -> Path:
    """
    Ensure directory exists, create if it doesn't.

    Args:
        directory: Directory path

    Returns:
        Path object for the directory
    """
    dir_path = Path(directory)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path
