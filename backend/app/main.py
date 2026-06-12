import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.database import engine
from app.core.limiter import limiter

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Security gate: refuse to start in production with insecure defaults
    problems = settings.has_insecure_defaults()
    if problems and settings.is_production():
        msg = "STARTUP ABORTED — insecure configuration: " + "; ".join(problems)
        logger.critical(msg)
        raise RuntimeError(msg)
    if problems:
        for p in problems:
            logger.warning("INSECURE CONFIG (acceptable in dev): %s", p)

    yield
    await engine.dispose()


app = FastAPI(
    title="Career Intelligence Platform",
    description="Evidence-based AI career toolkit — CV, cover letter, interview workspace.",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — origins read from CORS_ORIGINS env var (comma-separated)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(v1_router, prefix="/api/v1")
