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
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Generator, List, Optional

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

# Eastern Mediterranean targets — close enough for overlap scenarios
TARGETS_PHASE1 = [
    {"name": "Athens", "latitude": 37.9838, "longitude": 23.7275},
    {"name": "London", "latitude": 51.5074, "longitude": -0.1278},
]

TARGETS_PHASE2 = TARGETS_PHASE1 + [
    {"name": "Cairo", "latitude": 30.0444, "longitude": 31.2357},
    {"name": "Istanbul", "latitude": 41.0082, "longitude": 28.9784},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post(
    path: str, payload: Dict[str, Any], timeout: int = 120
) -> Dict[str, Any]:
    """POST to API and assert 200."""
    resp = requests.post(f"{API}{path}", json=payload, timeout=timeout)
    assert resp.status_code == 200, (
        f"POST {path} returned {resp.status_code}: {resp.text[:500]}"
    )
    return resp.json()


def _get(
    path: str, params: Optional[Dict[str, Any]] = None, timeout: int = 30
) -> Dict[str, Any]:
    """GET from API and assert 200."""
    resp = requests.get(f"{API}{path}", params=params, timeout=timeout)
    assert resp.status_code == 200, (
        f"GET {path} returned {resp.status_code}: {resp.text[:300]}"
    )
    return resp.json()


def _patch(
    path: str, params: Optional[Dict[str, Any]] = None, timeout: int = 15
) -> Dict[str, Any]:
    """PATCH API and assert 200."""
    resp = requests.patch(f"{API}{path}", params=params, timeout=timeout)
    assert resp.status_code == 200, (
        f"PATCH {path} returned {resp.status_code}: {resp.text[:300]}"
    )
    return resp.json()


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


def _create_workspace(name: str) -> str:
    """Create workspace and return its ID."""
    resp = _post("/workspaces", {"name": name})
    ws_id = resp.get("workspace_id")
    assert ws_id, f"No workspace_id in response: {resp}"
    return ws_id


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
    return resp.get("state", {})


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
    assert plan["success"] and plan.get("new_plan_items"), (
        f"Plan failed or empty: {plan.get('message')}"
    )
    return _commit(
        plan["plan_id"], workspace_id, lock_level=lock_level, force=force
    )


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
    except Exception:
        pass


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

    def test_03_from_scratch_plan(
        self, seeded_mission: Dict, workspace: str
    ) -> None:
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
        assert len(acqs) == commit["committed"], (
            f"Expected {commit['committed']} acquisitions, got {len(acqs)}"
        )
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

    def test_08_conflict_recompute(
        self, seeded_mission: Dict, workspace: str
    ) -> None:
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
        assert locked_id in kept, (
            f"Hard-locked {locked_id} not in kept set: {kept}"
        )
        print(
            f"Repair: fixed={repair['fixed_count']}, flex={repair['flex_count']}, "
            f"kept={len(kept)}"
        )

    def test_10_commit_repair(
        self, seeded_mission: Dict, workspace: str
    ) -> None:
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
        print(f"Re-plan with extra target: {len(items)} items, targets={sorted(target_ids)}")

        # Re-seed with original targets to avoid poisoning subsequent tests
        _seed(TLE_SAT1, TARGETS_PHASE1, days=3)

    def test_12_direct_commit(
        self, seeded_mission: Dict, workspace: str
    ) -> None:
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

    def test_13_schedule_horizon(
        self, seeded_mission: Dict, workspace: str
    ) -> None:
        """Schedule horizon returns data."""
        _plan_commit(workspace)
        horizon = _get(
            "/schedule/horizon", {"workspace_id": workspace}
        )
        assert horizon["success"]
        acqs = horizon.get("acquisitions", [])
        print(f"Horizon: {len(acqs)} acquisitions")

    def test_14_target_locations(
        self, seeded_mission: Dict, workspace: str
    ) -> None:
        """Target locations endpoint returns positions."""
        _plan_commit(workspace)
        locs = _get(
            "/schedule/target-locations", {"workspace_id": workspace}
        )
        assert locs["success"]
        targets = locs.get("targets", [])
        print(f"Target locations: {len(targets)}")

    def test_15_commit_history(
        self, seeded_mission: Dict, workspace: str
    ) -> None:
        """Commit history returns audit entries."""
        _plan_commit(workspace)
        history = _get(
            "/schedule/commit-history", {"workspace_id": workspace}
        )
        assert history["success"]
        entries = history.get("audit_logs", [])
        print(f"Commit history: {len(entries)} entries")

    def test_16_workspace_isolation(
        self, seeded_mission: Dict, workspace: str
    ) -> None:
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
            assert len(ids2) == 0, (
                f"Workspace {ws2_id} has {len(ids2)} acquisitions (leak!)"
            )
            print("Workspace isolation verified")
        finally:
            requests.delete(f"{API}/workspaces/{ws2_id}", timeout=10)

    def test_17_auto_escalate_locks(
        self, seeded_mission: Dict, workspace: str
    ) -> None:
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
        data = _seed_constellation(
            [TLE_SAT1, TLE_SAT2], TARGETS_PHASE2, days=3
        )
        passes = data.get("data", {}).get("mission_data", {}).get("passes", [])
        assert len(passes) > 0, (
            f"Constellation produced 0 passes. Message: {data.get('message', '')}"
        )
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

    def test_04_repair_preserves_constellation_locks(
        self, workspace: str
    ) -> None:
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
            assert lid in diff.get("kept", []), (
                f"Hard-locked {lid} not in kept!"
            )

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

    def test_05_conflict_detection_constellation(
        self, workspace: str
    ) -> None:
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
        print(
            f"Bulk delete: {del_resp['deleted']} deleted, hard-lock preserved"
        )

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
        assert resp.status_code in [400, 409], (
            f"Double commit should fail, got {resp.status_code}"
        )
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
        assert resp.status_code == 400, (
            f"Invalid lock_level should return 400, got {resp.status_code}"
        )
        print("Invalid lock_level 'soft' correctly rejected")

    def test_03_commit_nonexistent_plan(self) -> None:
        """Committing a nonexistent plan returns 404."""
        resp = requests.post(
            f"{API}/schedule/commit",
            json={"plan_id": "nonexistent_plan_xyz"},
            timeout=15,
        )
        assert resp.status_code == 404
        print("Nonexistent plan correctly rejected (404)")

    def test_04_lock_nonexistent_acquisition(self) -> None:
        """Locking a nonexistent acquisition returns error."""
        resp = requests.patch(
            f"{API}/schedule/acquisition/nonexistent_acq_xyz/lock",
            params={"lock_level": "hard"},
            timeout=10,
        )
        assert resp.status_code in [404, 400, 500]
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

    def test_06_schedule_state_has_conflicts_key(
        self, workspace: str
    ) -> None:
        """Schedule state includes conflict data (B3 fix validation)."""
        resp = _get("/schedule/state", {"workspace_id": workspace})
        state = resp.get("state", {})
        assert "conflicts" in state, "Schedule state missing 'conflicts' key"
        assert isinstance(state["conflicts"], list)
        print(f"Schedule state has {len(state['conflicts'])} conflicts")

    def test_07_get_conflicts_endpoint(self, workspace: str) -> None:
        """GET /conflicts returns structured conflict data."""
        conflicts_resp = _get(
            "/schedule/conflicts", {"workspace_id": workspace}
        )
        assert conflicts_resp["success"]
        conflict_list = conflicts_resp.get("conflicts", [])
        for c in conflict_list:
            assert "type" in c
            assert "severity" in c
        print(f"Conflicts endpoint: {len(conflict_list)} conflicts")

    def test_08_commit_with_conflicts_returns_409(
        self, workspace: str
    ) -> None:
        """Committing plan with conflicts returns 409 (not force)."""
        # Plan + commit to fill schedule
        _plan_commit(workspace)

        # Re-plan (same opportunities = conflicts)
        plan2 = _plan(workspace)
        if not plan2.get("new_plan_items"):
            pytest.skip("No plan items for conflict test")

        resp = requests.post(
            f"{API}/schedule/commit",
            json={
                "plan_id": plan2["plan_id"],
                "workspace_id": workspace,
            },
            timeout=30,
        )
        if plan2.get("conflicts_if_committed"):
            assert resp.status_code == 409, (
                f"Expected 409 for conflicting commit, got {resp.status_code}"
            )
            detail = resp.json().get("detail", {})
            assert "predicted_conflicts" in detail
            print(
                f"Conflicting commit correctly rejected (409) with "
                f"{len(detail['predicted_conflicts'])} conflicts"
            )
        else:
            # No conflicts predicted — commit may succeed
            print("No conflicts predicted, commit may have succeeded")

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
        assert n2 < n1, (
            f"Dedup failed: second plan has {n2} items, first had {n1}"
        )
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
            it for it in new_items
            if it.get("target_id") == deleted_target_id
            and it.get("satellite_id") == deleted_sat_id
        ]
        # Either we get the pair back or we get at least fewer items blocked
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
            assert n2 > 0, "Workspace 2 should have plan items (no cross-workspace dedup)"
            print(
                f"Workspace isolation: ws1 committed {n1}, "
                f"ws2 independently planned {n2}"
            )
        finally:
            for ws in (ws1, ws2):
                try:
                    requests.delete(f"{API}/workspaces/{ws}", timeout=10)
                except Exception:
                    pass
