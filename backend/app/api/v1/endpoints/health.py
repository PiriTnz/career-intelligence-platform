from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.llm import get_provider
from app.llm.ollama import OllamaProvider

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
        ollama_ok = await OllamaProvider().health_check()
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
