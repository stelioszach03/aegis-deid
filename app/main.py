from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded

from app.api.v1 import router as api_v1_router
from app.api import v1 as api_v1_module
from app.core.logging import setup_logging, get_logger
from app.core.config import get_settings
from app.deid.engine import DeidEngine, POLICY_MAP as DEFAULT_POLICY_MAP
from app.api.security import require_api_key, rate_limit
from app.core.limiter import limiter

setup_logging(component="api")
log = get_logger("api")

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS allowlist from settings (comma separated)
_cors = [o.strip() for o in (settings.cors_allow_origins or "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors or ["http://localhost", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static and templates
app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")
templates = Jinja2Templates(directory="app/ui/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    response = templates.TemplateResponse(
        "index.html",
        {"request": request, "title": settings.app_name, "version": settings.app_version},
    )
    # In dev, set an HttpOnly cookie with the API key so the browser can auth without exposing it in UI
    try:
        if (settings.app_env or "dev") == "dev" and settings.api_key:
            response.set_cookie(
                key="X-API-Key",
                value=settings.api_key,
                httponly=True,
                secure=False,
                samesite="lax",
            )
    except Exception:
        pass
    return response


# API v1 with API key dependency (health exempted by dependency itself)
app.include_router(
    api_v1_router, prefix="/api/v1", dependencies=[Depends(require_api_key), Depends(rate_limit)]
)

# (Global default limits applied; health dependency already exempt from auth.)

# Request size limit middleware (1MB default)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body_size: int = 1_000_000):
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request, call_next):
        body = await request.body()
        if len(body) > self.max_body_size:
            return JSONResponse(
                status_code=413,
                content={"detail": "Payload too large: request exceeds server body limit."},
            )

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = receive
        return await call_next(request)


app.add_middleware(BodySizeLimitMiddleware, max_body_size=settings.request_body_limit)

# Provide a default in-memory engine singleton for app state (available to routes if needed)
app.state.policy_map = {**DEFAULT_POLICY_MAP}
app.state.deid_engine = DeidEngine(
    policy_map=app.state.policy_map,
    salt=settings.deid_salt,
    default_policy=settings.deid_default_policy,
)
