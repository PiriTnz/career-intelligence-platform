from fastapi import APIRouter
router = APIRouter()

@router.get("/")
async def list_profiles():
    return {"message": "profile routes — coming in Phase 1"}
