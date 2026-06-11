from fastapi import APIRouter
import httpx, os

router = APIRouter()

@router.get("/health")
async def health():
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{os.getenv('OLLAMA_URL','http://ollama:11434')}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        pass
    return {"status": "ok", "ollama": ollama_ok}
