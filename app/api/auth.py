from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    oauth2_scheme,
)
from app.crud import user as crud_user
from app.models.user import User
from app.models.auth_token import AuthToken
from app.schemas.auth import (
    RegisterRequest,
    UserResponse,
    ProfileUpdateRequest,
    OAuthLoginRequest,
)
from app.services.oauth import get_user_info, OAuthError


router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    # 이메일은 선택 항목이 되었습니다. 전달된 경우 중복 체크 수행
    if data.email:
        existing = crud_user.get_user_by_email(db, data.email)
        if existing:
            raise HTTPException(status_code=400, detail="이미 가입된 이메일입니다")

    hashed = hash_password(data.password)
    user = crud_user.create_user(
        db,
        nickname=data.nickname,
        email=data.email,
        hashed_password=hashed,
        provider="local",
    )
    return user


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # legacy email / password login
    user = crud_user.get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.password or ""):
        raise HTTPException(status_code=400, detail="이메일 또는 비밀번호 오류")

    token = create_access_token({"user_id": user.id})
    return {"access_token": token, "token_type": "bearer"}


from app.services.oauth import get_user_info, OAuthError, get_user_info_from_code


@router.post("/oauth/exchange")
async def oauth_exchange(
    data: OAuthLoginRequest, db: Session = Depends(get_db)
):
    try:
        info = await get_user_info_from_code(data.provider, data.code, data.redirect_uri)
    except OAuthError:
        raise HTTPException(status_code=401, detail="소셜 로그인 토큰이 유효하지 않습니다")

    provider = data.provider
    provider_id = info.get("id")
    if provider_id is None:
        raise HTTPException(status_code=400, detail="Provider did not return an id")

    user = crud_user.get_user_by_provider(db, provider, provider_id)
    if not user:
        nickname = info.get("nickname") or f"{provider}_{provider_id}"
        user = crud_user.create_user(
            db,
            nickname=nickname,
            email=info.get("email"),
            provider=provider,
            provider_id=provider_id,
        )
    token = create_access_token({"user_id": user.id})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_current_user(user: User = Depends(get_current_user)):
    return user


@router.put("/profile", response_model=UserResponse)
def update_profile(
    data: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = crud_user.update_user_profile(
        db, user, nickname=data.nickname, profile_image=data.profile_image
    )
    return updated
