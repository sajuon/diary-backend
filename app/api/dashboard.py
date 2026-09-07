from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.diary import DiaryEntry
from app.models.fortune import DailyFortune
from app.models.letter import OtterLetter
from app.schemas.diary import DiaryEntryResponse
from app.schemas.fortune import DailyFortuneResponse
from app.schemas.letter import OtterLetterResponse
from app.schemas.auth import UserResponse
from app.services.streak import calc_streak_summary


router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def kst_today_date():
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


class DashboardResponse(BaseModel):
    user: UserResponse
    today_diary: Optional[DiaryEntryResponse] = None
    today_fortune: Optional[DailyFortuneResponse] = None
    today_letter: Optional[OtterLetterResponse] = None
    diary_stats: dict


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = kst_today_date()

    today_diary = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.user_id == user.id, DiaryEntry.entry_date == today)
        .first()
    )

    today_fortune = (
        db.query(DailyFortune)
        .filter(DailyFortune.user_id == user.id, DailyFortune.fortune_date == today)
        .first()
    )

    today_letter = (
        db.query(OtterLetter)
        .filter(OtterLetter.user_id == user.id)
        .order_by(OtterLetter.letter_date.desc(), OtterLetter.id.desc())
        .first()
    )

    summary = calc_streak_summary(db, user.id)

    diary_stats = {
        "total_diaries": summary["total_diaries"],
        "consecutive_days": summary["streak"],
        "has_today": summary["has_today"],
    }

    user_payload = {
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

    return {
        "user": user_payload,
        "today_diary": today_diary,
        "today_fortune": today_fortune,
        "today_letter": today_letter,
        "diary_stats": diary_stats,
    }