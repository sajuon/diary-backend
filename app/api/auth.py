from datetime import datetime
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
from app.models.user import User
from app.models.auth_token import AuthToken
from app.schemas.auth import RegisterRequest, UserResponse, ProfileUpdateRequest


router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="이미 가입된 이메일입니다")

    user = User(
        email=data.email,
        password=hash_password(data.password),
        nickname=data.nickname,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=400, detail="이메일 또는 비밀번호 오류")

    token = create_access_token({"user_id": user.id})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/logout")
def logout(
    token: str = Depends(oauth2_scheme),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰")

    exp = payload.get("exp")
    if exp is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰")

    expires_at = datetime.fromtimes_
