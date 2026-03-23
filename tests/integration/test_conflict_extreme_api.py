#!/usr/bin/env python3
"""
Extreme conflict API regression coverage.

Exercises a dense far-future overlap set over real HTTP and verifies that
conflict recomputation finds the full batch without requiring explicit bounds.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import pytest
import requests

BASE_URL = "http://localhost:8000"
API = f"{BASE_URL}/api/v1"

pytestmark = pytest.mark.requires_server


def _post(path: str, payload: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    resp = requests.post(f"{API}{path}", json=payload, timeout=timeout)
    assert resp.status_code == 200, f"{path} returned {resp.status_code}: {resp.text[:500]}"
    return resp.json()  # type: ignore[no-any-return]


def _get(path: str, params: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    resp = requests.get(f"{API}{path}", params=params, timeout=timeout)
    assert resp.status_code == 200, f"{path} returned {resp.status_code}: {resp.text[:500]}"
    return resp.json()  # type: ignore[no-any-return]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _create_workspace(name: str) -> str:
    data = _post("/workspaces", {"name": name, "mission_mode": "OPTICAL"})
    workspace_id = data.get("workspace_id")
    assert workspace_id, data
    return str(workspace_id)


def _delete_workspace(workspace_id: str) -> None:
    resp = requests.delete(f"{API}/workspaces/{workspace_id}", timeout=30)
    assert resp.status_code == 200, resp.text[:300]


def _direct_commit(
    workspace_id: str,
    target_id: str,
    satellite_id: str,
    start_time: str,
    end_time: str,
) -> Dict[str, Any]:
    return _post(
        "/schedule/commit/direct",
        {
            "workspace_id": workspace_id,
            "algorithm": "test_synthetic",
            "force": True,
            "items": [
                {
                    "opportunity_id": f"extreme_{uuid.uuid4().hex[:8]}",
                    "satellite_id": satellite_id,
                    "target_id": target_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "roll_angle_deg": 0.0,
                    "pitch_angle_deg": 0.0,
                }
            ],
        },
    )


def _direct_commit_default(
    target_id: str,
    satellite_id: str,
    start_time: str,
    end_time: str,
) -> Dict[str, Any]:
    return _post(
        "/schedule/commit/direct",
        {
            "algorithm": "test_default_workspace",
            "force": False,
            "items": [
                {
                    "opportunity_id": f"default_{uuid.uuid4().hex[:8]}",
                    "satellite_id": satellite_id,
                    "target_id": target_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "roll_angle_deg": 0.0,
                    "pitch_angle_deg": 0.0,
                }
            ],
        },
    )


def _bulk_delete(workspace_id: str, acquisition_ids: list[str]) -> Dict[str, Any]:
    return _post(
        "/schedule/acquisitions/bulk-delete",
        {
            "workspace_id": workspace_id,
            "acquisition_ids": acquisition_ids,
            "force": True,
        },
    )


def test_far_future_dense_overlap_recompute_without_bounds() -> None:
    """
    Build a dense overlap set well beyond now+7d and verify recompute catches it.

    Expected overlap pairs:
    - LONG-A with LONG-B
    - LONG-A with EDGE-POINT
    - LONG-A with TAIL-C
    - TAIL-C with EDGE-POINT
    """
    workspace_id = _create_workspace(f"extreme_{uuid.uuid4().hex[:8]}")
    try:
        base = datetime.now(timezone.utc) + timedelta(days=45)
        _direct_commit(
            workspace_id,
            "LONG-A",
            "SAT-EXTREME-1",
            _iso(base),
            _iso(base + timedelta(minutes=10)),
        )
        _direct_commit(
            workspace_id,
            "LONG-B",
            "SAT-EXTREME-1",
            _iso(base + timedelta(minutes=5)),
            _iso(base + timedelta(minutes=6)),
        )
        _direct_commit(
            workspace_id,
            "TAIL-C",
            "SAT-EXTREME-1",
            _iso(base + timedelta(minutes=9)),
            _iso(base + timedelta(minutes=11)),
        )
        _direct_commit(
            workspace_id,
            "EDGE-POINT",
            "SAT-EXTREME-1",
            _iso(base + timedelta(minutes=10)),
            _iso(base + timedelta(minutes=10)),
        )

        recompute = _post("/schedule/conflicts/recompute", {"workspace_id": workspace_id})
        assert recompute["success"], recompute
        assert recompute["detected"] >= 4, recompute
        assert recompute["persisted"] >= 4, recompute

        conflicts = _get("/schedule/conflicts", {"workspace_id": workspace_id})
        conflict_list = conflicts.get("conflicts", [])
        temporal = [c for c in conflict_list if c.get("type") == "temporal_overlap"]
        assert len(temporal) >= 4, conflicts
    finally:
        _delete_workspace(workspace_id)


def _overlaps(
    start1: datetime,
    end1: datetime,
    start2: datetime,
    end2: datetime,
) -> bool:
    point1 = start1 == end1
    point2 = start2 == end2
    if point1 and point2:
        return start1 == start2
    if point1:
        return start2 <= start1 <= end2
    if point2:
        return start1 <= start2 <= end1
    return start1 < end2 and start2 < end1


def test_randomized_far_future_overlap_pairs_match_naive_model() -> None:
    """Stress recompute over HTTP and compare persisted overlap pairs to a naive model."""
    seeds = [101, 202, 303]

    for seed in seeds:
        workspace_id = _create_workspace(f"extreme_pairs_{seed}_{uuid.uuid4().hex[:6]}")
        try:
            rng = random.Random(seed)
            base = datetime.now(timezone.utc) + timedelta(days=60 + seed % 5)
            committed: list[dict[str, Any]] = []

            for idx in range(10):
                satellite_id = f"SAT-EXTREME-{rng.randint(1, 3)}"
                slot = rng.randint(0, 12)
                duration_minutes = rng.randint(0, 4)
                start_dt = base + timedelta(minutes=slot * 2)
                end_dt = start_dt + timedelta(minutes=duration_minutes)
                target_id = f"R{seed}-{idx}"
                _direct_commit(
                    workspace_id,
                    target_id,
                    satellite_id,
                    _iso(start_dt),
                    _iso(end_dt),
                )
                committed.append(
                    {
                        "satellite_id": satellite_id,
                        "target_id": target_id,
                        "start": start_dt,
                        "end": end_dt,
                    }
                )

            recompute = _post("/schedule/conflicts/recompute", {"workspace_id": workspace_id})
            assert recompute["success"], recompute

            conflicts = _get("/schedule/conflicts", {"workspace_id": workspace_id})
            state = _get("/schedule/state", {"workspace_id": workspace_id})
            acquisition_targets = {
                acquisition["id"]: acquisition["target_id"]
                for acquisition in state.get("state", {}).get("acquisitions", [])
            }
            actual_pairs = {
                frozenset(
                    {
                        acquisition_targets[conflict["acquisition_ids"][0]],
                        acquisition_targets[conflict["acquisition_ids"][1]],
                    }
                )
                for conflict in conflicts.get("conflicts", [])
                if conflict.get("type") == "temporal_overlap"
            }

            expected_pairs: set[frozenset[str]] = set()
            for i, left in enumerate(committed):
                for right in committed[i + 1 :]:
                    if left["satellite_id"] != right["satellite_id"]:
                        continue
                    if _overlaps(left["start"], left["end"], right["start"], right["end"]):
                        expected_pairs.add(
                            frozenset({left["target_id"], right["target_id"]})
                        )

            assert actual_pairs == expected_pairs, {
                "seed": seed,
                "expected_pairs": sorted(sorted(pair) for pair in expected_pairs),
                "actual_pairs": sorted(sorted(pair) for pair in actual_pairs),
                "recompute": recompute,
            }
        finally:
            _delete_workspace(workspace_id)


def test_default_workspace_direct_commit_is_isolated_from_other_workspaces() -> None:
    """Implicit default direct commits should ignore conflicts in unrelated workspaces."""
    other_workspace_id = _create_workspace(f"extreme_default_iso_{uuid.uuid4().hex[:8]}")
    default_acquisition_ids: list[str] = []
    try:
        base = datetime.now(timezone.utc) + timedelta(days=50)
        _direct_commit(
            other_workspace_id,
            "OTHER-WS",
            "SAT-EXTREME-ISO",
            _iso(base),
            _iso(base + timedelta(minutes=5)),
        )

        default_commit = _direct_commit_default(
            "DEFAULT-WS",
            "SAT-EXTREME-ISO",
            _iso(base),
            _iso(base + timedelta(minutes=5)),
        )
        assert default_commit["committed"] == 1, default_commit
        default_acquisition_ids = default_commit.get("acquisition_ids", [])

        default_state = _get("/schedule/state", {"workspace_id": "default"})
        other_state = _get("/schedule/state", {"workspace_id": other_workspace_id})

        assert len(default_state["state"]["acquisitions"]) >= 1, default_state
        assert any(
            acquisition["target_id"] == "DEFAULT-WS"
            for acquisition in default_state["state"]["acquisitions"]
        ), default_state
        assert any(
            acquisition["target_id"] == "OTHER-WS"
            for acquisition in other_state["state"]["acquisitions"]
        ), other_state
    finally:
        if default_acquisition_ids:
            _bulk_delete("default", default_acquisition_ids)
        _delete_workspace(other_workspace_id)
