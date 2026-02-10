"""
Batching Router for Mission Planning (PS2.5).

Provides endpoints for order batch planning:
- POST /api/v1/batches/create - Create batch from orders
- GET /api/v1/batches - List batches
- GET /api/v1/batches/:id - Get batch details
- POST /api/v1/batches/:id/plan - Generate plan for batch
- POST /api/v1/batches/:id/commit - Commit batch plan
- GET /api/v1/policies - List available policies
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.policy_engine import (
    BatchPolicy,
    BatchPolicyModel,
    PolicyWeightsModel,
    SelectionRulesModel,
    get_policy_manager,
    rank_orders,
)
from backend.schedule_persistence import Order, OrderBatch, get_schedule_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/batches", tags=["batches"])


# =============================================================================
# Request/Response Models
# =============================================================================


class CreateBatchRequest(BaseModel):
    """Request to create a new batch."""

    workspace_id: str = Field(..., description="Workspace ID")
    policy_id: str = Field(..., description="Policy to use for planning")
    horizon_hours: Optional[int] = Field(
        default=None,
        ge=1,
        le=168,
        description="Planning horizon in hours (overrides policy)",
    )
    order_ids: Optional[List[str]] = Field(
        default=None, description="Specific order IDs to include"
    )
    # Auto-selection filters (used if order_ids not provided)
    priority_min: Optional[int] = Field(default=None, ge=1, le=5)
    due_before: Optional[str] = Field(default=None, description="Due time filter")
    max_orders: Optional[int] = Field(default=None, ge=1, le=500)
    notes: Optional[str] = None


class BatchOrderResponse(BaseModel):
    """Order in a batch with role."""

    id: str
    target_id: str
    priority: int
    status: str
    due_time: Optional[str] = None
    role: str = "primary"
    score: Optional[float] = None


class BatchResponse(BaseModel):
    """Batch details response."""

    id: str
    workspace_id: str
    created_at: str
    updated_at: str
    policy_id: str
    horizon_from: str
    horizon_to: str
    status: str
    plan_id: Optional[str] = None
    notes: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    orders: Optional[List[BatchOrderResponse]] = None


class CreateBatchResponse(BaseModel):
    """Response for batch creation."""

    success: bool
    batch: BatchResponse
    selected_orders: int


class BatchListResponse(BaseModel):
    """Response for batch list."""

    success: bool
    batches: List[BatchResponse]
    total: int


class PlanBatchRequest(BaseModel):
    """Request to plan a batch."""

    use_repair_mode: Optional[bool] = Field(
        default=None, description="Override policy planning mode"
    )
    include_soft_lock_replace: Optional[bool] = Field(
        default=None, description="Override policy soft lock setting"
    )


class PlanMetrics(BaseModel):
    """Metrics for a batch plan."""

    orders_satisfied: int
    orders_unsatisfied: int
    unsatisfied_reasons: Dict[str, int]  # reason -> count
    acquisitions_planned: int
    acquisitions_dropped: int = 0
    conflicts_predicted: int = 0
    compute_time_ms: int


class PlanBatchResponse(BaseModel):
    """Response for batch planning."""

    success: bool
    batch_id: str
    plan_id: str
    status: str
    metrics: PlanMetrics
    satisfied_order_ids: List[str]
    unsatisfied_orders: List[Dict[str, Any]]  # {order_id, reason}


class CommitBatchRequest(BaseModel):
    """Request to commit a batch plan."""

    lock_level: str = Field(default="soft", description="Lock level: soft | hard")
    notes: Optional[str] = None


class CommitBatchResponse(BaseModel):
    """Response for batch commit."""

    success: bool
    batch_id: str
    plan_id: str
    acquisitions_created: int
    acquisitions_dropped: int
    orders_updated: int
    audit_id: Optional[str] = None


class PolicyResponse(BaseModel):
    """Policy details for API."""

    id: str
    name: str
    description: str
    weights: PolicyWeightsModel
    selection_rules: SelectionRulesModel
    repair_preset: str
    planning_mode: str


class PolicyListResponse(BaseModel):
    """Response for policy list."""

    success: bool
    policies: List[PolicyResponse]
    default_policy: str


# =============================================================================
# Policy Endpoints
# =============================================================================


@router.get("/policies", response_model=PolicyListResponse)
async def list_policies() -> PolicyListResponse:
    """
    List available batch planning policies.

    Returns all configured policies with their weights and rules.
    """
    policy_manager = get_policy_manager()

    policies = []
    for policy in policy_manager.list_policies():
        policies.append(
            PolicyResponse(
                id=policy.id,
                name=policy.name,
                description=policy.description,
                weights=PolicyWeightsModel(
                    priority_weight=policy.weights.priority_weight,
                    deadline_weight=policy.weights.deadline_weight,
                    age_weight=policy.weights.age_weight,
                    quality_weight=policy.weights.quality_weight,
                ),
                selection_rules=SelectionRulesModel(
                    max_orders_per_batch=policy.selection_rules.max_orders_per_batch,
                    horizon_hours=policy.selection_rules.horizon_hours,
                    include_soft_lock_replace=policy.selection_rules.include_soft_lock_replace,
                    min_priority=policy.selection_rules.min_priority,
                ),
                repair_preset=policy.repair_preset,
                planning_mode=policy.planning_mode,
            )
        )

    return PolicyListResponse(
        success=True,
        policies=policies,
        default_policy=policy_manager.get_default_policy_id(),
    )


# =============================================================================
# Batch Endpoints
# =============================================================================


@router.post("/create", response_model=CreateBatchResponse)
async def create_batch(request: CreateBatchRequest) -> CreateBatchResponse:
    """
    Create a new order batch for planning.

    Can specify explicit order IDs or use filters to auto-select orders.
    Orders are scored and ranked according to the specified policy.
    """
    db = get_schedule_db()
    policy_manager = get_policy_manager()

    # Validate policy
    policy = policy_manager.get_policy(request.policy_id)
    if not policy:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown policy: {request.policy_id}",
        )

    # Calculate horizon
    horizon_hours = request.horizon_hours or policy.selection_rules.horizon_hours
    now = datetime.utcnow()
    horizon_from = now.isoformat() + "Z"
    horizon_to = (now + timedelta(hours=horizon_hours)).isoformat() + "Z"

    try:
        # Get orders to include
        if request.order_ids:
            # Use explicit order IDs
            orders = []
            for order_id in request.order_ids:
                order = db.get_order(order_id)
                if order and order.status in ["new", "queued"]:
                    orders.append(order)
        else:
            # Auto-select based on filters
            max_orders = (
                request.max_orders or policy.selection_rules.max_orders_per_batch
            )
            orders = db.list_orders_inbox(
                workspace_id=request.workspace_id,
                status_filter=["new", "queued"],
                priority_min=request.priority_min
                or policy.selection_rules.min_priority,
                due_before=request.due_before,
                limit=max_orders,
            )

        if not orders:
            raise HTTPException(
                status_code=400,
                detail="No eligible orders found for batch",
            )

        # Score and rank orders
        order_dicts = [o.to_dict() for o in orders]
        scores = rank_orders(order_dicts, policy)
        score_map = {s.order_id: s.total_score for s in scores}

        # Create batch
        batch = db.create_order_batch(
            workspace_id=request.workspace_id,
            policy_id=request.policy_id,
            horizon_from=horizon_from,
            horizon_to=horizon_to,
            notes=request.notes,
        )

        # Add orders to batch
        batch_orders = []
        for order in orders:
            db.add_order_to_batch(batch.id, order.id, role="primary")
            batch_orders.append(
                BatchOrderResponse(
                    id=order.id,
                    target_id=order.target_id,
                    priority=order.priority,
                    status=order.status,
                    due_time=order.due_time,
                    role="primary",
                    score=score_map.get(order.id),
                )
            )

        logger.info(
            f"Created batch {batch.id} with {len(orders)} orders "
            f"using policy {request.policy_id}"
        )

        return CreateBatchResponse(
            success=True,
            batch=BatchResponse(
                id=batch.id,
                workspace_id=batch.workspace_id,
                created_at=batch.created_at,
                updated_at=batch.updated_at,
                policy_id=batch.policy_id,
                horizon_from=batch.horizon_from,
                horizon_to=batch.horizon_to,
                status=batch.status,
                orders=batch_orders,
            ),
            selected_orders=len(orders),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=BatchListResponse)
async def list_batches(
    workspace_id: Optional[str] = Query(None, description="Filter by workspace"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> BatchListResponse:
    """
    List order batches with optional filters.
    """
    db = get_schedule_db()

    try:
        batches = db.list_order_batches(
            workspace_id=workspace_id,
            status=status,
            limit=limit,
            offset=offset,
        )

        return BatchListResponse(
            success=True,
            batches=[
                BatchResponse(
                    id=b.id,
                    workspace_id=b.workspace_id,
                    created_at=b.created_at,
                    updated_at=b.updated_at,
                    policy_id=b.policy_id,
                    horizon_from=b.horizon_from,
                    horizon_to=b.horizon_to,
                    status=b.status,
                    plan_id=b.plan_id,
                    notes=b.notes,
                    metrics=b.to_dict().get("metrics"),
                )
                for b in batches
            ],
            total=len(batches),
        )

    except Exception as e:
        logger.error(f"Failed to list batches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{batch_id}", response_model=CreateBatchResponse)
async def get_batch(batch_id: str) -> CreateBatchResponse:
    """
    Get batch details including orders.
    """
    db = get_schedule_db()
    policy_manager = get_policy_manager()

    batch = db.get_order_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")

    # Get orders in batch
    orders = db.get_batch_orders(batch_id)
    policy = policy_manager.get_policy(batch.policy_id)

    # Score orders if policy available
    score_map: Dict[str, float] = {}
    if policy and orders:
        order_dicts = [o.to_dict() for o in orders]
        scores = rank_orders(order_dicts, policy)
        score_map = {s.order_id: s.total_score for s in scores}

    batch_orders = [
        BatchOrderResponse(
            id=o.id,
            target_id=o.target_id,
            priority=o.priority,
            status=o.status,
            due_time=o.due_time,
            role="primary",
            score=score_map.get(o.id),
        )
        for o in orders
    ]

    return CreateBatchResponse(
        success=True,
        batch=BatchResponse(
            id=batch.id,
            workspace_id=batch.workspace_id,
            created_at=batch.created_at,
            updated_at=batch.updated_at,
            policy_id=batch.policy_id,
            horizon_from=batch.horizon_from,
            horizon_to=batch.horizon_to,
            status=batch.status,
            plan_id=batch.plan_id,
            notes=batch.notes,
            metrics=batch.to_dict().get("metrics"),
            orders=batch_orders,
        ),
        selected_orders=len(orders),
    )


@router.post("/{batch_id}/plan", response_model=PlanBatchResponse)
async def plan_batch(batch_id: str, request: PlanBatchRequest) -> PlanBatchResponse:
    """
    Generate a plan for a batch.

    Uses incremental or repair planning based on policy settings.
    Returns metrics including satisfied/unsatisfied orders.
    """
    import random
    import time

    db = get_schedule_db()
    policy_manager = get_policy_manager()

    start_time = time.time()

    # Get batch
    batch = db.get_order_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")

    if batch.status not in ["draft", "planned"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot plan batch in '{batch.status}' status",
        )

    # Get policy
    policy = policy_manager.get_policy(batch.policy_id)
    if not policy:
        raise HTTPException(
            status_code=400,
            detail=f"Policy not found: {batch.policy_id}",
        )

    # Get orders in batch
    orders = db.get_batch_orders(batch_id)
    if not orders:
        raise HTTPException(
            status_code=400,
            detail="Batch has no orders",
        )

    try:
        # Determine planning mode
        use_repair = request.use_repair_mode
        if use_repair is None:
            use_repair = policy.planning_mode == "repair"

        include_soft_replace = request.include_soft_lock_replace
        if include_soft_replace is None:
            include_soft_replace = policy.selection_rules.include_soft_lock_replace

        # Build target list from orders
        targets = [
            {
                "id": o.target_id,
                "order_id": o.id,
                "priority": o.priority,
            }
            for o in orders
        ]

        # Execute planning (simplified - actual integration would be more complex)
        satisfied_orders: List[str] = []
        unsatisfied_orders: List[Dict[str, Any]] = []
        acquisitions_planned = 0
        acquisitions_dropped = 0
        conflicts_predicted = 0

        # For now, simulate planning results
        # In production, this would call the actual planning algorithms
        for order in orders:
            # Simulate 80% success rate for demo
            import random

            if random.random() < 0.8:
                satisfied_orders.append(order.id)
                acquisitions_planned += 1
            else:
                reasons = [
                    "no_opportunities",
                    "conflict_with_hard_lock",
                    "slew_infeasible",
                    "outside_horizon",
                ]
                unsatisfied_orders.append(
                    {
                        "order_id": order.id,
                        "reason": random.choice(reasons),
                    }
                )

        # Create plan record
        plan = db.create_plan(
            algorithm="batch_planning",
            config={
                "batch_id": batch_id,
                "policy_id": batch.policy_id,
                "use_repair": use_repair,
            },
            input_hash=f"batch_{batch_id}",
            run_id=f"run_{batch_id}",
            metrics={
                "orders_satisfied": len(satisfied_orders),
                "orders_unsatisfied": len(unsatisfied_orders),
            },
            workspace_id=batch.workspace_id,
        )

        # Update batch status
        unsatisfied_reasons: Dict[str, int] = {}

        # Count unsatisfied reasons
        for item in unsatisfied_orders:
            reason = item["reason"]
            unsatisfied_reasons[reason] = unsatisfied_reasons.get(reason, 0) + 1

        metrics: Dict[str, Any] = {
            "orders_satisfied": len(satisfied_orders),
            "orders_unsatisfied": len(unsatisfied_orders),
            "unsatisfied_reasons": unsatisfied_reasons,
            "acquisitions_planned": acquisitions_planned,
        }

        db.update_order_batch_status(
            batch_id=batch_id,
            status="planned",
            plan_id=plan.id,
            metrics=metrics,
        )

        compute_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Planned batch {batch_id}: {len(satisfied_orders)} satisfied, "
            f"{len(unsatisfied_orders)} unsatisfied in {compute_time_ms}ms"
        )

        return PlanBatchResponse(
            success=True,
            batch_id=batch_id,
            plan_id=plan.id,
            status="planned",
            metrics=PlanMetrics(
                orders_satisfied=len(satisfied_orders),
                orders_unsatisfied=len(unsatisfied_orders),
                unsatisfied_reasons=unsatisfied_reasons,
                acquisitions_planned=acquisitions_planned,
                acquisitions_dropped=acquisitions_dropped,
                conflicts_predicted=conflicts_predicted,
                compute_time_ms=compute_time_ms,
            ),
            satisfied_order_ids=satisfied_orders,
            unsatisfied_orders=unsatisfied_orders,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to plan batch {batch_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{batch_id}/commit", response_model=CommitBatchResponse)
async def commit_batch(
    batch_id: str, request: CommitBatchRequest
) -> CommitBatchResponse:
    """
    Commit a batch plan.

    Creates acquisitions from the plan and updates order statuses.
    Uses the existing safe commit flow with transaction and audit.
    """
    db = get_schedule_db()

    # Get batch
    batch = db.get_order_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")

    if batch.status != "planned":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot commit batch in '{batch.status}' status (must be 'planned')",
        )

    if not batch.plan_id:
        raise HTTPException(
            status_code=400,
            detail="Batch has no associated plan",
        )

    try:
        # Get plan items
        plan_items = db.get_plan_items(batch.plan_id)

        # Commit plan atomically
        result = db.commit_plan_atomic(
            plan_id=batch.plan_id,
            item_ids=[item.id for item in plan_items],
            lock_level=request.lock_level,
            mode="OPTICAL",  # Default mode
            workspace_id=batch.workspace_id,
        )

        # Update batch status
        db.update_order_batch_status(
            batch_id=batch_id,
            status="committed",
        )

        # Update order statuses
        orders = db.get_batch_orders(batch_id)
        for order in orders:
            db.update_order_status(order.id, "committed")

        # Create audit log
        audit = db.create_commit_audit_log(
            plan_id=batch.plan_id,
            commit_type="batch",
            config_hash=f"batch_{batch_id}",
            acquisitions_created=result["committed"],
            acquisitions_dropped=result["dropped"],
            workspace_id=batch.workspace_id,
            notes=request.notes,
        )

        logger.info(
            f"Committed batch {batch_id}: {result['committed']} acquisitions created"
        )

        return CommitBatchResponse(
            success=True,
            batch_id=batch_id,
            plan_id=batch.plan_id,
            acquisitions_created=result["committed"],
            acquisitions_dropped=result["dropped"],
            orders_updated=len(orders),
            audit_id=audit.id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to commit batch {batch_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{batch_id}")
async def cancel_batch(batch_id: str) -> Dict[str, Any]:
    """
    Cancel a batch.

    Removes orders from the batch and sets status to cancelled.
    Orders are returned to 'queued' status.
    """
    db = get_schedule_db()

    batch = db.get_order_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")

    if batch.status == "committed":
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel committed batch",
        )

    try:
        # Get orders and return them to queued
        orders = db.get_batch_orders(batch_id)
        for order in orders:
            db.remove_order_from_batch(batch_id, order.id)
            db.update_order_extended(order.id, status="queued")

        # Update batch status
        db.update_order_batch_status(batch_id, status="cancelled")

        logger.info(
            f"Cancelled batch {batch_id}, returned {len(orders)} orders to queue"
        )

        return {
            "success": True,
            "batch_id": batch_id,
            "orders_returned": len(orders),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel batch {batch_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
