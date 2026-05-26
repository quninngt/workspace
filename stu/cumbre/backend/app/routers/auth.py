from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, ChangePasswordRequest, AuthResponse, UserResponse
from app.services.auth import hash_password, verify_password, create_token
from app.services.dependencies import get_current_user


router = APIRouter(prefix="/api/auth", tags=["auth"])

_MIN_PASSWORD_LENGTH = 8


@router.post("/register", response_model=AuthResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if len(body.password) < _MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"密码至少{_MIN_PASSWORD_LENGTH}位")

    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该邮箱已注册")

    user = User(name=body.name, email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_token(user.id)
    return AuthResponse(token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail="邮箱或密码错误")

    token = create_token(user.id)
    return AuthResponse(token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码错误")
    if len(body.new_password) < _MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"新密码至少{_MIN_PASSWORD_LENGTH}位")

    user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"ok": True}
