"""Security helpers for privileged backend surfaces."""

from __future__ import annotations

import ipaddress
import os
from typing import Optional

from fastapi import HTTPException, Request, status


def _read_bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _extract_access_token(request: Request, header_name: str) -> Optional[str]:
    authorization = request.headers.get("Authorization", "").strip()
    if authorization.lower().startswith("bearer "):
        bearer_token = authorization[7:].strip()
        if bearer_token:
            return bearer_token

    header_token = request.headers.get(header_name, "").strip()
    return header_token or None


def _is_trusted_local_client(host: Optional[str]) -> bool:
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1", "testclient", "testserver"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _require_scoped_access(
    request: Request,
    *,
    scope_name: str,
    env_var_name: str,
    header_name: str,
    allow_loopback_env_var: str,
    allow_loopback_default: bool,
) -> None:
    expected_token = os.environ.get(env_var_name, "").strip()
    presented_token = _extract_access_token(request, header_name)

    if expected_token:
        if presented_token != expected_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"{scope_name.capitalize()} token required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return

    allow_loopback = _read_bool_env(allow_loopback_env_var, allow_loopback_default)
    client_host = getattr(request.client, "host", None)
    if allow_loopback and _is_trusted_local_client(client_host):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"{scope_name.capitalize()} access is disabled for non-local clients without "
            f"{env_var_name} configured"
        ),
    )


def require_admin_access(request: Request) -> None:
    """Protect privileged admin surfaces behind loopback or an explicit token."""
    _require_scoped_access(
        request,
        scope_name="admin",
        env_var_name="MISSION_PLANNER_ADMIN_TOKEN",
        header_name="X-Admin-Token",
        allow_loopback_env_var="MISSION_PLANNER_ALLOW_LOOPBACK_ADMIN",
        allow_loopback_default=True,
    )


def require_dev_access(request: Request) -> None:
    """Protect dev-only tooling endpoints behind DEV_MODE and optional token auth."""
    if not _read_bool_env("DEV_MODE", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev endpoints are disabled (set DEV_MODE=1 to enable)",
        )

    _require_scoped_access(
        request,
        scope_name="dev",
        env_var_name="MISSION_PLANNER_DEV_TOKEN",
        header_name="X-Dev-Token",
        allow_loopback_env_var="MISSION_PLANNER_ALLOW_LOOPBACK_DEV",
        allow_loopback_default=True,
    )
