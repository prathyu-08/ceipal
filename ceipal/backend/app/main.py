"""
main.py
-------
FastAPI application entry point.

- Registers CORS middleware (allows React dev server on :5173)
- Mounts all route modules
- Exposes Swagger UI at /docs and ReDoc at /redoc
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config.settings import get_settings
from app.routes import dashboard
from app.services.ceipal_service import start_priority_cache_loader

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="CEIPAL Analytics Dashboard API",
    description=(
        "Backend proxy for the CEIPAL ATS APIs. "
        "Authenticates with CEIPAL, fetches jobs / users / applicants, "
        "and returns enriched analytics data for the React dashboard."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS – allow React Vite dev server and any production origin
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite default
        "http://localhost:3000",   # CRA fallback
        "http://127.0.0.1:5173",
        "*",                        # Remove in production; add specific domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(dashboard.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "message": "CEIPAL Analytics API is running."}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """Start background priority cache loader on server boot."""
    start_priority_cache_loader()
