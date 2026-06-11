from fastapi import APIRouter
router = APIRouter()

@router.get("/")
async def placeholder():
    return {"message": "feedback routes — coming soon"}
