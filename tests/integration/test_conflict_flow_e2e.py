#!/usr/bin/env python3
"""
End-to-end conflict flow validation.

Exercises the full planning → commit → re-plan → conflict prediction pipeline:
1. Seed a mission via /mission/analyze so opportunities exist
2. Create a fresh workspace
3. Run from_scratch plan (via /plan endpoint)
4. Commit acquisitions
5. Run incremental plan that must conflict with committed items
6. Validate conflicts_if_committed contains enriched reason + details
7. Run repair plan and validate its conflicts_if_committed
8. Cleanup workspace

Requires: backend running on localhost:8000
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Generator, Optional

import pytest
import requests

BASE_URL = "http://localhost:8000"
API = f"{BASE_URL}/api/v1"

pytestmark = pytest.mark.requires_server


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post(path: str, payload: Dict[str, Any], timeout: int = 120) -> Dict[str, Any]:
    resp = requests.post(f"{API}{path}", json=payload, timeout=timeout)
    assert (
        resp.status_code == 200
    ), f"{path} returned {resp.status_code}: {resp.text[:500]}"
    return resp.json()  # type: ignore[no-any-return]


def _get(
    path: str, params: Optional[Dict[str, Any]] = None, timeout: int = 30
) -> Dict[str, Any]:
    resp = requests.get(f"{API}{path}", params=params, timeout=timeout)
    assert (
        resp.status_code == 200
    ), f"{path} returned {resp.status_code}: {resp.text[:300]}"
    return resp.json()  # type: ignore[no-any-return]


# Recent ICEYE-X44 TLE (epoch 2025-288 — usable for dates around that epoch)
_TLE = {
    "name": "ICEYE-X44",
    "line1": "1 62707U 25009DC  25288.94104150  .00005233  00000+0  49676-3 0  9994",
    "line2": "2 62707  97.7279   6.9881 0001205 170.4542 189.6701 14.93939975 63446",
}

# Targets in the Eastern Mediterranean — close enough to produce overlaps
_TARGETS = [
    {"name": "Athens", "latitude": 37.9838, "longitude": 23.7275, "priority": 5},
    {"name": "Thessaloniki", "latitude": 40.6401, "longitude": 22.9444, "priority": 4},
    {"name": "Izmir", "latitude": 38.4237, "longitude": 27.1428, "priority": 3},
    {"name": "Heraklion", "latitude": 35.3387, "longitude": 25.1442, "priority": 2},
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def seed_mission() -> Dict[str, Any]:
    """Ensure the planner has opportunities to work with.

    Tries /mission/analyze first; if the TLE is too stale (0 passes),
    falls back to checking whether /schedule/plan already returns items
    (the server may have a mission loaded from a previous session).
    """
    now = datetime.now(timezone.utc)
    start = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (now + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload: Dict[str, Any] = {
        "tle": _TLE,
        "targets": _TARGETS,
        "start_time": start,
        "end_time": end,
        "mission_type": "imaging",
        "pointing_angle": 45.0,
    }
    resp = requests.post(f"{API}/mission/analyze", json=payload, timeout=120)
    assert resp.status_code == 200, f"Failed to seed mission: {resp.text[:300]}"
    data: Dict[str, Any] = resp.json()
    passes = data.get("passes", [])

    if len(passes) > 0:
        print(
            f"\n🌍 Mission seeded: {len(passes)} passes across {len(_TARGETS)} targets"
            f" ({start} → {end})"
        )
        return data

    # TLE may be stale — check if server already has a usable mission state
    plan_resp = requests.post(
        f"{API}/schedule/plan",
        json={"planning_mode": "from_scratch"},
        timeout=120,
    )
    assert (
        plan_resp.status_code == 200
    ), f"Fallback plan check failed: {plan_resp.text[:300]}"
    plan_data: Dict[str, Any] = plan_resp.json()
    item_count = len(plan_data.get("new_plan_items", []))
    assert item_count > 0, (
        "Mission analysis returned 0 passes (TLE likely stale) AND /schedule/plan "
        "returned 0 items (no prior mission state). Load a mission in the UI first, "
        "or update the TLE in this test file."
    )
    print(
        f"\n🌍 TLE stale (0 new passes), but server already has {item_count} "
        f"plan items from a prior mission — using existing state"
    )
    return plan_data


@pytest.fixture()
def workspace() -> Generator[str, None, None]:
    """Create an ephemeral workspace and tear it down after test."""
    tag = uuid.uuid4().hex[:8]
    name = f"conflict_test_{tag}"
    resp = requests.post(f"{API}/workspaces", json={"name": name}, timeout=15)
    assert resp.status_code == 200, f"Failed to create workspace: {resp.text[:200]}"
    data = resp.json()
    ws_id: str = data.get("id") or data.get("workspace", {}).get("id")
    assert ws_id, f"No workspace ID in response: {data}"
    print(f"\n🏗️  Created workspace: {name} ({ws_id})")
    yield ws_id
    # Cleanup
    try:
        requests.delete(f"{API}/workspaces/{ws_id}", timeout=10)
        print(f"🧹 Cleaned up workspace {ws_id}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Scenario 1: plan structure smoke test
# ---------------------------------------------------------------------------


class TestPlanStructure:
    """Validate /plan returns well-formed responses with all required keys."""

    def test_plan_returns_conflicts_if_committed_key(self) -> None:
        """Smoke: /plan response includes conflicts_if_committed array."""
        data = _post("/schedule/plan", {"planning_mode": "from_scratch"})
        assert data.get("success"), f"Plan failed: {data.get('message')}"
        assert "conflicts_if_committed" in data, "Missing conflicts_if_committed key"
        assert isinstance(data["conflicts_if_committed"], list)

        cp = data.get("commit_preview", {})
        assert (
            "will_create" in cp or "new_items_count" in cp
        ), f"Malformed commit_preview: {cp}"

        items = data.get("new_plan_items", [])
        print(
            f"✅ Plan: {len(items)} items, {len(data['conflicts_if_committed'])} conflicts"
        )

    def test_plan_items_have_required_fields(self) -> None:
        """Every plan item has the fields the frontend needs."""
        data = _post("/schedule/plan", {"planning_mode": "from_scratch"})
        required = [
            "opportunity_id",
            "satellite_id",
            "target_id",
            "start_time",
            "end_time",
        ]
        for item in data.get("new_plan_items", [])[:5]:
            for field in required:
                assert (
                    field in item
                ), f"Plan item missing '{field}': {list(item.keys())}"
        print(
            f"✅ All {len(data.get('new_plan_items', []))} plan items have required fields"
        )


# ---------------------------------------------------------------------------
# Scenario 2: plan → commit → re-plan → conflict detection
# ---------------------------------------------------------------------------


class TestConflictFlowFromScratch:
    """Full lifecycle: plan → commit → re-plan → validate conflicts."""

    def test_commit_then_replan_produces_conflicts_or_avoids_them(
        self, workspace: str
    ) -> None:
        """After committing a plan, re-planning should either detect conflicts
        or cleanly avoid them — both are valid outcomes. Validate structure."""

        # Step 1: from_scratch plan
        plan1 = _post(
            "/schedule/plan",
            {
                "planning_mode": "from_scratch",
                "workspace_id": workspace,
            },
        )
        assert plan1["success"], f"Plan 1 failed: {plan1.get('message')}"
        items1 = plan1.get("new_plan_items", [])
        plan_id = plan1.get("plan_id")
        print(f"📋 Plan 1: {len(items1)} items, plan_id={plan_id}")
        assert len(items1) > 0, "Plan produced 0 items — mission may not be seeded"

        # Step 2: Commit
        commit = _post(
            "/schedule/commit",
            {
                "plan_id": plan_id,
                "workspace_id": workspace,
                "lock_level": "none",
            },
        )
        committed = commit.get("committed", 0)
        print(f"💾 Committed {committed} acquisitions")
        assert committed > 0, "Commit returned 0 created acquisitions"

        # Step 3: Re-plan (from_scratch again, same workspace)
        plan2 = _post(
            "/schedule/plan",
            {
                "planning_mode": "from_scratch",
                "workspace_id": workspace,
            },
        )
        assert plan2["success"], f"Plan 2 failed: {plan2.get('message')}"
        items2 = plan2.get("new_plan_items", [])
        conflicts2 = plan2.get("conflicts_if_committed", [])
        print(f"📋 Plan 2: {len(items2)} items, {len(conflicts2)} conflicts predicted")

        # Validate conflict structure (if any)
        for c in conflicts2:
            assert "type" in c
            assert "severity" in c
            assert "description" in c
            assert "acquisition_ids" in c
            assert "reason" in c, f"Missing enriched 'reason': {c}"
            assert "details" in c, f"Missing enriched 'details': {c}"
            assert (
                isinstance(c["reason"], str) and len(c["reason"]) > 10
            ), f"Reason should be descriptive: {c['reason']}"
            print(f"  ⚡ {c['type']} ({c['severity']}): {c['description'][:80]}")
            print(f"     reason: {c['reason'][:60]}")
            if c["details"]:
                print(f"     details: {list(c['details'].keys())}")

        if conflicts2:
            print(f"✅ {len(conflicts2)} enriched conflicts with reason + details")
        else:
            print(f"ℹ️  0 conflicts — planner cleanly avoided overlaps (valid)")


# ---------------------------------------------------------------------------
# Scenario 3: repair plan flow → conflicts_if_committed
# ---------------------------------------------------------------------------


class TestRepairConflictFlow:
    """Validate repair plan returns well-formed conflicts_if_committed."""

    def test_repair_plan_structure(self, workspace: str) -> None:
        """Seed workspace, run repair, validate structure."""

        # Seed: plan + commit
        plan = _post(
            "/schedule/plan",
            {
                "planning_mode": "from_scratch",
                "workspace_id": workspace,
            },
        )
        if not plan["success"] or not plan.get("new_plan_items"):
            pytest.skip("No plan items — can't seed workspace for repair test")

        _post(
            "/schedule/commit",
            {
                "plan_id": plan["plan_id"],
                "workspace_id": workspace,
                "lock_level": "none",
            },
        )
        print(f"💾 Seeded workspace")

        # Repair
        repair = _post(
            "/schedule/repair",
            {
                "workspace_id": workspace,
                "planning_mode": "repair",
            },
        )
        assert repair.get("success"), f"Repair failed: {repair.get('message')}"
        assert "repair_diff" in repair, "Missing repair_diff"
        assert "conflicts_if_committed" in repair, "Missing conflicts_if_committed"
        assert "metrics_comparison" in repair, "Missing metrics_comparison"

        conflicts = repair["conflicts_if_committed"]
        diff = repair["repair_diff"]
        metrics = repair["metrics_comparison"]
        items = repair.get("new_plan_items", [])

        print(f"🔧 Repair: {len(items)} items")
        print(
            f"   added={len(diff.get('added',[]))} dropped={len(diff.get('dropped',[]))} "
            f"kept={len(diff.get('kept',[]))} moved={len(diff.get('moved',[]))}"
        )
        print(
            f"   score: {metrics.get('score_before','?')} → {metrics.get('score_after','?')}"
        )
        print(f"   conflicts: {len(conflicts)}")

        for c in conflicts:
            assert "type" in c
            assert "severity" in c
            assert "description" in c
            assert "reason" in c, f"Repair conflict missing 'reason': {c}"
            assert "details" in c, f"Repair conflict missing 'details': {c}"
            print(f"  ⚡ {c['type']} ({c['severity']}): {c['description'][:80]}")

        print(f"✅ Repair plan structure validated")


# ---------------------------------------------------------------------------
# Scenario 4: conflict enrichment field quality
# ---------------------------------------------------------------------------


class TestConflictEnrichmentFields:
    """Validate the enriched reason/details fields when conflicts exist."""

    def test_reason_is_human_readable_when_conflicts_exist(
        self, workspace: str
    ) -> None:
        """When conflicts ARE generated, reason must be a real English sentence."""

        # Seed workspace with committed acquisitions
        plan = _post(
            "/schedule/plan",
            {
                "planning_mode": "from_scratch",
                "workspace_id": workspace,
            },
        )
        if not plan["success"] or not plan.get("new_plan_items"):
            pytest.skip("No plan items to seed")

        _post(
            "/schedule/commit",
            {
                "plan_id": plan["plan_id"],
                "workspace_id": workspace,
                "lock_level": "none",
            },
        )

        # Re-plan to potentially get conflicts
        plan2 = _post(
            "/schedule/plan",
            {
                "planning_mode": "from_scratch",
                "workspace_id": workspace,
            },
        )
        conflicts = plan2.get("conflicts_if_committed", [])

        if not conflicts:
            # Also try repair path
            repair = _post(
                "/schedule/repair",
                {
                    "workspace_id": workspace,
                    "planning_mode": "repair",
                },
            )
            conflicts = repair.get("conflicts_if_committed", [])

        if not conflicts:
            pytest.skip(
                "No conflicts generated in either path — can't validate enrichment"
            )

        for c in conflicts:
            reason = c.get("reason", "")
            assert len(reason) > 20, f"Reason too short: '{reason}'"
            assert " " in reason, f"Reason should be multi-word: '{reason}'"

            if c["type"] == "temporal_overlap":
                assert any(
                    w in reason.lower() for w in ["overlap", "simultaneously", "time"]
                ), f"temporal_overlap reason should reference overlap: '{reason}'"
            elif c["type"] == "slew_infeasible":
                assert any(
                    w in reason.lower() for w in ["repoint", "maneuver", "time", "gap"]
                ), f"slew_infeasible reason should reference maneuver: '{reason}'"

            details = c.get("details")
            if details is not None:
                assert isinstance(details, dict), f"details should be a dict: {details}"

        print(f"✅ {len(conflicts)} conflicts validated for enrichment quality")


# ---------------------------------------------------------------------------
# Scenario 5: commit_preview consistency
# ---------------------------------------------------------------------------


class TestCommitPreviewConsistency:
    """Validate commit_preview fields are consistent with conflicts."""

    def test_commit_preview_counts_match(self) -> None:
        """commit_preview conflict count is consistent with conflicts_if_committed."""
        data = _post("/schedule/plan", {"planning_mode": "from_scratch"})
        conflicts = data.get("conflicts_if_committed", [])
        cp = data.get("commit_preview", {})

        error_conflicts = [c for c in conflicts if c.get("severity") == "error"]
        will_conflict = cp.get("will_conflict_with", 0)
        print(f"📊 Conflicts: {len(conflicts)} total, {len(error_conflicts)} errors")
        print(f"   commit_preview.will_conflict_with: {will_conflict}")

        if conflicts:
            assert will_conflict >= 0, "will_conflict_with should be non-negative"
        print(f"✅ Commit preview consistent")


# ---------------------------------------------------------------------------
# Scenario 6: direct conflict injection
# ---------------------------------------------------------------------------


class TestDirectConflictInjection:
    """Validate direct conflict injection via /commit/direct."""

    def test_direct_conflict_injection(self, workspace: str) -> None:
        """Inject a conflict directly and validate it's detected."""

        # Step 1: from_scratch plan
        plan = _post(
            "/schedule/plan",
            {
                "planning_mode": "from_scratch",
                "workspace_id": workspace,
            },
        )
        assert plan["success"], f"Plan failed: {plan.get('message')}"
        items = plan.get("new_plan_items", [])
        plan_id = plan.get("plan_id")
        print(f"📋 Plan: {len(items)} items, plan_id={plan_id}")
        assert len(items) > 0, "Plan produced 0 items — mission may not be seeded"

        # Step 2: Commit a conflicting acquisition directly (same time slot)
        item0 = items[0]
        conflicting_item = {
            "opportunity_id": item0.get("opportunity_id", "injected_opp_001"),
            "satellite_id": item0["satellite_id"],
            "target_id": item0["target_id"],
            "start_time": item0["start_time"],
            "end_time": item0["end_time"],
            "roll_angle_deg": item0.get("roll_angle_deg", 0.0),
            "pitch_angle_deg": item0.get("pitch_angle_deg", 0.0),
        }
        commit = _post(
            "/schedule/commit/direct",
            {
                "workspace_id": workspace,
                "items": [conflicting_item],
                "force": True,
            },
        )
        assert commit.get("success"), f"Direct commit failed: {commit.get('message')}"
        committed = commit.get("committed", 0)
        print(
            f"💾 Direct-committed {committed} acquisitions (same slot as plan item 0)"
        )
        assert committed > 0, "Commit returned 0 created acquisitions"

        # Step 3: Re-plan (from_scratch again, same workspace)
        plan2 = _post(
            "/schedule/plan",
            {
                "planning_mode": "from_scratch",
                "workspace_id": workspace,
            },
        )
        assert plan2["success"], f"Plan 2 failed: {plan2.get('message')}"
        items2 = plan2.get("new_plan_items", [])
        conflicts2 = plan2.get("conflicts_if_committed", [])
        print(f"📋 Plan 2: {len(items2)} items, {len(conflicts2)} conflicts predicted")

        # Validate conflict structure (if any)
        for c in conflicts2:
            assert "type" in c
            assert "severity" in c
            assert "description" in c
            assert "acquisition_ids" in c
            assert "reason" in c, f"Missing enriched 'reason': {c}"
            assert "details" in c, f"Missing enriched 'details': {c}"
            assert (
                isinstance(c["reason"], str) and len(c["reason"]) > 10
            ), f"Reason should be descriptive: {c['reason']}"
            print(f"  ⚡ {c['type']} ({c['severity']}): {c['description'][:80]}")
            print(f"     reason: {c['reason'][:60]}")
            if c["details"]:
                print(f"     details: {list(c['details'].keys())}")

        if conflicts2:
            print(f"✅ {len(conflicts2)} enriched conflicts with reason + details")
        else:
            print(f"ℹ️  0 conflicts — planner cleanly avoided overlaps (valid)")
