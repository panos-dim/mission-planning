"""
Schedule Persistence Layer for Mission Planning v2.0.

Provides SQLite-based persistence for:
- Orders (user imaging requests)
- Acquisitions (committed schedule slots)
- Plans (candidate schedules)
- Plan items (individual scheduled opportunities within a plan)
- Conflicts (detected scheduling issues)

Schema version: 2.0
"""

import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

# Schema version for this module
SCHEMA_VERSION = "2.3"

# Default database path (same as workspace_persistence.py)
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "workspaces.db"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Order:
    """User imaging request with extended workflow fields."""

    id: str
    created_at: str
    updated_at: str
    status: str  # new | queued | planned | committed | rejected | expired
    target_id: str
    priority: int
    constraints_json: Optional[str]
    requested_window_start: Optional[str]
    requested_window_end: Optional[str]
    source: str  # manual | api | batch | import
    notes: Optional[str]
    external_ref: Optional[str]
    workspace_id: Optional[str]
    # Extended fields for PS2.5
    order_type: str = "IMAGING"  # IMAGING | DOWNLINK | MAINTENANCE
    due_time: Optional[str] = None  # SLA deadline
    earliest_start: Optional[str] = None  # Constraint: earliest start time
    latest_end: Optional[str] = None  # Constraint: latest end time
    batch_id: Optional[str] = None  # Associated batch (nullable)
    tags_json: Optional[str] = None  # JSON array of tags
    requested_satellite_group: Optional[str] = None  # Preferred satellite group
    user_notes: Optional[str] = None  # User-provided notes
    reject_reason: Optional[str] = None  # Reason for rejection

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        constraints = None
        if self.constraints_json:
            try:
                constraints = json.loads(self.constraints_json)
            except json.JSONDecodeError:
                constraints = None

        tags = None
        if self.tags_json:
            try:
                tags = json.loads(self.tags_json)
            except json.JSONDecodeError:
                tags = None

        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "target_id": self.target_id,
            "priority": self.priority,
            "constraints": constraints,
            "requested_window": (
                {
                    "start": self.requested_window_start,
                    "end": self.requested_window_end,
                }
                if self.requested_window_start or self.requested_window_end
                else None
            ),
            "source": self.source,
            "notes": self.notes,
            "external_ref": self.external_ref,
            "workspace_id": self.workspace_id,
            # Extended fields
            "order_type": self.order_type,
            "due_time": self.due_time,
            "earliest_start": self.earliest_start,
            "latest_end": self.latest_end,
            "batch_id": self.batch_id,
            "tags": tags,
            "requested_satellite_group": self.requested_satellite_group,
            "user_notes": self.user_notes,
            "reject_reason": self.reject_reason,
        }


@dataclass
class OrderBatch:
    """Batch of orders for planning."""

    id: str
    workspace_id: str
    created_at: str
    updated_at: str
    policy_id: str  # Reference to planning policy
    horizon_from: str  # Planning horizon start
    horizon_to: str  # Planning horizon end
    status: str  # draft | planned | committed | cancelled
    plan_id: Optional[str] = None  # Generated plan ID
    notes: Optional[str] = None
    metrics_json: Optional[str] = None  # Coverage metrics

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        metrics = None
        if self.metrics_json:
            try:
                metrics = json.loads(self.metrics_json)
            except json.JSONDecodeError:
                metrics = None

        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "policy_id": self.policy_id,
            "horizon_from": self.horizon_from,
            "horizon_to": self.horizon_to,
            "status": self.status,
            "plan_id": self.plan_id,
            "notes": self.notes,
            "metrics": metrics,
        }


@dataclass
class BatchMember:
    """Order membership in a batch."""

    id: str
    batch_id: str
    order_id: str
    role: str  # primary | optional
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "order_id": self.order_id,
            "role": self.role,
            "created_at": self.created_at,
        }


@dataclass
class Acquisition:
    """Committed schedule slot."""

    id: str
    created_at: str
    updated_at: str
    satellite_id: str
    target_id: str
    start_time: str
    end_time: str
    mode: str  # OPTICAL | SAR
    roll_angle_deg: float
    pitch_angle_deg: float
    incidence_angle_deg: Optional[float]
    look_side: Optional[str]  # LEFT | RIGHT
    pass_direction: Optional[str]  # ASCENDING | DESCENDING
    sar_mode: Optional[str]  # spot | strip | scan | dwell
    swath_width_km: Optional[float]
    scene_length_km: Optional[float]
    state: str  # tentative | locked | committed | executing | completed | failed
    lock_level: str  # none | hard
    source: str  # auto | manual | reshuffle
    order_id: Optional[str]
    plan_id: Optional[str]
    opportunity_id: Optional[str]
    quality_score: Optional[float]
    maneuver_time_s: Optional[float]
    slack_time_s: Optional[float]
    workspace_id: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "satellite_id": self.satellite_id,
            "target_id": self.target_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "mode": self.mode,
            "geometry": {
                "roll_deg": self.roll_angle_deg,
                "pitch_deg": self.pitch_angle_deg,
                "incidence_deg": self.incidence_angle_deg,
            },
            "state": self.state,
            "lock_level": self.lock_level,
            "source": self.source,
            "order_id": self.order_id,
            "plan_id": self.plan_id,
            "opportunity_id": self.opportunity_id,
            "quality_score": self.quality_score,
            "maneuver_time_s": self.maneuver_time_s,
            "slack_time_s": self.slack_time_s,
            "workspace_id": self.workspace_id,
        }

        # Add SAR-specific fields if present
        if self.mode == "SAR":
            result["sar"] = {
                "look_side": self.look_side,
                "pass_direction": self.pass_direction,
                "sar_mode": self.sar_mode,
                "swath_width_km": self.swath_width_km,
                "scene_length_km": self.scene_length_km,
            }

        return result


@dataclass
class Plan:
    """Candidate schedule."""

    id: str
    created_at: str
    algorithm: str
    config_json: str
    input_hash: str
    run_id: str
    score: Optional[float]
    metrics_json: str
    status: str  # candidate | committed | superseded | rejected
    workspace_id: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        config: Dict[str, Any] = {}
        metrics: Dict[str, Any] = {}
        try:
            config = json.loads(self.config_json) if self.config_json else {}
            metrics = json.loads(self.metrics_json) if self.metrics_json else {}
        except json.JSONDecodeError:
            pass

        return {
            "id": self.id,
            "created_at": self.created_at,
            "algorithm": self.algorithm,
            "config": config,
            "input_hash": self.input_hash,
            "run_id": self.run_id,
            "score": self.score,
            "metrics": metrics,
            "status": self.status,
            "workspace_id": self.workspace_id,
        }


@dataclass
class PlanItem:
    """Individual scheduled opportunity within a plan."""

    id: str
    plan_id: str
    opportunity_id: str
    satellite_id: str
    target_id: str
    start_time: str
    end_time: str
    roll_angle_deg: float
    pitch_angle_deg: float
    value: Optional[float]
    quality_score: Optional[float]
    maneuver_time_s: Optional[float]
    slack_time_s: Optional[float]
    order_id: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "opportunity_id": self.opportunity_id,
            "satellite_id": self.satellite_id,
            "target_id": self.target_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "geometry": {
                "roll_deg": self.roll_angle_deg,
                "pitch_deg": self.pitch_angle_deg,
            },
            "value": self.value,
            "quality_score": self.quality_score,
            "maneuver_time_s": self.maneuver_time_s,
            "slack_time_s": self.slack_time_s,
            "order_id": self.order_id,
        }


@dataclass
class Conflict:
    """Detected scheduling conflict."""

    id: str
    detected_at: str
    type: str  # temporal_overlap | slew_infeasible | resource_contention
    severity: str  # error | warning | info
    description: Optional[str]
    acquisition_ids_json: str  # JSON array of acquisition IDs
    resolved_at: Optional[str]
    resolution_action: Optional[str]
    resolution_notes: Optional[str]
    workspace_id: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        acquisition_ids = []
        try:
            acquisition_ids = json.loads(self.acquisition_ids_json)
        except json.JSONDecodeError:
            pass

        return {
            "id": self.id,
            "detected_at": self.detected_at,
            "type": self.type,
            "severity": self.severity,
            "description": self.description,
            "acquisition_ids": acquisition_ids,
            "resolved_at": self.resolved_at,
            "resolution_action": self.resolution_action,
            "resolution_notes": self.resolution_notes,
            "workspace_id": self.workspace_id,
        }


@dataclass
class CommitAuditLog:
    """Audit log entry for commit operations."""

    id: str
    created_at: str
    plan_id: str
    workspace_id: Optional[str]
    committed_by: Optional[str]  # user identifier
    commit_type: str  # normal | repair | force
    config_hash: str
    repair_diff_json: Optional[str]  # JSON of repair diff (if repair commit)
    acquisitions_created: int
    acquisitions_dropped: int
    score_before: Optional[float]
    score_after: Optional[float]
    conflicts_before: int
    conflicts_after: int
    notes: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        repair_diff = None
        if self.repair_diff_json:
            try:
                repair_diff = json.loads(self.repair_diff_json)
            except json.JSONDecodeError:
                pass

        return {
            "id": self.id,
            "created_at": self.created_at,
            "plan_id": self.plan_id,
            "workspace_id": self.workspace_id,
            "committed_by": self.committed_by,
            "commit_type": self.commit_type,
            "config_hash": self.config_hash,
            "repair_diff": repair_diff,
            "acquisitions_created": self.acquisitions_created,
            "acquisitions_dropped": self.acquisitions_dropped,
            "score_before": self.score_before,
            "score_after": self.score_after,
            "conflicts_before": self.conflicts_before,
            "conflicts_after": self.conflicts_after,
            "notes": self.notes,
        }


# =============================================================================
# Database Manager
# =============================================================================


class ScheduleDB:
    """SQLite-based schedule persistence manager for v2.0 schema."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Uses default if not specified.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_directory()
        self._run_migrations()

    def _ensure_directory(self) -> None:
        """Ensure the database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    def _run_migrations(self) -> None:
        """Run database migrations to bring schema to current version."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create schema_migrations table if not exists
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL,
                    description TEXT
                )
            """
            )

            # Check current version
            cursor.execute(
                "SELECT version FROM schema_migrations ORDER BY applied_at DESC LIMIT 1"
            )
            row = cursor.fetchone()
            current_version = row["version"] if row else "1.0"

            if current_version < "2.0":
                self._migrate_to_v2(conn)

            if current_version < "2.1":
                self._migrate_to_v2_1(conn)

            if current_version < "2.2":
                self._migrate_to_v2_2(conn)

            if current_version < "2.3":
                self._migrate_to_v2_3(conn)

            if current_version < "2.4":
                self._migrate_to_v2_4(conn)

            conn.commit()

    def _migrate_to_v2(self, conn: sqlite3.Connection) -> None:
        """Migrate database schema to v2.0."""
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat() + "Z"

        logger.info("Running migration to schema v2.0...")

        # Create orders table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                target_id TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 5,
                constraints_json TEXT,
                requested_window_start TEXT,
                requested_window_end TEXT,
                source TEXT DEFAULT 'manual',
                notes TEXT,
                external_ref TEXT,
                workspace_id TEXT REFERENCES workspaces(id)
            )
        """
        )

        # Create acquisitions table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS acquisitions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                satellite_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                mode TEXT NOT NULL DEFAULT 'OPTICAL',
                roll_angle_deg REAL NOT NULL,
                pitch_angle_deg REAL DEFAULT 0.0,
                incidence_angle_deg REAL,
                look_side TEXT,
                pass_direction TEXT,
                sar_mode TEXT,
                swath_width_km REAL,
                scene_length_km REAL,
                state TEXT NOT NULL DEFAULT 'tentative',
                lock_level TEXT DEFAULT 'none',
                source TEXT NOT NULL DEFAULT 'auto',
                order_id TEXT REFERENCES orders(id),
                plan_id TEXT REFERENCES plans(id),
                opportunity_id TEXT,
                quality_score REAL,
                maneuver_time_s REAL,
                slack_time_s REAL,
                workspace_id TEXT REFERENCES workspaces(id)
            )
        """
        )

        # Create plans table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                algorithm TEXT NOT NULL,
                config_json TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                run_id TEXT NOT NULL,
                score REAL,
                metrics_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'candidate',
                workspace_id TEXT REFERENCES workspaces(id)
            )
        """
        )

        # Create plan_items table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS plan_items (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
                opportunity_id TEXT NOT NULL,
                satellite_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                roll_angle_deg REAL NOT NULL,
                pitch_angle_deg REAL DEFAULT 0.0,
                value REAL,
                quality_score REAL,
                maneuver_time_s REAL,
                slack_time_s REAL,
                order_id TEXT REFERENCES orders(id)
            )
        """
        )

        # Create conflicts table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conflicts (
                id TEXT PRIMARY KEY,
                detected_at TEXT NOT NULL,
                type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'error',
                description TEXT,
                acquisition_ids_json TEXT NOT NULL,
                resolved_at TEXT,
                resolution_action TEXT,
                resolution_notes TEXT,
                workspace_id TEXT REFERENCES workspaces(id)
            )
        """
        )

        # Create indexes for orders
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_target ON orders(target_id)"
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_orders_window
               ON orders(requested_window_start, requested_window_end)"""
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_workspace ON orders(workspace_id)"
        )

        # Create indexes for acquisitions
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_acq_satellite_time
               ON acquisitions(satellite_id, start_time)"""
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_acq_target ON acquisitions(target_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_acq_state ON acquisitions(state)"
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_acq_time_range
               ON acquisitions(start_time, end_time)"""
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_acq_order ON acquisitions(order_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_acq_workspace ON acquisitions(workspace_id)"
        )

        # Create indexes for plans
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_plans_workspace ON plans(workspace_id)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status)")

        # Create indexes for plan_items
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_planitems_plan ON plan_items(plan_id)"
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_planitems_opportunity
               ON plan_items(opportunity_id)"""
        )

        # Create indexes for conflicts
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_conflicts_workspace ON conflicts(workspace_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_conflicts_type ON conflicts(type)"
        )

        # Create commit_audit_logs table for commit traceability
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS commit_audit_logs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                plan_id TEXT NOT NULL REFERENCES plans(id),
                workspace_id TEXT REFERENCES workspaces(id),
                committed_by TEXT,
                commit_type TEXT NOT NULL DEFAULT 'normal',
                config_hash TEXT NOT NULL,
                repair_diff_json TEXT,
                acquisitions_created INTEGER NOT NULL DEFAULT 0,
                acquisitions_dropped INTEGER NOT NULL DEFAULT 0,
                score_before REAL,
                score_after REAL,
                conflicts_before INTEGER NOT NULL DEFAULT 0,
                conflicts_after INTEGER NOT NULL DEFAULT 0,
                notes TEXT
            )
        """
        )

        # Create indexes for commit_audit_logs
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_workspace ON commit_audit_logs(workspace_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_plan ON commit_audit_logs(plan_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_created ON commit_audit_logs(created_at)"
        )

        # Record migration
        cursor.execute(
            """
            INSERT OR REPLACE INTO schema_migrations (version, applied_at, description)
            VALUES (?, ?, ?)
        """,
            (
                "2.0",
                now,
                "Persistent scheduling: orders, acquisitions, plans, conflicts",
            ),
        )

        logger.info("Migration to schema v2.0 complete")

    def _migrate_to_v2_1(self, conn: sqlite3.Connection) -> None:
        """Migrate database schema to v2.1 - Order inbox & batch planning."""
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat() + "Z"

        logger.info("Running migration to schema v2.1...")

        # Add new columns to orders table
        new_order_columns = [
            ("order_type", "TEXT DEFAULT 'IMAGING'"),
            ("due_time", "TEXT"),
            ("earliest_start", "TEXT"),
            ("latest_end", "TEXT"),
            ("batch_id", "TEXT"),
            ("tags_json", "TEXT"),
            ("requested_satellite_group", "TEXT"),
            ("user_notes", "TEXT"),
            ("reject_reason", "TEXT"),
        ]

        for col_name, col_type in new_order_columns:
            try:
                cursor.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                # Column already exists
                pass

        # Create order_batches table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS order_batches (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                policy_id TEXT NOT NULL,
                horizon_from TEXT NOT NULL,
                horizon_to TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                plan_id TEXT REFERENCES plans(id),
                notes TEXT,
                metrics_json TEXT
            )
        """
        )

        # Create batch_members table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS batch_members (
                id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL REFERENCES order_batches(id) ON DELETE CASCADE,
                order_id TEXT NOT NULL REFERENCES orders(id),
                role TEXT NOT NULL DEFAULT 'primary',
                created_at TEXT NOT NULL,
                UNIQUE(batch_id, order_id)
            )
        """
        )

        # Create indexes for order_batches
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_batches_workspace ON order_batches(workspace_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_batches_status ON order_batches(status)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_batches_horizon ON order_batches(horizon_from, horizon_to)"
        )

        # Create indexes for batch_members
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_batch_members_batch ON batch_members(batch_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_batch_members_order ON batch_members(order_id)"
        )

        # Create indexes for new order columns
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_due_time ON orders(due_time)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_order_type ON orders(order_type)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_batch ON orders(batch_id)"
        )

        # Record migration
        cursor.execute(
            """
            INSERT OR REPLACE INTO schema_migrations (version, applied_at, description)
            VALUES (?, ?, ?)
        """,
            (
                "2.1",
                now,
                "Order inbox automation & batch planning: extended order fields, batches, batch_members",
            ),
        )

        logger.info("Migration to schema v2.1 complete")

    def _migrate_to_v2_2(self, conn: sqlite3.Connection) -> None:
        """Migrate database schema to v2.2 - Soft lock removal.

        PR-OPS-REPAIR-DEFAULT-01: Normalize all soft locks to none.
        Only hard and none lock levels are supported going forward.
        """
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat() + "Z"

        logger.info("Running migration to schema v2.2...")

        # Normalize soft locks to none
        cursor.execute(
            """
            UPDATE acquisitions
            SET lock_level = 'none', updated_at = ?
            WHERE lock_level = 'soft'
        """,
            (now,),
        )
        soft_count = cursor.rowcount

        if soft_count > 0:
            logger.info(f"Normalized {soft_count} soft locks to 'none'")

        # Record migration
        cursor.execute(
            """
            INSERT OR REPLACE INTO schema_migrations (version, applied_at, description)
            VALUES (?, ?, ?)
        """,
            (
                "2.2",
                now,
                "Soft lock removal: normalized all soft locks to none (PR-OPS-REPAIR-DEFAULT-01)",
            ),
        )

        logger.info("Migration to schema v2.2 complete")

    def _migrate_to_v2_3(self, conn: sqlite3.Connection) -> None:
        """Migrate database schema to v2.3 - Priority semantics inversion.

        PR: chore/priority-semantics-1-best-5-lowest-default-5
        Old semantics: 5 = best (highest importance), 1 = lowest
        New semantics: 1 = best (highest importance), 5 = lowest
        Formula: new_priority = 6 - old_priority  (1<->5, 2<->4, 3 stays 3)
        """
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat() + "Z"

        logger.info(
            "Running migration to schema v2.3 (priority semantics inversion)..."
        )

        # Invert order priorities: 6 - priority maps 1<->5, 2<->4, 3 stays 3
        cursor.execute(
            "UPDATE orders SET priority = 6 - priority WHERE priority BETWEEN 1 AND 5"
        )
        migrated_count = cursor.rowcount
        if migrated_count > 0:
            logger.info(
                f"Inverted priorities for {migrated_count} orders (old: 5=best -> new: 1=best)"
            )
        else:
            logger.info(
                "No orders to migrate (table empty or no rows with priority 1-5)"
            )

        # Record migration
        cursor.execute(
            """
            INSERT OR REPLACE INTO schema_migrations (version, applied_at, description)
            VALUES (?, ?, ?)
        """,
            (
                "2.3",
                now,
                "Priority semantics inversion: 1=best, 5=lowest, default=5",
            ),
        )

        logger.info("Migration to schema v2.3 complete")

    def _migrate_to_v2_4(self, conn: sqlite3.Connection) -> None:
        """Migrate database schema to v2.4 - Add missing audit log columns.

        The commit_audit_logs table was created in v2.0 but score_before,
        score_after, conflicts_before, and conflicts_after columns were added
        to the CREATE TABLE definition without an ALTER migration.
        """
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat() + "Z"

        logger.info("Running migration to schema v2.4...")

        new_columns = [
            ("score_before", "REAL"),
            ("score_after", "REAL"),
            ("conflicts_before", "INTEGER NOT NULL DEFAULT 0"),
            ("conflicts_after", "INTEGER NOT NULL DEFAULT 0"),
        ]

        for col_name, col_type in new_columns:
            try:
                cursor.execute(
                    f"ALTER TABLE commit_audit_logs ADD COLUMN {col_name} {col_type}"
                )
                logger.info(f"  Added column commit_audit_logs.{col_name}")
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Record migration
        cursor.execute(
            """
            INSERT OR REPLACE INTO schema_migrations (version, applied_at, description)
            VALUES (?, ?, ?)
        """,
            (
                "2.4",
                now,
                "Add score_before/after, conflicts_before/after to commit_audit_logs",
            ),
        )

        logger.info("Migration to schema v2.4 complete")

    # =========================================================================
    # Order Operations
    # =========================================================================

    def create_order(
        self,
        target_id: str,
        priority: int = 5,
        constraints: Optional[Dict[str, Any]] = None,
        requested_window_start: Optional[str] = None,
        requested_window_end: Optional[str] = None,
        source: str = "manual",
        notes: Optional[str] = None,
        external_ref: Optional[str] = None,
        workspace_id: Optional[str] = None,
        # Extended fields for PS2.5
        order_type: str = "IMAGING",
        due_time: Optional[str] = None,
        earliest_start: Optional[str] = None,
        latest_end: Optional[str] = None,
        tags: Optional[List[str]] = None,
        requested_satellite_group: Optional[str] = None,
        user_notes: Optional[str] = None,
    ) -> Order:
        """Create a new order.

        Args:
            target_id: Target to image
            priority: Priority 1=best, 5=lowest (default 5)
            constraints: Optional constraints dict
            requested_window_start: Optional start of requested window
            requested_window_end: Optional end of requested window
            source: Order source (manual | api | batch | import)
            notes: Optional notes
            external_ref: Optional external reference ID
            workspace_id: Associated workspace
            order_type: IMAGING | DOWNLINK | MAINTENANCE
            due_time: SLA deadline (ISO datetime)
            earliest_start: Earliest start constraint
            latest_end: Latest end constraint
            tags: List of tags
            requested_satellite_group: Preferred satellite group
            user_notes: User-provided notes

        Returns:
            Created Order object
        """
        order_id = f"ord_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat() + "Z"

        constraints_json = json.dumps(constraints) if constraints else None
        tags_json = json.dumps(tags) if tags else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO orders (
                    id, created_at, updated_at, status, target_id, priority,
                    constraints_json, requested_window_start, requested_window_end,
                    source, notes, external_ref, workspace_id,
                    order_type, due_time, earliest_start, latest_end,
                    tags_json, requested_satellite_group, user_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    order_id,
                    now,
                    now,
                    "new",
                    target_id,
                    priority,
                    constraints_json,
                    requested_window_start,
                    requested_window_end,
                    source,
                    notes,
                    external_ref,
                    workspace_id,
                    order_type,
                    due_time,
                    earliest_start,
                    latest_end,
                    tags_json,
                    requested_satellite_group,
                    user_notes,
                ),
            )
            conn.commit()

        logger.info(f"Created order {order_id} for target {target_id}")

        return Order(
            id=order_id,
            created_at=now,
            updated_at=now,
            status="new",
            target_id=target_id,
            priority=priority,
            constraints_json=constraints_json,
            requested_window_start=requested_window_start,
            requested_window_end=requested_window_end,
            source=source,
            notes=notes,
            external_ref=external_ref,
            workspace_id=workspace_id,
            order_type=order_type,
            due_time=due_time,
            earliest_start=earliest_start,
            latest_end=latest_end,
            tags_json=tags_json,
            requested_satellite_group=requested_satellite_group,
            user_notes=user_notes,
        )

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_order(row)

    def list_orders(
        self,
        workspace_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Order]:
        """List orders with optional filters.

        Args:
            workspace_id: Filter by workspace
            status: Filter by status (new|planned|committed|cancelled|completed)
            limit: Max results
            offset: Pagination offset

        Returns:
            List of Order objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM orders WHERE 1=1"
            params: List[Any] = []

            if workspace_id:
                query += " AND workspace_id = ?"
                params.append(workspace_id)
            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [self._row_to_order(row) for row in cursor.fetchall()]

    def update_order_status(self, order_id: str, status: str) -> bool:
        """Update order status.

        Args:
            order_id: Order to update
            status: New status

        Returns:
            True if updated
        """
        valid_statuses = ["new", "planned", "committed", "cancelled", "completed"]
        if status not in valid_statuses:
            raise ValueError(
                f"Invalid status: {status}. Must be one of {valid_statuses}"
            )

        now = datetime.now(timezone.utc).isoformat() + "Z"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, order_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_order(
        self, order_id: str, cascade_acquisitions: bool = True
    ) -> Dict[str, Any]:
        """Delete an order and optionally its associated acquisitions.

        Args:
            order_id: Order to delete
            cascade_acquisitions: If True, also delete acquisitions linked to this order

        Returns:
            Dict with deleted counts: {"order_deleted": bool, "acquisitions_deleted": int}
        """
        result: Dict[str, Any] = {"order_deleted": False, "acquisitions_deleted": 0}

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check order exists
            cursor.execute("SELECT id FROM orders WHERE id = ?", (order_id,))
            if not cursor.fetchone():
                return result

            # Delete associated acquisitions if requested
            if cascade_acquisitions:
                cursor.execute(
                    "SELECT COUNT(*) as cnt FROM acquisitions WHERE order_id = ?",
                    (order_id,),
                )
                acq_count = cursor.fetchone()["cnt"]
                cursor.execute(
                    "DELETE FROM acquisitions WHERE order_id = ?",
                    (order_id,),
                )
                result["acquisitions_deleted"] = acq_count

            # Remove from batch_members
            cursor.execute(
                "DELETE FROM batch_members WHERE order_id = ?",
                (order_id,),
            )

            # Delete the order
            cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
            result["order_deleted"] = cursor.rowcount > 0

            conn.commit()

        if result["order_deleted"]:
            logger.info(
                f"Deleted order {order_id} (cascade_acquisitions={cascade_acquisitions}, "
                f"acquisitions_deleted={result['acquisitions_deleted']})"
            )

        return result

    def _row_to_order(self, row: sqlite3.Row) -> Order:
        """Convert database row to Order object."""
        # Handle new columns that might not exist in older databases
        row_keys = row.keys()
        return Order(
            id=row["id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            status=row["status"],
            target_id=row["target_id"],
            priority=row["priority"],
            constraints_json=row["constraints_json"],
            requested_window_start=row["requested_window_start"],
            requested_window_end=row["requested_window_end"],
            source=row["source"],
            notes=row["notes"],
            external_ref=row["external_ref"],
            workspace_id=row["workspace_id"],
            # Extended fields (v2.1)
            order_type=row["order_type"] if "order_type" in row_keys else "IMAGING",
            due_time=row["due_time"] if "due_time" in row_keys else None,
            earliest_start=(
                row["earliest_start"] if "earliest_start" in row_keys else None
            ),
            latest_end=row["latest_end"] if "latest_end" in row_keys else None,
            batch_id=row["batch_id"] if "batch_id" in row_keys else None,
            tags_json=row["tags_json"] if "tags_json" in row_keys else None,
            requested_satellite_group=(
                row["requested_satellite_group"]
                if "requested_satellite_group" in row_keys
                else None
            ),
            user_notes=row["user_notes"] if "user_notes" in row_keys else None,
            reject_reason=row["reject_reason"] if "reject_reason" in row_keys else None,
        )

    # =========================================================================
    # Acquisition Operations
    # =========================================================================

    def create_acquisition(
        self,
        satellite_id: str,
        target_id: str,
        start_time: str,
        end_time: str,
        roll_angle_deg: float,
        pitch_angle_deg: float = 0.0,
        mode: str = "OPTICAL",
        incidence_angle_deg: Optional[float] = None,
        look_side: Optional[str] = None,
        pass_direction: Optional[str] = None,
        sar_mode: Optional[str] = None,
        swath_width_km: Optional[float] = None,
        scene_length_km: Optional[float] = None,
        state: str = "tentative",
        lock_level: str = "none",
        source: str = "auto",
        order_id: Optional[str] = None,
        plan_id: Optional[str] = None,
        opportunity_id: Optional[str] = None,
        quality_score: Optional[float] = None,
        maneuver_time_s: Optional[float] = None,
        slack_time_s: Optional[float] = None,
        workspace_id: Optional[str] = None,
    ) -> Acquisition:
        """Create a new acquisition (scheduled slot)."""
        acq_id = f"acq_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat() + "Z"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO acquisitions (
                    id, created_at, updated_at, satellite_id, target_id,
                    start_time, end_time, mode, roll_angle_deg, pitch_angle_deg,
                    incidence_angle_deg, look_side, pass_direction, sar_mode,
                    swath_width_km, scene_length_km, state, lock_level, source,
                    order_id, plan_id, opportunity_id, quality_score,
                    maneuver_time_s, slack_time_s, workspace_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    acq_id,
                    now,
                    now,
                    satellite_id,
                    target_id,
                    start_time,
                    end_time,
                    mode,
                    roll_angle_deg,
                    pitch_angle_deg,
                    incidence_angle_deg,
                    look_side,
                    pass_direction,
                    sar_mode,
                    swath_width_km,
                    scene_length_km,
                    state,
                    lock_level,
                    source,
                    order_id,
                    plan_id,
                    opportunity_id,
                    quality_score,
                    maneuver_time_s,
                    slack_time_s,
                    workspace_id,
                ),
            )
            conn.commit()

        logger.info(
            f"Created acquisition {acq_id}: {satellite_id} -> {target_id} at {start_time}"
        )

        return Acquisition(
            id=acq_id,
            created_at=now,
            updated_at=now,
            satellite_id=satellite_id,
            target_id=target_id,
            start_time=start_time,
            end_time=end_time,
            mode=mode,
            roll_angle_deg=roll_angle_deg,
            pitch_angle_deg=pitch_angle_deg,
            incidence_angle_deg=incidence_angle_deg,
            look_side=look_side,
            pass_direction=pass_direction,
            sar_mode=sar_mode,
            swath_width_km=swath_width_km,
            scene_length_km=scene_length_km,
            state=state,
            lock_level=lock_level,
            source=source,
            order_id=order_id,
            plan_id=plan_id,
            opportunity_id=opportunity_id,
            quality_score=quality_score,
            maneuver_time_s=maneuver_time_s,
            slack_time_s=slack_time_s,
            workspace_id=workspace_id,
        )

    def get_acquisition(self, acq_id: str) -> Optional[Acquisition]:
        """Get an acquisition by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM acquisitions WHERE id = ?", (acq_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_acquisition(row)

    def list_acquisitions(
        self,
        workspace_id: Optional[str] = None,
        satellite_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        state: Optional[str] = None,
        include_tentative: bool = True,
        limit: int = 500,
        offset: int = 0,
    ) -> List[Acquisition]:
        """List acquisitions with filters.

        Args:
            workspace_id: Filter by workspace
            satellite_id: Filter by satellite
            start_time: Filter acquisitions starting after this time
            end_time: Filter acquisitions ending before this time
            state: Filter by state
            include_tentative: Include tentative acquisitions
            limit: Max results
            offset: Pagination offset

        Returns:
            List of Acquisition objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM acquisitions WHERE 1=1"
            params: List[Any] = []

            if workspace_id:
                # Include acquisitions with matching workspace_id OR NULL workspace_id
                query += " AND (workspace_id = ? OR workspace_id IS NULL)"
                params.append(workspace_id)
            if satellite_id:
                query += " AND satellite_id = ?"
                params.append(satellite_id)
            if start_time:
                query += " AND start_time >= ?"
                params.append(start_time)
            if end_time:
                query += " AND end_time <= ?"
                params.append(end_time)
            if state:
                query += " AND state = ?"
                params.append(state)
            if not include_tentative:
                query += " AND state != 'tentative'"

            query += " ORDER BY start_time ASC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [self._row_to_acquisition(row) for row in cursor.fetchall()]

    def delete_acquisition(self, acquisition_id: str) -> bool:
        """Delete a single acquisition by ID.

        Hard-locked acquisitions cannot be deleted unless force is used
        at the router level.

        Args:
            acquisition_id: Acquisition to delete

        Returns:
            True if deleted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM acquisitions WHERE id = ?",
                (acquisition_id,),
            )
            conn.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Deleted acquisition {acquisition_id}")
        return deleted

    def bulk_delete_acquisitions(self, acquisition_ids: List[str]) -> Dict[str, Any]:
        """Delete multiple acquisitions by ID.

        Args:
            acquisition_ids: List of acquisition IDs to delete

        Returns:
            Dict with {"deleted": int, "failed": list[str]}
        """
        if not acquisition_ids:
            return {"deleted": 0, "failed": []}

        deleted_count = 0
        failed: List[str] = []

        with self._get_connection() as conn:
            cursor = conn.cursor()
            for acq_id in acquisition_ids:
                cursor.execute(
                    "DELETE FROM acquisitions WHERE id = ?",
                    (acq_id,),
                )
                if cursor.rowcount > 0:
                    deleted_count += 1
                else:
                    failed.append(acq_id)
            conn.commit()

        logger.info(
            f"Bulk deleted {deleted_count} acquisitions " f"({len(failed)} failed)"
        )
        return {"deleted": deleted_count, "failed": failed}

    def get_acquisitions_in_horizon(
        self,
        start_time: str,
        end_time: str,
        workspace_id: Optional[str] = None,
        satellite_id: Optional[str] = None,
        include_tentative: bool = True,
    ) -> List[Acquisition]:
        """Get acquisitions within a time horizon.

        This is the key query for incremental planning - returns all acquisitions
        that overlap with the given time window.

        Args:
            start_time: Horizon start
            end_time: Horizon end
            workspace_id: Filter by workspace
            satellite_id: Filter by satellite
            include_tentative: Include tentative acquisitions

        Returns:
            List of overlapping Acquisition objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Find acquisitions that overlap with the horizon
            # Overlap condition: acq.start < horizon.end AND acq.end > horizon.start
            query = """
                SELECT * FROM acquisitions
                WHERE start_time < ? AND end_time > ?
            """
            params: List[Any] = [end_time, start_time]

            if workspace_id:
                # Include acquisitions with matching workspace_id OR NULL workspace_id
                # (NULL workspace_id means "global" or legacy data that belongs to all workspaces)
                query += " AND (workspace_id = ? OR workspace_id IS NULL)"
                params.append(workspace_id)
            if satellite_id:
                query += " AND satellite_id = ?"
                params.append(satellite_id)
            if not include_tentative:
                query += " AND state != 'tentative'"

            query += " ORDER BY start_time ASC"

            cursor.execute(query, params)
            return [self._row_to_acquisition(row) for row in cursor.fetchall()]

    def get_committed_acquisitions_for_satellite(
        self,
        satellite_id: str,
        start_time: str,
        end_time: str,
        workspace_id: Optional[str] = None,
    ) -> List[Acquisition]:
        """Get committed/locked acquisitions for a satellite in a time range.

        Used by incremental planning to find blocked intervals.

        Args:
            satellite_id: Satellite ID
            start_time: Window start
            end_time: Window end
            workspace_id: Optional workspace filter

        Returns:
            List of committed/locked Acquisition objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT * FROM acquisitions
                WHERE satellite_id = ?
                  AND start_time < ?
                  AND end_time > ?
                  AND (state IN ('committed', 'locked', 'executing')
                       OR lock_level = 'hard')
            """
            params: List[Any] = [satellite_id, end_time, start_time]

            if workspace_id:
                # Include acquisitions with matching workspace_id OR NULL workspace_id
                query += " AND (workspace_id = ? OR workspace_id IS NULL)"
                params.append(workspace_id)

            query += " ORDER BY start_time ASC"

            cursor.execute(query, params)
            return [self._row_to_acquisition(row) for row in cursor.fetchall()]

    def update_acquisition_state(
        self,
        acq_id: str,
        state: Optional[str] = None,
        lock_level: Optional[str] = None,
    ) -> bool:
        """Update acquisition state and/or lock level."""
        now = datetime.now(timezone.utc).isoformat() + "Z"

        updates = ["updated_at = ?"]
        params: List[Any] = [now]

        if state:
            valid_states = [
                "tentative",
                "locked",
                "committed",
                "executing",
                "completed",
                "failed",
            ]
            if state not in valid_states:
                raise ValueError(f"Invalid state: {state}")
            updates.append("state = ?")
            params.append(state)

        if lock_level:
            valid_locks = ["none", "hard"]
            if lock_level not in valid_locks:
                raise ValueError(
                    f"Invalid lock_level: {lock_level}. Must be 'none' or 'hard'"
                )
            updates.append("lock_level = ?")
            params.append(lock_level)

        params.append(acq_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE acquisitions SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()
            return cursor.rowcount > 0

    def _row_to_acquisition(self, row: sqlite3.Row) -> Acquisition:
        """Convert database row to Acquisition object."""
        return Acquisition(
            id=row["id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            satellite_id=row["satellite_id"],
            target_id=row["target_id"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            mode=row["mode"],
            roll_angle_deg=row["roll_angle_deg"],
            pitch_angle_deg=row["pitch_angle_deg"],
            incidence_angle_deg=row["incidence_angle_deg"],
            look_side=row["look_side"],
            pass_direction=row["pass_direction"],
            sar_mode=row["sar_mode"],
            swath_width_km=row["swath_width_km"],
            scene_length_km=row["scene_length_km"],
            state=row["state"],
            lock_level=row["lock_level"],
            source=row["source"],
            order_id=row["order_id"],
            plan_id=row["plan_id"],
            opportunity_id=row["opportunity_id"],
            quality_score=row["quality_score"],
            maneuver_time_s=row["maneuver_time_s"],
            slack_time_s=row["slack_time_s"],
            workspace_id=row["workspace_id"],
        )

    # =========================================================================
    # Plan Operations
    # =========================================================================

    def create_plan(
        self,
        algorithm: str,
        config: Dict[str, Any],
        input_hash: str,
        run_id: str,
        metrics: Dict[str, Any],
        score: Optional[float] = None,
        workspace_id: Optional[str] = None,
    ) -> Plan:
        """Create a new plan."""
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat() + "Z"

        config_json = json.dumps(config)
        metrics_json = json.dumps(metrics)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO plans (
                    id, created_at, algorithm, config_json, input_hash,
                    run_id, score, metrics_json, status, workspace_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    plan_id,
                    now,
                    algorithm,
                    config_json,
                    input_hash,
                    run_id,
                    score,
                    metrics_json,
                    "candidate",
                    workspace_id,
                ),
            )
            conn.commit()

        logger.info(f"Created plan {plan_id} with algorithm {algorithm}")

        return Plan(
            id=plan_id,
            created_at=now,
            algorithm=algorithm,
            config_json=config_json,
            input_hash=input_hash,
            run_id=run_id,
            score=score,
            metrics_json=metrics_json,
            status="candidate",
            workspace_id=workspace_id,
        )

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get a plan by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM plans WHERE id = ?", (plan_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_plan(row)

    def update_plan_status(self, plan_id: str, status: str) -> bool:
        """Update plan status."""
        valid_statuses = ["candidate", "committed", "superseded", "rejected"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE plans SET status = ? WHERE id = ?",
                (status, plan_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def _row_to_plan(self, row: sqlite3.Row) -> Plan:
        """Convert database row to Plan object."""
        return Plan(
            id=row["id"],
            created_at=row["created_at"],
            algorithm=row["algorithm"],
            config_json=row["config_json"],
            input_hash=row["input_hash"],
            run_id=row["run_id"],
            score=row["score"],
            metrics_json=row["metrics_json"],
            status=row["status"],
            workspace_id=row["workspace_id"],
        )

    # =========================================================================
    # Plan Item Operations
    # =========================================================================

    def create_plan_item(
        self,
        plan_id: str,
        opportunity_id: str,
        satellite_id: str,
        target_id: str,
        start_time: str,
        end_time: str,
        roll_angle_deg: float,
        pitch_angle_deg: float = 0.0,
        value: Optional[float] = None,
        quality_score: Optional[float] = None,
        maneuver_time_s: Optional[float] = None,
        slack_time_s: Optional[float] = None,
        order_id: Optional[str] = None,
    ) -> PlanItem:
        """Create a plan item."""
        item_id = f"planitem_{uuid.uuid4().hex[:12]}"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO plan_items (
                    id, plan_id, opportunity_id, satellite_id, target_id,
                    start_time, end_time, roll_angle_deg, pitch_angle_deg,
                    value, quality_score, maneuver_time_s, slack_time_s, order_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    item_id,
                    plan_id,
                    opportunity_id,
                    satellite_id,
                    target_id,
                    start_time,
                    end_time,
                    roll_angle_deg,
                    pitch_angle_deg,
                    value,
                    quality_score,
                    maneuver_time_s,
                    slack_time_s,
                    order_id,
                ),
            )
            conn.commit()

        return PlanItem(
            id=item_id,
            plan_id=plan_id,
            opportunity_id=opportunity_id,
            satellite_id=satellite_id,
            target_id=target_id,
            start_time=start_time,
            end_time=end_time,
            roll_angle_deg=roll_angle_deg,
            pitch_angle_deg=pitch_angle_deg,
            value=value,
            quality_score=quality_score,
            maneuver_time_s=maneuver_time_s,
            slack_time_s=slack_time_s,
            order_id=order_id,
        )

    def get_plan_items(self, plan_id: str) -> List[PlanItem]:
        """Get all items for a plan."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM plan_items WHERE plan_id = ? ORDER BY start_time ASC",
                (plan_id,),
            )
            return [self._row_to_plan_item(row) for row in cursor.fetchall()]

    def _row_to_plan_item(self, row: sqlite3.Row) -> PlanItem:
        """Convert database row to PlanItem object."""
        return PlanItem(
            id=row["id"],
            plan_id=row["plan_id"],
            opportunity_id=row["opportunity_id"],
            satellite_id=row["satellite_id"],
            target_id=row["target_id"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            roll_angle_deg=row["roll_angle_deg"],
            pitch_angle_deg=row["pitch_angle_deg"],
            value=row["value"],
            quality_score=row["quality_score"],
            maneuver_time_s=row["maneuver_time_s"],
            slack_time_s=row["slack_time_s"],
            order_id=row["order_id"],
        )

    # =========================================================================
    # Commit Plan Operation
    # =========================================================================

    def commit_plan(
        self,
        plan_id: str,
        item_ids: List[str],
        lock_level: str = "none",
        mode: str = "OPTICAL",
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Commit plan items as acquisitions.

        This is the key operation that turns a candidate plan into
        committed acquisitions.

        Args:
            plan_id: Plan to commit
            item_ids: Specific plan item IDs to commit
            lock_level: Lock level for created acquisitions (none|hard)
            mode: Mission mode (OPTICAL|SAR)
            workspace_id: Workspace ID for acquisitions

        Returns:
            Dict with committed count, acquisition IDs, and updated orders
        """
        # PR-OPS-REPAIR-DEFAULT-01: Normalize lock levels (soft → none)
        if lock_level == "soft":
            lock_level = "none"
        if lock_level not in ["none", "hard"]:
            lock_level = "none"

        created_acquisitions = []
        updated_orders = set()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get the plan
            cursor.execute("SELECT * FROM plans WHERE id = ?", (plan_id,))
            plan_row = cursor.fetchone()
            if not plan_row:
                raise ValueError(f"Plan not found: {plan_id}")

            # Get plan items to commit
            if item_ids:
                placeholders = ",".join("?" * len(item_ids))
                cursor.execute(
                    f"SELECT * FROM plan_items WHERE plan_id = ? AND id IN ({placeholders})",
                    [plan_id] + item_ids,
                )
            else:
                cursor.execute("SELECT * FROM plan_items WHERE plan_id = ?", (plan_id,))

            items = cursor.fetchall()
            now = datetime.now(timezone.utc).isoformat() + "Z"

            for item in items:
                acq_id = f"acq_{uuid.uuid4().hex[:12]}"

                # Create acquisition from plan item
                cursor.execute(
                    """
                    INSERT INTO acquisitions (
                        id, created_at, updated_at, satellite_id, target_id,
                        start_time, end_time, mode, roll_angle_deg, pitch_angle_deg,
                        state, lock_level, source, order_id, plan_id, opportunity_id,
                        quality_score, maneuver_time_s, slack_time_s, workspace_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        acq_id,
                        now,
                        now,
                        item["satellite_id"],
                        item["target_id"],
                        item["start_time"],
                        item["end_time"],
                        mode,
                        item["roll_angle_deg"],
                        item["pitch_angle_deg"],
                        "committed",
                        lock_level,
                        "auto",
                        item["order_id"],
                        plan_id,
                        item["opportunity_id"],
                        item["quality_score"],
                        item["maneuver_time_s"],
                        item["slack_time_s"],
                        workspace_id,
                    ),
                )

                created_acquisitions.append({"id": acq_id, "plan_item_id": item["id"]})

                # Track order for status update
                if item["order_id"]:
                    updated_orders.add(item["order_id"])

            # Update order statuses
            for order_id in updated_orders:
                cursor.execute(
                    "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
                    ("committed", now, order_id),
                )

            # Update plan status
            cursor.execute(
                "UPDATE plans SET status = ? WHERE id = ?",
                ("committed", plan_id),
            )

            conn.commit()

        logger.info(
            f"Committed plan {plan_id}: {len(created_acquisitions)} acquisitions created"
        )

        return {
            "committed": len(created_acquisitions),
            "acquisitions_created": created_acquisitions,
            "orders_updated": list(updated_orders),
        }

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_acquisition_statistics(
        self,
        start_time: str,
        end_time: str,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get acquisition statistics for a time window.

        Args:
            start_time: Window start
            end_time: Window end
            workspace_id: Optional workspace filter

        Returns:
            Statistics dict
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            base_query = """
                FROM acquisitions
                WHERE start_time < ? AND end_time > ?
            """
            params: List[Any] = [end_time, start_time]

            if workspace_id:
                # Include acquisitions with matching workspace_id OR NULL workspace_id
                base_query += " AND (workspace_id = ? OR workspace_id IS NULL)"
                params.append(workspace_id)

            # Total count
            cursor.execute(f"SELECT COUNT(*) as cnt {base_query}", params)
            total = cursor.fetchone()["cnt"]

            # By state
            cursor.execute(
                f"SELECT state, COUNT(*) as cnt {base_query} GROUP BY state", params
            )
            by_state = {row["state"]: row["cnt"] for row in cursor.fetchall()}

            # By satellite
            cursor.execute(
                f"SELECT satellite_id, COUNT(*) as cnt {base_query} GROUP BY satellite_id",
                params,
            )
            by_satellite = {
                row["satellite_id"]: row["cnt"] for row in cursor.fetchall()
            }

            return {
                "total_acquisitions": total,
                "by_state": by_state,
                "by_satellite": by_satellite,
            }

    # =========================================================================
    # Conflict Operations
    # =========================================================================

    def create_conflict(
        self,
        conflict_type: str,
        severity: str,
        description: str,
        acquisition_ids: List[str],
        workspace_id: Optional[str] = None,
    ) -> Conflict:
        """Create a new conflict record.

        Args:
            conflict_type: Type of conflict (temporal_overlap | slew_infeasible)
            severity: Severity level (error | warning | info)
            description: Human-readable description
            acquisition_ids: List of acquisition IDs involved
            workspace_id: Associated workspace

        Returns:
            Created Conflict object
        """
        conflict_id = f"conflict_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat() + "Z"
        acquisition_ids_json = json.dumps(acquisition_ids)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO conflicts (
                    id, detected_at, type, severity, description,
                    acquisition_ids_json, workspace_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    conflict_id,
                    now,
                    conflict_type,
                    severity,
                    description,
                    acquisition_ids_json,
                    workspace_id,
                ),
            )
            conn.commit()

        logger.info(
            f"Created conflict {conflict_id}: {conflict_type} ({severity}) "
            f"involving {len(acquisition_ids)} acquisitions"
        )

        return Conflict(
            id=conflict_id,
            detected_at=now,
            type=conflict_type,
            severity=severity,
            description=description,
            acquisition_ids_json=acquisition_ids_json,
            resolved_at=None,
            resolution_action=None,
            resolution_notes=None,
            workspace_id=workspace_id,
        )

    def get_conflict(self, conflict_id: str) -> Optional[Conflict]:
        """Get a conflict by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM conflicts WHERE id = ?", (conflict_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_conflict(row)

    def list_conflicts(
        self,
        workspace_id: Optional[str] = None,
        conflict_type: Optional[str] = None,
        severity: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 500,
        offset: int = 0,
    ) -> List[Conflict]:
        """List conflicts with optional filters.

        Args:
            workspace_id: Filter by workspace
            conflict_type: Filter by type (temporal_overlap | slew_infeasible)
            severity: Filter by severity (error | warning | info)
            resolved: If True, only resolved; if False, only unresolved; if None, all
            limit: Max results
            offset: Pagination offset

        Returns:
            List of Conflict objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM conflicts WHERE 1=1"
            params: List[Any] = []

            if workspace_id:
                query += " AND workspace_id = ?"
                params.append(workspace_id)
            if conflict_type:
                query += " AND type = ?"
                params.append(conflict_type)
            if severity:
                query += " AND severity = ?"
                params.append(severity)
            if resolved is not None:
                if resolved:
                    query += " AND resolved_at IS NOT NULL"
                else:
                    query += " AND resolved_at IS NULL"

            query += " ORDER BY detected_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [self._row_to_conflict(row) for row in cursor.fetchall()]

    def get_conflicts_in_horizon(
        self,
        start_time: str,
        end_time: str,
        workspace_id: Optional[str] = None,
        satellite_id: Optional[str] = None,
        include_resolved: bool = False,
    ) -> List[Conflict]:
        """Get conflicts for acquisitions within a time horizon.

        This queries conflicts that involve acquisitions overlapping with
        the specified time window.

        Args:
            start_time: Horizon start
            end_time: Horizon end
            workspace_id: Filter by workspace
            satellite_id: Filter by satellite (requires joining acquisitions)
            include_resolved: Include resolved conflicts

        Returns:
            List of Conflict objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get acquisitions in horizon first
            acq_query = """
                SELECT id FROM acquisitions
                WHERE start_time < ? AND end_time > ?
            """
            acq_params: List[Any] = [end_time, start_time]

            if workspace_id:
                # Include acquisitions with matching workspace_id OR NULL workspace_id
                acq_query += " AND (workspace_id = ? OR workspace_id IS NULL)"
                acq_params.append(workspace_id)
            if satellite_id:
                acq_query += " AND satellite_id = ?"
                acq_params.append(satellite_id)

            cursor.execute(acq_query, acq_params)
            acq_ids = {row["id"] for row in cursor.fetchall()}

            if not acq_ids:
                return []

            # Get all conflicts for the workspace
            conflict_query = "SELECT * FROM conflicts WHERE 1=1"
            conflict_params: List[Any] = []

            if workspace_id:
                # Include conflicts with matching workspace_id OR NULL workspace_id
                conflict_query += " AND (workspace_id = ? OR workspace_id IS NULL)"
                conflict_params.append(workspace_id)
            if not include_resolved:
                conflict_query += " AND resolved_at IS NULL"

            conflict_query += " ORDER BY detected_at DESC"

            cursor.execute(conflict_query, conflict_params)
            all_conflicts = [self._row_to_conflict(row) for row in cursor.fetchall()]

            # Filter to conflicts involving acquisitions in the horizon
            horizon_conflicts = []
            for conflict in all_conflicts:
                try:
                    conflict_acq_ids = json.loads(conflict.acquisition_ids_json)
                    if any(aid in acq_ids for aid in conflict_acq_ids):
                        horizon_conflicts.append(conflict)
                except json.JSONDecodeError:
                    continue

            return horizon_conflicts

    def get_conflicts_for_acquisition(
        self,
        acquisition_id: str,
        include_resolved: bool = False,
    ) -> List[Conflict]:
        """Get all conflicts involving a specific acquisition.

        Args:
            acquisition_id: Acquisition ID to search for
            include_resolved: Include resolved conflicts

        Returns:
            List of Conflict objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # SQLite doesn't have native JSON array search, so we search text
            query = "SELECT * FROM conflicts WHERE acquisition_ids_json LIKE ?"
            params: List[Any] = [f'%"{acquisition_id}"%']

            if not include_resolved:
                query += " AND resolved_at IS NULL"

            query += " ORDER BY detected_at DESC"

            cursor.execute(query, params)
            return [self._row_to_conflict(row) for row in cursor.fetchall()]

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution_action: str,
        resolution_notes: Optional[str] = None,
    ) -> bool:
        """Mark a conflict as resolved.

        Args:
            conflict_id: Conflict to resolve
            resolution_action: Action taken (e.g., "removed_acquisition", "rescheduled")
            resolution_notes: Optional notes about resolution

        Returns:
            True if updated
        """
        now = datetime.now(timezone.utc).isoformat() + "Z"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE conflicts
                SET resolved_at = ?, resolution_action = ?, resolution_notes = ?
                WHERE id = ?
            """,
                (now, resolution_action, resolution_notes, conflict_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def clear_unresolved_conflicts(self, workspace_id: str) -> int:
        """Delete all unresolved conflicts for a workspace.

        Used when recomputing conflicts to start fresh.

        Args:
            workspace_id: Workspace to clear

        Returns:
            Number of conflicts deleted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM conflicts
                WHERE workspace_id = ? AND resolved_at IS NULL
            """,
                (workspace_id,),
            )
            conn.commit()
            deleted = cursor.rowcount

        logger.info(
            f"Cleared {deleted} unresolved conflicts for workspace {workspace_id}"
        )
        return deleted

    def get_conflict_statistics(
        self,
        workspace_id: Optional[str] = None,
        include_resolved: bool = False,
    ) -> Dict[str, Any]:
        """Get conflict statistics.

        Args:
            workspace_id: Optional workspace filter
            include_resolved: Include resolved conflicts in counts

        Returns:
            Statistics dict with totals by type and severity
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            base_query = "FROM conflicts WHERE 1=1"
            params: List[Any] = []

            if workspace_id:
                # Include conflicts with matching workspace_id OR NULL workspace_id
                base_query += " AND (workspace_id = ? OR workspace_id IS NULL)"
                params.append(workspace_id)
            if not include_resolved:
                base_query += " AND resolved_at IS NULL"

            # Total count
            cursor.execute(f"SELECT COUNT(*) as cnt {base_query}", params)
            total = cursor.fetchone()["cnt"]

            # By type
            cursor.execute(
                f"SELECT type, COUNT(*) as cnt {base_query} GROUP BY type", params
            )
            by_type = {row["type"]: row["cnt"] for row in cursor.fetchall()}

            # By severity
            cursor.execute(
                f"SELECT severity, COUNT(*) as cnt {base_query} GROUP BY severity",
                params,
            )
            by_severity = {row["severity"]: row["cnt"] for row in cursor.fetchall()}

            return {
                "total": total,
                "by_type": by_type,
                "by_severity": by_severity,
            }

    def _row_to_conflict(self, row: sqlite3.Row) -> Conflict:
        """Convert database row to Conflict object."""
        return Conflict(
            id=row["id"],
            detected_at=row["detected_at"],
            type=row["type"],
            severity=row["severity"],
            description=row["description"],
            acquisition_ids_json=row["acquisition_ids_json"],
            resolved_at=row["resolved_at"],
            resolution_action=row["resolution_action"],
            resolution_notes=row["resolution_notes"],
            workspace_id=row["workspace_id"],
        )

    # =========================================================================
    # Bulk Lock Operations
    # =========================================================================

    def update_acquisition_lock_level(
        self,
        acquisition_id: str,
        lock_level: str,
    ) -> bool:
        """Update lock level for a single acquisition.

        Args:
            acquisition_id: Acquisition ID to update
            lock_level: New lock level (none | hard)

        Returns:
            True if updated successfully
        """
        return self.update_acquisition_state(acquisition_id, lock_level=lock_level)

    def bulk_update_lock_levels(
        self,
        acquisition_ids: List[str],
        lock_level: str,
    ) -> Dict[str, Any]:
        """Update lock level for multiple acquisitions.

        Args:
            acquisition_ids: List of acquisition IDs to update
            lock_level: New lock level (none | hard)

        Returns:
            Dict with updated count and any failures
        """
        valid_locks = ["none", "hard"]
        if lock_level not in valid_locks:
            raise ValueError(
                f"Invalid lock_level: {lock_level}. Must be one of {valid_locks}"
            )

        now = datetime.now(timezone.utc).isoformat() + "Z"
        updated = 0
        failed: List[str] = []

        with self._get_connection() as conn:
            cursor = conn.cursor()
            for acq_id in acquisition_ids:
                try:
                    cursor.execute(
                        "UPDATE acquisitions SET lock_level = ?, updated_at = ? WHERE id = ?",
                        (lock_level, now, acq_id),
                    )
                    if cursor.rowcount > 0:
                        updated += 1
                    else:
                        failed.append(acq_id)
                except Exception as e:
                    logger.warning(f"Failed to update lock for {acq_id}: {e}")
                    failed.append(acq_id)
            conn.commit()

        logger.info(
            f"Bulk lock update: {updated} updated to {lock_level}, {len(failed)} failed"
        )

        return {
            "updated": updated,
            "failed": failed,
            "lock_level": lock_level,
        }

    def hard_lock_all_committed(
        self,
        workspace_id: str,
    ) -> Dict[str, Any]:
        """Hard-lock all committed acquisitions in a workspace.

        Args:
            workspace_id: Workspace ID

        Returns:
            Dict with updated count
        """
        now = datetime.now(timezone.utc).isoformat() + "Z"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE acquisitions
                SET lock_level = 'hard', updated_at = ?
                WHERE workspace_id = ?
                  AND state = 'committed'
                  AND lock_level != 'hard'
            """,
                (now, workspace_id),
            )
            conn.commit()
            updated = cursor.rowcount

        logger.info(
            f"Hard-locked {updated} committed acquisitions in workspace {workspace_id}"
        )

        return {
            "updated": updated,
            "workspace_id": workspace_id,
        }

    def get_acquisitions_by_lock_level(
        self,
        workspace_id: str,
        lock_level: Optional[str] = None,
    ) -> List[Acquisition]:
        """Get acquisitions filtered by lock level.

        Args:
            workspace_id: Workspace ID
            lock_level: Optional lock level filter

        Returns:
            List of Acquisition objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM acquisitions WHERE workspace_id = ?"
            params: List[Any] = [workspace_id]

            if lock_level:
                query += " AND lock_level = ?"
                params.append(lock_level)

            query += " ORDER BY start_time ASC"

            cursor.execute(query, params)
            return [self._row_to_acquisition(row) for row in cursor.fetchall()]

    # =========================================================================
    # Commit Audit Log Operations
    # =========================================================================

    def create_commit_audit_log(
        self,
        plan_id: str,
        commit_type: str,
        config_hash: str,
        acquisitions_created: int,
        acquisitions_dropped: int = 0,
        workspace_id: Optional[str] = None,
        committed_by: Optional[str] = None,
        repair_diff: Optional[Dict[str, Any]] = None,
        score_before: Optional[float] = None,
        score_after: Optional[float] = None,
        conflicts_before: int = 0,
        conflicts_after: int = 0,
        notes: Optional[str] = None,
    ) -> CommitAuditLog:
        """Create a commit audit log entry.

        Args:
            plan_id: Plan being committed
            commit_type: Type of commit (normal | repair | force)
            config_hash: Hash of config used for planning
            acquisitions_created: Number of acquisitions created
            acquisitions_dropped: Number of acquisitions dropped (repair)
            workspace_id: Associated workspace
            committed_by: User identifier
            repair_diff: Repair diff object (for repair commits)
            score_before: Score before commit
            score_after: Score after commit
            conflicts_before: Conflicts before commit
            conflicts_after: Conflicts after commit
            notes: Optional notes

        Returns:
            Created CommitAuditLog object
        """
        audit_id = f"audit_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat() + "Z"
        repair_diff_json = json.dumps(repair_diff) if repair_diff else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO commit_audit_logs (
                    id, created_at, plan_id, workspace_id, committed_by,
                    commit_type, config_hash, repair_diff_json,
                    acquisitions_created, acquisitions_dropped,
                    score_before, score_after, conflicts_before, conflicts_after, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    audit_id,
                    now,
                    plan_id,
                    workspace_id,
                    committed_by,
                    commit_type,
                    config_hash,
                    repair_diff_json,
                    acquisitions_created,
                    acquisitions_dropped,
                    score_before,
                    score_after,
                    conflicts_before,
                    conflicts_after,
                    notes,
                ),
            )
            conn.commit()

        logger.info(
            f"Created commit audit log {audit_id}: plan={plan_id}, "
            f"type={commit_type}, created={acquisitions_created}, dropped={acquisitions_dropped}"
        )

        return CommitAuditLog(
            id=audit_id,
            created_at=now,
            plan_id=plan_id,
            workspace_id=workspace_id,
            committed_by=committed_by,
            commit_type=commit_type,
            config_hash=config_hash,
            repair_diff_json=repair_diff_json,
            acquisitions_created=acquisitions_created,
            acquisitions_dropped=acquisitions_dropped,
            score_before=score_before,
            score_after=score_after,
            conflicts_before=conflicts_before,
            conflicts_after=conflicts_after,
            notes=notes,
        )

    def get_commit_audit_logs(
        self,
        workspace_id: Optional[str] = None,
        plan_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CommitAuditLog]:
        """Get commit audit logs with optional filters.

        Args:
            workspace_id: Filter by workspace
            plan_id: Filter by plan
            limit: Max results
            offset: Pagination offset

        Returns:
            List of CommitAuditLog objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM commit_audit_logs WHERE 1=1"
            params: List[Any] = []

            if workspace_id:
                query += " AND workspace_id = ?"
                params.append(workspace_id)
            if plan_id:
                query += " AND plan_id = ?"
                params.append(plan_id)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [self._row_to_audit_log(row) for row in cursor.fetchall()]

    def _row_to_audit_log(self, row: sqlite3.Row) -> CommitAuditLog:
        """Convert database row to CommitAuditLog object."""
        return CommitAuditLog(
            id=row["id"],
            created_at=row["created_at"],
            plan_id=row["plan_id"],
            workspace_id=row["workspace_id"],
            committed_by=row["committed_by"],
            commit_type=row["commit_type"],
            config_hash=row["config_hash"],
            repair_diff_json=row["repair_diff_json"],
            acquisitions_created=row["acquisitions_created"],
            acquisitions_dropped=row["acquisitions_dropped"],
            score_before=row["score_before"],
            score_after=row["score_after"],
            conflicts_before=row["conflicts_before"],
            conflicts_after=row["conflicts_after"],
            notes=row["notes"],
        )

    # =========================================================================
    # Atomic Commit with Rollback Support
    # =========================================================================

    def commit_plan_atomic(
        self,
        plan_id: str,
        item_ids: List[str],
        lock_level: str = "none",
        mode: str = "OPTICAL",
        workspace_id: Optional[str] = None,
        drop_acquisition_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Atomically commit plan items and optionally drop acquisitions.

        This is the transactional commit operation that ensures either all
        changes are applied or none (rollback on failure).

        Args:
            plan_id: Plan to commit
            item_ids: Specific plan item IDs to commit (empty = all)
            lock_level: Lock level for created acquisitions
            mode: Mission mode (OPTICAL | SAR)
            workspace_id: Workspace ID for acquisitions
            drop_acquisition_ids: Acquisitions to delete (for repair commits)

        Returns:
            Dict with results or raises exception on failure

        Raises:
            ValueError: If plan not found or invalid
            Exception: On database error (transaction rolled back)
        """
        if lock_level not in ["none", "hard"]:
            lock_level = "none"

        created_acquisitions: List[Dict[str, str]] = []
        dropped_acquisitions: List[str] = []
        updated_orders: set = set()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            try:
                # Start transaction (implicit with BEGIN)
                cursor.execute("BEGIN IMMEDIATE")

                # Get the plan
                cursor.execute("SELECT * FROM plans WHERE id = ?", (plan_id,))
                plan_row = cursor.fetchone()
                if not plan_row:
                    raise ValueError(f"Plan not found: {plan_id}")

                if plan_row["status"] == "committed":
                    raise ValueError(f"Plan {plan_id} is already committed")

                now = datetime.now(timezone.utc).isoformat() + "Z"

                # Step 1: Drop acquisitions (for repair commits)
                if drop_acquisition_ids:
                    for acq_id in drop_acquisition_ids:
                        # Mark as failed/superseded rather than delete to preserve history
                        cursor.execute(
                            """
                            UPDATE acquisitions
                            SET state = 'failed', updated_at = ?, lock_level = 'none'
                            WHERE id = ?
                        """,
                            (now, acq_id),
                        )
                        if cursor.rowcount > 0:
                            dropped_acquisitions.append(acq_id)

                # Step 2: Get plan items to commit
                if item_ids:
                    placeholders = ",".join("?" * len(item_ids))
                    cursor.execute(
                        f"SELECT * FROM plan_items WHERE plan_id = ? AND id IN ({placeholders})",
                        [plan_id] + item_ids,
                    )
                else:
                    cursor.execute(
                        "SELECT * FROM plan_items WHERE plan_id = ?", (plan_id,)
                    )

                items = cursor.fetchall()

                # Step 3: Create acquisitions from plan items
                for item in items:
                    acq_id = f"acq_{uuid.uuid4().hex[:12]}"

                    cursor.execute(
                        """
                        INSERT INTO acquisitions (
                            id, created_at, updated_at, satellite_id, target_id,
                            start_time, end_time, mode, roll_angle_deg, pitch_angle_deg,
                            state, lock_level, source, order_id, plan_id, opportunity_id,
                            quality_score, maneuver_time_s, slack_time_s, workspace_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            acq_id,
                            now,
                            now,
                            item["satellite_id"],
                            item["target_id"],
                            item["start_time"],
                            item["end_time"],
                            mode,
                            item["roll_angle_deg"],
                            item["pitch_angle_deg"],
                            "committed",
                            lock_level,
                            "auto",
                            item["order_id"],
                            plan_id,
                            item["opportunity_id"],
                            item["quality_score"],
                            item["maneuver_time_s"],
                            item["slack_time_s"],
                            workspace_id,
                        ),
                    )

                    created_acquisitions.append(
                        {"id": acq_id, "plan_item_id": item["id"]}
                    )

                    if item["order_id"]:
                        updated_orders.add(item["order_id"])

                # Step 4: Update order statuses
                for order_id in updated_orders:
                    cursor.execute(
                        "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
                        ("committed", now, order_id),
                    )

                # Step 5: Update plan status
                cursor.execute(
                    "UPDATE plans SET status = ? WHERE id = ?",
                    ("committed", plan_id),
                )

                # Commit transaction
                conn.commit()

                logger.info(
                    f"Atomic commit plan {plan_id}: {len(created_acquisitions)} created, "
                    f"{len(dropped_acquisitions)} dropped"
                )

                return {
                    "success": True,
                    "committed": len(created_acquisitions),
                    "dropped": len(dropped_acquisitions),
                    "acquisitions_created": created_acquisitions,
                    "acquisitions_dropped": dropped_acquisitions,
                    "orders_updated": list(updated_orders),
                }

            except Exception as e:
                # Rollback on any error
                conn.rollback()
                logger.error(f"Atomic commit failed for plan {plan_id}: {e}")
                raise

    # =========================================================================
    # Order Batch Operations (PS2.5)
    # =========================================================================

    def create_order_batch(
        self,
        workspace_id: str,
        policy_id: str,
        horizon_from: str,
        horizon_to: str,
        notes: Optional[str] = None,
    ) -> OrderBatch:
        """Create a new order batch.

        Args:
            workspace_id: Associated workspace
            policy_id: Planning policy to use
            horizon_from: Planning horizon start (ISO datetime)
            horizon_to: Planning horizon end (ISO datetime)
            notes: Optional notes

        Returns:
            Created OrderBatch object
        """
        batch_id = f"batch_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat() + "Z"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO order_batches (
                    id, workspace_id, created_at, updated_at, policy_id,
                    horizon_from, horizon_to, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    batch_id,
                    workspace_id,
                    now,
                    now,
                    policy_id,
                    horizon_from,
                    horizon_to,
                    "draft",
                    notes,
                ),
            )
            conn.commit()

        logger.info(f"Created order batch {batch_id} for workspace {workspace_id}")

        return OrderBatch(
            id=batch_id,
            workspace_id=workspace_id,
            created_at=now,
            updated_at=now,
            policy_id=policy_id,
            horizon_from=horizon_from,
            horizon_to=horizon_to,
            status="draft",
            notes=notes,
        )

    def get_order_batch(self, batch_id: str) -> Optional[OrderBatch]:
        """Get an order batch by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM order_batches WHERE id = ?", (batch_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_order_batch(row)

    def list_order_batches(
        self,
        workspace_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[OrderBatch]:
        """List order batches with optional filters.

        Args:
            workspace_id: Filter by workspace
            status: Filter by status (draft | planned | committed | cancelled)
            limit: Max results
            offset: Pagination offset

        Returns:
            List of OrderBatch objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM order_batches WHERE 1=1"
            params: List[Any] = []

            if workspace_id:
                query += " AND workspace_id = ?"
                params.append(workspace_id)
            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [self._row_to_order_batch(row) for row in cursor.fetchall()]

    def update_order_batch_status(
        self,
        batch_id: str,
        status: str,
        plan_id: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update order batch status.

        Args:
            batch_id: Batch to update
            status: New status (draft | planned | committed | cancelled)
            plan_id: Associated plan ID (for planned/committed status)
            metrics: Coverage metrics

        Returns:
            True if updated
        """
        valid_statuses = ["draft", "planned", "committed", "cancelled"]
        if status not in valid_statuses:
            raise ValueError(
                f"Invalid status: {status}. Must be one of {valid_statuses}"
            )

        now = datetime.now(timezone.utc).isoformat() + "Z"
        metrics_json = json.dumps(metrics) if metrics else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE order_batches
                SET status = ?, updated_at = ?, plan_id = COALESCE(?, plan_id),
                    metrics_json = COALESCE(?, metrics_json)
                WHERE id = ?
            """,
                (status, now, plan_id, metrics_json, batch_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def _row_to_order_batch(self, row: sqlite3.Row) -> OrderBatch:
        """Convert database row to OrderBatch object."""
        return OrderBatch(
            id=row["id"],
            workspace_id=row["workspace_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            policy_id=row["policy_id"],
            horizon_from=row["horizon_from"],
            horizon_to=row["horizon_to"],
            status=row["status"],
            plan_id=row["plan_id"],
            notes=row["notes"],
            metrics_json=row["metrics_json"],
        )

    # =========================================================================
    # Batch Member Operations (PS2.5)
    # =========================================================================

    def add_order_to_batch(
        self,
        batch_id: str,
        order_id: str,
        role: str = "primary",
    ) -> BatchMember:
        """Add an order to a batch.

        Args:
            batch_id: Batch ID
            order_id: Order ID to add
            role: Role in batch (primary | optional)

        Returns:
            Created BatchMember object
        """
        member_id = f"bm_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat() + "Z"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO batch_members (id, batch_id, order_id, role, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (member_id, batch_id, order_id, role, now),
            )

            # Update order's batch_id reference
            cursor.execute(
                "UPDATE orders SET batch_id = ?, updated_at = ? WHERE id = ?",
                (batch_id, now, order_id),
            )

            conn.commit()

        return BatchMember(
            id=member_id,
            batch_id=batch_id,
            order_id=order_id,
            role=role,
            created_at=now,
        )

    def remove_order_from_batch(self, batch_id: str, order_id: str) -> bool:
        """Remove an order from a batch.

        Args:
            batch_id: Batch ID
            order_id: Order ID to remove

        Returns:
            True if removed
        """
        now = datetime.now(timezone.utc).isoformat() + "Z"

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Remove from batch_members
            cursor.execute(
                "DELETE FROM batch_members WHERE batch_id = ? AND order_id = ?",
                (batch_id, order_id),
            )
            removed = cursor.rowcount > 0

            # Clear order's batch_id reference
            if removed:
                cursor.execute(
                    "UPDATE orders SET batch_id = NULL, updated_at = ? WHERE id = ?",
                    (now, order_id),
                )

            conn.commit()
            return removed

    def get_batch_members(self, batch_id: str) -> List[BatchMember]:
        """Get all members of a batch.

        Args:
            batch_id: Batch ID

        Returns:
            List of BatchMember objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM batch_members WHERE batch_id = ? ORDER BY created_at ASC",
                (batch_id,),
            )
            return [self._row_to_batch_member(row) for row in cursor.fetchall()]

    def get_batch_orders(self, batch_id: str) -> List[Order]:
        """Get all orders in a batch.

        Args:
            batch_id: Batch ID

        Returns:
            List of Order objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT o.* FROM orders o
                JOIN batch_members bm ON o.id = bm.order_id
                WHERE bm.batch_id = ?
                ORDER BY o.priority ASC, o.due_time ASC
            """,
                (batch_id,),
            )
            return [self._row_to_order(row) for row in cursor.fetchall()]

    def _row_to_batch_member(self, row: sqlite3.Row) -> BatchMember:
        """Convert database row to BatchMember object."""
        return BatchMember(
            id=row["id"],
            batch_id=row["batch_id"],
            order_id=row["order_id"],
            role=row["role"],
            created_at=row["created_at"],
        )

    # =========================================================================
    # Extended Order Operations (PS2.5)
    # =========================================================================

    def list_orders_inbox(
        self,
        workspace_id: str,
        status_filter: Optional[List[str]] = None,
        priority_min: Optional[int] = None,
        due_before: Optional[str] = None,
        order_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Order]:
        """List orders for inbox view with extended filters.

        Args:
            workspace_id: Workspace to query
            status_filter: Filter by statuses (default: ['new', 'queued'])
            priority_min: Minimum priority filter
            due_before: Due time filter (ISO datetime)
            order_type: Filter by order type
            tags: Filter by tags (any match)
            limit: Max results
            offset: Pagination offset

        Returns:
            List of Order objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM orders WHERE workspace_id = ?"
            params: List[Any] = [workspace_id]

            # Default to inbox statuses
            if status_filter is None:
                status_filter = ["new", "queued"]

            if status_filter:
                placeholders = ",".join("?" * len(status_filter))
                query += f" AND status IN ({placeholders})"
                params.extend(status_filter)

            if priority_min is not None:
                query += " AND priority >= ?"
                params.append(priority_min)

            if due_before:
                query += " AND due_time <= ?"
                params.append(due_before)

            if order_type:
                query += " AND order_type = ?"
                params.append(order_type)

            # Note: Tag filtering requires JSON search which SQLite handles via LIKE
            if tags:
                tag_conditions = []
                for tag in tags:
                    tag_conditions.append("tags_json LIKE ?")
                    params.append(f'%"{tag}"%')
                query += f" AND ({' OR '.join(tag_conditions)})"

            query += " ORDER BY priority ASC, due_time ASC NULLS LAST, created_at ASC"
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [self._row_to_order(row) for row in cursor.fetchall()]

    def update_order_extended(
        self,
        order_id: str,
        status: Optional[str] = None,
        due_time: Optional[str] = None,
        batch_id: Optional[str] = None,
        reject_reason: Optional[str] = None,
        user_notes: Optional[str] = None,
    ) -> bool:
        """Update order with extended fields.

        Args:
            order_id: Order to update
            status: New status
            due_time: New due time
            batch_id: New batch ID (or None to clear)
            reject_reason: Rejection reason (for rejected status)
            user_notes: User notes

        Returns:
            True if updated
        """
        now = datetime.now(timezone.utc).isoformat() + "Z"

        updates = ["updated_at = ?"]
        params: List[Any] = [now]

        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if due_time is not None:
            updates.append("due_time = ?")
            params.append(due_time)

        if batch_id is not None:
            updates.append("batch_id = ?")
            params.append(batch_id if batch_id else None)

        if reject_reason is not None:
            updates.append("reject_reason = ?")
            params.append(reject_reason)

        if user_notes is not None:
            updates.append("user_notes = ?")
            params.append(user_notes)

        params.append(order_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE orders SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()
            return cursor.rowcount > 0

    def bulk_create_orders(
        self,
        orders_data: List[Dict[str, Any]],
        workspace_id: str,
        source: str = "import",
    ) -> List[Order]:
        """Bulk create orders from a list of data dicts.

        Args:
            orders_data: List of order data dicts
            workspace_id: Workspace ID
            source: Order source

        Returns:
            List of created Order objects
        """
        created_orders: List[Order] = []
        now = datetime.now(timezone.utc).isoformat() + "Z"

        with self._get_connection() as conn:
            cursor = conn.cursor()

            for data in orders_data:
                order_id = f"ord_{uuid.uuid4().hex[:12]}"
                constraints_json = (
                    json.dumps(data.get("constraints"))
                    if data.get("constraints")
                    else None
                )
                tags_json = json.dumps(data.get("tags")) if data.get("tags") else None

                cursor.execute(
                    """
                    INSERT INTO orders (
                        id, created_at, updated_at, status, target_id, priority,
                        constraints_json, requested_window_start, requested_window_end,
                        source, notes, external_ref, workspace_id,
                        order_type, due_time, earliest_start, latest_end,
                        tags_json, requested_satellite_group, user_notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        order_id,
                        now,
                        now,
                        "new",
                        data.get("target_id", ""),
                        data.get("priority", 5),
                        constraints_json,
                        data.get("requested_window_start"),
                        data.get("requested_window_end"),
                        source,
                        data.get("notes"),
                        data.get("external_ref"),
                        workspace_id,
                        data.get("order_type", "IMAGING"),
                        data.get("due_time"),
                        data.get("earliest_start"),
                        data.get("latest_end"),
                        tags_json,
                        data.get("requested_satellite_group"),
                        data.get("user_notes"),
                    ),
                )

                created_orders.append(
                    Order(
                        id=order_id,
                        created_at=now,
                        updated_at=now,
                        status="new",
                        target_id=data.get("target_id", ""),
                        priority=data.get("priority", 5),
                        constraints_json=constraints_json,
                        requested_window_start=data.get("requested_window_start"),
                        requested_window_end=data.get("requested_window_end"),
                        source=source,
                        notes=data.get("notes"),
                        external_ref=data.get("external_ref"),
                        workspace_id=workspace_id,
                        order_type=data.get("order_type", "IMAGING"),
                        due_time=data.get("due_time"),
                        earliest_start=data.get("earliest_start"),
                        latest_end=data.get("latest_end"),
                        tags_json=tags_json,
                        requested_satellite_group=data.get("requested_satellite_group"),
                        user_notes=data.get("user_notes"),
                    )
                )

            conn.commit()

        logger.info(
            f"Bulk created {len(created_orders)} orders for workspace {workspace_id}"
        )
        return created_orders


# =============================================================================
# Global Instance
# =============================================================================

_schedule_db: Optional[ScheduleDB] = None


def get_schedule_db() -> ScheduleDB:
    """Get the global schedule database instance."""
    global _schedule_db
    if _schedule_db is None:
        _schedule_db = ScheduleDB()
    return _schedule_db


def reset_schedule_db(db_path: Optional[Path] = None) -> ScheduleDB:
    """Reset the global schedule database instance."""
    global _schedule_db
    _schedule_db = ScheduleDB(db_path)
    return _schedule_db
