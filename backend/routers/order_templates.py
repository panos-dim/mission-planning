"""Recurring order-template CRUD routes."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.schedule_persistence import get_schedule_db
from backend.schemas.order_templates import (
    CreateOrderTemplateRequest,
    OrderTemplateCreateResponse,
    OrderTemplateDeleteResponse,
    OrderTemplateFields,
    OrderTemplateListResponse,
    OrderTemplateResponse,
    UpdateOrderTemplateRequest,
)
from mission_planner.utils import update_log_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/order-templates", tags=["order-templates"])


def _bind_order_template_log_context(
    workspace_id: Optional[str] = None,
    template_id: Optional[str] = None,
    **extra: Any,
) -> None:
    """Attach template-scoped context to the current request logs."""
    context: Dict[str, Any] = dict(extra)
    if workspace_id:
        context["workspace_id"] = workspace_id
    if template_id:
        context["template_id"] = template_id
    if context:
        update_log_context(**context)


@router.post("", response_model=OrderTemplateCreateResponse)
async def create_order_template(
    request: CreateOrderTemplateRequest,
) -> OrderTemplateCreateResponse:
    """Create a recurring order template."""
    db = get_schedule_db()
    _bind_order_template_log_context(workspace_id=request.workspace_id)

    try:
        template = db.create_order_template(**request.model_dump())
        _bind_order_template_log_context(
            workspace_id=template.workspace_id,
            template_id=template.id,
        )
        return OrderTemplateCreateResponse(
            success=True,
            template=OrderTemplateResponse(**template.to_dict()),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Failed to create order template: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("", response_model=OrderTemplateListResponse)
async def list_order_templates(
    workspace_id: Optional[str] = Query(None, description="Filter by workspace ID"),
    status: Optional[str] = Query(
        None, description="Filter by status: active | paused | ended"
    ),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> OrderTemplateListResponse:
    """List recurring order templates."""
    db = get_schedule_db()
    _bind_order_template_log_context(workspace_id=workspace_id)

    try:
        templates = db.list_order_templates(
            workspace_id=workspace_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return OrderTemplateListResponse(
            success=True,
            templates=[OrderTemplateResponse(**template.to_dict()) for template in templates],
            total=len(templates),
        )
    except Exception as exc:
        logger.error("Failed to list order templates: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{template_id}", response_model=OrderTemplateCreateResponse)
async def get_order_template(template_id: str) -> OrderTemplateCreateResponse:
    """Get a single recurring order template."""
    db = get_schedule_db()
    _bind_order_template_log_context(template_id=template_id)

    template = db.get_order_template(template_id)
    if not template:
        raise HTTPException(
            status_code=404,
            detail=f"Order template not found: {template_id}",
        )

    _bind_order_template_log_context(
        workspace_id=template.workspace_id,
        template_id=template_id,
    )
    return OrderTemplateCreateResponse(
        success=True,
        template=OrderTemplateResponse(**template.to_dict()),
    )


@router.patch("/{template_id}", response_model=OrderTemplateCreateResponse)
async def patch_order_template(
    template_id: str,
    request: UpdateOrderTemplateRequest,
) -> OrderTemplateCreateResponse:
    """Patch a recurring order template."""
    db = get_schedule_db()
    _bind_order_template_log_context(template_id=template_id)

    current = db.get_order_template(template_id)
    if not current:
        raise HTTPException(
            status_code=404,
            detail=f"Order template not found: {template_id}",
        )

    _bind_order_template_log_context(
        workspace_id=current.workspace_id,
        template_id=template_id,
    )

    try:
        current_data = current.to_dict()
        merged_payload = {
            field_name: current_data[field_name]
            for field_name in OrderTemplateFields.model_fields
        }
        merged_payload.update(request.model_dump(exclude_unset=True))
        validated = OrderTemplateFields(**merged_payload)

        updated = db.replace_order_template(
            template_id,
            **validated.model_dump(),
        )
        if not updated:
            raise HTTPException(
                status_code=404,
                detail=f"Order template not found: {template_id}",
            )

        return OrderTemplateCreateResponse(
            success=True,
            template=OrderTemplateResponse(**updated.to_dict()),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to patch order template %s: %s", template_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{template_id}", response_model=OrderTemplateDeleteResponse)
async def delete_order_template(
    template_id: str,
) -> OrderTemplateDeleteResponse:
    """Delete an unused recurring order template."""
    db = get_schedule_db()
    _bind_order_template_log_context(template_id=template_id)

    current = db.get_order_template(template_id)
    if not current:
        raise HTTPException(
            status_code=404,
            detail=f"Order template not found: {template_id}",
        )

    _bind_order_template_log_context(
        workspace_id=current.workspace_id,
        template_id=template_id,
    )

    try:
        result = db.delete_order_template(template_id)
        if not result["template_deleted"]:
            raise HTTPException(
                status_code=404,
                detail=f"Order template not found: {template_id}",
            )

        return OrderTemplateDeleteResponse(
            success=True,
            message=f"Order template {template_id} deleted",
            template_deleted=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to delete order template %s: %s", template_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

