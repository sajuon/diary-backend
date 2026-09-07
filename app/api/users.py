from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.auth import UserResponse
from app.services.streak import calc_streak_summary


router = APIRouter(prefix="/api/users", tags=["Users"])


def _user_payload(user: User, summary: dict) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "nickname": user.nickname,
        "profile_image": getattr(user, "profile_image", None),
        "provider": user.provider,
        "provider_id": getattr(user, "provider_id", None),
        "pearls": getattr(user, "pearls", 0),
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "streak_n": summary["streak_n"],
        "has_today": summary["has_today"],
        "total_diaries": summary["total_diaries"],
    }


@router.get("/me", response_model=UserResponse)
def get_me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    summary = calc_streak_summary(db, user.id)
    return _user_payload(user, summary)


@router.post("/me/profile-image")
async def upload_profile_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")

    save_dir = os.path.join(os.getcwd(), "static", "profile_images")
    os.makedirs(save_dir, exist_ok=True)

    save_path = os.path.join(save_dir, f"user_{user.id}_{file.filename}")

    with open(save_path, "wb") as f:
        f.write(await file.read())

    rel_path = f"/static/profile_images/user_{user.id}_{file.filename}"
    user.profile_image = rel_path
    db.commit()
    db.refresh(user)

    return JSONResponse({"profile_image": rel_path})


class UpdateMeRequest(BaseModel):
    nickname: str | None = None
    profile_image: str | None = None


class AddPearlsRequest(BaseModel):
    amount: int


@router.put("/me", response_model=UserResponse)
def update_me(
    data: UpdateMeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = False

    if data.nickname is not None:
        user.nickname = data.nickname
        updated = True

    if data.profile_image is not None:
        user.profile_image = data.profile_image
        updated = True

    if updated:
        db.commit()
        db.refresh(user)

    summary = calc_streak_summary(db, user.id)
    return _user_payload(user, summary)


@router.post("/me/add-pearls", response_model=UserResponse)
def add_pearls(
    data: AddPearlsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="추가할 진주 개수는 양수여야 합니다")

    user.pearls += data.amount
    db.commit()
    db.refresh(user)

    summary = calc_streak_summary(db, user.id)
    return _user_payload(user, summary)