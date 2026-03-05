from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.diary import DiaryEntry
from app.schemas.auth import UserResponse


router = APIRouter(prefix="/api/users", tags=["Users"])


# ---------------------------
# Utils
# ---------------------------

def kst_today_date():
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


def calc_streak_summary(db: Session, user_id: int):
    """
    요구사항에 맞춘 streak 계산:

    - has_today == False (오늘 일기 X)
      streak_n = (어제까지 연속일) + 1
      홈 문구: "오늘도 기록하면 n일 달성!"
      우측 숫자: n

    - has_today == True (오늘 일기 O)
      streak_n = (오늘 포함 연속일)
      홈 문구: "내일도 기록하면 n+1일 달성!"
      우측 숫자: n
    """

    today = kst_today_date()

    rows = (
        db.query(DiaryEntry.entry_date)
        .filter(DiaryEntry.user_id == user_id)
        .order_by(DiaryEntry.entry_date.desc())
        .all()
    )
    dates = [r[0] for r in rows]
    date_set = set(dates)

    has_today = today in date_set
    total_diaries = len(dates)

    # 연속 체크 시작점
    start = today if has_today else (today - timedelta(days=1))

    streak = 0
    d = start
    while d in date_set:
        streak += 1
        d -= timedelta(days=1)

    # 화면에 찍힐 n
    streak_n = streak if has_today else (streak + 1)

    return {
        "streak_n": streak_n,
        "has_today": has_today,
        "total_diaries": total_diaries,
    }


# ---------------------------
# Endpoints
# ---------------------------

@router.get("/me", response_model=UserResponse)
def get_me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    summary = calc_streak_summary(db, user.id)

    # UserResponse는 from_attributes=True지만,
    # 추가 필드를 붙이려면 dict 형태로 반환하는 게 안전함.
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
        **summary,
    }


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

    # update 후에도 streak 붙여서 반환(프론트 동기화 편함)
    summary = calc_streak_summary(db, user.id)
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
        **summary,
    }


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

    # add 후에도 streak 붙여서 반환
    summary = calc_streak_summary(db, user.id)
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
        **summary,
    }