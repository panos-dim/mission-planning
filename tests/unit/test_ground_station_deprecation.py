"""Regression coverage for deprecated ground-station support."""

from __future__ import annotations


def test_ground_station_config_endpoint_returns_empty_deprecated_payload(
    test_client, monkeypatch
) -> None:
    monkeypatch.setenv("MISSION_PLANNER_ADMIN_TOKEN", "admin-secret")

    response = test_client.get(
        "/api/v1/config/ground-stations",
        headers={"X-Admin-Token": "admin-secret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["deprecated"] is True
    assert payload["ground_stations"] == []
    assert payload["count"] == 0


def test_ground_station_mutation_endpoints_return_gone(
    test_client, monkeypatch
) -> None:
    monkeypatch.setenv("MISSION_PLANNER_ADMIN_TOKEN", "admin-secret")
    headers = {"X-Admin-Token": "admin-secret"}

    post_response = test_client.post(
        "/api/v1/config/ground-stations",
        headers=headers,
        json={"name": "Deprecated GS"},
    )
    put_response = test_client.put(
        "/api/v1/config/ground-stations/Deprecated%20GS",
        headers=headers,
        json={"name": "Deprecated GS"},
    )
    delete_response = test_client.delete(
        "/api/v1/config/ground-stations/Deprecated%20GS",
        headers=headers,
    )

    assert post_response.status_code == 410
    assert put_response.status_code == 410
    assert delete_response.status_code == 410
    assert "deprecated and disabled" in post_response.json()["detail"]


def test_full_config_omits_ground_stations(test_client, monkeypatch) -> None:
    monkeypatch.setenv("MISSION_PLANNER_ADMIN_TOKEN", "admin-secret")

    response = test_client.get(
        "/api/v1/config/full",
        headers={"X-Admin-Token": "admin-secret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "ground_stations" not in payload["config"]
