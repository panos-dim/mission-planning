"""Regression coverage for readiness probes and privileged-route access guards."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend.security import require_admin_access


def _make_request(host: str) -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [],
        "client": (host, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_health_endpoint_reports_ok(test_client) -> None:
    response = test_client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["ready"] is True


def test_ready_endpoint_reports_component_checks(test_client) -> None:
    response = test_client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["ready"] is True
    assert payload["checks"]["schedule_db"]["ready"] is True
    assert payload["checks"]["config"]["ready"] is True
    assert payload["checks"]["satellites"]["ready"] is True


def test_ready_endpoint_returns_503_when_schedule_db_is_not_ready(
    test_client, monkeypatch
) -> None:
    class BrokenDB:
        def health_check(self) -> dict[str, Any]:
            return {"ready": False, "error": "db unavailable"}

    monkeypatch.setattr("backend.main.get_schedule_db", lambda: BrokenDB())

    response = test_client.get("/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["ready"] is False
    assert payload["checks"]["schedule_db"]["ready"] is False


def test_dev_route_requires_token_when_configured(test_client, monkeypatch) -> None:
    monkeypatch.setenv("MISSION_PLANNER_DEV_TOKEN", "dev-secret")

    unauthorized = test_client.get("/api/v1/dev/route-latency")
    assert unauthorized.status_code == 401

    authorized = test_client.get(
        "/api/v1/dev/route-latency",
        headers={"X-Dev-Token": "dev-secret"},
    )
    assert authorized.status_code == 200


def test_admin_route_requires_token_when_configured(test_client, monkeypatch) -> None:
    monkeypatch.setenv("MISSION_PLANNER_ADMIN_TOKEN", "admin-secret")

    unauthorized = test_client.get("/api/v1/config/full")
    assert unauthorized.status_code == 401

    authorized = test_client.get(
        "/api/v1/config/full",
        headers={"X-Admin-Token": "admin-secret"},
    )
    assert authorized.status_code == 200


def test_admin_access_rejects_non_local_clients_without_token(monkeypatch) -> None:
    monkeypatch.delenv("MISSION_PLANNER_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("MISSION_PLANNER_ALLOW_LOOPBACK_ADMIN", "1")

    with pytest.raises(HTTPException) as exc_info:
        require_admin_access(_make_request("203.0.113.10"))

    assert exc_info.value.status_code == 403
