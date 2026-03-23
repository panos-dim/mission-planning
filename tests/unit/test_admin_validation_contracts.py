"""Contract tests for admin/config validation surfaces used by the frontend."""


def test_governance_endpoint_exposes_admin_and_mission_inputs(test_client) -> None:
    response = test_client.get("/api/v1/config/governance")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "max_spacecraft_roll_deg" in payload["admin_only_params"]
    assert "start_time" in payload["mission_input_params"]["common"]
    assert "sar.imaging_mode" in payload["mission_input_params"]["sar"]
    assert "pass_duration_s" in payload["derived_params"]


def test_satellite_config_summary_supports_filtering(test_client) -> None:
    response = test_client.get("/api/v1/config/satellite-config-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["satellites"], payload

    first_satellite = payload["satellites"][0]
    assert {
        "id",
        "name",
        "imaging_type",
        "bus",
        "sensor",
        "sar_capable",
    } <= set(first_satellite)
    assert {
        "max_roll_deg",
        "max_roll_rate_dps",
        "max_pitch_deg",
        "max_pitch_rate_dps",
        "settling_time_s",
        "agility_dps",
    } <= set(first_satellite["bus"])

    filtered = test_client.get(
        "/api/v1/config/satellite-config-summary",
        params={"satellite_ids": first_satellite["id"]},
    )

    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["success"] is True
    assert [item["id"] for item in filtered_payload["satellites"]] == [
        first_satellite["id"]
    ]


def test_e2e_catalog_endpoint_returns_review_metadata(test_client) -> None:
    response = test_client.get("/api/v1/validate/e2e/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert payload["suites"], payload
    assert payload["input_profiles"], payload

    profile_ids = {profile["id"] for profile in payload["input_profiles"]}
    first_suite = payload["suites"][0]
    assert "name" in first_suite
    assert isinstance(first_suite["tests"], list) and first_suite["tests"]
    assert set(first_suite.get("input_profile_ids", [])) <= profile_ids
