"""
Orders Router for Mission Planning.

Provides endpoints for Order Inbox functionality:
- POST /api/v1/orders - Create order
- GET /api/v1/orders - List orders with filters
- GET /api/v1/orders/:id - Get single order
- PATCH /api/v1/orders/:id - Update order status
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

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
    priority: int = Field(default=3, ge=1, le=5, description="Priority 1-5")
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
    """Single order response."""

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


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=OrderCreateResponse)
async def create_order(request: CreateOrderRequest) -> OrderCreateResponse:
    """
    Create a new order (imaging request).

    An order represents the user's intent to acquire imagery of a target.
    Orders can have:
    - Priority (1-5, where 5 is highest)
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
