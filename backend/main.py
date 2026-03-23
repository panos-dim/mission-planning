"""
FastAPI backend for Satellite Mission Planning Web App.

Provides REST API endpoints for:
- TLE input and validation
- Orbit propagation
- Visibility calculations
- CZML generation for Cesium visualization
- Mission analysis and planning
"""

import hashlib
import json
import logging
import math
import os
import sys
import tempfile
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from io import BytesIO
from threading import Lock
from time import perf_counter
from typing import Any, Dict, List, Optional, Union

import requests
import yaml  # type: ignore[import-untyped]
from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel  # Only used for inline models if any remain

# Ensure mission_planner is importable (centralised path setup)
import backend._paths  # noqa: F401, E402

try:
    from mission_planner.audit import (
        PRESET_SCENARIOS,
        compare_roll_vs_pitch,
        generate_scenario,
        get_preset_scenario,
        run_algorithm_audit,
    )
    from mission_planner.orbit import SatelliteOrbit
    from mission_planner.parallel import cleanup_process_pool
    from mission_planner.planner import MissionPlanner
    from mission_planner.quality_scoring import (
        WEIGHT_PRESETS,
        MultiCriteriaWeights,
        QualityModel,
        compute_composite_value,
        compute_quality_score,
        compute_timing_score,
    )
    from mission_planner.scheduler import (
        AlgorithmType,
        MissionScheduler,
        Opportunity,
        SchedulerConfig,
    )
    from mission_planner.targets import GroundTarget, TargetManager
    from mission_planner.utils import (
        reset_log_context,
        set_log_context,
        download_tle_file,
        format_duration,
        get_common_tle_sources,
        setup_logging,
        update_log_context,
    )
    from mission_planner.visibility import VisibilityCalculator
except ImportError as e:
    # Use sys.stderr for critical import errors (before logger setup)
    sys.stderr.write(f"Error importing mission planner modules: {e}\n")
    sys.stderr.write(
        "Make sure you're running from the project root or have installed the package\n"
    )
    sys.exit(1)

# Import configuration manager
from backend.config_manager import ConfigManager, reload_config
from backend.coordinate_parser import CoordinateParser, FileParser, TargetValidator

# Import CZML generator, coordinate parser, routers, and satellite manager
from backend.czml_generator import CZMLGenerator, generate_mission_czml
from backend.mission_settings_manager import MissionSettingsManager
from backend.routers.batching import router as batching_router
from backend.routers.config_admin import router as config_admin_router
from backend.routers.dev import router as dev_router
from backend.routers.orders import router as orders_router
from backend.routers.schedule import router as schedule_router
from backend.routers.validation import router as validation_router
from backend.routers.workspaces import router as workspaces_router
from backend.satellite_manager import SatelliteManager
from backend.schedule_persistence import get_schedule_db
from backend.validation.mission_input_validator import (
    reload_validation_config,
    validate_mission_input,
)

# Initialize configuration managers
config_manager = ConfigManager()
satellite_manager = SatelliteManager()
mission_settings_manager = MissionSettingsManager()

# Setup logging early
setup_logging()
logger = logging.getLogger(__name__)
_QUIET_REQUEST_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/static")
_HEAVY_REQUEST_PREFIXES = (
    "/api/v1/mission/analyze",
    "/api/v1/planning",
    "/api/v1/schedule/plan",
    "/api/v1/schedule/commit",
    "/api/v1/schedule/repair",
    "/api/v1/workspaces/save-current",
)
_ROUTE_FAMILY_PREFIXES = (
    ("/api/v1/schedule", "schedule"),
    ("/api/v1/planning", "planning"),
    ("/api/v1/mission", "mission"),
    ("/api/v1/orders", "orders"),
    ("/api/v1/workspaces", "workspaces"),
    ("/api/v1/debug", "debug"),
    ("/api/v1/dev", "debug"),
    ("/api/v1/validation", "validation"),
    ("/api/v1/config", "config"),
    ("/api/v1/tle", "tle"),
)
_STATUS_CLASS_KEYS = ("2xx", "3xx", "4xx", "5xx", "other")


def _read_env_float(name: str, default: float) -> float:
    """Read a float environment variable with a safe fallback."""
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _get_request_latency_profile(path: str) -> str:
    """Classify requests so heavy endpoints get higher slow-request thresholds."""
    if path == "/" or path.startswith(_QUIET_REQUEST_PREFIXES):
        return "quiet"
    if path.startswith(_HEAVY_REQUEST_PREFIXES):
        return "heavy"
    return "default"


def _get_slow_request_threshold_ms(path: str) -> float:
    """Return the slow-request threshold for a given route."""
    default_ms = max(_read_env_float("MISSION_PLANNER_LOG_SLOW_REQUEST_MS", 750.0), 0.0)
    heavy_default_ms = max(default_ms * 3.0, 2500.0)
    heavy_ms = max(
        _read_env_float("MISSION_PLANNER_LOG_HEAVY_REQUEST_MS", heavy_default_ms),
        default_ms,
    )
    return heavy_ms if _get_request_latency_profile(path) == "heavy" else default_ms


def _get_latency_bucket(duration_ms: float) -> str:
    """Map request duration to a compact bucket label."""
    if duration_ms < 50:
        return "<50ms"
    if duration_ms < 200:
        return "50-200ms"
    if duration_ms < 1000:
        return "200ms-1s"
    if duration_ms < 5000:
        return "1-5s"
    return ">=5s"


def _format_request_duration(duration_ms: float) -> str:
    """Format durations compactly for access logs."""
    if duration_ms < 1000:
        return f"{duration_ms:.1f}ms"
    return format_duration(duration_ms / 1000.0)


def _get_route_summary_every() -> int:
    """Return how many requests to batch per latency summary."""
    try:
        return max(int(os.environ.get("MISSION_PLANNER_LOG_ROUTE_SUMMARY_EVERY", 10)), 0)
    except (TypeError, ValueError):
        return 10


def _get_route_history_limit() -> int:
    """Return how many emitted route summaries to retain in memory."""
    try:
        return max(int(os.environ.get("MISSION_PLANNER_LOG_ROUTE_HISTORY_LIMIT", 50)), 0)
    except (TypeError, ValueError):
        return 50


def _get_route_baseline_windows() -> int:
    """Return how many historical windows to use when computing baselines."""
    try:
        return max(
            int(os.environ.get("MISSION_PLANNER_LOG_ROUTE_BASELINE_WINDOWS", 5)),
            0,
        )
    except (TypeError, ValueError):
        return 5


def _get_route_hot_multiplier() -> float:
    """Return the relative increase required to flag a hot route."""
    try:
        return max(
            float(os.environ.get("MISSION_PLANNER_LOG_ROUTE_HOT_MULTIPLIER", 1.75)),
            1.0,
        )
    except (TypeError, ValueError):
        return 1.75


def _get_route_hot_min_delta_ms() -> float:
    """Return the minimum absolute latency jump required for hot-route warnings."""
    try:
        return max(
            float(os.environ.get("MISSION_PLANNER_LOG_ROUTE_HOT_MIN_DELTA_MS", 250.0)),
            0.0,
        )
    except (TypeError, ValueError):
        return 250.0


def _get_route_hot_min_windows() -> int:
    """Return the minimum baseline windows required before hot detection activates."""
    try:
        return max(
            int(os.environ.get("MISSION_PLANNER_LOG_ROUTE_HOT_MIN_WINDOWS", 2)),
            0,
        )
    except (TypeError, ValueError):
        return 2


def _get_recent_error_limit() -> int:
    """Return how many recent request errors to retain in memory."""
    try:
        return max(
            int(os.environ.get("MISSION_PLANNER_LOG_RECENT_ERROR_LIMIT", 50)),
            0,
        )
    except (TypeError, ValueError):
        return 50


def _get_request_route_label(request: Request) -> str:
    """Use the route template when available to avoid high-cardinality summaries."""
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    return route_path or request.url.path


def _get_route_family(path: str) -> str:
    """Map a route path to a stable product-area family."""
    if path == "/":
        return "root"
    for prefix, family in _ROUTE_FAMILY_PREFIXES:
        if path.startswith(prefix):
            return family
    return "other"


def _get_status_class(status_code: int) -> str:
    """Bucket an HTTP status code into its status class."""
    if 200 <= status_code < 300:
        return "2xx"
    if 300 <= status_code < 400:
        return "3xx"
    if 400 <= status_code < 500:
        return "4xx"
    if 500 <= status_code < 600:
        return "5xx"
    return "other"


def _empty_status_counts() -> Dict[str, int]:
    """Return a new zeroed status-class counter map."""
    return {key: 0 for key in _STATUS_CLASS_KEYS}


def _normalize_status_counts(status_counts: Optional[Dict[str, int]] = None) -> Dict[str, int]:
    """Normalize sparse status counts into a complete fixed-key mapping."""
    normalized = _empty_status_counts()
    if not status_counts:
        return normalized
    for key, value in status_counts.items():
        if key in normalized:
            normalized[key] = int(value)
    return normalized


def _merge_status_counts(target: Dict[str, int], source: Optional[Dict[str, int]]) -> None:
    """Add source counters into target in place."""
    for key, value in _normalize_status_counts(source).items():
        target[key] += int(value)


def _percentile_ms(samples_ms: List[float], percentile: float) -> float:
    """Compute a nearest-rank percentile for a non-empty list of durations."""
    if not samples_ms:
        return 0.0
    ordered = sorted(samples_ms)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[min(rank - 1, len(ordered) - 1)]


def _aggregate_entry_status_counts(entries: List[Dict[str, Any]]) -> Dict[str, int]:
    """Aggregate status-class counters across route or history entries."""
    totals = _empty_status_counts()
    for entry in entries:
        _merge_status_counts(totals, entry.get("status_counts"))
    return totals


def _summarize_route_families(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate route entries into family-level summaries."""
    families: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        family = str(entry.get("route_family") or "other")
        family_summary = families.setdefault(
            family,
            {
                "family": family,
                "route_count": 0,
                "request_count": 0,
                "total_ms": 0.0,
                "p95_ms": 0.0,
                "max_ms": 0.0,
                "slow_count": 0,
                "error_count": 0,
                "hot_count": 0,
                "status_counts": _empty_status_counts(),
            },
        )
        request_count = int(entry.get("count") or 0)
        avg_ms = float(entry.get("avg_ms") or 0.0)
        family_summary["route_count"] += 1
        family_summary["request_count"] += request_count
        family_summary["total_ms"] += avg_ms * request_count
        family_summary["p95_ms"] = max(
            float(family_summary["p95_ms"]),
            float(entry.get("p95_ms") or 0.0),
        )
        family_summary["max_ms"] = max(
            float(family_summary["max_ms"]),
            float(entry.get("max_ms") or 0.0),
        )
        family_summary["slow_count"] += int(entry.get("slow_count") or 0)
        family_summary["error_count"] += int(entry.get("error_count") or 0)
        family_summary["hot_count"] += 1 if entry.get("is_hot") else 0
        _merge_status_counts(
            family_summary["status_counts"],
            entry.get("status_counts"),
        )

    summarized: List[Dict[str, Any]] = []
    for family_summary in families.values():
        request_count = int(family_summary["request_count"])
        avg_ms = (
            float(family_summary["total_ms"]) / request_count if request_count > 0 else 0.0
        )
        summarized.append(
            {
                "family": family_summary["family"],
                "route_count": int(family_summary["route_count"]),
                "request_count": request_count,
                "avg_ms": avg_ms,
                "p95_ms": float(family_summary["p95_ms"]),
                "max_ms": float(family_summary["max_ms"]),
                "slow_count": int(family_summary["slow_count"]),
                "error_count": int(family_summary["error_count"]),
                "hot_count": int(family_summary["hot_count"]),
                "status_counts": dict(family_summary["status_counts"]),
            }
        )

    summarized.sort(
        key=lambda item: (
            int(item["error_count"]),
            int(item["hot_count"]),
            int(item["slow_count"]),
            float(item["max_ms"]),
            int(item["request_count"]),
        ),
        reverse=True,
    )
    return summarized


def _summarize_recent_error_families(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate recent errors into family-level summaries."""
    families: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        family = str(entry.get("route_family") or "other")
        family_summary = families.setdefault(
            family,
            {
                "family": family,
                "error_count": 0,
                "route_count": 0,
                "routes": set(),
                "max_duration_ms": 0.0,
                "latest_occurred_at": None,
                "status_counts": _empty_status_counts(),
            },
        )
        family_summary["error_count"] += 1
        family_summary["routes"].add(str(entry.get("route") or ""))
        family_summary["max_duration_ms"] = max(
            float(family_summary["max_duration_ms"]),
            float(entry.get("duration_ms") or 0.0),
        )
        occurred_at = entry.get("occurred_at")
        if occurred_at and (
            family_summary["latest_occurred_at"] is None
            or str(occurred_at) > str(family_summary["latest_occurred_at"])
        ):
            family_summary["latest_occurred_at"] = str(occurred_at)

        status_class = str(entry.get("status_class") or "other")
        if status_class in family_summary["status_counts"]:
            family_summary["status_counts"][status_class] += 1

    summarized: List[Dict[str, Any]] = []
    for family_summary in families.values():
        summarized.append(
            {
                "family": family_summary["family"],
                "error_count": int(family_summary["error_count"]),
                "route_count": len(family_summary["routes"]),
                "max_duration_ms": float(family_summary["max_duration_ms"]),
                "latest_occurred_at": family_summary["latest_occurred_at"],
                "status_counts": dict(family_summary["status_counts"]),
            }
        )

    summarized.sort(
        key=lambda item: (
            int(item["error_count"]),
            float(item["max_duration_ms"]),
            str(item["latest_occurred_at"] or ""),
        ),
        reverse=True,
    )
    return summarized


@dataclass
class _RouteLatencyBatch:
    """Rolling batch of request timings for one route label."""

    count: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    slow_count: int = 0
    error_count: int = 0
    samples_ms: List[float] = field(default_factory=list)
    status_counts: Dict[str, int] = field(default_factory=_empty_status_counts)


class _RouteLatencyAggregator:
    """Aggregate route timings and emit periodic summary snapshots."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._batches: Dict[str, _RouteLatencyBatch] = {}
        self._history: List[Dict[str, Any]] = []
        self._recent_errors: List[Dict[str, Any]] = []

    def reset(self) -> None:
        """Clear all in-memory route timing batches."""
        with self._lock:
            self._batches.clear()
            self._history.clear()
            self._recent_errors.clear()

    def _build_summary(
        self,
        route_label: str,
        *,
        count: int,
        avg_ms: float,
        p95_ms: float,
        max_ms: float,
        slow_count: int,
        error_count: int,
        status_counts: Dict[str, int],
    ) -> Dict[str, Any]:
        """Build a normalized route summary payload."""
        return {
            "route": route_label,
            "route_family": _get_route_family(route_label),
            "count": float(count),
            "avg_ms": avg_ms,
            "p95_ms": p95_ms,
            "max_ms": max_ms,
            "slow_count": float(slow_count),
            "error_count": float(error_count),
            "status_counts": _normalize_status_counts(status_counts),
            "profile": _get_request_latency_profile(route_label),
            "slow_threshold_ms": _get_slow_request_threshold_ms(route_label),
        }

    def _get_route_history_locked(
        self,
        route_label: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return recent emitted summaries for one route."""
        route_history = [
            entry for entry in reversed(self._history) if entry.get("route") == route_label
        ]
        if limit is not None:
            route_history = route_history[: max(limit, 0)]
        return route_history

    def _build_baseline_locked(
        self,
        route_label: str,
        current_avg_ms: float,
        current_p95_ms: float,
    ) -> Dict[str, float]:
        """Build baseline comparison fields from recent route history."""
        window_count = _get_route_baseline_windows()
        if window_count <= 0:
            return {}

        route_history = self._get_route_history_locked(route_label, limit=window_count)
        if not route_history:
            return {}

        baseline_avg_ms = sum(float(entry["avg_ms"]) for entry in route_history) / len(
            route_history
        )
        baseline_p95_ms = sum(float(entry["p95_ms"]) for entry in route_history) / len(
            route_history
        )
        return {
            "baseline_windows": float(len(route_history)),
            "baseline_avg_ms": baseline_avg_ms,
            "baseline_p95_ms": baseline_p95_ms,
            "avg_delta_ms": current_avg_ms - baseline_avg_ms,
            "p95_delta_ms": current_p95_ms - baseline_p95_ms,
        }

    def _annotate_hot_route_locked(self, summary: Dict[str, Any]) -> None:
        """Mark summaries that spike far above their recent baseline."""
        summary["is_hot"] = False
        summary["hot_reason"] = None

        baseline_windows = int(summary.get("baseline_windows") or 0)
        if baseline_windows < _get_route_hot_min_windows():
            return

        hot_multiplier = _get_route_hot_multiplier()
        min_delta_ms = _get_route_hot_min_delta_ms()
        comparisons = (
            (
                "p95",
                float(summary.get("p95_ms") or 0.0),
                float(summary.get("baseline_p95_ms") or 0.0),
                float(summary.get("p95_delta_ms") or 0.0),
            ),
            (
                "avg",
                float(summary.get("avg_ms") or 0.0),
                float(summary.get("baseline_avg_ms") or 0.0),
                float(summary.get("avg_delta_ms") or 0.0),
            ),
        )

        for metric_name, current_ms, baseline_ms, delta_ms in comparisons:
            if baseline_ms <= 0:
                continue
            if current_ms >= baseline_ms * hot_multiplier and delta_ms >= min_delta_ms:
                summary["is_hot"] = True
                summary["hot_reason"] = (
                    f"{metric_name} jumped from {baseline_ms:.1f}ms to "
                    f"{current_ms:.1f}ms (+{delta_ms:.1f}ms)"
                )
                return

    def _append_history_locked(self, summary: Dict[str, Any]) -> None:
        """Append a summary to the rolling history buffer."""
        history_limit = _get_route_history_limit()
        if history_limit <= 0:
            return

        history_entry = {
            **summary,
            "status_counts": dict(summary.get("status_counts") or {}),
            "emitted_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }
        self._history.append(history_entry)
        overflow = len(self._history) - history_limit
        if overflow > 0:
            del self._history[:overflow]

    def _append_recent_error_locked(
        self,
        *,
        route_label: str,
        method: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Append a recent non-success request outcome to the rolling error buffer."""
        error_limit = _get_recent_error_limit()
        if error_limit <= 0 or status_code < 400:
            return

        self._recent_errors.append(
            {
                "occurred_at": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "method": method,
                "route": route_label,
                "route_family": _get_route_family(route_label),
                "status_code": int(status_code),
                "status_class": _get_status_class(status_code),
                "duration_ms": float(duration_ms),
                "profile": _get_request_latency_profile(route_label),
            }
        )
        overflow = len(self._recent_errors) - error_limit
        if overflow > 0:
            del self._recent_errors[:overflow]

    def snapshot(self, limit: int = 20, reset: bool = False) -> List[Dict[str, Any]]:
        """Return a ranked snapshot of current route timing batches."""
        with self._lock:
            snapshots: List[Dict[str, Any]] = []
            for route_label, batch in self._batches.items():
                if batch.count <= 0:
                    continue
                avg_ms = batch.total_ms / batch.count
                p95_ms = _percentile_ms(batch.samples_ms, 0.95)
                summary = self._build_summary(
                    route_label,
                    count=batch.count,
                    avg_ms=avg_ms,
                    p95_ms=p95_ms,
                    max_ms=batch.max_ms,
                    slow_count=batch.slow_count,
                    error_count=batch.error_count,
                    status_counts=batch.status_counts,
                )
                summary.update(
                    self._build_baseline_locked(
                        route_label,
                        current_avg_ms=avg_ms,
                        current_p95_ms=p95_ms,
                    )
                )
                self._annotate_hot_route_locked(summary)
                snapshots.append(summary)

            snapshots.sort(
                key=lambda item: (
                    float(item["error_count"]),
                    float(item["slow_count"]),
                    float(item["max_ms"]),
                    float(item["avg_ms"]),
                    float(item["count"]),
                ),
                reverse=True,
            )

            if reset:
                self._batches.clear()

        return snapshots[: max(limit, 0)]

    def history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent emitted route summaries, newest first."""
        with self._lock:
            return list(reversed(self._history[-max(limit, 0) :]))

    def recent_errors(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent request errors, newest first."""
        with self._lock:
            return list(reversed(self._recent_errors[-max(limit, 0) :]))

    def record(
        self,
        route_label: str,
        duration_ms: float,
        status_code: int,
        slow_threshold_ms: float,
        method: str = "GET",
    ) -> Optional[Dict[str, Any]]:
        """Record a request duration and return a summary when the batch is full."""
        summary_every = _get_route_summary_every()
        if summary_every <= 0:
            return None

        with self._lock:
            self._append_recent_error_locked(
                route_label=route_label,
                method=method,
                status_code=status_code,
                duration_ms=duration_ms,
            )
            batch = self._batches.setdefault(route_label, _RouteLatencyBatch())
            batch.count += 1
            batch.total_ms += duration_ms
            batch.max_ms = max(batch.max_ms, duration_ms)
            batch.samples_ms.append(duration_ms)
            if duration_ms >= slow_threshold_ms:
                batch.slow_count += 1
            if status_code >= 400:
                batch.error_count += 1
            batch.status_counts[_get_status_class(status_code)] += 1

            if batch.count < summary_every:
                return None

            avg_ms = batch.total_ms / batch.count
            p95_ms = _percentile_ms(batch.samples_ms, 0.95)
            summary = self._build_summary(
                route_label,
                count=batch.count,
                avg_ms=avg_ms,
                p95_ms=p95_ms,
                max_ms=batch.max_ms,
                slow_count=batch.slow_count,
                error_count=batch.error_count,
                status_counts=batch.status_counts,
            )
            summary.update(
                self._build_baseline_locked(
                    route_label,
                    current_avg_ms=avg_ms,
                    current_p95_ms=p95_ms,
                )
            )
            self._annotate_hot_route_locked(summary)
            self._append_history_locked(summary)
            self._batches[route_label] = _RouteLatencyBatch()
            return summary


_ROUTE_LATENCY_AGGREGATOR = _RouteLatencyAggregator()


def get_route_latency_snapshot(
    limit: int = 20,
    reset: bool = False,
) -> Dict[str, Any]:
    """Expose the current in-memory route latency batches for dev tooling."""
    routes = _ROUTE_LATENCY_AGGREGATOR.snapshot(limit=limit, reset=reset)
    history = _ROUTE_LATENCY_AGGREGATOR.history(limit=limit)
    recent_errors = _ROUTE_LATENCY_AGGREGATOR.recent_errors(limit=limit)
    return {
        "summary_every": _get_route_summary_every(),
        "history_limit": _get_route_history_limit(),
        "baseline_windows": _get_route_baseline_windows(),
        "status_counts": _aggregate_entry_status_counts(routes),
        "history_status_counts": _aggregate_entry_status_counts(history),
        "recent_error_limit": _get_recent_error_limit(),
        "recent_error_count": len(recent_errors),
        "recent_error_status_counts": {
            key: sum(
                1 for entry in recent_errors if entry.get("status_class") == key
            )
            for key in _STATUS_CLASS_KEYS
        },
        "error_families": _summarize_recent_error_families(recent_errors),
        "families": _summarize_route_families(routes),
        "routes": routes,
        "history": history,
        "recent_errors": recent_errors,
    }


# =============================================================================
# App State — replaces module-level mutable globals (thread-safe access)
# =============================================================================


def get_cached_opportunities() -> List[Dict[str, Any]]:
    """Get cached opportunities from the last mission analysis."""
    return getattr(app.state, "opportunities_cache", [])


def set_cached_opportunities(opportunities: List[Dict[str, Any]]) -> None:
    """Set cached opportunities from mission analysis."""
    app.state.opportunities_cache = opportunities


# =============================================================================
# Lifespan — replaces deprecated @app.on_event (FastAPI 0.109+)
# =============================================================================
from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Manage startup/shutdown lifecycle."""
    # --- Startup ---
    config_manager.load_config()
    logger.info(
        f"Loaded {len(config_manager.ground_stations)} ground stations from configuration"
    )
    logger.info(
        f"Loaded {len(satellite_manager.get_satellites())} satellites from configuration"
    )
    app.state.opportunities_cache = []
    app.state.current_mission_data = {}

    yield

    # --- Shutdown ---
    logger.info("Application shutting down, cleaning up process pool...")
    cleanup_process_pool()
    logger.info("Process pool cleanup complete")


# Initialize FastAPI app
app = FastAPI(
    title="Satellite Mission Planning API",
    description="REST API for satellite mission planning and visualization",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def add_request_logging_context(
    request: Request,
    call_next: Any,
) -> Response:
    """Attach a stable request ID to logs and responses."""
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    token = set_log_context(request_id=request_id)
    started_at = perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (perf_counter() - started_at) * 1000.0
        _ROUTE_LATENCY_AGGREGATOR.record(
            route_label=_get_request_route_label(request),
            duration_ms=duration_ms,
            status_code=500,
            slow_threshold_ms=_get_slow_request_threshold_ms(request.url.path),
            method=request.method,
        )
        logger.exception(
            "HTTP %s %s -> 500 in %s",
            request.method,
            request.url.path,
            _format_request_duration(duration_ms),
        )
        raise
    finally:
        if "response" in locals():
            duration_ms = (perf_counter() - started_at) * 1000.0
            path = request.url.path
            route_label = _get_request_route_label(request)
            duration_text = _format_request_duration(duration_ms)
            latency_bucket = _get_latency_bucket(duration_ms)
            latency_profile = _get_request_latency_profile(path)
            slow_threshold_ms = _get_slow_request_threshold_ms(path)
            is_slow_request = (
                response.status_code < 400 and duration_ms >= slow_threshold_ms
            )
            if response.status_code >= 500:
                log_level = logging.ERROR
            elif response.status_code >= 400:
                log_level = logging.WARNING
            elif is_slow_request:
                log_level = logging.WARNING
            elif latency_profile == "quiet":
                log_level = logging.DEBUG
            else:
                log_level = logging.INFO

            if is_slow_request:
                logger.log(
                    log_level,
                    "Slow HTTP %s %s -> %d in %s (profile=%s threshold=%.0fms bucket=%s)",
                    request.method,
                    path,
                    response.status_code,
                    duration_text,
                    latency_profile,
                    slow_threshold_ms,
                    latency_bucket,
                )
            else:
                logger.log(
                    log_level,
                    "HTTP %s %s -> %d in %s",
                    request.method,
                    path,
                    response.status_code,
                    duration_text,
                )

            if latency_profile != "quiet":
                route_summary = _ROUTE_LATENCY_AGGREGATOR.record(
                    route_label=route_label,
                    duration_ms=duration_ms,
                    status_code=response.status_code,
                    slow_threshold_ms=slow_threshold_ms,
                    method=request.method,
                )
                if route_summary is not None:
                    is_hot_route = bool(route_summary.get("is_hot"))
                    summary_level = (
                        logging.WARNING
                        if route_summary["p95_ms"] >= slow_threshold_ms
                        or route_summary["error_count"] > 0
                        or is_hot_route
                        else logging.INFO
                    )
                    logger.log(
                        summary_level,
                        "Latency summary %s %s: count=%d avg=%s p95=%s max=%s slow=%d/%d errors=%d profile=%s threshold=%.0fms",
                        request.method,
                        route_label,
                        int(route_summary["count"]),
                        _format_request_duration(route_summary["avg_ms"]),
                        _format_request_duration(route_summary["p95_ms"]),
                        _format_request_duration(route_summary["max_ms"]),
                        int(route_summary["slow_count"]),
                        int(route_summary["count"]),
                        int(route_summary["error_count"]),
                        latency_profile,
                        slow_threshold_ms,
                    )
                    if is_hot_route:
                        logger.warning(
                            "Hot route %s %s: %s (baseline_windows=%d avg=%s baseline_avg=%s p95=%s baseline_p95=%s)",
                            request.method,
                            route_label,
                            route_summary.get("hot_reason"),
                            int(route_summary.get("baseline_windows") or 0),
                            _format_request_duration(float(route_summary["avg_ms"])),
                            _format_request_duration(
                                float(route_summary.get("baseline_avg_ms") or 0.0)
                            ),
                            _format_request_duration(float(route_summary["p95_ms"])),
                            _format_request_duration(
                                float(route_summary.get("baseline_p95_ms") or 0.0)
                            ),
                        )
        reset_log_context(token)

    response.headers["X-Request-ID"] = request_id
    return response

# CORS — use CORS_ORIGINS env var in production, default to * for development
_cors_origins_env = os.environ.get("CORS_ORIGINS", "*")
_cors_origins = (
    [o.strip() for o in _cors_origins_env.split(",")]
    if _cors_origins_env != "*"
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(workspaces_router)
app.include_router(validation_router)
app.include_router(config_admin_router)
app.include_router(schedule_router)
app.include_router(orders_router)
app.include_router(batching_router)
app.include_router(dev_router)

# Serve static files (built React app)
if os.path.exists("../frontend/dist"):
    app.mount("/static", StaticFiles(directory="../frontend/dist"), name="static")


# Pydantic models — imported from backend.schemas (extracted for maintainability)
from backend.schemas import (  # noqa: E402
    BatchPassEnrichmentRequest,
    BenchmarkRequest,
    CoordinateInput,
    DebugSatellite,
    DebugTarget,
    EnrichedPassResponse,
    GeometryAnalysisRequest,
    LightingAnalysisRequest,
    MissionRequest,
    MissionResponse,
    ParsedTarget,
    PassEnrichmentRequest,
    PassGeometryResponse,
    PassLightingResponse,
    PassManeuverResponse,
    PassQualityResponse,
    PlanningAuditMetadata,
    PlanningParams,
    PlanningRequest,
    PlanningResponse,
    RunScenarioRequest,
    SARInputParams,
    SatelliteCreateRequest,
    SatelliteUpdateRequest,
    TargetData,
    TimeWindow,
    TLEData,
)

# Global state moved to app.state via lifespan (see above)


# =============================================================================
# STK-like Pass Enrichment Helper
# =============================================================================


def _enrich_and_convert_pass(
    pass_details: Any,
    pass_index: int,
    targets: List[Any],
    vis_calc: Any,
) -> Dict[str, Any]:
    """
    Enrich a pass with STK-like comprehensive data and convert to dictionary.

    Args:
        pass_details: PassDetails object
        pass_index: Index of this pass in the list
        targets: List of GroundTarget objects
        vis_calc: VisibilityCalculator instance

    Returns:
        Dictionary with all pass data including STK-like enhancements
    """
    # Find the corresponding target
    target = next((t for t in targets if t.name == pass_details.target_name), None)

    # Set pass index
    pass_details.pass_index = pass_index

    # Enrich with STK-like data if we have both target and vis_calc
    if target and vis_calc:
        try:
            vis_calc.enrich_pass_with_stk_data(
                pass_details,
                target,
                max_roll_rate_dps=1.0,  # Default roll rate
                sensor_gsd_base_m=None,  # GSD not computed for now
            )
        except Exception as e:
            logger.warning(f"Failed to enrich pass {pass_index}: {e}")

    # Use the PassDetails.to_dict() method which includes all STK-like data
    result: Dict[str, Any] = pass_details.to_dict()
    return result


def _summarize_czml_packets(czml_data: List[Dict[str, Any]]) -> Dict[str, int]:
    """Create a compact packet summary for log output."""
    counts: Counter[str] = Counter()

    for packet in czml_data:
        packet_id = str(packet.get("id", "unknown"))
        if packet_id == "document":
            counts["document"] += 1
        elif packet_id == "pointing_cone":
            counts["pointing_cone"] += 1
        elif packet_id.startswith("agility_envelope_"):
            counts["agility_envelope"] += 1
        elif packet_id.startswith("pass_track"):
            counts["pass_track"] += 1
        elif packet_id.startswith("target_"):
            counts["target"] += 1
        elif packet_id.endswith("_ground_track") or packet_id == "satellite_ground_track":
            counts["ground_track"] += 1
        elif packet_id.startswith("sat_"):
            counts["satellite"] += 1
        else:
            counts["other"] += 1

    counts["total"] = len(czml_data)
    return dict(counts)


# =============================================================================
# Constellation Support Functions
# =============================================================================

# Import shared color palette (single source of truth)
from backend.constants.colors import get_satellite_color_by_index


def create_satellite_orbit_from_tle(tle_data: TLEData) -> SatelliteOrbit:
    """
    Create a SatelliteOrbit instance from TLEData.

    Args:
        tle_data: TLEData with name, line1, line2

    Returns:
        SatelliteOrbit instance with loaded orbit predictor
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
        f.write(f"{tle_data.name}\n{tle_data.line1}\n{tle_data.line2}\n")
        tle_file = f.name

    try:
        satellite = SatelliteOrbit.from_tle_file(tle_file, satellite_name=tle_data.name)
        return satellite
    finally:
        os.unlink(tle_file)


def create_satellites_from_request(
    request: MissionRequest,
) -> Dict[str, SatelliteOrbit]:
    """
    Create satellite orbit objects from mission request.

    Handles both legacy single-satellite and new constellation formats.

    Args:
        request: MissionRequest with tle or satellites field

    Returns:
        Dict mapping satellite_id to SatelliteOrbit instance
    """
    satellites = {}
    satellite_list = request.get_satellite_list()

    for tle_data in satellite_list:
        sat_id = f"sat_{tle_data.name}"
        satellites[sat_id] = create_satellite_orbit_from_tle(tle_data)
        logger.info(f"Created satellite orbit for {tle_data.name} (id: {sat_id})")

    return satellites


def assign_satellite_colors(satellite_list: List[TLEData]) -> Dict[str, str]:
    """
    Assign distinct colors to each satellite for visualization.
    Supports any constellation size with automatic color generation for 9+ satellites.

    Args:
        satellite_list: List of TLEData objects

    Returns:
        Dict mapping satellite_id to hex color string
    """
    return {
        f"sat_{s.name}": get_satellite_color_by_index(i)
        for i, s in enumerate(satellite_list)
    }


def get_satellite_info_list(satellite_list: List[TLEData]) -> List[Dict[str, str]]:
    """
    Build satellite info list for API response.

    Args:
        satellite_list: List of TLEData objects

    Returns:
        List of dicts with id, name, and color for each satellite
    """
    colors = assign_satellite_colors(satellite_list)
    return [
        {"id": f"sat_{s.name}", "name": s.name, "color": colors[f"sat_{s.name}"]}
        for s in satellite_list
    ]


# =============================================================================
# API Endpoints
# =============================================================================


@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint - health check"""
    return {"message": "Satellite Mission Planning API is running"}


@app.post("/api/v1/tle/validate")
async def validate_tle(tle_data: TLEData) -> Dict[str, Any]:
    """Validate TLE data and return satellite information"""
    try:
        # Create temporary TLE file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write(f"{tle_data.name}\n{tle_data.line1}\n{tle_data.line2}\n")
            tle_file = f.name

        # Validate TLE by creating SatelliteOrbit
        satellite = SatelliteOrbit.from_tle_file(tle_file, satellite_name=tle_data.name)

        # Get current position for validation
        now = datetime.now(timezone.utc)
        lat, lon, alt = satellite.get_position(now)

        # Clean up temp file
        os.unlink(tle_file)

        return {
            "valid": True,
            "satellite_name": tle_data.name,
            "current_position": {
                "latitude": lat,
                "longitude": lon,
                "altitude_km": alt,
                "timestamp": now.isoformat(),
            },
            "orbital_period_minutes": satellite.get_orbital_period().total_seconds()
            / 60.0,
        }

    except Exception as e:
        logger.error(f"TLE validation failed: {str(e)}")
        return {"valid": False, "error": str(e)}


@app.post("/api/v1/mission/analyze")
async def analyze_mission(request: MissionRequest) -> MissionResponse:
    """Analyze mission and return visibility windows, CZML data, and schedules"""
    try:
        # Get normalized satellite list (works for both legacy and constellation)
        satellite_list = request.get_satellite_list()
        is_constellation = request.is_constellation()

        logger.info(
            "Mission analysis started: satellites=%d constellation=%s",
            len(satellite_list),
            is_constellation,
        )

        # Validate mission inputs against platform constraints
        satellite_ids = [sat.name for sat in satellite_list]
        mission_input = {
            "imagingType": request.imaging_type,
            "pointingAngle": request.max_spacecraft_roll_deg,
            "startTime": request.start_time,
            "endTime": request.end_time,
            "sar": request.sar.model_dump() if request.sar else None,
        }
        validation_result = validate_mission_input(
            mission_input, satellite_ids, clamp_on_warning=True
        )

        if not validation_result.valid:
            error_msgs = "; ".join([e.message for e in validation_result.errors])
            raise HTTPException(
                status_code=400, detail=f"Validation failed: {error_msgs}"
            )

        # Log warnings
        for warning in validation_result.warnings:
            logger.warning(
                f"Mission input warning: {warning.field} - {warning.message}"
            )

        # Create satellite orbit objects using factory
        satellites_dict = create_satellites_from_request(request)

        # For current implementation, use primary (first) satellite
        # Multi-satellite pass computation will be added in PR #3
        primary_tle = satellite_list[0]
        primary_sat_id = f"sat_{primary_tle.name}"
        satellite = satellites_dict[primary_sat_id]

        # Build satellite info for response
        satellite_info_list = get_satellite_info_list(satellite_list)

        # Get sensor FOV from satellite config (if managed satellite)
        # NOTE: imaging_type and max_spacecraft_roll come from REQUEST, not satellite config
        # This allows using SAR satellite TLEs for optical analysis (common use case)
        sensor_fov_from_satellite = None
        max_roll_from_satellite = None

        # Use REQUEST imaging_type (not satellite config) for settings lookup
        # This improves DX: user can use any satellite TLE for any imaging type
        effective_imaging_type = request.imaging_type or "optical"
        logger.debug("Using imaging_type from request: %s", effective_imaging_type)

        # Get max_spacecraft_roll from satellite_settings based on REQUEST imaging_type
        if (
            effective_imaging_type == "optical"
            and "optical" in satellite_manager.satellite_settings
        ):
            optical_settings = satellite_manager.satellite_settings["optical"]
            if (
                "spacecraft" in optical_settings
                and "max_spacecraft_roll_deg" in optical_settings["spacecraft"]
            ):
                max_roll_from_satellite = optical_settings["spacecraft"][
                    "max_spacecraft_roll_deg"
                ]
                logger.debug(
                    "Using max spacecraft roll from optical settings: %s°",
                    max_roll_from_satellite,
                )
        elif (
            effective_imaging_type == "sar"
            and "sar" in satellite_manager.satellite_settings
        ):
            sar_settings = satellite_manager.satellite_settings["sar"]
            if (
                "spacecraft" in sar_settings
                and "max_spacecraft_roll_deg" in sar_settings["spacecraft"]
            ):
                max_roll_from_satellite = sar_settings["spacecraft"][
                    "max_spacecraft_roll_deg"
                ]
                logger.debug(
                    "Using max spacecraft roll from SAR settings: %s°",
                    max_roll_from_satellite,
                )

        # Check if primary satellite is managed (in satellites.yaml) for sensor FOV only
        managed_satellites = satellite_manager.get_satellites()
        for sat in managed_satellites:
            if sat.name == primary_tle.name:
                # Use sensor FOV from satellite config (if available)
                if (
                    hasattr(sat, "sensor_fov_half_angle_deg")
                    and sat.sensor_fov_half_angle_deg is not None
                ):
                    sensor_fov_from_satellite = sat.sensor_fov_half_angle_deg
                    logger.debug(
                        "Using sensor FOV from satellite config: %s° for %s",
                        sensor_fov_from_satellite,
                        sat.name,
                    )
                break

        # Create targets with configuration-based elevation masks
        targets = []
        actual_max_spacecraft_roll = None  # Track for CZML generation
        for target_data in request.targets:
            # Determine elevation mask from configuration
            if request.elevation_mask is not None:
                # Use explicit elevation mask from request
                elevation_mask = request.elevation_mask
            elif request.ground_station_name:
                # Use ground station specific elevation mask
                elevation_mask = config_manager.get_elevation_mask(
                    request.ground_station_name, request.mission_type
                )
            else:
                # Use mission-type defaults from config
                if request.mission_type in config_manager.mission_settings:
                    _mask = config_manager.mission_settings[
                        request.mission_type
                    ].default_elevation_mask
                    elevation_mask = float(_mask) if _mask is not None else 10.0
                else:
                    _mask = config_manager.defaults.get("elevation_mask", 10)
                    elevation_mask = float(_mask) if _mask is not None else 10.0

            # Handle sensor FOV with priority: satellite config > request > defaults
            sensor_fov = None
            if sensor_fov_from_satellite is not None:
                # First priority: Sensor FOV from satellite config (satellites.yaml)
                sensor_fov = sensor_fov_from_satellite
                logger.debug(
                    "Target '%s': sensor_fov_half_angle_deg=%s° from satellite config",
                    target_data.name,
                    sensor_fov,
                )
            elif (
                hasattr(request, "sensor_fov_half_angle_deg")
                and request.sensor_fov_half_angle_deg is not None
            ):
                # Second priority: Sensor FOV from request (deprecated path)
                sensor_fov = request.sensor_fov_half_angle_deg
                logger.debug(
                    "Target '%s': sensor_fov_half_angle_deg=%s° from request",
                    target_data.name,
                    sensor_fov,
                )
            else:
                # No FOV specified anywhere, will use target defaults
                logger.debug(
                    "Target '%s': no sensor FOV specified, using imaging-type defaults",
                    target_data.name,
                )

            # Handle max spacecraft roll (agility limit) for visibility analysis
            # This determines which opportunities are POSSIBLE (satellite can slew to point)
            max_spacecraft_roll = None
            if max_roll_from_satellite is not None:
                # Use from satellite_settings based on REQUEST imaging_type
                max_spacecraft_roll = max_roll_from_satellite
                logger.debug(
                    "Target '%s': max_spacecraft_roll=%s° from %s settings",
                    target_data.name,
                    max_spacecraft_roll,
                    effective_imaging_type,
                )
            elif request.max_spacecraft_roll_deg is not None:
                # Use from request
                max_spacecraft_roll = request.max_spacecraft_roll_deg
                logger.debug(
                    "Target '%s': max_spacecraft_roll=%s° from request",
                    target_data.name,
                    max_spacecraft_roll,
                )
            else:
                # Default to 45° for optical
                max_spacecraft_roll = 45.0
                logger.debug(
                    "Target '%s': no max roll specified, using default %s°",
                    target_data.name,
                    max_spacecraft_roll,
                )

            # Save for CZML generation (use first target's value)
            if actual_max_spacecraft_roll is None:
                actual_max_spacecraft_roll = max_spacecraft_roll

            target = GroundTarget(
                name=target_data.name,
                latitude=target_data.latitude,
                longitude=target_data.longitude,
                description=target_data.description or "",
                mission_type=request.mission_type,
                elevation_mask=elevation_mask,
                sensor_fov_half_angle_deg=sensor_fov,  # Sensor FOV (for visualization)
                max_spacecraft_roll=max_spacecraft_roll,  # Spacecraft agility limit (for visibility)
                priority=(
                    target_data.priority if target_data.priority is not None else 5
                ),
                color=(
                    target_data.color if target_data.color else "#EF4444"
                ),  # Marker color
            )
            # Log imaging type for imaging missions
            if request.mission_type == "imaging":
                logger.debug(
                    "Target '%s': imaging_type=%s",
                    target_data.name,
                    effective_imaging_type,
                )
            targets.append(target)

        # Parse start time and end time
        start_time = datetime.fromisoformat(request.start_time.replace("Z", "+00:00"))

        # Handle end_time vs duration_hours (end_time takes precedence)
        if request.end_time:
            # Use explicit end_time
            end_time = datetime.fromisoformat(request.end_time.replace("Z", "+00:00"))
            logger.debug("Using end_time from request: %s", request.end_time)
        elif request.duration_hours is not None:
            # Backward compatibility: use duration_hours
            end_time = start_time + timedelta(hours=request.duration_hours)
            logger.debug(
                "Using duration_hours from request: %sh",
                request.duration_hours,
            )
        else:
            # Neither provided - error
            raise ValueError("Either end_time or duration_hours must be provided")

        # Validate that end_time is after start_time
        if end_time <= start_time:
            raise ValueError(
                f"end_time ({end_time}) must be after start_time ({start_time})"
            )

        # Calculate duration for logging and response
        duration_hours = (end_time - start_time).total_seconds() / 3600.0
        # Determine if we should use parallel processing
        # Auto-enable for 2+ targets (1 target has overhead that exceeds benefit)
        use_parallel = request.use_parallel
        if use_parallel is None:
            use_parallel = len(targets) >= 2  # Enable for 2+ targets

        logger.info(
            "Mission request: targets=%d mission_type=%s imaging_type=%s window=%s..%s duration_hours=%.2f parallel=%s adaptive=%s",
            len(targets),
            request.mission_type,
            effective_imaging_type,
            request.start_time,
            request.end_time or f"+{request.duration_hours}h",
            duration_hours,
            use_parallel,
            bool(request.use_adaptive),
        )

        # =========================================================================
        # CONSTELLATION SUPPORT: Compute passes for ALL satellites
        # =========================================================================
        all_passes = []
        passes_by_satellite = {}
        sar_passes_list = []  # For SAR-specific pass data
        is_sar_mission = effective_imaging_type == "sar"

        # Prepare SAR parameters if this is a SAR mission
        sar_input_params = None
        if is_sar_mission:
            from backend.sar_czml import generate_sar_czml

            from mission_planner.sar_config import LookSide, PassDirection
            from mission_planner.sar_config import SARInputParams as SARConfigParams
            from mission_planner.sar_config import SARMode
            from mission_planner.sar_visibility import SARVisibilityCalculator

            # Get SAR params from request or use defaults
            # Map API mode names to internal names: spotlight→spot, stripmap→strip
            api_to_internal_mode = {
                "spotlight": "spot",
                "stripmap": "strip",
                "scan": "scan",
                "spot": "spot",
                "strip": "strip",
            }

            if request.sar:
                sar_input_params = SARConfigParams(
                    imaging_mode=SARMode.from_string(request.sar.imaging_mode),
                    incidence_min_deg=request.sar.incidence_min_deg,
                    incidence_max_deg=request.sar.incidence_max_deg,
                    look_side=LookSide.from_string(request.sar.look_side),
                    pass_direction=PassDirection.from_string(
                        request.sar.pass_direction
                    ),
                )
            elif request.sar_mode:
                # Use sar_mode from top-level request (frontend sends this)
                from mission_planner.sar_config import get_default_sar_params

                internal_mode = api_to_internal_mode.get(
                    request.sar_mode.lower(), "strip"
                )
                sar_input_params = get_default_sar_params(internal_mode)
            else:
                # Use defaults for strip mode
                from mission_planner.sar_config import get_default_sar_params

                sar_input_params = get_default_sar_params("strip")

            logger.info(
                "SAR mission analysis: mode=%s look_side=%s pass_direction=%s",
                sar_input_params.imaging_mode.value,
                sar_input_params.look_side.value,
                sar_input_params.pass_direction.value,
            )

        for sat_id, sat_orbit in satellites_dict.items():
            # Get satellite name from ID (remove "sat_" prefix)
            sat_name = sat_id.replace("sat_", "")

            logger.info("Computing passes for satellite: %s (%s)", sat_name, sat_id)

            # Create mission planner for this satellite
            sat_planner = MissionPlanner(satellite=sat_orbit, targets=targets)

            # Run mission analysis for this satellite
            sat_passes_dict = sat_planner.compute_passes(
                start_time,
                end_time,
                use_parallel=use_parallel,
                max_workers=request.max_workers,
                use_adaptive=(
                    request.use_adaptive if request.use_adaptive is not None else True
                ),
            )

            # Flatten passes and tag with satellite_id
            sat_all_passes = []
            for target_name, target_passes in sat_passes_dict.items():
                for p in target_passes:
                    # Tag pass with satellite_id for constellation tracking
                    p.satellite_id = sat_id
                    sat_all_passes.append(p)

            # SAR-specific analysis: enhance passes with SAR attributes
            if is_sar_mission and sar_input_params:
                base_vis_calc = VisibilityCalculator(
                    satellite=sat_orbit, use_adaptive=False
                )
                sar_calc = SARVisibilityCalculator(base_vis_calc, sar_input_params)

                for p in sat_all_passes:
                    # Find matching target
                    matching_target = next(
                        (t for t in targets if t.name == p.target_name), None
                    )
                    if matching_target is not None:
                        # Compute SAR-specific attributes for this pass
                        sar_passes = sar_calc.compute_sar_passes(
                            matching_target.latitude,
                            matching_target.longitude,
                            matching_target.name,
                            p.start_time,
                            p.end_time,
                        )
                        if sar_passes:
                            # Use first SAR pass that matches this base pass
                            sar_pass = sar_passes[0]
                            sar_passes_list.append(sar_pass)
                            # Copy SAR data to base pass
                            if hasattr(sar_pass, "sar_data") and sar_pass.sar_data:
                                p.mode = "SAR"
                                p.sar_data = sar_pass.sar_data

            passes_by_satellite[sat_id] = sat_all_passes
            all_passes.extend(sat_all_passes)

            logger.info("Found %d passes for %s", len(sat_all_passes), sat_name)

        # Sort all passes chronologically across all satellites
        all_passes.sort(key=lambda p: p.start_time)

        logger.info(
            "Total passes across %d satellite(s): %d",
            len(satellites_dict),
            len(all_passes),
        )

        # Get satellite agility from satellite configuration
        satellite_agility = 1.0  # Default value
        managed_satellite = satellite_manager.get_satellite_by_id(primary_tle.name)
        if managed_satellite is None:
            # Try to find by name if ID lookup fails
            for sat in satellite_manager.get_satellites():
                if sat.name == primary_tle.name:
                    managed_satellite = sat
                    break

        if managed_satellite:
            satellite_agility = managed_satellite.satellite_agility
            logger.debug(
                "Using satellite agility from config: %s°/s for %s",
                satellite_agility,
                primary_tle.name,
            )
        else:
            logger.warning(
                f"Satellite '{primary_tle.name}' not found in configuration, using default agility: {satellite_agility}°/s"
            )

        # Get sensor FOV from first target (they should all be the same)
        actual_sensor_fov = (
            targets[0].sensor_fov_half_angle_deg
            if targets and hasattr(targets[0], "sensor_fov_half_angle_deg")
            else None
        )

        # Create visibility calculator for STK-like pass enrichment
        # Use primary satellite for enrichment (constellation passes are tagged with sat_id)
        primary_vis_calc = VisibilityCalculator(satellite=satellite, use_adaptive=False)

        # Generate mission data
        mission_data: Dict[str, Any] = {
            # Legacy single satellite name (for backward compatibility)
            "satellite_name": primary_tle.name if not is_constellation else None,
            # NEW: Constellation support
            "satellites": satellite_info_list,
            "is_constellation": is_constellation,
            "mission_type": request.mission_type,
            "imaging_type": effective_imaging_type,  # optical or sar
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_hours": duration_hours,  # Calculated duration for backward compatibility
            "elevation_mask": (
                request.elevation_mask
                if request.elevation_mask is not None
                else elevation_mask
            ),
            "sensor_fov_half_angle_deg": actual_sensor_fov,
            "max_spacecraft_roll_deg": request.max_spacecraft_roll_deg,
            "max_spacecraft_pitch_deg": (
                request.max_spacecraft_pitch_deg
                if request.max_spacecraft_pitch_deg is not None
                else request.max_spacecraft_roll_deg
            ),  # 2D slew: default to same as roll
            "satellite_agility": satellite_agility,
            "total_passes": len(all_passes),
            "targets": [
                {
                    "name": t.name,
                    "latitude": t.latitude,
                    "longitude": t.longitude,
                    "description": t.description,
                    "priority": t.priority,
                    "color": t.color,
                }
                for t in targets
            ],
            "passes": [
                _enrich_and_convert_pass(p, idx, targets, primary_vis_calc)
                for idx, p in enumerate(all_passes)
            ],
        }

        # Add SAR-specific data to mission response
        if is_sar_mission and sar_input_params:
            mission_data["sar"] = {
                "imaging_mode": sar_input_params.imaging_mode.value,
                "look_side": sar_input_params.look_side.value,
                "pass_direction": sar_input_params.pass_direction.value,
                "incidence_min_deg": sar_input_params.incidence_min_deg,
                "incidence_max_deg": sar_input_params.incidence_max_deg,
                "sar_passes_count": len(sar_passes_list),
            }

        # Pass mission parameters to CZML generator
        actual_sensor_fov = None

        if request.mission_type == "imaging":
            # Get sensor FOV: prioritize satellite config > target > request
            if sensor_fov_from_satellite is not None:
                actual_sensor_fov = sensor_fov_from_satellite
            elif (
                targets
                and hasattr(targets[0], "sensor_fov_half_angle_deg")
                and targets[0].sensor_fov_half_angle_deg is not None
            ):
                actual_sensor_fov = targets[0].sensor_fov_half_angle_deg
            elif request.sensor_fov_half_angle_deg is not None:
                actual_sensor_fov = request.sensor_fov_half_angle_deg

        logger.info(
            "Generating CZML: mission_type=%s sensor_fov_half_angle_deg=%s",
            request.mission_type,
            actual_sensor_fov,
        )

        filtered_passes = [p for p in all_passes if p.max_elevation >= 0]

        # Build satellite colors dict for CZML
        satellite_colors_dict = {
            info["id"]: info["color"] for info in satellite_info_list
        }

        generator = CZMLGenerator(
            satellite=satellite,
            satellites=satellites_dict,
            satellite_colors=satellite_colors_dict,
            targets=targets,
            passes=filtered_passes,
            start_time=start_time,
            end_time=end_time,
            mission_type=request.mission_type,
            sensor_fov_half_angle_deg=actual_sensor_fov,
            max_spacecraft_roll_deg=actual_max_spacecraft_roll,
            imaging_type=request.imaging_type,  # "optical" or "sar"
        )
        logger.debug(
            "CZMLGenerator initialized with sensor_fov=%s°, max_roll=%s°",
            generator.sensor_fov_half_angle_deg,
            generator.max_spacecraft_roll_deg,
        )

        # Generate CZML for Cesium visualization
        czml_data = generator.generate()

        # Add SAR-specific CZML packets if this is a SAR mission
        if is_sar_mission and sar_passes_list:
            from backend.sar_czml import generate_sar_czml

            sar_czml_packets = generate_sar_czml(
                satellite=satellite,
                sar_passes=sar_passes_list,
                start_time=start_time,
                end_time=end_time,
                include_dynamic_swath=True,
                sar_params=sar_input_params,
            )
            czml_data.extend(sar_czml_packets)
            logger.info("Added %d SAR swath CZML packets", len(sar_czml_packets))

        packet_summary = _summarize_czml_packets(czml_data)
        logger.info(
            "CZML summary: total=%d satellites=%d ground_tracks=%d pass_tracks=%d targets=%d pointing_cones=%d agility_envelopes=%d other=%d",
            packet_summary.get("total", 0),
            packet_summary.get("satellite", 0),
            packet_summary.get("ground_track", 0),
            packet_summary.get("pass_track", 0),
            packet_summary.get("target", 0),
            packet_summary.get("pointing_cone", 0),
            packet_summary.get("agility_envelope", 0),
            packet_summary.get("other", 0),
        )

        # Store in app state (for development - use proper storage in production)
        app.state.current_mission_data = {
            "mission_data": mission_data,
            "czml_data": czml_data,
            "satellite": satellite,
            "satellites_dict": satellites_dict,  # All satellites for constellation scheduling
            "targets": targets,
            "passes": all_passes,
        }

        # Note: temp files are cleaned up in create_satellites_from_request()

        logger.info(
            "Mission analysis completed: passes=%d czml_packets=%d window=%s..%s",
            len(all_passes),
            len(czml_data),
            start_time.strftime("%Y-%m-%d %H:%M"),
            end_time.strftime("%Y-%m-%d %H:%M"),
        )
        if all_passes:
            first_pass = all_passes[0]
            logger.debug(
                "First pass types: start=%s (%s) end=%s (%s)",
                first_pass.start_time,
                type(first_pass.start_time),
                first_pass.end_time,
                type(first_pass.end_time),
            )

        # Log the final response structure
        response_data = {"mission_data": mission_data, "czml_data": czml_data}
        logger.debug(
            "Final response data czml type=%s length=%d",
            type(czml_data),
            len(czml_data) if czml_data else 0,
        )

        return MissionResponse(
            success=True,
            message=f"Mission analysis completed. Found {len(all_passes)} passes.",
            data=response_data,
        )

    except Exception as e:
        logger.error(f"Mission analysis failed: {str(e)}")
        return MissionResponse(
            success=False, message=f"Mission analysis failed: {str(e)}"
        )


@app.get("/api/v1/mission/czml")
async def get_mission_czml() -> List[Dict[str, Any]]:
    """Get CZML data for current mission"""
    _cmd = getattr(app.state, "current_mission_data", {})
    if not _cmd:
        raise HTTPException(status_code=404, detail="No mission data available")

    czml_result: List[Dict[str, Any]] = _cmd.get("czml_data", [])
    return czml_result


@app.get("/api/v1/mission/schedule")
async def get_mission_schedule() -> Dict[str, Any]:
    """Get mission schedule data"""
    _cmd = getattr(app.state, "current_mission_data", {})
    if not _cmd:
        raise HTTPException(status_code=404, detail="No mission data available")

    result: Dict[str, Any] = _cmd.get("mission_data", {})
    return result


# =============================================================================
# STK-like Analysis API Endpoints
# =============================================================================


@app.post("/api/v1/analysis/geometry", tags=["Analysis"])
async def analyze_geometry(request: GeometryAnalysisRequest) -> PassGeometryResponse:
    """
    Analyze satellite-target geometry at a specific timestamp.

    Returns elevation, azimuth, range, incidence angle, and optional GSD.
    """
    try:
        # Create satellite from TLE lines
        tle_lines = [
            request.satellite_tle.name,
            request.satellite_tle.line1,
            request.satellite_tle.line2,
        ]
        satellite = SatelliteOrbit(tle_lines, request.satellite_tle.name)
        vis_calc = VisibilityCalculator(satellite=satellite, use_adaptive=False)

        # Create target
        target = GroundTarget(
            name=request.target.name,
            latitude=request.target.latitude,
            longitude=request.target.longitude,
            description=request.target.description or "",
            mission_type="imaging",
        )

        # Parse timestamp
        timestamp = datetime.fromisoformat(request.timestamp.replace("Z", "+00:00"))
        if timestamp.tzinfo:
            timestamp = timestamp.replace(tzinfo=None)

        # Compute geometry
        geometry = vis_calc._compute_geometry_at_time(
            target, timestamp, request.sensor_gsd_base_m
        )

        return PassGeometryResponse(
            elevation_deg=geometry.elevation_deg,
            azimuth_deg=geometry.azimuth_deg,
            range_km=geometry.range_km,
            incidence_angle_deg=geometry.incidence_angle_deg,
            ground_sample_distance_m=geometry.ground_sample_distance_m,
        )

    except Exception as e:
        logger.error(f"Geometry analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/analysis/lighting", tags=["Analysis"])
async def analyze_lighting(request: LightingAnalysisRequest) -> PassLightingResponse:
    """
    Analyze lighting conditions at a location and time.

    Returns sun elevation, target illumination status, and local solar time.
    """
    try:
        from mission_planner.sunlight import get_sun_elevation, is_target_illuminated

        # Parse timestamp
        timestamp = datetime.fromisoformat(request.timestamp.replace("Z", "+00:00"))
        if timestamp.tzinfo:
            timestamp = timestamp.replace(tzinfo=None)

        # Get sun elevation
        sun_elevation = get_sun_elevation(
            request.latitude, request.longitude, timestamp
        )

        # Check illumination
        target_sunlit = is_target_illuminated(
            request.latitude, request.longitude, timestamp, min_sun_elevation=0.0
        )

        # Calculate local solar time
        utc_hour = timestamp.hour + timestamp.minute / 60 + timestamp.second / 3600
        lst_hour = (utc_hour + request.longitude / 15) % 24
        lst_minutes = int((lst_hour % 1) * 60)
        lst_hour_int = int(lst_hour)
        local_solar_time = f"{lst_hour_int:02d}:{lst_minutes:02d}"

        return PassLightingResponse(
            target_sunlit=target_sunlit,
            satellite_sunlit=sun_elevation > -18,  # Civil twilight approximation
            sun_elevation_deg=sun_elevation,
            local_solar_time=local_solar_time,
        )

    except Exception as e:
        logger.error(f"Lighting analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/analysis/pass/enrich", tags=["Analysis"])
async def enrich_pass(request: PassEnrichmentRequest) -> EnrichedPassResponse:
    """
    Enrich a single pass with comprehensive STK-like metrics.

    Computes geometry at AOS/TCA/LOS, lighting, quality score, and maneuver requirements.
    """
    try:
        # Create satellite from TLE lines
        tle_lines = [
            request.satellite_tle.name,
            request.satellite_tle.line1,
            request.satellite_tle.line2,
        ]
        satellite = SatelliteOrbit(tle_lines, request.satellite_tle.name)
        vis_calc = VisibilityCalculator(satellite=satellite, use_adaptive=False)

        # Create target
        target = GroundTarget(
            name=request.target.name,
            latitude=request.target.latitude,
            longitude=request.target.longitude,
            description=request.target.description or "",
            mission_type="imaging",
        )

        # Parse timestamps
        start_time = datetime.fromisoformat(request.start_time.replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(request.end_time.replace("Z", "+00:00"))
        max_elev_time = datetime.fromisoformat(
            request.max_elevation_time.replace("Z", "+00:00")
        )

        for ts in [start_time, end_time, max_elev_time]:
            if ts.tzinfo:
                ts = ts.replace(tzinfo=None)

        # Import PassDetails
        from mission_planner.visibility import PassDetails

        # Create PassDetails object
        pass_details = PassDetails(
            target_name=request.target.name,
            satellite_name=request.satellite_tle.name,
            start_time=start_time.replace(tzinfo=None),
            end_time=end_time.replace(tzinfo=None),
            max_elevation_time=max_elev_time.replace(tzinfo=None),
            max_elevation=request.max_elevation,
            start_azimuth=0.0,  # Will be computed
            max_elevation_azimuth=0.0,
            end_azimuth=0.0,
            pass_index=0,
        )

        # Enrich with STK-like data
        vis_calc.enrich_pass_with_stk_data(
            pass_details, target, request.max_roll_rate_dps
        )

        # Convert to response
        pass_dict = pass_details.to_dict()

        return EnrichedPassResponse(
            target=pass_dict["target"],
            satellite_name=pass_dict["satellite_name"],
            satellite_id=pass_dict.get(
                "satellite_id", f"sat_{pass_dict['satellite_name']}"
            ),
            pass_index=pass_dict.get("pass_index", 0),
            start_time=pass_dict["start_time"],
            end_time=pass_dict["end_time"],
            max_elevation_time=pass_dict["max_elevation_time"],
            duration_s=pass_dict.get("duration_s", 0),
            max_elevation=pass_dict["max_elevation"],
            start_azimuth=pass_dict.get("start_azimuth", 0),
            end_azimuth=pass_dict.get("end_azimuth", 0),
            pass_type=pass_dict.get("pass_type", "imaging"),
            geometry_aos=(
                PassGeometryResponse(**pass_dict["geometry_aos"])
                if pass_dict.get("geometry_aos")
                else None
            ),
            geometry_tca=(
                PassGeometryResponse(**pass_dict["geometry_tca"])
                if pass_dict.get("geometry_tca")
                else None
            ),
            geometry_los=(
                PassGeometryResponse(**pass_dict["geometry_los"])
                if pass_dict.get("geometry_los")
                else None
            ),
            lighting=(
                PassLightingResponse(**pass_dict["lighting"])
                if pass_dict.get("lighting")
                else None
            ),
            quality=(
                PassQualityResponse(**pass_dict["quality"])
                if pass_dict.get("quality")
                else None
            ),
            maneuver=(
                PassManeuverResponse(**pass_dict["maneuver"])
                if pass_dict.get("maneuver")
                else None
            ),
        )

    except Exception as e:
        logger.error(f"Pass enrichment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/analysis/passes/batch", tags=["Analysis"])
async def enrich_passes_batch(
    request: BatchPassEnrichmentRequest,
) -> List[Dict[str, Any]]:
    """
    Enrich multiple passes with STK-like metrics in batch.

    More efficient than calling /api/analysis/pass/enrich multiple times.
    """
    try:
        # Create satellite from TLE lines
        tle_lines = [
            request.satellite_tle.name,
            request.satellite_tle.line1,
            request.satellite_tle.line2,
        ]
        satellite = SatelliteOrbit(tle_lines, request.satellite_tle.name)
        vis_calc = VisibilityCalculator(satellite=satellite, use_adaptive=False)

        # Create targets dict for lookup
        targets_dict = {
            t.name: GroundTarget(
                name=t.name,
                latitude=t.latitude,
                longitude=t.longitude,
                description=t.description or "",
                mission_type="imaging",
            )
            for t in request.targets
        }

        enriched_passes = []

        for idx, pass_data in enumerate(request.passes):
            target_name: str = (
                pass_data.get("target") or pass_data.get("target_name") or ""
            )
            target = targets_dict.get(target_name)

            if not target or not target_name:
                enriched_passes.append(
                    pass_data
                )  # Return unchanged if target not found
                continue

            try:
                # Import PassDetails
                from mission_planner.visibility import PassDetails

                # Parse timestamps
                start_time = datetime.fromisoformat(
                    pass_data["start_time"].replace("Z", "+00:00")
                )
                end_time = datetime.fromisoformat(
                    pass_data["end_time"].replace("Z", "+00:00")
                )
                max_elev_time = datetime.fromisoformat(
                    pass_data["max_elevation_time"].replace("Z", "+00:00")
                )

                # Create PassDetails
                pass_details = PassDetails(
                    target_name=target_name,
                    satellite_name=pass_data.get(
                        "satellite_name", request.satellite_tle.name
                    ),
                    start_time=start_time.replace(tzinfo=None),
                    end_time=end_time.replace(tzinfo=None),
                    max_elevation_time=max_elev_time.replace(tzinfo=None),
                    max_elevation=pass_data.get("max_elevation", 0),
                    start_azimuth=pass_data.get("start_azimuth", 0),
                    max_elevation_azimuth=pass_data.get("max_elevation_azimuth", 0),
                    end_azimuth=pass_data.get("end_azimuth", 0),
                    pass_index=idx,
                )

                # Enrich
                vis_calc.enrich_pass_with_stk_data(
                    pass_details, target, request.max_roll_rate_dps
                )

                enriched_passes.append(pass_details.to_dict())

            except Exception as e:
                logger.warning(f"Failed to enrich pass {idx}: {e}")
                enriched_passes.append(pass_data)

        return enriched_passes

    except Exception as e:
        logger.error(f"Batch pass enrichment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analysis/quality/factors", tags=["Analysis"])
async def get_quality_factors() -> Dict[str, Any]:
    """
    Get documentation on quality scoring factors.

    Returns the factors and weights used in quality score calculation.
    """
    return {
        "description": "Quality score is computed from 0-100 based on multiple factors",
        "factors": {
            "elevation": {
                "description": "Higher elevation is better for imaging",
                "scoring": {
                    "< 10°": "-40 points, 'Very low elevation'",
                    "10-20°": "-25 points, 'Low elevation'",
                    "20-40°": "-10 points",
                    "40-70°": "0 points (baseline)",
                    "> 70°": "+5 points bonus",
                },
            },
            "incidence_angle": {
                "description": "Lower off-nadir angle is better for most applications",
                "scoring": {
                    "> 50°": "-30 points, 'High incidence angle'",
                    "40-50°": "-15 points",
                    "30-40°": "-5 points",
                    "< 30°": "0 points (optimal)",
                },
            },
            "lighting": {
                "description": "Target must be illuminated for optical imaging",
                "scoring": {
                    "not_sunlit (optical)": "-50 points, not feasible",
                    "sun_elevation < 15°": "-10 points, 'Low sun angle'",
                },
            },
            "duration": {
                "description": "Longer passes provide more imaging options",
                "scoring": {
                    "< 60s": "-20 points, 'Very short pass'",
                    "60-120s": "-10 points, 'Short pass'",
                    "> 300s": "+5 points bonus",
                },
            },
        },
        "score_range": {"min": 0, "max": 100},
    }


@app.get("/api/v1/tle/sources")
async def get_tle_sources() -> Dict[str, List[Dict[str, str]]]:
    """Get available TLE data sources from Celestrak"""
    sources = get_common_tle_sources()

    # Format for frontend dropdown
    formatted_sources = []
    for key, url in sources.items():
        # Convert key to readable name
        name = key.replace("celestrak_", "").replace("_", " ").title()
        formatted_sources.append(
            {
                "id": key,
                "name": f"Celestrak - {name}",
                "url": url,
                "description": f"Celestrak {name} satellites",
            }
        )

    return {"sources": formatted_sources}


@app.get("/api/v1/tle/catalog/{source_id}")
async def get_satellite_catalog(source_id: str) -> Dict[str, Any]:
    """Get satellite catalog from specified Celestrak source"""
    sources = get_common_tle_sources()

    if source_id not in sources:
        raise HTTPException(status_code=404, detail="TLE source not found")

    try:
        url = sources[source_id]
        logger.info(f"Fetching TLE data from: {url}")

        response = requests.get(url, timeout=30)
        response.raise_for_status()

        tle_data = response.text.strip()

        # Parse TLE data into satellite list
        satellites = []
        lines = tle_data.split("\n")

        for i in range(0, len(lines) - 2, 3):
            if i + 2 < len(lines):
                name = lines[i].strip()
                line1 = lines[i + 1].strip()
                line2 = lines[i + 2].strip()

                if name and line1.startswith("1 ") and line2.startswith("2 "):
                    satellites.append({"name": name, "line1": line1, "line2": line2})

        logger.info(f"Parsed {len(satellites)} satellites from {source_id}")

        return {"source": source_id, "count": len(satellites), "satellites": satellites}

    except requests.RequestException as e:
        logger.error(f"Failed to fetch TLE data from {url}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch TLE data: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error parsing TLE data: {e}")
        raise HTTPException(status_code=500, detail=f"Error parsing TLE data: {str(e)}")


@app.post("/api/v1/tle/search")
async def search_satellites(request: Dict[str, Any]) -> Dict[str, Any]:
    """Search for satellites by name across Celestrak sources"""
    search_term = request.get("query", "").lower()
    source_id = request.get("source", "celestrak_active")

    if not search_term:
        raise HTTPException(status_code=400, detail="Search query is required")

    try:
        # Get catalog from specified source
        catalog_response = await get_satellite_catalog(source_id)
        satellites = catalog_response["satellites"]

        # Filter satellites by search term
        matching_satellites = []
        for sat in satellites:
            if search_term in sat["name"].lower():
                matching_satellites.append(sat)

        return {
            "query": search_term,
            "source": source_id,
            "count": len(matching_satellites),
            "satellites": matching_satellites[:50],  # Limit to 50 results
        }

    except Exception as e:
        logger.error(f"Error searching satellites: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/api/v1/targets/parse")
async def parse_coordinate(request: CoordinateInput) -> Dict[str, Any]:
    """Parse coordinate string in various formats."""
    try:
        result = CoordinateParser.parse_coordinate_string(request.coordinate_string)

        if result:
            lat, lon = result
            return {
                "success": True,
                "latitude": lat,
                "longitude": lon,
                "original": request.coordinate_string,
            }
        else:
            return {
                "success": False,
                "error": "Could not parse coordinates. Please check format.",
                "original": request.coordinate_string,
            }
    except Exception as e:
        logger.error(f"Error parsing coordinate: {e}")
        return {
            "success": False,
            "error": str(e),
            "original": request.coordinate_string,
        }


@app.post("/api/v1/targets/upload")
async def upload_targets_file(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Upload and parse a file containing targets."""
    try:
        # Check file extension
        allowed_extensions = [".kml", ".kmz", ".json", ".csv", ".txt"]
        filename = file.filename or ""
        file_ext = os.path.splitext(filename)[1].lower()

        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}",
            )

        # Read file content
        content = await file.read()

        # Parse file
        try:
            targets = FileParser.parse_file(file.filename or "", content)
        except Exception as e:
            logger.error(f"Error parsing file {file.filename}: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to parse file: {str(e)}"
            )

        # Validate and deduplicate
        validated_targets = TargetValidator.validate_and_deduplicate(targets)

        # Convert to ParsedTarget format
        parsed_targets = [
            {
                "name": t["name"],
                "latitude": round(t["latitude"], 6),
                "longitude": round(t["longitude"], 6),
                "description": t.get("description", ""),
                "source": "file",
            }
            for t in validated_targets
        ]

        # Check if we found any targets
        if len(parsed_targets) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"No valid targets found in {file.filename}. Please check the file format and content.",
            )

        return {
            "success": True,
            "filename": file.filename,
            "total_found": len(targets),
            "valid_targets": len(parsed_targets),
            "targets": parsed_targets,
            "message": f"Successfully parsed {len(parsed_targets)} valid targets from {file.filename}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing uploaded file: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.post("/api/v1/targets/validate")
async def validate_targets(targets: List[TargetData]) -> Dict[str, Any]:
    """Validate a list of targets and check for duplicates."""
    try:
        # Convert to dict format for validator
        target_dicts = [
            {
                "name": t.name,
                "latitude": t.latitude,
                "longitude": t.longitude,
                "description": t.description or "",
            }
            for t in targets
        ]

        # Validate and deduplicate
        validated = TargetValidator.validate_and_deduplicate(target_dicts)

        # Convert back to TargetData format
        validated_targets = [
            {
                "name": t["name"],
                "latitude": t["latitude"],
                "longitude": t["longitude"],
                "description": t.get("description", ""),
            }
            for t in validated
        ]

        return {
            "success": True,
            "original_count": len(targets),
            "validated_count": len(validated_targets),
            "removed_duplicates": len(targets) - len(validated_targets),
            "targets": validated_targets,
        }

    except Exception as e:
        logger.error(f"Error validating targets: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error validating targets: {str(e)}"
        )


# Configuration Management Endpoints
@app.get("/api/v1/config/ground-stations")
async def get_ground_stations() -> Dict[str, Any]:
    """Get all configured ground stations"""
    try:
        stations = config_manager.get_ground_stations_list()
        return {"success": True, "ground_stations": stations, "count": len(stations)}
    except Exception as e:
        logger.error(f"Error getting ground stations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/config/ground-stations")
async def add_ground_station(station: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new ground station"""
    try:
        success = config_manager.add_ground_station(station)
        if success:
            return {"success": True, "message": "Ground station added successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to add ground station")
    except Exception as e:
        logger.error(f"Error adding ground station: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/config/ground-stations/{name}")
async def update_ground_station(name: str, station: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing ground station"""
    try:
        success = config_manager.update_ground_station(name, station)
        if success:
            return {"success": True, "message": "Ground station updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Ground station not found")
    except Exception as e:
        logger.error(f"Error updating ground station: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/config/ground-stations/{name}")
async def delete_ground_station(name: str) -> Dict[str, Any]:
    """Delete a ground station"""
    try:
        success = config_manager.delete_ground_station(name)
        if success:
            return {"success": True, "message": "Ground station deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Ground station not found")
    except Exception as e:
        logger.error(f"Error deleting ground station: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/config/full")
async def get_full_config() -> Dict[str, Any]:
    """Get the full configuration"""
    try:
        config = config_manager.to_dict()
        return {"success": True, "config": config}
    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/config/reload")
async def reload_configuration() -> Dict[str, Any]:
    """Reload configuration from file"""
    try:
        success = reload_config()
        if success:
            return {
                "success": True,
                "message": "Configuration reloaded successfully",
                "ground_stations_count": len(config_manager.ground_stations),
            }
        else:
            raise HTTPException(
                status_code=500, detail="Failed to reload configuration"
            )
    except Exception as e:
        logger.error(f"Error reloading configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/config/upload")
async def upload_config(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Upload a configuration file (YAML or JSON)"""
    try:
        # Check file extension
        config_filename = file.filename or ""
        file_ext = os.path.splitext(config_filename)[1].lower()
        if file_ext not in [".yaml", ".yml", ".json"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only YAML and JSON files are supported.",
            )

        # Read file content
        content = await file.read()

        # Parse based on file type
        if file_ext == ".json":
            config_data = json.loads(content)
        else:  # YAML
            config_data = yaml.safe_load(content)

        # Load configuration from parsed data
        success = config_manager.from_dict(config_data)

        if success:
            return {
                "success": True,
                "message": f"Configuration loaded from {file.filename}",
                "ground_stations_count": len(config_manager.ground_stations),
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to load configuration")

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
    except Exception as e:
        logger.error(f"Error uploading configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === SATELLITE MANAGEMENT ENDPOINTS ===


@app.get("/api/v1/satellites")
async def get_satellites() -> Dict[str, Any]:
    """Get all managed satellites"""
    try:
        satellites = satellite_manager.get_satellites()
        logger.info(f"Found {len(satellites)} satellites, converting to dict...")
        satellites_dict = []
        for sat in satellites:
            try:
                sat_dict = sat.to_dict()
                satellites_dict.append(sat_dict)
            except Exception as sat_error:
                logger.error(
                    f"Error converting satellite {sat.name} to dict: {sat_error}",
                    exc_info=True,
                )
                raise
        return {
            "success": True,
            "satellites": satellites_dict,
            "count": len(satellites_dict),
        }
    except Exception as e:
        logger.error(f"Error getting satellites: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/satellites/{satellite_id}")
async def get_satellite(satellite_id: str) -> Dict[str, Any]:
    """Get specific satellite by ID"""
    try:
        satellite = satellite_manager.get_satellite_by_id(satellite_id)
        if not satellite:
            raise HTTPException(status_code=404, detail="Satellite not found")

        return {"success": True, "satellite": satellite.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting satellite {satellite_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/satellites")
async def create_satellite(request: SatelliteCreateRequest) -> Dict[str, Any]:
    """Add new satellite to managed list"""
    try:
        satellite_data = request.dict()
        satellite = satellite_manager.add_satellite(satellite_data)

        return {
            "success": True,
            "message": f"Satellite '{satellite.name}' added successfully",
            "satellite": satellite.to_dict(),
        }
    except Exception as e:
        logger.error(f"Error creating satellite: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/satellites/{satellite_id}")
async def update_satellite(
    satellite_id: str, request: SatelliteUpdateRequest
) -> Dict[str, Any]:
    """Update existing satellite"""
    try:
        # Filter out None values
        updates = {k: v for k, v in request.dict().items() if v is not None}

        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        satellite = satellite_manager.update_satellite(satellite_id, updates)
        if not satellite:
            raise HTTPException(status_code=404, detail="Satellite not found")

        return {
            "success": True,
            "message": f"Satellite '{satellite.name}' updated successfully",
            "satellite": satellite.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating satellite {satellite_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/satellites/{satellite_id}")
async def delete_satellite(satellite_id: str) -> Dict[str, Any]:
    """Remove satellite from managed list"""
    try:
        success = satellite_manager.remove_satellite(satellite_id)
        if not success:
            raise HTTPException(status_code=404, detail="Satellite not found")

        return {"success": True, "message": "Satellite removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting satellite {satellite_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/satellites/config/full")
async def get_satellite_config() -> Dict[str, Any]:
    """Get full satellite configuration including defaults and mission settings"""
    try:
        return {"success": True, "config": satellite_manager.get_config_dict()}
    except Exception as e:
        logger.error(f"Error getting satellite config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/satellites/config/reload")
async def reload_satellite_config() -> Dict[str, Any]:
    """Reload satellite configuration from file"""
    try:
        success = satellite_manager.load_config()
        if success:
            satellites = satellite_manager.get_satellites()
            return {
                "success": True,
                "message": "Satellite configuration reloaded successfully",
                "satellites_count": len(satellites),
            }
        else:
            raise HTTPException(
                status_code=500, detail="Failed to reload satellite configuration"
            )
    except Exception as e:
        logger.error(f"Error reloading satellite configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/satellites/{satellite_id}/refresh-tle")
async def refresh_satellite_tle(
    satellite_id: str, source_url: Optional[str] = None
) -> Dict[str, Any]:
    """Refresh TLE data for a specific satellite"""
    try:
        satellite = satellite_manager.refresh_satellite_tle(
            satellite_id, source_url or ""
        )
        if not satellite:
            raise HTTPException(
                status_code=404, detail="Satellite not found or TLE refresh failed"
            )

        tle_age = satellite_manager.get_tle_age_days(satellite_id)

        return {
            "success": True,
            "message": f"TLE data refreshed for satellite '{satellite.name}'",
            "satellite": satellite.to_dict(),
            "tle_age_days": tle_age,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing TLE for satellite {satellite_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/satellites/{satellite_id}/tle-age")
async def get_satellite_tle_age(satellite_id: str) -> Dict[str, Any]:
    """Get the age of TLE data for a specific satellite"""
    try:
        tle_age = satellite_manager.get_tle_age_days(satellite_id)
        if tle_age is None:
            raise HTTPException(
                status_code=404, detail="Satellite not found or no TLE data"
            )

        satellite = satellite_manager.get_satellite_by_id(satellite_id)

        return {
            "success": True,
            "satellite_id": satellite_id,
            "satellite_name": satellite.name if satellite else "Unknown",
            "tle_age_days": tle_age,
            "tle_updated_at": satellite.tle_updated_at if satellite else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting TLE age for satellite {satellite_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Mission Settings API Endpoints


@app.get("/api/v1/mission-settings")
async def get_mission_settings() -> Dict[str, Any]:
    """Get all mission settings"""
    try:
        return {"success": True, "settings": mission_settings_manager.get_config_dict()}
    except Exception as e:
        logger.error(f"Error getting mission settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/mission-settings/{section}/{key}")
async def update_mission_setting(
    section: str, key: str, value: Dict[str, Any]
) -> Dict[str, Any]:
    """Update a specific mission setting"""
    try:
        # Log the update request
        logger.info(
            f"Updating setting {section}.{key} with value: {value.get('value')}"
        )
        success = mission_settings_manager.update_setting(
            section, key, value.get("value")
        )
        if not success:
            logger.warning(f"Failed to update setting {section}.{key}")
            raise HTTPException(
                status_code=400, detail=f"Failed to update setting {section}.{key}"
            )

        return {"success": True, "message": f"Updated {section}.{key} successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating mission setting {section}.{key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/config/mission-settings")
async def save_mission_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Save mission settings to file"""
    try:
        # Update the mission settings by updating each section
        for section, values in settings.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    mission_settings_manager.update_setting(section, key, value)

        # Save to file
        success = mission_settings_manager.save_config()

        if success:
            return {"success": True, "message": "Mission settings saved successfully"}
        else:
            raise HTTPException(
                status_code=500, detail="Failed to save mission settings"
            )
    except Exception as e:
        logger.error(f"Error saving mission settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/mission-settings/reload")
async def reload_mission_settings() -> Dict[str, Any]:
    """Reload mission settings from file"""
    try:
        success = mission_settings_manager.load_config()
        if success:
            return {
                "success": True,
                "message": "Mission settings reloaded successfully",
            }
        else:
            raise HTTPException(
                status_code=500, detail="Failed to reload mission settings"
            )
    except Exception as e:
        logger.error(f"Error reloading mission settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === MISSION PLANNING ENDPOINTS (Algorithm Suite) ===


@app.get("/api/v1/planning/weight-presets")
async def get_weight_presets() -> Dict[str, Any]:
    """Get available weight presets for multi-criteria scoring."""
    presets = {}
    for name, weights in WEIGHT_PRESETS.items():
        presets[name] = {
            "raw": weights.to_dict(),
            "normalized": weights.normalized_dict(),
            "description": {
                "balanced": "Equal priority and geometry, with timing consideration",
                "priority_first": "Prioritize high-importance targets",
                "quality_first": "Prioritize best imaging geometry",
                "urgent": "Time-sensitive: prioritize early opportunities",
                "archival": "Quality archival: prioritize best geometry",
            }.get(name, ""),
        }
    return {"presets": presets}


def _compute_incidence_angle_at_time(
    satellite: SatelliteOrbit,
    target_lat: float,
    target_lon: float,
    timestamp: datetime,
    vel_lat_norm: Optional[float] = None,
    vel_lon_norm: Optional[float] = None,
) -> float:
    """
    Compute the SIGNED incidence (roll) angle from satellite to target at a specific time.

    This is critical for accurate maneuver calculations - the angle must be computed
    at the actual imaging time, not at pass start.

    Args:
        satellite: SatelliteOrbit object for position lookup
        target_lat: Target latitude in degrees
        target_lon: Target longitude in degrees
        timestamp: Specific time to compute the angle
        vel_lat_norm: Pre-computed normalized velocity lat (optional, saves 1 propagation call)
        vel_lon_norm: Pre-computed normalized velocity lon (optional)

    Returns:
        Signed incidence angle in degrees (positive = right of track, negative = left)
    """
    # Get satellite position at this specific time
    sat_lat, sat_lon, sat_alt = satellite.get_position(timestamp)

    # Use pre-computed velocity direction if provided (avoids extra propagation call)
    _vlat_n: float = 1.0
    _vlon_n: float = 0.0
    if vel_lat_norm is not None and vel_lon_norm is not None:
        _vlat_n = vel_lat_norm
        _vlon_n = vel_lon_norm
    else:
        sat_lat_future, sat_lon_future, _ = satellite.get_position(
            timestamp + timedelta(seconds=1)
        )
        vel_lat = sat_lat_future - sat_lat
        vel_lon = sat_lon_future - sat_lon
        vel_mag = math.sqrt(vel_lat**2 + vel_lon**2)
        if vel_mag > 0:
            _vlat_n = vel_lat / vel_mag
            _vlon_n = vel_lon / vel_mag
        else:
            _vlat_n = 1.0
            _vlon_n = 0.0

    # Calculate look angle magnitude (off-nadir angle)
    # Using spherical geometry
    earth_radius_km = 6371.0
    sat_height_km = sat_alt

    # Convert to radians
    sat_lat_rad = math.radians(sat_lat)
    sat_lon_rad = math.radians(sat_lon)
    target_lat_rad = math.radians(target_lat)
    target_lon_rad = math.radians(target_lon)

    # Angular distance on Earth's surface (haversine)
    dlat = target_lat_rad - sat_lat_rad
    dlon = target_lon_rad - sat_lon_rad
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(sat_lat_rad) * math.cos(target_lat_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    ground_distance_km = earth_radius_km * c

    # Look angle from nadir using geometry
    # tan(look_angle) = ground_distance / satellite_height (simplified)
    if sat_height_km > 0:
        look_angle_rad = math.atan2(ground_distance_km, sat_height_km)
        look_angle_deg = math.degrees(look_angle_rad)
    else:
        look_angle_deg = 0.0

    # Determine sign using cross-track calculation
    target_vec_lat = target_lat - sat_lat
    target_vec_lon = target_lon - sat_lon
    cross_track = target_vec_lon * _vlat_n - target_vec_lat * _vlon_n

    # Apply sign based on which side of ground track
    # Positive cross_track = target to left when looking along velocity
    if cross_track >= 0:
        signed_angle = -look_angle_deg  # Left of track = negative
    else:
        signed_angle = look_angle_deg  # Right of track = positive

    return signed_angle


@app.post("/api/v1/planning/schedule")
def schedule_mission(request: PlanningRequest) -> PlanningResponse:
    """
    Run mission planning algorithms on opportunities from last mission analysis.

    Applies satellite agility constraints and returns schedules + metrics
    for selected algorithms.
    """
    import time as _time

    t0 = _time.perf_counter()
    try:
        _cmd = getattr(app.state, "current_mission_data", {})

        if not _cmd or "passes" not in _cmd:
            raise HTTPException(
                status_code=400,
                detail="No mission analysis available. Run mission analysis first.",
            )

        passes = _cmd["passes"]
        targets = _cmd["targets"]
        mission_data = _cmd["mission_data"]
        satellite = _cmd.get("satellite")  # Primary satellite (legacy)
        satellites_dict = _cmd.get(
            "satellites_dict", {}
        )  # All satellites for constellation

        if getattr(request, "workspace_id", None):
            update_log_context(workspace_id=request.workspace_id)

        logger.debug(
            "Planning context: satellite_available=%s constellation_satellites=%d satellite_type=%s",
            satellite is not None,
            len(satellites_dict),
            type(satellite).__name__ if satellite else None,
        )

        if not passes:
            return PlanningResponse(
                success=False, message="No opportunities available for planning"
            )

        # Build target positions map and priority map
        target_positions = {
            target.name: (target.latitude, target.longitude) for target in targets
        }
        target_priorities = {
            target.name: getattr(target, "priority", 5) for target in targets
        }
        logger.debug("Target priorities: %s", target_priorities)

        # Get max spacecraft pitch from mission analysis (needed for pitch calculation)
        max_spacecraft_pitch_for_opps = mission_data.get("max_spacecraft_pitch_deg")
        if max_spacecraft_pitch_for_opps is None:
            max_spacecraft_pitch_for_opps = 45.0  # Default if not set
        logger.debug(
            "Using max_spacecraft_pitch_deg=%s° for opportunity generation",
            max_spacecraft_pitch_for_opps,
        )

        # Convert passes to opportunities with quality scoring
        opportunities = []
        quality_model_enum = QualityModel(request.quality_model.lower())

        # Setup multi-criteria weights
        if request.weight_preset and request.weight_preset in WEIGHT_PRESETS:
            # Use preset
            multi_weights = WEIGHT_PRESETS[request.weight_preset]
            logger.info(
                f"Using weight preset: {request.weight_preset} -> {multi_weights.normalized_dict()}"
            )
        else:
            # Use custom weights from request
            multi_weights = MultiCriteriaWeights(
                priority=request.weight_priority,
                geometry=request.weight_geometry,
                timing=request.weight_timing,
            )
            logger.info(f"Using custom weights: {multi_weights.normalized_dict()}")

        # Count total opportunities for timing score (estimated)
        total_opp_estimate = len(passes) * 50  # Rough estimate
        opp_index = 0

        logger.info("Processing %d passes to create opportunities", len(passes))
        for idx, pass_detail in enumerate(passes):
            # PassDetails may be objects or dicts (from serialization)
            # Handle both cases for robust access
            if isinstance(pass_detail, dict):
                sat_name = pass_detail["satellite_name"]
                target_name = pass_detail["target_name"]
                start_time = datetime.fromisoformat(pass_detail["start_time"])
                end_time = datetime.fromisoformat(pass_detail["end_time"])
                max_elevation_time = datetime.fromisoformat(
                    pass_detail["max_elevation_time"]
                )
                max_elevation = pass_detail["max_elevation"]
                start_azimuth = pass_detail["start_azimuth"]
                incidence_angle_deg = pass_detail.get("incidence_angle_deg")
                mode = pass_detail.get("mode", "OPTICAL")
                # Extract SAR data if present (from dict)
                sar_data_dict = pass_detail.get("sar_data")
            else:
                sat_name = pass_detail.satellite_name
                target_name = pass_detail.target_name
                start_time = pass_detail.start_time
                end_time = pass_detail.end_time
                max_elevation_time = pass_detail.max_elevation_time
                max_elevation = pass_detail.max_elevation
                start_azimuth = pass_detail.start_azimuth
                incidence_angle_deg = getattr(pass_detail, "incidence_angle_deg", None)
                mode = getattr(pass_detail, "mode", "OPTICAL")
                # Extract SAR data if present (from object)
                sar_data_dict = None
                if hasattr(pass_detail, "sar_data") and pass_detail.sar_data:
                    sar_obj = pass_detail.sar_data
                    sar_data_dict = {
                        "look_side": (
                            sar_obj.look_side.value
                            if hasattr(sar_obj.look_side, "value")
                            else sar_obj.look_side
                        ),
                        "pass_direction": (
                            sar_obj.pass_direction.value
                            if hasattr(sar_obj.pass_direction, "value")
                            else sar_obj.pass_direction
                        ),
                        "imaging_mode": (
                            sar_obj.imaging_mode.value
                            if hasattr(sar_obj.imaging_mode, "value")
                            else sar_obj.imaging_mode
                        ),
                        "incidence_center_deg": sar_obj.incidence_center_deg,
                        "incidence_near_deg": getattr(
                            sar_obj, "incidence_near_deg", None
                        ),
                        "incidence_far_deg": getattr(
                            sar_obj, "incidence_far_deg", None
                        ),
                        "swath_width_km": sar_obj.swath_width_km,
                        "scene_length_km": sar_obj.scene_length_km,
                        "quality_score": sar_obj.quality_score,
                    }

            # Log each pass being processed (debug-level to avoid I/O overhead)
            logger.debug(
                f"Pass {idx+1}: {target_name} mode={mode} inc={incidence_angle_deg} t={max_elevation_time}"
            )

            # For IMAGING missions: Create multiple opportunities across ENTIRE pass duration
            # with 1-second sampling for truly continuous pitch coverage
            if mode == "IMAGING":
                # Calculate pass duration
                pass_duration_s = (end_time - start_time).total_seconds()

                # 5-second sampling for good pitch coverage without overwhelming the scheduler
                # (1s was causing ~4000+ opportunities with O(n²) scheduling, leading to timeouts)
                SAMPLE_INTERVAL_S = 5.0
                num_samples = max(3, int(pass_duration_s / SAMPLE_INTERVAL_S))

                # Cap at 36 opportunities per pass (3 minutes / 5s = 36)
                num_samples = max(3, min(36, num_samples))

                imaging_times = []

                # Sample uniformly across the pass duration
                for i in range(num_samples):
                    # Calculate fraction through the pass (0.0 = start, 0.5 = middle, 1.0 = end)
                    fraction = i / (num_samples - 1) if num_samples > 1 else 0.5

                    # Calculate actual imaging time within the pass
                    imaging_time = start_time + timedelta(
                        seconds=pass_duration_s * fraction
                    )

                    # Calculate time offset from max elevation (for pitch calculation)
                    time_offset = (imaging_time - max_elevation_time).total_seconds()

                    # Calculate dynamic pitch based on orbital mechanics
                    # Use larger threshold (5 seconds) to ensure we get true pitch=0 opportunities for roll-only
                    if abs(time_offset) < 5.0:
                        pitch_angle = 0.0
                    else:
                        # Orbital velocity at typical altitude (~600km)
                        GM = 3.986004418e5  # km³/s²
                        earth_radius_km = 6371.0
                        sat_altitude_km = 590.0  # Approximate for ICEYE-X44
                        orbital_radius_km = earth_radius_km + sat_altitude_km
                        orbital_velocity_km_s = (GM / orbital_radius_km) ** 0.5

                        # Along-track distance
                        along_track_distance_km = orbital_velocity_km_s * abs(
                            time_offset
                        )

                        # Pitch angle from geometry
                        pitch_rad = math.atan2(along_track_distance_km, sat_altitude_km)
                        pitch_deg = math.degrees(pitch_rad)

                        # Apply sign and clamp to mission's max pitch capability
                        if time_offset < 0:
                            pitch_deg = -pitch_deg
                        pitch_angle = max(
                            -max_spacecraft_pitch_for_opps,
                            min(max_spacecraft_pitch_for_opps, pitch_deg),
                        )

                    # Generate meaningful ID suffix
                    if abs(time_offset) < 5:
                        time_type = "max"
                    elif time_offset < 0:
                        time_type = f"early_{abs(int(time_offset))}"
                    else:
                        time_type = f"late_{int(time_offset)}"

                    imaging_times.append((time_type, imaging_time, pitch_angle))

                logger.debug(
                    f"IMAGING mode for {target_name}: created {len(imaging_times)} opportunities "
                    f"across {pass_duration_s:.0f}s pass"
                )
            else:
                # Non-imaging: single opportunity for the entire window
                imaging_times = [("full", start_time, 0.0)]
                logger.debug(
                    f"NON-IMAGING mode for {target_name}: mode={mode}, using full window"
                )

            # Get target coordinates for incidence angle calculation
            target_coords = target_positions.get(target_name)

            # Get satellite object for this specific satellite (for dynamic angle computation)
            sat_key = f"sat_{sat_name}"
            sat_obj_for_angle = satellites_dict.get(sat_key)

            # PERF: Precompute velocity direction once per pass (at max_elevation_time).
            # Velocity barely changes within a single pass, so reuse for all opportunities.
            pass_vel_lat_norm, pass_vel_lon_norm = None, None
            if sat_obj_for_angle:
                try:
                    _p0_lat, _p0_lon, _ = sat_obj_for_angle.get_position(
                        max_elevation_time
                    )
                    _p1_lat, _p1_lon, _ = sat_obj_for_angle.get_position(
                        max_elevation_time + timedelta(seconds=1)
                    )
                    _vlat = _p1_lat - _p0_lat
                    _vlon = _p1_lon - _p0_lon
                    _vmag = math.sqrt(_vlat**2 + _vlon**2)
                    if _vmag > 0:
                        pass_vel_lat_norm = _vlat / _vmag
                        pass_vel_lon_norm = _vlon / _vmag
                except Exception:
                    pass  # fallback: computed per-opportunity inside the function

            # Create one opportunity for each imaging time (early/max/late)
            for time_type, imaging_time, pitch_angle in imaging_times:
                # Generate unique opportunity ID including time type
                opp_id = f"{sat_name}_{target_name}_{idx}_{time_type}"

                # CRITICAL FIX: Compute incidence angle at THIS SPECIFIC imaging_time
                # Previously used stale angle from pass start - caused wrong roll values!
                if sat_obj_for_angle and target_coords:
                    try:
                        actual_incidence_angle = _compute_incidence_angle_at_time(
                            sat_obj_for_angle,
                            target_coords[0],  # latitude
                            target_coords[1],  # longitude
                            imaging_time,
                            vel_lat_norm=pass_vel_lat_norm,
                            vel_lon_norm=pass_vel_lon_norm,
                        )
                    except Exception as e:
                        logger.warning(
                            f"Could not compute incidence angle at imaging time: {e}"
                        )
                        actual_incidence_angle = (
                            incidence_angle_deg
                            if incidence_angle_deg is not None
                            else 0.0
                        )  # Fallback
                else:
                    actual_incidence_angle = (
                        incidence_angle_deg
                        if incidence_angle_deg is not None
                        else 0.0  # Fallback if no satellite object
                    )

                # Get base priority/value
                if request.value_source == "custom" and request.custom_values:
                    base_priority = request.custom_values.get(opp_id, 5.0)
                elif request.value_source == "target_priority":
                    # Use target priority from target data (1-5)
                    base_priority = float(target_priorities.get(target_name, 5))
                else:
                    base_priority = 5.0  # Uniform (default=5, lowest priority)

                # Compute quality score from incidence angle (using ACTUAL angle at imaging time)
                quality_score = compute_quality_score(
                    incidence_angle_deg=actual_incidence_angle,
                    mode=mode,
                    quality_model=quality_model_enum,
                    ideal_incidence_deg=request.ideal_incidence_deg,
                    band_width_deg=request.band_width_deg,
                )

                # Compute timing score (earlier = higher)
                timing_score = compute_timing_score(opp_index, total_opp_estimate)
                opp_index += 1

                # Compute composite value using multi-criteria weights
                value = compute_composite_value(
                    priority=base_priority,
                    quality_score=quality_score,
                    timing_score=timing_score,
                    weights=multi_weights,
                )

                opp = Opportunity(
                    id=opp_id,
                    satellite_id=sat_name,
                    target_id=target_name,
                    start_time=imaging_time,
                    end_time=imaging_time,  # Single point in time
                    max_elevation=max_elevation,
                    azimuth=start_azimuth,
                    value=value,
                    incidence_angle=actual_incidence_angle,  # FIXED: Use angle at imaging time
                    pitch_angle=pitch_angle,  # NEW: forward/backward looking angle
                    # SAR-specific fields (threaded from pass sar_data)
                    mission_mode="SAR" if sar_data_dict else "OPTICAL",
                    sar_mode=(
                        sar_data_dict.get("imaging_mode") if sar_data_dict else None
                    ),
                    look_side=sar_data_dict.get("look_side") if sar_data_dict else None,
                    pass_direction=(
                        sar_data_dict.get("pass_direction") if sar_data_dict else None
                    ),
                    incidence_center_deg=(
                        sar_data_dict.get("incidence_center_deg")
                        if sar_data_dict
                        else None
                    ),
                    incidence_near_deg=(
                        sar_data_dict.get("incidence_near_deg")
                        if sar_data_dict
                        else None
                    ),
                    incidence_far_deg=(
                        sar_data_dict.get("incidence_far_deg")
                        if sar_data_dict
                        else None
                    ),
                    swath_width_km=(
                        sar_data_dict.get("swath_width_km") if sar_data_dict else None
                    ),
                    scene_length_km=(
                        sar_data_dict.get("scene_length_km") if sar_data_dict else None
                    ),
                    sar_quality_score=(
                        sar_data_dict.get("quality_score") if sar_data_dict else None
                    ),
                )
                opportunities.append(opp)

        t1 = _time.perf_counter()
        logger.info(
            "Opportunity generation: %.2fs (%d opportunities from %d passes)",
            t1 - t0,
            len(opportunities),
            len(passes),
        )

        # Cache opportunities for /api/v1/schedule/plan and /repair endpoints
        opp_dicts = []
        for opp in opportunities:
            opp_dict = {
                "id": opp.id,
                "opportunity_id": opp.id,
                "satellite_id": opp.satellite_id,
                "target_id": opp.target_id,
                "start_time": (
                    opp.start_time.isoformat()
                    if hasattr(opp.start_time, "isoformat")
                    else str(opp.start_time)
                ),
                "end_time": (
                    opp.end_time.isoformat()
                    if hasattr(opp.end_time, "isoformat")
                    else str(opp.end_time)
                ),
                "roll_angle_deg": (
                    getattr(opp, "incidence_angle", None)
                    if getattr(opp, "incidence_angle", None) is not None
                    else getattr(opp, "roll_angle_deg", 0.0)
                ),
                "pitch_angle_deg": (
                    getattr(opp, "pitch_angle", None)
                    if getattr(opp, "pitch_angle", None) is not None
                    else getattr(opp, "pitch_angle_deg", 0.0)
                ),
                "value": getattr(opp, "value", 1.0),
                "incidence_angle_deg": (
                    getattr(opp, "incidence_angle", None)
                    if getattr(opp, "incidence_angle", None) is not None
                    else getattr(opp, "incidence_angle_deg", None)
                ),
                "quality_score": getattr(opp, "quality_score", None),
                "priority": getattr(opp, "priority", 1),
            }
            opp_dicts.append(opp_dict)
        set_cached_opportunities(opp_dicts)
        logger.debug(
            "Cached %d opportunities for /plan and /repair endpoints",
            len(opp_dicts),
        )

        logger.info(
            "Weights: priority=%.0f%% geometry=%.0f%% timing=%.0f%% (preset=%s)",
            multi_weights.norm_priority * 100,
            multi_weights.norm_geometry * 100,
            multi_weights.norm_timing * 100,
            request.weight_preset,
        )

        # =====================================================================
        # INCREMENTAL MODE: Filter out opportunities that conflict with
        # committed acquisitions (blocked intervals per satellite)
        # =====================================================================
        blocked_intervals_by_satellite: Dict[str, List[tuple]] = {}

        if request.mode == "incremental":
            logger.info(f"[INCREMENTAL MODE] Loading committed acquisitions...")

            # Get time window from mission data
            mission_start = mission_data.get("start_time")
            mission_end = mission_data.get("end_time")

            if mission_start and mission_end:
                schedule_db = get_schedule_db()

                # Get all committed/locked acquisitions in this time window
                for sat_name in set(opp.satellite_id for opp in opportunities):
                    committed = schedule_db.get_committed_acquisitions_for_satellite(
                        satellite_id=sat_name,
                        start_time=mission_start,
                        end_time=mission_end,
                        workspace_id=request.workspace_id,
                    )

                    if committed:
                        blocked_intervals_by_satellite[sat_name] = [
                            (acq.start_time, acq.end_time) for acq in committed
                        ]
                        logger.debug(
                            "[INCREMENTAL MODE] Satellite %s: %d committed acquisitions",
                            sat_name,
                            len(committed),
                        )

                # Filter opportunities that overlap with blocked intervals
                original_count = len(opportunities)
                filtered_opportunities = []

                for opp in opportunities:
                    blocked = blocked_intervals_by_satellite.get(opp.satellite_id, [])
                    is_blocked = False

                    # Check if this opportunity overlaps any blocked interval
                    opp_start = (
                        opp.start_time.isoformat()
                        if hasattr(opp.start_time, "isoformat")
                        else str(opp.start_time)
                    )
                    opp_end = (
                        opp.end_time.isoformat()
                        if hasattr(opp.end_time, "isoformat")
                        else str(opp.end_time)
                    )

                    for block_start, block_end in blocked:
                        # Overlap check: opp_start < block_end AND opp_end > block_start
                        if opp_start < block_end and opp_end > block_start:
                            is_blocked = True
                            break

                    if not is_blocked:
                        filtered_opportunities.append(opp)

                opportunities = filtered_opportunities
                removed_count = original_count - len(opportunities)

                if removed_count > 0:
                    logger.info(
                        f"[INCREMENTAL MODE] Filtered out {removed_count} opportunities "
                        f"that conflict with committed acquisitions. "
                        f"Remaining: {len(opportunities)}"
                    )
                else:
                    logger.info(
                        f"[INCREMENTAL MODE] No conflicts found. All {len(opportunities)} "
                        f"opportunities available for planning."
                    )
            else:
                logger.warning(
                    "[INCREMENTAL MODE] Could not determine mission time window. "
                    "Falling back to from_scratch mode."
                )
        else:
            logger.info("[FROM_SCRATCH MODE] Ignoring existing acquisitions")

        # Store all opportunities for all algorithms
        all_opportunities = opportunities.copy()

        # Get max spacecraft roll from mission analysis
        max_spacecraft_roll = mission_data.get("max_spacecraft_roll_deg")
        if max_spacecraft_roll is None:
            max_spacecraft_roll = 45.0  # Default if not set
        # Get max spacecraft pitch from mission analysis (for 2D slew capability!)
        max_spacecraft_pitch = mission_data.get("max_spacecraft_pitch_deg")
        if max_spacecraft_pitch is None:
            max_spacecraft_pitch = 45.0  # Default if not set

        # Get satellite agility from mission analysis config
        _sat_agility = mission_data.get("satellite_agility", request.max_roll_rate_dps)
        _agility_source = (
            "config" if "satellite_agility" in mission_data else "request default"
        )
        logger.info(
            "[Plan] Scheduler limits: roll=%s° pitch=%s° agility=%s°/s (%s)",
            max_spacecraft_roll,
            max_spacecraft_pitch,
            _sat_agility,
            _agility_source,
        )

        # Create scheduler config
        config = SchedulerConfig(
            imaging_time_s=request.imaging_time_s,
            max_spacecraft_roll_deg=max_spacecraft_roll,  # Use max_spacecraft_roll from mission analysis
            max_roll_rate_dps=_sat_agility,
            max_roll_accel_dps2=request.max_roll_accel_dps2,
            max_spacecraft_pitch_deg=max_spacecraft_pitch,  # Use pitch from mission analysis
            max_pitch_rate_dps=request.max_pitch_rate_dps,
            max_pitch_accel_dps2=request.max_pitch_accel_dps2,
            look_window_s=request.look_window_s,
            value_source=request.value_source,
            default_value=1.0,
        )

        # Create scheduler with satellite objects for constellation scheduling
        scheduler = MissionScheduler(
            config, satellite=satellite, satellites=satellites_dict
        )
        logger.debug(
            "Scheduler initialized with %d satellites for constellation",
            len(satellites_dict),
        )

        # Get unique targets for coverage statistics
        all_targets = set(opp.target_id for opp in all_opportunities)
        total_targets = len(all_targets)

        logger.info(
            "Planning input: unique_targets=%d opportunities=%d",
            total_targets,
            len(all_opportunities),
        )

        # Run scheduling with roll_pitch_best_fit (the only active algorithm)
        # Other algorithms are deprecated but code is kept for reference
        results = {}

        # Always use roll_pitch_best_fit regardless of request.algorithms
        # This is the best algorithm combining global best geometry with 2D slew
        algo = AlgorithmType.ROLL_PITCH_BEST_FIT
        algo_name = "roll_pitch_best_fit"
        algo_opportunities = all_opportunities
        logger.info(
            "roll_pitch_best_fit using %d opportunities (2D slew, global best geometry)",
            len(algo_opportunities),
        )

        # Log deprecation warning if other algorithms were requested
        deprecated_algos = [a for a in request.algorithms if a != "roll_pitch_best_fit"]
        if deprecated_algos:
            logger.warning(
                f"DEPRECATED: Algorithms {deprecated_algos} are deprecated. Using roll_pitch_best_fit instead."
            )

        try:
            # Run scheduling with appropriate opportunity set
            t2 = _time.perf_counter()
            schedule, metrics = scheduler.schedule(
                algo_opportunities, target_positions, algo
            )
            t3 = _time.perf_counter()
            logger.info(
                "Scheduling algorithm: %.2fs (%d accepted from %d opportunities)",
                t3 - t2,
                len(schedule),
                len(algo_opportunities),
            )

            # Compute target-level statistics
            acquired_targets = set(s.target_id for s in schedule)
            missing_targets = all_targets - acquired_targets
            target_coverage_pct = (
                (len(acquired_targets) / total_targets * 100)
                if total_targets > 0
                else 0.0
            )

            # Calculate angle statistics for API response
            # For roll+pitch, off-nadir is the vector magnitude: sqrt(roll² + pitch²)
            off_nadir_angles = []
            for s in schedule:
                roll = abs(s.roll_angle) if s.roll_angle is not None else 0.0
                pitch = abs(s.pitch_angle) if s.pitch_angle is not None else 0.0
                off_nadir = math.sqrt(roll**2 + pitch**2)
                off_nadir_angles.append(off_nadir)

            avg_incidence_temp = (
                sum(off_nadir_angles) / len(off_nadir_angles)
                if off_nadir_angles
                else 0.0
            )
            avg_roll_temp = (
                sum(abs(s.roll_angle) for s in schedule if s.roll_angle is not None)
                / len(schedule)
                if schedule
                else 0.0
            )
            avg_pitch_temp = (
                sum(abs(s.pitch_angle) for s in schedule if s.pitch_angle is not None)
                / len(schedule)
                if schedule
                else 0.0
            )

            # Build planner_summary for intelligent UI narrative
            _ps_target_acqs = []
            _ps_satellites_used = set()
            for s in schedule:
                _ps_satellites_used.add(s.satellite_id)
                _ps_target_acqs.append(
                    {
                        "target_id": s.target_id,
                        "satellite_id": s.satellite_id,
                        "start_time": (
                            s.start_time.isoformat()
                            if hasattr(s.start_time, "isoformat")
                            else str(s.start_time)
                        ),
                        "end_time": (
                            s.end_time.isoformat()
                            if hasattr(s.end_time, "isoformat")
                            else str(s.end_time)
                        ),
                        "action": "added",
                    }
                )
            _ps_not_scheduled = []
            for tid in sorted(missing_targets):
                _ps_not_scheduled.append(
                    {
                        "target_id": tid,
                        "reason": "No feasible slot within planning constraints",
                    }
                )
            _horizon_start = mission_data.get("start_time", "")
            _horizon_end = mission_data.get("end_time", "")

            # Package results with target-level info and angle statistics
            results[algo_name] = {
                "schedule": [s.to_dict() for s in schedule],
                "metrics": metrics.to_dict(),
                "target_statistics": {
                    "total_targets": total_targets,
                    "targets_acquired": len(acquired_targets),
                    "targets_missing": len(missing_targets),
                    "coverage_percentage": round(target_coverage_pct, 1),
                    "acquired_target_ids": sorted(list(acquired_targets)),
                    "missing_target_ids": sorted(list(missing_targets)),
                },
                "angle_statistics": {
                    "avg_off_nadir_deg": round(avg_incidence_temp, 2),
                    "avg_cross_track_deg": round(avg_roll_temp, 2),
                    "avg_along_track_deg": round(avg_pitch_temp, 2),
                },
                "planner_summary": {
                    "target_acquisitions": _ps_target_acqs,
                    "targets_not_scheduled": _ps_not_scheduled,
                    "horizon": {
                        "start": (
                            _horizon_start
                            if isinstance(_horizon_start, str)
                            else (
                                _horizon_start.isoformat()
                                if hasattr(_horizon_start, "isoformat")
                                else str(_horizon_start)
                            )
                        ),
                        "end": (
                            _horizon_end
                            if isinstance(_horizon_end, str)
                            else (
                                _horizon_end.isoformat()
                                if hasattr(_horizon_end, "isoformat")
                                else str(_horizon_end)
                            )
                        ),
                    },
                    "satellites_used": sorted(_ps_satellites_used),
                    "total_targets_with_opportunities": total_targets,
                    "total_targets_covered": len(acquired_targets),
                },
            }

            # Calculate summary statistics
            # Off-nadir angle is vector magnitude: sqrt(roll² + pitch²)
            off_nadir_summary = []
            for s in schedule:
                roll = abs(s.roll_angle) if s.roll_angle is not None else 0.0
                pitch = abs(s.pitch_angle) if s.pitch_angle is not None else 0.0
                off_nadir_summary.append(math.sqrt(roll**2 + pitch**2))

            avg_incidence = (
                sum(off_nadir_summary) / len(off_nadir_summary)
                if off_nadir_summary
                else 0.0
            )
            valid_densities = [
                s.density
                for s in schedule
                if s.density is not None and s.density != float("inf")
            ]
            avg_density = (
                sum(valid_densities) / len(valid_densities) if valid_densities else 0.0
            )
            total_value = sum(s.value for s in schedule if s.value is not None)
            total_maneuver = sum(
                s.maneuver_time for s in schedule if s.maneuver_time is not None
            )
            total_slack = sum(
                s.slack_time for s in schedule if s.slack_time is not None
            )

            # Calculate angle statistics (optical imaging terminology)
            avg_roll = (
                sum(abs(s.roll_angle) for s in schedule if s.roll_angle is not None)
                / len(schedule)
                if schedule
                else 0.0
            )
            avg_pitch = (
                sum(abs(s.pitch_angle) for s in schedule if s.pitch_angle is not None)
                / len(schedule)
                if schedule
                else 0.0
            )
            total_pitch = sum(
                abs(s.pitch_angle) for s in schedule if s.pitch_angle is not None
            )
            max_pitch = max(
                (abs(s.pitch_angle) for s in schedule if s.pitch_angle is not None),
                default=0.0,
            )

            # Log comprehensive summary
            logger.info(
                "[%s] coverage=%d/%d (%.1f%%) avg_off_nadir=%.2f° avg_roll=%.2f° avg_pitch=%.2f° maneuver=%.1fs slack=%.1fs value=%.1f density=%.2f runtime=%.2fms",
                algo_name.upper(),
                len(acquired_targets),
                total_targets,
                target_coverage_pct,
                avg_incidence,
                avg_roll,
                avg_pitch,
                total_maneuver,
                total_slack,
                total_value,
                avg_density,
                metrics.runtime_ms,
            )
            if max_pitch > 0:
                logger.debug(
                    "[%s] pitch totals: total=%.2f° max=%.2f°",
                    algo_name.upper(),
                    total_pitch,
                    max_pitch,
                )

        except Exception as e:
            logger.error(f"Error running {algo_name}: {e}")
            results[algo_name] = {
                "error": str(e),
                "schedule": [],
                "metrics": {},
                "target_statistics": {
                    "total_targets": total_targets,
                    "targets_acquired": 0,
                    "targets_missing": total_targets,
                    "coverage_percentage": 0.0,
                    "acquired_target_ids": [],
                    "missing_target_ids": sorted(list(all_targets)),
                },
            }

        # Compute audit metadata for instrumentation
        run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_uuid = str(uuid.uuid4())[:8]
        run_id = f"run_{run_timestamp}_{run_uuid}"
        candidate_plan_id = f"plan_temp_{run_uuid}"
        update_log_context(run_id=run_id)

        # Compute input hash for reproducibility
        input_data = {
            "request": request.model_dump(),
            "passes_count": len(passes),
            "targets_count": len(targets),
            "mission_start": mission_data.get("start_time"),
            "mission_end": mission_data.get("end_time"),
        }
        input_json = json.dumps(input_data, sort_keys=True, default=str)
        plan_input_hash = (
            f"sha256:{hashlib.sha256(input_json.encode()).hexdigest()[:16]}"
        )

        # Collect opportunity IDs considered
        opportunities_considered = [opp.id for opp in all_opportunities]

        audit_metadata = {
            "plan_input_hash": plan_input_hash,
            "run_id": run_id,
            "candidate_plan_id": candidate_plan_id,
            "opportunities_considered": opportunities_considered,
        }

        # Add audit metadata to results
        results["audit"] = audit_metadata  # type: ignore[assignment]

        logger.info(
            f"[AUDIT] run_id={run_id}, input_hash={plan_input_hash}, opps={len(opportunities_considered)}"
        )

        t_end = _time.perf_counter()
        logger.info("Total scheduling endpoint: %.2fs", t_end - t0)

        return PlanningResponse(
            success=True,
            message=f"Scheduled with {len(results) - 1} algorithms for {total_targets} targets",
            results=results,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mission planning failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Mission planning failed: {str(e)}"
        )


@app.get("/api/v1/planning/opportunities")
async def get_opportunities() -> Dict[str, Any]:
    """Get opportunities from last mission analysis."""
    try:
        _cmd = getattr(app.state, "current_mission_data", {})

        if not _cmd or "passes" not in _cmd:
            raise HTTPException(status_code=404, detail="No mission analysis available")

        passes = _cmd["passes"]
        targets = _cmd["targets"]

        # Convert to opportunity format
        opportunities = []
        for idx, pass_detail in enumerate(passes):
            # Handle both dict and object formats
            if isinstance(pass_detail, dict):
                sat_name = pass_detail["satellite_name"]
                target_name = pass_detail["target_name"]
                start_time = datetime.fromisoformat(pass_detail["start_time"])
                end_time = datetime.fromisoformat(pass_detail["end_time"])
                max_elevation = pass_detail["max_elevation"]
                start_azimuth = pass_detail["start_azimuth"]
            else:
                sat_name = pass_detail.satellite_name
                target_name = pass_detail.target_name
                start_time = pass_detail.start_time
                end_time = pass_detail.end_time
                max_elevation = pass_detail.max_elevation
                start_azimuth = pass_detail.start_azimuth

            opportunities.append(
                {
                    "id": f"{sat_name}_{target_name}_{idx}",
                    "satellite_id": sat_name,
                    "target_id": target_name,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "duration_seconds": (end_time - start_time).total_seconds(),
                    "max_elevation": max_elevation,
                    "azimuth": start_azimuth,
                }
            )

        return {
            "success": True,
            "count": len(opportunities),
            "opportunities": opportunities,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/planning/config")
async def get_planning_config() -> Dict[str, Any]:
    """Get planning configuration defaults."""
    try:
        # Get defaults from mission settings
        settings = mission_settings_manager.get_config_dict()

        # Extract relevant planning parameters
        config = {
            "imaging_time_s": 5.0,  # Default
            "max_roll_rate_dps": 1.0,
            "max_roll_accel_dps2": 1000.0,
            "look_window_s": 600.0,
            "value_source": "uniform",
            "algorithms": ["first_fit", "best_fit", "roll_pitch_first_fit"],
        }

        return {"success": True, "config": config}

    except Exception as e:
        logger.error(f"Error getting planning config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/planning/test-baseline")
async def test_baseline_performance() -> Dict[str, Any]:
    """Test current best_fit performance in 1-day vs 1-week scenarios."""
    try:
        # Hardcoded test mission data (your example)
        test_tle = TLEData(
            name="ICEYE-X44",
            line1="1 62707U 25009DC  25306.22031033  .00004207  00000+0  39848-3 0  9995",
            line2="2 62707  97.7269  23.9854 0002193 135.9671 224.1724 14.94137357 66022",
        )

        test_targets = [
            TargetData(
                name="Athens",
                latitude=37.9838,
                longitude=23.7275,
                description="Greek Capital - Highest Priority",
                priority=1,
            ),
            TargetData(
                name="Istanbul",
                latitude=41.0082,
                longitude=28.9784,
                description="Turkey - Major City (~500km from Athens)",
                priority=2,
            ),
            TargetData(
                name="Thessaloniki",
                latitude=40.6401,
                longitude=22.9444,
                description="Northern Greece (~310km from Athens)",
                priority=3,
            ),
            TargetData(
                name="Izmir",
                latitude=38.4237,
                longitude=27.1428,
                description="Western Turkey (~280km from Athens)",
                priority=3,
            ),
            TargetData(
                name="Nicosia",
                latitude=35.1856,
                longitude=33.3823,
                description="Cyprus - Capital (~800km from Athens)",
                priority=3,
            ),
            TargetData(
                name="Sofia",
                latitude=42.6977,
                longitude=23.3219,
                description="Bulgaria - Capital (~550km from Athens)",
                priority=4,
            ),
            TargetData(
                name="Rhodes",
                latitude=36.4341,
                longitude=28.2176,
                description="Greek Island (~430km from Athens)",
                priority=4,
            ),
            TargetData(
                name="Antalya",
                latitude=36.8969,
                longitude=30.7133,
                description="Southern Turkey (~480km from Athens)",
                priority=4,
            ),
            TargetData(
                name="Heraklion",
                latitude=35.3387,
                longitude=25.1442,
                description="Crete, Greece (~380km from Athens)",
                priority=5,
            ),
            TargetData(
                name="Patras",
                latitude=38.2466,
                longitude=21.7346,
                description="Western Greece (~210km from Athens)",
                priority=5,
            ),
        ]

        results = {}

        # Test 1-day window
        logger.info("🧪 Testing 1-day window")
        one_day_mission = MissionRequest(
            tle=test_tle,
            targets=test_targets,
            start_time="2025-11-11T10:30:00Z",
            end_time="2025-11-12T10:30:00Z",
            mission_type="imaging",
            imaging_type="optical",
            max_spacecraft_roll_deg=45,
        )

        mission_response = await analyze_mission(one_day_mission)
        if mission_response.success:
            planning_request = PlanningRequest(
                imaging_time_s=1.0, algorithms=["first_fit", "best_fit"]
            )
            planning_response = schedule_mission(planning_request)
            if planning_response.success and planning_response.results:
                results["one_day"] = {
                    "first_fit": planning_response.results.get("first_fit", {}).get(
                        "metrics", {}
                    ),
                    "best_fit": planning_response.results.get("best_fit", {}).get(
                        "metrics", {}
                    ),
                }

        # Test 1-week window
        logger.info("🧪 Testing 1-week window")
        one_week_mission = MissionRequest(
            tle=test_tle,
            targets=test_targets,
            start_time="2025-11-11T10:30:00Z",
            end_time="2025-11-18T10:30:00Z",
            mission_type="imaging",
            imaging_type="optical",
            max_spacecraft_roll_deg=45,
        )

        mission_response = await analyze_mission(one_week_mission)
        if mission_response.success:
            planning_request = PlanningRequest(
                imaging_time_s=1.0, algorithms=["first_fit", "best_fit"]
            )
            planning_response = schedule_mission(planning_request)
            if planning_response.success and planning_response.results:
                results["one_week"] = {
                    "first_fit": planning_response.results.get("first_fit", {}).get(
                        "metrics", {}
                    ),
                    "best_fit": planning_response.results.get("best_fit", {}).get(
                        "metrics", {}
                    ),
                }

        return {"success": True, "baseline_results": results}

    except Exception as e:
        logger.error(f"Baseline test failed: {str(e)}")
        return {"success": False, "error": str(e)}


# ===== DEBUG / AUDIT API ENDPOINTS =====


@app.post("/api/v1/debug/planning/run_scenario")
async def run_debug_scenario(request: RunScenarioRequest) -> Dict[str, Any]:
    """
    Run a single planning scenario with multiple algorithms for deep audit.

    This endpoint runs mission analysis and planning for a controlled scenario,
    returning detailed metrics, invariant checks, and schedules for each algorithm.

    Returns per-algorithm audit reports with:
    - Coverage metrics (accepted/rejected opportunities)
    - Value metrics (total value, mean value)
    - Geometry metrics (incidence angles)
    - Roll/pitch usage (for 2D slew algorithms)
    - Time metrics (maneuver, imaging, slack, utilization)
    - Invariant checks (overlap, limits, slack, monotonicity)
    - Complete schedule
    """
    try:
        logger.info(f"🔍 Debug: Running scenario {request.scenario_id or 'custom'}")
        logger.info(f"  Satellites: {len(request.satellites)}")
        logger.info(f"  Targets: {len(request.targets)}")
        logger.info(f"  Algorithms: {', '.join(request.algorithms)}")

        # Parse time window
        start_time = datetime.fromisoformat(
            request.time_window.start.replace("Z", "+00:00")
        )
        end_time = datetime.fromisoformat(
            request.time_window.end.replace("Z", "+00:00")
        )

        # Convert satellites and targets
        satellites = []
        for sat in request.satellites:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".tle", delete=False
            ) as f:
                f.write(f"{sat.name}\n{sat.tle_line1}\n{sat.tle_line2}\n")
                tle_file = f.name
            satellites.append(
                SatelliteOrbit.from_tle_file(tle_file, satellite_name=sat.name)
            )
            os.unlink(tle_file)

        targets = [
            GroundTarget(
                name=t.name,
                latitude=t.latitude,
                longitude=t.longitude,
                priority=t.priority,
            )
            for t in request.targets
        ]

        # Run mission analysis to get opportunities
        logger.info("  📊 Running mission analysis...")

        # Use first satellite for now (multi-satellite TBD)
        satellite = satellites[0]

        # Create visibility calculator
        vis_calc = VisibilityCalculator(satellite=satellite)

        # Find passes for each target
        opportunities = []

        # Check if any roll_pitch algorithm is being used
        use_pitch = any("roll_pitch" in algo for algo in request.algorithms)

        # Configurable parameters for imaging windows
        MIN_PASS_DURATION_S = 60  # Minimum pass duration for window opportunities
        EARLY_OFFSET_S = -30  # Seconds before max elevation
        LATE_OFFSET_S = +30  # Seconds after max elevation

        for target in targets:
            passes = vis_calc.find_passes(
                target=target,
                start_time=start_time,
                end_time=end_time,
                time_step_seconds=30,
            )

            # Convert passes to opportunities
            for idx, p in enumerate(passes):
                pass_duration = (p.end_time - p.start_time).total_seconds()

                if use_pitch and pass_duration >= MIN_PASS_DURATION_S:
                    # ROLL+PITCH MODE: Create opportunities throughout the ENTIRE pass duration
                    # This enables full pitch range usage based on actual pass geometry
                    # IMPORTANT: We also include the max-elevation opportunity (pitch=0) to ensure
                    # roll+pitch algorithms can always match or beat roll-only performance

                    # Use max_elevation_time if available, otherwise approximate as midpoint
                    max_elev_time = (
                        p.max_elevation_time
                        if hasattr(p, "max_elevation_time")
                        else p.start_time + timedelta(seconds=pass_duration / 2)
                    )

                    # Calculate number of opportunities based on pass duration
                    # MAXIMUM GRANULARITY: 1-second sampling for truly continuous coverage
                    # This creates the finest possible pitch resolution
                    SAMPLE_INTERVAL_S = 1.0
                    num_samples = max(
                        3, int(pass_duration / SAMPLE_INTERVAL_S)
                    )  # At least 3 samples

                    # Allow up to 180 opportunities per pass (3 minutes / 1s = 180)
                    # This gives maximum continuous coverage with 1-second resolution
                    num_samples = max(3, min(180, num_samples))

                    logger.debug(
                        f"Creating {num_samples} opportunities across {pass_duration:.0f}s pass for {target.name}"
                    )

                    # Sample uniformly across the pass duration
                    for i in range(num_samples):
                        # Calculate fraction through the pass (0.0 = start, 0.5 = middle, 1.0 = end)
                        fraction = i / (num_samples - 1) if num_samples > 1 else 0.5

                        # Calculate actual imaging time within the pass
                        imaging_time = p.start_time + timedelta(
                            seconds=pass_duration * fraction
                        )

                        # Calculate time offset from max elevation (for pitch calculation)
                        time_offset = (imaging_time - max_elev_time).total_seconds()

                        # Generate meaningful ID suffix
                        if abs(time_offset) < 5:
                            time_type = "max"
                        elif time_offset < 0:
                            time_type = f"early_{abs(int(time_offset))}"
                        else:
                            time_type = f"late_{int(time_offset)}"

                        # Get satellite position at this imaging time
                        try:
                            sat_position = satellite.get_position(imaging_time)

                            # Calculate dynamic pitch for this time offset
                            pitch_angle = vis_calc._calculate_pitch_angle(
                                satellite_position=sat_position,
                                target_position=(target.latitude, target.longitude),
                                time_offset_seconds=time_offset,
                                max_pitch_deg=request.planning_params.max_spacecraft_pitch_deg,
                            )

                            # Calculate incidence angle (roll) at this specific time
                            sat_lat, sat_lon, sat_alt = sat_position
                            incidence_angle = vis_calc._calculate_signed_roll_angle(
                                sat_lat=sat_lat,
                                sat_lon=sat_lon,
                                sat_alt=sat_alt,
                                target_lat=target.latitude,
                                target_lon=target.longitude,
                                timestamp=imaging_time,
                            )

                        except Exception as e:
                            logger.warning(
                                f"Error calculating angles for {target.name} at {imaging_time}: {e}"
                            )
                            pitch_angle = 0.0
                            incidence_angle = (
                                p.incidence_angle_deg if p.incidence_angle_deg else 0.0
                            )

                        opp = Opportunity(
                            id=f"{satellite.satellite_name}_{target.name}_{idx}_{time_type}",
                            satellite_id=satellite.satellite_name,
                            target_id=target.name,
                            start_time=imaging_time,
                            end_time=imaging_time
                            + timedelta(seconds=5),  # Imaging duration
                            incidence_angle=incidence_angle,  # Dynamic roll
                            pitch_angle=pitch_angle,  # Dynamic pitch
                        )
                        opportunities.append(opp)

                else:
                    # ROLL-ONLY MODE: Create single opportunity at max elevation (original behavior)
                    # This preserves the baseline for comparison
                    opp = Opportunity(
                        id=f"{satellite.satellite_name}_{target.name}_{idx}",
                        satellite_id=satellite.satellite_name,
                        target_id=target.name,
                        start_time=p.start_time,
                        end_time=p.end_time,
                        incidence_angle=(
                            p.incidence_angle_deg if p.incidence_angle_deg else 0.0
                        ),
                        pitch_angle=0.0,  # Roll-only mode: pitch always zero
                    )
                    opportunities.append(opp)

        if use_pitch:
            logger.info(
                f"  ✅ Found {len(opportunities)} opportunities (roll+pitch mode with imaging windows)"
            )
        else:
            logger.info(
                f"  ✅ Found {len(opportunities)} opportunities (roll-only mode)"
            )

        # Create planning constraints
        constraints = SchedulerConfig(
            imaging_time_s=request.planning_params.imaging_time_s,
            max_roll_rate_dps=request.planning_params.max_roll_rate_dps,
            max_roll_accel_dps2=request.planning_params.max_roll_accel_dps2,
            max_spacecraft_roll_deg=request.planning_params.max_spacecraft_roll_deg,
            max_pitch_rate_dps=request.planning_params.max_pitch_rate_dps,
            max_pitch_accel_dps2=request.planning_params.max_pitch_accel_dps2,
            max_spacecraft_pitch_deg=request.planning_params.max_spacecraft_pitch_deg,
        )

        # Run audit for each algorithm
        results = {}
        for algorithm in request.algorithms:
            logger.info(f"  🔬 Auditing {algorithm}...")

            audit_report = run_algorithm_audit(
                algorithm_name=algorithm,
                opportunities=opportunities,
                constraints=constraints,
                satellite_ids=[s.satellite_name for s in satellites],
                quality_model=request.planning_params.quality_model,
                quality_weight=request.planning_params.quality_weight,
            )

            # Convert to dict
            results[algorithm] = {
                "status": audit_report.status,
                "metrics": {
                    "accepted": audit_report.metrics.accepted,
                    "rejected": audit_report.metrics.rejected,
                    "total_opportunities": audit_report.metrics.total_opportunities,
                    "total_value": audit_report.metrics.total_value,
                    "mean_value": audit_report.metrics.mean_value,
                    "mean_incidence_deg": audit_report.metrics.mean_incidence_deg,
                    "min_incidence_deg": audit_report.metrics.min_incidence_deg,
                    "max_incidence_deg": audit_report.metrics.max_incidence_deg,
                    "total_roll_used_deg": audit_report.metrics.total_roll_used_deg,
                    "max_roll_deg": audit_report.metrics.max_roll_deg,
                    "mean_roll_deg": audit_report.metrics.mean_roll_deg,
                    "total_pitch_used_deg": audit_report.metrics.total_pitch_used_deg,
                    "max_pitch_deg": audit_report.metrics.max_pitch_deg,
                    "mean_pitch_deg": audit_report.metrics.mean_pitch_deg,
                    "opps_using_pitch": audit_report.metrics.opps_using_pitch,
                    "total_maneuver_time_s": audit_report.metrics.total_maneuver_time_s,
                    "total_imaging_time_s": audit_report.metrics.total_imaging_time_s,
                    "total_slack_time_s": audit_report.metrics.total_slack_time_s,
                    "utilization": audit_report.metrics.utilization,
                    "runtime_ms": audit_report.metrics.runtime_ms,
                },
                "invariants": [
                    {
                        "name": inv.name,
                        "ok": inv.ok,
                        "details": inv.details,
                        "affected_items": inv.affected_items,
                    }
                    for inv in audit_report.invariants
                ],
                "schedule": audit_report.schedule,
                "warnings": audit_report.warnings,
                "errors": audit_report.errors,
            }

        # Add roll vs pitch comparison if both are present
        comparisons = {}
        if "first_fit" in results and "first_fit_roll_pitch" in results:
            from mission_planner.audit import (
                AlgorithmMetrics,
                AuditReport,
                InvariantCheck,
            )

            # Reconstruct audit reports for comparison
            ff_result: Dict[str, Any] = results["first_fit"]
            rp_result: Dict[str, Any] = results["first_fit_roll_pitch"]
            ff_metrics: Dict[str, Any] = ff_result["metrics"]
            rp_metrics: Dict[str, Any] = rp_result["metrics"]
            ff_invariants: List[Dict[str, Any]] = ff_result["invariants"]
            rp_invariants: List[Dict[str, Any]] = rp_result["invariants"]
            ff_schedule: List[Dict[str, Any]] = ff_result["schedule"]
            rp_schedule: List[Dict[str, Any]] = rp_result["schedule"]

            roll_only = AuditReport(
                algorithm_name="first_fit",
                status=str(ff_result["status"]),
                metrics=AlgorithmMetrics(**ff_metrics),
                invariants=[InvariantCheck(**inv) for inv in ff_invariants],
                schedule=ff_schedule,
            )

            roll_pitch = AuditReport(
                algorithm_name="first_fit_roll_pitch",
                status=str(rp_result["status"]),
                metrics=AlgorithmMetrics(**rp_metrics),
                invariants=[InvariantCheck(**inv) for inv in rp_invariants],
                schedule=rp_schedule,
            )

            comparisons["first_fit_vs_roll_pitch"] = compare_roll_vs_pitch(
                roll_only, roll_pitch
            )

        return {
            "scenario_id": request.scenario_id or "custom",
            "algorithms": results,
            "comparisons": comparisons,
            "summary": {
                "total_opportunities": len(opportunities),
                "algorithms_run": len(results),
                "time_window": {
                    "start": request.time_window.start,
                    "end": request.time_window.end,
                    "duration_hours": (end_time - start_time).total_seconds() / 3600,
                },
            },
        }

    except Exception as e:
        logger.error(f"Debug scenario failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/debug/planning/benchmark")
async def run_benchmark(request: BenchmarkRequest) -> Dict[str, Any]:
    """
    Run benchmark across multiple scenarios with different parameter configurations.

    Returns aggregated metrics showing algorithm performance across diverse conditions.
    Useful for parameter sweeps and statistical analysis.
    """
    try:
        logger.info(f"🔬 Debug: Running benchmark")
        logger.info(f"  Presets: {request.presets}")
        logger.info(f"  Random scenarios: {request.num_random_scenarios}")
        logger.info(f"  Algorithms: {', '.join(request.algorithms)}")

        all_scenarios = []

        # Add preset scenarios
        for preset_id in request.presets:
            scenario = get_preset_scenario(preset_id)
            all_scenarios.append(scenario)

        # Add random scenarios
        for i in range(request.num_random_scenarios):
            scenario = generate_scenario(
                scenario_type="random",
                num_targets=10,
                time_span_hours=12,
                seed=i,
                mission_mode=request.mission_mode,
            )
            all_scenarios.append(scenario)

        logger.info(f"  Total scenarios to run: {len(all_scenarios)}")

        # Results aggregation
        algorithm_results: Dict[str, List[Dict[str, Any]]] = {
            algo: [] for algo in request.algorithms
        }
        scenario_results = []

        # Run each scenario
        for scenario in all_scenarios:
            logger.info(f"  Running scenario: {scenario.scenario_id}")

            # Convert scenario to RunScenarioRequest
            scenario_request = RunScenarioRequest(
                scenario_id=scenario.scenario_id,
                satellites=[
                    DebugSatellite(
                        id=sat.id,
                        name=sat.name,
                        tle_line1=sat.tle_line1,
                        tle_line2=sat.tle_line2,
                    )
                    for sat in scenario.satellites
                ],
                targets=[
                    DebugTarget(
                        id=t.name,  # Use name as id for GroundTarget
                        name=t.name,
                        latitude=t.latitude,
                        longitude=t.longitude,
                        priority=getattr(t, "priority", 5),
                    )
                    for t in scenario.targets
                ],
                time_window=TimeWindow(
                    start=scenario.time_window_start.isoformat() + "Z",
                    end=scenario.time_window_end.isoformat() + "Z",
                ),
                mission_mode=scenario.mission_mode,
                algorithms=request.algorithms,
            )

            # Run scenario
            try:
                result = await run_debug_scenario(scenario_request)
                scenario_results.append(
                    {
                        "scenario_id": scenario.scenario_id,
                        "success": True,
                        "algorithms": {
                            algo: result["algorithms"][algo]["metrics"]
                            for algo in request.algorithms
                        },
                    }
                )

                # Aggregate metrics
                for algo in request.algorithms:
                    algorithm_results[algo].append(
                        result["algorithms"][algo]["metrics"]
                    )

            except Exception as e:
                logger.error(f"  Failed: {scenario.scenario_id}: {e}")
                scenario_results.append(
                    {
                        "scenario_id": scenario.scenario_id,
                        "success": False,
                        "error": str(e),
                    }
                )

        # Compute aggregated statistics
        aggregated = {}
        for algo, results in algorithm_results.items():
            if not results:
                continue

            aggregated[algo] = {
                "scenarios_run": len(results),
                "mean_accepted": sum(r["accepted"] for r in results) / len(results),
                "median_accepted": sorted([r["accepted"] for r in results])[
                    len(results) // 2
                ],
                "mean_total_value": sum(r["total_value"] for r in results)
                / len(results),
                "mean_utilization": sum(r["utilization"] for r in results)
                / len(results),
                "mean_incidence_deg": (
                    sum(r["mean_incidence_deg"] for r in results) / len(results)
                    if all(r["mean_incidence_deg"] > 0 for r in results)
                    else 0
                ),
                "mean_runtime_ms": sum(r["runtime_ms"] for r in results) / len(results),
                "max_roll_deg": max(r["max_roll_deg"] for r in results),
                "max_pitch_deg": max(r["max_pitch_deg"] for r in results),
                "total_pitch_used_deg": sum(r["total_pitch_used_deg"] for r in results),
            }

        return {
            "summary": {
                "total_scenarios": len(all_scenarios),
                "successful_scenarios": len(
                    [s for s in scenario_results if s.get("success")]
                ),
                "failed_scenarios": len(
                    [s for s in scenario_results if not s.get("success")]
                ),
                "algorithms_tested": request.algorithms,
            },
            "aggregated_metrics": aggregated,
            "scenario_results": scenario_results,
        }

    except Exception as e:
        logger.error(f"Benchmark failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/debug/planning/presets")
async def list_preset_scenarios() -> Dict[str, Any]:
    """List available preset scenarios for benchmarking."""
    return {
        "presets": list(PRESET_SCENARIOS.keys()),
        "descriptions": {
            "simple_two_targets": "Two targets with clear visibility, easy to verify manually",
            "tight_timing_three_targets": "Three targets with tight spacing - roll+pitch should recover additional shots",
            "long_day_many_targets": "15 targets over 24 hours - stress test for algorithm scalability",
            "cross_hemisphere": "Targets spanning northern and southern hemispheres",
            "dense_cluster": "Dense cluster of 8 targets in small area",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
