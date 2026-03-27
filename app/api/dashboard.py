from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
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

    total_diaries = (
        db.query(func.count(DiaryEntry.id))
        .filter(DiaryEntry.user_id == user.id)
        .scalar()
    )

    has_today = today_diary is not None
    consecutive_days = 0
    check_date = today if has_today else (today - timedelta(days=1))

    while True:
        exists = (
            db.query(DiaryEntry.id)
            .filter(DiaryEntry.user_id == user.id, DiaryEntry.entry_date == check_date)
            .first()
        )
        if not exists:
            break
        consecutive_days += 1
        check_date -= timedelta(days=1)

    diary_stats = {
        "total_diaries": int(total_diaries or 0),
        "consecutive_days": consecutive_days,
        "has_today": has_today,
    }

    return {
        "user": user,
        "today_diary": today_diary,
        "today_fortune": today_fortune,
        "today_letter": today_letter,
        "diary_stats": diary_stats,
    }