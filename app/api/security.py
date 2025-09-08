from typing import Optional, Dict, Tuple

import time
from fastapi import Header, HTTPException, Request

from app.core.config import get_settings


async def require_api_key(
    request: Request, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")
) -> None:
    settings = get_settings()
    # Exempt health endpoints
    path = request.url.path or ""
    if path.endswith("/health"):
        return
    # If API key configured, require exact match
    if settings.api_key:
        supplied = x_api_key or request.cookies.get("X-API-Key") or request.cookies.get("api_key")
        if not supplied or supplied != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
    # If not configured, allow (demo mode)
    return


# Simple in-process rate limiter (per IP per minute) for critical endpoints
_rate_store: Dict[Tuple[str, str, int], int] = {}


async def rate_limit(request: Request) -> None:
    path = request.url.path
    if not (path.endswith("/deid") or path.endswith("/deid/file")):
        return
    client_ip = request.client.host if request.client else "unknown"
    minute_window = int(time.time() // 60)
    key = (client_ip, path, minute_window)
    count = _rate_store.get(key, 0) + 1
    _rate_store[key] = count
    if count > 30:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
