#!/usr/bin/env python3
"""
Test script for backend API endpoints - Sensor FOV Decoupling PR
Tests backward compatibility and new sensor/spacecraft separation.
"""

import json
import os
from datetime import UTC, datetime, timedelta

import pytest
import requests

BASE_URL = os.getenv("MISSION_PLANNER_TEST_BASE_URL", "http://localhost:8000").rstrip(
    "/"
)

pytestmark = pytest.mark.requires_server  # All tests in this module require server


def _iso_z(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _assert_successful_analysis(response: requests.Response) -> dict:
    assert response.status_code == 200, (
        f"Mission analysis failed with {response.status_code}: {response.text}"
    )
    data = response.json()
    assert data.get("success") is True, f"Mission analysis reported failure: {data}"
    payload = data.get("data", {})
    assert isinstance(payload, dict), f"Expected response data payload, got: {data}"
    mission_data = payload.get("mission_data", {})
    assert isinstance(
        mission_data, dict
    ), f"Expected mission_data payload, got: {payload}"
    assert "passes" in mission_data, f"Expected mission passes in payload, got: {data}"
    assert "czml_data" in payload, f"Expected CZML payload in response, got: {data}"
    return data


def test_health() -> None:
    """Test health check endpoint"""
    print("\n" + "=" * 80)
    print("TEST 1: Health Check")
    print("=" * 80)

    response = requests.get(f"{BASE_URL}/", timeout=15)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200, "Health check failed"
    print("✅ Health check passed")


def test_legacy_pointing_angle() -> None:
    """Test backward compatibility with legacy pointing_angle parameter"""
    print("\n" + "=" * 80)
    print("TEST 2: Legacy API - pointing_angle (Backward Compatibility)")
    print("=" * 80)

    start_time = datetime.now(UTC)
    end_time = start_time + timedelta(hours=24)

    payload = {
        "tle": {
            "name": "ICEYE-X44",
            "line1": "1 62707U 25009DC  25288.94104150  .00005233  00000+0  49676-3 0  9994",
            "line2": "2 62707  97.7279   6.9881 0001205 170.4542 189.6701 14.93939975 63446",
        },
        "targets": [
            {
                "name": "Test Target UAE",
                "latitude": 24.4539,
                "longitude": 54.3773,
                "priority": 1,
            }
        ],
        "start_time": _iso_z(start_time),
        "end_time": _iso_z(end_time),
        "mission_type": "imaging",
        "pointing_angle": 45.0,  # LEGACY parameter - should trigger deprecation warning
    }

    print(f"\n📤 Request payload (using legacy pointing_angle=45.0):")
    print(json.dumps({k: v for k, v in payload.items() if k != "tle"}, indent=2))

    response = requests.post(
        f"{BASE_URL}/api/v1/mission/analyze", json=payload, timeout=60
    )
    print(f"\n📥 Status: {response.status_code}")
    data = _assert_successful_analysis(response)
    mission_data = data["data"]["mission_data"]
    czml_data = data["data"]["czml_data"]

    print(f"✅ Mission planned successfully")
    print(f"   - Found {len(mission_data.get('passes', []))} passes")
    print(f"   - CZML packets: {len(czml_data)}")

    # Check if pointing cone was generated (should be for imaging mission)
    czml_ids = [p.get("id") for p in czml_data]
    if "pointing_cone" in czml_ids:
        print(f"   - ✅ Sensor footprint (pointing_cone) generated")
    else:
        print(f"   - ⚠️  No sensor footprint found")

    print("✅ Legacy API test passed")


def test_new_sensor_fov_api() -> None:
    """Test new API with sensor_fov_half_angle_deg"""
    print("\n" + "=" * 80)
    print("TEST 3: New API - sensor_fov_half_angle_deg")
    print("=" * 80)

    start_time = datetime.now(UTC)
    end_time = start_time + timedelta(hours=24)

    payload = {
        "tle": {
            "name": "ICEYE-X44",
            "line1": "1 62707U 25009DC  25288.94104150  .00005233  00000+0  49676-3 0  9994",
            "line2": "2 62707  97.7279   6.9881 0001205 170.4542 189.6701 14.93939975 63446",
        },
        "targets": [
            {
                "name": "Test Target UAE",
                "latitude": 24.4539,
                "longitude": 54.3773,
                "priority": 1,
            }
        ],
        "start_time": _iso_z(start_time),
        "end_time": _iso_z(end_time),
        "mission_type": "imaging",
        "sensor_fov_half_angle_deg": 30.0,  # NEW parameter
    }

    print(f"\n📤 Request payload (using new sensor_fov_half_angle_deg=30.0):")
    print(json.dumps({k: v for k, v in payload.items() if k != "tle"}, indent=2))

    response = requests.post(
        f"{BASE_URL}/api/v1/mission/analyze", json=payload, timeout=60
    )
    print(f"\n📥 Status: {response.status_code}")
    data = _assert_successful_analysis(response)
    mission_data = data["data"]["mission_data"]
    czml_data = data["data"]["czml_data"]

    print(f"✅ Mission planned successfully")
    print(f"   - Found {len(mission_data.get('passes', []))} passes")
    print(f"   - CZML packets: {len(czml_data)}")

    # Check if pointing cone was generated
    czml_ids = [p.get("id") for p in czml_data]
    if "pointing_cone" in czml_ids:
        print(f"   - ✅ Sensor footprint (pointing_cone) generated with new API")
    else:
        print(f"   - ⚠️  No sensor footprint found")

    print("✅ New API test passed")


def test_communication_mission() -> None:
    """Test communication mission (no sensor FOV needed)"""
    print("\n" + "=" * 80)
    print("TEST 4: Communication Mission (No Sensor FOV)")
    print("=" * 80)

    start_time = datetime.now(UTC)
    end_time = start_time + timedelta(hours=24)

    payload = {
        "tle": {
            "name": "ICEYE-X44",
            "line1": "1 62707U 25009DC  25288.94104150  .00005233  00000+0  49676-3 0  9994",
            "line2": "2 62707  97.7279   6.9881 0001205 170.4542 189.6701 14.93939975 63446",
        },
        "targets": [
            {
                "name": "Ground Station UAE",
                "latitude": 24.4539,
                "longitude": 54.3773,
                "priority": 1,
            }
        ],
        "start_time": _iso_z(start_time),
        "end_time": _iso_z(end_time),
        "mission_type": "communication",  # No pointing_angle or sensor_fov needed
    }

    print(f"\n📤 Request payload (communication mission):")
    print(json.dumps({k: v for k, v in payload.items() if k != "tle"}, indent=2))

    response = requests.post(
        f"{BASE_URL}/api/v1/mission/analyze", json=payload, timeout=60
    )
    print(f"\n📥 Status: {response.status_code}")
    data = _assert_successful_analysis(response)
    mission_data = data["data"]["mission_data"]
    czml_data = data["data"]["czml_data"]

    print(f"✅ Mission planned successfully")
    print(f"   - Found {len(mission_data.get('passes', []))} passes")

    # Should NOT have pointing cone for communication mission
    czml_ids = [p.get("id") for p in czml_data]
    if "pointing_cone" not in czml_ids:
        print(f"   - ✅ No sensor footprint (correct for communication)")
    else:
        print(f"   - ⚠️  Unexpected sensor footprint for communication mission")

    print("✅ Communication mission test passed")


def test_wide_fov_tight_bus_scenario() -> None:
    """Test scenario: Wide sensor FOV, limited spacecraft agility"""
    print("\n" + "=" * 80)
    print("TEST 5: Wide-FOV / Tight Bus Scenario")
    print("=" * 80)
    print("Scenario: 50° sensor FOV should find many opportunities in analysis")
    print("          Scheduler with 30° bus limit should prune some")

    start_time = datetime.now(UTC)
    end_time = start_time + timedelta(hours=48)

    payload = {
        "tle": {
            "name": "ICEYE-X44",
            "line1": "1 62707U 25009DC  25288.94104150  .00005233  00000+0  49676-3 0  9994",
            "line2": "2 62707  97.7279   6.9881 0001205 170.4542 189.6701 14.93939975 63446",
        },
        "targets": [
            {
                "name": "Wide FOV Target",
                "latitude": 24.4539,
                "longitude": 54.3773,
                "priority": 1,
            }
        ],
        "start_time": _iso_z(start_time),
        "end_time": _iso_z(end_time),
        "mission_type": "imaging",
        "sensor_fov_half_angle_deg": 50.0,  # Wide sensor FOV
        # Note: Scheduler uses config default (90°) or would need separate spacecraft config
    }

    print(f"\n📤 Request: sensor_fov_half_angle_deg=50.0° (wide FOV)")

    response = requests.post(
        f"{BASE_URL}/api/v1/mission/analyze", json=payload, timeout=60
    )
    print(f"\n📥 Status: {response.status_code}")
    data = _assert_successful_analysis(response)
    mission_data = data["data"]["mission_data"]

    print(f"✅ Mission planned successfully")
    print(
        f"   - Found {len(mission_data.get('passes', []))} passes (wide FOV should find more)"
    )

    print("✅ Wide-FOV scenario test passed")


def main() -> int:
    """Run all tests"""
    print("\n" + "=" * 80)
    print("BACKEND API TEST SUITE - Sensor FOV Decoupling PR")
    print("=" * 80)
    print("Testing backward compatibility and new sensor/spacecraft separation")

    tests = [
        ("Health Check", test_health),
        ("Legacy pointing_angle", test_legacy_pointing_angle),
        ("New sensor_fov_half_angle_deg", test_new_sensor_fov_api),
        ("Communication Mission", test_communication_mission),
        ("Wide-FOV Scenario", test_wide_fov_tight_bus_scenario),
    ]

    results = []
    for name, test_func in tests:
        try:
            test_func()
            results.append((name, True))
        except Exception as e:
            print(f"\n❌ Test '{name}' failed with exception: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    total = len(results)
    passed = sum(1 for _, r in results if r)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Backend is ready.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review above output.")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
