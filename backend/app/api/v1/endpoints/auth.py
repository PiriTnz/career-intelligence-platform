from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.limiter import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User
from app.schemas.user import LoginRequest, Token, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    existing = await db.execute(select(User).where(User.email == user_in.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        name=user_in.name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
async def login(
    request: Request,
    creds: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(User).where(User.email == creds.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(creds.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token(subject=str(user.id))
    return {"access_token": token, "token_type": "bearer", "user": user}
