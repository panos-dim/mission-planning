"""
Property-based regression tests for conflict detection and commit prediction.

These tests stress the scheduler with randomized temporal layouts so we can
compare the implementation against a simple model of the expected behavior.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from hypothesis import HealthCheck, given, settings, strategies as st
from hypothesis.stateful import Bundle, RuleBasedStateMachine, consumes, invariant, rule

from backend.conflict_detection import ConflictDetector
from backend.incremental_planning import predict_commit_conflicts
from backend.schedule_persistence import ScheduleDB
from backend.workspace_persistence import WorkspaceDB

BASE_TIME = datetime(2035, 1, 1, tzinfo=timezone.utc)
SATELLITES = ["SAT-1", "SAT-2", "SAT-3"]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _make_time(slot: int) -> datetime:
    return BASE_TIME + timedelta(days=30, seconds=slot * 20)


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


def _temp_db() -> Iterator[tuple[ScheduleDB, str, Path]]:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    db = ScheduleDB(db_path)
    workspace_id = WorkspaceDB(db_path).create_workspace(
        name="Property Workspace",
        mission_mode="OPTICAL",
    )
    try:
        yield db, workspace_id, db_path
    finally:
        os.unlink(db_path)


specs_strategy = st.lists(
    st.tuples(
        st.sampled_from(SATELLITES),
        st.integers(min_value=0, max_value=40),
        st.integers(min_value=0, max_value=25),
    ),
    min_size=1,
    max_size=8,
)


@settings(
    max_examples=80,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(specs=specs_strategy)
def test_temporal_overlap_detector_matches_naive_model(
    specs: list[tuple[str, int, int]],
) -> None:
    """Temporal overlap detection should match a naive all-pairs model."""
    for db, workspace_id, _db_path in _temp_db():
        expected_pairs: set[frozenset[str]] = set()
        created: list[dict[str, Any]] = []

        for idx, (satellite_id, slot, duration_seconds) in enumerate(specs):
            start_dt = _make_time(slot)
            end_dt = start_dt + timedelta(seconds=duration_seconds)
            target_id = f"T{idx}"
            db.create_acquisition(
                satellite_id=satellite_id,
                target_id=target_id,
                start_time=_iso(start_dt),
                end_time=_iso(end_dt),
                roll_angle_deg=0.0,
                workspace_id=workspace_id,
                state="committed",
            )
            created.append(
                {
                    "satellite_id": satellite_id,
                    "target_id": target_id,
                    "start": start_dt,
                    "end": end_dt,
                }
            )

        for i, left in enumerate(created):
            for right in created[i + 1 :]:
                if left["satellite_id"] != right["satellite_id"]:
                    continue
                if _overlaps(left["start"], left["end"], right["start"], right["end"]):
                    expected_pairs.add(
                        frozenset({left["target_id"], right["target_id"]})
                    )

        detector = ConflictDetector(db)
        conflicts = detector.detect_conflicts(
            workspace_id=workspace_id,
            start_time=_iso(BASE_TIME),
            end_time=_iso(BASE_TIME + timedelta(days=60)),
        )
        actual_pairs = {
            frozenset({c.details["acq1_target"], c.details["acq2_target"]})
            for c in conflicts
            if c.type == "temporal_overlap"
        }

        assert actual_pairs == expected_pairs


@settings(
    max_examples=80,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    primary_specs=specs_strategy,
    secondary_specs=specs_strategy,
    new_specs=specs_strategy,
)
def test_predict_commit_conflicts_stays_within_workspace_boundary(
    primary_specs: list[tuple[str, int, int]],
    secondary_specs: list[tuple[str, int, int]],
    new_specs: list[tuple[str, int, int]],
) -> None:
    """Commit preview must ignore overlapping acquisitions in unrelated workspaces."""
    for db, workspace_id, db_path in _temp_db():
        secondary_workspace_id = WorkspaceDB(db_path).create_workspace(
            name="Secondary Property Workspace",
            mission_mode="OPTICAL",
        )
        primary_existing: list[dict[str, Any]] = []
        new_items: list[dict[str, Any]] = []

        for idx, (satellite_id, slot, duration_seconds) in enumerate(primary_specs):
            start_dt = _make_time(slot)
            end_dt = start_dt + timedelta(seconds=duration_seconds)
            target_id = f"P{idx}"
            db.create_acquisition(
                satellite_id=satellite_id,
                target_id=target_id,
                start_time=_iso(start_dt),
                end_time=_iso(end_dt),
                roll_angle_deg=0.0,
                pitch_angle_deg=0.0,
                workspace_id=workspace_id,
                state="committed",
            )
            primary_existing.append(
                {
                    "satellite_id": satellite_id,
                    "target_id": target_id,
                    "start": start_dt,
                    "end": end_dt,
                }
            )

        for idx, (satellite_id, slot, duration_seconds) in enumerate(secondary_specs):
            start_dt = _make_time(slot)
            end_dt = start_dt + timedelta(seconds=duration_seconds)
            db.create_acquisition(
                satellite_id=satellite_id,
                target_id=f"S{idx}",
                start_time=_iso(start_dt),
                end_time=_iso(end_dt),
                roll_angle_deg=0.0,
                pitch_angle_deg=0.0,
                workspace_id=secondary_workspace_id,
                state="committed",
            )

        for idx, (satellite_id, slot, duration_seconds) in enumerate(new_specs):
            start_dt = _make_time(slot)
            end_dt = start_dt + timedelta(seconds=duration_seconds)
            new_items.append(
                {
                    "satellite_id": satellite_id,
                    "target_id": f"N{idx}",
                    "start_time": _iso(start_dt),
                    "end_time": _iso(end_dt),
                    "roll_angle_deg": 0.0,
                    "pitch_angle_deg": 0.0,
                }
            )

        predicted, _count = predict_commit_conflicts(
            db=db,
            workspace_id=workspace_id,
            new_items=new_items,
            horizon_start=BASE_TIME,
            horizon_end=BASE_TIME + timedelta(hours=1),
        )

        expected_pairs: set[frozenset[str]] = set()
        combined = primary_existing + [
            {
                "satellite_id": item["satellite_id"],
                "target_id": item["target_id"],
                "start": datetime.fromisoformat(item["start_time"].replace("Z", "+00:00")),
                "end": datetime.fromisoformat(item["end_time"].replace("Z", "+00:00")),
            }
            for item in new_items
        ]

        for i, left in enumerate(combined):
            for right in combined[i + 1 :]:
                if left["satellite_id"] != right["satellite_id"]:
                    continue
                if not (
                    left["target_id"].startswith("N") or right["target_id"].startswith("N")
                ):
                    continue
                if _overlaps(left["start"], left["end"], right["start"], right["end"]):
                    expected_pairs.add(
                        frozenset({left["target_id"], right["target_id"]})
                    )

        actual_pairs = {
            frozenset({c["details"]["acq1_target"], c["details"]["acq2_target"]})
            for c in predicted
            if c["type"] == "temporal_overlap"
        }

        assert actual_pairs == expected_pairs


@settings(
    max_examples=80,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(existing_specs=specs_strategy, new_specs=specs_strategy)
def test_predict_commit_conflicts_matches_naive_new_item_model(
    existing_specs: list[tuple[str, int, int]],
    new_specs: list[tuple[str, int, int]],
) -> None:
    """Commit preview should report exactly the overlaps involving new items."""
    for db, workspace_id, _db_path in _temp_db():
        existing: list[dict[str, Any]] = []
        new_items: list[dict[str, Any]] = []

        for idx, (satellite_id, slot, duration_seconds) in enumerate(existing_specs):
            start_dt = _make_time(slot)
            end_dt = start_dt + timedelta(seconds=duration_seconds)
            target_id = f"E{idx}"
            db.create_acquisition(
                satellite_id=satellite_id,
                target_id=target_id,
                start_time=_iso(start_dt),
                end_time=_iso(end_dt),
                roll_angle_deg=0.0,
                pitch_angle_deg=0.0,
                workspace_id=workspace_id,
                state="committed",
            )
            existing.append(
                {
                    "satellite_id": satellite_id,
                    "target_id": target_id,
                    "start": start_dt,
                    "end": end_dt,
                }
            )

        for idx, (satellite_id, slot, duration_seconds) in enumerate(new_specs):
            start_dt = _make_time(slot)
            end_dt = start_dt + timedelta(seconds=duration_seconds)
            target_id = f"N{idx}"
            new_items.append(
                {
                    "satellite_id": satellite_id,
                    "target_id": target_id,
                    "start_time": _iso(start_dt),
                    "end_time": _iso(end_dt),
                    "roll_angle_deg": 0.0,
                    "pitch_angle_deg": 0.0,
                }
            )

        predicted, _count = predict_commit_conflicts(
            db=db,
            workspace_id=workspace_id,
            new_items=new_items,
            horizon_start=BASE_TIME,
            horizon_end=BASE_TIME + timedelta(hours=1),
        )

        expected_pairs: set[frozenset[str]] = set()
        combined = existing + [
            {
                "satellite_id": item["satellite_id"],
                "target_id": item["target_id"],
                "start": datetime.fromisoformat(item["start_time"].replace("Z", "+00:00")),
                "end": datetime.fromisoformat(item["end_time"].replace("Z", "+00:00")),
            }
            for item in new_items
        ]

        for i, left in enumerate(combined):
            for right in combined[i + 1 :]:
                if left["satellite_id"] != right["satellite_id"]:
                    continue
                if not (
                    left["target_id"].startswith("N") or right["target_id"].startswith("N")
                ):
                    continue
                if _overlaps(left["start"], left["end"], right["start"], right["end"]):
                    expected_pairs.add(
                        frozenset({left["target_id"], right["target_id"]})
                    )

        actual_pairs = {
            frozenset({c["details"]["acq1_target"], c["details"]["acq2_target"]})
            for c in predicted
            if c["type"] == "temporal_overlap"
        }

        assert actual_pairs == expected_pairs
        assert all(any(target.startswith("N") for target in pair) for pair in actual_pairs)


@settings(
    max_examples=30,
    stateful_step_count=12,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
class ConflictSequenceStateMachine(RuleBasedStateMachine):
    """Stateful regression coverage for add/delete schedule mutations."""

    acquisitions = Bundle("acquisitions")

    def __init__(self) -> None:
        super().__init__()
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._db_path = Path(self._tmp.name)
        self.db = ScheduleDB(self._db_path)
        self.workspace_id = WorkspaceDB(self._db_path).create_workspace(
            name="Conflict Sequence Workspace",
            mission_mode="OPTICAL",
        )
        self.model: dict[str, dict[str, Any]] = {}
        self.counter = 0

    def teardown(self) -> None:
        os.unlink(self._db_path)

    @rule(
        target=acquisitions,
        satellite_id=st.sampled_from(SATELLITES),
        slot=st.integers(min_value=0, max_value=40),
        duration_seconds=st.integers(min_value=0, max_value=25),
    )
    def add_acquisition(
        self,
        satellite_id: str,
        slot: int,
        duration_seconds: int,
    ) -> str:
        start_dt = _make_time(slot)
        end_dt = start_dt + timedelta(seconds=duration_seconds)
        target_id = f"S{self.counter}"
        self.counter += 1
        acq = self.db.create_acquisition(
            satellite_id=satellite_id,
            target_id=target_id,
            start_time=_iso(start_dt),
            end_time=_iso(end_dt),
            roll_angle_deg=0.0,
            pitch_angle_deg=0.0,
            workspace_id=self.workspace_id,
            state="committed",
        )
        self.model[acq.id] = {
            "satellite_id": satellite_id,
            "target_id": target_id,
            "start": start_dt,
            "end": end_dt,
        }
        return acq.id

    @rule(acq_id=consumes(acquisitions))
    def delete_acquisition(self, acq_id: str) -> None:
        if acq_id not in self.model:
            return
        assert self.db.delete_acquisition(acq_id, force=True)
        del self.model[acq_id]

    @invariant()
    def detector_matches_naive_model(self) -> None:
        detector = ConflictDetector(self.db)
        conflicts = detector.detect_conflicts(
            workspace_id=self.workspace_id,
            start_time=_iso(BASE_TIME),
            end_time=_iso(BASE_TIME + timedelta(days=60)),
        )
        actual_pairs = {
            frozenset({c.details["acq1_target"], c.details["acq2_target"]})
            for c in conflicts
            if c.type == "temporal_overlap"
        }

        expected_pairs: set[frozenset[str]] = set()
        items = list(self.model.values())
        for i, left in enumerate(items):
            for right in items[i + 1 :]:
                if left["satellite_id"] != right["satellite_id"]:
                    continue
                if _overlaps(left["start"], left["end"], right["start"], right["end"]):
                    expected_pairs.add(
                        frozenset({left["target_id"], right["target_id"]})
                    )

        assert actual_pairs == expected_pairs


TestConflictSequenceStateMachine = ConflictSequenceStateMachine.TestCase
