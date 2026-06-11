from fastapi import APIRouter, Depends

from app.api.deps import get_current_active_user
from app.db.models import User
from app.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_active_user)) -> User:
    return current_user
