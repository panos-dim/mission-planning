"""
Orders Router for Mission Planning (PS2.5).

Provides endpoints for Order Inbox automation:
- POST /api/v1/orders - Create order
- POST /api/v1/orders/import - Bulk import orders
- GET /api/v1/orders - List orders with filters
- GET /api/v1/orders/inbox - Inbox view with extended filters
- GET /api/v1/orders/:id - Get single order
- PATCH /api/v1/orders/:id - Update order status
- POST /api/v1/orders/:id/reject - Reject order with reason
- POST /api/v1/orders/:id/defer - Defer order (push due_time)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.policy_engine import get_policy_manager, rank_orders
from backend.schedule_persistence import get_schedule_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


# =============================================================================
# Request/Response Models
# =============================================================================


class OrderConstraints(BaseModel):
    """Order constraints."""

    max_incidence_deg: Optional[float] = None
    preferred_satellite: Optional[str] = None
    look_side: Optional[str] = None  # LEFT | RIGHT | ANY
    pass_direction: Optional[str] = None  # ASCENDING | DESCENDING | ANY


class CreateOrderRequest(BaseModel):
    """Request to create a new order."""

    target_id: str = Field(..., description="Target to image")
    priority: int = Field(
        default=5, ge=1, le=5, description="Priority 1=best, 5=lowest"
    )
    constraints: Optional[OrderConstraints] = None
    requested_window_start: Optional[str] = Field(
        default=None, description="Start of requested window (ISO datetime)"
    )
    requested_window_end: Optional[str] = Field(
        default=None, description="End of requested window (ISO datetime)"
    )
    notes: Optional[str] = None
    external_ref: Optional[str] = Field(
        default=None, description="External reference ID"
    )
    workspace_id: Optional[str] = Field(
        default=None, description="Associated workspace ID"
    )


class UpdateOrderRequest(BaseModel):
    """Request to update an order (status only for now)."""

    status: str = Field(
        ...,
        description="New status: new | planned | committed | cancelled | completed",
    )


class OrderResponse(BaseModel):
    """Single order response with extended PS2.5 fields."""

    id: str
    created_at: str
    updated_at: str
    status: str
    target_id: str
    priority: int
    constraints: Optional[Dict[str, Any]] = None
    requested_window: Optional[Dict[str, Optional[str]]] = None
    source: str
    notes: Optional[str] = None
    external_ref: Optional[str] = None
    workspace_id: Optional[str] = None
    # Extended PS2.5 fields
    order_type: str = "IMAGING"
    due_time: Optional[str] = None
    earliest_start: Optional[str] = None
    latest_end: Optional[str] = None
    batch_id: Optional[str] = None
    tags: Optional[List[str]] = None
    requested_satellite_group: Optional[str] = None
    user_notes: Optional[str] = None
    reject_reason: Optional[str] = None


class OrderListResponse(BaseModel):
    """Response for order list endpoint."""

    success: bool
    orders: List[OrderResponse]
    total: int


class OrderCreateResponse(BaseModel):
    """Response for order creation."""

    success: bool
    order: OrderResponse


class OrderUpdateResponse(BaseModel):
    """Response for order update."""

    success: bool
    message: str
    order: Optional[OrderResponse] = None


# PS2.5 Extended Models


class ExtendedCreateOrderRequest(BaseModel):
    """Extended request to create a new order with PS2.5 fields."""

    target_id: str = Field(..., description="Target to image")
    priority: int = Field(
        default=5, ge=1, le=5, description="Priority 1=best, 5=lowest"
    )
    constraints: Optional[OrderConstraints] = None
    requested_window_start: Optional[str] = Field(
        default=None, description="Start of requested window (ISO datetime)"
    )
    requested_window_end: Optional[str] = Field(
        default=None, description="End of requested window (ISO datetime)"
    )
    notes: Optional[str] = None
    external_ref: Optional[str] = Field(
        default=None, description="External reference ID"
    )
    workspace_id: Optional[str] = Field(
        default=None, description="Associated workspace ID"
    )
    # Extended PS2.5 fields
    order_type: str = Field(
        default="IMAGING", description="IMAGING | DOWNLINK | MAINTENANCE"
    )
    due_time: Optional[str] = Field(
        default=None, description="SLA deadline (ISO datetime)"
    )
    earliest_start: Optional[str] = Field(
        default=None, description="Earliest start constraint"
    )
    latest_end: Optional[str] = Field(default=None, description="Latest end constraint")
    tags: Optional[List[str]] = Field(default=None, description="Order tags")
    requested_satellite_group: Optional[str] = Field(
        default=None, description="Preferred satellite group"
    )
    user_notes: Optional[str] = Field(default=None, description="User-provided notes")


class ImportOrderItem(BaseModel):
    """Single order item for bulk import."""

    target_id: str
    priority: int = Field(default=5, ge=1, le=5)
    constraints: Optional[Dict[str, Any]] = None
    requested_window_start: Optional[str] = None
    requested_window_end: Optional[str] = None
    external_ref: Optional[str] = None
    order_type: str = "IMAGING"
    due_time: Optional[str] = None
    earliest_start: Optional[str] = None
    latest_end: Optional[str] = None
    tags: Optional[List[str]] = None
    requested_satellite_group: Optional[str] = None
    user_notes: Optional[str] = None


class ImportOrdersRequest(BaseModel):
    """Request to bulk import orders."""

    orders: List[ImportOrderItem] = Field(..., min_length=1, max_length=500)
    workspace_id: str = Field(..., description="Target workspace ID")


class ImportOrdersResponse(BaseModel):
    """Response for bulk import."""

    success: bool
    imported_count: int
    orders: List[OrderResponse]


class InboxOrderResponse(BaseModel):
    """Order with score for inbox view."""

    order: OrderResponse
    score: float
    score_breakdown: Dict[str, float]


class InboxListResponse(BaseModel):
    """Response for inbox endpoint."""

    success: bool
    orders: List[InboxOrderResponse]
    total: int
    policy_id: str


class RejectOrderRequest(BaseModel):
    """Request to reject an order."""

    reason: str = Field(
        ..., min_length=1, max_length=500, description="Rejection reason"
    )


class DeferOrderRequest(BaseModel):
    """Request to defer an order."""

    new_due_time: Optional[str] = Field(
        default=None, description="New due time (ISO datetime)"
    )
    defer_hours: Optional[int] = Field(
        default=None, ge=1, le=168, description="Hours to defer by"
    )
    notes: Optional[str] = Field(default=None, description="Deferral notes")


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=OrderCreateResponse)
async def create_order(request: CreateOrderRequest) -> OrderCreateResponse:
    """
    Create a new order (imaging request).

    An order represents the user's intent to acquire imagery of a target.
    Orders can have:
    - Priority (1-5, where 1 is best/highest importance)
    - Constraints (max incidence, preferred satellite, etc.)
    - Requested time window

    The order starts in 'new' status and progresses through:
    new → planned → committed → completed
    """
    db = get_schedule_db()

    try:
        constraints_dict = (
            request.constraints.model_dump() if request.constraints else None
        )

        order = db.create_order(
            target_id=request.target_id,
            priority=request.priority,
            constraints=constraints_dict,
            requested_window_start=request.requested_window_start,
            requested_window_end=request.requested_window_end,
            source="manual",
            notes=request.notes,
            external_ref=request.external_ref,
            workspace_id=request.workspace_id,
        )

        logger.info(f"Created order {order.id} for target {request.target_id}")

        return OrderCreateResponse(
            success=True,
            order=OrderResponse(**order.to_dict()),
        )

    except Exception as e:
        logger.error(f"Failed to create order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=OrderListResponse)
async def list_orders(
    status: Optional[str] = Query(
        None,
        description="Filter by status: new | planned | committed | cancelled | completed",
    ),
    workspace_id: Optional[str] = Query(None, description="Filter by workspace ID"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> OrderListResponse:
    """
    List orders with optional filters.

    Supports filtering by:
    - status: Order lifecycle state
    - workspace_id: Associated workspace

    Returns orders sorted by creation time (newest first).
    """
    db = get_schedule_db()

    # Validate status if provided
    if status:
        valid_statuses = ["new", "planned", "committed", "cancelled", "completed"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Must be one of {valid_statuses}",
            )

    try:
        orders = db.list_orders(
            workspace_id=workspace_id,
            status=status,
            limit=limit,
            offset=offset,
        )

        return OrderListResponse(
            success=True,
            orders=[OrderResponse(**o.to_dict()) for o in orders],
            total=len(orders),
        )

    except Exception as e:
        logger.error(f"Failed to list orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# NOTE: /inbox must be defined BEFORE /{order_id} to avoid route conflicts
@router.get("/inbox", response_model=InboxListResponse)
async def get_inbox(
    workspace_id: str = Query(..., description="Workspace ID"),
    priority_min: Optional[int] = Query(
        None, ge=1, le=5, description="Minimum priority"
    ),
    due_within_hours: Optional[int] = Query(
        None, ge=1, le=168, description="Due within N hours"
    ),
    order_type: Optional[str] = Query(None, description="Filter by order type"),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter"),
    policy_id: Optional[str] = Query(None, description="Policy to use for scoring"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> InboxListResponse:
    """
    Get orders inbox with scoring and extended filters.

    Returns orders in 'new' or 'queued' status, scored and ranked
    according to the specified policy (or default policy).

    Supports filtering by:
    - priority_min: Minimum priority level
    - due_within_hours: Orders due within N hours
    - order_type: IMAGING | DOWNLINK | MAINTENANCE
    - tags: Comma-separated list of tags (any match)
    """
    db = get_schedule_db()
    policy_manager = get_policy_manager()

    # Get policy
    if policy_id:
        policy = policy_manager.get_policy(policy_id)
        if not policy:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown policy: {policy_id}",
            )
    else:
        policy = policy_manager.get_default_policy()
        policy_id = policy_manager.get_default_policy_id()

    # Calculate due_before if due_within_hours specified
    due_before = None
    if due_within_hours:
        due_before = (
            datetime.now(timezone.utc) + timedelta(hours=due_within_hours)
        ).isoformat() + "Z"

    # Parse tags
    tag_list = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    try:
        orders = db.list_orders_inbox(
            workspace_id=workspace_id,
            status_filter=["new", "queued"],
            priority_min=priority_min,
            due_before=due_before,
            order_type=order_type,
            tags=tag_list,
            limit=limit,
            offset=offset,
        )

        # Score and rank orders
        order_dicts = [o.to_dict() for o in orders]
        scores = rank_orders(order_dicts, policy)

        # Build response with scores
        inbox_orders = []
        score_map = {s.order_id: s for s in scores}
        for order in orders:
            score = score_map.get(order.id)
            inbox_orders.append(
                InboxOrderResponse(
                    order=OrderResponse(**order.to_dict()),
                    score=score.total_score if score else 0.0,
                    score_breakdown=score.breakdown if score else {},
                )
            )

        # Sort by score descending
        inbox_orders.sort(key=lambda x: x.score, reverse=True)

        return InboxListResponse(
            success=True,
            orders=inbox_orders,
            total=len(inbox_orders),
            policy_id=policy_id,
        )

    except Exception as e:
        logger.error(f"Failed to get inbox: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{order_id}", response_model=OrderCreateResponse)
async def get_order(order_id: str) -> OrderCreateResponse:
    """
    Get a single order by ID.
    """
    db = get_schedule_db()

    order = db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")

    return OrderCreateResponse(
        success=True,
        order=OrderResponse(**order.to_dict()),
    )


@router.patch("/{order_id}", response_model=OrderUpdateResponse)
async def update_order(
    order_id: str, request: UpdateOrderRequest
) -> OrderUpdateResponse:
    """
    Update an order (status changes only for now).

    Valid status transitions:
    - new → planned (when included in a plan)
    - planned → committed (when plan is committed)
    - any → cancelled (manual cancellation)
    - committed → completed (after execution)
    """
    db = get_schedule_db()

    # Check order exists
    existing = db.get_order(order_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")

    try:
        success = db.update_order_status(order_id, request.status)

        if success:
            updated = db.get_order(order_id)
            return OrderUpdateResponse(
                success=True,
                message=f"Order status updated to '{request.status}'",
                order=OrderResponse(**updated.to_dict()) if updated else None,
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to update order")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class OrderDeleteResponse(BaseModel):
    """Response for order deletion."""

    success: bool
    message: str
    order_deleted: bool
    acquisitions_deleted: int


@router.delete("/{order_id}", response_model=OrderDeleteResponse)
async def delete_order(
    order_id: str,
    cascade_acquisitions: bool = Query(
        True, description="Also delete acquisitions linked to this order"
    ),
) -> OrderDeleteResponse:
    """
    Delete an order and optionally its associated acquisitions.

    This permanently removes the order from the database.
    If cascade_acquisitions is True (default), all acquisitions linked
    to this order are also deleted.

    Hard-locked acquisitions linked to the order will also be deleted
    when cascade is enabled.
    """
    db = get_schedule_db()

    # Check order exists
    existing = db.get_order(order_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")

    try:
        result = db.delete_order(
            order_id=order_id,
            cascade_acquisitions=cascade_acquisitions,
        )

        if result["order_deleted"]:
            logger.info(
                f"Deleted order {order_id} "
                f"(acquisitions_deleted={result['acquisitions_deleted']})"
            )
            return OrderDeleteResponse(
                success=True,
                message=f"Order {order_id} deleted"
                + (
                    f" ({result['acquisitions_deleted']} acquisitions removed)"
                    if result["acquisitions_deleted"] > 0
                    else ""
                ),
                order_deleted=True,
                acquisitions_deleted=result["acquisitions_deleted"],
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to delete order")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PS2.5 Endpoints - Order Inbox Automation
# =============================================================================


@router.post("/import", response_model=ImportOrdersResponse)
async def import_orders(request: ImportOrdersRequest) -> ImportOrdersResponse:
    """
    Bulk import orders from targets/opportunities selection.

    Creates multiple orders at once from an external source or batch selection.
    All orders are created with 'new' status and 'import' source.
    """
    db = get_schedule_db()

    try:
        orders_data = [
            {
                "target_id": item.target_id,
                "priority": item.priority,
                "constraints": item.constraints,
                "requested_window_start": item.requested_window_start,
                "requested_window_end": item.requested_window_end,
                "external_ref": item.external_ref,
                "order_type": item.order_type,
                "due_time": item.due_time,
                "earliest_start": item.earliest_start,
                "latest_end": item.latest_end,
                "tags": item.tags,
                "requested_satellite_group": item.requested_satellite_group,
                "user_notes": item.user_notes,
            }
            for item in request.orders
        ]

        created_orders = db.bulk_create_orders(
            orders_data=orders_data,
            workspace_id=request.workspace_id,
            source="import",
        )

        logger.info(
            f"Imported {len(created_orders)} orders to workspace {request.workspace_id}"
        )

        return ImportOrdersResponse(
            success=True,
            imported_count=len(created_orders),
            orders=[OrderResponse(**o.to_dict()) for o in created_orders],
        )

    except Exception as e:
        logger.error(f"Failed to import orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{order_id}/reject", response_model=OrderUpdateResponse)
async def reject_order(
    order_id: str, request: RejectOrderRequest
) -> OrderUpdateResponse:
    """
    Reject an order with a reason.

    Sets the order status to 'rejected' and records the rejection reason.
    Rejected orders will not be included in future batches.
    """
    db = get_schedule_db()

    # Check order exists
    existing = db.get_order(order_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")

    # Validate current status
    if existing.status in ["committed", "completed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject order in '{existing.status}' status",
        )

    try:
        success = db.update_order_extended(
            order_id=order_id,
            status="rejected",
            reject_reason=request.reason,
        )

        if success:
            updated = db.get_order(order_id)
            logger.info(f"Rejected order {order_id}: {request.reason}")
            return OrderUpdateResponse(
                success=True,
                message=f"Order rejected: {request.reason}",
                order=OrderResponse(**updated.to_dict()) if updated else None,
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to reject order")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reject order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{order_id}/defer", response_model=OrderUpdateResponse)
async def defer_order(order_id: str, request: DeferOrderRequest) -> OrderUpdateResponse:
    """
    Defer an order by pushing its due time.

    Can specify either:
    - new_due_time: Explicit new due time
    - defer_hours: Hours to add to current due time (or now if no due time)

    The order status is set back to 'queued' if it was in a batch.
    """
    db = get_schedule_db()

    # Check order exists
    existing = db.get_order(order_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")

    # Validate current status
    if existing.status in ["committed", "completed", "rejected"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot defer order in '{existing.status}' status",
        )

    # Calculate new due time
    if request.new_due_time:
        new_due_time = request.new_due_time
    elif request.defer_hours:
        base_time = datetime.now(timezone.utc)
        if existing.due_time:
            try:
                base_time = datetime.fromisoformat(
                    existing.due_time.replace("Z", "+00:00")
                )
                if base_time.tzinfo:
                    base_time = base_time.replace(tzinfo=None)
            except ValueError:
                pass
        new_due_time = (
            base_time + timedelta(hours=request.defer_hours)
        ).isoformat() + "Z"
    else:
        raise HTTPException(
            status_code=400,
            detail="Must specify either new_due_time or defer_hours",
        )

    try:
        # Update due time and optionally add notes
        user_notes = existing.user_notes or ""
        if request.notes:
            defer_note = f"[Deferred] {request.notes}"
            user_notes = f"{user_notes}\n{defer_note}" if user_notes else defer_note

        success = db.update_order_extended(
            order_id=order_id,
            status="queued",  # Move back to queued
            due_time=new_due_time,
            user_notes=user_notes.strip() if user_notes else None,
        )

        if success:
            updated = db.get_order(order_id)
            logger.info(f"Deferred order {order_id} to {new_due_time}")
            return OrderUpdateResponse(
                success=True,
                message=f"Order deferred to {new_due_time}",
                order=OrderResponse(**updated.to_dict()) if updated else None,
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to defer order")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to defer order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
