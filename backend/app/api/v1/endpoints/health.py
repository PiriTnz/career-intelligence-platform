from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.core.config import settings
from app.core.database import get_db
from app.llm import get_provider

router = APIRouter()


@router.get("/health", tags=["health"])
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    db_ok = False
    ollama_ok = False

    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags")
            ollama_ok = resp.status_code == 200
    except Exception:
        pass

    provider = get_provider()

    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "ollama": ollama_ok,
        "llm_provider": provider.provider_name,
        "llm_model": provider.model,
    }
