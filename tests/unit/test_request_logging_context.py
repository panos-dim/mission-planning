"""Tests for request-scoped logging context propagation."""

import io
import logging
import os
from unittest.mock import patch

from mission_planner.utils import _LogContextFilter


def test_request_id_header_is_generated(test_client) -> None:
    response = test_client.get("/")

    assert response.status_code == 200
    request_id = response.headers.get("X-Request-ID")
    assert request_id
    assert len(request_id) == 12


def test_request_id_header_is_preserved(test_client) -> None:
    response = test_client.get("/", headers={"X-Request-ID": "req-test-123"})

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "req-test-123"


def test_request_completion_log_includes_request_id(test_client) -> None:
    logger = logging.getLogger("backend.main")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s%(log_context)s"))
    handler.addFilter(_LogContextFilter())

    original_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    try:
        response = test_client.get("/", headers={"X-Request-ID": "req-log-123"})
        assert response.status_code == 200
        handler.flush()
        output = stream.getvalue()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        handler.close()

    assert "HTTP GET / -> 200" in output
    assert "[req=req-log-123]" in output


def test_schedule_request_completion_log_includes_workspace_id(test_client) -> None:
    logger = logging.getLogger("backend.main")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s%(log_context)s"))
    handler.addFilter(_LogContextFilter())

    original_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    try:
        response = test_client.get(
            "/api/v1/schedule/state",
            params={"workspace_id": "ws-log-1"},
            headers={"X-Request-ID": "req-ws-log-123"},
        )
        assert response.status_code == 200
        handler.flush()
        output = stream.getvalue()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        handler.close()

    assert "HTTP GET /api/v1/schedule/state -> 200" in output
    assert "[req=req-ws-log-123 ws=ws-log-1]" in output


def test_slow_request_logs_warning_with_latency_details(test_client) -> None:
    logger = logging.getLogger("backend.main")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s%(log_context)s"))
    handler.addFilter(_LogContextFilter())

    original_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    try:
        with patch("backend.main.perf_counter", side_effect=[100.0, 102.2]):
            response = test_client.get(
                "/api/v1/schedule/state",
                params={"workspace_id": "ws-slow-1"},
                headers={"X-Request-ID": "req-slow-123"},
            )
        assert response.status_code == 200
        handler.flush()
        output = stream.getvalue()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        handler.close()

    assert "Slow HTTP GET /api/v1/schedule/state -> 200 in 2.2s" in output
    assert "threshold=750ms" in output
    assert "bucket=1-5s" in output
    assert "[req=req-slow-123 ws=ws-slow-1]" in output


def test_route_latency_summary_logs_periodic_stats(test_client) -> None:
    from backend.main import _ROUTE_LATENCY_AGGREGATOR

    logger = logging.getLogger("backend.main")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s%(log_context)s"))
    handler.addFilter(_LogContextFilter())

    original_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    _ROUTE_LATENCY_AGGREGATOR.reset()

    try:
        with patch.dict(
            os.environ,
            {"MISSION_PLANNER_LOG_ROUTE_SUMMARY_EVERY": "2"},
            clear=False,
        ):
            with patch(
                "backend.main.perf_counter",
                side_effect=[10.0, 10.3, 20.0, 20.9],
            ):
                first = test_client.get(
                    "/api/v1/schedule/state",
                    params={"workspace_id": "ws-summary-1"},
                    headers={"X-Request-ID": "req-summary-1"},
                )
                second = test_client.get(
                    "/api/v1/schedule/state",
                    params={"workspace_id": "ws-summary-1"},
                    headers={"X-Request-ID": "req-summary-2"},
                )
        assert first.status_code == 200
        assert second.status_code == 200
        handler.flush()
        output = stream.getvalue()
    finally:
        _ROUTE_LATENCY_AGGREGATOR.reset()
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        handler.close()

    assert "Latency summary GET /api/v1/schedule/state: count=2" in output
    assert "avg=600.0ms" in output
    assert "p95=900.0ms" in output
    assert "slow=1/2" in output
    assert "profile=default threshold=750ms" in output
    assert "[req=req-summary-2 ws=ws-summary-1]" in output


def test_dev_route_latency_endpoint_reports_and_resets_batches(test_client) -> None:
    from backend.main import _ROUTE_LATENCY_AGGREGATOR, get_route_latency_snapshot

    _ROUTE_LATENCY_AGGREGATOR.reset()

    try:
        _ROUTE_LATENCY_AGGREGATOR.record(
            route_label="/api/v1/schedule/state",
            duration_ms=320.0,
            status_code=200,
            slow_threshold_ms=750.0,
        )
        _ROUTE_LATENCY_AGGREGATOR.record(
            route_label="/api/v1/schedule/state",
            duration_ms=980.0,
            status_code=200,
            slow_threshold_ms=750.0,
        )
        _ROUTE_LATENCY_AGGREGATOR.record(
            route_label="/api/v1/orders/inbox",
            duration_ms=120.0,
            status_code=500,
            slow_threshold_ms=750.0,
        )

        response = test_client.get(
            "/api/v1/dev/route-latency",
            params={"limit": 10, "reset": "true"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["route_count"] == 2
        assert payload["history_count"] == 0
        assert payload["family_count"] == 2
        assert payload["status_counts"] == {
            "2xx": 2,
            "3xx": 0,
            "4xx": 0,
            "5xx": 1,
            "other": 0,
        }
        assert payload["history_status_counts"] == {
            "2xx": 0,
            "3xx": 0,
            "4xx": 0,
            "5xx": 0,
            "other": 0,
        }
        assert payload["recent_error_count"] == 1
        assert payload["recent_error_status_counts"] == {
            "2xx": 0,
            "3xx": 0,
            "4xx": 0,
            "5xx": 1,
            "other": 0,
        }
        assert payload["error_family_count"] == 1

        routes = {item["route"]: item for item in payload["routes"]}
        assert "/api/v1/schedule/state" in routes
        schedule_route = routes["/api/v1/schedule/state"]
        assert schedule_route["route_family"] == "schedule"
        assert schedule_route["count"] == 2
        assert schedule_route["avg_ms"] == 650.0
        assert schedule_route["p95_ms"] == 980.0
        assert schedule_route["slow_count"] == 1
        assert schedule_route["error_count"] == 0
        assert schedule_route["status_counts"] == {
            "2xx": 2,
            "3xx": 0,
            "4xx": 0,
            "5xx": 0,
            "other": 0,
        }
        assert schedule_route["profile"] == "default"
        assert schedule_route["slow_threshold_ms"] == 750.0

        families = {item["family"]: item for item in payload["families"]}
        assert families["schedule"]["request_count"] == 2
        assert families["schedule"]["slow_count"] == 1
        assert families["schedule"]["error_count"] == 0
        assert families["schedule"]["hot_count"] == 0
        assert families["schedule"]["status_counts"]["2xx"] == 2
        assert families["orders"]["request_count"] == 1
        assert families["orders"]["error_count"] == 1
        assert families["orders"]["status_counts"]["5xx"] == 1

        recent_error = payload["recent_errors"][0]
        assert recent_error["route"] == "/api/v1/orders/inbox"
        assert recent_error["route_family"] == "orders"
        assert recent_error["status_code"] == 500
        assert recent_error["status_class"] == "5xx"

        error_family = payload["error_families"][0]
        assert error_family["family"] == "orders"
        assert error_family["error_count"] == 1
        assert error_family["route_count"] == 1
        assert error_family["status_counts"]["5xx"] == 1

        remaining_routes = {
            item["route"]
            for item in get_route_latency_snapshot(limit=10, reset=False)["routes"]
        }
        assert "/api/v1/schedule/state" not in remaining_routes
        assert get_route_latency_snapshot(limit=10, reset=False)["recent_error_count"] == 1
    finally:
        _ROUTE_LATENCY_AGGREGATOR.reset()


def test_dev_route_latency_endpoint_includes_history_and_baseline(test_client) -> None:
    from backend.main import _ROUTE_LATENCY_AGGREGATOR

    _ROUTE_LATENCY_AGGREGATOR.reset()

    try:
        with patch.dict(
            os.environ,
            {
                "MISSION_PLANNER_LOG_ROUTE_SUMMARY_EVERY": "2",
                "MISSION_PLANNER_LOG_ROUTE_HISTORY_LIMIT": "10",
                "MISSION_PLANNER_LOG_ROUTE_BASELINE_WINDOWS": "3",
                "MISSION_PLANNER_LOG_ROUTE_HOT_MULTIPLIER": "1.4",
                "MISSION_PLANNER_LOG_ROUTE_HOT_MIN_DELTA_MS": "100",
                "MISSION_PLANNER_LOG_ROUTE_HOT_MIN_WINDOWS": "1",
            },
            clear=False,
        ):
            _ROUTE_LATENCY_AGGREGATOR.record(
                route_label="/api/v1/schedule/state",
                duration_ms=400.0,
                status_code=200,
                slow_threshold_ms=750.0,
            )
            emitted = _ROUTE_LATENCY_AGGREGATOR.record(
                route_label="/api/v1/schedule/state",
                duration_ms=800.0,
                status_code=200,
                slow_threshold_ms=750.0,
            )
            assert emitted is not None

            _ROUTE_LATENCY_AGGREGATOR.record(
                route_label="/api/v1/schedule/state",
                duration_ms=1000.0,
                status_code=200,
                slow_threshold_ms=750.0,
            )

            response = test_client.get(
                "/api/v1/dev/route-latency",
                params={"limit": 10},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["history_limit"] == 10
        assert payload["baseline_windows"] == 3
        assert payload["history_count"] == 1
        assert payload["route_count"] == 1
        assert payload["family_count"] == 1
        assert payload["status_counts"] == {
            "2xx": 1,
            "3xx": 0,
            "4xx": 0,
            "5xx": 0,
            "other": 0,
        }
        assert payload["history_status_counts"] == {
            "2xx": 2,
            "3xx": 0,
            "4xx": 0,
            "5xx": 0,
            "other": 0,
        }
        assert payload["recent_error_count"] == 0
        assert payload["recent_error_status_counts"] == {
            "2xx": 0,
            "3xx": 0,
            "4xx": 0,
            "5xx": 0,
            "other": 0,
        }
        assert payload["error_family_count"] == 0
        assert payload["recent_errors"] == []
        assert payload["error_families"] == []

        history_entry = payload["history"][0]
        assert history_entry["route"] == "/api/v1/schedule/state"
        assert history_entry["route_family"] == "schedule"
        assert history_entry["count"] == 2
        assert history_entry["avg_ms"] == 600.0
        assert history_entry["p95_ms"] == 800.0
        assert history_entry["status_counts"] == {
            "2xx": 2,
            "3xx": 0,
            "4xx": 0,
            "5xx": 0,
            "other": 0,
        }
        assert history_entry["is_hot"] is False
        assert history_entry["hot_reason"] is None

        route_entry = payload["routes"][0]
        assert route_entry["route"] == "/api/v1/schedule/state"
        assert route_entry["route_family"] == "schedule"
        assert route_entry["count"] == 1
        assert route_entry["avg_ms"] == 1000.0
        assert route_entry["p95_ms"] == 1000.0
        assert route_entry["status_counts"] == {
            "2xx": 1,
            "3xx": 0,
            "4xx": 0,
            "5xx": 0,
            "other": 0,
        }
        assert route_entry["baseline_windows"] == 1
        assert route_entry["baseline_avg_ms"] == 600.0
        assert route_entry["baseline_p95_ms"] == 800.0
        assert route_entry["avg_delta_ms"] == 400.0
        assert route_entry["p95_delta_ms"] == 200.0
        assert route_entry["is_hot"] is True
        assert route_entry["hot_reason"] == "avg jumped from 600.0ms to 1000.0ms (+400.0ms)"

        family_entry = payload["families"][0]
        assert family_entry["family"] == "schedule"
        assert family_entry["route_count"] == 1
        assert family_entry["request_count"] == 1
        assert family_entry["hot_count"] == 1
        assert family_entry["status_counts"]["2xx"] == 1
    finally:
        _ROUTE_LATENCY_AGGREGATOR.reset()


def test_hot_route_warning_logs_against_recent_baseline(test_client) -> None:
    from backend.main import _ROUTE_LATENCY_AGGREGATOR

    logger = logging.getLogger("backend.main")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s%(log_context)s"))
    handler.addFilter(_LogContextFilter())

    original_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    _ROUTE_LATENCY_AGGREGATOR.reset()

    try:
        with patch.dict(
            os.environ,
            {
                "MISSION_PLANNER_LOG_ROUTE_SUMMARY_EVERY": "2",
                "MISSION_PLANNER_LOG_ROUTE_HISTORY_LIMIT": "10",
                "MISSION_PLANNER_LOG_ROUTE_BASELINE_WINDOWS": "1",
                "MISSION_PLANNER_LOG_ROUTE_HOT_MULTIPLIER": "1.4",
                "MISSION_PLANNER_LOG_ROUTE_HOT_MIN_DELTA_MS": "100",
                "MISSION_PLANNER_LOG_ROUTE_HOT_MIN_WINDOWS": "1",
            },
            clear=False,
        ):
            with patch(
                "backend.main.perf_counter",
                side_effect=[10.0, 10.3, 20.0, 20.4, 30.0, 31.0, 40.0, 41.2],
            ):
                for idx in range(4):
                    response = test_client.get(
                        "/api/v1/schedule/state",
                        params={"workspace_id": "ws-hot-1"},
                        headers={"X-Request-ID": f"req-hot-{idx}"},
                    )
                    assert response.status_code == 200
        handler.flush()
        output = stream.getvalue()
    finally:
        _ROUTE_LATENCY_AGGREGATOR.reset()
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        handler.close()

    assert "Hot route GET /api/v1/schedule/state:" in output
    assert "p95 jumped from 400.0ms to 1200.0ms (+800.0ms)" in output
    assert "baseline_windows=1" in output
    assert "[req=req-hot-3 ws=ws-hot-1]" in output
