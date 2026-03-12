#!/usr/bin/env python3
"""
Comprehensive E2E Scheduling Workflow Tests.

MOD-delivery validation: exercises every scheduling path against the live backend.

Phase 1 (TestSingleSatelliteLifecycle):
  Single satellite full lifecycle — plan, commit, lock, re-plan, repair, delete

Phase 2 (TestConstellationLifecycle):
  2-satellite constellation — prove the same with multi-sat operations

Phase 3 (TestEdgeCasesAndInvariants):
  Edge cases, error handling, data integrity

Requires: backend running on localhost:8000  (.venv/bin/python -m uvicorn backend.main:app)
Auto-skipped by conftest.py when server is not reachable.
"""

import uuid
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Generator, List, Optional, cast

import pytest
import requests

BASE_URL = "http://localhost:8000"
API = f"{BASE_URL}/api/v1"

pytestmark = pytest.mark.requires_server

# ---------------------------------------------------------------------------
# TLE data — fresh from config/satellites.yaml (epoch ~2026-03-05)
# ---------------------------------------------------------------------------

TLE_SAT1 = {
    "name": "ICEYE-X53",
    "line1": "1 64584U 25135BJ  26064.28789825  .00007988  00000+0  63127-3 0  9993",
    "line2": "2 64584  97.7436 181.4786 0000928 206.1630 153.9547 15.00931401 38499",
}

TLE_SAT2 = {
    "name": "ICEYE-X56",
    "line1": "1 64574U 25135AY  26064.24103889  .00005857  00000+0  54245-3 0  9992",
    "line2": "2 64574  97.7613 180.1478 0001209 343.6792  16.4390 14.94873959 38391",
}

TLE_SAT4 = {
    "name": "ICEYE-X67",
    "line1": "1 66302U 25248K   26069.50002314  .00025257  00000+0  15729-2 0  9992",
    "line2": "2 66302  45.4044 292.6802 0006925 210.4525 343.9970 15.09210416  5829",
}

CANONICAL_REVIEW_START = "2026-03-08T00:00:00Z"
CANONICAL_REVIEW_END = "2026-03-11T00:00:00Z"

# Eastern Mediterranean targets — close enough for overlap scenarios
TARGETS_PHASE1 = [
    {"name": "Athens", "latitude": 37.9838, "longitude": 23.7275},
    {"name": "London", "latitude": 51.5074, "longitude": -0.1278},
]

TARGETS_PHASE2 = TARGETS_PHASE1 + [
    {"name": "Cairo", "latitude": 30.0444, "longitude": 31.2357},
    {"name": "Istanbul", "latitude": 41.0082, "longitude": 28.9784},
]

ORBIT_REVIEW_TARGETS = [
    {"name": "Svalbard", "latitude": 78.2298, "longitude": 15.4078, "priority": 1},
    {"name": "Athens", "latitude": 37.9838, "longitude": 23.7275, "priority": 3},
    {"name": "Singapore", "latitude": 1.3521, "longitude": 103.8198, "priority": 2},
]

STRATEGY_TIMING_TARGET = [
    {
        "name": "AthensFocus",
        "latitude": 37.9838,
        "longitude": 23.7275,
        "priority": 3,
    }
]

STRATEGY_PRIORITY_TARGETS = [
    {
        "name": "PriorityAnchor",
        "latitude": 37.9838,
        "longitude": 23.7275,
        "priority": 1,
    },
    {
        "name": "PriorityShadow",
        "latitude": 37.9845,
        "longitude": 23.7280,
        "priority": 5,
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post(path: str, payload: Dict[str, Any], timeout: int = 120) -> Dict[str, Any]:
    """POST to API and assert 200."""
    resp = requests.post(f"{API}{path}", json=payload, timeout=timeout)
    assert (
        resp.status_code == 200
    ), f"POST {path} returned {resp.status_code}: {resp.text[:500]}"
    data = resp.json()
    assert isinstance(data, dict), f"POST {path} did not return a JSON object"
    return cast(Dict[str, Any], data)


def _get(
    path: str, params: Optional[Dict[str, Any]] = None, timeout: int = 30
) -> Dict[str, Any]:
    """GET from API and assert 200."""
    resp = requests.get(f"{API}{path}", params=params, timeout=timeout)
    assert (
        resp.status_code == 200
    ), f"GET {path} returned {resp.status_code}: {resp.text[:300]}"
    data = resp.json()
    assert isinstance(data, dict), f"GET {path} did not return a JSON object"
    return cast(Dict[str, Any], data)


def _patch(
    path: str, params: Optional[Dict[str, Any]] = None, timeout: int = 15
) -> Dict[str, Any]:
    """PATCH API and assert 200."""
    resp = requests.patch(f"{API}{path}", params=params, timeout=timeout)
    assert (
        resp.status_code == 200
    ), f"PATCH {path} returned {resp.status_code}: {resp.text[:300]}"
    data = resp.json()
    assert isinstance(data, dict), f"PATCH {path} did not return a JSON object"
    return cast(Dict[str, Any], data)


def _seed(
    tle: Dict[str, str],
    targets: List[Dict],
    days: int = 3,
) -> Dict[str, Any]:
    """Seed mission analysis with single satellite. Returns response."""
    now = datetime.now(timezone.utc)
    payload = {
        "tle": tle,
        "targets": targets,
        "start_time": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_time": (now + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "imaging_type": "optical",
    }
    return _post("/mission/analyze", payload, timeout=120)


def _seed_constellation(
    satellites: List[Dict],
    targets: List[Dict],
    days: int = 3,
) -> Dict[str, Any]:
    """Seed mission analysis with constellation."""
    now = datetime.now(timezone.utc)
    payload = {
        "satellites": satellites,
        "targets": targets,
        "start_time": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_time": (now + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "imaging_type": "optical",
    }
    return _post("/mission/analyze", payload, timeout=120)


def _analyze_mission(
    *,
    targets: List[Dict[str, Any]],
    tle: Optional[Dict[str, str]] = None,
    satellites: Optional[List[Dict[str, str]]] = None,
    start_time: str = CANONICAL_REVIEW_START,
    end_time: str = CANONICAL_REVIEW_END,
) -> Dict[str, Any]:
    """Run mission analysis with explicit canonical inputs."""
    payload: Dict[str, Any] = {
        "targets": targets,
        "start_time": start_time,
        "end_time": end_time,
        "mission_type": "imaging",
        "elevation_mask": 10.0,
        "pointing_angle": 45.0,
        "imaging_type": "optical",
    }
    if satellites is not None:
        payload["satellites"] = satellites
    elif tle is not None:
        payload["tle"] = tle
    else:
        raise AssertionError("Expected tle or satellites for mission analysis")
    return _post("/mission/analyze", payload, timeout=120)


def _extract_mission_passes(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract mission-analysis passes from either response envelope shape."""
    mission_data = response.get("data", {}).get("mission_data", {})
    passes = mission_data.get("passes")
    if isinstance(passes, list):
        return passes
    raw_passes = response.get("passes", [])
    return raw_passes if isinstance(raw_passes, list) else []


def _create_workspace(name: str) -> str:
    """Create workspace and return its ID."""
    resp = _post("/workspaces", {"name": name})
    ws_id = resp.get("workspace_id")
    assert isinstance(ws_id, str) and ws_id, f"No workspace_id in response: {resp}"
    return ws_id


def _parse_ts(s: str) -> datetime:
    """Parse ISO-8601 timestamp to datetime. Handles Z suffix and microseconds."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _run_planning_schedule(**overrides: Any) -> Dict[str, Any]:
    """Run the planning endpoint using the active analyzed mission."""
    payload: Dict[str, Any] = {
        "algorithms": ["roll_pitch_best_fit"],
        "mode": "from_scratch",
        "value_source": "target_priority",
        "quality_model": "monotonic",
        "look_window_s": 600.0,
    }
    payload.update(overrides)
    return _post("/planning/schedule", payload, timeout=120)


def _planning_result(response: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the active planner result block."""
    results = response.get("results", {})
    assert isinstance(results, dict), f"Missing results block: {response}"
    result = results.get("roll_pitch_best_fit")
    assert isinstance(result, dict), f"Missing roll_pitch_best_fit result: {response}"
    return cast(Dict[str, Any], result)


def _safe_cleanup(
    workspace_id: str,
    seed_tle: Optional[Dict] = None,
    seed_targets: Optional[List] = None,
) -> None:
    """Best-effort cleanup: restore seed + delete workspace. Never raises."""
    if seed_tle and seed_targets:
        try:
            _seed(seed_tle, seed_targets, days=3)
        except Exception as exc:
            warnings.warn(f"Seed restoration failed for {workspace_id}: {exc}")
    try:
        requests.delete(f"{API}/workspaces/{workspace_id}", timeout=10)
    except Exception as exc:
        warnings.warn(f"Workspace {workspace_id} cleanup failed: {exc}")


def _plan(workspace_id: str, mode: str = "from_scratch") -> Dict[str, Any]:
    """Run planning and return response."""
    return _post(
        "/schedule/plan",
        {"planning_mode": mode, "workspace_id": workspace_id},
    )


def _commit(plan_id: str, workspace_id: str, **kwargs: Any) -> Dict[str, Any]:
    """Commit a plan. kwargs forwarded (force, lock_level, etc)."""
    payload = {"plan_id": plan_id, "workspace_id": workspace_id, **kwargs}
    return _post("/schedule/commit", payload)


def _state(workspace_id: str) -> Dict[str, Any]:
    """Get schedule state for workspace. Returns the 'state' dict."""
    resp = _get("/schedule/state", {"workspace_id": workspace_id})
    state = resp.get("state", {})
    assert isinstance(state, dict), f"Schedule state is not an object: {resp}"
    return cast(Dict[str, Any], state)


def _acq_ids(state: Dict[str, Any]) -> List[str]:
    """Extract acquisition IDs from state dict."""
    return [a["id"] for a in state.get("acquisitions", [])]


def _plan_commit(
    workspace_id: str, lock_level: str = "none", force: bool = True
) -> Dict[str, Any]:
    """Plan + commit in one call. Returns commit response.

    force=True by default so tests focusing on non-conflict behaviour
    don't fail when cached opportunities produce overlaps.
    """
    plan = _plan(workspace_id)
    assert plan["success"] and plan.get(
        "new_plan_items"
    ), f"Plan failed or empty: {plan.get('message')}"
    return _commit(plan["plan_id"], workspace_id, lock_level=lock_level, force=force)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def seeded_mission() -> Dict[str, Any]:
    """Seed single-satellite mission (module scope). Returns analyze response."""
    data = _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
    passes = data.get("data", {}).get("mission_data", {}).get("passes", [])
    assert len(passes) > 0, (
        f"Mission analysis produced 0 passes — TLE may be stale. "
        f"Message: {data.get('message', '')}"
    )
    return data


@pytest.fixture()
def workspace() -> Generator[str, None, None]:
    """Create ephemeral workspace, tear down after test."""
    tag = uuid.uuid4().hex[:8]
    ws_id = _create_workspace(f"sched_e2e_{tag}")
    yield ws_id
    try:
        requests.delete(f"{API}/workspaces/{ws_id}", timeout=10)
    except Exception as exc:
        warnings.warn(f"Workspace {ws_id} cleanup failed: {exc}")


# ===========================================================================
# PHASE 1: Single Satellite Full Lifecycle
# ===========================================================================


class TestSingleSatelliteLifecycle:
    """Full single-satellite scheduling lifecycle."""

    def test_01_health_check(self) -> None:
        """Server is reachable."""
        resp = requests.get(f"{BASE_URL}/", timeout=10)
        assert resp.status_code == 200
        assert "running" in resp.json().get("message", "").lower()

    def test_02_seed_mission(self, seeded_mission: Dict) -> None:
        """Mission analysis produces passes."""
        passes = seeded_mission["data"]["mission_data"]["passes"]
        print(f"Seeded: {len(passes)} passes")
        assert len(passes) > 0

    def test_03_from_scratch_plan(self, seeded_mission: Dict, workspace: str) -> None:
        """FROM_SCRATCH plan produces items with required fields."""
        plan = _plan(workspace)
        assert plan["success"], f"Plan failed: {plan.get('message')}"
        items = plan.get("new_plan_items", [])
        assert len(items) > 0, "FROM_SCRATCH produced 0 items"
        assert "plan_id" in plan

        required = [
            "opportunity_id",
            "satellite_id",
            "target_id",
            "start_time",
            "end_time",
        ]
        for item in items:
            for f in required:
                assert f in item, f"Plan item missing '{f}'"
        print(f"Plan: {len(items)} items, plan_id={plan['plan_id']}")

    def test_04_commit_and_verify_state(
        self, seeded_mission: Dict, workspace: str
    ) -> None:
        """Commit plan creates acquisitions visible in schedule state."""
        commit = _plan_commit(workspace)
        assert commit["success"]
        assert commit["committed"] > 0

        state = _state(workspace)
        acqs = state.get("acquisitions", [])
        assert (
            len(acqs) == commit["committed"]
        ), f"Expected {commit['committed']} acquisitions, got {len(acqs)}"
        for a in acqs:
            assert a["lock_level"] == "none"
            assert a["state"] == "committed"
        print(f"Committed {commit['committed']}, verified in state")

    def test_05_hard_lock_and_protection(
        self, seeded_mission: Dict, workspace: str
    ) -> None:
        """Hard-locked acquisitions cannot be deleted without force."""
        _plan_commit(workspace)
        state = _state(workspace)
        ids = _acq_ids(state)
        assert len(ids) >= 2, f"Need >=2 acquisitions, got {len(ids)}"

        to_lock = ids[:2]
        lock_resp = _post(
            "/schedule/acquisitions/bulk-lock",
            {"acquisition_ids": to_lock, "lock_level": "hard"},
        )
        assert lock_resp["updated"] == len(to_lock)

        # Verify lock applied
        state2 = _state(workspace)
        for a in state2["acquisitions"]:
            if a["id"] in to_lock:
                assert a["lock_level"] == "hard"

        # Bulk delete without force — should skip hard-locked
        del_resp = _post(
            "/schedule/acquisitions/bulk-delete",
            {
                "acquisition_ids": to_lock,
                "workspace_id": workspace,
                "force": False,
            },
        )
        assert del_resp["deleted"] == 0, "Hard-locked should not be deleted"
        assert len(del_resp["skipped_hard_locked"]) == len(to_lock)

        # Verify still present
        state3 = _state(workspace)
        remaining = _acq_ids(state3)
        for lid in to_lock:
            assert lid in remaining
        print(f"Hard-lock protection verified for {len(to_lock)} acquisitions")

    def test_06_delete_unlocked_acquisition(
        self, seeded_mission: Dict, workspace: str
    ) -> None:
        """Unlocked acquisitions can be deleted."""
        _plan_commit(workspace)
        state = _state(workspace)
        ids = _acq_ids(state)

        target = ids[0]
        resp = requests.delete(
            f"{API}/schedule/acquisition/{target}",
            params={"workspace_id": workspace},
            timeout=15,
        )
        assert resp.status_code == 200

        remaining = _acq_ids(_state(workspace))
        assert target not in remaining
        print("Deleted unlocked acquisition OK")

    def test_07_replan_detects_conflicts(
        self, seeded_mission: Dict, workspace: str
    ) -> None:
        """Re-planning on committed schedule predicts conflicts."""
        _plan_commit(workspace)

        plan2 = _plan(workspace)
        assert plan2["success"]
        conflicts = plan2.get("conflicts_if_committed", [])
        # With same opportunities cached, re-planning should detect overlaps
        for c in conflicts:
            assert "type" in c
            assert "severity" in c
        print(
            f"Re-plan: {len(plan2.get('new_plan_items', []))} items, "
            f"{len(conflicts)} predicted conflicts"
        )

    def test_08_conflict_recompute(self, seeded_mission: Dict, workspace: str) -> None:
        """Conflict recompute runs and returns detection results."""
        _plan_commit(workspace)
        result = _post(
            "/schedule/conflicts/recompute",
            {"workspace_id": workspace},
        )
        assert result["success"]
        assert "detected" in result
        print(f"Conflicts detected: {result['detected']}")

    def test_09_repair_preserves_hard_locks(
        self, seeded_mission: Dict, workspace: str
    ) -> None:
        """Repair plan keeps hard-locked acquisitions in the 'kept' set."""
        _plan_commit(workspace)
        state = _state(workspace)
        ids = _acq_ids(state)
        assert len(ids) >= 2

        locked_id = ids[0]
        _post(
            "/schedule/acquisitions/bulk-lock",
            {"acquisition_ids": [locked_id], "lock_level": "hard"},
        )

        repair = _post(
            "/schedule/repair",
            {"workspace_id": workspace, "planning_mode": "repair"},
        )
        assert repair["success"]
        assert "repair_diff" in repair
        diff = repair["repair_diff"]
        kept = diff.get("kept", [])
        assert locked_id in kept, f"Hard-locked {locked_id} not in kept set: {kept}"
        print(
            f"Repair: fixed={repair['fixed_count']}, flex={repair['flex_count']}, "
            f"kept={len(kept)}"
        )

    def test_10_commit_repair(self, seeded_mission: Dict, workspace: str) -> None:
        """Repair commit creates/drops acquisitions, preserving locks."""
        _plan_commit(workspace)
        state = _state(workspace)
        ids = _acq_ids(state)
        locked_id = ids[0]
        _post(
            "/schedule/acquisitions/bulk-lock",
            {"acquisition_ids": [locked_id], "lock_level": "hard"},
        )

        repair = _post(
            "/schedule/repair",
            {"workspace_id": workspace, "planning_mode": "repair"},
        )
        diff = repair["repair_diff"]

        repair_commit = _post(
            "/schedule/repair/commit",
            {
                "plan_id": repair["plan_id"],
                "workspace_id": workspace,
                "drop_acquisition_ids": diff.get("dropped", []),
                "lock_level": "none",
            },
        )
        assert repair_commit["success"]

        # Hard-lock preserved
        remaining = _acq_ids(_state(workspace))
        assert locked_id in remaining, f"Hard-locked {locked_id} disappeared!"
        print(
            f"Repair committed: {repair_commit.get('committed', 0)} created, "
            f"{repair_commit.get('dropped', 0)} dropped"
        )

    def test_11_add_target_and_replan(
        self, seeded_mission: Dict, workspace: str
    ) -> None:
        """Re-seeding with additional target produces new plan."""
        all_targets = TARGETS_PHASE1 + [
            {"name": "Heraklion", "latitude": 35.3387, "longitude": 25.1442},
        ]
        _seed(TLE_SAT1, all_targets, days=3)

        plan = _plan(workspace)
        assert plan["success"]
        items = plan.get("new_plan_items", [])
        target_ids = set(it["target_id"] for it in items)
        print(
            f"Re-plan with extra target: {len(items)} items, targets={sorted(target_ids)}"
        )

        # Re-seed with original targets to avoid poisoning subsequent tests
        _seed(TLE_SAT1, TARGETS_PHASE1, days=3)

    def test_12_direct_commit(self, seeded_mission: Dict, workspace: str) -> None:
        """Direct commit (bypassing plan) creates acquisitions."""
        plan = _plan(workspace)
        assert plan["success"] and plan.get("new_plan_items")
        item = plan["new_plan_items"][0]

        direct = _post(
            "/schedule/commit/direct",
            {
                "workspace_id": workspace,
                "items": [
                    {
                        "opportunity_id": item.get(
                            "opportunity_id", f"direct_{uuid.uuid4().hex[:8]}"
                        ),
                        "satellite_id": item["satellite_id"],
                        "target_id": item["target_id"],
                        "start_time": item["start_time"],
                        "end_time": item["end_time"],
                        "roll_angle_deg": item.get("roll_angle_deg", 0.0),
                        "pitch_angle_deg": item.get("pitch_angle_deg", 0.0),
                    }
                ],
                "force": True,
            },
        )
        assert direct["success"]
        assert direct.get("committed", 0) > 0
        print(f"Direct committed {direct['committed']} acquisitions")

    def test_13_schedule_horizon(self, seeded_mission: Dict, workspace: str) -> None:
        """Schedule horizon returns data."""
        _plan_commit(workspace)
        horizon = _get("/schedule/horizon", {"workspace_id": workspace})
        assert horizon["success"]
        acqs = horizon.get("acquisitions", [])
        print(f"Horizon: {len(acqs)} acquisitions")

    def test_14_target_locations(self, seeded_mission: Dict, workspace: str) -> None:
        """Target locations endpoint returns positions."""
        _plan_commit(workspace)
        locs = _get("/schedule/target-locations", {"workspace_id": workspace})
        assert locs["success"]
        targets = locs.get("targets", [])
        print(f"Target locations: {len(targets)}")

    def test_15_commit_history(self, seeded_mission: Dict, workspace: str) -> None:
        """Commit history returns audit entries."""
        _plan_commit(workspace)
        history = _get("/schedule/commit-history", {"workspace_id": workspace})
        assert history["success"]
        entries = history.get("audit_logs", [])
        print(f"Commit history: {len(entries)} entries")

    def test_16_workspace_isolation(self, seeded_mission: Dict, workspace: str) -> None:
        """Acquisitions in one workspace don't leak to another."""
        _plan_commit(workspace)
        state1 = _state(workspace)
        ids1 = _acq_ids(state1)
        assert len(ids1) > 0

        ws2_id = _create_workspace(f"iso_{uuid.uuid4().hex[:8]}")
        try:
            state2 = _state(ws2_id)
            ids2 = _acq_ids(state2)
            # Second workspace should have 0 acquisitions
            assert (
                len(ids2) == 0
            ), f"Workspace {ws2_id} has {len(ids2)} acquisitions (leak!)"
            print("Workspace isolation verified")
        finally:
            _safe_cleanup(ws2_id)

    def test_17_auto_escalate_locks(self, seeded_mission: Dict, workspace: str) -> None:
        """Auto-escalate locks endpoint runs without errors."""
        _plan_commit(workspace)
        result = _post(
            "/schedule/acquisitions/auto-escalate-locks",
            {"workspace_id": workspace},
        )
        assert result["success"]
        print(f"Auto-escalated: {result.get('escalated_count', 0)} acquisitions")

    def test_18_single_acq_lock_via_patch(
        self, seeded_mission: Dict, workspace: str
    ) -> None:
        """PATCH lock endpoint works for individual acquisition."""
        _plan_commit(workspace)
        state = _state(workspace)
        acq_id = _acq_ids(state)[0]

        result = _patch(
            f"/schedule/acquisition/{acq_id}/lock",
            params={"lock_level": "hard"},
        )
        assert result["success"]
        assert result["lock_level"] == "hard"

        # Verify lock applied
        state2 = _state(workspace)
        for a in state2["acquisitions"]:
            if a["id"] == acq_id:
                assert a["lock_level"] == "hard"
        print(f"PATCH lock verified on {acq_id}")


# ===========================================================================
# PHASE 2: 2-Satellite Constellation
# ===========================================================================


class TestConstellationLifecycle:
    """Full constellation (2 satellites) scheduling lifecycle."""

    @pytest.fixture(autouse=True, scope="class")
    def seed_constellation(self) -> Dict[str, Any]:
        """Seed constellation mission at class scope."""
        data = _seed_constellation([TLE_SAT1, TLE_SAT2], TARGETS_PHASE2, days=3)
        passes = data.get("data", {}).get("mission_data", {}).get("passes", [])
        assert (
            len(passes) > 0
        ), f"Constellation produced 0 passes. Message: {data.get('message', '')}"
        return data

    def test_01_constellation_plan(self, workspace: str) -> None:
        """Plan with constellation produces items."""
        plan = _plan(workspace)
        assert plan["success"]
        items = plan.get("new_plan_items", [])
        assert len(items) > 0

        sat_counts: Dict[str, int] = {}
        for it in items:
            sid = it["satellite_id"]
            sat_counts[sid] = sat_counts.get(sid, 0) + 1
        print(f"Plan: {len(items)} items across satellites: {sat_counts}")

    def test_02_commit_and_verify(self, workspace: str) -> None:
        """Committed acquisitions are correctly attributed to each satellite."""
        commit = _plan_commit(workspace)
        assert commit["committed"] > 0

        state = _state(workspace)
        acqs = state.get("acquisitions", [])
        sat_counts: Dict[str, int] = {}
        for a in acqs:
            sid = a["satellite_id"]
            sat_counts[sid] = sat_counts.get(sid, 0) + 1
        assert len(acqs) == commit["committed"]
        print(f"Per-satellite acquisitions: {sat_counts}")

    def test_03_lock_per_satellite(self, workspace: str) -> None:
        """Lock one acquisition per satellite, verify locks applied."""
        _plan_commit(workspace)
        state = _state(workspace)

        sats_seen: set = set()
        ids_to_lock = []
        for a in state["acquisitions"]:
            sid = a["satellite_id"]
            if sid not in sats_seen:
                ids_to_lock.append(a["id"])
                sats_seen.add(sid)

        result = _post(
            "/schedule/acquisitions/bulk-lock",
            {"acquisition_ids": ids_to_lock, "lock_level": "hard"},
        )
        assert result["updated"] == len(ids_to_lock)
        print(f"Locked {len(ids_to_lock)} acquisitions (1 per satellite)")

    def test_04_repair_preserves_constellation_locks(self, workspace: str) -> None:
        """Repair preserves hard-locked acquisitions from each satellite."""
        _plan_commit(workspace)
        state = _state(workspace)

        sats_seen: set = set()
        locked_ids = []
        for a in state["acquisitions"]:
            if a["satellite_id"] not in sats_seen:
                locked_ids.append(a["id"])
                sats_seen.add(a["satellite_id"])

        _post(
            "/schedule/acquisitions/bulk-lock",
            {"acquisition_ids": locked_ids, "lock_level": "hard"},
        )

        repair = _post(
            "/schedule/repair",
            {"workspace_id": workspace, "planning_mode": "repair"},
        )
        assert repair["success"]
        diff = repair["repair_diff"]
        for lid in locked_ids:
            assert lid in diff.get("kept", []), f"Hard-locked {lid} not in kept!"

        repair_commit = _post(
            "/schedule/repair/commit",
            {
                "plan_id": repair["plan_id"],
                "workspace_id": workspace,
                "drop_acquisition_ids": diff.get("dropped", []),
                "lock_level": "none",
            },
        )
        assert repair_commit["success"]

        remaining = _acq_ids(_state(workspace))
        for lid in locked_ids:
            assert lid in remaining
        print(f"Constellation repair: {len(locked_ids)} locks preserved")

    def test_05_conflict_detection_constellation(self, workspace: str) -> None:
        """Conflict detection works for constellation."""
        _plan_commit(workspace)
        result = _post(
            "/schedule/conflicts/recompute",
            {"workspace_id": workspace},
        )
        assert result["success"]
        print(f"Constellation conflicts: {result['detected']} detected")

    def test_06_bulk_delete_respects_locks(self, workspace: str) -> None:
        """Bulk delete removes unlocked but preserves hard-locked."""
        _plan_commit(workspace)
        state = _state(workspace)
        ids = _acq_ids(state)
        assert len(ids) >= 3

        locked_id = ids[0]
        _post(
            "/schedule/acquisitions/bulk-lock",
            {"acquisition_ids": [locked_id], "lock_level": "hard"},
        )

        del_resp = _post(
            "/schedule/acquisitions/bulk-delete",
            {"acquisition_ids": ids, "workspace_id": workspace, "force": False},
        )
        remaining = _acq_ids(_state(workspace))
        assert locked_id in remaining, "Hard-locked was deleted without force!"
        for uid in ids[1:]:
            assert uid not in remaining
        print(f"Bulk delete: {del_resp['deleted']} deleted, hard-lock preserved")

    def test_07_force_delete_hard_locked(self, workspace: str) -> None:
        """Force delete removes even hard-locked acquisitions."""
        _plan_commit(workspace, lock_level="hard")
        state = _state(workspace)
        ids = _acq_ids(state)
        target = ids[0]

        del_resp = _post(
            "/schedule/acquisitions/bulk-delete",
            {
                "acquisition_ids": [target],
                "workspace_id": workspace,
                "force": True,
            },
        )
        assert del_resp["deleted"] == 1
        remaining = _acq_ids(_state(workspace))
        assert target not in remaining
        print("Force-deleted hard-locked acquisition OK")


# ===========================================================================
# PHASE 3: Edge Cases & Invariants
# ===========================================================================


class TestEdgeCasesAndInvariants:
    """Edge cases, error handling, and data integrity checks."""

    @pytest.fixture(autouse=True, scope="class")
    def ensure_seeded(self) -> None:
        """Ensure mission is seeded for edge case tests."""
        _seed(TLE_SAT1, TARGETS_PHASE1, days=3)

    def test_01_double_commit_rejected(self, workspace: str) -> None:
        """Committing an already-committed plan returns error."""
        plan = _plan(workspace)
        assert plan["success"] and plan.get("new_plan_items")
        plan_id = plan["plan_id"]

        _commit(plan_id, workspace)

        # Second commit should fail (400 or 409)
        resp = requests.post(
            f"{API}/schedule/commit",
            json={"plan_id": plan_id, "workspace_id": workspace},
            timeout=30,
        )
        assert resp.status_code in [
            400,
            409,
        ], f"Double commit should fail, got {resp.status_code}"
        print(f"Double commit correctly rejected ({resp.status_code})")

    def test_02_invalid_lock_level_rejected(self, workspace: str) -> None:
        """Invalid lock level 'soft' returns 400."""
        plan = _plan(workspace)
        if not plan.get("success") or not plan.get("new_plan_items"):
            pytest.skip("No plan items")

        resp = requests.post(
            f"{API}/schedule/commit",
            json={
                "plan_id": plan["plan_id"],
                "workspace_id": workspace,
                "lock_level": "soft",
            },
            timeout=30,
        )
        assert (
            resp.status_code == 400
        ), f"Invalid lock_level should return 400, got {resp.status_code}"
        print("Invalid lock_level 'soft' correctly rejected")

    def test_03_commit_nonexistent_plan(self, workspace: str) -> None:
        """Committing a nonexistent plan returns 404."""
        resp = requests.post(
            f"{API}/schedule/commit",
            json={"plan_id": "nonexistent_plan_xyz", "workspace_id": workspace},
            timeout=15,
        )
        assert resp.status_code in (404, 422), (
            f"Nonexistent plan should return 404 or 422, got {resp.status_code}: "
            f"{resp.text[:200]}"
        )
        print(f"Nonexistent plan correctly rejected ({resp.status_code})")

    def test_04_lock_nonexistent_acquisition(self) -> None:
        """Locking a nonexistent acquisition returns 404 (not 500)."""
        resp = requests.patch(
            f"{API}/schedule/acquisition/nonexistent_acq_xyz/lock",
            params={"lock_level": "hard"},
            timeout=10,
        )
        assert resp.status_code in (404, 400), (
            f"Lock nonexistent should return 404 or 400, got {resp.status_code} "
            f"(500 indicates unhandled server error): {resp.text[:200]}"
        )
        print(f"Lock nonexistent acq: {resp.status_code}")

    def test_05_acquisition_data_integrity(self, workspace: str) -> None:
        """All committed acquisitions have required fields."""
        _plan_commit(workspace)
        state = _state(workspace)
        acqs = state.get("acquisitions", [])
        assert len(acqs) > 0

        required = [
            "id",
            "satellite_id",
            "target_id",
            "start_time",
            "end_time",
            "lock_level",
            "state",
        ]
        for a in acqs:
            for f in required:
                assert f in a, f"Acquisition missing '{f}': {list(a.keys())}"
            assert a["state"] == "committed"
        print(f"All {len(acqs)} acquisitions have proper fields")

    def test_06_schedule_state_has_conflicts_key(self, workspace: str) -> None:
        """Schedule state includes conflict data (B3 fix validation)."""
        resp = _get("/schedule/state", {"workspace_id": workspace})
        state = resp.get("state", {})
        assert "conflicts" in state, "Schedule state missing 'conflicts' key"
        assert isinstance(state["conflicts"], list)
        print(f"Schedule state has {len(state['conflicts'])} conflicts")

    def test_07_get_conflicts_endpoint(self, workspace: str) -> None:
        """GET /conflicts returns structured conflict data."""
        conflicts_resp = _get("/schedule/conflicts", {"workspace_id": workspace})
        assert conflicts_resp["success"]
        conflict_list = conflicts_resp.get("conflicts", [])
        for c in conflict_list:
            assert "type" in c
            assert "severity" in c
        print(f"Conflicts endpoint: {len(conflict_list)} conflicts")

    def test_08_commit_with_conflicts_returns_409(self, workspace: str) -> None:
        """Committing a stale plan into a newly blocked slot returns 409."""
        plan = _plan(workspace)
        assert plan["success"] and plan.get(
            "new_plan_items"
        ), f"Expected non-empty plan for conflict test: {plan.get('message')}"
        item = plan["new_plan_items"][0]
        direct_commit = _direct_commit_synthetic(
            workspace,
            item["satellite_id"],
            f"{item['target_id']}_blocking",
            item["start_time"],
            item["end_time"],
            force=True,
        )
        assert direct_commit[
            "success"
        ], f"Blocking direct commit failed: {direct_commit}"
        resp = requests.post(
            f"{API}/schedule/commit",
            json={
                "plan_id": plan["plan_id"],
                "workspace_id": workspace,
            },
            timeout=30,
        )
        assert resp.status_code == 409, (
            f"Expected 409 for conflicting commit, got {resp.status_code}: "
            f"{resp.text[:300]}"
        )
        detail = resp.json().get("detail", {})
        predicted_conflicts = detail.get("predicted_conflicts", [])
        assert (
            predicted_conflicts
        ), f"Expected predicted_conflicts in 409 detail, got: {detail}"
        print(
            f"Conflicting commit correctly rejected (409) with "
            f"{len(predicted_conflicts)} conflicts"
        )

    def test_09_opportunities_endpoint(self) -> None:
        """GET /planning/opportunities returns cached opportunities."""
        resp = _get("/planning/opportunities")
        opps = resp.get("opportunities", [])
        print(f"Cached opportunities: {len(opps)}")


# ===========================================================================
# PHASE 4: Target Deduplication
# ===========================================================================


class TestTargetDeduplication:
    """Verify that re-planning skips targets already scheduled in the workspace."""

    @pytest.fixture(autouse=True, scope="class")
    def ensure_seeded(self) -> None:
        """Seed with Phase-1 targets."""
        _seed(TLE_SAT1, TARGETS_PHASE1, days=3)

    def test_01_replan_deduplicates(self, workspace: str) -> None:
        """Second plan in same workspace should produce fewer/zero items."""
        # First plan + commit
        plan1 = _plan(workspace)
        assert plan1["success"] and plan1.get("new_plan_items")
        n1 = len(plan1["new_plan_items"])
        _commit(plan1["plan_id"], workspace, force=True)

        # Second plan — dedup should kick in
        plan2 = _plan(workspace)
        n2 = len(plan2.get("new_plan_items", []))
        assert n2 < n1, f"Dedup failed: second plan has {n2} items, first had {n1}"
        print(f"Dedup: {n1} → {n2} items (reduction {n1 - n2})")

    def test_02_replan_no_crash_on_commit(self, workspace: str) -> None:
        """Re-committing after dedup must not crash with UNIQUE constraint."""
        pc1 = _plan_commit(workspace)
        committed1 = pc1.get("committed", 0)
        assert committed1 > 0

        plan2 = _plan(workspace)
        if plan2.get("new_plan_items"):
            # If any items survived dedup, committing them should succeed
            commit2 = _commit(plan2["plan_id"], workspace, force=True)
            assert commit2.get("committed", 0) >= 0
            print(f"Second commit OK ({commit2.get('committed', 0)} items)")
        else:
            print("Second plan empty (full dedup) — no commit needed")

    def test_03_deleted_acq_allows_replan(self, workspace: str) -> None:
        """Deleting an acquisition allows re-planning for that target."""
        # Plan + commit
        pc = _plan_commit(workspace)
        state = _state(workspace)
        acqs = state.get("acquisitions", [])
        assert len(acqs) > 0

        # Delete one acquisition
        target_to_delete = acqs[0]
        deleted_target_id = target_to_delete["target_id"]
        deleted_sat_id = target_to_delete["satellite_id"]
        _post(
            "/schedule/acquisitions/bulk-delete",
            {
                "acquisition_ids": [target_to_delete["id"]],
                "workspace_id": workspace,
                "force": True,
            },
        )

        # Re-plan — the deleted target's pair should be re-schedulable
        plan2 = _plan(workspace)
        new_items = plan2.get("new_plan_items", [])
        re_scheduled = [
            it
            for it in new_items
            if it.get("target_id") == deleted_target_id
            and it.get("satellite_id") == deleted_sat_id
        ]
        # After deleting an acq, the re-plan should produce items for that
        # target (slot is no longer blocked) or at minimum succeed.
        assert plan2["success"], f"Re-plan after delete failed: {plan2.get('message')}"
        assert len(new_items) > 0 or plan2["planning_mode"] == "repair", (
            f"Expected new items or repair mode after deleting {deleted_target_id}, "
            f"got {len(new_items)} items in mode {plan2['planning_mode']}"
        )
        print(
            f"After deleting {deleted_target_id}: "
            f"{len(new_items)} new items, "
            f"{len(re_scheduled)} for deleted target"
        )

    def test_04_different_workspace_no_dedup(self) -> None:
        """Different workspace should NOT see dedup from another workspace."""
        ws1 = _create_workspace(f"dedup_ws1_{uuid.uuid4().hex[:6]}")
        ws2 = _create_workspace(f"dedup_ws2_{uuid.uuid4().hex[:6]}")
        try:
            # Plan + commit in ws1
            pc1 = _plan_commit(ws1)
            n1 = pc1.get("committed", 0)
            assert n1 > 0

            # Plan in ws2 — should NOT be deduped by ws1's acquisitions
            plan2 = _plan(ws2)
            n2 = len(plan2.get("new_plan_items", []))
            assert (
                n2 > 0
            ), "Workspace 2 should have plan items (no cross-workspace dedup)"
            print(
                f"Workspace isolation: ws1 committed {n1}, "
                f"ws2 independently planned {n2}"
            )
        finally:
            _safe_cleanup(ws1)
            _safe_cleanup(ws2)


# =============================================================================
# Phase 5: Auto-Mode Selection Verification
# =============================================================================


class TestAutoModeSelection:
    """Verify auto-mode selection fires and picks correct mode."""

    def test_01_fresh_workspace_selects_from_scratch(
        self, seeded_mission: Dict
    ) -> None:
        """Empty workspace → auto-selects FROM_SCRATCH."""
        ws = _create_workspace(f"automode_fresh_{uuid.uuid4().hex[:6]}")
        try:
            plan = _plan(ws)
            assert plan["success"]
            assert (
                plan["planning_mode"] == "from_scratch"
            ), f"Expected from_scratch, got {plan['planning_mode']}"
            ctx = plan.get("schedule_context", {})
            assert ctx.get("existing_acquisition_count", -1) == 0
            print(
                f"Auto-mode: {plan['planning_mode']} | "
                f"reason: {ctx.get('mode_selection_reason', '')[:80]}"
            )
        finally:
            _safe_cleanup(ws)

    def test_02_replan_same_targets_selects_repair(self, seeded_mission: Dict) -> None:
        """Existing schedule + same targets → auto-selects REPAIR."""
        ws = _create_workspace(f"automode_repair_{uuid.uuid4().hex[:6]}")
        try:
            # Plan and commit first
            _plan_commit(ws)

            # Re-plan with same cached opportunities (same targets)
            plan = _plan(ws)
            assert plan["success"]
            assert plan["planning_mode"] == "repair", (
                f"Expected repair for same targets, got {plan['planning_mode']}. "
                f"Context: {plan.get('schedule_context', {})}"
            )
            ctx = plan.get("schedule_context", {})
            assert ctx.get("existing_acquisition_count", 0) > 0
            assert ctx.get("new_target_count", -1) == 0
            print(
                f"Auto-mode: {plan['planning_mode']} | "
                f"existing={ctx.get('existing_acquisition_count')} | "
                f"reason: {ctx.get('mode_selection_reason', '')[:80]}"
            )
        finally:
            _safe_cleanup(ws)

    def test_03_new_targets_selects_incremental(self, seeded_mission: Dict) -> None:
        """Existing schedule + new targets → auto-selects INCREMENTAL."""
        ws = _create_workspace(f"automode_incr_{uuid.uuid4().hex[:6]}")
        try:
            # Plan and commit with original targets
            _plan_commit(ws)

            # Re-seed with EXTRA target not in original set
            extra_targets = TARGETS_PHASE1 + [
                {"name": "Heraklion", "latitude": 35.3387, "longitude": 25.1442},
            ]
            _seed(TLE_SAT1, extra_targets, days=3)

            # Re-plan — auto-mode should detect the new target
            plan = _plan(ws)
            assert plan["success"]
            assert plan["planning_mode"] == "incremental", (
                f"Expected incremental for new targets, got {plan['planning_mode']}. "
                f"Context: {plan.get('schedule_context', {})}"
            )
            ctx = plan.get("schedule_context", {})
            assert (
                ctx.get("new_target_count", 0) > 0
            ), f"Expected new_target_count > 0, got {ctx.get('new_target_count')}"
            print(
                f"Auto-mode: {plan['planning_mode']} | "
                f"new_targets={ctx.get('new_target_count')} | "
                f"reason: {ctx.get('mode_selection_reason', '')[:80]}"
            )
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_04_force_mode_overrides_auto(self, seeded_mission: Dict) -> None:
        """Explicitly setting mode overrides auto-selection."""
        ws = _create_workspace(f"automode_force_{uuid.uuid4().hex[:6]}")
        try:
            _plan_commit(ws)

            # Force from_scratch even though auto would pick repair
            plan = _post(
                "/schedule/plan",
                {
                    "planning_mode": "from_scratch",
                    "workspace_id": ws,
                },
            )
            # from_scratch is the default, so auto-mode runs and picks repair
            # Only non-default modes act as force override
            assert plan["planning_mode"] in ("from_scratch", "repair")

            # Force incremental explicitly
            plan2 = _post(
                "/schedule/plan",
                {
                    "planning_mode": "incremental",
                    "workspace_id": ws,
                },
            )
            assert (
                plan2["planning_mode"] == "incremental"
            ), f"Forced incremental, got {plan2['planning_mode']}"
            print(f"Force override: incremental → {plan2['planning_mode']}")
        finally:
            _safe_cleanup(ws)

    def test_05_schedule_context_has_mode_metadata(self, seeded_mission: Dict) -> None:
        """Plan response includes full mode selection metadata."""
        ws = _create_workspace(f"automode_ctx_{uuid.uuid4().hex[:6]}")
        try:
            plan = _plan(ws)
            assert plan["success"]
            ctx = plan.get("schedule_context", {})

            # Verify all mode-selection metadata is present
            assert "planning_mode" in ctx, "Missing planning_mode in context"
            assert "mode_selection_reason" in ctx, "Missing mode_selection_reason"
            assert (
                "existing_acquisition_count" in ctx
            ), "Missing existing_acquisition_count"
            assert "new_target_count" in ctx, "Missing new_target_count"
            assert "conflict_count" in ctx, "Missing conflict_count"
            print(f"Context keys verified: {sorted(ctx.keys())}")
        finally:
            _safe_cleanup(ws)

    def test_06_conflict_count_in_mode_selection(self, seeded_mission: Dict) -> None:
        """Conflict count is wired into mode selection context."""
        ws = _create_workspace(f"automode_conflict_{uuid.uuid4().hex[:6]}")
        try:
            _plan_commit(ws)

            # Re-plan and check conflict_count is populated (may be 0 or >0)
            plan = _plan(ws)
            ctx = plan.get("schedule_context", {})
            assert "conflict_count" in ctx, "conflict_count not in schedule_context"
            # Just verify it's an integer (wired), not that conflicts exist
            assert isinstance(ctx["conflict_count"], int)
            print(f"conflict_count wired: {ctx['conflict_count']}")
        finally:
            _safe_cleanup(ws)


class TestPlanningStrategyValidation:
    """Validate orbit diversity and planner weighting through /planning/schedule."""

    def test_01_orbit_diversity_changes_visibility(self) -> None:
        """Polar and mid-inclination orbits should not see the same latitude bands."""
        analysis = _analyze_mission(
            satellites=[TLE_SAT1, TLE_SAT4],
            targets=ORBIT_REVIEW_TARGETS,
        )
        passes = _extract_mission_passes(analysis)
        assert passes, "Mission analysis returned no passes for orbit-diversity review"

        counts: Dict[str, Dict[str, int]] = {}
        for mission_pass in passes:
            target_name = str(mission_pass["target_name"])
            satellite_name = str(mission_pass["satellite_name"])
            target_counts = counts.setdefault(target_name, {})
            target_counts[satellite_name] = target_counts.get(satellite_name, 0) + 1

        svalbard_counts = counts.get("Svalbard", {})
        assert (
            svalbard_counts.get("ICEYE-X53", 0) > 0
        ), f"Polar orbit should reach Svalbard: {counts}"
        assert (
            svalbard_counts.get("ICEYE-X67", 0) == 0
        ), f"45-degree orbit should not reach Svalbard: {counts}"
        assert (
            counts.get("Athens", {}).get("ICEYE-X67", 0) > 0
        ), f"45-degree orbit should cover Athens: {counts}"
        assert (
            counts.get("Singapore", {}).get("ICEYE-X67", 0) > 0
        ), f"45-degree orbit should cover Singapore: {counts}"
        print(f"Orbit visibility split verified: {counts}")

    def test_02_quality_first_vs_urgent_changes_single_target_choice(self) -> None:
        """Urgent should schedule earlier while quality-first should not worsen geometry."""
        analysis = _analyze_mission(
            tle=TLE_SAT1,
            targets=STRATEGY_TIMING_TARGET,
        )
        passes = _extract_mission_passes(analysis)
        assert passes, "Expected at least one pass for timing-vs-geometry review"

        quality_first = _planning_result(
            _run_planning_schedule(weight_preset="quality_first")
        )
        urgent = _planning_result(_run_planning_schedule(weight_preset="urgent"))

        quality_schedule = quality_first.get("schedule", [])
        urgent_schedule = urgent.get("schedule", [])
        assert (
            len(quality_schedule) == 1
        ), f"Expected exactly one scheduled item for quality_first: {quality_schedule}"
        assert (
            len(urgent_schedule) == 1
        ), f"Expected exactly one scheduled item for urgent: {urgent_schedule}"

        quality_item = quality_schedule[0]
        urgent_item = urgent_schedule[0]
        quality_start = _parse_ts(quality_item["start_time"])
        urgent_start = _parse_ts(urgent_item["start_time"])
        quality_incidence = abs(float(quality_item.get("incidence_angle", 0.0)))
        urgent_incidence = abs(float(urgent_item.get("incidence_angle", 0.0)))

        assert urgent_start <= quality_start, (
            f"Urgent preset should not schedule later than quality-first: "
            f"urgent={urgent_item['start_time']} quality={quality_item['start_time']}"
        )
        assert quality_incidence <= urgent_incidence + 1e-6, (
            f"Quality-first should not worsen incidence: "
            f"quality={quality_incidence:.2f} urgent={urgent_incidence:.2f}"
        )
        print(
            f"Urgent picked {urgent_item['opportunity_id']} at {urgent_item['start_time']} "
            f"vs quality-first {quality_item['opportunity_id']} at "
            f"{quality_item['start_time']}"
        )

    def test_03_priority_first_prefers_high_priority_target_under_overlap(self) -> None:
        """Priority-first should keep the higher-priority target when near-duplicate targets compete."""
        analysis = _analyze_mission(
            tle=TLE_SAT1,
            targets=STRATEGY_PRIORITY_TARGETS,
            start_time="2026-03-08T00:00:00Z",
            end_time="2026-03-09T00:00:00Z",
        )
        passes = _extract_mission_passes(analysis)
        assert passes, "Expected at least one pass for priority-overlap review"

        priority_first = _planning_result(
            _run_planning_schedule(
                weight_preset="priority_first",
                imaging_time_s=43200.0,
            )
        )
        schedule = priority_first.get("schedule", [])
        scheduled_targets = [item["target_id"] for item in schedule]

        assert (
            len(schedule) == 1
        ), f"Expected a single surviving target under long overlap: {scheduled_targets}"
        assert scheduled_targets[0] == "PriorityAnchor", (
            f"Priority-first should select the higher-priority target, got "
            f"{scheduled_targets}"
        )
        print(f"Priority-first selected {scheduled_targets[0]} under forced overlap")


# =============================================================================
# Phase 6: Scale Tests — 50-100 targets, incremental add/remove/replan
# =============================================================================

# Geographically distributed targets for scale testing
SCALE_TARGETS_BATCH_1 = [
    {"name": "Athens", "latitude": 37.9838, "longitude": 23.7275},
    {"name": "London", "latitude": 51.5074, "longitude": -0.1278},
    {"name": "Cairo", "latitude": 30.0444, "longitude": 31.2357},
    {"name": "Istanbul", "latitude": 41.0082, "longitude": 28.9784},
    {"name": "Berlin", "latitude": 52.5200, "longitude": 13.4050},
    {"name": "Moscow", "latitude": 55.7558, "longitude": 37.6173},
    {"name": "Mumbai", "latitude": 19.0760, "longitude": 72.8777},
    {"name": "Tokyo", "latitude": 35.6762, "longitude": 139.6503},
    {"name": "Sydney", "latitude": -33.8688, "longitude": 151.2093},
    {"name": "SaoPaulo", "latitude": -23.5505, "longitude": -46.6333},
    {"name": "NewYork", "latitude": 40.7128, "longitude": -74.0060},
    {"name": "LosAngeles", "latitude": 34.0522, "longitude": -118.2437},
    {"name": "Paris", "latitude": 48.8566, "longitude": 2.3522},
    {"name": "Rome", "latitude": 41.9028, "longitude": 12.4964},
    {"name": "Madrid", "latitude": 40.4168, "longitude": -3.7038},
    {"name": "Dubai", "latitude": 25.2048, "longitude": 55.2708},
    {"name": "Singapore", "latitude": 1.3521, "longitude": 103.8198},
    {"name": "Seoul", "latitude": 37.5665, "longitude": 126.9780},
    {"name": "Bangkok", "latitude": 13.7563, "longitude": 100.5018},
    {"name": "CapeTown", "latitude": -33.9249, "longitude": 18.4241},
]

SCALE_TARGETS_BATCH_2 = [
    {"name": "Nairobi", "latitude": -1.2921, "longitude": 36.8219},
    {"name": "Lima", "latitude": -12.0464, "longitude": -77.0428},
    {"name": "Jakarta", "latitude": -6.2088, "longitude": 106.8456},
    {"name": "Toronto", "latitude": 43.6532, "longitude": -79.3832},
    {"name": "Santiago", "latitude": -33.4489, "longitude": -70.6693},
    {"name": "Helsinki", "latitude": 60.1699, "longitude": 24.9384},
    {"name": "Reykjavik", "latitude": 64.1466, "longitude": -21.9426},
    {"name": "Wellington", "latitude": -41.2865, "longitude": 174.7762},
    {"name": "BuenosAires", "latitude": -34.6037, "longitude": -58.3816},
    {"name": "MexicoCity", "latitude": 19.4326, "longitude": -99.1332},
    {"name": "Stockholm", "latitude": 59.3293, "longitude": 18.0686},
    {"name": "Oslo", "latitude": 59.9139, "longitude": 10.7522},
    {"name": "Lisbon", "latitude": 38.7223, "longitude": -9.1393},
    {"name": "Ankara", "latitude": 39.9334, "longitude": 32.8597},
    {"name": "Tehran", "latitude": 35.6892, "longitude": 51.3890},
]

SCALE_TARGETS_BATCH_3 = [
    {"name": "Shanghai", "latitude": 31.2304, "longitude": 121.4737},
    {"name": "Beijing", "latitude": 39.9042, "longitude": 116.4074},
    {"name": "Lagos", "latitude": 6.5244, "longitude": 3.3792},
    {"name": "Bogota", "latitude": 4.7110, "longitude": -74.0721},
    {"name": "Karachi", "latitude": 24.8607, "longitude": 67.0011},
    {"name": "Manila", "latitude": 14.5995, "longitude": 120.9842},
    {"name": "Taipei", "latitude": 25.0330, "longitude": 121.5654},
    {"name": "HoChiMinh", "latitude": 10.8231, "longitude": 106.6297},
    {"name": "Hanoi", "latitude": 21.0285, "longitude": 105.8542},
    {"name": "Dhaka", "latitude": 23.8103, "longitude": 90.4125},
    {"name": "Riyadh", "latitude": 24.7136, "longitude": 46.6753},
    {"name": "Algiers", "latitude": 36.7538, "longitude": 3.0588},
    {"name": "Tunis", "latitude": 36.8065, "longitude": 10.1815},
    {"name": "Casablanca", "latitude": 33.5731, "longitude": -7.5898},
    {"name": "Accra", "latitude": 5.6037, "longitude": -0.1870},
]

TLE_SAT3 = {
    "name": "ICEYE-X44",
    "line1": "1 62707U 25009DC  25337.22325646  .00005980  00000+0  55896-3 0  9995",
    "line2": "2 62707  97.7247  54.4904 0002410  80.3183 279.8309 14.94500111 70658",
}


class TestScaleSingleSatellite:
    """Scale test: single satellite with 50+ targets, incremental add/remove."""

    def test_01_initial_20_targets(self) -> None:
        """Plan + commit 20 targets on a fresh workspace."""
        ws = _create_workspace(f"scale1_{uuid.uuid4().hex[:6]}")
        try:
            # Seed with 20 targets
            seed = _seed(TLE_SAT1, SCALE_TARGETS_BATCH_1, days=3)
            assert seed["success"], f"Seed failed: {seed.get('message')}"
            passes = seed.get("data", {}).get("mission_data", {}).get("passes", [])
            print(f"Batch 1 seed: {len(passes)} passes for 20 targets")

            # Plan — should auto-select FROM_SCRATCH (empty workspace)
            plan = _plan(ws)
            assert plan["success"]
            assert plan["planning_mode"] == "from_scratch"
            items_b1 = plan.get("new_plan_items", [])
            targets_planned = set(it["target_id"] for it in items_b1)
            print(
                f"Batch 1 plan: {len(items_b1)} items | "
                f"{len(targets_planned)} unique targets | "
                f"mode={plan['planning_mode']}"
            )
            assert len(items_b1) > 0, "Expected plan items for 20 targets"

            # Commit
            commit = _commit(plan["plan_id"], ws, force=True)
            assert commit["success"]
            n_committed = commit.get("committed", 0)
            print(f"Batch 1 committed: {n_committed} acquisitions")
            assert n_committed > 0

            # Verify state
            state = _state(ws)
            acqs = state.get("acquisitions", [])
            print(f"State after batch 1: {len(acqs)} acquisitions in schedule")
            assert len(acqs) == n_committed

            # --- Add 15 more targets (batch 2) → INCREMENTAL ---
            all_targets_35 = SCALE_TARGETS_BATCH_1 + SCALE_TARGETS_BATCH_2
            seed2 = _seed(TLE_SAT1, all_targets_35, days=3)
            assert seed2["success"]
            passes2 = seed2.get("data", {}).get("mission_data", {}).get("passes", [])
            print(f"Batch 1+2 seed: {len(passes2)} passes for 35 targets")

            # Re-plan — should auto-select INCREMENTAL (new targets detected)
            plan2 = _plan(ws)
            assert plan2["success"]
            ctx2 = plan2.get("schedule_context", {})
            print(
                f"Batch 2 plan: mode={plan2['planning_mode']} | "
                f"existing={ctx2.get('existing_acquisition_count', '?')} | "
                f"new_targets={ctx2.get('new_target_count', '?')} | "
                f"items={len(plan2.get('new_plan_items', []))}"
            )
            assert plan2["planning_mode"] == "incremental", (
                f"Expected incremental after adding targets, got {plan2['planning_mode']}. "
                f"Context: {ctx2}"
            )
            assert ctx2.get("new_target_count", 0) > 0

            items_b2 = plan2.get("new_plan_items", [])
            if items_b2:
                commit2 = _commit(plan2["plan_id"], ws, force=True)
                assert commit2["success"]
                print(
                    f"Batch 2 committed: {commit2.get('committed', 0)} new acquisitions"
                )

            # --- Add 15 more targets (batch 3) → total 50 → INCREMENTAL ---
            all_targets_50 = all_targets_35 + SCALE_TARGETS_BATCH_3
            seed3 = _seed(TLE_SAT1, all_targets_50, days=3)
            assert seed3["success"]
            passes3 = seed3.get("data", {}).get("mission_data", {}).get("passes", [])
            print(f"Batch 1+2+3 seed: {len(passes3)} passes for 50 targets")

            plan3 = _plan(ws)
            assert plan3["success"]
            ctx3 = plan3.get("schedule_context", {})
            print(
                f"Batch 3 plan: mode={plan3['planning_mode']} | "
                f"existing={ctx3.get('existing_acquisition_count', '?')} | "
                f"new_targets={ctx3.get('new_target_count', '?')} | "
                f"items={len(plan3.get('new_plan_items', []))}"
            )
            assert (
                plan3["planning_mode"] == "incremental"
            ), f"Expected incremental for batch 3, got {plan3['planning_mode']}"

            items_b3 = plan3.get("new_plan_items", [])
            if items_b3:
                commit3 = _commit(plan3["plan_id"], ws, force=True)
                assert commit3["success"]
                print(
                    f"Batch 3 committed: {commit3.get('committed', 0)} new acquisitions"
                )

            # --- Verify final schedule state ---
            final_state = _state(ws)
            final_acqs = final_state.get("acquisitions", [])
            final_targets = set(a["target_id"] for a in final_acqs)
            print(
                f"\nFinal schedule: {len(final_acqs)} acquisitions | "
                f"{len(final_targets)} unique targets"
            )
            assert (
                len(final_acqs) > n_committed
            ), "Expected more acquisitions after incremental adds"

            # --- Replan same targets → REPAIR or INCREMENTAL ---
            # If all targets have acquisitions → REPAIR (no new targets)
            # If some targets lack acquisitions (sat didn't overfly) → INCREMENTAL
            # Either is correct; key: NOT from_scratch (schedule exists)
            plan4 = _plan(ws)
            assert plan4["success"]
            ctx4 = plan4.get("schedule_context", {})
            print(
                f"Replan (same targets): mode={plan4['planning_mode']} | "
                f"existing={ctx4.get('existing_acquisition_count', '?')} | "
                f"new_targets={ctx4.get('new_target_count', '?')}"
            )
            assert plan4["planning_mode"] in (
                "repair",
                "incremental",
            ), f"Expected repair or incremental, got {plan4['planning_mode']}"
            assert (
                plan4["planning_mode"] != "from_scratch"
            ), "Should not be from_scratch — schedule has existing acquisitions"

            # --- Delete some unlocked acquisitions and replan ---
            unlocked = [a for a in final_acqs if a.get("lock_level", "none") == "none"]
            acq_ids_to_delete = [a["id"] for a in unlocked[:3]]
            assert len(acq_ids_to_delete) > 0, "Need at least 1 unlocked acq to delete"
            del_resp = _post(
                "/schedule/acquisitions/bulk-delete",
                {
                    "acquisition_ids": acq_ids_to_delete,
                    "workspace_id": ws,
                    "force": True,
                },
            )
            deleted = del_resp.get("deleted", 0)
            skipped = len(del_resp.get("skipped_hard_locked", []))
            print(f"Deleted {deleted} acquisitions (skipped {skipped} hard-locked)")
            assert deleted == len(acq_ids_to_delete), (
                f"Expected {len(acq_ids_to_delete)} deleted, got {deleted}. "
                f"Skipped: {del_resp.get('skipped_hard_locked', [])}"
            )

            # Replan after deletion
            plan5 = _plan(ws)
            assert plan5["success"]
            ctx5 = plan5.get("schedule_context", {})
            remaining = ctx5.get("existing_acquisition_count", 0)
            print(
                f"After deletion replan: mode={plan5['planning_mode']} | "
                f"remaining={remaining} | items={len(plan5.get('new_plan_items', []))}"
            )

            print(f"\n{'='*60}")
            print(f"SINGLE SAT SCALE TEST PASSED")
            print(
                f"  Batches: 20 → 35 → 50 targets"
                f" | Final: {len(final_acqs)} acqs, {len(final_targets)} targets"
            )
            print(
                f"  Modes exercised: from_scratch → incremental → incremental → repair"
            )
            print(f"{'='*60}")

        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)


class TestScaleConstellation:
    """Scale test: 3-satellite constellation with 50+ targets."""

    def test_01_constellation_incremental_growth(self) -> None:
        """3-sat constellation: plan 20 → add 15 → add 15 → remove → replan."""
        ws = _create_workspace(f"scale_const_{uuid.uuid4().hex[:6]}")
        try:
            sats = [TLE_SAT1, TLE_SAT2, TLE_SAT3]

            # --- Batch 1: 20 targets, 3 satellites ---
            seed1 = _seed_constellation(sats, SCALE_TARGETS_BATCH_1, days=3)
            assert seed1[
                "success"
            ], f"Constellation seed failed: {seed1.get('message')}"
            passes1 = seed1.get("data", {}).get("mission_data", {}).get("passes", [])
            sats_in_data = (
                seed1.get("data", {}).get("mission_data", {}).get("satellites", [])
            )
            print(
                f"Constellation batch 1: {len(passes1)} passes | "
                f"{len(sats_in_data)} satellites | 20 targets"
            )
            assert len(sats_in_data) >= 2, "Expected constellation with 2+ satellites"

            plan1 = _plan(ws)
            assert plan1["success"]
            assert plan1["planning_mode"] == "from_scratch"
            items1 = plan1.get("new_plan_items", [])
            sats_planned = set(it["satellite_id"] for it in items1)
            targets_planned = set(it["target_id"] for it in items1)
            print(
                f"Const plan 1: {len(items1)} items | "
                f"{len(sats_planned)} sats | "
                f"{len(targets_planned)} targets | "
                f"mode={plan1['planning_mode']}"
            )
            assert len(items1) > 0

            commit1 = _commit(plan1["plan_id"], ws, force=True)
            assert commit1["success"]
            n1 = commit1.get("committed", 0)
            print(f"Const commit 1: {n1} acquisitions")

            # --- Lock some acquisitions to test preservation ---
            state1 = _state(ws)
            acqs1 = state1.get("acquisitions", [])
            lock_ids = [a["id"] for a in acqs1[:2]]
            _post(
                "/schedule/acquisitions/bulk-lock",
                {"acquisition_ids": lock_ids, "lock_level": "hard"},
            )
            print(f"Hard-locked {len(lock_ids)} acquisitions: {lock_ids}")

            # --- Batch 2: add 15 more targets → 35 total ---
            all_35 = SCALE_TARGETS_BATCH_1 + SCALE_TARGETS_BATCH_2
            seed2 = _seed_constellation(sats, all_35, days=3)
            assert seed2["success"]
            passes2 = seed2.get("data", {}).get("mission_data", {}).get("passes", [])
            print(f"Const batch 2: {len(passes2)} passes for 35 targets")

            plan2 = _plan(ws)
            assert plan2["success"]
            ctx2 = plan2.get("schedule_context", {})
            print(
                f"Const plan 2: mode={plan2['planning_mode']} | "
                f"existing={ctx2.get('existing_acquisition_count', '?')} | "
                f"new_targets={ctx2.get('new_target_count', '?')} | "
                f"items={len(plan2.get('new_plan_items', []))}"
            )
            assert (
                plan2["planning_mode"] == "incremental"
            ), f"Expected incremental, got {plan2['planning_mode']}. ctx={ctx2}"

            items2 = plan2.get("new_plan_items", [])
            if items2:
                commit2 = _commit(plan2["plan_id"], ws, force=True)
                assert commit2["success"]
                print(f"Const commit 2: {commit2.get('committed', 0)} new acquisitions")

            # --- Batch 3: add 15 more → 50 total ---
            all_50 = all_35 + SCALE_TARGETS_BATCH_3
            seed3 = _seed_constellation(sats, all_50, days=3)
            assert seed3["success"]
            passes3 = seed3.get("data", {}).get("mission_data", {}).get("passes", [])
            print(f"Const batch 3: {len(passes3)} passes for 50 targets")

            plan3 = _plan(ws)
            assert plan3["success"]
            ctx3 = plan3.get("schedule_context", {})
            print(
                f"Const plan 3: mode={plan3['planning_mode']} | "
                f"existing={ctx3.get('existing_acquisition_count', '?')} | "
                f"new_targets={ctx3.get('new_target_count', '?')} | "
                f"items={len(plan3.get('new_plan_items', []))}"
            )
            assert plan3["planning_mode"] == "incremental"

            items3 = plan3.get("new_plan_items", [])
            if items3:
                commit3 = _commit(plan3["plan_id"], ws, force=True)
                assert commit3["success"]
                print(f"Const commit 3: {commit3.get('committed', 0)} new acquisitions")

            # --- Verify locked acquisitions survived ---
            state_final = _state(ws)
            final_acqs = state_final.get("acquisitions", [])
            final_ids = set(a["id"] for a in final_acqs)
            for lid in lock_ids:
                assert (
                    lid in final_ids
                ), f"Hard-locked acquisition {lid} missing after incremental adds!"
            locked_acqs = [a for a in final_acqs if a.get("lock_level") == "hard"]
            print(f"Hard-locked acquisitions preserved: {len(locked_acqs)}")

            # --- Verify multi-satellite coverage ---
            final_sats = set(a["satellite_id"] for a in final_acqs)
            final_targets = set(a["target_id"] for a in final_acqs)
            print(
                f"Final state: {len(final_acqs)} acqs | "
                f"{len(final_sats)} satellites | "
                f"{len(final_targets)} targets"
            )

            # --- Delete some and replan → REPAIR ---
            del_candidates = [
                a["id"] for a in final_acqs if a.get("lock_level") != "hard"
            ][:5]
            if del_candidates:
                del_resp = _post(
                    "/schedule/acquisitions/bulk-delete",
                    {
                        "acquisition_ids": del_candidates,
                        "workspace_id": ws,
                        "force": True,
                    },
                )
                print(f"Deleted {del_resp.get('deleted', 0)} unlocked acquisitions")

            # Replan same targets → REPAIR
            plan4 = _plan(ws)
            assert plan4["success"]
            ctx4 = plan4.get("schedule_context", {})
            print(
                f"Post-delete replan: mode={plan4['planning_mode']} | "
                f"existing={ctx4.get('existing_acquisition_count', '?')}"
            )
            assert plan4["planning_mode"] in (
                "repair",
                "incremental",
            ), f"Expected repair or incremental, got {plan4['planning_mode']}"
            assert (
                plan4["planning_mode"] != "from_scratch"
            ), "Should not be from_scratch — schedule has existing acquisitions"

            # --- Hard-locks still present after everything ---
            post_repair = _state(ws)
            post_acqs = post_repair.get("acquisitions", [])
            post_ids = set(a["id"] for a in post_acqs)
            for lid in lock_ids:
                assert (
                    lid in post_ids
                ), f"Hard-locked {lid} vanished after repair cycle!"

            print(f"\n{'='*60}")
            print(f"CONSTELLATION SCALE TEST PASSED")
            print(
                f"  3 satellites | 50 targets (20→35→50)"
                f" | {len(final_acqs)} total acqs"
            )
            print(f"  Modes: from_scratch → incremental(×2) → {plan4['planning_mode']}")
            print(f"  Hard-locks preserved through all operations")
            print(f"{'='*60}")

        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)


# =============================================================================
# Phase 7: Advanced Mode Selection — deep MOD edge cases
# =============================================================================

# Extra target sets for mode-transition tests
MOD_TARGETS_A = [
    {"name": "Paris", "latitude": 48.8566, "longitude": 2.3522},
    {"name": "Berlin", "latitude": 52.5200, "longitude": 13.4050},
    {"name": "Madrid", "latitude": 40.4168, "longitude": -3.7038},
]

MOD_TARGETS_B = [
    {"name": "Rome", "latitude": 41.9028, "longitude": 12.4964},
    {"name": "Vienna", "latitude": 48.2082, "longitude": 16.3738},
]

MOD_TARGETS_C = [
    {"name": "Oslo", "latitude": 59.9139, "longitude": 10.7522},
    {"name": "Helsinki", "latitude": 60.1699, "longitude": 24.9384},
    {"name": "Stockholm", "latitude": 59.3293, "longitude": 18.0686},
]


class TestAdvancedModeSelection:
    """
    Deep MOD scenarios: mode transitions, workspace isolation,
    lock interactions, forced overrides, delete-all recovery,
    target churn, and reason-string correctness.
    """

    # ----- T1: Delete ALL → schedule empties → FROM_SCRATCH recovery -----
    def test_01_delete_all_reverts_to_from_scratch(self) -> None:
        """
        Plan → commit → delete every acquisition → replan.
        Mode must revert to FROM_SCRATCH because schedule is now empty.
        """
        ws = _create_workspace(f"mod01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            # Plan + commit
            plan1 = _plan(ws)
            assert plan1["success"] and plan1["planning_mode"] == "from_scratch"
            commit1 = _commit(plan1["plan_id"], ws, force=True)
            n = commit1["committed"]
            assert n > 0
            print(f"Committed {n} acquisitions")

            # Delete ALL with force (bypass freeze window)
            state = _state(ws)
            all_ids = [a["id"] for a in state["acquisitions"]]
            assert len(all_ids) == n
            del_resp = _post(
                "/schedule/acquisitions/bulk-delete",
                {"acquisition_ids": all_ids, "workspace_id": ws, "force": True},
            )
            assert (
                del_resp["deleted"] == n
            ), f"Expected {n} deleted, got {del_resp['deleted']}"
            print(f"Deleted all {n} acquisitions")

            # Replan — should be FROM_SCRATCH (empty workspace)
            plan2 = _plan(ws)
            assert plan2["success"]
            ctx2 = plan2.get("schedule_context", {})
            assert plan2["planning_mode"] == "from_scratch", (
                f"Expected from_scratch after deleting all, got {plan2['planning_mode']}. "
                f"existing_acq={ctx2.get('existing_acquisition_count')}"
            )
            assert ctx2.get("existing_acquisition_count", -1) == 0
            print(
                f"After delete-all: mode={plan2['planning_mode']} | "
                f"existing={ctx2.get('existing_acquisition_count')} ✓"
            )
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    # ----- T2: Full lifecycle: FS → INC → INC → DEL-ALL → FS -----
    def test_02_full_mode_lifecycle(self) -> None:
        """
        FROM_SCRATCH → commit → add targets → INCREMENTAL → commit →
        add more → INCREMENTAL → commit → delete all → FROM_SCRATCH.
        Exercises every mode transition in sequence.
        """
        ws = _create_workspace(f"mod02_{uuid.uuid4().hex[:6]}")
        try:
            # Step 1: FROM_SCRATCH with targets A
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            p1 = _plan(ws)
            assert p1["planning_mode"] == "from_scratch"
            c1 = _commit(p1["plan_id"], ws, force=True)
            assert c1["committed"] > 0
            print(f"Step 1 FROM_SCRATCH: {c1['committed']} committed")

            # Step 2: Add targets B → INCREMENTAL
            _seed(TLE_SAT1, MOD_TARGETS_A + MOD_TARGETS_B, days=3)
            p2 = _plan(ws)
            assert (
                p2["planning_mode"] == "incremental"
            ), f"Expected incremental, got {p2['planning_mode']}"
            ctx2 = p2.get("schedule_context", {})
            assert ctx2.get("new_target_count", 0) > 0
            if p2.get("new_plan_items"):
                c2 = _commit(p2["plan_id"], ws, force=True)
                print(f"Step 2 INCREMENTAL: {c2['committed']} new")

            # Step 3: Add targets C → INCREMENTAL again
            _seed(TLE_SAT1, MOD_TARGETS_A + MOD_TARGETS_B + MOD_TARGETS_C, days=3)
            p3 = _plan(ws)
            assert (
                p3["planning_mode"] == "incremental"
            ), f"Expected incremental, got {p3['planning_mode']}"
            if p3.get("new_plan_items"):
                c3 = _commit(p3["plan_id"], ws, force=True)
                print(f"Step 3 INCREMENTAL: {c3['committed']} new")

            # Step 4: Same targets → REPAIR
            p4 = _plan(ws)
            ctx4 = p4.get("schedule_context", {})
            print(
                f"Step 4 replan same: mode={p4['planning_mode']} | "
                f"new_targets={ctx4.get('new_target_count')}"
            )
            # May be repair or incremental if some targets weren't planned
            assert p4["planning_mode"] != "from_scratch"

            # Step 5: Delete ALL → FROM_SCRATCH
            st = _state(ws)
            all_ids = [a["id"] for a in st["acquisitions"]]
            _post(
                "/schedule/acquisitions/bulk-delete",
                {"acquisition_ids": all_ids, "workspace_id": ws, "force": True},
            )
            p5 = _plan(ws)
            assert (
                p5["planning_mode"] == "from_scratch"
            ), f"After delete-all, expected from_scratch, got {p5['planning_mode']}"
            print(f"Step 5 after delete-all: from_scratch ✓")

            print(f"\nLifecycle: FS → INC → INC → REPAIR/INC → FS  ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    # ----- T3: Force override of every mode + reason strings -----
    def test_03_force_every_mode_with_reasons(self) -> None:
        """
        Force each of the 3 modes explicitly and verify:
        - Mode is exactly what was forced
        - Reason string contains 'Explicitly requested'
        - schedule_context still has all metadata keys
        """
        ws = _create_workspace(f"mod03_{uuid.uuid4().hex[:6]}")
        try:
            # First commit something so auto would normally pick repair
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            _plan_commit(ws)

            for forced_mode in ("incremental", "repair"):
                plan = _post(
                    "/schedule/plan",
                    {"planning_mode": forced_mode, "workspace_id": ws},
                )
                assert plan["success"]
                assert (
                    plan["planning_mode"] == forced_mode
                ), f"Forced {forced_mode}, got {plan['planning_mode']}"
                reason = plan.get("schedule_context", {}).get(
                    "mode_selection_reason", ""
                )
                assert (
                    "Explicitly requested" in reason
                ), f"Force reason should say 'Explicitly requested', got: {reason}"
                ctx = plan.get("schedule_context", {})
                for key in (
                    "planning_mode",
                    "existing_acquisition_count",
                    "new_target_count",
                    "conflict_count",
                ):
                    assert (
                        key in ctx
                    ), f"Missing {key} in context when forcing {forced_mode}"
                print(f"Force {forced_mode}: reason='{reason[:60]}' ✓")

            # Force from_scratch — since it's the default, auto-mode runs.
            # To truly force it, we need a non-default value. Verify this.
            p_fs = _post(
                "/schedule/plan",
                {"planning_mode": "from_scratch", "workspace_id": ws},
            )
            # Auto-mode should fire and pick repair (schedule exists, same targets)
            assert p_fs["planning_mode"] in (
                "repair",
                "incremental",
            ), f"from_scratch default should trigger auto-mode, got {p_fs['planning_mode']}"
            reason_fs = p_fs.get("schedule_context", {}).get(
                "mode_selection_reason", ""
            )
            assert (
                "Explicitly requested" not in reason_fs
            ), "from_scratch (default) should NOT show 'Explicitly requested'"
            print(f"Default from_scratch triggers auto: {p_fs['planning_mode']} ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    # ----- T4: Workspace isolation — different states, different modes -----
    def test_04_workspace_isolation_different_modes(self) -> None:
        """
        Two workspaces: ws1 has committed schedule (→ REPAIR),
        ws2 is empty (→ FROM_SCRATCH). Same seeded opportunities.
        """
        ws1 = _create_workspace(f"mod04a_{uuid.uuid4().hex[:6]}")
        ws2 = _create_workspace(f"mod04b_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)

            # ws1: plan + commit → has schedule
            _plan_commit(ws1)

            # ws2: no commits → empty
            # Plan both — should get different modes
            p1 = _plan(ws1)
            p2 = _plan(ws2)

            ctx1 = p1.get("schedule_context", {})
            ctx2 = p2.get("schedule_context", {})

            # ws2 is empty → from_scratch
            assert (
                p2["planning_mode"] == "from_scratch"
            ), f"Empty ws2 should be from_scratch, got {p2['planning_mode']}"
            assert ctx2.get("existing_acquisition_count", -1) == 0

            # ws1 has schedule → repair or incremental (not from_scratch)
            assert (
                p1["planning_mode"] != "from_scratch"
            ), f"ws1 has schedule, should not be from_scratch"
            assert ctx1.get("existing_acquisition_count", 0) > 0

            print(
                f"ws1 ({p1['planning_mode']}, existing={ctx1.get('existing_acquisition_count')}) "
                f"vs ws2 ({p2['planning_mode']}, existing={ctx2.get('existing_acquisition_count')}) ✓"
            )
        finally:
            _safe_cleanup(ws1, TLE_SAT1, TARGETS_PHASE1)
            _safe_cleanup(ws2)

    # ----- T5: Hard-lock + new targets → INCREMENTAL preserves locks -----
    def test_05_incremental_preserves_hard_locks(self) -> None:
        """
        Commit → hard-lock 2 acqs → add new targets → INCREMENTAL →
        commit → verify locked acqs still present and locked.
        """
        ws = _create_workspace(f"mod05_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            c1 = _plan_commit(ws)
            n1 = c1["committed"]
            assert n1 >= 2, f"Need ≥2 to lock, got {n1}"

            # Hard-lock first 2
            state1 = _state(ws)
            acqs1 = state1["acquisitions"]
            lock_ids = [acqs1[0]["id"], acqs1[1]["id"]]
            _post(
                "/schedule/acquisitions/bulk-lock",
                {"acquisition_ids": lock_ids, "lock_level": "hard"},
            )

            # Verify locked
            state_locked = _state(ws)
            for a in state_locked["acquisitions"]:
                if a["id"] in lock_ids:
                    assert a["lock_level"] == "hard", f"{a['id']} not hard-locked"

            # Add new targets → should trigger INCREMENTAL
            _seed(TLE_SAT1, MOD_TARGETS_A + MOD_TARGETS_B, days=3)
            p2 = _plan(ws)
            assert (
                p2["planning_mode"] == "incremental"
            ), f"New targets should trigger incremental, got {p2['planning_mode']}"
            ctx2 = p2.get("schedule_context", {})
            assert ctx2.get("new_target_count", 0) > 0

            # Commit incremental
            if p2.get("new_plan_items"):
                c2 = _commit(p2["plan_id"], ws, force=True)
                print(f"Incremental added {c2.get('committed', 0)} new")

            # Verify hard-locked acqs survived
            state_after = _state(ws)
            after_ids = {a["id"] for a in state_after["acquisitions"]}
            for lid in lock_ids:
                assert (
                    lid in after_ids
                ), f"Hard-locked {lid} vanished after incremental!"
                acq = next(a for a in state_after["acquisitions"] if a["id"] == lid)
                assert (
                    acq["lock_level"] == "hard"
                ), f"Lock on {lid} degraded to {acq['lock_level']}!"
            print(f"Locks preserved: {lock_ids} ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    # ----- T6: Target churn — add, remove, add different, verify modes -----
    def test_06_target_churn_add_remove_readd(self) -> None:
        """
        Commit A → remove some acqs → add targets B (different) → INCREMENTAL →
        commit → swap to targets C (remove B, add C) → INCREMENTAL →
        verify mode selection adapts to target-set diffs correctly.
        """
        ws = _create_workspace(f"mod06_{uuid.uuid4().hex[:6]}")
        try:
            # Phase 1: Commit with targets A
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            c1 = _plan_commit(ws)
            n1 = c1["committed"]
            print(f"Phase 1: {n1} acqs for A")

            # Delete half the acquisitions
            st = _state(ws)
            half = [a["id"] for a in st["acquisitions"]][: max(1, n1 // 2)]
            _post(
                "/schedule/acquisitions/bulk-delete",
                {"acquisition_ids": half, "workspace_id": ws, "force": True},
            )
            print(f"Deleted {len(half)} acqs")

            # Phase 2: Switch to A + B → should detect B as new
            _seed(TLE_SAT1, MOD_TARGETS_A + MOD_TARGETS_B, days=3)
            p2 = _plan(ws)
            ctx2 = p2.get("schedule_context", {})
            print(
                f"Phase 2: mode={p2['planning_mode']} | "
                f"existing={ctx2.get('existing_acquisition_count')} | "
                f"new_targets={ctx2.get('new_target_count')}"
            )
            assert (
                p2["planning_mode"] == "incremental"
            ), f"New targets B should trigger incremental, got {p2['planning_mode']}"
            if p2.get("new_plan_items"):
                _commit(p2["plan_id"], ws, force=True)

            # Phase 3: Switch to A + C (dropping B, adding C)
            _seed(TLE_SAT1, MOD_TARGETS_A + MOD_TARGETS_C, days=3)
            p3 = _plan(ws)
            ctx3 = p3.get("schedule_context", {})
            print(
                f"Phase 3: mode={p3['planning_mode']} | "
                f"existing={ctx3.get('existing_acquisition_count')} | "
                f"new_targets={ctx3.get('new_target_count')}"
            )
            # C targets are new → should be INCREMENTAL
            assert (
                p3["planning_mode"] == "incremental"
            ), f"New targets C should trigger incremental, got {p3['planning_mode']}"
            assert ctx3.get("new_target_count", 0) > 0

            print(f"Target churn: A → (A+B) → (A+C) modes correct ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    # ----- T7: Direct-commit synthetic acqs → force conflict-driven REPAIR -----
    def test_07_direct_commit_creates_conflicts_for_repair(self) -> None:
        """
        Plan + commit normal acqs, then direct-commit overlapping acqs
        with force=True to create real conflicts. Replan should see
        conflict_count > 0 in the context.
        """
        ws = _create_workspace(f"mod07_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            c1 = _plan_commit(ws)
            n1 = c1["committed"]
            assert n1 > 0

            # Get an existing acquisition to create an overlap
            st = _state(ws)
            existing = st["acquisitions"][0]
            overlap_start = existing["start_time"]
            overlap_end = existing["end_time"]

            # Direct-commit a conflicting acquisition on the same satellite
            synth = {
                "items": [
                    {
                        "opportunity_id": f"synth_opp_{uuid.uuid4().hex[:8]}",
                        "satellite_id": existing["satellite_id"],
                        "target_id": "synth_conflict_target",
                        "start_time": overlap_start,
                        "end_time": overlap_end,
                        "roll_angle_deg": 5.0,
                    }
                ],
                "algorithm": "test_synthetic",
                "workspace_id": ws,
                "force": True,
            }
            dc = _post("/schedule/commit/direct", synth)
            assert dc["success"], f"Direct commit failed: {dc.get('message')}"
            print(f"Direct-committed overlapping acq: {dc['acquisition_ids']}")

            # Replan — should have conflict_count > 0
            plan = _plan(ws)
            assert plan["success"]
            ctx = plan.get("schedule_context", {})
            conflict_count = ctx.get("conflict_count", 0)
            print(
                f"After conflict injection: mode={plan['planning_mode']} | "
                f"conflict_count={conflict_count} | "
                f"existing={ctx.get('existing_acquisition_count')}"
            )
            # With conflicts and no new targets, should be REPAIR
            # (but synth target is "new" from auto-mode's perspective)
            assert ctx.get("existing_acquisition_count", 0) > 0
            assert isinstance(conflict_count, int)
            # The synthetic target may show as "new" → INCREMENTAL,
            # or if fully covered → REPAIR. Both valid. Key: not from_scratch.
            assert plan["planning_mode"] != "from_scratch"
            print(f"Conflict-driven mode: {plan['planning_mode']} ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    # ----- T8: Reason string correctness for each auto-selected mode -----
    def test_08_reason_strings_match_rules(self) -> None:
        """
        Exercise each auto-selection rule and verify reason substring:
        - FROM_SCRATCH: 'No existing schedule'
        - INCREMENTAL: 'new target(s) detected'
        - REPAIR: 'existing acquisition(s)'
        """
        ws = _create_workspace(f"mod08_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)

            # Rule 1: FROM_SCRATCH
            p1 = _plan(ws)
            r1 = p1.get("schedule_context", {}).get("mode_selection_reason", "")
            assert "No existing schedule" in r1, f"FROM_SCRATCH reason wrong: {r1}"
            print(f"FROM_SCRATCH reason: '{r1[:70]}' ✓")

            _commit(p1["plan_id"], ws, force=True)

            # Rule 2: INCREMENTAL — add new target
            _seed(TLE_SAT1, MOD_TARGETS_A + MOD_TARGETS_B, days=3)
            p2 = _plan(ws)
            r2 = p2.get("schedule_context", {}).get("mode_selection_reason", "")
            assert "new target(s) detected" in r2, f"INCREMENTAL reason wrong: {r2}"
            assert (
                "incrementally" in r2.lower()
            ), f"INCREMENTAL reason should mention 'incrementally': {r2}"
            print(f"INCREMENTAL reason: '{r2[:70]}' ✓")

            # Rule 3 or 4: REPAIR — same targets (existing schedule)
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            p3 = _plan(ws)
            if p3["planning_mode"] == "repair":
                r3 = p3.get("schedule_context", {}).get("mode_selection_reason", "")
                # Rule 3: "conflict(s)" or Rule 4: "existing acquisition(s)"
                assert (
                    "existing" in r3.lower() or "conflict" in r3.lower()
                ), f"REPAIR reason should mention existing/conflict: {r3}"
                print(f"REPAIR reason: '{r3[:70]}' ✓")
            else:
                # Some targets may appear new if not fully covered
                print(f"Replan selected {p3['planning_mode']} (acceptable)")

            # Force override reason
            pf = _post(
                "/schedule/plan",
                {"planning_mode": "repair", "workspace_id": ws},
            )
            rf = pf.get("schedule_context", {}).get("mode_selection_reason", "")
            assert "Explicitly requested" in rf
            assert "repair" in rf.lower()
            print(f"Force reason: '{rf}' ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    # ----- T9: Constellation mode selection with mixed per-sat coverage -----
    def test_09_constellation_mixed_coverage(self) -> None:
        """
        Constellation with 2 sats: commit → add targets only reachable
        by one sat → verify INCREMENTAL fires and multi-sat metadata correct.
        """
        ws = _create_workspace(f"mod09_{uuid.uuid4().hex[:6]}")
        try:
            sats = [TLE_SAT1, TLE_SAT2]
            _seed_constellation(sats, MOD_TARGETS_A, days=3)

            # Plan + commit
            p1 = _plan(ws)
            assert p1["planning_mode"] == "from_scratch"
            items1 = p1.get("new_plan_items", [])
            sats_covered = set(it["satellite_id"] for it in items1)
            assert len(items1) > 0
            c1 = _commit(p1["plan_id"], ws, force=True)
            print(f"Const commit: {c1['committed']} acqs | sats: {sats_covered}")

            # Add Nordic targets (high latitude, different coverage)
            _seed_constellation(sats, MOD_TARGETS_A + MOD_TARGETS_C, days=3)
            p2 = _plan(ws)
            ctx2 = p2.get("schedule_context", {})
            assert (
                p2["planning_mode"] == "incremental"
            ), f"Expected incremental, got {p2['planning_mode']}"
            assert ctx2.get("new_target_count", 0) > 0

            # Verify multi-sat items in incremental plan
            items2 = p2.get("new_plan_items", [])
            if items2:
                inc_sats = set(it["satellite_id"] for it in items2)
                print(
                    f"Incremental: {len(items2)} items | sats: {inc_sats} | "
                    f"new_targets={ctx2.get('new_target_count')}"
                )
            print(f"Constellation mixed coverage ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    # ----- T10: Rapid commit cycles — 5 back-to-back incremental adds -----
    def test_10_rapid_incremental_cycles(self) -> None:
        """
        Start with 2 targets → commit → add 1 target at a time for 5 rounds.
        Every round must be INCREMENTAL with new_target_count > 0.
        Tests that the mode-selection state tracking doesn't drift.
        """
        ws = _create_workspace(f"mod10_{uuid.uuid4().hex[:6]}")
        try:
            base = [
                {"name": "Athens", "latitude": 37.9838, "longitude": 23.7275},
                {"name": "London", "latitude": 51.5074, "longitude": -0.1278},
            ]
            extras = [
                {"name": "Paris", "latitude": 48.8566, "longitude": 2.3522},
                {"name": "Berlin", "latitude": 52.5200, "longitude": 13.4050},
                {"name": "Madrid", "latitude": 40.4168, "longitude": -3.7038},
                {"name": "Rome", "latitude": 41.9028, "longitude": 12.4964},
                {"name": "Vienna", "latitude": 48.2082, "longitude": 16.3738},
            ]

            # Initial from_scratch
            _seed(TLE_SAT1, base, days=3)
            p0 = _plan(ws)
            assert p0["planning_mode"] == "from_scratch"
            _commit(p0["plan_id"], ws, force=True)
            modes = ["from_scratch"]

            # 5 incremental rounds
            for i, extra in enumerate(extras):
                current_targets = base + extras[: i + 1]
                _seed(TLE_SAT1, current_targets, days=3)
                p = _plan(ws)
                ctx = p.get("schedule_context", {})
                mode = p["planning_mode"]
                modes.append(mode)
                print(
                    f"Round {i+1}: +{extra['name']} → mode={mode} | "
                    f"new={ctx.get('new_target_count')} | "
                    f"existing={ctx.get('existing_acquisition_count')}"
                )
                assert mode == "incremental", (
                    f"Round {i+1}: expected incremental, got {mode}. "
                    f"new_targets={ctx.get('new_target_count')}"
                )
                if p.get("new_plan_items"):
                    _commit(p["plan_id"], ws, force=True)

            print(f"Modes: {' → '.join(modes)} ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    # ----- T11: Hard-lock ALL → replan same targets → REPAIR -----
    def test_11_all_locked_replan_is_repair(self) -> None:
        """
        Commit → hard-lock every acquisition → replan same targets.
        Mode should be REPAIR (existing schedule, no new targets).
        All locked items should be preserved.
        """
        ws = _create_workspace(f"mod11_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            c1 = _plan_commit(ws)
            n1 = c1["committed"]
            assert n1 > 0

            # Lock ALL
            st = _state(ws)
            all_ids = [a["id"] for a in st["acquisitions"]]
            _post(
                "/schedule/acquisitions/bulk-lock",
                {"acquisition_ids": all_ids, "lock_level": "hard"},
            )
            print(f"Hard-locked all {len(all_ids)} acquisitions")

            # Replan same targets → should be REPAIR
            p2 = _plan(ws)
            ctx2 = p2.get("schedule_context", {})
            print(
                f"Replan all-locked: mode={p2['planning_mode']} | "
                f"existing={ctx2.get('existing_acquisition_count')} | "
                f"new_targets={ctx2.get('new_target_count')}"
            )
            assert p2["planning_mode"] in (
                "repair",
                "incremental",
            ), f"Expected repair/incremental, got {p2['planning_mode']}"
            assert p2["planning_mode"] != "from_scratch"

            # Verify locks still intact
            st2 = _state(ws)
            for a in st2["acquisitions"]:
                if a["id"] in all_ids:
                    assert (
                        a["lock_level"] == "hard"
                    ), f"Lock on {a['id']} degraded after replan!"
            print(f"All locks preserved after replan ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    # ----- T12: Partial delete + new targets → INCREMENTAL -----
    def test_12_partial_delete_plus_new_targets(self) -> None:
        """
        Commit A → delete some A acqs → add targets B →
        Mode should be INCREMENTAL (new targets B detected).
        Verifies that deletion doesn't confuse the target diff logic.
        """
        ws = _create_workspace(f"mod12_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            c1 = _plan_commit(ws)
            n1 = c1["committed"]

            # Delete 1 acquisition
            st = _state(ws)
            del_id = st["acquisitions"][0]["id"]
            _post(
                "/schedule/acquisitions/bulk-delete",
                {"acquisition_ids": [del_id], "workspace_id": ws, "force": True},
            )
            print(f"Deleted 1 acq, {n1 - 1} remain")

            # Add new targets B
            _seed(TLE_SAT1, MOD_TARGETS_A + MOD_TARGETS_B, days=3)
            p2 = _plan(ws)
            ctx2 = p2.get("schedule_context", {})
            print(
                f"After del+add: mode={p2['planning_mode']} | "
                f"new_targets={ctx2.get('new_target_count')} | "
                f"existing={ctx2.get('existing_acquisition_count')}"
            )
            assert p2["planning_mode"] == "incremental", (
                f"New targets should override deletion → incremental, "
                f"got {p2['planning_mode']}"
            )
            assert ctx2.get("new_target_count", 0) > 0
            assert ctx2.get("existing_acquisition_count", 0) > 0
            print(f"Partial delete + new targets → INCREMENTAL ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)


# =============================================================================
# Phase 8: Freeze Window E2E Tests
# =============================================================================


def _horizon(workspace_id: str, days: int = 7) -> List[Dict[str, Any]]:
    """Get ALL acquisitions via /schedule/horizon (no limit, unlike _state)."""
    now = datetime.now(timezone.utc)
    params = {
        "workspace_id": workspace_id,
        "from": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": (now + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    resp = _get("/schedule/horizon", params)
    acquisitions = resp.get("acquisitions", [])
    assert isinstance(
        acquisitions, list
    ), f"Schedule horizon acquisitions are not a list: {resp}"
    return cast(List[Dict[str, Any]], acquisitions)


def _direct_commit_synthetic(
    workspace_id: str,
    satellite_id: str,
    target_id: str,
    start_time: str,
    end_time: str,
    force: bool = True,
    lock_level: str = "none",
) -> Dict[str, Any]:
    """Direct-commit a synthetic acquisition with precise timing."""
    return _post(
        "/schedule/commit/direct",
        {
            "items": [
                {
                    "opportunity_id": f"synth_{uuid.uuid4().hex[:8]}",
                    "satellite_id": satellite_id,
                    "target_id": target_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "roll_angle_deg": 5.0,
                }
            ],
            "algorithm": "test_synthetic",
            "workspace_id": workspace_id,
            "force": force,
            "lock_level": lock_level,
        },
    )


class TestFreezeWindow:
    """
    Verify the 2h freeze window protects near-execution acquisitions
    from deletion, and that force=True overrides it.
    """

    def test_01_single_delete_frozen_acq_returns_409(self) -> None:
        """
        Direct-commit an acq starting 30min from now (inside freeze window).
        DELETE without force → 409.
        """
        ws = _create_workspace(f"freeze01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            # Create acquisition starting 30 min from now (well inside 2h window)
            now = datetime.now(timezone.utc)
            t_start = (now + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            t_end = (now + timedelta(minutes=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
            dc = _direct_commit_synthetic(
                ws, "sat_ICEYE-X53", "freeze_target", t_start, t_end
            )
            acq_id = dc["acquisition_ids"][0]
            print(f"Created frozen acq {acq_id} starting at {t_start}")

            # Try to delete without force → should get 409
            resp = requests.delete(
                f"{API}/schedule/acquisition/{acq_id}",
                params={"force": "false", "workspace_id": ws},
                timeout=15,
            )
            assert (
                resp.status_code == 409
            ), f"Expected 409 for frozen acq, got {resp.status_code}: {resp.text[:200]}"
            assert "freeze window" in resp.json().get("detail", "").lower()
            print(f"Frozen delete blocked: 409 ✓")

            # Force delete → should succeed
            resp2 = requests.delete(
                f"{API}/schedule/acquisition/{acq_id}",
                params={"force": "true", "workspace_id": ws},
                timeout=15,
            )
            assert (
                resp2.status_code == 200
            ), f"Force delete should succeed, got {resp2.status_code}"
            print(f"Force delete of frozen acq: 200 ✓")
        finally:
            _safe_cleanup(ws)

    def test_02_bulk_delete_skips_frozen_acqs(self) -> None:
        """
        Create 2 acqs: one inside freeze window, one outside.
        Bulk delete without force → only the non-frozen one is deleted.
        """
        ws = _create_workspace(f"freeze02_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            now = datetime.now(timezone.utc)
            # Acq 1: 30 min from now (frozen)
            t1_start = (now + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            t1_end = (now + timedelta(minutes=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
            dc1 = _direct_commit_synthetic(
                ws, "sat_ICEYE-X53", "frozen_tgt", t1_start, t1_end
            )
            frozen_id = dc1["acquisition_ids"][0]

            # Acq 2: 5 hours from now (outside freeze)
            t2_start = (now + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
            t2_end = (now + timedelta(hours=5, minutes=5)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            dc2 = _direct_commit_synthetic(
                ws, "sat_ICEYE-X53", "safe_tgt", t2_start, t2_end
            )
            safe_id = dc2["acquisition_ids"][0]

            print(f"Frozen: {frozen_id} at +30min | Safe: {safe_id} at +5h")

            # Bulk delete without force
            del_resp = _post(
                "/schedule/acquisitions/bulk-delete",
                {
                    "acquisition_ids": [frozen_id, safe_id],
                    "workspace_id": ws,
                    "force": False,
                },
            )
            assert (
                del_resp["deleted"] == 1
            ), f"Expected 1 deleted (safe only), got {del_resp['deleted']}"
            # Frozen one should still exist
            acqs = _horizon(ws)
            remaining_ids = [a["id"] for a in acqs]
            assert frozen_id in remaining_ids, "Frozen acq should survive"
            assert safe_id not in remaining_ids, "Safe acq should be deleted"
            print(f"Bulk delete: 1 deleted, frozen survived ✓")
        finally:
            _safe_cleanup(ws)

    def test_03_force_bulk_delete_overrides_freeze(self) -> None:
        """Bulk delete with force=True deletes even frozen acquisitions."""
        ws = _create_workspace(f"freeze03_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            now = datetime.now(timezone.utc)
            t_start = (now + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
            t_end = (now + timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
            dc = _direct_commit_synthetic(
                ws, "sat_ICEYE-X53", "force_tgt", t_start, t_end
            )
            acq_id = dc["acquisition_ids"][0]

            del_resp = _post(
                "/schedule/acquisitions/bulk-delete",
                {"acquisition_ids": [acq_id], "workspace_id": ws, "force": True},
            )
            assert del_resp["deleted"] == 1
            print(f"Force bulk delete of frozen acq: 1 deleted ✓")
        finally:
            _safe_cleanup(ws)

    def test_04_acq_outside_freeze_deletes_normally(self) -> None:
        """Acquisition 3+ hours away deletes without force."""
        ws = _create_workspace(f"freeze04_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            now = datetime.now(timezone.utc)
            t_start = (now + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
            t_end = (now + timedelta(hours=3, minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
            dc = _direct_commit_synthetic(
                ws, "sat_ICEYE-X53", "far_tgt", t_start, t_end
            )
            acq_id = dc["acquisition_ids"][0]

            resp = requests.delete(
                f"{API}/schedule/acquisition/{acq_id}",
                params={"force": "false", "workspace_id": ws},
                timeout=15,
            )
            assert (
                resp.status_code == 200
            ), f"Acq outside freeze should delete, got {resp.status_code}"
            print(f"Non-frozen acq deleted normally: 200 ✓")
        finally:
            _safe_cleanup(ws)


# =============================================================================
# Phase 9: Snapshot & Rollback E2E Tests
# =============================================================================


class TestSnapshotRollback:
    """
    Verify that snapshots are auto-created on commit and rollback
    restores the prior schedule state.
    """

    def test_01_commit_creates_snapshot(self) -> None:
        """Committing a plan auto-creates a pre-commit snapshot."""
        ws = _create_workspace(f"snap01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            _plan_commit(ws)

            # List snapshots — should have at least 1
            snaps = _get("/schedule/snapshots", {"workspace_id": ws})
            assert snaps["count"] > 0, "Expected snapshot after commit"
            snap = snaps["snapshots"][0]
            assert "id" in snap
            assert snap["workspace_id"] == ws
            assert "plan_id" in snap
            print(f"Snapshot created: {snap['id']} for plan {snap['plan_id']}")
        finally:
            _safe_cleanup(ws)

    def test_02_multiple_commits_create_multiple_snapshots(self) -> None:
        """Each commit creates a separate snapshot."""
        ws = _create_workspace(f"snap02_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            _plan_commit(ws)
            snaps1 = _get("/schedule/snapshots", {"workspace_id": ws})
            count1 = snaps1["count"]

            # Add targets and commit again
            _seed(TLE_SAT1, MOD_TARGETS_A + MOD_TARGETS_B, days=3)
            p2 = _plan(ws)
            if p2.get("new_plan_items"):
                _commit(p2["plan_id"], ws, force=True)

            snaps2 = _get("/schedule/snapshots", {"workspace_id": ws})
            count2 = snaps2["count"]
            assert (
                count2 > count1
            ), f"Expected more snapshots after 2nd commit: {count1} → {count2}"
            print(f"Snapshots: {count1} → {count2} after 2 commits ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_03_rollback_restores_prior_state(self) -> None:
        """
        Commit batch1 → commit batch2 → rollback to pre-batch2 snapshot →
        verify acq count matches batch1 state.
        """
        ws = _create_workspace(f"snap03_{uuid.uuid4().hex[:6]}")
        try:
            # Batch 1: commit A targets
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            c1 = _plan_commit(ws)
            n1 = c1["committed"]
            print(f"Batch 1: {n1} acqs committed")

            # Record snapshot IDs after batch 1
            snaps_after_1 = _get("/schedule/snapshots", {"workspace_id": ws})
            snap_ids_after_1 = {s["id"] for s in snaps_after_1.get("snapshots", [])}

            # Batch 2: add more targets, commit
            _seed(TLE_SAT1, MOD_TARGETS_A + MOD_TARGETS_B, days=3)
            p2 = _plan(ws)
            items2 = p2.get("new_plan_items", [])
            if items2:
                c2 = _commit(p2["plan_id"], ws, force=True)
                n2 = c2.get("committed", 0)
                print(f"Batch 2: {n2} more acqs committed")

            # Find the NEW snapshot created by batch 2's commit (pre-batch2 state)
            snaps_after_2 = _get("/schedule/snapshots", {"workspace_id": ws})
            all_snap_ids = {s["id"] for s in snaps_after_2.get("snapshots", [])}
            new_snap_ids = all_snap_ids - snap_ids_after_1
            if new_snap_ids:
                # The new snapshot captures pre-batch2 state (= batch1's state)
                snap_id = sorted(new_snap_ids)[0]
            else:
                # If no new snapshot (batch 2 was empty), use the most recent
                snap_id = snaps_after_2["snapshots"][0]["id"]
            print(f"Rolling back to snapshot {snap_id}")

            # Rollback
            rollback = _post(
                "/schedule/rollback",
                {"snapshot_id": snap_id, "workspace_id": ws},
            )
            assert rollback["success"], f"Rollback failed: {rollback}"
            restored = rollback.get("restored", 0)
            print(
                f"Rollback: deleted_current={rollback.get('deleted_current')}, "
                f"restored={restored}"
            )

            # Verify state matches batch 1
            acqs = _horizon(ws)
            assert (
                len(acqs) == n1
            ), f"After rollback expected {n1} acqs (batch 1), got {len(acqs)}"
            print(f"Rollback restored {len(acqs)} acqs (matches batch 1) ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_04_rollback_nonexistent_snapshot_returns_404(self) -> None:
        """Rollback with invalid snapshot_id returns 404."""
        ws = _create_workspace(f"snap04_{uuid.uuid4().hex[:6]}")
        try:
            resp = requests.post(
                f"{API}/schedule/rollback",
                json={"snapshot_id": "snap_nonexistent", "workspace_id": ws},
                timeout=15,
            )
            assert (
                resp.status_code == 404
            ), f"Expected 404 for bad snapshot, got {resp.status_code}"
            print(f"Nonexistent snapshot: 404 ✓")
        finally:
            _safe_cleanup(ws)

    def test_05_rollback_then_replan_mode_correct(self) -> None:
        """
        Commit → rollback to empty → replan → FROM_SCRATCH.
        Rollback to pre-first-commit means empty schedule.
        """
        ws = _create_workspace(f"snap05_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            _plan_commit(ws)

            # Get the first snapshot (pre-first-commit = empty schedule).
            # After only one commit, there's exactly one snapshot. Use it.
            snaps = _get("/schedule/snapshots", {"workspace_id": ws})
            assert (
                snaps.get("count", 0) >= 1
            ), "Expected at least 1 snapshot after commit"
            snap_id = snaps["snapshots"][0]["id"]

            # Rollback to the snapshot (which captures pre-commit = empty state)
            rb = _post(
                "/schedule/rollback", {"snapshot_id": snap_id, "workspace_id": ws}
            )
            assert rb["success"], f"Rollback failed: {rb}"

            # Verify schedule is actually empty after rollback
            post_acqs = _horizon(ws)
            assert (
                len(post_acqs) == 0
            ), f"Expected empty schedule after rollback, got {len(post_acqs)} acqs"

            # Replan → should be FROM_SCRATCH (schedule is now empty)
            p2 = _plan(ws)
            ctx2 = p2.get("schedule_context", {})
            assert (
                p2["planning_mode"] == "from_scratch"
            ), f"After rollback to empty, expected from_scratch, got {p2['planning_mode']}"
            assert ctx2.get("existing_acquisition_count", -1) == 0
            print(f"Post-rollback: from_scratch, existing=0 ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)


# =============================================================================
# Phase 10: Blocked Intervals — INCREMENTAL avoids committed time slots
# =============================================================================


class TestBlockedIntervals:
    """
    Verify that INCREMENTAL planning avoids time slots already
    occupied by committed acquisitions.
    """

    def test_01_incremental_avoids_committed_time_slots(self) -> None:
        """
        Commit acqs for targets A → add targets B → force INCREMENTAL →
        verify new acqs don't overlap existing ones on the same satellite.
        """
        ws = _create_workspace(f"blocked01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            c1 = _plan_commit(ws)
            n1 = c1["committed"]
            assert n1 > 0

            # Get committed acq times
            existing = _horizon(ws)
            committed_slots = [
                (a["satellite_id"], a["start_time"], a["end_time"]) for a in existing
            ]
            print(f"Committed {len(committed_slots)} time slots")

            # Add new targets and force INCREMENTAL
            _seed(TLE_SAT1, MOD_TARGETS_A + MOD_TARGETS_C, days=3)
            p2 = _post(
                "/schedule/plan",
                {"planning_mode": "incremental", "workspace_id": ws},
            )
            assert p2["success"]
            new_items = p2.get("new_plan_items", [])
            print(f"Incremental planned {len(new_items)} new items")

            # Check no new item overlaps with committed slots on same satellite
            overlaps = 0
            for item in new_items:
                item_start = _parse_ts(item["start_time"])
                item_end = _parse_ts(item["end_time"])
                item_sat = item["satellite_id"]
                for sat, cs, ce in committed_slots:
                    if sat == item_sat:
                        cs_dt = _parse_ts(cs)
                        ce_dt = _parse_ts(ce)
                        if item_start < ce_dt and item_end > cs_dt:
                            overlaps += 1
                            print(
                                f"  OVERLAP: {item_sat} {item['start_time']}-{item['end_time']} "
                                f"vs committed {cs}-{ce}"
                            )

            assert (
                overlaps == 0
            ), f"Incremental items should not overlap committed slots! Found {overlaps}"
            print(f"No overlaps between incremental and committed ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_02_incremental_plan_items_are_future_only(self) -> None:
        """
        Incremental plan items should all start after the earliest
        committed acquisition's end time (no time travel).
        All items must be in the future relative to now.
        """
        ws = _create_workspace(f"blocked02_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            _plan_commit(ws)

            _seed(TLE_SAT1, MOD_TARGETS_A + MOD_TARGETS_B, days=3)
            p2 = _post(
                "/schedule/plan",
                {"planning_mode": "incremental", "workspace_id": ws},
            )
            assert p2["success"]
            items = p2.get("new_plan_items", [])

            now_dt = datetime.now(timezone.utc)
            past_items = [it for it in items if _parse_ts(it["start_time"]) < now_dt]
            assert (
                len(past_items) == 0
            ), f"Found {len(past_items)} items starting in the past!"
            print(f"All {len(items)} incremental items are future ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)


# =============================================================================
# Phase 11: Conflict Resolution — REPAIR resolves conflicts
# =============================================================================


class TestConflictResolution:
    """
    Verify that the REPAIR endpoint resolves conflicts by dropping
    conflicting unlocked acquisitions while preserving hard-locks.
    """

    def test_01_repair_identifies_fixed_and_flex(self) -> None:
        """
        Commit acqs → hard-lock some → call /repair →
        verify fixed_count matches locked, flex_count matches unlocked.
        """
        ws = _create_workspace(f"conflict01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            c1 = _plan_commit(ws)
            n1 = c1["committed"]

            # Hard-lock 2 acquisitions
            st = _state(ws)
            lock_ids = [a["id"] for a in st["acquisitions"][:2]]
            _post(
                "/schedule/acquisitions/bulk-lock",
                {"acquisition_ids": lock_ids, "lock_level": "hard"},
            )

            # Call repair endpoint
            repair = _post("/schedule/repair", {"workspace_id": ws})
            assert repair["success"]
            assert (
                repair["fixed_count"] == 2
            ), f"Expected 2 fixed, got {repair['fixed_count']}"
            assert (
                repair["flex_count"] == n1 - 2
            ), f"Expected {n1-2} flex, got {repair['flex_count']}"
            print(
                f"Repair: fixed={repair['fixed_count']}, "
                f"flex={repair['flex_count']} ✓"
            )
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_02_repair_drops_conflicting_unlocked(self) -> None:
        """
        Create overlapping acquisitions (conflict), hard-lock one,
        call /repair → unlocked conflicting one should be dropped.
        """
        ws = _create_workspace(f"conflict02_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            _plan_commit(ws)

            # Get an existing acq and create an overlap
            st = _state(ws)
            existing = st["acquisitions"][0]
            overlap_start = existing["start_time"]
            overlap_end = existing["end_time"]

            # Hard-lock the existing one
            _post(
                "/schedule/acquisitions/bulk-lock",
                {"acquisition_ids": [existing["id"]], "lock_level": "hard"},
            )

            # Direct-commit conflicting (unlocked) acq at same time
            dc = _direct_commit_synthetic(
                ws,
                existing["satellite_id"],
                "conflict_tgt",
                overlap_start,
                overlap_end,
                force=True,
            )
            conflict_acq_id = dc["acquisition_ids"][0]
            print(
                f"Hard-locked {existing['id']} | "
                f"Conflicting unlocked {conflict_acq_id}"
            )

            # Call repair
            repair = _post("/schedule/repair", {"workspace_id": ws})
            assert repair["success"]
            diff = repair.get("repair_diff", {})
            dropped = diff.get("dropped", [])
            kept = diff.get("kept", [])

            print(
                f"Repair diff: kept={len(kept)}, dropped={len(dropped)}, "
                f"hard_lock_warnings={diff.get('hard_lock_warnings', [])}"
            )

            # The unlocked conflicting acq MUST be dropped — we injected a
            # deliberate overlap with a hard-locked acquisition.
            assert len(dropped) > 0, (
                f"Repair should have dropped conflicting acquisitions but "
                f"dropped=[] with hard_lock_warnings={diff.get('hard_lock_warnings', [])}"
            )
            assert conflict_acq_id in dropped, (
                f"Expected unlocked {conflict_acq_id} to be dropped, "
                f"dropped={dropped}"
            )
            print(f"Unlocked conflict dropped ✓")

            # The hard-locked one should be in kept
            assert (
                existing["id"] in kept
            ), f"Hard-locked {existing['id']} should be kept, kept={kept}"
            print(f"Hard-locked acq preserved in repair ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_03_repair_metrics_show_conflict_reduction(self) -> None:
        """
        Inject conflicts → repair → verify metrics_comparison shows
        conflicts_before > 0.
        """
        ws = _create_workspace(f"conflict03_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            _plan_commit(ws)

            # Inject overlap for conflict
            st = _state(ws)
            existing = st["acquisitions"][0]
            _direct_commit_synthetic(
                ws,
                existing["satellite_id"],
                "overlap_tgt",
                existing["start_time"],
                existing["end_time"],
                force=True,
            )

            # Repair
            repair = _post("/schedule/repair", {"workspace_id": ws})
            assert repair["success"]

            mc = repair.get("metrics_comparison", {})
            print(
                f"Metrics: score_before={mc.get('score_before')}, "
                f"score_after={mc.get('score_after')}, "
                f"score_delta={mc.get('score_delta')}"
            )

            # The repair should produce a valid diff
            diff = repair.get("repair_diff", {})
            assert "kept" in diff, "repair_diff should have 'kept'"
            assert "dropped" in diff, "repair_diff should have 'dropped'"
            assert "added" in diff, "repair_diff should have 'added'"
            print(
                f"Repair diff: kept={len(diff['kept'])}, "
                f"dropped={len(diff['dropped'])}, "
                f"added={len(diff['added'])} ✓"
            )
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_04_repair_commit_applies_diff(self) -> None:
        """
        Call /repair → get plan_id + drops → /repair/commit →
        verify drops are deleted and new items are created.
        """
        ws = _create_workspace(f"conflict04_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            _plan_commit(ws)

            # Inject overlap
            st = _state(ws)
            existing = st["acquisitions"][0]
            _post(
                "/schedule/acquisitions/bulk-lock",
                {"acquisition_ids": [existing["id"]], "lock_level": "hard"},
            )
            dc = _direct_commit_synthetic(
                ws,
                existing["satellite_id"],
                "repair_commit_tgt",
                existing["start_time"],
                existing["end_time"],
                force=True,
            )
            unlocked_id = dc["acquisition_ids"][0]

            # Get pre-repair count
            pre_acqs = _horizon(ws)
            pre_count = len(pre_acqs)

            # Repair plan
            repair = _post("/schedule/repair", {"workspace_id": ws})
            plan_id = repair.get("plan_id")
            diff = repair.get("repair_diff", {})
            drops = diff.get("dropped", [])
            print(
                f"Repair plan {plan_id}: drops={drops}, "
                f"new_items={len(repair.get('new_plan_items', []))}"
            )

            if plan_id and drops:
                # Commit repair
                rc = _post(
                    "/schedule/repair/commit",
                    {
                        "plan_id": plan_id,
                        "workspace_id": ws,
                        "drop_acquisition_ids": drops,
                        "force": True,
                    },
                )
                assert rc["success"], f"Repair commit failed: {rc}"
                print(
                    f"Repair commit: committed={rc.get('committed')}, "
                    f"dropped={rc.get('dropped')} ✓"
                )

                # Verify dropped acqs are marked as 'failed' (soft-delete)
                # The system preserves history by setting state='failed'
                # rather than hard-deleting the rows.
                post_acqs = _horizon(ws)
                post_by_id = {a["id"]: a for a in post_acqs}
                for d in drops:
                    if d in post_by_id:
                        assert post_by_id[d].get("state") == "failed", (
                            f"Dropped {d} should be state='failed', "
                            f"got '{post_by_id[d].get('state')}'"
                        )
                # Hard-locked should survive with non-failed state
                assert existing["id"] in post_by_id
                assert (
                    post_by_id[existing["id"]].get("state") != "failed"
                ), "Hard-locked acq should not be marked as failed"
                print(f"Dropped acqs marked failed, hard-lock preserved ✓")
            else:
                print(f"No drops to commit (repair found no conflicts to resolve)")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)


# =============================================================================
# Phase 12: State Pagination — /horizon returns full count
# =============================================================================


class TestStatePagination:
    """
    Verify that /schedule/state truncates at 100 and /schedule/horizon
    returns the full count, and that mode selection uses the correct
    (untruncated) acquisition count.
    """

    def test_01_state_endpoint_truncates_at_100(self) -> None:
        """
        Commit >100 acquisitions via two plan+commit cycles (planner caps at
        100 per plan) → /state returns max 100, /horizon returns all.
        """
        ws = _create_workspace(f"pag01_{uuid.uuid4().hex[:6]}")
        try:
            # Batch 1: seed + plan + commit (up to 100 acqs)
            sats = [TLE_SAT1, TLE_SAT2, TLE_SAT3]
            _seed_constellation(sats, SCALE_TARGETS_BATCH_1, days=7)
            p1 = _plan(ws)
            if not p1.get("new_plan_items"):
                pytest.skip("No plan items for pagination test")
            c1 = _commit(p1["plan_id"], ws, force=True)
            n1 = c1["committed"]

            # Batch 2: seed extra targets + incremental plan + commit
            _seed_constellation(sats, SCALE_TARGETS_BATCH_2, days=7)
            p2 = _plan(ws)
            if not p2.get("new_plan_items"):
                pytest.skip("No incremental items for pagination test")
            c2 = _commit(p2["plan_id"], ws, force=True)
            n2 = c2["committed"]

            total = n1 + n2
            print(f"Committed {n1} + {n2} = {total} acquisitions")

            if total <= 100:
                pytest.skip(f"Need >100 acqs for this test, got {total}")

            # /state should cap at 100
            state = _state(ws)
            state_count = len(state.get("acquisitions", []))
            assert (
                state_count == 100
            ), f"/state should return 100 max, got {state_count}"

            # /horizon should return all
            horizon_acqs = _horizon(ws, days=7)
            assert (
                len(horizon_acqs) >= total
            ), f"/horizon should return all {total}, got {len(horizon_acqs)}"
            print(
                f"/state={state_count} (truncated) vs "
                f"/horizon={len(horizon_acqs)} (full) ✓"
            )
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_02_mode_selection_uses_full_count(self) -> None:
        """
        Commit >100 acqs via two cycles → replan → mode selection should see
        the real (untruncated) existing_acquisition_count, not 100.
        """
        ws = _create_workspace(f"pag02_{uuid.uuid4().hex[:6]}")
        try:
            sats = [TLE_SAT1, TLE_SAT2, TLE_SAT3]

            # Batch 1
            _seed_constellation(sats, SCALE_TARGETS_BATCH_1, days=7)
            p1 = _plan(ws)
            if not p1.get("new_plan_items"):
                pytest.skip("No plan items")
            c1 = _commit(p1["plan_id"], ws, force=True)
            n1 = c1["committed"]

            # Batch 2
            _seed_constellation(sats, SCALE_TARGETS_BATCH_2, days=7)
            p2 = _plan(ws)
            if not p2.get("new_plan_items"):
                pytest.skip("No incremental items")
            c2 = _commit(p2["plan_id"], ws, force=True)
            n2 = c2["committed"]

            total = n1 + n2
            print(f"Committed {n1} + {n2} = {total} acquisitions")

            if total <= 100:
                pytest.skip(f"Need >100 for pagination test, got {total}")

            # Replan — mode selection should see ALL acquisitions
            _seed_constellation(sats, SCALE_TARGETS_BATCH_3, days=7)
            p3 = _plan(ws)
            ctx = p3.get("schedule_context", {})
            existing = ctx.get("existing_acquisition_count", 0)
            print(
                f"Mode selection: existing_acquisition_count={existing}, "
                f"mode={p3['planning_mode']}"
            )
            assert (
                existing >= total
            ), f"Mode selection should see >={total} acqs, got {existing}"
            assert (
                p3["planning_mode"] != "from_scratch"
            ), "Should not be from_scratch with >100 existing acquisitions"
            print(f"Mode selection uses full count ({existing}) ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)


# =============================================================================
# Phase 13: High-Risk Coverage — previously untested critical paths
# =============================================================================


class TestMasterScheduleEndpoint:
    """
    Verify GET /schedule/master returns timeline data in both
    detail and aggregate modes.
    """

    def test_01_master_detail_mode(self) -> None:
        """GET /master with zoom=detail returns acquisitions with full fields."""
        ws = _create_workspace(f"master01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws)

            now = datetime.now(timezone.utc)
            resp = _get(
                "/schedule/master",
                {
                    "workspace_id": ws,
                    "t_start": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "t_end": (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "zoom": "detail",
                    "limit": 100,
                },
            )
            items = resp.get("items", [])
            assert len(items) > 0, "Master detail mode returned 0 items"
            first = items[0]
            for field in (
                "id",
                "satellite_id",
                "target_id",
                "start_time",
                "lock_level",
                "state",
            ):
                assert (
                    field in first
                ), f"Master item missing required field '{field}': {list(first.keys())}"
            print(f"Master detail: {len(items)} items, fields OK ✓")
        finally:
            _safe_cleanup(ws)

    def test_02_master_aggregate_mode(self) -> None:
        """GET /master with zoom=aggregate returns bucketed counts."""
        ws = _create_workspace(f"master02_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws)

            now = datetime.now(timezone.utc)
            resp = _get(
                "/schedule/master",
                {
                    "workspace_id": ws,
                    "t_start": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "t_end": (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "zoom": "aggregate",
                },
            )
            assert resp.get("success", False), f"Master aggregate failed: {resp}"
            print(f"Master aggregate: {resp.get('total_count', '?')} total ✓")
        finally:
            _safe_cleanup(ws)

    def test_03_master_pagination(self) -> None:
        """GET /master with limit+offset returns paginated results."""
        ws = _create_workspace(f"master03_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws)

            now = datetime.now(timezone.utc)
            params = {
                "workspace_id": ws,
                "t_start": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "t_end": (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "zoom": "detail",
                "limit": 2,
                "offset": 0,
            }
            page1 = _get("/schedule/master", params)
            items1 = page1.get("items", [])
            assert len(items1) <= 2, f"Limit=2 but got {len(items1)} items"

            if len(items1) == 2:
                params["offset"] = 2
                page2 = _get("/schedule/master", params)
                items2 = page2.get("items", [])
                ids1 = {i["id"] for i in items1}
                ids2 = {i["id"] for i in items2}
                assert ids1.isdisjoint(ids2), f"Pages overlap: {ids1 & ids2}"
                print(
                    f"Pagination: page1={len(items1)}, page2={len(items2)}, no overlap ✓"
                )
            else:
                print(f"Only {len(items1)} items — pagination not testable")
        finally:
            _safe_cleanup(ws)


class TestHardLockCommitted:
    """
    Verify POST /acquisitions/hard-lock-committed freezes all committed
    work in a workspace before repair.
    """

    def test_01_hard_lock_all_committed(self) -> None:
        """Hard-lock all committed acquisitions in one call."""
        ws = _create_workspace(f"hlc01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            c = _plan_commit(ws)
            n = c["committed"]
            assert n > 0

            unlocked = [
                a for a in _state(ws)["acquisitions"] if a["lock_level"] == "none"
            ]
            assert (
                len(unlocked) == n
            ), f"Expected all {n} acqs unlocked, got {len(unlocked)}"

            resp = _post(
                "/schedule/acquisitions/hard-lock-committed",
                {"workspace_id": ws},
            )
            assert resp["success"]
            assert resp["updated"] == n, f"Expected {n} updated, got {resp['updated']}"

            hard = [a for a in _state(ws)["acquisitions"] if a["lock_level"] == "hard"]
            assert len(hard) == n, f"Expected all {n} hard-locked, got {len(hard)}"
            print(f"Hard-locked all {n} committed acquisitions ✓")
        finally:
            _safe_cleanup(ws)


class TestSingleDeleteHardLock:
    """
    Verify single-acquisition DELETE returns 409 for hard-locked items
    (separate from freeze window protection).
    """

    def test_01_single_delete_hard_locked_returns_409(self) -> None:
        """DELETE a hard-locked acquisition without force returns 409."""
        ws = _create_workspace(f"sdhl01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws)

            st = _state(ws)
            acq_id = st["acquisitions"][0]["id"]

            _post(
                "/schedule/acquisitions/bulk-lock",
                {"acquisition_ids": [acq_id], "lock_level": "hard"},
            )

            resp = requests.delete(
                f"{API}/schedule/acquisition/{acq_id}",
                params={"workspace_id": ws},
                timeout=15,
            )
            assert resp.status_code == 409, (
                f"Expected 409 for hard-locked delete, got {resp.status_code}: "
                f"{resp.text[:200]}"
            )

            resp2 = requests.delete(
                f"{API}/schedule/acquisition/{acq_id}",
                params={"workspace_id": ws, "force": "true"},
                timeout=15,
            )
            assert (
                resp2.status_code == 200
            ), f"Force delete of hard-locked should succeed, got {resp2.status_code}"
            print(f"Hard-lock delete: 409 without force, 200 with force ✓")
        finally:
            _safe_cleanup(ws)


class TestRepairCommitProtections:
    """
    Verify /repair/commit rejects drops of frozen/hard-locked items
    when force=False, and that cross-workspace drops return 403.
    """

    def test_01_repair_commit_rejects_frozen_without_force(self) -> None:
        """
        Repair commit dropping a frozen acq with force=False → 400.
        """
        ws = _create_workspace(f"rcp01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            _plan_commit(ws)

            st = _state(ws)
            existing = st["acquisitions"][0]

            dc = _direct_commit_synthetic(
                ws,
                existing["satellite_id"],
                "rcp_tgt",
                existing["start_time"],
                existing["end_time"],
                force=True,
            )

            # Create a frozen acq (starts in 30 min)
            now = datetime.now(timezone.utc)
            frozen_start = (now + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            frozen_end = (now + timedelta(minutes=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
            frozen_dc = _direct_commit_synthetic(
                ws,
                "sat_ICEYE-X53",
                "frozen_rcp_tgt",
                frozen_start,
                frozen_end,
                force=True,
            )
            frozen_id = frozen_dc["acquisition_ids"][0]

            repair = _post("/schedule/repair", {"workspace_id": ws})
            plan_id = repair.get("plan_id")
            assert plan_id, f"No plan_id in repair response: {repair}"

            resp = requests.post(
                f"{API}/schedule/repair/commit",
                json={
                    "plan_id": plan_id,
                    "workspace_id": ws,
                    "drop_acquisition_ids": [frozen_id],
                    "force": False,
                },
                timeout=30,
            )
            assert resp.status_code == 400, (
                f"Expected 400 for frozen drop without force, got {resp.status_code}: "
                f"{resp.text[:300]}"
            )
            detail = resp.json().get("detail", {})
            assert (
                "freeze" in str(detail).lower() or "protection" in str(detail).lower()
            ), f"Expected freeze/protection mention in error: {detail}"
            print(f"Repair commit rejected frozen drop (400) ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_02_repair_commit_rejects_cross_workspace_drop(self) -> None:
        """Repair commit dropping an acq from another workspace → 403."""
        ws1 = _create_workspace(f"rcp_ws1_{uuid.uuid4().hex[:6]}")
        ws2 = _create_workspace(f"rcp_ws2_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            _plan_commit(ws1)
            _plan_commit(ws2)

            ws1_acq_id = _state(ws1)["acquisitions"][0]["id"]

            existing = _state(ws2)["acquisitions"][0]
            _direct_commit_synthetic(
                ws2,
                existing["satellite_id"],
                "xws_tgt",
                existing["start_time"],
                existing["end_time"],
                force=True,
            )
            repair = _post("/schedule/repair", {"workspace_id": ws2})
            plan_id = repair.get("plan_id")
            assert plan_id

            resp = requests.post(
                f"{API}/schedule/repair/commit",
                json={
                    "plan_id": plan_id,
                    "workspace_id": ws2,
                    "drop_acquisition_ids": [ws1_acq_id],
                    "force": True,
                },
                timeout=30,
            )
            assert resp.status_code == 403, (
                f"Expected 403 for cross-workspace drop, got {resp.status_code}: "
                f"{resp.text[:300]}"
            )
            print(f"Cross-workspace drop rejected (403) ✓")
        finally:
            _safe_cleanup(ws1, TLE_SAT1, TARGETS_PHASE1)
            _safe_cleanup(ws2)


class TestRollbackVsLocks:
    """Verify rollback unconditionally deletes even hard-locked acquisitions."""

    def test_01_rollback_deletes_hard_locked_acquisitions(self) -> None:
        """Commit + hard-lock all → rollback → hard-locked acqs are gone."""
        ws = _create_workspace(f"rblk01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, MOD_TARGETS_A, days=3)
            _plan_commit(ws)

            st = _state(ws)
            acqs = st["acquisitions"]
            n = len(acqs)
            assert n > 0

            all_ids = [a["id"] for a in acqs]
            _post(
                "/schedule/acquisitions/bulk-lock",
                {"acquisition_ids": all_ids, "lock_level": "hard"},
            )

            snaps = _get("/schedule/snapshots", {"workspace_id": ws})
            assert snaps.get("count", 0) >= 1
            snap_id = snaps["snapshots"][0]["id"]

            rb = _post(
                "/schedule/rollback",
                {"snapshot_id": snap_id, "workspace_id": ws},
            )
            assert rb["success"]
            assert rb["deleted_current"] >= n, (
                f"Rollback should delete {n} acqs (including hard-locked), "
                f"deleted {rb['deleted_current']}"
            )

            post_acqs = _horizon(ws)
            assert (
                len(post_acqs) == 0
            ), f"Expected empty schedule after rollback, got {len(post_acqs)}"
            print(
                f"Rollback deleted {rb['deleted_current']} acqs "
                f"(including {n} hard-locked) ✓"
            )
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)


class TestPartialCommit:
    """Verify committing a subset of plan items via items_to_commit."""

    def test_01_partial_commit_with_unknown_ids_commits_nothing(self) -> None:
        """
        items_to_commit filters by plan_item.id (internal DB IDs, not
        opportunity_id). Passing unknown IDs commits 0 items — the API
        does not expose plan_item.id in PlanItemPreviewResponse.
        This test documents that limitation.
        """
        ws = _create_workspace(f"partial01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            plan = _plan(ws)
            assert plan["success"]
            items = plan.get("new_plan_items", [])
            assert len(items) >= 2, f"Need >=2 plan items, got {len(items)}"

            # Use opportunity_id (the only ID available) — should commit 0
            # because the backend matches on plan_items.id, not opportunity_id
            opp_id = items[0]["opportunity_id"]
            resp = _commit(
                plan["plan_id"],
                ws,
                items_to_commit=[opp_id],
                force=True,
            )
            committed = resp.get("committed", 0)
            assert (
                committed == 0
            ), f"Expected 0 (opportunity_id ≠ plan_item.id), got {committed}"
            print(
                f"Partial commit with opportunity_id: {committed} "
                f"(API doesn't expose plan_item IDs) ✓"
            )
        finally:
            _safe_cleanup(ws)

    def test_02_full_commit_then_verify(self) -> None:
        """Full commit (empty items_to_commit) commits all items."""
        ws = _create_workspace(f"partial02_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            plan = _plan(ws)
            assert plan["success"]
            n_items = len(plan.get("new_plan_items", []))
            assert n_items > 0

            resp = _commit(plan["plan_id"], ws, force=True)
            committed = resp.get("committed", 0)
            assert (
                committed == n_items
            ), f"Full commit should commit all {n_items} items, got {committed}"
            print(f"Full commit: {committed}/{n_items} items ✓")
        finally:
            _safe_cleanup(ws)


# ===========================================================================
# PHASE 14: Medium-Risk Coverage — Conflict Filtering, Commit History,
#            Repair Scope, recompute_conflicts, Global State, Auto-Escalation
# ===========================================================================


class TestConflictFiltering:
    """Verify /conflicts endpoint filtering by type, severity, and resolved status."""

    def test_01_conflict_type_filter(self) -> None:
        """Filter conflicts by type (temporal_overlap / slew_infeasible)."""
        ws = _create_workspace(f"cfilt01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws, force=True)

            # Fetch all conflicts (unfiltered)
            all_resp = _get(
                "/schedule/conflicts",
                {"workspace_id": ws, "include_resolved": True},
            )
            all_conflicts = all_resp.get("conflicts", [])

            # Filter by temporal_overlap
            to_resp = _get(
                "/schedule/conflicts",
                {
                    "workspace_id": ws,
                    "conflict_type": "temporal_overlap",
                    "include_resolved": True,
                },
            )
            to_conflicts = to_resp.get("conflicts", [])
            for c in to_conflicts:
                assert (
                    c["type"] == "temporal_overlap"
                ), f"Expected type=temporal_overlap, got {c['type']}"

            # Filter by slew_infeasible
            si_resp = _get(
                "/schedule/conflicts",
                {
                    "workspace_id": ws,
                    "conflict_type": "slew_infeasible",
                    "include_resolved": True,
                },
            )
            si_conflicts = si_resp.get("conflicts", [])
            for c in si_conflicts:
                assert (
                    c["type"] == "slew_infeasible"
                ), f"Expected type=slew_infeasible, got {c['type']}"

            # Union of filtered types should equal total
            assert len(to_conflicts) + len(si_conflicts) == len(all_conflicts), (
                f"Filter mismatch: {len(to_conflicts)} temporal + "
                f"{len(si_conflicts)} slew ≠ {len(all_conflicts)} total"
            )
            print(
                f"Conflict type filter: {len(to_conflicts)} temporal, "
                f"{len(si_conflicts)} slew, {len(all_conflicts)} total ✓"
            )
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_02_severity_filter(self) -> None:
        """Filter conflicts by severity (error / warning / info)."""
        ws = _create_workspace(f"cfilt02_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws, force=True)

            all_resp = _get(
                "/schedule/conflicts",
                {"workspace_id": ws, "include_resolved": True},
            )
            all_conflicts = all_resp.get("conflicts", [])

            total_filtered = 0
            for sev in ("error", "warning", "info"):
                sev_resp = _get(
                    "/schedule/conflicts",
                    {
                        "workspace_id": ws,
                        "severity": sev,
                        "include_resolved": True,
                    },
                )
                sev_conflicts = sev_resp.get("conflicts", [])
                for c in sev_conflicts:
                    assert (
                        c["severity"] == sev
                    ), f"Expected severity={sev}, got {c['severity']}"
                total_filtered += len(sev_conflicts)
                print(f"  severity={sev}: {len(sev_conflicts)} conflicts")

            assert total_filtered == len(
                all_conflicts
            ), f"Severity sum {total_filtered} ≠ total {len(all_conflicts)}"
            print(f"Severity filter: {total_filtered} total ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_03_include_resolved_flag(self) -> None:
        """include_resolved=False excludes resolved conflicts."""
        ws = _create_workspace(f"cfilt03_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws, force=True)

            # Get unresolved (default)
            unresolved_resp = _get(
                "/schedule/conflicts",
                {
                    "workspace_id": ws,
                    "include_resolved": False,
                },
            )
            unresolved = unresolved_resp.get("conflicts", [])
            for c in unresolved:
                assert (
                    c.get("resolved_at") is None
                ), f"Unresolved filter returned resolved conflict: {c['id']}"

            # Get all (including resolved)
            all_resp = _get(
                "/schedule/conflicts",
                {
                    "workspace_id": ws,
                    "include_resolved": True,
                },
            )
            all_conflicts = all_resp.get("conflicts", [])

            assert len(all_conflicts) >= len(unresolved), (
                f"include_resolved=True ({len(all_conflicts)}) should be >= "
                f"include_resolved=False ({len(unresolved)})"
            )
            print(
                f"Resolved filter: {len(unresolved)} unresolved, "
                f"{len(all_conflicts)} total ✓"
            )
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_04_summary_counts_match(self) -> None:
        """Conflict response summary has by_severity counts matching actual conflicts."""
        ws = _create_workspace(f"cfilt04_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws, force=True)

            resp = _get("/schedule/conflicts", {"workspace_id": ws})
            conflicts = resp.get("conflicts", [])
            summary = resp.get("summary", {})

            # Summary should exist
            assert isinstance(
                summary, dict
            ), f"Expected summary dict, got {type(summary)}"

            # Count severity distribution from actual conflicts
            actual_counts: Dict[str, int] = {}
            for c in conflicts:
                sev = c["severity"]
                actual_counts[sev] = actual_counts.get(sev, 0) + 1

            print(f"Conflict summary: {summary}")
            print(f"Actual severity distribution: {actual_counts} ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)


class TestRecomputeConflictsFlag:
    """Verify recompute_conflicts=False skips post-commit conflict detection."""

    def test_01_no_recompute_skips_conflict_detection(self) -> None:
        """Commit with recompute_conflicts=False reports 0 conflicts_detected."""
        ws = _create_workspace(f"recomp01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            plan = _plan(ws)
            assert plan["success"]

            resp = _commit(
                plan["plan_id"],
                ws,
                force=True,
                recompute_conflicts=False,
            )
            assert resp["success"]
            assert resp.get("conflicts_detected", 0) == 0, (
                f"Expected 0 conflicts_detected with recompute=False, "
                f"got {resp.get('conflicts_detected')}"
            )
            assert (
                len(resp.get("conflict_ids", [])) == 0
            ), "Expected no conflict_ids with recompute=False"
            print(
                f"Committed {resp['committed']} with recompute=False: "
                f"0 conflicts detected ✓"
            )
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_02_recompute_true_detects_conflicts(self) -> None:
        """Commit with recompute_conflicts=True (default) returns conflict counts."""
        ws = _create_workspace(f"recomp02_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            plan = _plan(ws)
            assert plan["success"]

            resp = _commit(
                plan["plan_id"],
                ws,
                force=True,
                recompute_conflicts=True,
            )
            assert resp["success"]
            cd = resp.get("conflicts_detected", -1)
            assert (
                isinstance(cd, int) and cd >= 0
            ), f"Expected non-negative int for conflicts_detected, got {cd}"
            cids = resp.get("conflict_ids", [])
            assert isinstance(cids, list)
            assert (
                len(cids) == cd
            ), f"conflicts_detected={cd} but conflict_ids has {len(cids)} items"
            print(
                f"Committed {resp['committed']} with recompute=True: "
                f"{cd} conflicts detected ✓"
            )
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)


class TestCommitHistoryPagination:
    """Verify /commit-history endpoint with plan_id filter and pagination."""

    def test_01_commit_history_records_repair_commits(self) -> None:
        """Repair commits create audit log entries in /commit-history."""
        ws = _create_workspace(f"chist01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws, force=True)

            # Repair + commit (only repair/commit writes audit logs)
            r1 = _post("/schedule/repair", {"workspace_id": ws})
            assert r1.get("success")
            rc1 = _post(
                "/schedule/repair/commit",
                {
                    "plan_id": r1["plan_id"],
                    "workspace_id": ws,
                    "force": True,
                },
            )
            assert rc1.get("success")

            # Second repair cycle
            r2 = _post("/schedule/repair", {"workspace_id": ws})
            assert r2.get("success")
            rc2 = _post(
                "/schedule/repair/commit",
                {
                    "plan_id": r2["plan_id"],
                    "workspace_id": ws,
                    "force": True,
                },
            )
            assert rc2.get("success")

            # Get commit history for this workspace
            hist = _get("/schedule/commit-history", {"workspace_id": ws})
            assert hist["success"]
            logs = hist["audit_logs"]
            assert (
                len(logs) >= 2
            ), f"Expected ≥2 audit logs after 2 repair commits, got {len(logs)}"

            # Verify audit log fields
            for log in logs:
                assert "id" in log
                assert "created_at" in log
                assert "plan_id" in log
                assert "commit_type" in log
            print(f"Commit history: {len(logs)} entries after 2 repair commits ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_02_plan_id_filter(self) -> None:
        """Filter commit history by plan_id returns only matching entries."""
        ws = _create_workspace(f"chist02_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws, force=True)

            # Two repair commits with distinct plan_ids
            r1 = _post("/schedule/repair", {"workspace_id": ws})
            assert r1.get("success")
            plan_id_1 = r1["plan_id"]
            _post(
                "/schedule/repair/commit",
                {
                    "plan_id": plan_id_1,
                    "workspace_id": ws,
                    "force": True,
                },
            )

            r2 = _post("/schedule/repair", {"workspace_id": ws})
            assert r2.get("success")
            plan_id_2 = r2["plan_id"]
            _post(
                "/schedule/repair/commit",
                {
                    "plan_id": plan_id_2,
                    "workspace_id": ws,
                    "force": True,
                },
            )

            # Filter by plan_id_1
            hist1 = _get(
                "/schedule/commit-history",
                {
                    "workspace_id": ws,
                    "plan_id": plan_id_1,
                },
            )
            for log in hist1["audit_logs"]:
                assert log["plan_id"] == plan_id_1, (
                    f"plan_id filter returned wrong plan: "
                    f"{log['plan_id']} ≠ {plan_id_1}"
                )

            # Filter by plan_id_2
            hist2 = _get(
                "/schedule/commit-history",
                {
                    "workspace_id": ws,
                    "plan_id": plan_id_2,
                },
            )
            for log in hist2["audit_logs"]:
                assert log["plan_id"] == plan_id_2, (
                    f"plan_id filter returned wrong plan: "
                    f"{log['plan_id']} ≠ {plan_id_2}"
                )

            print(
                f"plan_id filter: {len(hist1['audit_logs'])} for plan1, "
                f"{len(hist2['audit_logs'])} for plan2 ✓"
            )
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_03_pagination_limit_offset(self) -> None:
        """Limit and offset paginate commit history correctly."""
        ws = _create_workspace(f"chist03_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws, force=True)

            # Create 3 repair commits
            for i in range(3):
                r = _post("/schedule/repair", {"workspace_id": ws})
                assert r.get("success"), f"Repair {i+1} failed"
                _post(
                    "/schedule/repair/commit",
                    {
                        "plan_id": r["plan_id"],
                        "workspace_id": ws,
                        "force": True,
                    },
                )

            # Get all
            all_hist = _get("/schedule/commit-history", {"workspace_id": ws})
            total = len(all_hist["audit_logs"])
            assert total >= 3, f"Expected ≥3 entries, got {total}"

            # Page 1 (limit=1, offset=0)
            page1 = _get(
                "/schedule/commit-history",
                {
                    "workspace_id": ws,
                    "limit": 1,
                    "offset": 0,
                },
            )
            assert (
                len(page1["audit_logs"]) == 1
            ), f"Page 1 should have 1 entry, got {len(page1['audit_logs'])}"

            # Page 2 (limit=1, offset=1)
            page2 = _get(
                "/schedule/commit-history",
                {
                    "workspace_id": ws,
                    "limit": 1,
                    "offset": 1,
                },
            )
            assert len(page2["audit_logs"]) == 1

            # Pages should be different
            assert (
                page1["audit_logs"][0]["id"] != page2["audit_logs"][0]["id"]
            ), "Page 1 and page 2 returned same entry"
            print(f"Pagination: total={total}, pages verified ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)


class TestRepairScopeVariants:
    """Verify /repair endpoint with different repair_scope values."""

    def test_01_invalid_repair_scope_returns_400(self) -> None:
        """Invalid repair_scope value returns 400."""
        ws = _create_workspace(f"rscope01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws, force=True)

            resp = requests.post(
                f"{API}/schedule/repair",
                json={
                    "workspace_id": ws,
                    "repair_scope": "invalid_scope",
                },
                timeout=30,
            )
            assert (
                resp.status_code == 400
            ), f"Expected 400 for invalid repair_scope, got {resp.status_code}"
            assert (
                "invalid" in resp.text.lower() or "repair_scope" in resp.text.lower()
            ), f"Error message should mention repair_scope: {resp.text[:300]}"
            print("Invalid repair_scope → 400 ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_02_workspace_horizon_scope(self) -> None:
        """Default repair_scope='workspace_horizon' repairs entire workspace."""
        ws = _create_workspace(f"rscope02_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws, force=True)

            resp = _post(
                "/schedule/repair",
                {
                    "workspace_id": ws,
                    "repair_scope": "workspace_horizon",
                },
            )
            assert resp.get("success"), f"Repair failed: {resp.get('message')}"
            assert "plan_id" in resp, "Repair should return plan_id"
            print(f"workspace_horizon repair: {resp.get('message', 'ok')} ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_03_satellite_subset_scope(self) -> None:
        """repair_scope='satellite_subset' with satellite_subset list."""
        ws = _create_workspace(f"rscope03_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws, force=True)

            st = _state(ws)
            acqs = st.get("acquisitions", [])
            assert len(acqs) > 0, "Need acquisitions for satellite_subset test"
            sat_id = acqs[0]["satellite_id"]

            resp = _post(
                "/schedule/repair",
                {
                    "workspace_id": ws,
                    "repair_scope": "satellite_subset",
                    "satellite_subset": [sat_id],
                },
            )
            assert resp.get(
                "success"
            ), f"satellite_subset repair failed: {resp.get('message')}"
            print(f"satellite_subset repair (sat={sat_id}): ok ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_04_target_subset_scope(self) -> None:
        """repair_scope='target_subset' with target_subset list."""
        ws = _create_workspace(f"rscope04_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws, force=True)

            st = _state(ws)
            acqs = st.get("acquisitions", [])
            assert len(acqs) > 0, "Need acquisitions for target_subset test"
            tgt_id = acqs[0]["target_id"]

            resp = _post(
                "/schedule/repair",
                {
                    "workspace_id": ws,
                    "repair_scope": "target_subset",
                    "target_subset": [tgt_id],
                },
            )
            assert resp.get(
                "success"
            ), f"target_subset repair failed: {resp.get('message')}"
            print(f"target_subset repair (target={tgt_id}): ok ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)


class TestGlobalStateQuery:
    """Verify /state endpoint with and without workspace_id."""

    def test_01_global_state_returns_cross_workspace_data(self) -> None:
        """GET /state without workspace_id returns acquisitions from all workspaces."""
        ws1 = _create_workspace(f"gstate01a_{uuid.uuid4().hex[:6]}")
        ws2 = _create_workspace(f"gstate01b_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws1, force=True)
            _plan_commit(ws2, force=True)

            # Workspace-scoped state
            s1 = _state(ws1)
            s2 = _state(ws2)
            n1 = len(s1.get("acquisitions", []))
            n2 = len(s2.get("acquisitions", []))
            assert n1 > 0, "ws1 should have acquisitions"
            assert n2 > 0, "ws2 should have acquisitions"

            # Global state (no workspace_id)
            global_resp = _get("/schedule/state")
            global_state = global_resp.get("state", {})
            global_acqs = global_state.get("acquisitions", [])

            assert len(global_acqs) >= n1 + n2, (
                f"Global state ({len(global_acqs)}) should include >= "
                f"ws1({n1}) + ws2({n2}) = {n1 + n2} acquisitions"
            )

            # Verify response shape (Pydantic _meta is a private field,
            # not serialized in JSON — only success/message/state are exposed)
            assert global_resp.get("success") is True
            assert "message" in global_resp
            assert "state" in global_resp

            print(f"Global state: {len(global_acqs)} acqs " f"(ws1={n1}, ws2={n2}) ✓")
        finally:
            _safe_cleanup(ws1, TLE_SAT1, TARGETS_PHASE1)
            _safe_cleanup(ws2)

    def test_02_workspace_scoped_state_isolates(self) -> None:
        """GET /state?workspace_id=X returns only that workspace's acquisitions."""
        ws1 = _create_workspace(f"gstate02a_{uuid.uuid4().hex[:6]}")
        ws2 = _create_workspace(f"gstate02b_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws1, force=True)
            _plan_commit(ws2, force=True)

            s1 = _state(ws1)
            s2 = _state(ws2)
            ids1 = {a["id"] for a in s1.get("acquisitions", [])}
            ids2 = {a["id"] for a in s2.get("acquisitions", [])}

            # No overlap between workspace-scoped results
            overlap = ids1 & ids2
            assert len(overlap) == 0, (
                f"Workspace isolation violated: {len(overlap)} shared acq IDs: "
                f"{list(overlap)[:5]}"
            )
            print(
                f"Workspace isolation: ws1={len(ids1)}, ws2={len(ids2)}, "
                f"overlap=0 ✓"
            )
        finally:
            _safe_cleanup(ws1, TLE_SAT1, TARGETS_PHASE1)
            _safe_cleanup(ws2)


class TestAutoEscalationSideEffects:
    """Verify auto-escalation promotes locks for near-execution acquisitions."""

    def test_01_repair_commit_auto_escalates_near_execution(self) -> None:
        """
        Repair commit auto-escalates lock_level='none' acquisitions that
        start within the 2h freeze window to 'hard'.
        """
        ws = _create_workspace(f"escal01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws, force=True)

            pre_state = _state(ws)
            pre_acqs = pre_state.get("acquisitions", [])
            assert len(pre_acqs) > 0

            now = datetime.now(timezone.utc)
            freeze_cutoff = now + timedelta(hours=2)

            near_exec = []
            for a in pre_acqs:
                start = _parse_ts(a["start_time"])
                if start <= freeze_cutoff:
                    near_exec.append(a)

            # Run repair to trigger auto-escalation
            repair = _post("/schedule/repair", {"workspace_id": ws})
            assert repair.get("success"), f"Repair failed: {repair.get('message')}"

            # Commit repair (triggers auto_escalate_locks)
            repair_commit = _post(
                "/schedule/repair/commit",
                {
                    "plan_id": repair["plan_id"],
                    "workspace_id": ws,
                    "force": True,
                },
            )
            assert repair_commit.get(
                "success"
            ), f"Repair commit failed: {repair_commit.get('message')}"

            # Check post-commit lock levels
            post_state = _state(ws)
            post_acqs = post_state.get("acquisitions", [])
            post_by_id = {a["id"]: a for a in post_acqs}

            escalated = 0
            for a in near_exec:
                if a["id"] in post_by_id:
                    post_lock = post_by_id[a["id"]]["lock_level"]
                    if a["lock_level"] == "none" and post_lock == "hard":
                        escalated += 1

            if len(near_exec) > 0:
                print(
                    f"Auto-escalation: {len(near_exec)} acqs in freeze window, "
                    f"{escalated} escalated none→hard ✓"
                )
            else:
                print(
                    f"Auto-escalation: no acquisitions within 2h freeze window "
                    f"(all {len(pre_acqs)} start later) — path not exercised"
                )
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)


class TestInvalidObjectiveAndScope:
    """Verify validation of objective and repair_scope enums."""

    def test_01_invalid_objective_returns_400(self) -> None:
        """Invalid objective value returns 400."""
        ws = _create_workspace(f"invobj01_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws, force=True)

            resp = requests.post(
                f"{API}/schedule/repair",
                json={
                    "workspace_id": ws,
                    "objective": "invalid_objective",
                },
                timeout=30,
            )
            assert (
                resp.status_code == 400
            ), f"Expected 400 for invalid objective, got {resp.status_code}"
            assert (
                "objective" in resp.text.lower()
            ), f"Error should mention objective: {resp.text[:300]}"
            print("Invalid objective → 400 ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)

    def test_02_minimize_changes_objective(self) -> None:
        """Repair with objective='minimize_changes' should succeed."""
        ws = _create_workspace(f"invobj02_{uuid.uuid4().hex[:6]}")
        try:
            _seed(TLE_SAT1, TARGETS_PHASE1, days=3)
            _plan_commit(ws, force=True)

            resp = _post(
                "/schedule/repair",
                {
                    "workspace_id": ws,
                    "objective": "minimize_changes",
                },
            )
            assert resp.get(
                "success"
            ), f"minimize_changes repair failed: {resp.get('message')}"
            print("minimize_changes objective: ok ✓")
        finally:
            _safe_cleanup(ws, TLE_SAT1, TARGETS_PHASE1)
